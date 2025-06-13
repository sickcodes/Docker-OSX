# usb_writer_windows.py (Refining EFI setup and manual step guidance)
import subprocess
import os
import time
import shutil
import re
import glob
import plistlib
import traceback
import sys # Added for psutil check

try:
    from PyQt6.QtWidgets import QMessageBox
except ImportError:
    # Mock QMessageBox for standalone testing or if PyQt6 is not available
    class QMessageBox:
        Information = 1 # Dummy enum value
        Warning = 2   # Dummy enum value
        Question = 3  # Dummy enum value
        YesRole = 0   # Dummy role
        NoRole = 1    # Dummy role

        @staticmethod
        def information(parent, title, message, buttons=None, defaultButton=None):
            print(f"INFO (QMessageBox mock): Title='{title}', Message='{message}'")
            return QMessageBox.Yes # Simulate a positive action if needed
        @staticmethod
        def warning(parent, title, message, buttons=None, defaultButton=None):
            print(f"WARNING (QMessageBox mock): Title='{title}', Message='{message}'")
            return QMessageBox.Yes # Simulate a positive action
        @staticmethod
        def critical(parent, title, message, buttons=None, defaultButton=None):
            print(f"CRITICAL (QMessageBox mock): Title='{title}', Message='{message}'")
            return QMessageBox.Yes # Simulate a positive action
        # Add other static methods if your code uses them, e.g. question
        @staticmethod
        def question(parent, title, message, buttons=None, defaultButton=None):
            print(f"QUESTION (QMessageBox mock): Title='{title}', Message='{message}'")
            return QMessageBox.Yes # Simulate 'Yes' for testing

        # Dummy button values if your code checks for specific button results
        Yes = 0x00004000
        No = 0x00010000
        Cancel = 0x00400000


try:
    from plist_modifier import enhance_config_plist
except ImportError:
    print("Warning: plist_modifier not found. Enhancement will be skipped.")
    def enhance_config_plist(plist_path, macos_version, progress_callback):
        if progress_callback:
            progress_callback("Skipping plist enhancement: plist_modifier not available.")
        return False # Indicate failure or no action

# This path needs to be correct relative to where usb_writer_windows.py is, or use an absolute path strategy
OC_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "EFI_template_installer")

