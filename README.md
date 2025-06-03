# Skyscope macOS on PC USB Creator Tool

**Version:** 0.8.0 (Alpha)
**Developer:** Miss Casey Jay Topojani
**Business:** Skyscope Sentinel Intelligence

## Overview

This tool provides a graphical user interface to automate the creation of a bootable macOS USB drive for PC (Hackintosh) using the Docker-OSX project. It guides the user through selecting a macOS version, running the Docker-OSX container for macOS installation, extracting the necessary image files, and (currently for Linux users) writing these images to a USB drive.

## Features

*   User-friendly GUI for selecting macOS versions (Sonoma, Ventura, Monterey, Big Sur, Catalina).
*   Automated Docker command generation and execution for Docker-OSX.
*   Streams Docker logs directly into the application.
*   Extraction of the generated `mac_hdd_ng.img` (macOS system) and `OpenCore.qcow2` (EFI bootloader).
*   Management of the created Docker container (stop/remove).
*   USB drive detection.
*   Automated USB partitioning and image writing for **Linux systems**.
    *   Creates GPT partition table.
    *   Creates an EFI System Partition (ESP) and a main HFS+ partition for macOS.
    *   Copies EFI files and writes the macOS system image.
*   Warning prompts before destructive operations like USB writing.

## Current Status & Known Issues/Limitations

*   **USB Writing Platform Support:** USB writing functionality is currently **only implemented and tested for Linux**. macOS and Windows users can use the tool to generate and extract images but will need to use other methods for USB creation.
*   **macOS Image Size for USB:** The current Linux USB writing process for the main macOS system uses `dd` to write the converted raw image. While the source `mac_hdd_ng.img` is sparse, the raw conversion makes it its full provisioned size (e.g., 200GB). This means:
    *   The target USB drive must be large enough to hold this full raw size.
    *   This is inefficient and needs to be changed to a file-level copy (e.g., using `rsync` after mounting the source image) to only copy actual data and better fit various USB sizes. (This is a high-priority item based on recent feedback).
*   **Intel iGPU Compatibility:** Relies on the generic iGPU support provided by WhateverGreen.kext within the OpenCore configuration from Docker-OSX. This works for many iGPUs but isn't guaranteed for all without specific `config.plist` tuning.
*   **Dependency on Docker-OSX:** This tool orchestrates Docker-OSX. Changes or issues in the upstream Docker-OSX project might affect this tool.
*   **Elevated Privileges:** For USB writing on Linux, the application currently requires being run with `sudo`. It does not yet have in-app checks or prompts for this.

## Prerequisites

1.  **Docker:** Docker must be installed and running on your system. The current user must have permissions to run Docker commands.
    *   [Install Docker Engine](https://docs.docker.com/engine/install/)
2.  **Python:** Python 3.8+
3.  **Python Libraries:**
    *   `PyQt6`
    *   `psutil`
    *   Installation: `pip install PyQt6 psutil`
4.  **(For Linux USB Writing ONLY)**: The following command-line utilities must be installed and accessible in your PATH:
    *   `qemu-img` (usually from `qemu-utils` package)
    *   `parted`
    *   `kpartx` (often part of `multipath-tools` or `kpartx` package)
    *   `rsync`
    *   `mkfs.vfat` (usually from `dosfstools` package)
    *   `mkfs.hfsplus` (usually from `hfsprogs` package)
    *   `apfs-fuse` (may require manual installation from source or a third-party repository/PPA, as it's not always in standard Debian/Ubuntu repos)
    *   `lsblk` (usually from `util-linux` package)
    *   `partprobe` (usually from `parted` or `util-linux` package)
    *   You can typically install most of these on Debian/Ubuntu (including Debian 13 Trixie) with:
        ```bash
        sudo apt update
        sudo apt install qemu-utils parted kpartx rsync dosfstools hfsprogs util-linux
        ```
    *   For `apfs-fuse` on Debian/Ubuntu, you may need to search for a PPA or compile it from its source (e.g., from GitHub). Ensure it's in your PATH.

## How to Run

1.  Clone this repository or download the source files (`main_app.py`, `utils.py`, `constants.py`, `usb_writer_linux.py`).
2.  Install the prerequisite Python libraries: `pip install PyQt6 psutil`.
3.  **(Linux for USB Writing):** Ensure all command-line utilities listed under prerequisites are installed.
4.  Run the application:
    ```bash
    python main_app.py
    ```
    **(Linux for USB Writing):** You will need to run the application with `sudo` for USB writing operations to succeed, due to the nature of disk partitioning and direct write commands:
    ```bash
    sudo python main_app.py
    ```

## Usage Steps

1.  **Step 1: Create and Install macOS VM**
    *   Select your desired macOS version from the dropdown.
    *   Click "Create VM and Start macOS Installation".
    *   A Docker container will be started, and a QEMU window will appear.
    *   Follow the on-screen instructions within the QEMU window to install macOS. This is an interactive process (formatting the virtual disk, installing macOS).
    *   Once macOS is installed and you have shut down or closed the QEMU window, the Docker process will finish.
2.  **Step 2: Extract VM Images**
    *   After the VM setup process is complete, the "Extract Images from Container" button will become enabled.
    *   Click it and select a directory on your computer where the `mac_hdd_ng.img` and `OpenCore.qcow2` files will be saved.
    *   Wait for both extraction processes to complete.
3.  **Step 3: Container Management (Optional)**
    *   After image extraction (or if the VM setup finished), you can "Stop Container" (if it's somehow still running) and then "Remove Container" to clean up the Docker container (which is no longer needed if images are extracted).
4.  **Step 4: Select Target USB Drive and Write**
    *   Connect your target USB drive.
    *   Click "Refresh List" to scan for USB drives.
    *   Select your intended USB drive from the dropdown. **VERIFY CAREFULLY!**
    *   **WARNING:** The next step will erase all data on the selected USB drive.
    *   If you are on Linux and have all dependencies, and the images from Step 2 are ready, the "Write Images to USB Drive" button will be enabled.
    *   Click it and confirm the warning dialog. The application will then partition the USB and write the images. This will take a significant amount of time.

## Future Enhancements (Based on Feedback)

*   **Improve USB Writing for Image Sizing (High Priority):** Modify the USB writing process (especially for the main macOS system) to use file-level copies (e.g., `rsync` after mounting the source image) instead of `dd` for the entire raw image. This will correctly handle various USB drive sizes by only copying used data and fitting it to the partition.
*   **Explicit Docker Image Pull:** Add a separate step/feedback for `docker pull` before `docker run`.
*   **Privilege Handling:** Add checks to see if the application is run with necessary privileges for USB writing and guide the user if not.
*   **USB Writing for macOS and Windows:** Implement the `usb_writer_macos.py` and `usb_writer_windows.py` modules.
*   **GUI for Advanced Options:** Potentially allow users to specify custom Docker parameters or OpenCore properties.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

(To be decided - likely MIT or GPLv3)
