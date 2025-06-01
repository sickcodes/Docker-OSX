# usb_writer_linux.py
import subprocess
import os
import time
import shutil # For checking command existence

class USBWriterLinux:
    def __init__(self, device: str, opencore_qcow2_path: str, macos_qcow2_path: str, progress_callback=None):
        self.device = device
        self.opencore_qcow2_path = opencore_qcow2_path
        self.macos_qcow2_path = macos_qcow2_path
        self.progress_callback = progress_callback

        # Define unique temporary file and mount point names
        pid = os.getpid() # Make temp names more unique if multiple instances run (though unlikely for this app)
        self.opencore_raw_path = f"opencore_temp_{pid}.raw"
        self.macos_raw_path = f"macos_main_temp_{pid}.raw"
        self.mount_point_opencore_efi = f"/mnt/opencore_efi_temp_skyscope_{pid}"
        self.mount_point_usb_esp = f"/mnt/usb_esp_temp_skyscope_{pid}"
        self.mount_point_macos_source = f"/mnt/macos_source_temp_skyscope_{pid}"
        self.mount_point_usb_macos_target = f"/mnt/usb_macos_target_temp_skyscope_{pid}"

        self.temp_files_to_clean = [self.opencore_raw_path, self.macos_raw_path]
        self.temp_mount_points_to_clean = [
            self.mount_point_opencore_efi, self.mount_point_usb_esp,
            self.mount_point_macos_source, self.mount_point_usb_macos_target
        ]

    def _report_progress(self, message: str):
        print(message) # For standalone testing
        if self.progress_callback:
            self.progress_callback(message)

    def _run_command(self, command: list[str], check=True, capture_output=False, shell=False, timeout=None):
        self.progress_callback(f"Executing: {' '.join(command)}")
        try:
            process = subprocess.run(
                command,
                check=check,
                capture_output=capture_output,
                text=True,
                shell=shell, # Use shell=True with caution
                timeout=timeout
            )
            # Log stdout/stderr only if capture_output is True and content exists
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
            self._report_progress(f"Error executing {' '.join(command)} (return code {e.returncode}): {e}")
            if e.stderr: self._report_progress(f"STDERR: {e.stderr.strip()}")
            if e.stdout: self._report_progress(f"STDOUT: {e.stdout.strip()}") # Sometimes errors go to stdout
            raise
        except FileNotFoundError:
            self._report_progress(f"Error: Command '{command[0]}' not found. Is it installed and in PATH?")
            raise

    def _cleanup_temp_files(self):
        self._report_progress("Cleaning up temporary image files...")
        for f_path in self.temp_files_to_clean:
            if os.path.exists(f_path):
                try:
                    self._run_command(["sudo", "rm", "-f", f_path], check=False) # Use sudo rm for root-owned files
                    self._report_progress(f"Removed {f_path}")
                except Exception as e: # Catch broad exceptions from _run_command
                    self._report_progress(f"Error removing {f_path} via sudo rm: {e}")

    def _unmount_path(self, mount_point):
        if os.path.ismount(mount_point):
            self._report_progress(f"Unmounting {mount_point}...")
            self._run_command(["sudo", "umount", "-lf", mount_point], check=False, timeout=30)

    def _remove_dir_if_exists(self, dir_path):
         if os.path.exists(dir_path):
            try:
                self._run_command(["sudo", "rmdir", dir_path], check=False)
            except Exception as e: # Catch broad exceptions from _run_command
                 self._report_progress(f"Could not rmdir {dir_path}: {e}. May need manual cleanup.")


    def _cleanup_all_mounts_and_mappings(self):
        self._report_progress("Cleaning up all temporary mounts and kpartx mappings...")
        for mp in self.temp_mount_points_to_clean:
            self._unmount_path(mp) # Unmount first

        # Detach kpartx for raw images
        if os.path.exists(self.opencore_raw_path): # Check if raw file was even created
            self._run_command(["sudo", "kpartx", "-d", self.opencore_raw_path], check=False)
        if os.path.exists(self.macos_raw_path):
             self._run_command(["sudo", "kpartx", "-d", self.macos_raw_path], check=False)

        # Remove mount point directories after unmounting and detaching
        for mp in self.temp_mount_points_to_clean:
            self._remove_dir_if_exists(mp)


    def check_dependencies(self):
        self._report_progress("Checking dependencies (qemu-img, parted, kpartx, rsync, mkfs.vfat, mkfs.hfsplus, apfs-fuse)...")
        dependencies = ["qemu-img", "parted", "kpartx", "rsync", "mkfs.vfat", "mkfs.hfsplus", "apfs-fuse"]
        missing_deps = []
        for dep in dependencies:
            if not shutil.which(dep):
                missing_deps.append(dep)

        if missing_deps:
            msg = f"Missing dependencies: {', '.join(missing_deps)}. Please install them. `apfs-fuse` may require manual installation from source or a user repository (e.g., AUR for Arch Linux)."
            self._report_progress(msg)
            raise RuntimeError(msg)

        self._report_progress("All critical dependencies found.")
        return True

    def _get_mapped_partition_device(self, kpartx_output: str, partition_index_in_image: int = 1) -> str:
        lines = kpartx_output.splitlines()
        # Try to find loopXpY where Y is partition_index_in_image
        for line in lines:
            parts = line.split()
            if len(parts) > 2 and parts[0] == "add" and parts[1] == "map" and f"p{partition_index_in_image}" in parts[2]:
                return f"/dev/mapper/{parts[2]}"
        # Fallback for images that might be a single partition mapped directly (e.g. loopX)
        # This is less common for full disk images like OpenCore.qcow2 or mac_hdd_ng.img
        if partition_index_in_image == 1 and len(lines) == 1: # Only one mapping line
             parts = lines[0].split()
             if len(parts) > 2 and parts[0] == "add" and parts[1] == "map":
                 # Check if it does NOT look like a partition (no 'p' number)
                 if 'p' not in parts[2]:
                     return f"/dev/mapper/{parts[2]}" # e.g. /dev/mapper/loop0
        self._report_progress(f"Could not find partition index {partition_index_in_image} in kpartx output:\n{kpartx_output}")
        return None

    def format_and_write(self) -> bool:
        # Ensure cleanup runs even if errors occur early
        try:
            self.check_dependencies()
            self._cleanup_all_mounts_and_mappings() # Clean before start, just in case

            for mp in self.temp_mount_points_to_clean: # Create mount point directories
                self._run_command(["sudo", "mkdir", "-p", mp])

            self._report_progress(f"WARNING: ALL DATA ON {self.device} WILL BE ERASED!")
            self._report_progress(f"Unmounting all partitions on {self.device} (best effort)...")
            for i in range(1, 10):
                self._run_command(["sudo", "umount", f"{self.device}{i}"], check=False, timeout=5)
                self._run_command(["sudo", "umount", f"{self.device}p{i}"], check=False, timeout=5)

            self._report_progress(f"Creating new GPT partition table on {self.device}...")
            self._run_command(["sudo", "parted", "--script", self.device, "mklabel", "gpt"])
            self._report_progress("Creating EFI partition (ESP)...")
            self._run_command(["sudo", "parted", "--script", self.device, "mkpart", "EFI", "fat32", "1MiB", "551MiB"])
            self._run_command(["sudo", "parted", "--script", self.device, "set", "1", "esp", "on"])
            self._report_progress("Creating macOS partition...")
            self._run_command(["sudo", "parted", "--script", self.device, "mkpart", "macOS", "hfs+", "551MiB", "100%"])

            self._run_command(["sudo", "partprobe", self.device], timeout=10)
            time.sleep(3)

            esp_partition_dev = f"{self.device}1" if os.path.exists(f"{self.device}1") else f"{self.device}p1"
            macos_partition_dev = f"{self.device}2" if os.path.exists(f"{self.device}2") else f"{self.device}p2"

            if not (os.path.exists(esp_partition_dev) and os.path.exists(macos_partition_dev)):
                 raise RuntimeError(f"Could not reliably determine partition names for {self.device}. Expected {esp_partition_dev} and {macos_partition_dev} to exist after partprobe.")

            self._report_progress(f"Formatting ESP ({esp_partition_dev}) as FAT32...")
            self._run_command(["sudo", "mkfs.vfat", "-F", "32", esp_partition_dev])

            # --- Write EFI content ---
            self._report_progress(f"Converting OpenCore QCOW2 ({self.opencore_qcow2_path}) to RAW ({self.opencore_raw_path})...")
            self._run_command(["qemu-img", "convert", "-O", "raw", self.opencore_qcow2_path, self.opencore_raw_path])

            map_output_efi = self._run_command(["sudo", "kpartx", "-av", self.opencore_raw_path], capture_output=True).stdout
            mapped_efi_device = self._get_mapped_partition_device(map_output_efi, 1) # EFI is partition 1 in OpenCore.qcow2
            if not mapped_efi_device: raise RuntimeError(f"Could not map EFI partition from {self.opencore_raw_path}.")
            self._report_progress(f"Mapped OpenCore EFI partition device: {mapped_efi_device}")

            self._report_progress(f"Mounting {mapped_efi_device} to {self.mount_point_opencore_efi}...")
            self._run_command(["sudo", "mount", "-o", "ro", mapped_efi_device, self.mount_point_opencore_efi])
            self._report_progress(f"Mounting USB ESP ({esp_partition_dev}) to {self.mount_point_usb_esp}...")
            self._run_command(["sudo", "mount", esp_partition_dev, self.mount_point_usb_esp])

            self._report_progress(f"Copying EFI files from {self.mount_point_opencore_efi}/EFI to {self.mount_point_usb_esp}/EFI...")
            source_efi_content_path = os.path.join(self.mount_point_opencore_efi, "EFI")
            if not os.path.isdir(source_efi_content_path): # Check if EFI folder is in root of partition
                source_efi_content_path = self.mount_point_opencore_efi # Assume content is in root

            target_efi_dir_on_usb = os.path.join(self.mount_point_usb_esp, "EFI")
            self._run_command(["sudo", "mkdir", "-p", target_efi_dir_on_usb])
            self._run_command(["sudo", "rsync", "-avh", "--delete", f"{source_efi_content_path}/", f"{target_efi_dir_on_usb}/"]) # Copy content of EFI

            self._unmount_path(self.mount_point_opencore_efi)
            self._unmount_path(self.mount_point_usb_esp)
            self._run_command(["sudo", "kpartx", "-d", self.opencore_raw_path])

            # --- Write macOS main image (File-level copy) ---
            self._report_progress(f"Formatting macOS partition ({macos_partition_dev}) on USB as HFS+...")
            self._run_command(["sudo", "mkfs.hfsplus", "-v", "macOS_USB", macos_partition_dev])

            self._report_progress(f"Converting macOS QCOW2 ({self.macos_qcow2_path}) to RAW ({self.macos_raw_path})...")
            self._report_progress("This may take a very long time and consume significant disk space temporarily.")
            self._run_command(["qemu-img", "convert", "-O", "raw", self.macos_qcow2_path, self.macos_raw_path])

            self._report_progress(f"Mapping partitions from macOS RAW image ({self.macos_raw_path})...")
            map_output_macos = self._run_command(["sudo", "kpartx", "-av", self.macos_raw_path], capture_output=True).stdout
            # The mac_hdd_ng.img usually contains an APFS container.
            # kpartx might show multiple APFS volumes within the container, or the container partition itself.
            # We need to mount the APFS Data or System volume.
            # Typically, the main usable partition is the largest one, or the second one (after a small EFI if present in this image).
            mapped_macos_device = self._get_mapped_partition_device(map_output_macos, 2) # Try p2 (common for APFS container)
            if not mapped_macos_device:
                mapped_macos_device = self._get_mapped_partition_device(map_output_macos, 1) # Fallback to p1
            if not mapped_macos_device:
                raise RuntimeError(f"Could not identify and map main macOS data partition from {self.macos_raw_path}.")
            self._report_progress(f"Mapped macOS source partition device: {mapped_macos_device}")

            self._report_progress(f"Mounting source macOS partition ({mapped_macos_device}) to {self.mount_point_macos_source} using apfs-fuse...")
            self._run_command(["sudo", "apfs-fuse", "-o", "ro,allow_other", mapped_macos_device, self.mount_point_macos_source])

            self._report_progress(f"Mounting target USB macOS partition ({macos_partition_dev}) to {self.mount_point_usb_macos_target}...")
            self._run_command(["sudo", "mount", macos_partition_dev, self.mount_point_usb_macos_target])

            self._report_progress(f"Copying macOS system files from {self.mount_point_macos_source} to {self.mount_point_usb_macos_target} using rsync...")
            self._report_progress("This will take a very long time. Please be patient.")
            self._run_command(["sudo", "rsync", "-avh", "--delete", f"{self.mount_point_macos_source}/", f"{self.mount_point_usb_macos_target}/"]) # Note trailing slashes

            self._report_progress("USB writing process completed successfully.")
            return True

        except Exception as e:
            self._report_progress(f"An error occurred during USB writing: {e}")
            import traceback
            self._report_progress(traceback.format_exc()) # Log full traceback for debugging
            return False
        finally:
            self._cleanup_all_mounts_and_mappings()
            self._cleanup_temp_files()

