# Skyscope macOS on PC USB Creator Tool

**Version:** 0.8.1 (Alpha)
**Developer:** Miss Casey Jay Topojani
**Business:** Skyscope Sentinel Intelligence

## Vision: Your Effortless Bridge to macOS on PC

Welcome to the Skyscope macOS on PC USB Creator Tool! Our vision is to provide an exceptionally user-friendly, GUI-driven application that fully automates the complex process of creating a bootable macOS USB drive for virtually any PC. This tool leverages the power of Docker-OSX and OpenCore, aiming to simplify the Hackintosh journey from start to finish.

This project is dedicated to creating a seamless experience, from selecting your desired macOS version to generating a USB drive that's ready to boot your PC into macOS, complete with efforts to auto-configure for your hardware.

## Current Features & Capabilities

*   **Intuitive Graphical User Interface (PyQt6):** Guides you through each step of the process.
*   **macOS Version Selection:** Easily choose from popular macOS versions (Sonoma, Ventura, Monterey, Big Sur, Catalina).
*   **Automated Docker-OSX Orchestration:**
    *   **Intelligent Image Pulling:** Automatically pulls the required `sickcodes/docker-osx` image from Docker Hub, with progress displayed.
    *   **VM Creation & macOS Installation:** Launches the Docker-OSX container where you can interactively install macOS within a QEMU virtual machine.
    *   **Log Streaming:** View Docker and QEMU logs directly in the application for transparency.
*   **VM Image Extraction:** Once macOS is installed in the VM, the tool helps you extract the essential disk images (`mac_hdd_ng.img` and `OpenCore.qcow2`).
*   **Container Management:** Stop and remove the Docker-OSX container after use.
*   **Cross-Platform USB Drive Preparation:**
    *   **USB Detection:** Identifies potential USB drives on Linux, macOS, and Windows (using WMI for more accurate detection on Windows).
    *   **Automated EFI & macOS System Write (Linux & macOS):**
        *   Partitions the USB drive with a GUID Partition Table (GPT).
        *   Creates and formats an EFI System Partition (FAT32) and a main macOS partition (HFS+).
        *   Uses a robust file-level copy (`rsync`) for both EFI content and the main macOS system, ensuring compatibility with various USB sizes and only copying necessary data.
    *   **Windows USB Writing (Partial Automation):**
        *   Automates EFI partition creation and EFI file copying.
        *   **Important:** Writing the main macOS system image currently requires a guided manual step using an external "dd for Windows" utility due to Windows' limitations with direct, scriptable raw partition writing of HFS+/APFS filesystems. The tool prepares the raw image and provides instructions.
*   **Experimental `config.plist` Auto-Enhancement:**
    *   **Linux Host Detection:** If the tool is run on a Linux system, it can gather information about your host computer's hardware (iGPU, audio, Ethernet, CPU).
    *   **Targeted Modifications:** Optionally attempts to modify the `config.plist` (from the generated `OpenCore.qcow2`) to:
        *   Add common `DeviceProperties` for Intel iGPUs.
        *   Set appropriate audio `layout-id`s.
        *   Ensure necessary Ethernet kexts are enabled.
        *   Apply boot-args for NVIDIA GTX 970 based on target macOS version (e.g., `nv_disable=1` or `nvda_drv=1`).
    *   A backup of the original `config.plist` is created before modifications.
*   **Privilege Checking:** Warns if administrative/root privileges are needed for USB writing and are not detected.
*   **UI Feedback:** Status bar messages and an indeterminate progress bar keep you informed during long operations.

## Current Status & Known Limitations

*   **Windows Main OS USB Write:** This is the primary limitation, requiring a manual `dd` step. Future work aims to automate this if a reliable, redistributable CLI tool for raw partition writing is identified or developed.
*   **`config.plist` Enhancement is Experimental:**
    *   Hardware detection for this feature is **currently only implemented for Linux hosts.** On macOS/Windows, the plist modification step will run but won't apply hardware-specific changes.
    *   The applied patches are based on common configurations and may not be optimal or work for all hardware. Always test thoroughly.
*   **NVIDIA dGPU Support on Newer macOS:** Modern macOS (Mojave+) does not support NVIDIA Maxwell/Pascal/Turing/Ampere GPUs. The tool attempts to configure systems with these cards for basic display or to use an iGPU if available. Full acceleration is not possible on these macOS versions with these cards.
*   **Universal Compatibility:** While the goal is broad PC compatibility, Hackintoshing can be hardware-specific. Success is not guaranteed on all possible PC configurations.
*   **Dependency on External Projects:** Relies on Docker-OSX, OpenCore, and various community-sourced kexts and configurations.

## Prerequisites

