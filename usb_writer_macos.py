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

# Assumed to exist relative to this script or project root
OC_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "EFI_template_installer")

# For _get_gibmacos_product_folder to access MACOS_VERSIONS from constants.py
# This is a bit of a hack for a library module. Ideally, constants are passed or structured differently.
try:
    from constants import MACOS_VERSIONS
except ImportError:
    # Define a fallback or minimal version if constants.py is not found in this context
    # This might happen if usb_writer_macos.py is tested truly standalone without the full app structure.
    MACOS_VERSIONS = {"Sonoma": "14", "Ventura": "13", "Monterey": "12"} # Example
    print("Warning: constants.py not found, using fallback MACOS_VERSIONS for _get_gibmacos_product_folder.")


class USBWriterMacOS:
    def __init__(self, device: str, macos_download_path: str,
                 progress_callback=None, enhance_plist_enabled: bool = False,
                 target_macos_version: str = ""):
        self.device = device # e.g., /dev/diskX
        self.macos_download_path = macos_download_path
        self.progress_callback = progress_callback
        self.enhance_plist_enabled = enhance_plist_enabled
        self.target_macos_version = target_macos_version # Display name like "Sonoma"

        pid = os.getpid()
        # Using /tmp for macOS temporary files
        self.temp_basesystem_hfs_path = f"/tmp/temp_basesystem_{pid}.hfs"
        self.temp_efi_build_dir = f"/tmp/temp_efi_build_{pid}"
        self.temp_dmg_extract_dir = f"/tmp/temp_dmg_extract_{pid}" # For 7z extractions

        # Mount points will be dynamically created by diskutil or hdiutil attach
        # We just need to track them for cleanup if they are custom /tmp paths
        self.mount_point_usb_esp = f"/tmp/usb_esp_temp_skyscope_{pid}" # Or use /Volumes/EFI
        self.mount_point_usb_macos_target = f"/tmp/usb_macos_target_temp_skyscope_{pid}" # Or use /Volumes/Install macOS ...

        self.temp_files_to_clean = [self.temp_basesystem_hfs_path]
        self.temp_dirs_to_clean = [
            self.temp_efi_build_dir, self.temp_dmg_extract_dir,
            self.mount_point_usb_esp, self.mount_point_usb_macos_target
            # Mount points created by diskutil mount are usually in /Volumes/ and unmounted by name
        ]
        self.attached_dmg_devices = [] # Store device paths from hdiutil attach

    def _report_progress(self, message: str):
        if self.progress_callback: self.progress_callback(message)
        else: print(message)

    def _run_command(self, command: list[str], check=True, capture_output=False, timeout=None, shell=False):
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

    def _cleanup_temp_files_and_dirs(self):
        self._report_progress("Cleaning up temporary files, directories, and mounts on macOS...")
        for f_path in self.temp_files_to_clean:
            if os.path.exists(f_path):
                try: os.remove(f_path)
                except OSError as e: self._report_progress(f"Error removing temp file {f_path}: {e}")

        for dev_path in list(self.attached_dmg_devices):
            self._detach_dmg(dev_path)
        self.attached_dmg_devices = []

        for d_path in self.temp_dirs_to_clean:
            if os.path.ismount(d_path):
                try: self._run_command(["diskutil", "unmount", "force", d_path], check=False, timeout=30)
                except Exception: pass
            if os.path.exists(d_path):
                try: shutil.rmtree(d_path, ignore_errors=True)
                except OSError as e: self._report_progress(f"Error removing temp dir {d_path}: {e}")

    def _detach_dmg(self, device_path_or_mount_point):
        if not device_path_or_mount_point: return
        self._report_progress(f"Attempting to detach DMG: {device_path_or_mount_point}...")
        try:
            if os.path.ismount(device_path_or_mount_point):
                 self._run_command(["diskutil", "unmount", "force", device_path_or_mount_point], check=False)
            if device_path_or_mount_point.startswith("/dev/disk"):
                self._run_command(["hdiutil", "detach", device_path_or_mount_point, "-force"], check=False, timeout=30)
            if device_path_or_mount_point in self.attached_dmg_devices:
                self.attached_dmg_devices.remove(device_path_or_mount_point)
        except Exception as e:
            self._report_progress(f"Could not detach/unmount {device_path_or_mount_point}: {e}")


    def check_dependencies(self):
        self._report_progress("Checking dependencies (diskutil, hdiutil, 7z, rsync, dd)...")
        dependencies = ["diskutil", "hdiutil", "7z", "rsync", "dd"]
        missing_deps = [dep for dep in dependencies if not shutil.which(dep)]
        if missing_deps:
            msg = f"Missing dependencies: {', '.join(missing_deps)}. `7z` (p7zip) might need to be installed (e.g., via Homebrew: `brew install p7zip`). Others are standard."
            self._report_progress(msg); raise RuntimeError(msg)
        self._report_progress("All critical dependencies for macOS USB installer creation found.")
        return True

    def _get_gibmacos_product_folder(self) -> str | None:
        base_path = os.path.join(self.macos_download_path, "macOS Downloads", "publicrelease")
        if not os.path.isdir(base_path): base_path = self.macos_download_path
        if os.path.isdir(base_path):
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                version_tag = MACOS_VERSIONS.get(self.target_macos_version, self.target_macos_version).lower()
                if os.path.isdir(item_path) and (self.target_macos_version.lower() in item.lower() or version_tag in item.lower()):
                    self._report_progress(f"Identified gibMacOS product folder: {item_path}"); return item_path
        self._report_progress(f"Could not identify a specific product folder for '{self.target_macos_version}' in {base_path}. Using general download path: {self.macos_download_path}"); return self.macos_download_path

    def _find_gibmacos_asset(self, asset_patterns: list[str] | str, product_folder_path: str | None = None, search_deep=True) -> str | None:
        if isinstance(asset_patterns, str): asset_patterns = [asset_patterns]
        search_base = product_folder_path or self.macos_download_path
        self._report_progress(f"Searching for {asset_patterns} in {search_base} and subdirectories...")
        for pattern in asset_patterns:
            common_subdirs_for_pattern = ["", "SharedSupport"] # Most assets are here or root of product folder
            if "Install macOS" in pattern : # If looking for the .app bundle itself
                common_subdirs_for_pattern = [""] # Only look at root of product folder

            for sub_dir_pattern in common_subdirs_for_pattern:
                current_search_base = os.path.join(search_base, sub_dir_pattern)
                glob_pattern = os.path.join(glob.escape(current_search_base), pattern)

                found_files = glob.glob(glob_pattern, recursive=False)
                if found_files:
                    found_files.sort(key=os.path.getsize, reverse=True)
                    self._report_progress(f"Found '{pattern}' at: {found_files[0]} (in {current_search_base})")
                    return found_files[0]

            if search_deep:
                deep_search_pattern = os.path.join(glob.escape(search_base), "**", pattern)
                found_files_deep = sorted(glob.glob(deep_search_pattern, recursive=True), key=len)
                if found_files_deep:
                    self._report_progress(f"Found '{pattern}' via deep search at: {found_files_deep[0]}")
                    return found_files_deep[0]

        self._report_progress(f"Warning: Asset matching patterns '{asset_patterns}' not found in {search_base}.")
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
            if "basesystem.dmg" not in os.path.basename(current_target).lower():
                self._report_progress(f"Extracting BaseSystem.dmg from {current_target}..."); self._run_command(["7z", "e", current_target, "*/BaseSystem.dmg", "-r", f"-o{self.temp_dmg_extract_dir}"], check=True) # Recursive search
                found_bs_dmg = glob.glob(os.path.join(self.temp_dmg_extract_dir, "**", "*BaseSystem.dmg"), recursive=True)
                if not found_bs_dmg: raise RuntimeError(f"Could not extract BaseSystem.dmg from {current_target}")
                basesystem_dmg_to_process = found_bs_dmg[0]

            self._report_progress(f"Extracting HFS+ partition image from {basesystem_dmg_to_process}..."); self._run_command(["7z", "e", "-tdmg", basesystem_dmg_to_process, "*.hfs", f"-o{self.temp_dmg_extract_dir}"], check=True)
            hfs_files = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*.hfs"));
            if not hfs_files: raise RuntimeError(f"No .hfs file found from {basesystem_dmg_to_process}")
            final_hfs_file = max(hfs_files, key=os.path.getsize); self._report_progress(f"Found HFS+ image: {final_hfs_file}. Moving to {output_hfs_path}"); shutil.move(final_hfs_file, output_hfs_path); return True
        except Exception as e: self._report_progress(f"Error during HFS extraction: {e}\n{traceback.format_exc()}"); return False
        finally:
            if os.path.exists(self.temp_dmg_extract_dir): shutil.rmtree(self.temp_dmg_extract_dir, ignore_errors=True)


    def _create_minimal_efi_template(self, efi_dir_path):
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
            for mp_dir in self.temp_dirs_to_clean:
                 os.makedirs(mp_dir, exist_ok=True)

            self._report_progress(f"WARNING: ALL DATA ON {self.device} WILL BE ERASED!")
            self._run_command(["diskutil", "unmountDisk", "force", self.device], check=False, timeout=60); time.sleep(2)

            installer_vol_name = f"Install macOS {self.target_macos_version}"
            self._report_progress(f"Partitioning {self.device} as GPT: EFI (FAT32, 551MB), '{installer_vol_name}' (HFS+)...")
            self._run_command(["diskutil", "partitionDisk", self.device, "GPT", "FAT32", "EFI", "551MiB", "JHFS+", installer_vol_name, "0b"], timeout=180); time.sleep(3)

            disk_info_plist_str = self._run_command(["diskutil", "list", "-plist", self.device], capture_output=True).stdout
            if not disk_info_plist_str: raise RuntimeError("Failed to get disk info after partitioning.")
            disk_info = plistlib.loads(disk_info_plist_str.encode('utf-8'))

            esp_partition_dev = None; macos_partition_dev = None
            # Find the main disk entry first
            main_disk_entry = next((d for d in disk_info.get("AllDisksAndPartitions", []) if d.get("DeviceIdentifier") == self.device.replace("/dev/", "")), None)
            if main_disk_entry:
                for part in main_disk_entry.get("Partitions", []):
                    if part.get("VolumeName") == "EFI" and part.get("Content") == "EFI": esp_partition_dev = f"/dev/{part.get('DeviceIdentifier')}"
                    elif part.get("VolumeName") == installer_vol_name: macos_partition_dev = f"/dev/{part.get('DeviceIdentifier')}"

            if not (esp_partition_dev and macos_partition_dev): raise RuntimeError(f"Could not identify partitions on {self.device} (EFI: {esp_partition_dev}, macOS: {macos_partition_dev}). Check diskutil list output.")
            self._report_progress(f"Identified ESP: {esp_partition_dev}, macOS Partition: {macos_partition_dev}")

            product_folder_path = self._get_gibmacos_product_folder()
            source_for_hfs_extraction = self._find_gibmacos_asset(["BaseSystem.dmg", "InstallESD.dmg", "SharedSupport.dmg", "InstallAssistant.pkg"], product_folder_path, "BaseSystem.dmg (or source like InstallESD.dmg/SharedSupport.dmg/InstallAssistant.pkg)")
            if not source_for_hfs_extraction: raise RuntimeError("Essential macOS DMG/PKG for BaseSystem extraction not found in download path.")

            if not self._extract_hfs_from_dmg_or_pkg(source_for_hfs_extraction, self.temp_basesystem_hfs_path):
                raise RuntimeError("Failed to extract HFS+ image from BaseSystem assets.")

            raw_macos_partition_dev = macos_partition_dev.replace("/dev/disk", "/dev/rdisk")
            self._report_progress(f"Writing BaseSystem HFS+ image to {raw_macos_partition_dev} using dd...")
            self._run_command(["sudo", "dd", f"if={self.temp_basesystem_hfs_path}", f"of={raw_macos_partition_dev}", "bs=1m"], timeout=1800)

            self._report_progress(f"Mounting macOS Install partition ({macos_partition_dev}) on USB to {self.temp_usb_macos_target_mount}...")
            self._run_command(["diskutil", "mount", "-mountPoint", self.temp_usb_macos_target_mount, macos_partition_dev])

            self._report_progress("Copying necessary macOS installer assets to USB...")
            app_bundle_name = f"Install macOS {self.target_macos_version}.app"
            app_bundle_path_usb = os.path.join(self.temp_usb_macos_target_mount, app_bundle_name)
            contents_path_usb = os.path.join(app_bundle_path_usb, "Contents")
            shared_support_path_usb_app = os.path.join(contents_path_usb, "SharedSupport")
            self._run_command(["sudo", "mkdir", "-p", shared_support_path_usb_app])
            self._run_command(["sudo", "mkdir", "-p", os.path.join(contents_path_usb, "Resources")])

            coreservices_path_usb = os.path.join(self.temp_usb_macos_target_mount, "System", "Library", "CoreServices")
            self._run_command(["sudo", "mkdir", "-p", coreservices_path_usb])

            original_bs_dmg = self._find_gibmacos_asset("BaseSystem.dmg", product_folder_path, search_deep=True)
            if original_bs_dmg:
                self._report_progress(f"Copying BaseSystem.dmg to USB CoreServices and App SharedSupport...")
                self._run_command(["sudo", "cp", original_bs_dmg, os.path.join(coreservices_path_usb, "BaseSystem.dmg")])
                self._run_command(["sudo", "cp", original_bs_dmg, os.path.join(shared_support_path_usb_app, "BaseSystem.dmg")])
                original_bs_chunklist = self._find_gibmacos_asset("BaseSystem.chunklist", os.path.dirname(original_bs_dmg), search_deep=False)
                if original_bs_chunklist:
                    self._report_progress(f"Copying BaseSystem.chunklist...")
                    self._run_command(["sudo", "cp", original_bs_chunklist, os.path.join(coreservices_path_usb, "BaseSystem.chunklist")])
                    self._run_command(["sudo", "cp", original_bs_chunklist, os.path.join(shared_support_path_usb_app, "BaseSystem.chunklist")])

            installinfo_src = self._find_gibmacos_asset("InstallInfo.plist", product_folder_path, search_deep=True)
            if installinfo_src:
                self._report_progress(f"Copying InstallInfo.plist...")
                self._run_command(["sudo", "cp", installinfo_src, os.path.join(contents_path_usb, "Info.plist")])
                self._run_command(["sudo", "cp", installinfo_src, os.path.join(self.temp_usb_macos_target_mount, "InstallInfo.plist")])

            packages_dir_usb_system = os.path.join(self.temp_usb_macos_target_mount, "System", "Installation", "Packages")
            self._run_command(["sudo", "mkdir", "-p", packages_dir_usb_system])
            main_payload_src = self._find_gibmacos_asset(["InstallAssistant.pkg", "InstallESD.dmg"], product_folder_path, search_deep=True)
            if main_payload_src:
                payload_basename = os.path.basename(main_payload_src)
                self._report_progress(f"Copying main payload '{payload_basename}' to App SharedSupport and System Packages...")
                self._run_command(["sudo", "cp", main_payload_src, os.path.join(shared_support_path_usb_app, payload_basename)])
                self._run_command(["sudo", "cp", main_payload_src, os.path.join(packages_dir_usb_system, payload_basename)])

            self._run_command(["sudo", "touch", os.path.join(coreservices_path_usb, "boot.efi")]) # Placeholder for bootability

            # --- OpenCore EFI Setup ---
            self._report_progress("Setting up OpenCore EFI on ESP...")
            self._run_command(["diskutil", "mount", "-mountPoint", self.temp_usb_esp_mount, esp_partition_dev])
            if not os.path.isdir(OC_TEMPLATE_DIR) or not os.listdir(OC_TEMPLATE_DIR): self._create_minimal_efi_template(self.temp_efi_build_dir)
            else: self._run_command(["cp", "-a", f"{OC_TEMPLATE_DIR}/.", self.temp_efi_build_dir])

            temp_config_plist_path = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config.plist")
            if not os.path.exists(temp_config_plist_path) and os.path.exists(os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist")):
                shutil.copy2(os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist"), temp_config_plist_path)

            if self.enhance_plist_enabled and enhance_config_plist and os.path.exists(temp_config_plist_path):
                self._report_progress("Attempting to enhance config.plist (note: hardware detection is Linux-only)...")
                if enhance_config_plist(temp_config_plist_path, self.target_macos_version, self._report_progress): self._report_progress("config.plist enhancement processing complete.")
                else: self._report_progress("config.plist enhancement call failed or had issues.")

            self._report_progress(f"Copying final EFI folder to USB ESP ({self.temp_usb_esp_mount})...")
            self._run_command(["sudo", "rsync", "-avh", "--delete", f"{self.temp_efi_build_dir}/EFI/", f"{self.temp_usb_esp_mount}/EFI/"])

            self._report_progress(f"Blessing the installer volume: {self.temp_usb_macos_target_mount} with ESP {esp_partition_dev}")
            # Correct bless command needs the folder containing boot.efi for the system being blessed,
            # and the ESP mount point if different from system ESP.
            # For installer, it's often /Volumes/Install macOS XXX/System/Library/CoreServices
            bless_target_folder = os.path.join(self.temp_usb_macos_target_mount, "System", "Library", "CoreServices")
            self._run_command(["sudo", "bless", "--folder", bless_target_folder, "--label", installer_vol_name, "--setBoot"], check=False) # SetBoot might be enough for OpenCore
            # Alternative if ESP needs to be specified explicitly:
            # self._run_command(["sudo", "bless", "--mount", self.temp_usb_macos_target_mount, "--setBoot", "--file", os.path.join(bless_target_folder, "boot.efi"), "--bootefi", os.path.join(self.temp_usb_esp_mount, "EFI", "BOOT", "BOOTx64.efi")], check=False)


            self._report_progress("USB Installer creation process completed successfully.")
            return True
        except Exception as e:
            self._report_progress(f"An error occurred during USB writing on macOS: {e}\n{traceback.format_exc()}")
            return False
        finally:
            self._cleanup_temp_files_and_dirs()

if __name__ == '__main__':
    import traceback
    from constants import MACOS_VERSIONS # For testing _get_gibmacos_product_folder
    if platform.system() != "Darwin": print("This script is intended for macOS for standalone testing."); exit(1)
    print("USB Writer macOS Standalone Test - Installer Method")
    mock_download_dir = f"/tmp/temp_macos_download_skyscope_{os.getpid()}"; os.makedirs(mock_download_dir, exist_ok=True)
    target_version_cli = sys.argv[1] if len(sys.argv) > 1 else "Sonoma"
    mock_product_name_segment = MACOS_VERSIONS.get(target_version_cli, target_version_cli).lower()
    mock_product_name = f"012-34567 - macOS {target_version_cli} {mock_product_name_segment}.x.x"
    mock_product_folder_path = os.path.join(mock_download_dir, "macOS Downloads", "publicrelease", mock_product_name)
    os.makedirs(os.path.join(mock_product_folder_path, "SharedSupport"), exist_ok=True)
    with open(os.path.join(mock_product_folder_path, "SharedSupport", "BaseSystem.dmg"), "wb") as f: f.write(os.urandom(10*1024*1024))
    with open(os.path.join(mock_product_folder_path, "SharedSupport", "BaseSystem.chunklist"), "w") as f: f.write("dummy chunklist")
    with open(os.path.join(mock_product_folder_path, "InstallInfo.plist"), "wb") as f: plistlib.dump({"DisplayName":f"macOS {target_version_cli}"},f)
    with open(os.path.join(mock_product_folder_path, "InstallAssistant.pkg"), "wb") as f: f.write(os.urandom(1024))
    with open(os.path.join(mock_product_folder_path, "SharedSupport", "AppleDiagnostics.dmg"), "wb") as f: f.write(os.urandom(1024))

    if not os.path.exists(OC_TEMPLATE_DIR): os.makedirs(OC_TEMPLATE_DIR, exist_ok=True)
    if not os.path.exists(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC")): os.makedirs(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC"), exist_ok=True)
    if not os.path.exists(os.path.join(OC_TEMPLATE_DIR, "EFI", "BOOT")): os.makedirs(os.path.join(OC_TEMPLATE_DIR, "EFI", "BOOT"), exist_ok=True)
    dummy_config_template_path = os.path.join(OC_TEMPLATE_DIR, "EFI", "OC", "config.plist")
    if not os.path.exists(dummy_config_template_path):
         with open(dummy_config_template_path, "wb") as f: plistlib.dump({"TestTemplate":True}, f, fmt=plistlib.PlistFormat.XML)
    dummy_bootx64_efi_path = os.path.join(OC_TEMPLATE_DIR, "EFI", "BOOT", "BOOTx64.efi")
    if not os.path.exists(dummy_bootx64_efi_path):
        with open(dummy_bootx64_efi_path, "w") as f: f.write("dummy bootx64.efi content")


    print("\nAvailable external physical disks (use 'diskutil list external physical'):"); subprocess.run(["diskutil", "list", "external", "physical"], check=False)
    test_device = input("\nEnter target disk identifier (e.g., /dev/diskX). THIS DISK WILL BE WIPED: ")
    if not test_device or not test_device.startswith("/dev/disk"): print("Invalid disk."); shutil.rmtree(mock_download_dir, ignore_errors=True); exit(1) # No need to clean OC_TEMPLATE_DIR here
    if input(f"Sure to wipe {test_device}? (yes/NO): ").lower() == 'yes':
        writer = USBWriterMacOS(test_device, mock_download_dir, print, True, target_version_cli)
        writer.format_and_write()
    else: print("Test cancelled.")
    shutil.rmtree(mock_download_dir, ignore_errors=True)
    print("Mock download dir cleaned up.")
