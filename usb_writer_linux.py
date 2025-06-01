# usb_writer_linux.py
import subprocess
import os
import time

# Placeholder for progress reporting signal if this were a QObject
# from PyQt6.QtCore import pyqtSignal

class USBWriterLinux:
    # progress_signal = pyqtSignal(str) # Example for QObject integration

    def __init__(self, device: str, opencore_qcow2_path: str, macos_qcow2_path: str, progress_callback=None):
        """
        Args:
            device: The path to the USB device (e.g., /dev/sdx).
            opencore_qcow2_path: Path to the OpenCore.qcow2 image.
            macos_qcow2_path: Path to the mac_hdd_ng.img (qcow2).
            progress_callback: A function to call with progress strings.
        """
        self.device = device
        self.opencore_qcow2_path = opencore_qcow2_path
        self.macos_qcow2_path = macos_qcow2_path
        self.progress_callback = progress_callback

        self.opencore_raw_path = "opencore.raw" # Temporary raw image
        self.macos_raw_path = "macos_main.raw" # Temporary raw image
        self.mount_point_opencore_efi = "/mnt/opencore_efi_temp"
        self.mount_point_usb_esp = "/mnt/usb_esp_temp"


    def _report_progress(self, message: str):
        print(message) # For standalone testing
        if self.progress_callback:
            self.progress_callback(message)

    def _run_command(self, command: list[str], check=True, capture_output=False, shell=False):
        self._report_progress(f"Executing: {' '.join(command)}")
        try:
            process = subprocess.run(
                command,
                check=check,
                capture_output=capture_output,
                text=True,
                shell=shell # Use shell=True with caution
            )
            if capture_output:
                if process.stdout: self._report_progress(f"STDOUT: {process.stdout.strip()}")
                if process.stderr: self._report_progress(f"STDERR: {process.stderr.strip()}")
            return process
        except subprocess.CalledProcessError as e:
            self._report_progress(f"Error executing {' '.join(command)}: {e}")
            if e.stderr: self._report_progress(f"STDERR: {e.stderr.strip()}")
            if e.stdout: self._report_progress(f"STDOUT: {e.stdout.strip()}")
            raise
        except FileNotFoundError:
            self._report_progress(f"Error: Command {command[0]} not found. Is it installed and in PATH?")
            raise

    def _cleanup_temp_files(self):
        self._report_progress("Cleaning up temporary files...")
        for f_path in [self.opencore_raw_path, self.macos_raw_path]:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                    self._report_progress(f"Removed {f_path}")
                except OSError as e:
                    self._report_progress(f"Error removing {f_path}: {e}")

    def _unmount_and_remove_dir(self, mount_point):
        if os.path.ismount(mount_point):
            self._run_command(["sudo", "umount", mount_point], check=False)
        if os.path.exists(mount_point):
            try:
                os.rmdir(mount_point)
            except OSError as e:
                 self._report_progress(f"Could not rmdir {mount_point}: {e}. May need manual cleanup.")


    def _cleanup_mappings_and_mounts(self):
        self._report_progress("Cleaning up mappings and mounts...")
        self._unmount_and_remove_dir(self.mount_point_opencore_efi)
        self._unmount_and_remove_dir(self.mount_point_usb_esp)

        # Unmap kpartx devices - this is tricky as we don't know the loop device name easily without parsing
        # For OpenCore raw image
        if os.path.exists(self.opencore_raw_path):
            self._run_command(["sudo", "kpartx", "-d", self.opencore_raw_path], check=False)
        # For the USB device itself, if kpartx was used on it (it shouldn't be for this workflow)
        # self._run_command(["sudo", "kpartx", "-d", self.device], check=False)


    def check_dependencies(self):
        self._report_progress("Checking dependencies (qemu-img, parted, kpartx, rsync, mkfs.vfat)...")
        dependencies = ["qemu-img", "parted", "kpartx", "rsync", "mkfs.vfat"]
        for dep in dependencies:
            try:
                self._run_command([dep, "--version" if dep != "kpartx" and dep != "mkfs.vfat" else "-V"], capture_output=True) # kpartx has no version, mkfs.vfat uses -V
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                self._report_progress(f"Dependency {dep} not found or not working: {e}")
                raise RuntimeError(f"Dependency {dep} not found. Please install it.")
        self._report_progress("All dependencies found.")
        return True

    def format_and_write(self) -> bool:
        try:
            self.check_dependencies()

            self._report_progress(f"WARNING: ALL DATA ON {self.device} WILL BE ERASED!")
            # Unmount any existing partitions on the target USB device
            self._report_progress(f"Unmounting all partitions on {self.device}...")
            for i in range(1, 5): # Try to unmount a few potential partitions
                self._run_command(["sudo", "umount", f"{self.device}{i}"], check=False)
                self._run_command(["sudo", "umount", f"{self.device}p{i}"], check=False) # for nvme like

            # Create new GPT partition table
            self._report_progress(f"Creating new GPT partition table on {self.device}...")
            self._run_command(["sudo", "parted", "-s", self.device, "mklabel", "gpt"])

            # Create EFI partition (e.g., 512MB)
            self._report_progress("Creating EFI partition (ESP)...")
            self._run_command(["sudo", "parted", "-s", self.device, "mkpart", "EFI", "fat32", "1MiB", "513MiB"])
            self._run_command(["sudo", "parted", "-s", self.device, "set", "1", "esp", "on"])

            # Create macOS partition (remaining space)
            self._report_progress("Creating macOS partition...")
            self._run_command(["sudo", "parted", "-s", self.device, "mkpart", "macOS", "hfs+", "513MiB", "100%"])

            # Inform kernel of partition changes
            self._run_command(["sudo", "partprobe", self.device])
            time.sleep(2) # Give kernel time to recognize new partitions

            # Determine partition names (e.g., /dev/sdx1, /dev/sdx2)
            # This can be unreliable. A better way is `lsblk -jo NAME,PATH /dev/sdx`
            # For simplicity, assuming /dev/sdx1 for ESP, /dev/sdx2 for macOS partition
            esp_partition = f"{self.device}1"
            if not os.path.exists(esp_partition): esp_partition = f"{self.device}p1" # for nvme like /dev/nvme0n1p1

            macos_partition = f"{self.device}2"
            if not os.path.exists(macos_partition): macos_partition = f"{self.device}p2"

            if not (os.path.exists(esp_partition) and os.path.exists(macos_partition)):
                 self._report_progress(f"Could not reliably determine partition names for {self.device}. Expected {esp_partition} and {macos_partition}")
                 # Attempt to find them via lsblk if possible (more robust)
                 try:
                     lsblk_out = self._run_command(["lsblk", "-no", "NAME", "--paths", self.device], capture_output=True, check=True).stdout.strip().splitlines()
                     if len(lsblk_out) > 2 : # Device itself + at least 2 partitions
                         esp_partition = lsblk_out[1]
                         macos_partition = lsblk_out[2]
                         self._report_progress(f"Determined partitions using lsblk: ESP={esp_partition}, macOS={macos_partition}")
                     else:
                         raise RuntimeError("lsblk did not return enough partitions.")
                 except Exception as e_lsblk:
                     self._report_progress(f"Failed to determine partitions using lsblk: {e_lsblk}")
                     raise RuntimeError("Could not determine partition device names after partitioning.")


            # Format ESP as FAT32
            self._report_progress(f"Formatting ESP ({esp_partition}) as FAT32...")
            self._run_command(["sudo", "mkfs.vfat", "-F", "32", esp_partition])

            # --- Write EFI content ---
            self._report_progress(f"Converting OpenCore QCOW2 image ({self.opencore_qcow2_path}) to RAW ({self.opencore_raw_path})...")
            self._run_command(["qemu-img", "convert", "-O", "raw", self.opencore_qcow2_path, self.opencore_raw_path])

            self._report_progress(f"Mapping partitions from {self.opencore_raw_path}...")
            map_output = self._run_command(["sudo", "kpartx", "-av", self.opencore_raw_path], capture_output=True).stdout
            self._report_progress(f"kpartx output: {map_output}")
            # Example output: add map loop0p1 (253:0): 0 1048576 linear /dev/loop0 2048
            # We need to parse "loop0p1" or similar from this.
            mapped_efi_partition_name = None
            for line in map_output.splitlines():
                if "loop" in line and "p1" in line: # Assuming first partition is EFI
                    parts = line.split()
                    if len(parts) > 2:
                        mapped_efi_partition_name = parts[2] # e.g., loop0p1
                        break

            if not mapped_efi_partition_name:
                raise RuntimeError(f"Could not determine mapped EFI partition name from kpartx output for {self.opencore_raw_path}.")

            mapped_efi_device = f"/dev/mapper/{mapped_efi_partition_name}"
            self._report_progress(f"Mapped OpenCore EFI partition: {mapped_efi_device}")

            os.makedirs(self.mount_point_opencore_efi, exist_ok=True)
            os.makedirs(self.mount_point_usb_esp, exist_ok=True)

            self._report_progress(f"Mounting {mapped_efi_device} to {self.mount_point_opencore_efi}...")
            self._run_command(["sudo", "mount", "-o", "ro", mapped_efi_device, self.mount_point_opencore_efi])

            self._report_progress(f"Mounting USB ESP ({esp_partition}) to {self.mount_point_usb_esp}...")
            self._run_command(["sudo", "mount", esp_partition, self.mount_point_usb_esp])

            self._report_progress(f"Copying EFI files from {self.mount_point_opencore_efi} to {self.mount_point_usb_esp}...")
            # Copy contents of EFI folder
            source_efi_dir = os.path.join(self.mount_point_opencore_efi, "EFI")
            if not os.path.exists(source_efi_dir): # Sometimes it's directly in the root of the partition image
                source_efi_dir = self.mount_point_opencore_efi

            self._run_command(["sudo", "rsync", "-avh", "--delete", f"{source_efi_dir}/", f"{self.mount_point_usb_esp}/"])


            self._report_progress("Unmounting OpenCore EFI and USB ESP...")
            self._run_command(["sudo", "umount", self.mount_point_opencore_efi])
            self._run_command(["sudo", "umount", self.mount_point_usb_esp])
            self._run_command(["sudo", "kpartx", "-d", self.opencore_raw_path]) # Unmap loop device

            # --- Write macOS main image ---
            self._report_progress(f"Converting macOS QCOW2 image ({self.macos_qcow2_path}) to RAW ({self.macos_raw_path})...")
            self._report_progress("This may take a very long time and consume significant disk space temporarily.")
            # Add dd progress status if possible, or estimate time based on size
            # For qemu-img, there's no easy progress for convert.
            self._run_command(["qemu-img", "convert", "-O", "raw", self.macos_qcow2_path, self.macos_raw_path])

            self._report_progress(f"Writing RAW macOS image ({self.macos_raw_path}) to {macos_partition}...")
            self._report_progress("This will also take a very long time. Please be patient.")
            # Using dd with progress status
            dd_command = ["sudo", "dd", f"if={self.macos_raw_path}", f"of={macos_partition}", "bs=4M", "status=progress", "conv=fsync"]
            self._run_command(dd_command)

            self._report_progress("USB writing process completed successfully.")
            return True

        except Exception as e:
            self._report_progress(f"An error occurred during USB writing: {e}")
            return False
        finally:
            self._cleanup_mappings_and_mounts()
            self._cleanup_temp_files()