1.  **Docker:** Must be installed and running. Your user account needs permission to manage Docker.
    *   [Install Docker Engine](https://docs.docker.com/engine/install/)
2.  **Python:** Version 3.8 or newer.
3.  **Python Libraries:** Install with `pip install PyQt6 psutil`.
4.  **Platform-Specific CLI Tools for USB Writing:**

    *   **Linux (including Debian 13 "Trixie"):**
        *   `qemu-img` (from `qemu-utils`)
        *   `parted`
        *   `kpartx` (from `kpartx` or `multipath-tools`)
        *   `rsync`
        *   `mkfs.vfat` (from `dosfstools`)
        *   `mkfs.hfsplus` (from `hfsprogs`)
        *   `apfs-fuse`: Often requires manual compilation (e.g., from `sgan81/apfs-fuse` on GitHub). Typical build dependencies: `git g++ cmake libfuse3-dev libicu-dev zlib1g-dev libbz2-dev libssl-dev`. Ensure it's in your PATH.
        *   `lsblk`, `partprobe` (from `util-linux`)
        *   Install most via: `sudo apt update && sudo apt install qemu-utils parted kpartx rsync dosfstools hfsprogs util-linux`
    *   **macOS:**
        *   `qemu-img` (e.g., via Homebrew: `brew install qemu`)
        *   `diskutil`, `hdiutil`, `rsync` (standard macOS tools).
    *   **Windows:**
        *   `qemu-img` (install and add to PATH).
        *   `diskpart`, `robocopy` (standard Windows tools).
        *   `7z.exe` (7-Zip command-line tool, install and add to PATH) - for EFI file extraction.
        *   A "dd for Windows" utility (e.g., from SUSE, chrysocome.net, or similar). Ensure it's in your PATH and you know how to use it for writing to a physical disk's partition or offset.

## How to Run

1.  Ensure all prerequisites for your operating system are met.
2.  Clone this repository or download the source files.
3.  Install Python libraries: `pip install PyQt6 psutil`.
4.  Execute `python main_app.py`.
5.  **Important for USB Writing:**
    *   **Linux:** Run with `sudo python main_app.py`.
    *   **macOS:** The script will use `sudo` internally for `rsync` to USB EFI if needed. You might be prompted for your password. Ensure the main application has Full Disk Access if issues arise with `hdiutil` or `diskutil` not having permissions (System Settings > Privacy & Security).
    *   **Windows:** Run the application as Administrator.

## Step-by-Step Usage Guide

1.  **Step 1: Create and Install macOS VM**
    *   Launch the "Skyscope macOS on PC USB Creator Tool".
    *   Select your desired macOS version from the dropdown menu.
    *   Click "Create VM and Start macOS Installation".
    *   The tool will first pull the necessary Docker image (progress shown).
    *   Then, a QEMU window will appear. This is your virtual machine. Follow the standard macOS installation procedure within this window (use Disk Utility to erase and format the virtual hard drive, then install macOS). This part is interactive.
    *   Once macOS is fully installed in QEMU, shut down the macOS VM from within its own interface (Apple Menu > Shut Down). Closing the QEMU window will also terminate the process.
2.  **Step 2: Extract VM Images**
    *   After the Docker process from Step 1 finishes (QEMU window closes), the "Extract Images from Container" button will become active.
    *   Click it. You'll be prompted to select a directory on your computer. The `mac_hdd_ng.img` (macOS system) and `OpenCore.qcow2` (EFI bootloader) files will be copied here. This may take some time.
3.  **Step 3: Container Management (Optional)**
    *   Once images are extracted, the Docker container used for installation is no longer strictly needed.
    *   You can "Stop Container" (if it's listed as running by Docker for any reason) and then "Remove Container" to free up disk space.
4.  **Step 4: Select Target USB Drive and Write**
    *   Physically connect your USB flash drive.
    *   Click "Refresh List".
        *   **Linux/macOS:** Select your USB drive from the dropdown. Verify size and identifier carefully.
        *   **Windows:** USB drives detected via WMI will appear in the dropdown. Select the correct one. Ensure it's the `Disk X` number you intend.
    *   **(Optional, Experimental):** Check the "Try to auto-enhance config.plist..." box if you are on a Linux host and wish to attempt automatic `config.plist` modification for your hardware. A backup of the original `config.plist` will be made.
    *   **CRITICAL WARNING:** Double-check your selection. The next action will erase the selected USB drive.
    *   Click "Write Images to USB Drive". Confirm the data erasure warning.
    *   The process will now:
        *   (If enhancement enabled) Attempt to modify the `config.plist` within the source OpenCore image.
        *   Partition and format your USB drive.
        *   Copy EFI files to the USB's EFI partition.
        *   Copy macOS system files to the USB's main partition. (On Windows, this step requires manual `dd` operation as guided by the application).
    *   This is a lengthy process. Monitor the progress in the output area.
5.  **Boot!**
    *   Once complete, safely eject the USB drive. You can now try booting your PC from it. Remember to configure your PC's BIOS/UEFI for booting from USB and for macOS compatibility (e.g., disable Secure Boot, enable AHCI, XHCI Handoff, etc., as per standard Hackintosh guides like Dortania).

## Future Vision & Enhancements

*   **Fully Automated Windows USB Writing:** Replace the manual `dd` step with a reliable, integrated solution.
*   **Advanced `config.plist` Customization:**
    *   Expand hardware detection to macOS and Windows hosts.
    *   Provide more granular UI controls for plist enhancements (e.g., preview changes, select specific patches).
    *   Allow users to load/save `config.plist` modification profiles.
*   **Enhanced UI/UX for Progress:** Implement determinate progress bars with percentage completion and more dynamic status updates.
*   **Debian 13 "Trixie" (and other distros) Validation:** Continuous compatibility checks and dependency streamlining.
*   **"Universal" Config Strategy (Research):** Investigate advanced techniques for more adaptive OpenCore configurations, though true universality is a significant challenge.

## Contributing

Your contributions, feedback, and bug reports are highly welcome! Please fork the repository and submit pull requests, or open issues for discussion.

## License

(To be decided - e.g., MIT or GPLv3)
