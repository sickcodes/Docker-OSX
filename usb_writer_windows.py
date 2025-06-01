# usb_writer_windows.py
import subprocess
import os
import time
import shutil

class USBWriterWindows:
    def __init__(self, device_id: str, opencore_qcow2_path: str, macos_qcow2_path: str, progress_callback=None):
        self.device_id = device_id
        # Construct PhysicalDrive path carefully
        disk_number_str = "".join(filter(str.isdigit, device_id))
        self.physical_drive_path = f"\\\\.\\PhysicalDrive{disk_number_str}"
        self.opencore_qcow2_path = opencore_qcow2_path
        self.macos_qcow2_path = macos_qcow2_path
        self.progress_callback = progress_callback

        pid = os.getpid()
        self.opencore_raw_path = f"opencore_temp_{pid}.raw"
        self.macos_raw_path = f"macos_main_temp_{pid}.raw"
        self.temp_efi_extract_dir = f"temp_efi_files_{pid}"

        self.temp_files_to_clean = [self.opencore_raw_path, self.macos_raw_path]
        self.temp_dirs_to_clean = [self.temp_efi_extract_dir]
        self.assigned_efi_letter = None

    def _report_progress(self, message: str):
        if self.progress_callback:
            self.progress_callback(message)
        else:
            print(message)

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
        except subprocess.TimeoutExpired:
            self._report_progress(f"Command timed out after {timeout} seconds.")
            raise
        except subprocess.CalledProcessError as e:
            self._report_progress(f"Error executing (code {e.returncode}): {e.stderr or e.stdout or str(e)}")
            raise
        except FileNotFoundError:
            self._report_progress(f"Error: Command '{command[0] if isinstance(command, list) else command.split()[0]}' not found.")
            raise

    def _run_diskpart_script(self, script_content: str):
        script_file_path = f"diskpart_script_{os.getpid()}.txt"
        with open(script_file_path, "w") as f:
            f.write(script_content)
        try:
            self._report_progress(f"Running diskpart script...\n{script_content}")
            self._run_command(["diskpart", "/s", script_file_path], capture_output=True, check=False)
        finally:
            if os.path.exists(script_file_path): os.remove(script_file_path)

    def _cleanup_temp_files_and_dirs(self):
        self._report_progress("Cleaning up...")
        for f_path in self.temp_files_to_clean:
            if os.path.exists(f_path): os.remove(f_path)
        for d_path in self.temp_dirs_to_clean:
            if os.path.exists(d_path): shutil.rmtree(d_path, ignore_errors=True)

    def _find_available_drive_letter(self) -> str | None:
        import string
        # This is a placeholder. Actual psutil or ctypes calls would be more robust.
        # For now, assume 'S' is available if not 'E' through 'Z'.
        return 'S'

    def check_dependencies(self):
        self._report_progress("Checking dependencies (qemu-img, diskpart, robocopy)... DD for Win & 7z are manual checks.")
        dependencies = ["qemu-img", "diskpart", "robocopy"]
        missing = [dep for dep in dependencies if not shutil.which(dep)]
        if missing:
            raise RuntimeError(f"Missing dependencies: {', '.join(missing)}. qemu-img needs install & PATH.")
        self._report_progress("Base dependencies found. Ensure 'dd for Windows' and '7z.exe' are in PATH if needed.")
        return True

    def format_and_write(self) -> bool:
        try:
            self.check_dependencies()
            self._cleanup_temp_files_and_dirs()
            os.makedirs(self.temp_efi_extract_dir, exist_ok=True)

            disk_number = "".join(filter(str.isdigit, self.device_id))
            self._report_progress(f"WARNING: ALL DATA ON DISK {disk_number} ({self.physical_drive_path}) WILL BE ERASED!")

            self.assigned_efi_letter = self._find_available_drive_letter()
            if not self.assigned_efi_letter:
                raise RuntimeError("Could not find an available drive letter for EFI.")
            self._report_progress(f"Attempting to use letter {self.assigned_efi_letter}: for EFI.")

            script = f"select disk {disk_number}\nclean\nconvert gpt\n"
            script += f"create partition efi size=550\nformat fs=fat32 quick label=EFI\nassign letter={self.assigned_efi_letter}\n"
            script += "create partition primary label=macOS_USB\nexit\n"
            self._run_diskpart_script(script)
            time.sleep(5)

            self._report_progress(f"Converting OpenCore QCOW2 to RAW: {self.opencore_raw_path}")
            self._run_command(["qemu-img", "convert", "-O", "raw", self.opencore_qcow2_path, self.opencore_raw_path])

            self._report_progress("Extracting EFI files (using 7z if available)...")
            if shutil.which("7z"):
                # Simplified 7z call, assumes EFI folder is at root of first partition image by 7z
                self._run_command([
                    "7z", "x", self.opencore_raw_path,
                    f"-o{self.temp_efi_extract_dir}", "EFI", "-r", "-y"
                ], check=False)
                source_efi_folder = os.path.join(self.temp_efi_extract_dir, "EFI")
                if not os.path.isdir(source_efi_folder):
                    # Fallback: check if files were extracted to temp_efi_extract_dir directly
                    if os.path.exists(os.path.join(self.temp_efi_extract_dir, "BOOTX64.EFI")):
                        source_efi_folder = self.temp_efi_extract_dir
                    else:
                        raise RuntimeError("Could not extract EFI folder using 7-Zip.")

                target_efi_on_usb = f"{self.assigned_efi_letter}:\\EFI"
                if not os.path.exists(f"{self.assigned_efi_letter}:\\"):
                     raise RuntimeError(f"EFI partition {self.assigned_efi_letter}: not accessible after assign.")
                if not os.path.exists(target_efi_on_usb): os.makedirs(target_efi_on_usb, exist_ok=True)
                self._report_progress(f"Copying EFI files to {target_efi_on_usb}")
                self._run_command(["robocopy", source_efi_folder, target_efi_on_usb, "/E", "/S", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP"], check=True)
            else:
                raise RuntimeError("7-Zip CLI (7z.exe) not found in PATH for EFI extraction.")

            self._report_progress(f"Converting macOS QCOW2 to RAW: {self.macos_raw_path}")
            self._run_command(["qemu-img", "convert", "-O", "raw", self.macos_qcow2_path, self.macos_raw_path])

            self._report_progress("Windows RAW macOS image writing is a placeholder.")
            self._report_progress(f"RAW image at: {self.macos_raw_path}")
            self._report_progress(f"Target physical drive: {self.physical_drive_path}")
            self._report_progress("User needs to use 'dd for Windows' to write the above raw image to the second partition of the USB drive.")
            # Placeholder for actual dd command, as it's complex and risky to automate fully without specific dd tool knowledge
            # E.g. dd if=self.macos_raw_path of=\\\\.\\PhysicalDriveX --partition 2 bs=4M status=progress (syntax depends on dd variant)

            self._report_progress("Windows USB writing process (EFI part done, macOS part placeholder) completed.")
            return True

        except Exception as e:
            self._report_progress(f"Error during Windows USB writing: {e}")
            import traceback
            self._report_progress(traceback.format_exc())
            return False
        finally:
            if self.assigned_efi_letter:
                self._run_diskpart_script(f"select volume {self.assigned_efi_letter}\nremove letter={self.assigned_efi_letter}\nexit")
            self._cleanup_temp_files_and_dirs()

if __name__ == '__main__':
    if platform.system() != "Windows":
        print("This script is for Windows standalone testing."); exit(1)
    print("USB Writer Windows Standalone Test - Partial Implementation")
    # Requires Admin privileges
    mock_oc = "mock_oc_win.qcow2"
    mock_mac = "mock_mac_win.qcow2"
    if not os.path.exists(mock_oc): subprocess.run(["qemu-img", "create", "-f", "qcow2", mock_oc, "384M"])
    if not os.path.exists(mock_mac): subprocess.run(["qemu-img", "create", "-f", "qcow2", mock_mac, "1G"])

    disk_id = input("Enter target disk ID (e.g., '1' for 'disk 1'). WIPES DISK: ")
    if not disk_id.isdigit(): print("Invalid disk ID."); exit(1)
    actual_disk_id = f"disk {disk_id}" # This is how it's used in the class, but the input is just the number.

    if input(f"Sure to wipe disk {disk_id}? (yes/NO): ").lower() == 'yes':
        # Pass the disk number string to the constructor, it will form \\.\PhysicalDriveX
        writer = USBWriterWindows(disk_id, mock_oc, mock_mac, print)
        writer.format_and_write()
    else: print("Cancelled.")

    if os.path.exists(mock_oc): os.remove(mock_oc)
    if os.path.exists(mock_mac): os.remove(mock_mac)
    print("Mocks cleaned.")
