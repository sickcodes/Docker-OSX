# usb_writer_windows.py
import subprocess
import os
import time
import shutil
import re # For parsing diskpart output
import sys # For checking psutil import

# Try to import QMessageBox for the placeholder, otherwise use a mock for standalone test
try:
    from PyQt6.QtWidgets import QMessageBox
except ImportError:
    class QMessageBox: # Mock for standalone testing
        @staticmethod
        def information(*args): print(f"INFO (QMessageBox mock): Title='{args[1]}', Message='{args[2]}'")
        @staticmethod
        def warning(*args): print(f"WARNING (QMessageBox mock): Title='{args[1]}', Message='{args[2]}'"); return QMessageBox # Mock button press
        Yes = 1 # Mock value
        No = 0 # Mock value
        Cancel = 0 # Mock value


class USBWriterWindows:
    def __init__(self, device_id: str, opencore_qcow2_path: str, macos_qcow2_path: str,
                 progress_callback=None, enhance_plist_enabled: bool = False, target_macos_version: str = ""):
        # device_id is expected to be the disk number string, e.g., "1", "2" or "disk 1", "disk 2"
        self.disk_number = "".join(filter(str.isdigit, device_id))
        if not self.disk_number:
            raise ValueError(f"Invalid device_id format: '{device_id}'. Must contain a disk number.")

        self.physical_drive_path = f"\\\\.\\PhysicalDrive{self.disk_number}"

        self.opencore_qcow2_path = opencore_qcow2_path
        self.macos_qcow2_path = macos_qcow2_path
        self.progress_callback = progress_callback
        self.enhance_plist_enabled = enhance_plist_enabled # Not used in Windows writer yet
        self.target_macos_version = target_macos_version # Not used in Windows writer yet

        pid = os.getpid()
        self.opencore_raw_path = f"opencore_temp_{pid}.raw"
        self.macos_raw_path = f"macos_main_temp_{pid}.raw"
        self.temp_efi_extract_dir = f"temp_efi_files_{pid}"

        self.temp_files_to_clean = [self.opencore_raw_path, self.macos_raw_path]
        self.temp_dirs_to_clean = [self.temp_efi_extract_dir]
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
        script_file_path = f"diskpart_script_{os.getpid()}.txt"
        with open(script_file_path, "w") as f: f.write(script_content)
        output_text = "" # Initialize to empty string
        try:
            self._report_progress(f"Running diskpart script:\n{script_content}")
            process = self._run_command(["diskpart", "/s", script_file_path], capture_output=True, check=False)
            output_text = (process.stdout or "") + "\n" + (process.stderr or "") # Combine, as diskpart output can be inconsistent

            # Check for known success messages, otherwise assume potential issue or log output for manual check.
            # This is not a perfect error check for diskpart.
            success_indicators = [
                "DiskPart successfully", "successfully completed", "succeeded in creating",
                "successfully formatted", "successfully assigned"
            ]
            has_success_indicator = any(indicator in output_text for indicator in success_indicators)
            has_error_indicator = "Virtual Disk Service error" in output_text or "DiskPart has encountered an error" in output_text

            if has_error_indicator:
                 self._report_progress(f"Diskpart script may have failed. Output:\n{output_text}")
                 # Optionally raise an error here if script is critical
                 # raise subprocess.CalledProcessError(1, "diskpart", output=output_text)
            elif not has_success_indicator and "There are no partitions on this disk to show" not in output_text: # Allow benign message
                 self._report_progress(f"Diskpart script output does not clearly indicate success. Output:\n{output_text}")


            if capture_output_for_parse:
                return output_text
        finally:
            if os.path.exists(script_file_path): os.remove(script_file_path)
        return output_text if capture_output_for_parse else None # Return None if not capturing for parse


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
            # Check if psutil was imported by the main application
            if 'psutil' in sys.modules:
                partitions = sys.modules['psutil'].disk_partitions(all=True)
                for p in partitions:
                    if p.mountpoint and len(p.mountpoint) >= 2 and p.mountpoint[1] == ':': # Check for "X:"
                        used_letters.add(p.mountpoint[0].upper())
        except Exception as e:
            self._report_progress(f"Could not list used drive letters with psutil: {e}. Will try common letters.")

        for letter in "STUVWXYZGHIJKLMNOPQR":
            if letter not in used_letters and letter > 'D': # Avoid A, B, C, D
                # Further check if letter is truly available (e.g. subst) - more complex, skip for now
                return letter
        return None

    def check_dependencies(self):
        self._report_progress("Checking dependencies (qemu-img, diskpart, robocopy)... DD for Win & 7z are manual checks.")
        dependencies = ["qemu-img", "diskpart", "robocopy"]; missing = [dep for dep in dependencies if not shutil.which(dep)]
        if missing: raise RuntimeError(f"Missing dependencies: {', '.join(missing)}. qemu-img needs install & PATH.")
        self._report_progress("Base dependencies found. Ensure 'dd for Windows' and '7z.exe' are in PATH if needed.")
        return True

    def format_and_write(self) -> bool:
        try:
            self.check_dependencies()
            self._cleanup_temp_files_and_dirs() # Clean before start
            os.makedirs(self.temp_efi_extract_dir, exist_ok=True)

            self._report_progress(f"WARNING: ALL DATA ON DISK {self.disk_number} ({self.physical_drive_path}) WILL BE ERASED!")

            self.assigned_efi_letter = self._find_available_drive_letter()
            if not self.assigned_efi_letter: raise RuntimeError("Could not find an available drive letter for EFI.")
            self._report_progress(f"Will attempt to assign letter {self.assigned_efi_letter}: to EFI partition.")

            diskpart_script_part1 = f"select disk {self.disk_number}\nclean\nconvert gpt\n"
            diskpart_script_part1 += f"create partition efi size=550\nformat fs=fat32 quick label=EFI\nassign letter={self.assigned_efi_letter}\n"
            diskpart_script_part1 += "create partition primary label=macOS_USB\nexit\n"
            self._run_diskpart_script(diskpart_script_part1)
            time.sleep(5)

            macos_partition_offset_str = "Offset not determined"
            macos_partition_number_str = "2 (assumed)"

            diskpart_script_detail = f"select disk {self.disk_number}\nselect partition 2\ndetail partition\nexit\n"
            detail_output = self._run_diskpart_script(diskpart_script_detail, capture_output_for_parse=True)

            if detail_output:
                self._report_progress(f"Detail Partition Output:\n{detail_output}")
                offset_match = re.search(r"Offset in Bytes\s*:\s*(\d+)", detail_output, re.IGNORECASE)
                if offset_match: macos_partition_offset_str = f"{offset_match.group(1)} bytes ({int(offset_match.group(1)) // (1024*1024)} MiB)"

                # Try to find the line "Partition X" where X is the number we want
                part_num_search = re.search(r"Partition\s+(\d+)\s*\n\s*Type", detail_output, re.IGNORECASE | re.MULTILINE)
                if part_num_search:
                    macos_partition_number_str = part_num_search.group(1)
                    self._report_progress(f"Determined macOS partition number: {macos_partition_number_str}")
                else: # Fallback if the above specific regex fails
                    # Look for lines like "Partition 2", "Type : xxxxx"
                    # This is brittle if diskpart output format changes
                    partition_lines = [line for line in detail_output.splitlines() if "Partition " in line and "Type  :" in line]
                    if len(partition_lines) > 0 : # Assuming the one we want is the last "Partition X" before other details
                        last_part_match = re.search(r"Partition\s*(\d+)", partition_lines[-1])
                        if last_part_match: macos_partition_number_str = last_part_match.group(1)


            self._report_progress(f"Converting OpenCore QCOW2 to RAW: {self.opencore_raw_path}")
            self._run_command(["qemu-img", "convert", "-O", "raw", self.opencore_qcow2_path, self.opencore_raw_path])

            if shutil.which("7z"):
                self._report_progress("Attempting EFI extraction using 7-Zip...")
                self._run_command(["7z", "x", self.opencore_raw_path, f"-o{self.temp_efi_extract_dir}", "EFI", "-r", "-y"], check=False)
                source_efi_folder = os.path.join(self.temp_efi_extract_dir, "EFI")
                if not os.path.isdir(source_efi_folder):
                    if os.path.exists(os.path.join(self.temp_efi_extract_dir, "BOOTX64.EFI")): source_efi_folder = self.temp_efi_extract_dir
                    else: raise RuntimeError("Could not extract EFI folder using 7-Zip from OpenCore image.")

                target_efi_on_usb = f"{self.assigned_efi_letter}:\\EFI"
                if not os.path.exists(f"{self.assigned_efi_letter}:\\"): # Check if drive letter is mounted
                    time.sleep(3) # Wait a bit more
                    if not os.path.exists(f"{self.assigned_efi_letter}:\\"):
                         # Attempt to re-assign just in case
                         self._report_progress(f"Re-assigning drive letter {self.assigned_efi_letter} to EFI partition...")
                         reassign_script = f"select disk {self.disk_number}\nselect partition 1\nassign letter={self.assigned_efi_letter}\nexit\n"
                         self._run_diskpart_script(reassign_script)
                         time.sleep(3)
                         if not os.path.exists(f"{self.assigned_efi_letter}:\\"):
                             raise RuntimeError(f"EFI partition {self.assigned_efi_letter}: not accessible after assign/re-assign.")

                if not os.path.exists(target_efi_on_usb): os.makedirs(target_efi_on_usb, exist_ok=True)
                self._report_progress(f"Copying EFI files from '{source_efi_folder}' to '{target_efi_on_usb}'")
                self._run_command(["robocopy", source_efi_folder, target_efi_on_usb, "/E", "/S", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP", "/XO"], check=True) # Added /XO to exclude older
            else: raise RuntimeError("7-Zip CLI (7z.exe) not found in PATH for EFI extraction.")

            self._report_progress(f"Converting macOS QCOW2 to RAW: {self.macos_raw_path}")
            self._run_command(["qemu-img", "convert", "-O", "raw", self.macos_qcow2_path, self.macos_raw_path])

            abs_macos_raw_path = os.path.abspath(self.macos_raw_path)
            guidance_message = (
                f"RAW macOS image conversion complete:\n'{abs_macos_raw_path}'\n\n"
                f"Target USB: Disk {self.disk_number} (Path: {self.physical_drive_path})\n"
                f"The target macOS partition is: Partition {macos_partition_number_str}\n"
                f"Calculated Offset (approx): {macos_partition_offset_str}\n\n"
                "MANUAL STEP REQUIRED using a 'dd for Windows' utility:\n"
                "1. Open Command Prompt or PowerShell AS ADMINISTRATOR.\n"
                "2. Carefully identify your 'dd for Windows' utility and its exact syntax.\n"
                "   Common utilities: dd from SUSE (recommended), dd by chrysocome.net.\n"
                "3. Example 'dd' command (SYNTAX VARIES GREATLY BETWEEN DD TOOLS!):\n"
                f"   `dd if=\"{abs_macos_raw_path}\" of={self.physical_drive_path} bs=4M --progress`\n"
                "   (This example writes to the whole disk, which might be okay if your macOS partition is the first primary after EFI and occupies the rest). \n"
                "   A SAFER (but more complex) approach if your 'dd' supports it, is to write directly to the partition's OFFSET (requires dd that handles PhysicalDrive offsets correctly):\n"
                f"   `dd if=\"{abs_macos_raw_path}\" of={self.physical_drive_path} seek=<PARTITION_OFFSET_IN_BLOCKS_OR_BYTES> bs=<YOUR_BLOCK_SIZE> ...`\n"
                "   (The 'seek' parameter and its units depend on your dd tool. The offset from diskpart is in bytes.)\n\n"
                "VERIFY YOUR DD COMMAND AND TARGETS BEFORE EXECUTION. DATA LOSS IS LIKELY IF INCORRECT.\n"
                "This tool cannot automate this step due to the variability and risks of 'dd' utilities on Windows."
            )
            self._report_progress(f"GUIDANCE:\n{guidance_message}")
            QMessageBox.information(None, "Manual macOS Image Write Required", guidance_message)

            self._report_progress("Windows USB writing (EFI part automated, macOS part manual guidance provided) process initiated.")
            return True

        except Exception as e:
            self._report_progress(f"Error during Windows USB writing: {e}")
            import traceback; self._report_progress(traceback.format_exc())
            return False
        finally:
            if self.assigned_efi_letter:
                self._run_diskpart_script(f"select volume {self.assigned_efi_letter}\nremove letter={self.assigned_efi_letter}\nexit")
            self._cleanup_temp_files_and_dirs()

if __name__ == '__main__':
    if platform.system() != "Windows":
        print("This script is for Windows standalone testing."); exit(1)
    print("USB Writer Windows Standalone Test - Improved Guidance")
    mock_oc = "mock_oc_win.qcow2"; mock_mac = "mock_mac_win.qcow2"
    # Ensure qemu-img is available for mock file creation
    if not shutil.which("qemu-img"):
        print("qemu-img not found, cannot create mock files for test. Exiting.")
        exit(1)
    if not os.path.exists(mock_oc): subprocess.run(["qemu-img", "create", "-f", "qcow2", mock_oc, "384M"])
    if not os.path.exists(mock_mac): subprocess.run(["qemu-img", "create", "-f", "qcow2", mock_mac, "1G"])

    disk_id_input = input("Enter target disk NUMBER (e.g., '1' for 'disk 1'). THIS DISK WILL BE WIPES: ")
    if not disk_id_input.isdigit(): print("Invalid disk number."); exit(1)

    if input(f"Sure to wipe disk {disk_id_input}? (yes/NO): ").lower() == 'yes':
        # USBWriterWindows expects just the disk number string (e.g., "1")
        writer = USBWriterWindows(disk_id_input, mock_oc, mock_mac, print)
        writer.format_and_write()
    else: print("Cancelled.")

    if os.path.exists(mock_oc): os.remove(mock_oc)
    if os.path.exists(mock_mac): os.remove(mock_mac)
    print("Mocks cleaned.")