class USBWriterWindows:
    def __init__(self, device_id_str: str, macos_download_path: str,
                 progress_callback=None, enhance_plist_enabled: bool = False,
                 target_macos_version: str = ""):
        self.device_id_str = device_id_str
        self.disk_number = "".join(filter(str.isdigit, device_id_str))
        self.physical_drive_path = f"\\\\.\\PhysicalDrive{self.disk_number}"
        self.macos_download_path = macos_download_path
        self.progress_callback = progress_callback
        self.enhance_plist_enabled = enhance_plist_enabled
        self.target_macos_version = target_macos_version

        pid = os.getpid()
        # Use system temp for Windows more reliably
        self.temp_dir_base = os.path.join(os.environ.get("TEMP", "C:\\Temp"), f"skyscope_usb_temp_{pid}")
        self.temp_basesystem_hfs_path = os.path.join(self.temp_dir_base, f"temp_basesystem_{pid}.hfs")
        self.temp_efi_build_dir = os.path.join(self.temp_dir_base, f"temp_efi_build_{pid}")
        self.temp_dmg_extract_dir = os.path.join(self.temp_dir_base, f"temp_dmg_extract_{pid}")

        self.temp_files_to_clean = [self.temp_basesystem_hfs_path] # Specific files outside temp_dir_base (if any)
        self.temp_dirs_to_clean = [self.temp_dir_base] # Base temp dir for this instance
        self.assigned_efi_letter = None

    def _report_progress(self, message: str):
        if self.progress_callback: self.progress_callback(message)
        else: print(message)

    def _run_command(self, command: list[str] | str, check=True, capture_output=False, timeout=None, shell=False, working_dir=None, creationflags=0):
        self._report_progress(f"Executing: {command if isinstance(command, str) else ' '.join(command)}")
        try:
            process = subprocess.run(command, check=check, capture_output=capture_output, text=True, timeout=timeout, shell=shell, cwd=working_dir, creationflags=creationflags)
            if capture_output:
                if process.stdout and process.stdout.strip(): self._report_progress(f"STDOUT: {process.stdout.strip()}")
                if process.stderr and process.stderr.strip(): self._report_progress(f"STDERR: {process.stderr.strip()}")
            return process
        except subprocess.TimeoutExpired: self._report_progress(f"Command timed out after {timeout} seconds."); raise
        except subprocess.CalledProcessError as e: self._report_progress(f"Error executing (code {e.returncode}): {e.stderr or e.stdout or str(e)}"); raise
        except FileNotFoundError: self._report_progress(f"Error: Command '{command[0] if isinstance(command, list) else command.split()[0]}' not found."); raise

    def _run_diskpart_script(self, script_content: str, capture_output_for_parse=False) -> str | None:
        script_file_path = os.path.join(self.temp_dir_base, f"diskpart_script_{os.getpid()}.txt")
        os.makedirs(self.temp_dir_base, exist_ok=True)
        output_text = None
        try:
            self._report_progress(f"Running diskpart script:\n{script_content}")
            with open(script_file_path, "w") as f: f.write(script_content)
            # Use CREATE_NO_WINDOW for subprocess.run with diskpart
            process = self._run_command(["diskpart", "/s", script_file_path], capture_output=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
            output_text = (process.stdout or "") + "\n" + (process.stderr or "")
            if capture_output_for_parse: return output_text
        finally:
            if os.path.exists(script_file_path):
                try: os.remove(script_file_path)
                except OSError as e: self._report_progress(f"Warning: Could not remove temp diskpart script {script_file_path}: {e}")
        return None # Explicitly return None if not capturing for parse or if it fails before return

    def _cleanup_temp_files_and_dirs(self):
        self._report_progress("Cleaning up temporary files and directories on Windows...")
        for f_path in self.temp_files_to_clean:
            if os.path.exists(f_path):
                try: os.remove(f_path)
                except OSError as e: self._report_progress(f"Error removing file {f_path}: {e}")

        for d_path in self.temp_dirs_to_clean: # self.temp_dir_base is the main one
            if os.path.exists(d_path):
                try: shutil.rmtree(d_path, ignore_errors=False) # Try with ignore_errors=False first
                except OSError as e:
                    self._report_progress(f"Error removing dir {d_path}: {e}. Attempting force remove.")
                    try: shutil.rmtree(d_path, ignore_errors=True) # Fallback to ignore_errors=True
                    except OSError as e_force: self._report_progress(f"Force remove for dir {d_path} also failed: {e_force}")


    def _find_available_drive_letter(self) -> str | None:
        import string
        used_letters = set()
        try:
            # Try to use psutil if available (e.g., when run from main_app.py)
            if 'psutil' in sys.modules:
                import psutil # Ensure it's imported here if check passes
                partitions = psutil.disk_partitions(all=True)
                for p in partitions:
                    if p.mountpoint and len(p.mountpoint) == 2 and p.mountpoint[1] == ':':
                        used_letters.add(p.mountpoint[0].upper())
            else: # Fallback if psutil is not available (e.g. pure standalone script)
                self._report_progress("psutil not available, using limited drive letter detection.")
                # Basic check, might not be exhaustive
                for letter in string.ascii_uppercase[3:]: # D onwards
                    if os.path.exists(f"{letter}:\\"):
                        used_letters.add(letter)

        except Exception as e:
            self._report_progress(f"Error detecting used drive letters: {e}. Proceeding with caution.")

        # Prefer letters from S onwards, less likely to conflict with user drives
        for letter in "STUVWXYZGHIJKLMNOPQR":
            if letter not in used_letters and letter > 'C': # Ensure it's not A, B, C
                return letter
        return None

    def check_dependencies(self):
        self._report_progress("Checking dependencies (diskpart, robocopy, 7z, dd for Windows [manual check])...")
        dependencies = ["diskpart", "robocopy", "7z"]
        missing = [dep for dep in dependencies if not shutil.which(dep)]
        if missing:
            msg = f"Missing dependencies: {', '.join(missing)}. `diskpart` & `robocopy` should be standard. `7z.exe` (7-Zip) needs to be installed and its directory added to the system PATH."
            self._report_progress(msg)
            raise RuntimeError(msg)
        self._report_progress("Please ensure a 'dd for Windows' utility (e.g., from SUSE, Cygwin, or http://www.chrysocome.net/dd) is installed and accessible from your PATH for writing the main macOS BaseSystem image.")
        return True

    def _find_gibmacos_asset(self, asset_name: str, product_folder_path: str | None = None, search_deep=True) -> str | None:
        search_locations = []
        if product_folder_path and os.path.isdir(product_folder_path):
            search_locations.extend([product_folder_path, os.path.join(product_folder_path, "SharedSupport")])

        # Also search directly in macos_download_path and a potential "macOS Install Data" subdirectory
        search_locations.extend([self.macos_download_path, os.path.join(self.macos_download_path, "macOS Install Data")])

        # If a version-specific folder exists at the root of macos_download_path (less common for gibMacOS structure)
        if os.path.isdir(self.macos_download_path):
            for item in os.listdir(self.macos_download_path):
                item_path = os.path.join(self.macos_download_path, item)
                if os.path.isdir(item_path) and self.target_macos_version.lower() in item.lower():
                    search_locations.append(item_path)
                    search_locations.append(os.path.join(item_path, "SharedSupport"))
                    # Assuming first match is good enough for this heuristic
                    break

        # Deduplicate search locations while preserving order (Python 3.7+)
        search_locations = list(dict.fromkeys(search_locations))

        for loc in search_locations:
            if not os.path.isdir(loc): continue

            path = os.path.join(loc, asset_name)
            if os.path.exists(path):
                self._report_progress(f"Found '{asset_name}' at: {path}")
                return path

            # Case-insensitive glob as fallback for direct name match
            # Create a pattern like "[bB][aA][sS][eE][sS][yY][sS][tT][eE][mM].[dD][mM][gG]"
            pattern_parts = [f"[{c.lower()}{c.upper()}]" if c.isalpha() else re.escape(c) for c in asset_name]
            insensitive_glob_pattern = "".join(pattern_parts)

            found_files = glob.glob(os.path.join(loc, insensitive_glob_pattern), recursive=False)
            if found_files:
                self._report_progress(f"Found '{asset_name}' via case-insensitive glob at: {found_files[0]}")
                return found_files[0]

        if search_deep:
            self._report_progress(f"Asset '{asset_name}' not found in primary locations, starting deep search in {self.macos_download_path}...")
            deep_search_pattern = os.path.join(self.macos_download_path, "**", asset_name)
            # Sort by length to prefer shallower paths, then alphabetically
            found_files_deep = sorted(glob.glob(deep_search_pattern, recursive=True), key=lambda p: (len(os.path.dirname(p)), p))
            if found_files_deep:
                self._report_progress(f"Found '{asset_name}' via deep search at: {found_files_deep[0]}")
                return found_files_deep[0]

        self._report_progress(f"Warning: Asset '{asset_name}' not found.")
        return None

    def _get_gibmacos_product_folder(self) -> str | None:
        # constants.py should be in the same directory or Python path
        try: from constants import MACOS_VERSIONS
        except ImportError: MACOS_VERSIONS = {} ; self._report_progress("Warning: MACOS_VERSIONS from constants.py not loaded.")

        # Standard gibMacOS download structure: macOS Downloads/publicrelease/012-34567 - macOS Sonoma 14.0
        base_path = os.path.join(self.macos_download_path, "macOS Downloads", "publicrelease")
        if not os.path.isdir(base_path):
            # Fallback if "macOS Downloads/publicrelease" is not present, use macos_download_path directly
            base_path = self.macos_download_path

        if os.path.isdir(base_path):
            potential_folders = []
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                # Check if it's a directory and matches target_macos_version (name or tag)
                version_tag_from_constants = MACOS_VERSIONS.get(self.target_macos_version, self.target_macos_version.lower().replace(" ", ""))
                if os.path.isdir(item_path) and \
                   (self.target_macos_version.lower() in item.lower() or \
                    version_tag_from_constants.lower() in item.lower().replace(" ", "")):
                    potential_folders.append(item_path)

            if potential_folders:
                # Sort by length (prefer shorter, more direct matches) or other heuristics if needed
                best_match = min(potential_folders, key=len)
                self._report_progress(f"Identified gibMacOS product folder: {best_match}")
                return best_match

        self._report_progress(f"Could not identify a specific product folder for '{self.target_macos_version}'. Using general download path: {self.macos_download_path}")
        return self.macos_download_path # Fallback to the root download path

    def _extract_hfs_from_dmg_or_pkg(self, dmg_or_pkg_path: str, output_hfs_path: str) -> bool:
        temp_extract_dir = self.temp_dmg_extract_dir
        os.makedirs(temp_extract_dir, exist_ok=True)
        current_target = dmg_or_pkg_path
        try:
            if not os.path.exists(current_target):
                self._report_progress(f"Error: Input file for HFS extraction does not exist: {current_target}"); return False

            # Step 1: If it's a PKG, extract DMGs from it.
            if dmg_or_pkg_path.lower().endswith(".pkg"):
                self._report_progress(f"Extracting DMG(s) from PKG: {current_target} using 7z...")
                # Using 'e' to extract flat, '-txar' for PKG/XAR format.
                self._run_command(["7z", "e", "-txar", current_target, "*.dmg", f"-o{temp_extract_dir}", "-y"], check=True)
                dmgs_in_pkg = glob.glob(os.path.join(temp_extract_dir, "*.dmg"))
                if not dmgs_in_pkg: self._report_progress(f"No DMG files found after extracting PKG: {current_target}"); return False
                # Select the largest DMG, assuming it's the main one.
                current_target = max(dmgs_in_pkg, key=os.path.getsize, default=None)
                if not current_target: self._report_progress("Failed to select a DMG from PKG contents."); return False
                self._report_progress(f"Using DMG from PKG: {current_target}")

            # Step 2: Ensure we have a DMG file.
            if not current_target or not current_target.lower().endswith(".dmg"):
                self._report_progress(f"Not a valid DMG file for HFS extraction: {current_target}"); return False

            basesystem_dmg_to_process = current_target
            # Step 3: If the DMG is not BaseSystem.dmg, try to extract BaseSystem.dmg from it.
            # This handles cases like SharedSupport.dmg containing BaseSystem.dmg.
            if "basesystem.dmg" not in os.path.basename(current_target).lower():
                self._report_progress(f"Extracting BaseSystem.dmg from container DMG: {current_target} using 7z...")
                # Extract recursively, looking for any path that includes BaseSystem.dmg
                self._run_command(["7z", "e", current_target, "*/BaseSystem.dmg", "-r", f"-o{temp_extract_dir}", "-y"], check=True)
                found_bs_dmg_list = glob.glob(os.path.join(temp_extract_dir, "**", "*BaseSystem.dmg"), recursive=True)
                if not found_bs_dmg_list: self._report_progress(f"No BaseSystem.dmg found within {current_target}"); return False
                basesystem_dmg_to_process = max(found_bs_dmg_list, key=os.path.getsize, default=None) # Largest if multiple
                if not basesystem_dmg_to_process: self._report_progress("Failed to select BaseSystem.dmg from container."); return False
                self._report_progress(f"Processing extracted BaseSystem.dmg: {basesystem_dmg_to_process}")

            # Step 4: Extract HFS partition image from BaseSystem.dmg.
            self._report_progress(f"Extracting HFS+ partition image from {basesystem_dmg_to_process} using 7z...")
            # Using 'e' to extract flat, '-tdmg' for DMG format. Looking for '*.hfs' or specific partition files.
            # Common HFS file names inside BaseSystem.dmg are like '2.hfs' or similar.
            # Sometimes they don't have .hfs extension, 7z might list them by index.
            # We will try to extract any .hfs file.
            self._run_command(["7z", "e", "-tdmg", basesystem_dmg_to_process, "*.hfs", f"-o{temp_extract_dir}", "-y"], check=True)
            hfs_files = glob.glob(os.path.join(temp_extract_dir, "*.hfs"))

            if not hfs_files: # If no .hfs, try extracting by common partition indices if 7z supports listing them for DMG
                self._report_progress("No direct '*.hfs' found. Attempting extraction of common HFS partition by index (e.g., '2', '3')...")
                # This is more complex as 7z CLI might not easily allow extracting by index directly without listing first.
                # For now, we rely on .hfs existing. If this fails, user might need to extract manually with 7z GUI.
                # A more robust solution would involve listing contents and then extracting the correct file.
                self._report_progress("Extraction by index is not implemented. Please ensure BaseSystem.dmg contains a directly extractable .hfs file.")
                return False

            if not hfs_files: self._report_progress(f"No HFS files found after extracting DMG: {basesystem_dmg_to_process}"); return False

            final_hfs_file = max(hfs_files, key=os.path.getsize, default=None) # Largest HFS file
            if not final_hfs_file: self._report_progress("Failed to select HFS file."); return False

            self._report_progress(f"Found HFS+ image: {final_hfs_file}. Moving to {output_hfs_path}")
            shutil.move(final_hfs_file, output_hfs_path)
            return True
        except Exception as e:
            self._report_progress(f"Error during HFS extraction: {e}\n{traceback.format_exc()}"); return False

    def _create_minimal_efi_template_content(self, efi_dir_path_root):
        self._report_progress(f"Minimal EFI template directory '{OC_TEMPLATE_DIR}' not found or is empty. Creating basic structure at {efi_dir_path_root}")
        efi_path = os.path.join(efi_dir_path_root, "EFI")
        oc_dir = os.path.join(efi_path, "OC")
        os.makedirs(os.path.join(efi_path, "BOOT"), exist_ok=True)
        os.makedirs(oc_dir, exist_ok=True)
        for sub_dir in ["Drivers", "Kexts", "ACPI", "Tools", "Resources"]:
            os.makedirs(os.path.join(oc_dir, sub_dir), exist_ok=True)

        # Create dummy BOOTx64.efi and OpenCore.efi
        with open(os.path.join(efi_path, "BOOT", "BOOTx64.efi"), "w") as f: f.write("Minimal Boot")
        with open(os.path.join(oc_dir, "OpenCore.efi"), "w") as f: f.write("Minimal OC")

        # Create a very basic config.plist
        basic_config = {
            "#WARNING": "This is a minimal config.plist. Replace with a full one for booting macOS!",
            "Misc": {"Security": {"ScanPolicy": 0, "SecureBootModel": "Disabled"}},
            "PlatformInfo": {"Generic": {"MLB": "CHANGE_ME_MLB", "SystemSerialNumber": "CHANGE_ME_SERIAL", "SystemUUID": "CHANGE_ME_UUID", "ROM": b"\x00\x00\x00\x00\x00\x00"}},
            "NVRAM": {"Add": {"4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38C14": {"DefaultBackgroundColor": "00000000", "UIScale": "01"}}}, # Basic NVRAM
            "UEFI": {"Drivers": ["OpenRuntime.efi"], "Input": {"KeySupport": True}} # Example
        }
        config_plist_path = os.path.join(oc_dir, "config.plist")
        try:
            with open(config_plist_path, 'wb') as fp:
                plistlib.dump(basic_config, fp, fmt=plistlib.PlistFormat.XML)
            self._report_progress(f"Created minimal config.plist at {config_plist_path}")
        except Exception as e:
            self._report_progress(f"Error creating minimal config.plist: {e}")


    def format_and_write(self) -> bool:
        try:
            self.check_dependencies()
            if os.path.exists(self.temp_dir_base):
                self._report_progress(f"Cleaning up existing temp base directory: {self.temp_dir_base}")
                shutil.rmtree(self.temp_dir_base, ignore_errors=True)
            os.makedirs(self.temp_dir_base, exist_ok=True)
            os.makedirs(self.temp_efi_build_dir, exist_ok=True) # For building EFI contents before copy
            os.makedirs(self.temp_dmg_extract_dir, exist_ok=True) # For 7z extractions

            self._report_progress(f"WARNING: ALL DATA ON DISK {self.disk_number} ({self.physical_drive_path}) WILL BE ERASED!")
            # Optional: Add a QMessageBox.question here for final confirmation in GUI mode

            self.assigned_efi_letter = self._find_available_drive_letter()
            if not self.assigned_efi_letter: raise RuntimeError("Could not find an available drive letter for EFI.")
            self._report_progress(f"Will attempt to assign letter {self.assigned_efi_letter}: to EFI partition.")

            installer_vol_label = f"Install macOS {self.target_macos_version}"
            # Ensure label for diskpart is max 32 chars for FAT32. "Install macOS Monterey" is 23 chars.
            diskpart_script_part1 = f"select disk {self.disk_number}\nclean\nconvert gpt\n"
            # Create EFI (ESP) partition, 550MB is generous and common
            diskpart_script_part1 += f"create partition efi size=550\nformat fs=fat32 quick label=EFI\nassign letter={self.assigned_efi_letter}\n"
            # Create main macOS partition (HFS+). Let diskpart use remaining space.
            # AF00 is Apple HFS+ type GUID. For APFS, it's 7C3457EF-0000-11AA-AA11-00306543ECAC
            # We create as HFS+ because BaseSystem is HFS+. Installer will convert if needed.
            diskpart_script_part1 += f"create partition primary label=\"{installer_vol_label[:31]}\" id=AF00\nexit\n"

            self._run_diskpart_script(diskpart_script_part1)
            self._report_progress("Disk partitioning complete. Waiting for volumes to settle...")
            time.sleep(5) # Give Windows time to recognize new partitions

            macos_partition_number_str = "2 (typically)"; macos_partition_offset_str = "Offset not automatically determined for Windows dd"
            try:
                # Attempt to get partition details. This is informational.
                diskpart_script_detail = f"select disk {self.disk_number}\nlist partition\nexit\n"
                detail_output = self._run_diskpart_script(diskpart_script_detail, capture_output_for_parse=True)
                if detail_output:
                    # Try to find Partition 2, assuming it's our target HFS+ partition
                    part_match = re.search(r"Partition 2\s+Primary\s+\d+\s+[GMK]B\s+(\d+)\s+[GMK]B", detail_output, re.IGNORECASE)
                    if part_match:
                        macos_partition_offset_str = f"{part_match.group(1)} MB (approx. from start of disk for Partition 2)"
                    else: # Fallback if specific regex fails
                        self._report_progress("Could not parse partition 2 offset, using generic message.")
            except Exception as e:
                self._report_progress(f"Could not get detailed partition info from diskpart: {e}")


            # --- OpenCore EFI Setup ---
            self._report_progress("Setting up OpenCore EFI on ESP...")
            if not os.path.isdir(OC_TEMPLATE_DIR) or not os.listdir(OC_TEMPLATE_DIR):
                self._report_progress(f"EFI_template_installer at '{OC_TEMPLATE_DIR}' is missing or empty.")
                self._create_minimal_efi_template_content(self.temp_efi_build_dir) # Create in temp_efi_build_dir
            else:
                self._report_progress(f"Copying EFI template from {OC_TEMPLATE_DIR} to {self.temp_efi_build_dir}")
                shutil.copytree(OC_TEMPLATE_DIR, self.temp_efi_build_dir, dirs_exist_ok=True)

            temp_config_plist_path = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config.plist")
            if not os.path.exists(temp_config_plist_path):
                template_plist_path = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist")
                if os.path.exists(template_plist_path):
                    self._report_progress(f"Using template config: {template_plist_path}")
                    shutil.copy2(template_plist_path, temp_config_plist_path)
                else:
                    self._report_progress("No config.plist or config-template.plist found in EFI template. Creating a minimal one.")
                    plistlib.dump({"#Comment": "Minimal config by Skyscope - REPLACE ME", "PlatformInfo": {"Generic": {"MLB": "CHANGE_ME"}}},
                                  open(temp_config_plist_path, 'wb'), fmt=plistlib.PlistFormat.XML)

            if self.enhance_plist_enabled and enhance_config_plist: # Check if function exists
                self._report_progress("Attempting to enhance config.plist (note: hardware detection for enhancement is primarily Linux-based)...")
                if enhance_config_plist(temp_config_plist_path, self.target_macos_version, self._report_progress):
                    self._report_progress("config.plist enhancement process complete.")
                else:
                    self._report_progress("config.plist enhancement process failed or had issues (this is expected on Windows for hardware-specifics).")

            target_efi_on_usb_root = f"{self.assigned_efi_letter}:\\"
            # Ensure the assigned drive letter is actually available before robocopy
            if not os.path.exists(target_efi_on_usb_root):
                time.sleep(3) # Extra wait
                if not os.path.exists(target_efi_on_usb_root):
                     raise RuntimeError(f"EFI partition {target_efi_on_usb_root} not accessible after formatting and assignment.")

            self._report_progress(f"Copying final EFI folder from {os.path.join(self.temp_efi_build_dir, 'EFI')} to USB ESP ({target_efi_on_usb_root}EFI)...")
            # Using robocopy: /E for subdirs (incl. empty), /S for non-empty, /NFL no file list, /NDL no dir list, /NJH no job header, /NJS no job summary, /NC no class, /NS no size, /NP no progress
            # /MT:8 for multithreading (default is 8, can be 1-128)
            self._run_command(["robocopy", os.path.join(self.temp_efi_build_dir, "EFI"), os.path.join(target_efi_on_usb_root, "EFI"), "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP", "/MT:8", "/R:3", "/W:5"], check=True)
            self._report_progress(f"EFI setup complete on {target_efi_on_usb_root}")

            # --- Prepare BaseSystem HFS Image ---
            self._report_progress("Locating BaseSystem image (DMG or PKG containing it) from downloaded assets...")
            product_folder_path = self._get_gibmacos_product_folder()
            basesystem_source_dmg_or_pkg = (
                self._find_gibmacos_asset("BaseSystem.dmg", product_folder_path) or
                self._find_gibmacos_asset("InstallAssistant.pkg", product_folder_path) or # Common for newer macOS
                self._find_gibmacos_asset("SharedSupport.dmg", product_folder_path) # Older fallback
            )
            if not basesystem_source_dmg_or_pkg:
                # Last resort: search for any large PKG file as it might be the installer
                if product_folder_path:
                    pkgs = glob.glob(os.path.join(product_folder_path, "*.pkg")) + glob.glob(os.path.join(product_folder_path, "SharedSupport", "*.pkg"))
                    if pkgs: basesystem_source_dmg_or_pkg = max(pkgs, key=os.path.getsize, default=None)
                if not basesystem_source_dmg_or_pkg:
                     raise RuntimeError("Could not find BaseSystem.dmg, InstallAssistant.pkg, or SharedSupport.dmg in expected locations.")

            self._report_progress(f"Selected source for HFS extraction: {basesystem_source_dmg_or_pkg}")
            if not self._extract_hfs_from_dmg_or_pkg(basesystem_source_dmg_or_pkg, self.temp_basesystem_hfs_path):
                raise RuntimeError(f"Failed to extract HFS+ image from '{basesystem_source_dmg_or_pkg}'. Check 7z output above.")

            # --- Guidance for Manual Steps ---
            abs_hfs_path_win = os.path.abspath(self.temp_basesystem_hfs_path).replace("/", "\\")
            abs_download_path_win = os.path.abspath(self.macos_download_path).replace("/", "\\")
            physical_drive_path_win = self.physical_drive_path # Already has escaped backslashes for \\.\

            # Try to find specific assets for better guidance
            install_info_plist_src = self._find_gibmacos_asset("InstallInfo.plist", product_folder_path, search_deep=False) or "InstallInfo.plist (find in product folder)"
            basesystem_dmg_src = self._find_gibmacos_asset("BaseSystem.dmg", product_folder_path, search_deep=False) or "BaseSystem.dmg"
            basesystem_chunklist_src = self._find_gibmacos_asset("BaseSystem.chunklist", product_folder_path, search_deep=False) or "BaseSystem.chunklist"
            main_installer_pkg_src = self._find_gibmacos_asset("InstallAssistant.pkg", product_folder_path, search_deep=False) or \
                                     self._find_gibmacos_asset("InstallESD.dmg", product_folder_path, search_deep=False) or \
                                     "InstallAssistant.pkg OR InstallESD.dmg (main installer package)"
            apple_diag_src = self._find_gibmacos_asset("AppleDiagnostics.dmg", product_folder_path, search_deep=False) or "AppleDiagnostics.dmg (if present)"


            guidance_message = (
                f"AUTOMATED EFI SETUP COMPLETE on drive {self.assigned_efi_letter}: (USB partition 1).\n"
                f"TEMPORARY BaseSystem HFS image prepared at: '{abs_hfs_path_win}'.\n\n"
                f"MANUAL STEPS REQUIRED FOR MAIN macOS PARTITION (USB partition {macos_partition_number_str} - '{installer_vol_label}'):\n"
                f"TARGET DISK: Disk {self.disk_number} ({physical_drive_path_win})\n"
                f"TARGET PARTITION FOR HFS+ CONTENT: Partition {macos_partition_number_str} (Offset from disk start: {macos_partition_offset_str}).\n\n"

                f"1. WRITE BaseSystem IMAGE:\n"
                f"   You MUST use a 'dd for Windows' utility. Open Command Prompt or PowerShell AS ADMINISTRATOR.\n"
                f"   Example command (VERIFY SYNTAX & TARGETS for YOUR dd tool! Incorrect use can WIPE OTHER DRIVES!):\n"
                f"   `dd if=\"{abs_hfs_path_win}\" of={physical_drive_path_win} bs=8M --progress` (if targeting whole disk with offset for partition 2)\n"
                f"   OR (if your dd supports writing directly to a partition by its number/offset, less common for \\\\.\\PhysicalDrive targets):\n"
                f"   `dd if=\"{abs_hfs_path_win}\" of=\\\\?\\Volume{{GUID_OF_PARTITION_2}}\ bs=8M --progress` (more complex to get GUID)\n"
                f"   It's often SAFER to write to the whole physical drive path ({physical_drive_path_win}) if your `dd` version calculates offsets correctly or if you specify the exact starting sector/byte offset for partition 2.\n"
                f"   The BaseSystem HFS image is approx. {os.path.getsize(self.temp_basesystem_hfs_path)/(1024*1024):.2f} MB.\n\n"

                f"2. COPY OTHER INSTALLER FILES (CRITICAL FOR OFFLINE INSTALLER):\n"
                f"   After `dd`-ing BaseSystem.hfs, the '{installer_vol_label}' partition on the USB needs more files from your download path: '{abs_download_path_win}'.\n"
                f"   This requires a tool that can WRITE to HFS+ partitions from Windows (e.g., TransMac, Paragon HFS+ for Windows, HFSExplorer with write capabilities if any), OR perform this step on macOS/Linux.\n\n"
                f"   KEY FILES/FOLDERS TO COPY from '{abs_download_path_win}' (likely within a subfolder named like '{os.path.basename(product_folder_path if product_folder_path else '')}') to the ROOT of the '{installer_vol_label}' USB partition:\n"
                f"     a. Create folder: `Install macOS {self.target_macos_version}.app` (this is a directory)\n"
                f"     b. Copy '{os.path.basename(install_info_plist_src)}' to the root of '{installer_vol_label}' partition.\n"
                f"     c. Copy '{os.path.basename(basesystem_dmg_src)}' AND '{os.path.basename(basesystem_chunklist_src)}' into: `System/Library/CoreServices/` (on '{installer_vol_label}')\n"
                f"     d. Copy '{os.path.basename(main_installer_pkg_src)}' into: `Install macOS {self.target_macos_version}.app/Contents/SharedSupport/`\n"
                f"        (Alternatively, for older macOS, sometimes into: `System/Installation/Packages/`)\n"
                f"     e. Copy '{os.path.basename(apple_diag_src)}' (if found) into: `Install macOS {self.target_macos_version}.app/Contents/SharedSupport/` (or a similar recovery/diagnostics path if known for your version).\n"
                f"     f. Ensure `boot.efi` (from the OpenCore EFI, often copied from `usr/standalone/i386/boot.efi` inside BaseSystem.dmg or similar) is placed at `System/Library/CoreServices/boot.efi` on the '{installer_vol_label}' partition. (Your EFI setup on partition 1 handles OpenCore booting, this is for the macOS installer itself).\n\n"

                f"3. (Optional but Recommended) Create `.IAProductInfo` file at the root of the '{installer_vol_label}' partition. This file is a symlink to `Install macOS {self.target_macos_version}.app/Contents/SharedSupport/InstallInfo.plist` in real installers. On Windows, you may need to copy the `InstallInfo.plist` to this location as well if symlinks are hard.\n\n"

                "IMPORTANT:\n"
                "- Without step 2 (copying additional assets), the USB will likely NOT work as a full offline installer and may only offer Internet Recovery (if OpenCore is correctly configured for network access).\n"
                "- The temporary BaseSystem HFS image at '{abs_hfs_path_win}' will be DELETED when you close this program or this message.\n"
            )
            self._report_progress(f"GUIDANCE FOR MANUAL STEPS:\n{guidance_message}")
            # Use the QMessageBox mock or actual if available
            QMessageBox.information(None, f"Manual Steps Required for Windows USB - {self.target_macos_version}", guidance_message)

            self._report_progress("Windows USB installer preparation (EFI automated, macOS content requires manual steps as detailed).")
            return True

        except Exception as e:
            self._report_progress(f"FATAL ERROR during Windows USB writing: {e}"); self._report_progress(traceback.format_exc())
            # Show error in QMessageBox as well if possible
            QMessageBox.critical(None, "USB Writing Failed", f"An error occurred: {e}\n\n{traceback.format_exc()}")
            return False
        finally:
            if self.assigned_efi_letter:
                self._report_progress(f"Attempting to remove drive letter assignment for {self.assigned_efi_letter}:")
                # Run silently, don't check for errors as it's cleanup
                self._run_diskpart_script(f"select volume {self.assigned_efi_letter}\nremove letter={self.assigned_efi_letter}\nexit", capture_output_for_parse=False)

            # Cleanup of self.temp_dir_base will handle all sub-temp-dirs and files within it.
            self._cleanup_temp_files_and_dirs()
            self._report_progress("Temporary files cleanup attempted.")

# Standalone test block
if __name__ == '__main__':
    import platform
    if platform.system() != "Windows":
        print("This script's standalone test mode is intended for Windows.")
        # sys.exit(1) # Use sys.exit for proper exit codes

    print("USB Writer Windows Standalone Test - Installer Method Guidance")

    # Mock constants if not available (e.g. running totally standalone)
    try: from constants import MACOS_VERSIONS
    except ImportError: MACOS_VERSIONS = {"Sonoma": "sonoma", "Ventura": "ventura"} ; print("Mocked MACOS_VERSIONS")

    pid_test = os.getpid()
    # Create a unique temp directory for this test run to avoid conflicts
    # Place it in user's Temp for better behavior on Windows
    test_run_temp_dir = os.path.join(os.environ.get("TEMP", "C:\\Temp"), f"skyscope_test_run_{pid_test}")
    os.makedirs(test_run_temp_dir, exist_ok=True)

    # Mock download directory structure within the test_run_temp_dir
    mock_download_dir = os.path.join(test_run_temp_dir, "mock_macos_downloads")
    os.makedirs(mock_download_dir, exist_ok=True)

    # Example: Sonoma. More versions could be added for thorough testing.
    target_version_test = "Sonoma"
    version_tag_test = MACOS_VERSIONS.get(target_version_test, target_version_test.lower())

    mock_product_name = f"012-34567 - macOS {target_version_test} 14.1" # Example name
    mock_product_folder = os.path.join(mock_download_dir, "macOS Downloads", "publicrelease", mock_product_name)
    mock_shared_support = os.path.join(mock_product_folder, "SharedSupport")
    os.makedirs(mock_shared_support, exist_ok=True)

    # Create dummy files that would be found by _find_gibmacos_asset and _extract_hfs_from_dmg_or_pkg
    # 1. Dummy InstallAssistant.pkg (which contains BaseSystem.dmg)
    dummy_pkg_path = os.path.join(mock_product_folder, "InstallAssistant.pkg")
    with open(dummy_pkg_path, "wb") as f: f.write(os.urandom(10*1024*1024)) # 10MB dummy PKG
    # For the _extract_hfs_from_dmg_or_pkg to work with 7z, it needs a real archive.
    # This test won't actually run 7z unless 7z is installed and the dummy files are valid archives.
    # The focus here is testing the script logic, not 7z itself.
    # So, we'll also create a dummy extracted BaseSystem.hfs for the guidance part.

    # 2. Dummy files for the guidance message (these would normally be in mock_product_folder or mock_shared_support)
    with open(os.path.join(mock_product_folder, "InstallInfo.plist"), "w") as f: f.write("<plist><dict></dict></plist>")
    with open(os.path.join(mock_shared_support, "BaseSystem.dmg"), "wb") as f: f.write(os.urandom(5*1024*1024)) # Dummy DMG
    with open(os.path.join(mock_shared_support, "BaseSystem.chunklist"), "w") as f: f.write("chunklist content")
    # AppleDiagnostics.dmg is optional
    with open(os.path.join(mock_shared_support, "AppleDiagnostics.dmg"), "wb") as f: f.write(os.urandom(1*1024*1024))


    # Ensure OC_TEMPLATE_DIR (EFI_template_installer) exists for the test or use the minimal creation.
    # Relative path from usb_writer_windows.py to EFI_template_installer
    abs_oc_template_dir = OC_TEMPLATE_DIR
    if not os.path.exists(abs_oc_template_dir):
        print(f"Warning: Test OC_TEMPLATE_DIR '{abs_oc_template_dir}' not found. Minimal EFI will be created by script if needed.")
        # Optionally, create a dummy one for test if you want to test the copy logic:
        # os.makedirs(os.path.join(abs_oc_template_dir, "EFI", "OC"), exist_ok=True)
        # with open(os.path.join(abs_oc_template_dir, "EFI", "OC", "config-template.plist"), "wb") as f: plistlib.dump({"TestTemplate":True}, f)
    else:
        print(f"Using existing OC_TEMPLATE_DIR for test: {abs_oc_template_dir}")


    disk_id_input = input("Enter target PHYSICAL DISK NUMBER for test (e.g., '1' for PhysicalDrive1). WARNING: THIS DISK WILL BE MODIFIED/WIPED by diskpart. BE ABSOLUTELY SURE. Enter 'skip' to not run diskpart stage: ")

    if disk_id_input.lower() == 'skip':
        print("Skipping disk operations. Guidance message will be shown with placeholder disk info.")
        # Create a writer instance with a dummy disk ID for logic testing without diskpart
        writer = USBWriterWindows("disk 0", mock_download_dir, print, True, target_version_test)
        # We need to manually create a dummy temp_basesystem.hfs for the guidance message part
        os.makedirs(writer.temp_dir_base, exist_ok=True)
        with open(writer.temp_basesystem_hfs_path, "wb") as f: f.write(os.urandom(1024*1024)) # 1MB dummy HFS
        # Manually call parts of format_and_write that don't involve diskpart
        writer.check_dependencies() # Still check other deps
        # Simulate EFI setup success for guidance
        writer.assigned_efi_letter = "X"
        # ... then generate and show guidance (this part is inside format_and_write)
        # This is a bit clunky for 'skip' mode. Full format_and_write is better if safe.
        print("Test in 'skip' mode is limited. Full test requires a dedicated test disk.")

    elif not disk_id_input.isdigit():
        print("Invalid disk number.")
    else:
        actual_disk_id_str = f"\\\\.\\PhysicalDrive{disk_id_input}" # Match format used by class
        confirm = input(f"ARE YOU ABSOLUTELY SURE you want to test on {actual_disk_id_str}? This involves running 'diskpart clean'. Type 'YESIDO' to confirm: ")
        if confirm == 'YESIDO':
            writer = USBWriterWindows(actual_disk_id_str, mock_download_dir, print, True, target_version_test)
            try:
                writer.format_and_write()
                print(f"Test run completed. Check disk {disk_id_input} and console output.")
            except Exception as e:
                print(f"Test run failed: {e}")
                traceback.print_exc()
        else:
            print("Test cancelled by user.")

    # Cleanup the test run's unique temp directory
    print(f"Cleaning up test run temp directory: {test_run_temp_dir}")
    shutil.rmtree(test_run_temp_dir, ignore_errors=True)

    print("Standalone test finished.")
```
