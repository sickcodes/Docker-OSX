# usb_writer_macos.py
import subprocess
import os
import time
import shutil # For checking command existence
import plistlib # For parsing diskutil list -plist output

class USBWriterMacOS:
    def __init__(self, device: str, opencore_qcow2_path: str, macos_qcow2_path: str,
                 progress_callback=None, enhance_plist_enabled: bool = False, target_macos_version: str = ""): # New args
        self.device = device # Should be like /dev/diskX
        self.opencore_qcow2_path = opencore_qcow2_path
        self.macos_qcow2_path = macos_qcow2_path
        self.progress_callback = progress_callback
        self.enhance_plist_enabled = enhance_plist_enabled # Store
        self.target_macos_version = target_macos_version # Store

        pid = os.getpid()
        self.opencore_raw_path = f"opencore_temp_{pid}.raw"
        self.macos_raw_path = f"macos_main_temp_{pid}.raw"
        self.temp_opencore_mount = f"/tmp/opencore_efi_temp_skyscope_{pid}"
        self.temp_usb_esp_mount = f"/tmp/usb_esp_temp_skyscope_{pid}"
        self.temp_macos_source_mount = f"/tmp/macos_source_temp_skyscope_{pid}"
        self.temp_usb_macos_target_mount = f"/tmp/usb_macos_target_temp_skyscope_{pid}"

        self.temp_files_to_clean = [self.opencore_raw_path, self.macos_raw_path]
        self.temp_mount_points_to_clean = [
            self.temp_opencore_mount, self.temp_usb_esp_mount,
            self.temp_macos_source_mount, self.temp_usb_macos_target_mount
        ]
        self.attached_raw_images_devices = [] # Store devices from hdiutil attach

    def _report_progress(self, message: str):
        print(message) # For standalone testing
        if self.progress_callback:
            self.progress_callback(message)

    def _run_command(self, command: list[str], check=True, capture_output=False, timeout=None):
        self._report_progress(f"Executing: {' '.join(command)}")
        try:
            process = subprocess.run(
                command, check=check, capture_output=capture_output, text=True, timeout=timeout
            )
            if capture_output:
                if process.stdout and process.stdout.strip():
                    self._report_progress(f"STDOUT: {process.stdout.strip()}")
                if process.stderr and process.stderr.strip():
                    self._report_progress(f"STDERR: {process.stderr.strip()}")
            return process
        except subprocess.TimeoutExpired:
            self._report_progress(f"Command {' '.join(command)} timed out after {timeout} seconds.")
            raise
        except subprocess.CalledProcessError as e:
            self._report_progress(f"Error executing {' '.join(command)} (code {e.returncode}): {e.stderr or e.stdout or str(e)}")
            raise
        except FileNotFoundError:
            self._report_progress(f"Error: Command '{command[0]}' not found. Is it installed and in PATH?")
            raise

    def _cleanup_temp_files(self):
        self._report_progress("Cleaning up temporary image files...")
        for f_path in self.temp_files_to_clean:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                    self._report_progress(f"Removed {f_path}")
                except OSError as e:
                    self._report_progress(f"Error removing {f_path}: {e}")

    def _unmount_path(self, mount_path_or_device, is_device=False, force=False):
        target = mount_path_or_device
        cmd_base = ["diskutil"]
        action = "unmountDisk" if is_device else "unmount"

        if force:
            cmd = cmd_base + [action, "force", target]
        else:
            cmd = cmd_base + [action, target]

        is_target_valid_for_unmount = (os.path.ismount(mount_path_or_device) and not is_device) or \
                                     (is_device and os.path.exists(target))

        if is_target_valid_for_unmount:
            self._report_progress(f"Attempting to unmount {target} (Action: {action}, Force: {force})...")
            self._run_command(cmd, check=False, timeout=30)

    def _detach_raw_image_device(self, device_path):
        if device_path and os.path.exists(device_path):
            self._report_progress(f"Detaching raw image device {device_path}...")
            try:
                info_check = subprocess.run(["diskutil", "info", device_path], capture_output=True, text=True, check=False)
                if info_check.returncode == 0:
                    self._run_command(["hdiutil", "detach", device_path, "-force"], check=False, timeout=30)
                else:
                    self._report_progress(f"Device {device_path} appears invalid or already detached.")
            except Exception as e:
                 self._report_progress(f"Exception while checking/detaching {device_path}: {e}")

    def _cleanup_all_mounts_and_mappings(self):
        self._report_progress("Cleaning up all temporary mounts and attached raw images...")
        for mp in reversed(self.temp_mount_points_to_clean):
            self._unmount_path(mp, force=True)
            if os.path.exists(mp):
                try: os.rmdir(mp)
                except OSError as e: self._report_progress(f"Could not rmdir {mp}: {e}")

        devices_to_detach = list(self.attached_raw_images_devices)
        for dev_path in devices_to_detach:
            self._detach_raw_image_device(dev_path)
        self.attached_raw_images_devices = []


    def check_dependencies(self):
        self._report_progress("Checking dependencies (qemu-img, diskutil, hdiutil, rsync)...")
        dependencies = ["qemu-img", "diskutil", "hdiutil", "rsync"]
        missing_deps = []
        for dep in dependencies:
            if not shutil.which(dep):
                missing_deps.append(dep)

        if missing_deps:
            msg = f"Missing dependencies: {', '.join(missing_deps)}. `qemu-img` might need to be installed (e.g., via Homebrew: `brew install qemu`). `diskutil`, `hdiutil`, `rsync` are usually standard on macOS."
            self._report_progress(msg)
            raise RuntimeError(msg)

        self._report_progress("All critical dependencies found.")
        return True

    def _get_partition_device_id(self, parent_disk_id_str: str, partition_label_or_type: str) -> str | None:
        """Finds partition device ID by Volume Name or Content Hint."""
        target_disk_id = parent_disk_id_str.replace("/dev/", "")
        self._report_progress(f"Searching for partition '{partition_label_or_type}' on disk '{target_disk_id}'")
        try:
            result = self._run_command(["diskutil", "list", "-plist", target_disk_id], capture_output=True)
            if not result.stdout:
                self._report_progress(f"No stdout from diskutil list for {target_disk_id}")
                return None

            plist_data = plistlib.loads(result.stdout.encode('utf-8'))

            all_disks_and_partitions = plist_data.get("AllDisksAndPartitions", [])
            if not isinstance(all_disks_and_partitions, list):
                if plist_data.get("DeviceIdentifier") == target_disk_id:
                    all_disks_and_partitions = [plist_data]
                else:
                    all_disks_and_partitions = []

            for disk_info_entry in all_disks_and_partitions:
                current_disk_id_in_plist = disk_info_entry.get("DeviceIdentifier")
                if current_disk_id_in_plist == target_disk_id:
                    for part_info in disk_info_entry.get("Partitions", []):
                        vol_name = part_info.get("VolumeName")
                        content_hint = part_info.get("Content")
                        device_id = part_info.get("DeviceIdentifier")

                        if device_id:
                            if vol_name and vol_name.strip().lower() == partition_label_or_type.strip().lower():
                                self._report_progress(f"Found partition by VolumeName: {vol_name} -> /dev/{device_id}")
                                return f"/dev/{device_id}"
                            if content_hint and content_hint.strip().lower() == partition_label_or_type.strip().lower():
                                self._report_progress(f"Found partition by Content type: {content_hint} -> /dev/{device_id}")
                                return f"/dev/{device_id}"

            self._report_progress(f"Partition '{partition_label_or_type}' not found on disk '{target_disk_id}'.")
            return None
        except Exception as e:
            self._report_progress(f"Error parsing 'diskutil list -plist {target_disk_id}': {e}")
            return None

    def format_and_write(self) -> bool:
        try:
            self.check_dependencies()
            self._cleanup_all_mounts_and_mappings()

            for mp in self.temp_mount_points_to_clean:
                os.makedirs(mp, exist_ok=True)

            self._report_progress(f"WARNING: ALL DATA ON {self.device} WILL BE ERASED!")
            self._report_progress(f"Unmounting disk {self.device} (force)...")
            self._unmount_path(self.device, is_device=True, force=True)
            time.sleep(2)

            self._report_progress(f"Partitioning {self.device} with GPT scheme...")
            self._run_command([
                "diskutil", "partitionDisk", self.device, "GPT",
                "MS-DOS FAT32", "EFI", "551MiB",
                "JHFS+", "macOS_USB", "0b"
            ], timeout=180)
            time.sleep(3)

            esp_partition_dev = self._get_partition_device_id(self.device, "EFI")
            macos_partition_dev = self._get_partition_device_id(self.device, "macOS_USB")

            if not (esp_partition_dev and os.path.exists(esp_partition_dev)):
                esp_partition_dev = f"{self.device}s1"
            if not (macos_partition_dev and os.path.exists(macos_partition_dev)):
                macos_partition_dev = f"{self.device}s2"

            if not (os.path.exists(esp_partition_dev) and os.path.exists(macos_partition_dev)):
                 raise RuntimeError(f"Could not identify partitions on {self.device}. ESP: {esp_partition_dev}, macOS: {macos_partition_dev}")

            self._report_progress(f"Identified ESP: {esp_partition_dev}, macOS Partition: {macos_partition_dev}")

            # --- Write EFI content ---
            self._report_progress(f"Converting OpenCore QCOW2 ({self.opencore_qcow2_path}) to RAW ({self.opencore_raw_path})...")
            self._run_command(["qemu-img", "convert", "-O", "raw", self.opencore_qcow2_path, self.opencore_raw_path])

            self._report_progress(f"Attaching RAW OpenCore image ({self.opencore_raw_path})...")
            attach_cmd_efi = ["hdiutil", "attach", "-nomount", "-imagekey", "diskimage-class=CRawDiskImage", self.opencore_raw_path]
            efi_attach_output = self._run_command(attach_cmd_efi, capture_output=True).stdout.strip()
            raw_efi_disk_id = efi_attach_output.splitlines()[-1].strip().split()[0]
            if not raw_efi_disk_id.startswith("/dev/disk"):
                raise RuntimeError(f"Failed to attach raw EFI image: {efi_attach_output}")
            self.attached_raw_images_devices.append(raw_efi_disk_id)
            self._report_progress(f"Attached raw OpenCore image as {raw_efi_disk_id}")
            time.sleep(2)

            source_efi_partition_dev = self._get_partition_device_id(raw_efi_disk_id, "EFI") or f"{raw_efi_disk_id}s1"

            self._report_progress(f"Mounting source EFI partition ({source_efi_partition_dev}) to {self.temp_opencore_mount}...")
            self._run_command(["diskutil", "mount", "readOnly", "-mountPoint", self.temp_opencore_mount, source_efi_partition_dev], timeout=30)

            self._report_progress(f"Mounting target USB ESP ({esp_partition_dev}) to {self.temp_usb_esp_mount}...")
            self._run_command(["diskutil", "mount", "-mountPoint", self.temp_usb_esp_mount, esp_partition_dev], timeout=30)

            source_efi_content_path = os.path.join(self.temp_opencore_mount, "EFI")
            if not os.path.isdir(source_efi_content_path): source_efi_content_path = self.temp_opencore_mount

            target_efi_dir_on_usb = os.path.join(self.temp_usb_esp_mount, "EFI")
            self._report_progress(f"Copying EFI files from {source_efi_content_path} to {target_efi_dir_on_usb}...")
            self._run_command(["sudo", "rsync", "-avh", "--delete", f"{source_efi_content_path}/", f"{target_efi_dir_on_usb}/"])

            self._unmount_path(self.temp_opencore_mount, force=True)
            self._unmount_path(self.temp_usb_esp_mount, force=True)
            self._detach_raw_image_device(raw_efi_disk_id); raw_efi_disk_id = None

            # --- Write macOS main image (File-level copy) ---
            self._report_progress(f"Converting macOS QCOW2 ({self.macos_qcow2_path}) to RAW ({self.macos_raw_path})...")
            self._report_progress("This may take a very long time...")
            self._run_command(["qemu-img", "convert", "-O", "raw", self.macos_qcow2_path, self.macos_raw_path])

            self._report_progress(f"Attaching RAW macOS image ({self.macos_raw_path})...")
            attach_cmd_macos = ["hdiutil", "attach", "-nomount", "-imagekey", "diskimage-class=CRawDiskImage", self.macos_raw_path]
            macos_attach_output = self._run_command(attach_cmd_macos, capture_output=True).stdout.strip()
            raw_macos_disk_id = macos_attach_output.splitlines()[-1].strip().split()[0]
            if not raw_macos_disk_id.startswith("/dev/disk"):
                raise RuntimeError(f"Failed to attach raw macOS image: {macos_attach_output}")
            self.attached_raw_images_devices.append(raw_macos_disk_id)
            self._report_progress(f"Attached raw macOS image as {raw_macos_disk_id}")
            time.sleep(2)

            source_macos_part_dev = self._get_partition_device_id(raw_macos_disk_id, "Apple_APFS_Container") or \
                                    self._get_partition_device_id(raw_macos_disk_id, "Apple_APFS") or \
                                    self._get_partition_device_id(raw_macos_disk_id, "Apple_HFS") or \
                                    f"{raw_macos_disk_id}s2"
            if not (source_macos_part_dev and os.path.exists(source_macos_part_dev)):
                 raise RuntimeError(f"Could not find source macOS partition on {raw_macos_disk_id}")

            self._report_progress(f"Mounting source macOS partition ({source_macos_part_dev}) to {self.temp_macos_source_mount}...")
            self._run_command(["diskutil", "mount", "readOnly", "-mountPoint", self.temp_macos_source_mount, source_macos_part_dev], timeout=60)

            self._report_progress(f"Mounting target USB macOS partition ({macos_partition_dev}) to {self.temp_usb_macos_target_mount}...")
            self._run_command(["diskutil", "mount", "-mountPoint", self.temp_usb_macos_target_mount, macos_partition_dev], timeout=30)

            self._report_progress(f"Copying macOS system files from {self.temp_macos_source_mount} to {self.temp_usb_macos_target_mount} (sudo rsync)...")
            self._report_progress("This will also take a very long time.")
            self._run_command([
                "sudo", "rsync", "-avh", "--delete",
                "--exclude=.Spotlight-V100", "--exclude=.fseventsd", "--exclude=/.Trashes", "--exclude=/System/Volumes/VM", "--exclude=/private/var/vm",
                f"{self.temp_macos_source_mount}/", f"{self.temp_usb_macos_target_mount}/"
            ])

            self._report_progress("USB writing process completed successfully.")
            return True

        except Exception as e:
            self._report_progress(f"An error occurred during USB writing on macOS: {e}")
            import traceback
            self._report_progress(traceback.format_exc())
            return False
        finally:
            self._cleanup_all_mounts_and_mappings()
            self._cleanup_temp_files()

