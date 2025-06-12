# usb_writer_macos.py (Refactoring for Installer Workflow)
import subprocess
import os
import time
import shutil
import glob
import plistlib
import traceback

try:
    from plist_modifier import enhance_config_plist
except ImportError:
    enhance_config_plist = None
    print("Warning: plist_modifier.py not found. Plist enhancement feature will be disabled.")

OC_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "EFI_template_installer")

class USBWriterMacOS:
    def __init__(self, device: str, macos_download_path: str,
                 progress_callback=None, enhance_plist_enabled: bool = False,
                 target_macos_version: str = ""):
        self.device = device # e.g., /dev/diskX
        self.macos_download_path = macos_download_path
        self.progress_callback = progress_callback
        self.enhance_plist_enabled = enhance_plist_enabled
        self.target_macos_version = target_macos_version

        pid = os.getpid()
        self.temp_basesystem_hfs_path = f"/tmp/temp_basesystem_{pid}.hfs" # Use /tmp for macOS
        self.temp_efi_build_dir = f"/tmp/temp_efi_build_{pid}"
        self.temp_opencore_mount = f"/tmp/opencore_efi_temp_skyscope_{pid}" # For source BaseSystem.dmg's EFI (if needed)
        self.temp_usb_esp_mount = f"/tmp/usb_esp_temp_skyscope_{pid}"
        self.temp_macos_source_mount = f"/tmp/macos_source_temp_skyscope_{pid}" # Not used in this flow
        self.temp_usb_macos_target_mount = f"/tmp/usb_macos_target_temp_skyscope_{pid}"
        self.temp_dmg_extract_dir = f"/tmp/temp_dmg_extract_{pid}" # For 7z extractions

        self.temp_files_to_clean = [self.temp_basesystem_hfs_path]
        self.temp_dirs_to_clean = [
            self.temp_efi_build_dir, self.temp_opencore_mount,
            self.temp_usb_esp_mount, self.temp_macos_source_mount,
            self.temp_usb_macos_target_mount, self.temp_dmg_extract_dir
        ]
        self.attached_dmg_devices = [] # Store devices from hdiutil attach

    def _report_progress(self, message: str): # ... (same)
        if self.progress_callback: self.progress_callback(message)
        else: print(message)

    def _run_command(self, command: list[str], check=True, capture_output=False, timeout=None, shell=False): # ... (same)
        self._report_progress(f"Executing: {' '.join(command)}")
        try:
            process = subprocess.run(command, check=check, capture_output=capture_output, text=True, timeout=timeout, shell=shell)
            if capture_output:
                if process.stdout and process.stdout.strip(): self._report_progress(f"STDOUT: {process.stdout.strip()}")
                if process.stderr and process.stderr.strip(): self._report_progress(f"STDERR: {process.stderr.strip()}")
            return process
        except subprocess.TimeoutExpired: self._report_progress(f"Command timed out after {timeout} seconds."); raise
        except subprocess.CalledProcessError as e: self._report_progress(f"Error executing (code {e.returncode}): {e.stderr or e.stdout or str(e)}"); raise
        except FileNotFoundError: self._report_progress(f"Error: Command '{command[0]}' not found."); raise

    def _cleanup_temp_files_and_dirs(self): # Updated for macOS
        self._report_progress("Cleaning up temporary files and directories...")
        for f_path in self.temp_files_to_clean:
            if os.path.exists(f_path):
                try: os.remove(f_path) # No sudo needed for /tmp files usually
                except OSError as e: self._report_progress(f"Error removing temp file {f_path}: {e}")

        # Detach DMGs first
        for dev_path in list(self.attached_dmg_devices): # Iterate copy
            self._detach_dmg(dev_path)
        self.attached_dmg_devices = []

        for d_path in self.temp_dirs_to_clean:
            if os.path.ismount(d_path):
                try: self._run_command(["diskutil", "unmount", "force", d_path], check=False, timeout=30)
                except Exception: pass # Ignore if already unmounted or error
            if os.path.exists(d_path):
                try: shutil.rmtree(d_path, ignore_errors=True)
                except OSError as e: self._report_progress(f"Error removing temp dir {d_path}: {e}")

    def _detach_dmg(self, device_path_or_mount_point):
        if not device_path_or_mount_point: return
        self._report_progress(f"Attempting to detach DMG associated with {device_path_or_mount_point}...")
        try:
            # hdiutil detach can take a device path or sometimes a mount path if it's unique enough
            # Using -force to ensure it detaches even if volumes are "busy" (after unmount attempts)
            self._run_command(["hdiutil", "detach", device_path_or_mount_point, "-force"], check=False, timeout=30)
            if device_path_or_mount_point in self.attached_dmg_devices: # Check if it was in our list
                self.attached_dmg_devices.remove(device_path_or_mount_point)
            # Also try to remove if it's a /dev/diskX path that got added
            if device_path_or_mount_point.startswith("/dev/") and device_path_or_mount_point in self.attached_dmg_devices:
                self.attached_dmg_devices.remove(device_path_or_mount_point)

        except Exception as e:
            self._report_progress(f"Could not detach {device_path_or_mount_point}: {e}")


    def check_dependencies(self):
        self._report_progress("Checking dependencies (diskutil, hdiutil, 7z, rsync, dd)...")
        dependencies = ["diskutil", "hdiutil", "7z", "rsync", "dd"]
        missing_deps = [dep for dep in dependencies if not shutil.which(dep)]
        if missing_deps:
            msg = f"Missing dependencies: {', '.join(missing_deps)}. `7z` (p7zip) might need to be installed (e.g., via Homebrew: `brew install p7zip`)."
            self._report_progress(msg); raise RuntimeError(msg)
        self._report_progress("All critical dependencies for macOS USB installer creation found.")
        return True

    def _get_gibmacos_product_folder(self) -> str | None:
        base_path = os.path.join(self.macos_download_path, "macOS Downloads", "publicrelease")
        if not os.path.isdir(base_path): base_path = self.macos_download_path
        if os.path.isdir(base_path):
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                if os.path.isdir(item_path) and (self.target_macos_version.lower() in item.lower() or MACOS_VERSIONS.get(self.target_macos_version, "").lower() in item.lower()): # MACOS_VERSIONS needs to be accessible or passed if not global
                    self._report_progress(f"Identified gibMacOS product folder: {item_path}"); return item_path
        self._report_progress(f"Could not identify a specific product folder for '{self.target_macos_version}' in {base_path}. Using base download path."); return self.macos_download_path

    def _find_gibmacos_asset(self, asset_patterns: list[str] | str, product_folder_path: str | None = None) -> str | None:
        if isinstance(asset_patterns, str): asset_patterns = [asset_patterns]
        search_base = product_folder_path or self.macos_download_path
        self._report_progress(f"Searching for {asset_patterns} in {search_base} and subdirectories...")
        for pattern in asset_patterns:
            # Using iglob for efficiency if many files, but glob is fine for fewer expected matches
            found_files = glob.glob(os.path.join(search_base, "**", pattern), recursive=True)
            if found_files:
                found_files.sort(key=lambda x: (x.count(os.sep), len(x)))
                self._report_progress(f"Found {pattern}: {found_files[0]}")
                return found_files[0]
        self._report_progress(f"Warning: Asset pattern(s) {asset_patterns} not found in {search_base}.")
        return None

    def _extract_hfs_from_dmg_or_pkg(self, dmg_or_pkg_path: str, output_hfs_path: str) -> bool:
        os.makedirs(self.temp_dmg_extract_dir, exist_ok=True); current_target = dmg_or_pkg_path
        try:
            if dmg_or_pkg_path.endswith(".pkg"):
                self._report_progress(f"Extracting DMG from PKG {current_target}..."); self._run_command(["7z", "e", "-txar", current_target, "*.dmg", f"-o{self.temp_dmg_extract_dir}"], check=True)
                dmgs_in_pkg = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*.dmg"));
                if not dmgs_in_pkg: raise RuntimeError("No DMG found in PKG.")
                current_target = max(dmgs_in_pkg, key=os.path.getsize, default=None) or dmgs_in_pkg[0]
                if not current_target: raise RuntimeError("Could not determine primary DMG in PKG.")
                self._report_progress(f"Using DMG from PKG: {current_target}")
            if not current_target or not current_target.endswith(".dmg"): raise RuntimeError(f"Not a valid DMG: {current_target}")

            basesystem_dmg_to_process = current_target
            # If current_target is InstallESD.dmg or SharedSupport.dmg, it contains BaseSystem.dmg
            if "basesystem.dmg" not in os.path.basename(current_target).lower():
                self._report_progress(f"Extracting BaseSystem.dmg from {current_target}...")
                self._run_command(["7z", "e", current_target, "*/BaseSystem.dmg", f"-o{self.temp_dmg_extract_dir}"], check=True)
                found_bs_dmg = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*BaseSystem.dmg"), recursive=True)
                if not found_bs_dmg: raise RuntimeError(f"Could not extract BaseSystem.dmg from {current_target}")
                basesystem_dmg_to_process = found_bs_dmg[0]

            self._report_progress(f"Extracting HFS+ partition image from {basesystem_dmg_to_process}...")
            self._run_command(["7z", "e", "-tdmg", basesystem_dmg_to_process, "*.hfs", f"-o{self.temp_dmg_extract_dir}"], check=True)
            hfs_files = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*.hfs"));
            if not hfs_files: raise RuntimeError(f"No .hfs file found from {basesystem_dmg_to_process}")
            final_hfs_file = max(hfs_files, key=os.path.getsize); self._report_progress(f"Found HFS+ image: {final_hfs_file}. Moving to {output_hfs_path}"); shutil.move(final_hfs_file, output_hfs_path); return True
        except Exception as e: self._report_progress(f"Error during HFS extraction: {e}\n{traceback.format_exc()}"); return False
        finally:
            if os.path.exists(self.temp_dmg_extract_dir): shutil.rmtree(self.temp_dmg_extract_dir, ignore_errors=True)


    def _create_minimal_efi_template(self, efi_dir_path): # Same as linux version
        self._report_progress(f"Minimal EFI template directory not found or empty. Creating basic structure at {efi_dir_path}")
        oc_dir = os.path.join(efi_dir_path, "EFI", "OC"); os.makedirs(os.path.join(efi_dir_path, "EFI", "BOOT"), exist_ok=True); os.makedirs(oc_dir, exist_ok=True)
        for sub_dir in ["Drivers", "Kexts", "ACPI", "Tools", "Resources"]: os.makedirs(os.path.join(oc_dir, sub_dir), exist_ok=True)
        with open(os.path.join(efi_dir_path, "EFI", "BOOT", "BOOTx64.efi"), "w") as f: f.write("")
        with open(os.path.join(oc_dir, "OpenCore.efi"), "w") as f: f.write("")
        basic_config_content = {"#Comment": "Basic config template by Skyscope", "Misc": {"Security": {"ScanPolicy": 0, "SecureBootModel": "Disabled"}}, "PlatformInfo": {"Generic":{"MLB":"CHANGE_ME_MLB", "SystemSerialNumber":"CHANGE_ME_SERIAL", "SystemUUID":"CHANGE_ME_UUID", "ROM": b"\x00\x00\x00\x00\x00\x00"}}}
        try:
            with open(os.path.join(oc_dir, "config.plist"), 'wb') as f: plistlib.dump(basic_config_content, f, fmt=plistlib.PlistFormat.XML)
            self._report_progress("Created basic placeholder config.plist.")
        except Exception as e: self._report_progress(f"Could not create basic config.plist: {e}")


    def format_and_write(self) -> bool:
        try:
            self.check_dependencies()
            self._cleanup_temp_files_and_dirs()
            for mp_dir in self.temp_dirs_to_clean: # Use full list from constructor
                 os.makedirs(mp_dir, exist_ok=True)

            self._report_progress(f"WARNING: ALL DATA ON {self.device} WILL BE ERASED!")
            self._run_command(["diskutil", "unmountDisk", "force", self.device], check=False, timeout=60); time.sleep(2)

            installer_vol_name = f"Install macOS {self.target_macos_version}"
            self._report_progress(f"Partitioning {self.device} as GPT: EFI (FAT32, 551MB), '{installer_vol_name}' (HFS+)...")
            self._run_command(["diskutil", "partitionDisk", self.device, "GPT", "FAT32", "EFI", "551MiB", "JHFS+", installer_vol_name, "0b"], timeout=180); time.sleep(3)

            # Get actual partition identifiers
            disk_info_plist = self._run_command(["diskutil", "list", "-plist", self.device], capture_output=True).stdout
            if not disk_info_plist: raise RuntimeError("Failed to get disk info after partitioning.")
            disk_info = plistlib.loads(disk_info_plist.encode('utf-8'))

            esp_partition_dev = None; macos_partition_dev = None
            for disk_entry in disk_info.get("AllDisksAndPartitions", []):
                if disk_entry.get("DeviceIdentifier") == self.device.replace("/dev/", ""):
                    for part in disk_entry.get("Partitions", []):
                        if part.get("VolumeName") == "EFI": esp_partition_dev = f"/dev/{part.get('DeviceIdentifier')}"
                        elif part.get("VolumeName") == installer_vol_name: macos_partition_dev = f"/dev/{part.get('DeviceIdentifier')}"
            if not (esp_partition_dev and macos_partition_dev): raise RuntimeError(f"Could not identify partitions on {self.device} (EFI: {esp_partition_dev}, macOS: {macos_partition_dev}).")
            self._report_progress(f"Identified ESP: {esp_partition_dev}, macOS Partition: {macos_partition_dev}")

            # --- Prepare macOS Installer Content ---
            product_folder = self._get_gibmacos_product_folder()
            source_for_hfs_extraction = self._find_gibmacos_asset(["BaseSystem.dmg", "InstallESD.dmg", "SharedSupport.dmg"], product_folder, "BaseSystem.dmg (or source like InstallESD.dmg/SharedSupport.dmg)")
            if not source_for_hfs_extraction: raise RuntimeError("Essential macOS DMG for BaseSystem extraction not found in download path.")

            if not self._extract_hfs_from_dmg_or_pkg(source_for_hfs_extraction, self.temp_basesystem_hfs_path):
                raise RuntimeError("Failed to extract HFS+ image from BaseSystem assets.")

            raw_macos_partition_dev = macos_partition_dev.replace("/dev/disk", "/dev/rdisk") # Use raw device for dd
            self._report_progress(f"Writing BaseSystem HFS+ image to {raw_macos_partition_dev} using dd...")
            self._run_command(["sudo", "dd", f"if={self.temp_basesystem_hfs_path}", f"of={raw_macos_partition_dev}", "bs=1m"], timeout=1800)

            self._report_progress(f"Mounting macOS Install partition ({macos_partition_dev}) on USB...")
            self._run_command(["diskutil", "mount", "-mountPoint", self.temp_usb_macos_target_mount, macos_partition_dev])

            core_services_path_usb = os.path.join(self.temp_usb_macos_target_mount, "System", "Library", "CoreServices")
            self._run_command(["sudo", "mkdir", "-p", core_services_path_usb])

            original_bs_dmg = self._find_gibmacos_asset("BaseSystem.dmg", product_folder)
            if original_bs_dmg:
                self._report_progress(f"Copying {original_bs_dmg} to {core_services_path_usb}/BaseSystem.dmg")
                self._run_command(["sudo", "cp", original_bs_dmg, os.path.join(core_services_path_usb, "BaseSystem.dmg")])
                original_bs_chunklist = original_bs_dmg.replace(".dmg", ".chunklist")
                if os.path.exists(original_bs_chunklist):
                    self._report_progress(f"Copying {original_bs_chunklist} to {core_services_path_usb}/BaseSystem.chunklist")
                    self._run_command(["sudo", "cp", original_bs_chunklist, os.path.join(core_services_path_usb, "BaseSystem.chunklist")])

            install_info_src = self._find_gibmacos_asset("InstallInfo.plist", product_folder)
            if install_info_src:
                self._report_progress(f"Copying InstallInfo.plist to {self.temp_usb_macos_target_mount}/InstallInfo.plist")
                self._run_command(["sudo", "cp", install_info_src, os.path.join(self.temp_usb_macos_target_mount, "InstallInfo.plist")])

            packages_dir_usb = os.path.join(self.temp_usb_macos_target_mount, "System", "Installation", "Packages")
            self._run_command(["sudo", "mkdir", "-p", packages_dir_usb])

            # Copy main installer package(s) or app contents. This is simplified.
            # A real createinstallmedia copies the .app then uses it. We are building manually.
            # We need to find the main payload: InstallAssistant.pkg or InstallESD.dmg/SharedSupport.dmg content.
            main_payload_src = self._find_gibmacos_asset(["InstallAssistant.pkg", "InstallESD.dmg", "SharedSupport.dmg"], product_folder, "Main Installer Payload (PKG/DMG)")
            if main_payload_src:
                self._report_progress(f"Copying main payload {os.path.basename(main_payload_src)} to {packages_dir_usb}/")
                self._run_command(["sudo", "cp", main_payload_src, os.path.join(packages_dir_usb, os.path.basename(main_payload_src))])
                # If it's SharedSupport.dmg, its contents might be what's needed in Packages or elsewhere.
                # If InstallAssistant.pkg, it might need to be placed at root or specific app structure.
            else: self._report_progress("Warning: Main installer payload not found. Installer may be incomplete.")

            self._run_command(["sudo", "touch", os.path.join(core_services_path_usb, "boot.efi")])
            self._report_progress("macOS installer assets copied.")

            # --- OpenCore EFI Setup ---
            self._report_progress("Setting up OpenCore EFI on ESP...")
            if not os.path.isdir(OC_TEMPLATE_DIR) or not os.listdir(OC_TEMPLATE_DIR): self._create_minimal_efi_template(self.temp_efi_build_dir)
            else: self._report_progress(f"Copying OpenCore EFI template from {OC_TEMPLATE_DIR} to {self.temp_efi_build_dir}"); self._run_command(["cp", "-a", f"{OC_TEMPLATE_DIR}/.", self.temp_efi_build_dir])

            temp_config_plist_path = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config.plist")
            if not os.path.exists(temp_config_plist_path) and os.path.exists(os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist")):
                shutil.copy2(os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist"), temp_config_plist_path)

            if self.enhance_plist_enabled and enhance_config_plist and os.path.exists(temp_config_plist_path):
                self._report_progress("Attempting to enhance config.plist (note: hardware detection is Linux-only)...")
                if enhance_config_plist(temp_config_plist_path, self.target_macos_version, self._report_progress): self._report_progress("config.plist enhancement processing complete.")
                else: self._report_progress("config.plist enhancement call failed or had issues.")

            self._run_command(["diskutil", "mount", "-mountPoint", self.temp_usb_esp_mount, esp_partition_dev])
            self._report_progress(f"Copying final EFI folder to USB ESP ({self.temp_usb_esp_mount})...")
            self._run_command(["sudo", "rsync", "-avh", "--delete", f"{self.temp_efi_build_dir}/EFI/", f"{self.temp_usb_esp_mount}/EFI/"])

            self._report_progress("USB Installer creation process completed successfully.")
            return True
        except Exception as e:
            self._report_progress(f"An error occurred during USB writing on macOS: {e}\n{traceback.format_exc()}")
            return False
        finally:
            self._cleanup_temp_files_and_dirs()

if __name__ == '__main__':
    import traceback
    if platform.system() != "Darwin": print("This script is intended for macOS for standalone testing."); exit(1)
    print("USB Writer macOS Standalone Test - Installer Method")
    mock_download_dir = f"/tmp/temp_macos_download_skyscope_{os.getpid()}"; os.makedirs(mock_download_dir, exist_ok=True)
    # Simulate a more realistic gibMacOS product folder structure for testing _get_gibmacos_product_folder
    mock_product_name = f"012-34567 - macOS {sys.argv[1] if len(sys.argv) > 1 else 'Sonoma'} 14.1.2"
    mock_product_folder_path = os.path.join(mock_download_dir, "macOS Downloads", "publicrelease", mock_product_name)
    os.makedirs(os.path.join(mock_product_folder_path, "SharedSupport"), exist_ok=True) # Create SharedSupport directory

    # Create dummy BaseSystem.dmg inside the product folder's SharedSupport
    dummy_bs_dmg_path = os.path.join(mock_product_folder_path, "SharedSupport", "BaseSystem.dmg")
    if not os.path.exists(dummy_bs_dmg_path):
        with open(dummy_bs_dmg_path, "wb") as f: f.write(os.urandom(10*1024*1024)) # 10MB dummy DMG

    dummy_installinfo_path = os.path.join(mock_product_folder_path, "InstallInfo.plist")
    if not os.path.exists(dummy_installinfo_path):
        with open(dummy_installinfo_path, "wb") as f: plistlib.dump({"DisplayName":f"macOS {sys.argv[1] if len(sys.argv) > 1 else 'Sonoma'}"},f)

    if not os.path.exists(OC_TEMPLATE_DIR): os.makedirs(OC_TEMPLATE_DIR)
    if not os.path.exists(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC")): os.makedirs(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC"))
    dummy_config_template_path = os.path.join(OC_TEMPLATE_DIR, "EFI", "OC", "config.plist")
    if not os.path.exists(dummy_config_template_path):
         with open(dummy_config_template_path, "wb") as f: plistlib.dump({"TestTemplate":True}, f)

    print("\nAvailable external physical disks (use 'diskutil list external physical'):"); subprocess.run(["diskutil", "list", "external", "physical"], check=False)
    test_device = input("\nEnter target disk identifier (e.g., /dev/diskX). THIS DISK WILL BE WIPED: ")
    if not test_device or not test_device.startswith("/dev/disk"): print("Invalid disk."); shutil.rmtree(mock_download_dir, ignore_errors=True); exit(1) # No need to clean OC_TEMPLATE_DIR here
    if input(f"Sure to wipe {test_device}? (yes/NO): ").lower() == 'yes':
        writer = USBWriterMacOS(test_device, mock_download_dir, print, True, sys.argv[1] if len(sys.argv) > 1 else "Sonoma")
        writer.format_and_write()
    else: print("Test cancelled.")
    shutil.rmtree(mock_download_dir, ignore_errors=True)
    print("Mock download dir cleaned up.")