if __name__ == '__main__':
    # This is for standalone testing of this script.
    # YOU MUST RUN THIS SCRIPT WITH SUDO for it to work.
    # BE EXTREMELY CAREFUL with the device path.
    if os.geteuid() != 0:
        print("Please run this script as root (sudo) for testing.")
        exit(1)

    print("USB Writer Linux Standalone Test")
    # Replace with actual paths to your QCOW2 files for testing
    test_opencore_qcow2 = "path_to_your/OpenCore.qcow2"
    test_macos_qcow2 = "path_to_your/mac_hdd_ng.img"

    # IMPORTANT: List available block devices to help user choose.
    print("\nAvailable block devices (be careful!):")
    subprocess.run(["lsblk", "-d", "-o", "NAME,SIZE,MODEL"], check=True)

    test_device = input("\nEnter target device (e.g., /dev/sdX). THIS DEVICE WILL BE WIPED: ")
    if not test_device or not test_device.startswith("/dev/"):
        print("Invalid device. Exiting.")
        exit(1)

    if not (os.path.exists(test_opencore_qcow2) and os.path.exists(test_macos_qcow2)):
        print(f"Test files {test_opencore_qcow2} or {test_macos_qcow2} not found. Skipping write test.")
    else:
        confirm = input(f"Are you absolutely sure you want to wipe {test_device} and write images? (yes/NO): ")
        if confirm.lower() == 'yes':
            writer = USBWriterLinux(test_device, test_opencore_qcow2, test_macos_qcow2, print)
            writer.format_and_write()
        else:
            print("Test cancelled by user.")
