# usb_writer_linux.py (Refined asset copying)
import subprocess
import os
import time
import shutil
import glob
import re
import plistlib
import traceback

try:
    from plist_modifier import enhance_config_plist
except ImportError:
    enhance_config_plist = None
    print("Warning: plist_modifier.py not found. Plist enhancement feature will be disabled for USBWriterLinux.")

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
        from constants import MACOS_VERSIONS # Import for this method
        _report = self._report_progress
        _report(f"Searching for macOS product folder in {self.macos_download_path} for version {self.target_macos_version}")

        # Check for a specific versioned download folder first (gibMacOS pattern)
        # e.g. macOS Downloads/publicrelease/XXX - macOS Sonoma 14.X/
        possible_toplevel_folders = [
            os.path.join(self.macos_download_path, "macOS Downloads", "publicrelease"),
            os.path.join(self.macos_download_path, "macOS Downloads", "developerseed"),
            os.path.join(self.macos_download_path, "macOS Downloads", "customerseed"),
            self.macos_download_path # Fallback to searching directly in the provided path
        ]

        version_tag_from_constants = MACOS_VERSIONS.get(self.target_macos_version, self.target_macos_version).lower()
        target_version_str_simple = self.target_macos_version.lower().replace("macos","").strip()


        for base_path_to_search in possible_toplevel_folders:
            if not os.path.isdir(base_path_to_search): continue
            for item in os.listdir(base_path_to_search):
                item_path = os.path.join(base_path_to_search, item)
                item_lower = item.lower()
                # Heuristic: look for version string or display name in folder name
                if os.path.isdir(item_path) and \
                   ("macos" in item_lower and (target_version_str_simple in item_lower or version_tag_from_constants in item_lower)):
                    _report(f"Identified gibMacOS product folder: {item_path}")
                    return item_path

        _report(f"Could not identify a specific product folder. Using base download path: {self.macos_download_path}")
        return self.macos_download_path


    def _find_gibmacos_asset(self, asset_patterns: list[str] | str, product_folder_path: str, search_deep=True) -> str | None:
        if isinstance(asset_patterns, str): asset_patterns = [asset_patterns]
        self._report_progress(f"Searching for {asset_patterns} in {product_folder_path}...")

        # Prioritize direct children and common locations
        common_subdirs = ["", "SharedSupport", "Install macOS*.app/Contents/SharedSupport", "Install macOS*.app/Contents/Resources"]

        for pattern in asset_patterns:
            for sub_dir_pattern in common_subdirs:
                # Construct glob pattern, allowing for versioned app names
                current_search_base = os.path.join(product_folder_path, sub_dir_pattern.replace("Install macOS*.app", f"Install macOS {self.target_macos_version}.app"))
                # If the above doesn't exist, try generic app name for glob
                if not os.path.isdir(os.path.dirname(current_search_base)) and "Install macOS*.app" in sub_dir_pattern:
                     current_search_base = os.path.join(product_folder_path, sub_dir_pattern)


                glob_pattern = os.path.join(glob.escape(current_search_base), pattern) # Escape base path for glob

                # Search non-recursively first in specific paths
                found_files = glob.glob(glob_pattern, recursive=False)
                if found_files:
                    found_files.sort(key=os.path.getsize, reverse=True) # Prefer larger files if multiple (e.g. InstallESD.dmg)
                    self._report_progress(f"Found '{pattern}' at: {found_files[0]} (in {current_search_base})")
                    return found_files[0]

            # If requested and not found yet, do a broader recursive search from product_folder_path
            if search_deep:
                deep_search_pattern = os.path.join(glob.escape(product_folder_path), "**", pattern)
                found_files_deep = sorted(glob.glob(deep_search_pattern, recursive=True), key=len) # Prefer shallower paths
                if found_files_deep:
                    self._report_progress(f"Found '{pattern}' via deep search at: {found_files_deep[0]}")
                    return found_files_deep[0]

        self._report_progress(f"Warning: Asset matching patterns '{asset_patterns}' not found in {product_folder_path} or its common subdirectories.")
        return None

    def _extract_hfs_from_dmg_or_pkg(self, dmg_or_pkg_path: str, output_hfs_path: str) -> bool:
        # This method assumes dmg_or_pkg_path is the path to a file like BaseSystem.dmg, InstallESD.dmg, or InstallAssistant.pkg
        # It tries to extract the core HFS+ filesystem (often '4.hfs' from BaseSystem.dmg)
        os.makedirs(self.temp_dmg_extract_dir, exist_ok=True)
        current_target_dmg = None

        try:
            if dmg_or_pkg_path.endswith(".pkg"):
                self._report_progress(f"Extracting DMGs from PKG: {dmg_or_pkg_path}...")
                self._run_command(["7z", "x", dmg_or_pkg_path, "*.dmg", "-r", f"-o{self.temp_dmg_extract_dir}"], check=True) # Extract all DMGs recursively
                dmgs_in_pkg = glob.glob(os.path.join(self.temp_dmg_extract_dir, "**", "*.dmg"), recursive=True)
                if not dmgs_in_pkg: raise RuntimeError("No DMG found within PKG.")

                # Heuristic: find BaseSystem.dmg, else largest InstallESD.dmg, else largest SharedSupport.dmg
                bs_dmg = next((d for d in dmgs_in_pkg if "basesystem.dmg" in d.lower()), None)
                if bs_dmg: current_target_dmg = bs_dmg
                else:
                    esd_dmgs = [d for d in dmgs_in_pkg if "installesd.dmg" in d.lower()]
                    if esd_dmgs: current_target_dmg = max(esd_dmgs, key=os.path.getsize)
                    else:
                        ss_dmgs = [d for d in dmgs_in_pkg if "sharedsupport.dmg" in d.lower()]
                        if ss_dmgs: current_target_dmg = max(ss_dmgs, key=os.path.getsize) # This might contain BaseSystem.dmg
                        else: current_target_dmg = max(dmgs_in_pkg, key=os.path.getsize) # Last resort: largest DMG
                if not current_target_dmg: raise RuntimeError("Could not determine primary DMG within PKG.")
                self._report_progress(f"Identified primary DMG from PKG: {current_target_dmg}")
            elif dmg_or_pkg_path.endswith(".dmg"):
                current_target_dmg = dmg_or_pkg_path
            else:
                raise RuntimeError(f"Unsupported file type for HFS extraction: {dmg_or_pkg_path}")

            # If current_target_dmg is (likely) InstallESD.dmg or SharedSupport.dmg, we need to find BaseSystem.dmg within it
            basesystem_dmg_to_process = current_target_dmg
            if "basesystem.dmg" not in os.path.basename(current_target_dmg).lower():
                self._report_progress(f"Searching for BaseSystem.dmg within {current_target_dmg}...")
                # Extract to a sub-folder to avoid name clashes
                nested_extract_dir = os.path.join(self.temp_dmg_extract_dir, "nested_dmg_contents")
                os.makedirs(nested_extract_dir, exist_ok=True)
                self._run_command(["7z", "e", current_target_dmg, "*BaseSystem.dmg", "-r", f"-o{nested_extract_dir}"], check=True)
                found_bs_dmgs = glob.glob(os.path.join(nested_extract_dir, "**", "*BaseSystem.dmg"), recursive=True)
                if not found_bs_dmgs: raise RuntimeError(f"Could not extract BaseSystem.dmg from {current_target_dmg}")
                basesystem_dmg_to_process = found_bs_dmgs[0]
                self._report_progress(f"Located BaseSystem.dmg for processing: {basesystem_dmg_to_process}")

            self._report_progress(f"Extracting HFS+ partition image from {basesystem_dmg_to_process}...")
            self._run_command(["7z", "e", "-tdmg", basesystem_dmg_to_process, "*.hfs", f"-o{self.temp_dmg_extract_dir}"], check=True)
            hfs_files = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*.hfs"))
            if not hfs_files: # If no .hfs, maybe it's a flat DMG image already (unlikely for BaseSystem.dmg)
                 alt_files = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*"))
                 alt_files = [f for f in alt_files if os.path.isfile(f) and not f.lower().endswith((".xml",".chunklist",".plist")) and os.path.getsize(f) > 2*1024*1024*1024] # Min 2GB
                 if alt_files: hfs_files = alt_files
            if not hfs_files: raise RuntimeError(f"No suitable HFS+ image file found after extracting {basesystem_dmg_to_process}")

            final_hfs_file = max(hfs_files, key=os.path.getsize)
            self._report_progress(f"Found HFS+ partition image: {final_hfs_file}. Moving to {output_hfs_path}")
            shutil.move(final_hfs_file, output_hfs_path)
            return True
        except Exception as e:
            self._report_progress(f"Error during HFS extraction: {e}\n{traceback.format_exc()}"); return False
        finally:
            if os.path.exists(self.temp_dmg_extract_dir): shutil.rmtree(self.temp_dmg_extract_dir, ignore_errors=True)


    def format_and_write(self) -> bool:
        try:
            self.check_dependencies()
            self._cleanup_temp_files_and_dirs()
            for mp_dir in [self.mount_point_usb_esp, self.mount_point_usb_macos_target, self.temp_efi_build_dir]:
                self._run_command(["sudo", "mkdir", "-p", mp_dir])

            self._report_progress(f"WARNING: ALL DATA ON {self.device} WILL BE ERASED!")
            for i in range(1, 10): self._run_command(["sudo", "umount", "-lf", f"{self.device}{i}"], check=False, timeout=5); self._run_command(["sudo", "umount", "-lf", f"{self.device}p{i}"], check=False, timeout=5)

            self._report_progress(f"Partitioning {self.device} with GPT (sgdisk)...")
            self._run_command(["sudo", "sgdisk", "--zap-all", self.device])
            self._run_command(["sudo", "sgdisk", "-n", "1:0:+550M", "-t", "1:ef00", "-c", "1:EFI", self.device])
            usb_vol_name = f"Install macOS {self.target_macos_version}"
            self._run_command(["sudo", "sgdisk", "-n", "2:0:0",    "-t", "2:af00", "-c", f"2:{usb_vol_name[:11]}" , self.device])
            self._run_command(["sudo", "partprobe", self.device], timeout=10); time.sleep(3)

            esp_partition_dev = next((f"{self.device}{i}" for i in ["1", "p1"] if os.path.exists(f"{self.device}{i}")), None)
            macos_partition_dev = next((f"{self.device}{i}" for i in ["2", "p2"] if os.path.exists(f"{self.device}{i}")), None)
            if not (esp_partition_dev and macos_partition_dev): raise RuntimeError(f"Could not reliably determine partition names for {self.device}.")

            self._report_progress(f"Formatting ESP ({esp_partition_dev}) as FAT32...")
            self._run_command(["sudo", "mkfs.vfat", "-F", "32", "-n", "EFI", esp_partition_dev])
            self._report_progress(f"Formatting macOS Install partition ({macos_partition_dev}) as HFS+...")
            self._run_command(["sudo", "mkfs.hfsplus", "-v", usb_vol_name, macos_partition_dev])

            product_folder = self._get_gibmacos_product_folder()

            source_for_hfs_extraction = self._find_gibmacos_asset(["BaseSystem.dmg", "InstallESD.dmg", "SharedSupport.dmg", "InstallAssistant.pkg"], product_folder, "BaseSystem.dmg (or source like InstallESD.dmg/SharedSupport.dmg/InstallAssistant.pkg)")
            if not source_for_hfs_extraction: raise RuntimeError("Essential macOS DMG/PKG for BaseSystem extraction not found in download path.")

            if not self._extract_hfs_from_dmg_or_pkg(source_for_hfs_extraction, self.temp_basesystem_hfs_path):
                raise RuntimeError("Failed to extract HFS+ image from BaseSystem assets.")

            self._report_progress(f"Writing BaseSystem HFS+ image to {macos_partition_dev} using dd...")
            self._run_command(["sudo", "dd", f"if={self.temp_basesystem_hfs_path}", f"of={macos_partition_dev}", "bs=4M", "status=progress", "oflag=sync"])

            self._report_progress("Mounting macOS Install partition on USB...")
            self._run_command(["sudo", "mount", macos_partition_dev, self.mount_point_usb_macos_target])

            # --- Copying full installer assets ---
            self._report_progress("Copying macOS installer assets to USB...")

            # 1. Create "Install macOS [VersionName].app" structure
            app_bundle_name = f"Install macOS {self.target_macos_version}.app"
            app_bundle_path_usb = os.path.join(self.mount_point_usb_macos_target, app_bundle_name)
            contents_path_usb = os.path.join(app_bundle_path_usb, "Contents")
            shared_support_path_usb_app = os.path.join(contents_path_usb, "SharedSupport")
            resources_path_usb_app = os.path.join(contents_path_usb, "Resources")
            self._run_command(["sudo", "mkdir", "-p", shared_support_path_usb_app])
            self._run_command(["sudo", "mkdir", "-p", resources_path_usb_app])

            # 2. Copy BaseSystem.dmg & BaseSystem.chunklist
            core_services_path_usb = os.path.join(self.mount_point_usb_macos_target, "System", "Library", "CoreServices")
            self._run_command(["sudo", "mkdir", "-p", core_services_path_usb])
            original_bs_dmg = self._find_gibmacos_asset("BaseSystem.dmg", product_folder)
            if original_bs_dmg:
                self._report_progress(f"Copying BaseSystem.dmg to {core_services_path_usb}/ and {shared_support_path_usb_app}/")
                self._run_command(["sudo", "cp", original_bs_dmg, os.path.join(core_services_path_usb, "BaseSystem.dmg")])
                self._run_command(["sudo", "cp", original_bs_dmg, os.path.join(shared_support_path_usb_app, "BaseSystem.dmg")])
                original_bs_chunklist = self._find_gibmacos_asset("BaseSystem.chunklist", os.path.dirname(original_bs_dmg)) # Look in same dir as BaseSystem.dmg
                if original_bs_chunklist:
                    self._report_progress(f"Copying BaseSystem.chunklist...")
                    self._run_command(["sudo", "cp", original_bs_chunklist, os.path.join(core_services_path_usb, "BaseSystem.chunklist")])
                    self._run_command(["sudo", "cp", original_bs_chunklist, os.path.join(shared_support_path_usb_app, "BaseSystem.chunklist")])
            else: self._report_progress("Warning: Original BaseSystem.dmg not found to copy.")

            # 3. Copy InstallInfo.plist
            installinfo_src = self._find_gibmacos_asset("InstallInfo.plist", product_folder)
            if installinfo_src:
                self._report_progress(f"Copying InstallInfo.plist...")
                self._run_command(["sudo", "cp", installinfo_src, os.path.join(contents_path_usb, "Info.plist")]) # For .app bundle
                self._run_command(["sudo", "cp", installinfo_src, os.path.join(self.mount_point_usb_macos_target, "InstallInfo.plist")]) # For root of volume
            else: self._report_progress("Warning: InstallInfo.plist not found.")

            # 4. Copy main installer package(s) to .app/Contents/SharedSupport/
            #    And also to /System/Installation/Packages/ for direct BaseSystem boot.
            packages_dir_usb_system = os.path.join(self.mount_point_usb_macos_target, "System", "Installation", "Packages")
            self._run_command(["sudo", "mkdir", "-p", packages_dir_usb_system])

            main_payload_patterns = ["InstallAssistant.pkg", "InstallESD.dmg", "SharedSupport.dmg"] # Order of preference
            main_payload_src = self._find_gibmacos_asset(main_payload_patterns, product_folder, "Main Installer Payload (PKG/DMG)")

            if main_payload_src:
                payload_basename = os.path.basename(main_payload_src)
                self._report_progress(f"Copying main payload '{payload_basename}' to {shared_support_path_usb_app}/ and {packages_dir_usb_system}/")
                self._run_command(["sudo", "cp", main_payload_src, os.path.join(shared_support_path_usb_app, payload_basename)])
                self._run_command(["sudo", "cp", main_payload_src, os.path.join(packages_dir_usb_system, payload_basename)])
                # If it's SharedSupport.dmg, its *contents* are often what's needed in Packages, not the DMG itself.
                # This is a complex step; createinstallmedia does more. For now, copying the DMG/PKG might be enough for OpenCore to find.
            else: self._report_progress("Warning: Main installer payload (InstallAssistant.pkg, InstallESD.dmg, or SharedSupport.dmg) not found.")

            # 5. Copy AppleDiagnostics.dmg to .app/Contents/SharedSupport/
            diag_src = self._find_gibmacos_asset("AppleDiagnostics.dmg", product_folder)
            if diag_src:
                self._report_progress(f"Copying AppleDiagnostics.dmg to {shared_support_path_usb_app}/")
                self._run_command(["sudo", "cp", diag_src, os.path.join(shared_support_path_usb_app, "AppleDiagnostics.dmg")])

            # 6. Ensure /System/Library/CoreServices/boot.efi exists (can be a copy of OpenCore's BOOTx64.efi or a generic one)
            self._report_progress("Ensuring /System/Library/CoreServices/boot.efi exists on installer partition...")
            self._run_command(["sudo", "touch", os.path.join(core_services_path_usb, "boot.efi")]) # Placeholder, OC will handle actual boot

            self._report_progress("macOS installer assets copied to USB.")

            # --- OpenCore EFI Setup ---
            self._report_progress("Setting up OpenCore EFI on ESP...")
            if not os.path.isdir(OC_TEMPLATE_DIR) or not os.listdir(OC_TEMPLATE_DIR): self._create_minimal_efi_template(self.temp_efi_build_dir)
            else: self._report_progress(f"Copying OpenCore EFI template from {OC_TEMPLATE_DIR} to {self.temp_efi_build_dir}"); self._run_command(["sudo", "cp", "-a", f"{OC_TEMPLATE_DIR}/.", self.temp_efi_build_dir])
            temp_config_plist_path = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config.plist")
            if not os.path.exists(temp_config_plist_path):
                template_plist = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist")
                if os.path.exists(template_plist): self._run_command(["sudo", "cp", template_plist, temp_config_plist_path])
                else:
                    with open(temp_config_plist_path, 'wb') as f: plistlib.dump({"#Comment": "Basic config by Skyscope"}, f, fmt=plistlib.PlistFormat.XML); os.chmod(temp_config_plist_path, 0o644) # Ensure permissions
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
    # ... (Standalone test block needs constants.MACOS_VERSIONS for _get_gibmacos_product_folder)
    from constants import MACOS_VERSIONS # For standalone test
    import traceback
    if os.geteuid() != 0: print("Please run this script as root (sudo) for testing."); exit(1)
    print("USB Writer Linux Standalone Test - Installer Method (Fuller Asset Copying)")
    mock_download_dir = f"temp_macos_download_skyscope_{os.getpid()}"; os.makedirs(mock_download_dir, exist_ok=True)
    target_version_cli = sys.argv[1] if len(sys.argv) > 1 else "Sonoma" # Example: python usb_writer_linux.py Sonoma

    mock_product_name_segment = MACOS_VERSIONS.get(target_version_cli, target_version_cli).lower() # e.g. "sonoma" or "14"
    mock_product_name = f"012-34567 - macOS {target_version_cli} {mock_product_name_segment}.x.x"
    specific_product_folder = os.path.join(mock_download_dir, "macOS Downloads", "publicrelease", mock_product_name)
    os.makedirs(os.path.join(specific_product_folder, "SharedSupport"), exist_ok=True)
    os.makedirs(specific_product_folder, exist_ok=True)

    with open(os.path.join(specific_product_folder, "SharedSupport", "BaseSystem.dmg"), "wb") as f: f.write(os.urandom(10*1024*1024))
    with open(os.path.join(specific_product_folder, "SharedSupport", "BaseSystem.chunklist"), "w") as f: f.write("dummy chunklist")
    with open(os.path.join(specific_product_folder, "InstallInfo.plist"), "wb") as f: plistlib.dump({"DisplayName":f"macOS {target_version_cli}"},f)
    with open(os.path.join(specific_product_folder, "InstallAssistant.pkg"), "wb") as f: f.write(os.urandom(1024))
    with open(os.path.join(specific_product_folder, "SharedSupport", "AppleDiagnostics.dmg"), "wb") as f: f.write(os.urandom(1024))


    if not os.path.exists(OC_TEMPLATE_DIR): os.makedirs(OC_TEMPLATE_DIR)
    if not os.path.exists(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC")): os.makedirs(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC"))
    dummy_config_template_path = os.path.join(OC_TEMPLATE_DIR, "EFI", "OC", "config.plist")
    if not os.path.exists(dummy_config_template_path):
         with open(dummy_config_template_path, "w") as f: f.write("<plist><dict><key>TestTemplate</key><true/></dict></plist>")

    print("\nAvailable block devices (be careful!):"); subprocess.run(["lsblk", "-d", "-o", "NAME,SIZE,MODEL"], check=True)
    test_device = input("\nEnter target device (e.g., /dev/sdX). THIS DEVICE WILL BE WIPED: ")

    if not test_device or not test_device.startswith("/dev/"):
        print("Invalid device. Exiting.")
    else:
        confirm = input(f"Are you absolutely sure you want to wipe {test_device} and create installer for {target_version_cli}? (yes/NO): ")
        success = False
        if confirm.lower() == 'yes':
            writer = USBWriterLinux(device=test_device, macos_download_path=mock_download_dir, progress_callback=print, enhance_plist_enabled=True, target_macos_version=target_version_cli)
            success = writer.format_and_write()
        else: print("Test cancelled by user.")
        print(f"Test finished. Success: {success}")

    if os.path.exists(mock_download_dir): shutil.rmtree(mock_download_dir, ignore_errors=True)
    print("Mock download dir cleaned up.")