if __name__ == '__main__':
    if platform.system() != "Darwin": print("This script is intended for macOS."); exit(1)
    print("USB Writer macOS Standalone Test - File Copy Method")

    mock_opencore_path = "mock_opencore_macos.qcow2"
    mock_macos_path = "mock_macos_macos.qcow2"
    if not os.path.exists(mock_opencore_path): subprocess.run(["qemu-img", "create", "-f", "qcow2", mock_opencore_path, "384M"])
    if not os.path.exists(mock_macos_path): subprocess.run(["qemu-img", "create", "-f", "qcow2", mock_macos_path, "1G"])

    print("\nAvailable disks (use 'diskutil list external physical' in Terminal to identify your USB):")
    subprocess.run(["diskutil", "list", "external", "physical"], check=False)
    test_device = input("\nEnter target disk identifier (e.g., /dev/diskX - NOT /dev/diskXsY). THIS DISK WILL BE WIPED: ")

    if not test_device or not test_device.startswith("/dev/disk"):
        print("Invalid disk identifier. Exiting.")
        if os.path.exists(mock_opencore_path): os.remove(mock_opencore_path)
        if os.path.exists(mock_macos_path): os.remove(mock_macos_path)
        exit(1)

    confirm = input(f"Are you sure you want to wipe {test_device} and write mock images? (yes/NO): ")
    success = False
    if confirm.lower() == 'yes':
        print("Ensure you have sudo privileges for rsync if needed, or app is run as root.")
        writer = USBWriterMacOS(test_device, mock_opencore_path, mock_macos_path, print)
        success = writer.format_and_write()
    else:
        print("Test cancelled.")

    print(f"Test finished. Success: {success}")
    if os.path.exists(mock_opencore_path): os.remove(mock_opencore_path)
    if os.path.exists(mock_macos_path): os.remove(mock_macos_path)
    print("Mock files cleaned up.")