if __name__ == '__main__':
    if os.geteuid() != 0:
        print("Please run this script as root (sudo) for testing.")
        exit(1)

    print("USB Writer Linux Standalone Test - REFACTORED for File Copy")

    # Create dummy qcow2 files for testing script structure
    # These won't result in a bootable USB but allow testing the commands.
    mock_opencore_path = "mock_opencore_usb_writer.qcow2"
    mock_macos_path = "mock_macos_usb_writer.qcow2"

    print(f"Creating mock image: {mock_opencore_path}")
    subprocess.run(["qemu-img", "create", "-f", "qcow2", mock_opencore_path, "384M"], check=True)
    # TODO: A more complex mock would involve creating a partition table and filesystem inside this qcow2.
    # For now, this is just to ensure the file exists for qemu-img convert.
    # Actual EFI content would be needed for kpartx to map something meaningful.

    print(f"Creating mock image: {mock_macos_path}")
    subprocess.run(["qemu-img", "create", "-f", "qcow2", mock_macos_path, "1G"], check=True) # Small for quick test
    # TODO: Similar to above, a real test needs a qcow2 with a mountable filesystem.

    print("\nAvailable block devices (be careful!):")
    subprocess.run(["lsblk", "-d", "-o", "NAME,SIZE,MODEL"], check=True)
    test_device = input("\nEnter target device (e.g., /dev/sdX). THIS DEVICE WILL BE WIPED: ")

    if not test_device or not (test_device.startswith("/dev/") or test_device.startswith("/dev/mapper/")): # Allow /dev/mapper for testing with loop devices
        print("Invalid device. Exiting.")
        # Clean up mock files
        if os.path.exists(mock_opencore_path): os.remove(mock_opencore_path)
        if os.path.exists(mock_macos_path): os.remove(mock_macos_path)
        exit(1)

    confirm = input(f"Are you absolutely sure you want to wipe {test_device} and write mock images? (yes/NO): ")
    success = False
    if confirm.lower() == 'yes':
        writer = USBWriterLinux(test_device, mock_opencore_path, mock_macos_path, print)
        success = writer.format_and_write()
    else:
        print("Test cancelled by user.")

    print(f"Test finished. Success: {success}")
    # Clean up mock files
    if os.path.exists(mock_opencore_path): os.remove(mock_opencore_path)
    if os.path.exists(mock_macos_path): os.remove(mock_macos_path)
    print("Mock files cleaned up.")
