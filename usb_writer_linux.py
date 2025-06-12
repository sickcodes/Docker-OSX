# usb_writer_linux.py (Refined asset copying)
import subprocess
import os
import time
import shutil
import glob
import re
import plistlib

try:
    from plist_modifier import enhance_config_plist
except ImportError:
    enhance_config_plist = None
    print("Warning: plist_modifier.py not found. Plist enhancement feature will be disabled for USBWriterLinux.")

OC_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "EFI_template_installer")


class USBWriterLinux:
    def __init__(self, device: str, macos_download_path: str,
                 progress_callback=None, enhance_plist_enabled: bool = False,
                 target_macos_version: str = ""): # target_macos_version is display name e.g. "Sonoma"
        self.device = device
        self.macos_download_path = macos_download_path
        self.progress_callback = progress_callback
        self.enhance_plist_enabled = enhance_plist_enabled
        self.target_macos_version = target_macos_version

        pid = os.getpid()
        self.temp_basesystem_hfs_path = f"temp_basesystem_{pid}.hfs"
        self.temp_efi_build_dir = f"temp_efi_build_{pid}"
        self.temp_dmg_extract_dir = f"temp_dmg_extract_{pid}" # For extracting HFS from DMG

        self.mount_point_usb_esp = f"/mnt/usb_esp_temp_skyscope_{pid}"
        self.mount_point_usb_macos_target = f"/mnt/usb_macos_target_temp_skyscope_{pid}"

        self.temp_files_to_clean = [self.temp_basesystem_hfs_path]
        self.temp_dirs_to_clean = [
            self.temp_efi_build_dir, self.mount_point_usb_esp,
            self.mount_point_usb_macos_target, self.temp_dmg_extract_dir
        ]

    def _report_progress(self, message: str):
        if self.progress_callback: self.progress_callback(message)
        else: print(message)

    def _run_command(self, command: list[str] | str, check=True, capture_output=False, timeout=None, shell=False, working_dir=None):
        self._report_progress(f"Executing: {command if isinstance(command, str) else ' '.join(command)}")
        try:
            process = subprocess.run(
                command, check=check, capture_output=capture_output, text=True, timeout=timeout,
                shell=shell, cwd=working_dir,
                creationflags=0
            )
            if capture_output:
                if process.stdout and process.stdout.strip(): self._report_progress(f"STDOUT: {process.stdout.strip()}")
                if process.stderr and process.stderr.strip(): self._report_progress(f"STDERR: {process.stderr.strip()}")
            return process
        except subprocess.TimeoutExpired: self._report_progress(f"Command timed out after {timeout} seconds."); raise
        except subprocess.CalledProcessError as e: self._report_progress(f"Error executing (code {e.returncode}): {e.stderr or e.stdout or str(e)}"); raise
        except FileNotFoundError: self._report_progress(f"Error: Command '{command[0] if isinstance(command, list) else command.split()[0]}' not found."); raise

    def _cleanup_temp_files_and_dirs(self):
        self._report_progress("Cleaning up temporary files and directories...")
        for mp in self.temp_dirs_to_clean:
            if os.path.ismount(mp):
                self._run_command(["sudo", "umount", "-lf", mp], check=False, timeout=15)

        for f_path in self.temp_files_to_clean:
            if os.path.exists(f_path):
                try: self._run_command(["sudo", "rm", "-f", f_path], check=False)
                except Exception as e: self._report_progress(f"Error removing temp file {f_path}: {e}")
        for d_path in self.temp_dirs_to_clean:
            if os.path.exists(d_path):
                try: self._run_command(["sudo", "rm", "-rf", d_path], check=False)
                except Exception as e: self._report_progress(f"Error removing temp dir {d_path}: {e}")

    def check_dependencies(self):
        self._report_progress("Checking dependencies (sgdisk, mkfs.vfat, mkfs.hfsplus, 7z, rsync, dd)...")
        dependencies = ["sgdisk", "mkfs.vfat", "mkfs.hfsplus", "7z", "rsync", "dd"]
        missing_deps = [dep for dep in dependencies if not shutil.which(dep)]
        if missing_deps:
            msg = f"Missing dependencies: {', '.join(missing_deps)}. Please install them (e.g., hfsprogs, p7zip-full, gdisk)."
            self._report_progress(msg); raise RuntimeError(msg)
        self._report_progress("All critical dependencies for Linux USB installer creation found.")
        return True

    def _get_gibmacos_product_folder(self) -> str:
        """Heuristically finds the main product folder within gibMacOS downloads."""
        # gibMacOS often creates .../publicrelease/XXX - macOS [VersionName] [VersionNum]/
        # We need to find this folder.
        _report = self._report_progress
        _report(f"Searching for macOS product folder in {self.macos_download_path} for version {self.target_macos_version}")

        version_parts = self.target_macos_version.split(" ") # e.g., "Sonoma" or "Mac OS X", "High Sierra"
        primary_name = version_parts[0] # "Sonoma", "Mac", "High"
        if primary_name == "Mac" and len(version_parts) > 2 and version_parts[1] == "OS": # "Mac OS X"
            primary_name = "OS X"
            if len(version_parts) > 2 and version_parts[2] == "X": primary_name = "OS X" # For "Mac OS X"

        possible_folders = []
        for root, dirs, _ in os.walk(self.macos_download_path):
            for d_name in dirs:
                # Check if directory name contains "macOS" and a part of the target version name/number
                if "macOS" in d_name and (primary_name in d_name or self.target_macos_version in d_name):
                    possible_folders.append(os.path.join(root, d_name))

        if not possible_folders:
            _report(f"Could not automatically determine specific product folder. Using base download path: {self.macos_download_path}")
            return self.macos_download_path

        # Prefer shorter paths or more specific matches if multiple found
        # This heuristic might need refinement. For now, take the first plausible one.
        _report(f"Found potential product folder(s): {possible_folders}. Using: {possible_folders[0]}")
        return possible_folders[0]

    def _find_gibmacos_asset(self, asset_patterns: list[str] | str, product_folder: str, description: str) -> str | None:
        """Finds the first existing file matching a list of glob patterns within the product_folder."""
        if isinstance(asset_patterns, str): asset_patterns = [asset_patterns]
        self._report_progress(f"Searching for {description} using patterns {asset_patterns} in {product_folder}...")
        for pattern in asset_patterns:
            # Search both in root of product_folder and common subdirs like "SharedSupport" or "*.app/Contents/SharedSupport"
            search_glob_patterns = [
                os.path.join(product_folder, pattern),
                os.path.join(product_folder, "**", pattern), # Recursive search
            ]
            for glob_pattern in search_glob_patterns:
                found_files = glob.glob(glob_pattern, recursive=True)
                if found_files:
                    # Sort to get a predictable one if multiple (e.g. if pattern is too generic)
                    # Prefer files not too deep in structure if multiple found by simple pattern
                    found_files.sort(key=lambda x: (x.count(os.sep), len(x)))
                    self._report_progress(f"Found {description} at: {found_files[0]}")
                    return found_files[0]
        self._report_progress(f"Warning: {description} not found with patterns: {asset_patterns} in {product_folder} or its subdirectories.")
        return None

    def _extract_basesystem_hfs_from_source(self, source_dmg_path: str, output_hfs_path: str) -> bool:
        """Extracts the primary HFS+ partition image (e.g., '4.hfs') from a source DMG (BaseSystem.dmg or InstallESD.dmg)."""
        os.makedirs(self.temp_dmg_extract_dir, exist_ok=True)
        try:
            self._report_progress(f"Extracting HFS+ partition image from {source_dmg_path} into {self.temp_dmg_extract_dir}...")
            # 7z e -tdmg <dmg_path> *.hfs -o<output_dir_for_hfs> (usually 4.hfs or similar for BaseSystem)
            # For InstallESD.dmg, it might be a different internal path or structure.
            # Assuming the target is a standard BaseSystem.dmg or a DMG containing such structure.
            self._run_command(["7z", "e", "-tdmg", source_dmg_path, "*.hfs", f"-o{self.temp_dmg_extract_dir}"], check=True)

            hfs_files = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*.hfs"))
            if not hfs_files:
                # Fallback: try extracting * (if only one file inside a simple DMG, like some custom BaseSystem.dmg)
                self._run_command(["7z", "e", "-tdmg", source_dmg_path, "*", f"-o{self.temp_dmg_extract_dir}"], check=True)
                hfs_files = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*")) # Check all files
                hfs_files = [f for f in hfs_files if not f.endswith((".xml", ".chunklist", ".plist")) and os.path.getsize(f) > 100*1024*1024] # Filter out small/meta files

            if not hfs_files: raise RuntimeError(f"No suitable .hfs image found after extracting {source_dmg_path}")

            final_hfs_file = max(hfs_files, key=os.path.getsize) # Assume largest is the one
            self._report_progress(f"Found HFS+ partition image: {final_hfs_file}. Moving to {output_hfs_path}")
            shutil.move(final_hfs_file, output_hfs_path) # Use shutil.move for local files
            return True
        except Exception as e:
            self._report_progress(f"Error during HFS extraction from DMG: {e}\n{traceback.format_exc()}")
            return False
        finally:
            if os.path.exists(self.temp_dmg_extract_dir): shutil.rmtree(self.temp_dmg_extract_dir, ignore_errors=True)

    def format_and_write(self) -> bool:
        try:
            self.check_dependencies()
            self._cleanup_temp_files_and_dirs()
            for mp in [self.mount_point_usb_esp, self.mount_point_usb_macos_target, self.temp_efi_build_dir]:
                self._run_command(["sudo", "mkdir", "-p", mp])

            self._report_progress(f"WARNING: ALL DATA ON {self.device} WILL BE ERASED!")
            for i in range(1, 10): self._run_command(["sudo", "umount", "-lf", f"{self.device}{i}"], check=False, timeout=5); self._run_command(["sudo", "umount", "-lf", f"{self.device}p{i}"], check=False, timeout=5)

            self._report_progress(f"Partitioning {self.device} with GPT (sgdisk)...")
            self._run_command(["sudo", "sgdisk", "--zap-all", self.device])
            self._run_command(["sudo", "sgdisk", "-n", "1:0:+550M", "-t", "1:ef00", "-c", "1:EFI", self.device])
            self._run_command(["sudo", "sgdisk", "-n", "2:0:0",    "-t", "2:af00", "-c", f"2:Install macOS {self.target_macos_version}", self.device])
            self._run_command(["sudo", "partprobe", self.device], timeout=10); time.sleep(3)

            esp_partition_dev = next((f"{self.device}{i}" for i in ["1", "p1"] if os.path.exists(f"{self.device}{i}")), None)
            macos_partition_dev = next((f"{self.device}{i}" for i in ["2", "p2"] if os.path.exists(f"{self.device}{i}")), None)
            if not (esp_partition_dev and macos_partition_dev): raise RuntimeError(f"Could not reliably determine partition names for {self.device}.")

            self._report_progress(f"Formatting ESP ({esp_partition_dev}) as FAT32...")
            self._run_command(["sudo", "mkfs.vfat", "-F", "32", "-n", "EFI", esp_partition_dev])
            self._report_progress(f"Formatting macOS Install partition ({macos_partition_dev}) as HFS+...")
            self._run_command(["sudo", "mkfs.hfsplus", "-v", f"Install macOS {self.target_macos_version}", macos_partition_dev])

            # --- Prepare macOS Installer Content ---
            product_folder = self._get_gibmacos_product_folder()

            # Find BaseSystem.dmg (or equivalent like InstallESD.dmg if BaseSystem.dmg is not directly available)
            # Some gibMacOS downloads might have InstallESD.dmg which contains BaseSystem.dmg.
            # Others might have BaseSystem.dmg directly.
            source_for_hfs_extraction = self._find_gibmacos_asset(["BaseSystem.dmg", "InstallESD.dmg", "SharedSupport.dmg"], product_folder, "BaseSystem.dmg (or source like InstallESD.dmg/SharedSupport.dmg)")
            if not source_for_hfs_extraction: raise RuntimeError("Essential macOS DMG for BaseSystem extraction not found in download path.")

            self._report_progress("Extracting bootable HFS+ image from source DMG...")
            if not self._extract_basesystem_hfs_from_source(source_for_hfs_extraction, self.temp_basesystem_hfs_path):
                raise RuntimeError("Failed to extract HFS+ image from source DMG.")

            self._report_progress(f"Writing BaseSystem HFS+ image to {macos_partition_dev} using dd...")
            self._run_command(["sudo", "dd", f"if={self.temp_basesystem_hfs_path}", f"of={macos_partition_dev}", "bs=4M", "status=progress", "oflag=sync"])

            self._report_progress("Mounting macOS Install partition on USB...")
            self._run_command(["sudo", "mount", macos_partition_dev, self.mount_point_usb_macos_target])

            core_services_path_usb = os.path.join(self.mount_point_usb_macos_target, "System", "Library", "CoreServices")
            self._run_command(["sudo", "mkdir", "-p", core_services_path_usb])

            # Copy original BaseSystem.dmg and .chunklist from gibMacOS output
            original_bs_dmg = self._find_gibmacos_asset(["BaseSystem.dmg"], product_folder, "original BaseSystem.dmg")
            if original_bs_dmg:
                self._report_progress(f"Copying {original_bs_dmg} to {core_services_path_usb}/BaseSystem.dmg")
                self._run_command(["sudo", "cp", original_bs_dmg, os.path.join(core_services_path_usb, "BaseSystem.dmg")])
                original_bs_chunklist = original_bs_dmg.replace(".dmg", ".chunklist")
                if os.path.exists(original_bs_chunklist):
                    self._report_progress(f"Copying {original_bs_chunklist} to {core_services_path_usb}/BaseSystem.chunklist")
                    self._run_command(["sudo", "cp", original_bs_chunklist, os.path.join(core_services_path_usb, "BaseSystem.chunklist")])
            else: self._report_progress("Warning: Original BaseSystem.dmg not found in product folder to copy to CoreServices.")

            install_info_src = self._find_gibmacos_asset(["InstallInfo.plist"], product_folder, "InstallInfo.plist")
            if install_info_src:
                self._report_progress(f"Copying {install_info_src} to {self.mount_point_usb_macos_target}/InstallInfo.plist")
                self._run_command(["sudo", "cp", install_info_src, os.path.join(self.mount_point_usb_macos_target, "InstallInfo.plist")])
            else: self._report_progress("Warning: InstallInfo.plist not found in product folder.")

            # Copy Packages and other assets
            packages_target_path = os.path.join(self.mount_point_usb_macos_target, "System", "Installation", "Packages")
            self._run_command(["sudo", "mkdir", "-p", packages_target_path])

            # Try to find and copy InstallAssistant.pkg or InstallESD.dmg/SharedSupport.dmg contents for packages
            # This part is complex, as gibMacOS output varies.
            # If InstallAssistant.pkg is found, its contents (especially packages) are needed.
            # If SharedSupport.dmg is found, its contents are needed.
            install_assistant_pkg = self._find_gibmacos_asset(["InstallAssistant.pkg"], product_folder, "InstallAssistant.pkg")
            if install_assistant_pkg:
                 self._report_progress(f"Copying contents of InstallAssistant.pkg (Packages) from {os.path.dirname(install_assistant_pkg)} to {packages_target_path} (simplified, may need selective copy)")
                 # This is a placeholder. Real logic would extract from PKG or copy specific subfolders/files.
                 # For now, just copy the PKG itself as an example.
                 self._run_command(["sudo", "cp", install_assistant_pkg, packages_target_path])
            else:
                shared_support_dmg = self._find_gibmacos_asset(["SharedSupport.dmg"], product_folder, "SharedSupport.dmg for packages")
                if shared_support_dmg:
                    self._report_progress(f"Copying contents of SharedSupport.dmg from {shared_support_dmg} to {packages_target_path} (simplified)")
                    # Mount SharedSupport.dmg and rsync contents, or 7z extract and rsync
                    # Placeholder: copy the DMG itself. Real solution needs extraction.
                    self._run_command(["sudo", "cp", shared_support_dmg, packages_target_path])
                else:
                    self._report_progress("Warning: Neither InstallAssistant.pkg nor SharedSupport.dmg found for main packages. Installer may be incomplete.")

            # Create 'Install macOS [Version].app' structure (simplified)
            app_name = f"Install macOS {self.target_macos_version}.app"
            app_path_usb = os.path.join(self.mount_point_usb_macos_target, app_name)
            self._run_command(["sudo", "mkdir", "-p", os.path.join(app_path_usb, "Contents", "SharedSupport")])
            # Copying some key files into this structure might be needed too.

            # --- OpenCore EFI Setup --- (same as before, but using self.temp_efi_build_dir)
            self._report_progress("Setting up OpenCore EFI on ESP...")
            if not os.path.isdir(OC_TEMPLATE_DIR): self._report_progress(f"FATAL: OpenCore template dir not found: {OC_TEMPLATE_DIR}"); return False

            self._report_progress(f"Copying OpenCore EFI template from {OC_TEMPLATE_DIR} to {self.temp_efi_build_dir}")
            self._run_command(["sudo", "cp", "-a", f"{OC_TEMPLATE_DIR}/.", self.temp_efi_build_dir])

            temp_config_plist_path = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config.plist")
            # If template is config-template.plist, rename it for enhancement
            if not os.path.exists(temp_config_plist_path) and os.path.exists(os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist")):
                self._run_command(["sudo", "mv", os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist"), temp_config_plist_path])

            if self.enhance_plist_enabled and enhance_config_plist and os.path.exists(temp_config_plist_path):
                self._report_progress("Attempting to enhance config.plist...")
                if enhance_config_plist(temp_config_plist_path, self.target_macos_version, self._report_progress): self._report_progress("config.plist enhancement successful.")
                else: self._report_progress("config.plist enhancement failed or had issues.")

            self._run_command(["sudo", "mount", esp_partition_dev, self.mount_point_usb_esp])
            self._report_progress(f"Copying final EFI folder to USB ESP ({self.mount_point_usb_esp})...")
            self._run_command(["sudo", "rsync", "-avh", "--delete", f"{self.temp_efi_build_dir}/EFI/", f"{self.mount_point_usb_esp}/EFI/"])

            self._report_progress("USB Installer creation process completed successfully.")
            return True

        except Exception as e:
            self._report_progress(f"An error occurred during USB writing: {e}\n{traceback.format_exc()}")
            return False
        finally:
            self._cleanup_temp_files_and_dirs()

if __name__ == '__main__':
    if os.geteuid() != 0: print("Please run this script as root (sudo) for testing."); exit(1)
    print("USB Writer Linux Standalone Test - Installer Method (Refined)")

    mock_download_dir = f"temp_macos_download_test_{os.getpid()}"
    os.makedirs(mock_download_dir, exist_ok=True)

    # Create a more structured mock download similar to gibMacOS output
    product_name_slug = f"000-00000 - macOS {sys.argv[1] if len(sys.argv) > 1 else 'Sonoma'} 14.0" # Example
    specific_product_folder = os.path.join(mock_download_dir, "publicrelease", product_name_slug)
    os.makedirs(specific_product_folder, exist_ok=True)

    # Mock BaseSystem.dmg (tiny, not functional, for path testing)
    dummy_bs_dmg_path = os.path.join(specific_product_folder, "BaseSystem.dmg")
    if not os.path.exists(dummy_bs_dmg_path):
        with open(dummy_bs_dmg_path, "wb") as f: f.write(os.urandom(1024*10)) # 10KB dummy

    # Mock BaseSystem.chunklist
    dummy_bs_chunklist_path = os.path.join(specific_product_folder, "BaseSystem.chunklist")
    if not os.path.exists(dummy_bs_chunklist_path):
        with open(dummy_bs_chunklist_path, "w") as f: f.write("dummy chunklist")

    # Mock InstallInfo.plist
    dummy_installinfo_path = os.path.join(specific_product_folder, "InstallInfo.plist")
    if not os.path.exists(dummy_installinfo_path):
        with open(dummy_installinfo_path, "w") as f: plistlib.dump({"DummyInstallInfo": True}, f)

    # Mock InstallAssistant.pkg (empty for now, just to test its presence)
    dummy_pkg_path = os.path.join(specific_product_folder, "InstallAssistant.pkg")
    if not os.path.exists(dummy_pkg_path):
        with open(dummy_pkg_path, "wb") as f: f.write(os.urandom(1024))


    if not os.path.exists(OC_TEMPLATE_DIR): os.makedirs(OC_TEMPLATE_DIR)
    if not os.path.exists(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC")): os.makedirs(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC"))
    dummy_config_template_path = os.path.join(OC_TEMPLATE_DIR, "EFI", "OC", "config.plist")
    if not os.path.exists(dummy_config_template_path):
         with open(dummy_config_template_path, "w") as f: f.write("<plist><dict><key>TestTemplate</key><true/></dict></plist>")

    print("\nAvailable block devices (be careful!):")
    subprocess.run(["lsblk", "-d", "-o", "NAME,SIZE,MODEL"], check=True)
    test_device = input("\nEnter target device (e.g., /dev/sdX). THIS DEVICE WILL BE WIPED: ")

    if not test_device or not test_device.startswith("/dev/"):
        print("Invalid device. Exiting.")
    else:
        confirm = input(f"Are you absolutely sure you want to wipe {test_device} and create installer? (yes/NO): ")
        success = False
        if confirm.lower() == 'yes':
            writer = USBWriterLinux(
                device=test_device,
                macos_download_path=mock_download_dir, # Pass base download dir
                progress_callback=print,
                enhance_plist_enabled=True,
                target_macos_version=sys.argv[1] if len(sys.argv) > 1 else "Sonoma"
            )
            success = writer.format_and_write()
        else: print("Test cancelled by user.")
        print(f"Test finished. Success: {success}")

    if os.path.exists(mock_download_dir): shutil.rmtree(mock_download_dir, ignore_errors=True)
    print("Mock download dir cleaned up.")
