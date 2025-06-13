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

try:
    from constants import MACOS_VERSIONS
except ImportError:
    MACOS_VERSIONS = {"Sonoma": "14", "Ventura": "13", "Monterey": "12"}
    print("Warning: constants.py not found, using fallback MACOS_VERSIONS for _get_gibmacos_product_folder.")


class USBWriterMacOS:
    def __init__(self, device: str, macos_download_path: str,
                 progress_callback=None, enhance_plist_enabled: bool = False,
                 target_macos_version: str = ""):
        self.device = device
        self.macos_download_path = macos_download_path
        self.progress_callback = progress_callback
        self.enhance_plist_enabled = enhance_plist_enabled
        self.target_macos_version = target_macos_version

        pid = os.getpid()
        self.temp_basesystem_hfs_path = f"/tmp/temp_basesystem_{pid}.hfs"
        self.temp_efi_build_dir = f"/tmp/temp_efi_build_{pid}"
        self.temp_dmg_extract_dir = f"/tmp/temp_dmg_extract_{pid}"

        self.mounted_usb_esp_path = None # Will be like /Volumes/EFI
        self.mounted_usb_macos_path = None # Will be like /Volumes/Install macOS ...
        self.mounted_source_basesystem_path = f"/tmp/source_basesystem_mount_{pid}"

        self.temp_files_to_clean = [self.temp_basesystem_hfs_path]
        self.temp_dirs_to_clean = [
            self.temp_efi_build_dir, self.temp_dmg_extract_dir,
            self.mounted_source_basesystem_path
            # Actual USB mount points (/Volumes/EFI, /Volumes/Install macOS...) are unmounted, not rmdir'd from here
        ]
        self.attached_dmg_devices = [] # Store device paths from hdiutil attach

    def _report_progress(self, message: str, is_rsync_line: bool = False):
        # Simplified progress for macOS writer for now, can add rsync parsing later if needed
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

        # Unmount our specific /tmp mount points first
        if self.mounted_source_basesystem_path and os.path.ismount(self.mounted_source_basesystem_path):
            self._unmount_path(self.mounted_source_basesystem_path, force=True)
        # System mount points like /Volumes/EFI or /Volumes/Install macOS... are unmounted by diskutil unmountDisk or unmount
        # We also add them to temp_dirs_to_clean if we used their dynamic path for rmdir later (but only if they were /tmp based)

        for dev_path in list(self.attached_dmg_devices):
            self._detach_dmg(dev_path)
        self.attached_dmg_devices = []

        for f_path in self.temp_files_to_clean:
            if os.path.exists(f_path):
                try: os.remove(f_path)
                except OSError as e: self._report_progress(f"Error removing temp file {f_path}: {e}")

        for d_path in self.temp_dirs_to_clean:
            if os.path.exists(d_path) and d_path.startswith("/tmp/"): # Only remove /tmp dirs we created
                try: shutil.rmtree(d_path, ignore_errors=True)
                except OSError as e: self._report_progress(f"Error removing temp dir {d_path}: {e}")

    def _unmount_path(self, mount_path_or_device, is_device=False, force=False):
        target = mount_path_or_device
        cmd_base = ["diskutil"]
        action = "unmountDisk" if is_device else "unmount"
        cmd = cmd_base + ([action, "force", target] if force else [action, target])

        # Check if it's a valid target for unmount/unmountDisk
        # For mount paths, check os.path.ismount. For devices, check if base device exists.
        can_unmount = False
        if is_device:
            # Extract base disk identifier like /dev/diskX from /dev/diskXsY
            base_device = re.match(r"(/dev/disk\d+)", target)
            if base_device and os.path.exists(base_device.group(1)):
                can_unmount = True
        elif os.path.ismount(target):
            can_unmount = True

        if can_unmount:
            self._report_progress(f"Attempting to {action} {'forcefully ' if force else ''}{target}...")
            self._run_command(cmd, check=False, timeout=60) # Increased timeout for diskutil
        else:
            self._report_progress(f"Skipping unmount for {target}, not a valid mount point or device for this action.")


    def _detach_dmg(self, device_path):
        if not device_path or not device_path.startswith("/dev/disk"): return
        self._report_progress(f"Attempting to detach DMG device {device_path}...")
        try:
            # Ensure it's actually a virtual disk from hdiutil
            is_virtual_disk = False
            try:
                info_result = self._run_command(["diskutil", "info", "-plist", device_path], capture_output=True)
                if info_result.returncode == 0 and info_result.stdout:
                    disk_info = plistlib.loads(info_result.stdout.encode('utf-8'))
                    if disk_info.get("VirtualOrPhysical") == "Virtual":
                        is_virtual_disk = True
            except Exception: pass # Ignore parsing errors, proceed to detach attempt

            if is_virtual_disk:
                self._run_command(["hdiutil", "detach", device_path, "-force"], check=False, timeout=30)
            else:
                self._report_progress(f"{device_path} is not a virtual disk, or info check failed. Skipping direct hdiutil detach.")

            if device_path in self.attached_dmg_devices:
                self.attached_dmg_devices.remove(device_path)
        except Exception as e:
            self._report_progress(f"Could not detach {device_path}: {e}")


    def check_dependencies(self):
        self._report_progress("Checking dependencies (diskutil, hdiutil, 7z, rsync, dd, bless)...")
        dependencies = ["diskutil", "hdiutil", "7z", "rsync", "dd", "bless"]
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
        self._report_progress(f"Could not identify a specific product folder for '{self.target_macos_version}'. Using general download path: {self.macos_download_path}"); return self.macos_download_path

    def _find_gibmacos_asset(self, asset_patterns: list[str] | str, product_folder_path: str | None = None, search_deep=True) -> str | None:
        if isinstance(asset_patterns, str): asset_patterns = [asset_patterns]
        search_base = product_folder_path or self.macos_download_path
        self._report_progress(f"Searching for {asset_patterns} in {search_base} and subdirectories...")
        for pattern in asset_patterns:
            common_subdirs_for_pattern = ["", "SharedSupport", f"Install macOS {self.target_macos_version}.app/Contents/SharedSupport", f"Install macOS {self.target_macos_version}.app/Contents/Resources"]
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
                self._report_progress(f"Extracting DMG from PKG {current_target}..."); self._run_command(["7z", "e", "-txar", current_target, "*.dmg", f"-o{self.temp_dmg_extract_dir}"], check=True); dmgs_in_pkg = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*.dmg")); assert dmgs_in_pkg, "No DMG in PKG."; current_target = max(dmgs_in_pkg, key=os.path.getsize, default=dmgs_in_pkg[0]); assert current_target, "No primary DMG in PKG."; self._report_progress(f"Using DMG from PKG: {current_target}")
            assert current_target and current_target.endswith(".dmg"), f"Not a valid DMG: {current_target}"
            basesystem_dmg_to_process = current_target
            if "basesystem.dmg" not in os.path.basename(current_target).lower():
                self._report_progress(f"Extracting BaseSystem.dmg from {current_target}..."); self._run_command(["7z", "e", current_target, "*/BaseSystem.dmg", "-r", f"-o{self.temp_dmg_extract_dir}"], check=True); found_bs_dmg = glob.glob(os.path.join(self.temp_dmg_extract_dir, "**", "*BaseSystem.dmg"), recursive=True); assert found_bs_dmg, f"No BaseSystem.dmg from {current_target}"; basesystem_dmg_to_process = found_bs_dmg[0]
            self._report_progress(f"Extracting HFS+ partition image from {basesystem_dmg_to_process}..."); self._run_command(["7z", "e", "-tdmg", basesystem_dmg_to_process, "*.hfs", f"-o{self.temp_dmg_extract_dir}"], check=True); hfs_files = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*.hfs"));
            if not hfs_files: self._run_command(["7z", "e", "-tdmg", basesystem_dmg_to_process, "*", f"-o{self.temp_dmg_extract_dir}"], check=True); hfs_files = [os.path.join(self.temp_dmg_extract_dir, f) for f in os.listdir(self.temp_dmg_extract_dir) if not f.lower().endswith((".xml",".chunklist",".plist")) and os.path.isfile(os.path.join(self.temp_dmg_extract_dir,f)) and os.path.getsize(os.path.join(self.temp_dmg_extract_dir,f)) > 2*1024*1024*1024]
            assert hfs_files, f"No suitable HFS+ image file found after extracting {basesystem_dmg_to_process}"
            final_hfs_file = max(hfs_files, key=os.path.getsize); self._report_progress(f"Found HFS+ image: {final_hfs_file}. Moving to {output_hfs_path}"); shutil.move(final_hfs_file, output_hfs_path); return True
        except Exception as e: self._report_progress(f"Error during HFS extraction: {e}\n{traceback.format_exc()}"); return False
        finally:
            if os.path.exists(self.temp_dmg_extract_dir): shutil.rmtree(self.temp_dmg_extract_dir, ignore_errors=True)

    def _create_minimal_efi_template(self, efi_dir_path):
        self._report_progress(f"Minimal EFI template directory not found or empty. Creating basic structure at {efi_dir_path}"); oc_dir=os.path.join(efi_dir_path,"EFI","OC");os.makedirs(os.path.join(efi_dir_path,"EFI","BOOT"),exist_ok=True);os.makedirs(oc_dir,exist_ok=True);[os.makedirs(os.path.join(oc_dir,s),exist_ok=True) for s in ["Drivers","Kexts","ACPI","Tools","Resources"]];open(os.path.join(efi_dir_path,"EFI","BOOT","BOOTx64.efi"),"w").close();open(os.path.join(oc_dir,"OpenCore.efi"),"w").close();bc={"#Comment":"Basic config","Misc":{"Security":{"ScanPolicy":0,"SecureBootModel":"Disabled"}},"PlatformInfo":{"Generic":{"MLB":"CHANGE_ME_MLB","SystemSerialNumber":"CHANGE_ME_SERIAL","SystemUUID":"CHANGE_ME_UUID","ROM":b"\0"*6}}};plistlib.dump(bc,open(os.path.join(oc_dir,"config.plist"),'wb'),fmt=plistlib.PlistFormat.XML)

    def format_and_write(self) -> bool:
        try:
            self.check_dependencies()
            self._cleanup_temp_files_and_dirs()
            for mp_dir in self.temp_dirs_to_clean:
                 if not os.path.exists(mp_dir): os.makedirs(mp_dir, exist_ok=True)

            self._report_progress(f"WARNING: ALL DATA ON {self.device} WILL BE ERASED!")
            self._run_command(["diskutil", "unmountDisk", "force", self.device], check=False, timeout=60); time.sleep(2)

            installer_vol_name = f"Install macOS {self.target_macos_version}"
            self._report_progress(f"Partitioning {self.device} for '{installer_vol_name}'...")
            self._run_command(["diskutil", "partitionDisk", self.device, "GPT", "FAT32", "EFI", "551MiB", "JHFS+", installer_vol_name, "0b"], timeout=180); time.sleep(3)

            disk_info_plist_str = self._run_command(["diskutil", "list", "-plist", self.device], capture_output=True).stdout
            if not disk_info_plist_str: raise RuntimeError("Failed to get disk info after partitioning.")
            disk_info = plistlib.loads(disk_info_plist_str.encode('utf-8'))

            esp_partition_dev = None; macos_partition_dev = None
            main_disk_entry = next((d for d in disk_info.get("AllDisksAndPartitions", []) if d.get("DeviceIdentifier") == self.device.replace("/dev/", "")), None)
            if main_disk_entry:
                for part in main_disk_entry.get("Partitions", []):
                    if part.get("Content") == "EFI": esp_partition_dev = f"/dev/{part.get('DeviceIdentifier')}"
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

            self.mounted_usb_macos_path = f"/Volumes/{installer_vol_name}"
            if not os.path.ismount(self.mounted_usb_macos_path):
                 self._run_command(["diskutil", "mount", "-mountPoint", self.temp_usb_macos_target_mount, macos_partition_dev])
                 self.mounted_usb_macos_path = self.temp_usb_macos_target_mount

            self._report_progress(f"macOS partition mounted at {self.mounted_usb_macos_path}")

            usb_target_root = self.mounted_usb_macos_path
            app_bundle_name = f"Install macOS {self.target_macos_version}.app"
            app_bundle_path_usb = os.path.join(usb_target_root, app_bundle_name)
            contents_path_usb = os.path.join(app_bundle_path_usb, "Contents")
            shared_support_path_usb_app = os.path.join(contents_path_usb, "SharedSupport")
            resources_path_usb_app = os.path.join(contents_path_usb, "Resources")
            sys_install_pkgs_usb = os.path.join(usb_target_root, "System", "Installation", "Packages")
            coreservices_path_usb = os.path.join(usb_target_root, "System", "Library", "CoreServices")

            for p in [shared_support_path_usb_app, resources_path_usb_app, coreservices_path_usb, sys_install_pkgs_usb]:
                self._run_command(["sudo", "mkdir", "-p", p])

            for f_name in ["BaseSystem.dmg", "BaseSystem.chunklist"]:
                src_file = self._find_gibmacos_asset(f_name, product_folder_path, search_deep=True)
                if src_file: self._run_command(["sudo", "cp", src_file, os.path.join(shared_support_path_usb_app, os.path.basename(src_file))]); self._run_command(["sudo", "cp", src_file, os.path.join(coreservices_path_usb, os.path.basename(src_file))])
                else: self._report_progress(f"Warning: {f_name} not found.")

            installinfo_src = self._find_gibmacos_asset("InstallInfo.plist", product_folder_path, search_deep=True)
            if installinfo_src: self._run_command(["sudo", "cp", installinfo_src, os.path.join(contents_path_usb, "Info.plist")]); self._run_command(["sudo", "cp", installinfo_src, os.path.join(usb_target_root, "InstallInfo.plist")])
            else: self._report_progress("Warning: InstallInfo.plist not found.")

            main_pkg_src = self._find_gibmacos_asset(["InstallAssistant.pkg", "InstallESD.dmg"], product_folder_path, search_deep=True)
            if main_pkg_src: pkg_basename = os.path.basename(main_pkg_src); self._run_command(["sudo", "cp", main_pkg_src, os.path.join(shared_support_path_usb_app, pkg_basename)]); self._run_command(["sudo", "cp", main_pkg_src, os.path.join(sys_install_pkgs_usb, pkg_basename)])
            else: self._report_progress("Warning: Main installer PKG/DMG not found.")

            diag_src = self._find_gibmacos_asset("AppleDiagnostics.dmg", product_folder_path, search_deep=True)
            if diag_src: self._run_command(["sudo", "cp", diag_src, os.path.join(shared_support_path_usb_app, "AppleDiagnostics.dmg")])

            template_boot_efi = os.path.join(OC_TEMPLATE_DIR, "EFI", "BOOT", "BOOTx64.efi")
            if os.path.exists(template_boot_efi) and os.path.getsize(template_boot_efi) > 0: self._run_command(["sudo", "cp", template_boot_efi, os.path.join(coreservices_path_usb, "boot.efi")])
            else: self._report_progress(f"Warning: Template BOOTx64.efi for installer's boot.efi not found or empty.")

            ia_product_info_path = os.path.join(usb_target_root, ".IAProductInfo")
            ia_content_xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\"><plist version=\"1.0\"><dict><key>Product ID</key><string>com.apple.pkg.InstallAssistant</string><key>Product Path</key><string>" + app_bundle_name + "/Contents/SharedSupport/InstallAssistant.pkg</string></dict></plist>"
            temp_ia_path = f"/tmp/temp_iaproductinfo_{pid}.plist"
            with open(temp_ia_path, "w") as f: f.write(ia_content_xml)
            self._run_command(["sudo", "cp", temp_ia_path, ia_product_info_path])
            if os.path.exists(temp_ia_path): os.remove(temp_ia_path)

            self._report_progress("macOS installer assets copied.")

            self._report_progress("Setting up OpenCore EFI on ESP...")
            self.mounted_usb_esp_path = f"/Volumes/EFI" # Default mount path for ESP
            if not os.path.ismount(self.mounted_usb_esp_path):
                 self._run_command(["diskutil", "mount", "-mountPoint", self.temp_usb_esp_mount, esp_partition_dev])
                 self.mounted_usb_esp_path = self.temp_usb_esp_mount

            if not os.path.isdir(OC_TEMPLATE_DIR) or not os.listdir(OC_TEMPLATE_DIR): self._create_minimal_efi_template(self.temp_efi_build_dir)
            else: self._run_command(["cp", "-a", f"{OC_TEMPLATE_DIR}/.", self.temp_efi_build_dir])

            temp_config_plist_path = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config.plist")
            if not os.path.exists(temp_config_plist_path) and os.path.exists(os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist")):
                shutil.copy2(os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist"), temp_config_plist_path)

            if self.enhance_plist_enabled and enhance_config_plist and os.path.exists(temp_config_plist_path):
                self._report_progress("Attempting to enhance config.plist (note: hardware detection is Linux-only)...")
                if enhance_config_plist(temp_config_plist_path, self.target_macos_version, self._report_progress): self._report_progress("config.plist enhancement complete.")
                else: self._report_progress("config.plist enhancement call failed or had issues.")

            self._report_progress(f"Copying final EFI folder to USB ESP ({self.mounted_usb_esp_path})...")
            self._run_command(["sudo", "rsync", "-avh", "--delete", f"{self.temp_efi_build_dir}/EFI/", f"{self.mounted_usb_esp_path}/EFI/"])

            self._report_progress(f"Blessing the installer volume: {self.mounted_usb_macos_path}")
            bless_target_folder = os.path.join(self.mounted_usb_macos_path, "System", "Library", "CoreServices")
            self._run_command(["sudo", "bless", "--folder", bless_target_folder, "--label", installer_vol_name, "--setBoot"], check=False)

            self._report_progress("USB Installer creation process completed successfully.")
            return True
        except Exception as e:
            self._report_progress(f"An error occurred during USB writing on macOS: {e}"); self._report_progress(traceback.format_exc())
            return False
        finally:
            self._cleanup_temp_files_and_dirs()

if __name__ == '__main__':
    import traceback
    from constants import MACOS_VERSIONS
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
    if not test_device or not test_device.startswith("/dev/disk"): print("Invalid disk."); shutil.rmtree(mock_download_dir, ignore_errors=True); exit(1)
    if input(f"Sure to wipe {test_device}? (yes/NO): ").lower() == 'yes':
        writer = USBWriterMacOS(test_device, mock_download_dir, print, True, target_version_cli)
        writer.format_and_write()
    else: print("Test cancelled.")
    shutil.rmtree(mock_download_dir, ignore_errors=True)
    # Deliberately not cleaning OC_TEMPLATE_DIR in test, as it might be shared or pre-existing.
    print("Mock download dir cleaned up.")
