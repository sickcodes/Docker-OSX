# usb_writer_linux.py (Significant Refactoring for Installer Creation)
import subprocess
import os
import time
import shutil
import glob
import re
import plistlib # For plist_modifier call, and potentially for InstallInfo.plist

try:
    from plist_modifier import enhance_config_plist
except ImportError:
    enhance_config_plist = None
    print("Warning: plist_modifier.py not found. Plist enhancement feature will be disabled for USBWriterLinux.")

# Assume a basic OpenCore EFI template directory exists relative to this script
OC_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "EFI_template_installer")


class USBWriterLinux:
    def __init__(self, device: str, macos_download_path: str,
                 progress_callback=None, enhance_plist_enabled: bool = False,
                 target_macos_version: str = ""):
        self.device = device
        self.macos_download_path = macos_download_path
        self.progress_callback = progress_callback
        self.enhance_plist_enabled = enhance_plist_enabled
        self.target_macos_version = target_macos_version # String name like "Sonoma"

        pid = os.getpid()
        self.temp_basesystem_hfs_path = f"temp_basesystem_{pid}.hfs"
        self.temp_efi_build_dir = f"temp_efi_build_{pid}"
        self.temp_shared_support_extract_dir = f"temp_shared_support_extract_{pid}"


        self.mount_point_usb_esp = f"/mnt/usb_esp_temp_skyscope_{pid}"
        self.mount_point_usb_macos_target = f"/mnt/usb_macos_target_temp_skyscope_{pid}"

        self.temp_files_to_clean = [self.temp_basesystem_hfs_path]
        self.temp_dirs_to_clean = [
            self.temp_efi_build_dir, self.mount_point_usb_esp,
            self.mount_point_usb_macos_target, self.temp_shared_support_extract_dir
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
                creationflags=0 # No CREATE_NO_WINDOW on Linux
            )
            if capture_output: # Log only if content exists
                if process.stdout and process.stdout.strip(): self._report_progress(f"STDOUT: {process.stdout.strip()}")
                if process.stderr and process.stderr.strip(): self._report_progress(f"STDERR: {process.stderr.strip()}")
            return process
        except subprocess.TimeoutExpired: self._report_progress(f"Command timed out after {timeout} seconds."); raise
        except subprocess.CalledProcessError as e: self._report_progress(f"Error executing (code {e.returncode}): {e.stderr or e.stdout or str(e)}"); raise
        except FileNotFoundError: self._report_progress(f"Error: Command '{command[0] if isinstance(command, list) else command.split()[0]}' not found."); raise

    def _cleanup_temp_files_and_dirs(self):
        self._report_progress("Cleaning up temporary files and directories...")
        for mp in self.temp_dirs_to_clean: # Unmount first
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
            msg = f"Missing dependencies: {', '.join(missing_deps)}. Please install them (e.g., hfsprogs, p7zip-full)."
            self._report_progress(msg); raise RuntimeError(msg)
        self._report_progress("All critical dependencies for Linux USB installer creation found.")
        return True

    def _find_source_file(self, patterns: list[str], description: str) -> str | None:
        """Finds the first existing file matching a list of glob patterns within self.macos_download_path."""
        self._report_progress(f"Searching for {description} in {self.macos_download_path}...")
        for pattern in patterns:
            # Using iglob for efficiency if many files, but glob is fine for fewer expected matches
            found_files = glob.glob(os.path.join(self.macos_download_path, "**", pattern), recursive=True)
            if found_files:
                # Prefer files not inside .app bundles if multiple are found, unless it's the app itself.
                # This is a simple heuristic.
                non_app_files = [f for f in found_files if ".app/" not in f]
                target_file = non_app_files[0] if non_app_files else found_files[0]
                self._report_progress(f"Found {description} at: {target_file}")
                return target_file
        self._report_progress(f"Warning: {description} not found with patterns: {patterns}")
        return None

    def _extract_hfs_from_dmg(self, dmg_path: str, output_hfs_path: str) -> bool:
        """Extracts the primary HFS+ partition image (e.g., '4.hfs') from a DMG."""
        # Assumes BaseSystem.dmg or similar that contains a HFS+ partition image.
        temp_extract_dir = f"temp_hfs_extract_{os.getpid()}"
        os.makedirs(temp_extract_dir, exist_ok=True)
        try:
            self._report_progress(f"Extracting HFS+ partition image from {dmg_path}...")
            # 7z e -tdmg <dmg_path> *.hfs -o<output_dir_for_hfs> (usually 4.hfs or similar)
            self._run_command(["7z", "e", "-tdmg", dmg_path, "*.hfs", f"-o{temp_extract_dir}"], check=True)

            hfs_files = glob.glob(os.path.join(temp_extract_dir, "*.hfs"))
            if not hfs_files: raise RuntimeError(f"No .hfs file found after extracting {dmg_path}")

            final_hfs_file = max(hfs_files, key=os.path.getsize) # Assume largest is the one
            self._report_progress(f"Found HFS+ partition image: {final_hfs_file}. Moving to {output_hfs_path}")
            shutil.move(final_hfs_file, output_hfs_path)
            return True
        except Exception as e:
            self._report_progress(f"Error during HFS extraction from DMG: {e}")
            return False
        finally:
            if os.path.exists(temp_extract_dir): shutil.rmtree(temp_extract_dir, ignore_errors=True)

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
            self._run_command(["sudo", "sgdisk", "-n", "2:0:0",    "-t", "2:af00", "-c", "2:Install macOS", self.device])
            self._run_command(["sudo", "partprobe", self.device], timeout=10); time.sleep(3)

            esp_partition_dev = next((f"{self.device}{i}" for i in ["1", "p1"] if os.path.exists(f"{self.device}{i}")), None)
            macos_partition_dev = next((f"{self.device}{i}" for i in ["2", "p2"] if os.path.exists(f"{self.device}{i}")), None)
            if not (esp_partition_dev and macos_partition_dev): raise RuntimeError(f"Could not reliably determine partition names for {self.device}.")

            self._report_progress(f"Formatting ESP ({esp_partition_dev}) as FAT32...")
            self._run_command(["sudo", "mkfs.vfat", "-F", "32", "-n", "EFI", esp_partition_dev])
            self._report_progress(f"Formatting macOS Install partition ({macos_partition_dev}) as HFS+...")
            self._run_command(["sudo", "mkfs.hfsplus", "-v", f"Install macOS {self.target_macos_version}", macos_partition_dev])

            # --- Prepare macOS Installer Content ---
            basesystem_dmg_path = self._find_source_file(["BaseSystem.dmg", "InstallAssistant.pkg", "SharedSupport.dmg"], "BaseSystem.dmg or InstallAssistant.pkg or SharedSupport.dmg")
            if not basesystem_dmg_path: raise RuntimeError("Essential macOS installer DMG/PKG not found in download path.")

            if basesystem_dmg_path.endswith(".pkg") or "SharedSupport.dmg" in os.path.basename(basesystem_dmg_path) :
                # If we found InstallAssistant.pkg or SharedSupport.dmg, we need to extract BaseSystem.hfs from it.
                self._report_progress(f"Extracting bootable HFS+ image from {basesystem_dmg_path}...")
                if not self._extract_hfs_from_dmg(basesystem_dmg_path, self.temp_basesystem_hfs_path):
                    raise RuntimeError("Failed to extract HFS+ image from installer assets.")
            elif basesystem_dmg_path.endswith("BaseSystem.dmg"): # If it's BaseSystem.dmg directly
                 self._report_progress(f"Extracting bootable HFS+ image from {basesystem_dmg_path}...")
                 if not self._extract_hfs_from_dmg(basesystem_dmg_path, self.temp_basesystem_hfs_path):
                    raise RuntimeError("Failed to extract HFS+ image from BaseSystem.dmg.")
            else:
                raise RuntimeError(f"Unsupported file type for BaseSystem extraction: {basesystem_dmg_path}")


            self._report_progress(f"Writing BaseSystem HFS+ image to {macos_partition_dev} using dd...")
            self._run_command(["sudo", "dd", f"if={self.temp_basesystem_hfs_path}", f"of={macos_partition_dev}", "bs=4M", "status=progress", "oflag=sync"])

            self._report_progress("Mounting macOS Install partition on USB...")
            self._run_command(["sudo", "mount", macos_partition_dev, self.mount_point_usb_macos_target])

            # Copy BaseSystem.dmg & .chunklist to /System/Library/CoreServices/
            core_services_path_usb = os.path.join(self.mount_point_usb_macos_target, "System", "Library", "CoreServices")
            self._run_command(["sudo", "mkdir", "-p", core_services_path_usb])

            # Find original BaseSystem.dmg and chunklist in download path to copy them
            actual_bs_dmg = self._find_source_file(["BaseSystem.dmg"], "original BaseSystem.dmg for copying")
            if actual_bs_dmg:
                self._report_progress(f"Copying {actual_bs_dmg} to {core_services_path_usb}/BaseSystem.dmg")
                self._run_command(["sudo", "cp", actual_bs_dmg, os.path.join(core_services_path_usb, "BaseSystem.dmg")])

                bs_chunklist = actual_bs_dmg.replace(".dmg", ".chunklist")
                if os.path.exists(bs_chunklist):
                    self._report_progress(f"Copying {bs_chunklist} to {core_services_path_usb}/BaseSystem.chunklist")
                    self._run_command(["sudo", "cp", bs_chunklist, os.path.join(core_services_path_usb, "BaseSystem.chunklist")])
                else: self._report_progress(f"Warning: BaseSystem.chunklist not found at {bs_chunklist}")
            else: self._report_progress("Warning: Could not find original BaseSystem.dmg in download path to copy to CoreServices.")

            # Copy InstallInfo.plist
            install_info_src = self._find_source_file(["InstallInfo.plist"], "InstallInfo.plist")
            if install_info_src:
                self._report_progress(f"Copying {install_info_src} to {self.mount_point_usb_macos_target}/InstallInfo.plist")
                self._run_command(["sudo", "cp", install_info_src, os.path.join(self.mount_point_usb_macos_target, "InstallInfo.plist")])
            else: self._report_progress("Warning: InstallInfo.plist not found in download path.")

            # Copy Packages (placeholder - needs more specific logic based on gibMacOS output structure)
            self._report_progress("Placeholder: Copying macOS installation packages to USB (e.g., /System/Installation/Packages)...")
            # Example: sudo rsync -a /path/to/downloaded_packages_dir/ /mnt/usb_macos_target/System/Installation/Packages/
            # This needs to correctly identify the source Packages directory from gibMacOS output.
            # For now, we'll skip actual copying of packages folder, as its location and content can vary.
            # A proper implementation would require inspecting the gibMacOS download structure.
            # Create the directory though:
            self._run_command(["sudo", "mkdir", "-p", os.path.join(self.mount_point_usb_macos_target, "System", "Installation", "Packages")])


            # --- OpenCore EFI Setup ---
            self._report_progress("Setting up OpenCore EFI on ESP...")
            if not os.path.isdir(OC_TEMPLATE_DIR):
                self._report_progress(f"FATAL: OpenCore template directory not found at {OC_TEMPLATE_DIR}. Cannot proceed."); return False

            self._report_progress(f"Copying OpenCore EFI template from {OC_TEMPLATE_DIR} to {self.temp_efi_build_dir}")
            self._run_command(["sudo", "cp", "-a", f"{OC_TEMPLATE_DIR}/.", self.temp_efi_build_dir]) # Copy contents

            temp_config_plist_path = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config.plist") # Assume template is named config.plist
            if not os.path.exists(temp_config_plist_path) and os.path.exists(os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist")):
                # If template is config-template.plist, rename it for enhancement
                shutil.move(os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist"), temp_config_plist_path)

            if self.enhance_plist_enabled and enhance_config_plist and os.path.exists(temp_config_plist_path):
                self._report_progress("Attempting to enhance config.plist...")
                if enhance_config_plist(temp_config_plist_path, self.target_macos_version, self._report_progress):
                    self._report_progress("config.plist enhancement successful.")
                else: self._report_progress("config.plist enhancement failed or had issues. Continuing with (potentially original template) plist.")

            self._run_command(["sudo", "mount", esp_partition_dev, self.mount_point_usb_esp])
            self._report_progress(f"Copying final EFI folder to USB ESP ({self.mount_point_usb_esp})...")
            self._run_command(["sudo", "rsync", "-avh", "--delete", f"{self.temp_efi_build_dir}/EFI/", f"{self.mount_point_usb_esp}/EFI/"])

            self._report_progress("USB Installer creation process completed successfully.")
            return True

        except Exception as e:
            self._report_progress(f"An error occurred during USB writing: {e}")
            import traceback; self._report_progress(traceback.format_exc())
            return False
        finally:
            self._cleanup_temp_files_and_dirs()

if __name__ == '__main__':
    if os.geteuid() != 0: print("Please run this script as root (sudo) for testing."); exit(1)
    print("USB Writer Linux Standalone Test - Installer Method")

    mock_download_dir = f"temp_macos_download_test_{os.getpid()}"
    os.makedirs(mock_download_dir, exist_ok=True)

    # Create a dummy placeholder for what gibMacOS might download
    # This is highly simplified. A real gibMacOS download has a complex structure.
    # For this test, we'll simulate having BaseSystem.dmg and InstallInfo.plist
    mock_install_data_path = os.path.join(mock_download_dir, "macOS_Install_Data") # Simplified path
    os.makedirs(mock_install_data_path, exist_ok=True)
    dummy_bs_dmg_path = os.path.join(mock_install_data_path, "BaseSystem.dmg")
    dummy_installinfo_path = os.path.join(mock_download_dir, "InstallInfo.plist") # Often at root of a specific product download

    if not os.path.exists(dummy_bs_dmg_path):
        # Create a tiny dummy file for 7z to "extract" from.
        # To make _extract_hfs_from_dmg work, it needs a real DMG with a HFS part.
        # This is hard to mock simply. For now, it will likely fail extraction.
        # A better mock would be a small, actual DMG with a tiny HFS file.
        print(f"Creating dummy BaseSystem.dmg at {dummy_bs_dmg_path} (will likely fail HFS extraction in test without a real DMG structure)")
        with open(dummy_bs_dmg_path, "wb") as f: f.write(os.urandom(1024*10)) # 10KB dummy
    if not os.path.exists(dummy_installinfo_path):
        with open(dummy_installinfo_path, "w") as f: f.write("<plist><dict><key>DummyInstallInfo</key><true/></dict></plist>")

    # Create dummy EFI template
    if not os.path.exists(OC_TEMPLATE_DIR): os.makedirs(OC_TEMPLATE_DIR)
    if not os.path.exists(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC")): os.makedirs(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC"))
    dummy_config_template_path = os.path.join(OC_TEMPLATE_DIR, "EFI", "OC", "config.plist") # Name it config.plist directly
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
                macos_download_path=mock_download_dir,
                progress_callback=print,
                enhance_plist_enabled=True,
                target_macos_version="Sonoma"
            )
            success = writer.format_and_write()
        else: print("Test cancelled by user.")
        print(f"Test finished. Success: {success}")

    # Cleanup
    if os.path.exists(mock_download_dir): shutil.rmtree(mock_download_dir, ignore_errors=True)
    # if os.path.exists(OC_TEMPLATE_DIR) and "EFI_template_installer" in OC_TEMPLATE_DIR :
    #    shutil.rmtree(OC_TEMPLATE_DIR, ignore_errors=True) # Avoid deleting if it's a real shared template
    print("Mock download dir cleaned up.")
    print(f"Note: {OC_TEMPLATE_DIR} and its contents might persist if not created by this test run specifically.")
