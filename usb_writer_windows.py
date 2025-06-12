# usb_writer_windows.py (Refactoring for Installer Workflow)
import subprocess
import os
import time
import shutil
import re
import glob # For _find_gibmacos_asset
import traceback
import sys # For checking psutil import

# Try to import QMessageBox for the placeholder, otherwise use a mock for standalone test
try:
    from PyQt6.QtWidgets import QMessageBox # For user guidance
except ImportError:
    class QMessageBox: # Mock for standalone testing
        @staticmethod
        def information(*args): print(f"INFO (QMessageBox mock): Title='{args[1]}', Message='{args[2]}'")
        @staticmethod
        def warning(*args): print(f"WARNING (QMessageBox mock): Title='{args[1]}', Message='{args[2]}'"); return QMessageBox
        Yes = 1 # Mock value
        No = 0 # Mock value
        Cancel = 0 # Mock value

try:
    from plist_modifier import enhance_config_plist
except ImportError:
    enhance_config_plist = None
    print("Warning: plist_modifier.py not found. Plist enhancement feature will be disabled.")

OC_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "EFI_template_installer")

class USBWriterWindows:
    def __init__(self, device_id_str: str, macos_download_path: str,
                 progress_callback=None, enhance_plist_enabled: bool = False,
                 target_macos_version: str = ""):
        # device_id_str is expected to be the disk number string from user, e.g., "1", "2"
        self.disk_number = "".join(filter(str.isdigit, device_id_str))
        if not self.disk_number:
            raise ValueError(f"Invalid device_id format: '{device_id_str}'. Must contain a disk number.")

        self.physical_drive_path = f"\\\\.\\PhysicalDrive{self.disk_number}"

        self.macos_download_path = macos_download_path
        self.progress_callback = progress_callback
        self.enhance_plist_enabled = enhance_plist_enabled
        self.target_macos_version = target_macos_version

        pid = os.getpid()
        self.temp_basesystem_hfs_path = f"temp_basesystem_{pid}.hfs"
        self.temp_efi_build_dir = f"temp_efi_build_{pid}"
        self.temp_dmg_extract_dir = f"temp_dmg_extract_{pid}" # For 7z extractions


        self.temp_files_to_clean = [self.temp_basesystem_hfs_path]
        self.temp_dirs_to_clean = [self.temp_efi_build_dir, self.temp_dmg_extract_dir]
        self.assigned_efi_letter = None

    def _report_progress(self, message: str):
        if self.progress_callback: self.progress_callback(message)
        else: print(message)

    def _run_command(self, command: list[str] | str, check=True, capture_output=False, timeout=None, shell=False, working_dir=None):
        self._report_progress(f"Executing: {command if isinstance(command, str) else ' '.join(command)}")
        try:
            process = subprocess.run(
                command, check=check, capture_output=capture_output, text=True, timeout=timeout, shell=shell, cwd=working_dir,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if capture_output:
                if process.stdout and process.stdout.strip(): self._report_progress(f"STDOUT: {process.stdout.strip()}")
                if process.stderr and process.stderr.strip(): self._report_progress(f"STDERR: {process.stderr.strip()}")
            return process
        except subprocess.TimeoutExpired: self._report_progress(f"Command timed out after {timeout} seconds."); raise
        except subprocess.CalledProcessError as e: self._report_progress(f"Error executing (code {e.returncode}): {e.stderr or e.stdout or str(e)}"); raise
        except FileNotFoundError: self._report_progress(f"Error: Command '{command[0] if isinstance(command, list) else command.split()[0]}' not found."); raise


    def _run_diskpart_script(self, script_content: str, capture_output_for_parse=False) -> str | None:
        script_file_path = f"diskpart_script_{os.getpid()}.txt"; output_text = ""
        with open(script_file_path, "w") as f: f.write(script_content)
        try:
            self._report_progress(f"Running diskpart script:\n{script_content}")
            process = self._run_command(["diskpart", "/s", script_file_path], capture_output=True, check=False)
            output_text = (process.stdout or "") + "\n" + (process.stderr or "")

            success_indicators = ["DiskPart successfully", "successfully completed", "succeeded in creating", "successfully formatted", "successfully assigned"]
            has_success_indicator = any(indicator in output_text for indicator in success_indicators)
            has_error_indicator = "Virtual Disk Service error" in output_text or "DiskPart has encountered an error" in output_text

            if has_error_indicator:
                 self._report_progress(f"Diskpart script may have failed. Output:\n{output_text}")
            elif not has_success_indicator and "There are no partitions on this disk to show" not in output_text :
                 self._report_progress(f"Diskpart script output does not clearly indicate success. Output:\n{output_text}")

            if capture_output_for_parse: return output_text
        finally:
            if os.path.exists(script_file_path): os.remove(script_file_path)
        return output_text if capture_output_for_parse else None


    def _cleanup_temp_files_and_dirs(self):
        self._report_progress("Cleaning up...")
        for f_path in self.temp_files_to_clean:
            if os.path.exists(f_path):
                try: os.remove(f_path)
                except Exception as e: self._report_progress(f"Could not remove temp file {f_path}: {e}")
        for d_path in self.temp_dirs_to_clean:
            if os.path.exists(d_path):
                try: shutil.rmtree(d_path, ignore_errors=True)
                except Exception as e: self._report_progress(f"Could not remove temp dir {d_path}: {e}")


    def _find_available_drive_letter(self) -> str | None:
        import string; used_letters = set()
        try:
            if 'psutil' in sys.modules: # Check if psutil was imported by main app
                partitions = sys.modules['psutil'].disk_partitions(all=True)
                for p in partitions:
                    if p.mountpoint and len(p.mountpoint) >= 2 and p.mountpoint[1] == ':': # Check for "X:"
                        used_letters.add(p.mountpoint[0].upper())
        except Exception as e:
            self._report_progress(f"Could not list used drive letters with psutil: {e}. Will try common letters.")

        for letter in "STUVWXYZGHIJKLMNOPQR":
            if letter not in used_letters and letter > 'D': # Avoid A, B, C, D
                return letter
        return None

    def check_dependencies(self):
        self._report_progress("Checking dependencies (diskpart, robocopy, 7z, dd for Windows [manual check])...")
        dependencies = ["diskpart", "robocopy", "7z"]
        missing_deps = [dep for dep in dependencies if not shutil.which(dep)]
        if missing_deps:
            msg = f"Missing dependencies: {', '.join(missing_deps)}. `diskpart` & `robocopy` should be standard. `7z.exe` (7-Zip CLI) needs to be installed and in PATH."
            self._report_progress(msg); raise RuntimeError(msg)
        self._report_progress("Base dependencies found. Ensure a 'dd for Windows' utility is installed and in your PATH for writing the main macOS BaseSystem image.")
        return True

    def _find_gibmacos_asset(self, asset_patterns: list[str] | str, product_folder_path: str | None = None) -> str | None:
        if isinstance(asset_patterns, str): asset_patterns = [asset_patterns]
        search_base = product_folder_path or self.macos_download_path
        self._report_progress(f"Searching for {asset_patterns} in {search_base} and subdirectories...")
        for pattern in asset_patterns:
            found_files = glob.glob(os.path.join(search_base, "**", pattern), recursive=True)
            if found_files:
                found_files.sort(key=lambda x: (x.count(os.sep), len(x)))
                self._report_progress(f"Found {pattern}: {found_files[0]}")
                return found_files[0]
        self._report_progress(f"Warning: Asset pattern(s) {asset_patterns} not found in {search_base}.")
        return None

    def _get_gibmacos_product_folder(self) -> str | None:
        from constants import MACOS_VERSIONS # Import for this method
        base_path = os.path.join(self.macos_download_path, "macOS Downloads", "publicrelease")
        if not os.path.isdir(base_path): base_path = self.macos_download_path
        if os.path.isdir(base_path):
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                if os.path.isdir(item_path) and (self.target_macos_version.lower() in item.lower() or MACOS_VERSIONS.get(self.target_macos_version, "").lower() in item.lower()):
                    self._report_progress(f"Identified gibMacOS product folder: {item_path}"); return item_path
        self._report_progress(f"Could not identify a specific product folder for '{self.target_macos_version}' in {base_path}. Using base download path: {self.macos_download_path}"); return self.macos_download_path


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
                self._report_progress(f"Extracting BaseSystem.dmg from {current_target}..."); self._run_command(["7z", "e", current_target, "*/BaseSystem.dmg", f"-o{self.temp_dmg_extract_dir}"], check=True)
                found_bs_dmg = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*BaseSystem.dmg"), recursive=True)
                if not found_bs_dmg: raise RuntimeError(f"Could not extract BaseSystem.dmg from {current_target}")
                basesystem_dmg_to_process = found_bs_dmg[0]

            self._report_progress(f"Extracting HFS+ partition image from {basesystem_dmg_to_process}..."); self._run_command(["7z", "e", "-tdmg", basesystem_dmg_to_process, "*.hfs", f"-o{self.temp_dmg_extract_dir}"], check=True)
            hfs_files = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*.hfs"));
            if not hfs_files:
                self._run_command(["7z", "e", "-tdmg", basesystem_dmg_to_process, "*", f"-o{self.temp_dmg_extract_dir}"], check=True) # Try extracting all files
                hfs_files = [os.path.join(self.temp_dmg_extract_dir, f) for f in os.listdir(self.temp_dmg_extract_dir) if not f.lower().endswith((".xml",".chunklist",".plist")) and os.path.isfile(os.path.join(self.temp_dmg_extract_dir,f)) and os.path.getsize(os.path.join(self.temp_dmg_extract_dir,f)) > 100*1024*1024]

            if not hfs_files: raise RuntimeError(f"No suitable .hfs image found after extracting {basesystem_dmg_to_process}")
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
            os.makedirs(self.temp_efi_build_dir, exist_ok=True)

            self._report_progress(f"WARNING: ALL DATA ON DISK {self.disk_number} ({self.physical_drive_path}) WILL BE ERASED!")

            self.assigned_efi_letter = self._find_available_drive_letter()
            if not self.assigned_efi_letter: raise RuntimeError("Could not find an available drive letter for EFI.")
            self._report_progress(f"Will assign letter {self.assigned_efi_letter}: to EFI partition.")

            diskpart_script_part1 = f"select disk {self.disk_number}\nclean\nconvert gpt\n"
            diskpart_script_part1 += f"create partition efi size=550 label=\"EFI\"\nformat fs=fat32 quick\nassign letter={self.assigned_efi_letter}\n" # Assign after format
            diskpart_script_part1 += f"create partition primary label=\"Install macOS {self.target_macos_version}\" id=AF00\nexit\n" # Set HFS+ type ID
            self._run_diskpart_script(diskpart_script_part1)
            time.sleep(5)

            macos_partition_offset_str = "Offset not determined by diskpart"
            macos_partition_number_str = "2 (assumed)"

            diskpart_script_detail = f"select disk {self.disk_number}\nselect partition 2\ndetail partition\nexit\n"
            detail_output = self._run_diskpart_script(diskpart_script_detail, capture_output_for_parse=True)
            if detail_output:
                self._report_progress(f"Detail Partition Output:\n{detail_output}")
                offset_match = re.search(r"Offset in Bytes\s*:\s*(\d+)", detail_output, re.IGNORECASE)
                if offset_match: macos_partition_offset_str = f"{offset_match.group(1)} bytes ({int(offset_match.group(1)) // (1024*1024)} MiB)"

                part_num_match = re.search(r"Partition\s+(\d+)\s*\n\s*Type", detail_output, re.IGNORECASE | re.MULTILINE) # Match "Partition X" then "Type" on next line
                if part_num_match:
                    macos_partition_number_str = part_num_match.group(1)
                    self._report_progress(f"Determined macOS partition number: {macos_partition_number_str}")

            # --- OpenCore EFI Setup ---
            self._report_progress("Setting up OpenCore EFI on ESP...")
            if not os.path.isdir(OC_TEMPLATE_DIR) or not os.listdir(OC_TEMPLATE_DIR): self._create_minimal_efi_template(self.temp_efi_build_dir)
            else:
                self._report_progress(f"Copying OpenCore EFI template from {OC_TEMPLATE_DIR} to {self.temp_efi_build_dir}")
                if os.path.exists(self.temp_efi_build_dir): shutil.rmtree(self.temp_efi_build_dir)
                shutil.copytree(OC_TEMPLATE_DIR, self.temp_efi_build_dir, dirs_exist_ok=True)

            temp_config_plist_path = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config.plist")
            if not os.path.exists(temp_config_plist_path):
                template_plist_src = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist") # Name used in prior step
                if os.path.exists(template_plist_src): shutil.copy2(template_plist_src, temp_config_plist_path)
                else: self._create_minimal_efi_template(self.temp_efi_build_dir) # Fallback to create basic if template also missing

            if self.enhance_plist_enabled and enhance_config_plist and os.path.exists(temp_config_plist_path):
                self._report_progress("Attempting to enhance config.plist (note: hardware detection is Linux-only for this feature)...")
                if enhance_config_plist(temp_config_plist_path, self.target_macos_version, self._report_progress): self._report_progress("config.plist enhancement processing complete.")
                else: self._report_progress("config.plist enhancement call failed or had issues.")

            target_efi_on_usb_root = f"{self.assigned_efi_letter}:\\"
            if not os.path.exists(target_efi_on_usb_root): # Wait and check again
                time.sleep(3)
                if not os.path.exists(target_efi_on_usb_root):
                    raise RuntimeError(f"EFI partition {self.assigned_efi_letter}: not accessible after assign.")

            self._report_progress(f"Copying final EFI folder to USB ESP ({target_efi_on_usb_root})...")
            self._run_command(["robocopy", os.path.join(self.temp_efi_build_dir, "EFI"), target_efi_on_usb_root + "EFI", "/E", "/S", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP", "/XO"], check=True)
            self._report_progress(f"EFI setup complete on {target_efi_on_usb_root}")

            # --- Prepare BaseSystem ---
            self._report_progress("Locating BaseSystem image from downloaded assets...")
            product_folder_path = self._get_gibmacos_product_folder()
            source_for_hfs_extraction = self._find_gibmacos_asset(["BaseSystem.dmg", "InstallESD.dmg", "SharedSupport.dmg"], product_folder_path, "BaseSystem.dmg (or source like InstallESD.dmg/SharedSupport.dmg)")
            if not source_for_hfs_extraction: source_for_hfs_extraction = self._find_gibmacos_asset("InstallAssistant.pkg", product_folder_path, "InstallAssistant.pkg as BaseSystem source")
            if not source_for_hfs_extraction: raise RuntimeError("Could not find BaseSystem.dmg, InstallESD.dmg, SharedSupport.dmg or InstallAssistant.pkg.")

            if not self._extract_hfs_from_dmg_or_pkg(source_for_hfs_extraction, self.temp_basesystem_hfs_path):
                raise RuntimeError("Failed to extract HFS+ image from BaseSystem assets.")

            abs_hfs_path = os.path.abspath(self.temp_basesystem_hfs_path)
            guidance_message = (
                f"EFI setup complete on drive {self.assigned_efi_letter}:.\n"
                f"BaseSystem HFS image extracted to: '{abs_hfs_path}'.\n\n"
                f"MANUAL STEP REQUIRED FOR MAIN macOS PARTITION:\n"
                f"1. Open Command Prompt or PowerShell AS ADMINISTRATOR.\n"
                f"2. Use a 'dd for Windows' utility to write the extracted HFS image.\n"
                f"   Target: Disk {self.disk_number} (Path: {self.physical_drive_path}), Partition {macos_partition_number_str} (Offset: {macos_partition_offset_str}).\n"
                f"   Example command (VERIFY SYNTAX FOR YOUR DD TOOL!):\n"
                f"   `dd if=\"{abs_hfs_path}\" of={self.physical_drive_path} --target-partition {macos_partition_number_str} bs=4M --progress` (Conceptual, if dd supports partition targeting by number)\n"
                f"   OR, if writing to the whole disk by offset (VERY ADVANCED & RISKY if offset is wrong):\n"
                f"   `dd if=\"{abs_hfs_path}\" of={self.physical_drive_path} seek=<OFFSET_IN_BLOCKS_OR_BYTES> bs=<YOUR_BLOCK_SIZE> ...` (Offset from diskpart is in bytes)\n\n"
                "3. After writing BaseSystem, manually copy other installer files (like InstallAssistant.pkg or contents of SharedSupport.dmg) from "
                f"'{self.macos_download_path}' to the 'Install macOS {self.target_macos_version}' partition on the USB. This requires a tool that can write to HFS+ partitions from Windows (e.g., TransMac, HFSExplorer, or do this from a Mac/Linux environment).\n\n"
                "This tool CANNOT fully automate HFS+ partition writing or HFS+ file copying on Windows."
            )
            self._report_progress(f"GUIDANCE:\n{guidance_message}")
            QMessageBox.information(None, "Manual Steps Required for Windows USB", guidance_message) # Ensure QMessageBox is available or mocked

            self._report_progress("Windows USB installer preparation (EFI automated, macOS content manual guidance provided) initiated.")
            return True

        except Exception as e:
            self._report_progress(f"Error during Windows USB writing: {e}"); self._report_progress(traceback.format_exc())
            return False
        finally:
            if self.assigned_efi_letter:
                self._run_diskpart_script(f"select volume {self.assigned_efi_letter}\nremove letter={self.assigned_efi_letter}\nexit")
            self._cleanup_temp_files_and_dirs()

if __name__ == '__main__':
    import traceback
    from constants import MACOS_VERSIONS # Needed for _get_gibmacos_product_folder
    if platform.system() != "Windows": print("This script is for Windows standalone testing."); exit(1)
    print("USB Writer Windows Standalone Test - Installer Method Guidance")
    mock_download_dir = f"temp_macos_download_skyscope_{os.getpid()}"; os.makedirs(mock_download_dir, exist_ok=True)
    target_version_cli = sys.argv[1] if len(sys.argv) > 1 else "Sonoma"
    mock_product_name = f"000-00000 - macOS {target_version_cli} 14.x.x"
    mock_product_folder = os.path.join(mock_download_dir, "macOS Downloads", "publicrelease", mock_product_name)
    os.makedirs(os.path.join(mock_product_folder, "SharedSupport"), exist_ok=True)
    with open(os.path.join(mock_product_folder, "SharedSupport", "BaseSystem.dmg"), "w") as f: f.write("dummy base system dmg")

    if not os.path.exists(OC_TEMPLATE_DIR): os.makedirs(OC_TEMPLATE_DIR)
    if not os.path.exists(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC")): os.makedirs(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC"))
    with open(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC", "config-template.plist"), "wb") as f: plistlib.dump({"Test":True}, f, fmt=plistlib.PlistFormat.XML)

    disk_id_input = input("Enter target disk NUMBER (e.g., '1' for 'disk 1'). WIPES DISK: ")
    if not disk_id_input.isdigit(): print("Invalid disk number."); exit(1)

    if input(f"Sure to wipe disk {disk_id_input}? (yes/NO): ").lower() == 'yes':
        writer = USBWriterWindows(disk_id_input, mock_download_dir, print, True, target_version_cli)
        writer.format_and_write()
    else: print("Cancelled.")
    shutil.rmtree(mock_download_dir, ignore_errors=True)
    # shutil.rmtree(OC_TEMPLATE_DIR, ignore_errors=True) # Usually keep template
    print("Mock download dir cleaned up.")
