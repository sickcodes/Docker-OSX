# Skyscope macOS on PC USB Creator Tool

**Version:** 1.0.0 (Dev - New Workflow)
**Developer:** Miss Casey Jay Topojani
**Business:** Skyscope Sentinel Intelligence

## Vision: Your Effortless Bridge to macOS on PC

Welcome to the Skyscope macOS on PC USB Creator Tool! Our vision is to provide an exceptionally user-friendly, GUI-driven application that fully automates the complex process of creating a bootable macOS USB *Installer* for virtually any PC. This tool aims to be your comprehensive solution, simplifying the Hackintosh journey from start to finish by leveraging direct macOS downloads and intelligent OpenCore EFI configuration.

This project is dedicated to creating a seamless experience, from selecting your desired macOS version (defaulting to the latest like Sequoia where possible) to generating a USB drive that's ready to boot your PC and install macOS. We strive to incorporate advanced options for tech-savvy users while maintaining an intuitive interface for all.

## Core Features

*   **Intuitive Graphical User Interface (PyQt6):**
    *   Dark-themed by default (planned).
    *   Rounded window design (platform permitting).
    *   Clear, step-by-step workflow.
    *   Enhanced progress indicators (filling bars, spinners, percentage updates - planned).
*   **Automated macOS Installer Acquisition:**
    *   Directly downloads official macOS installer assets from Apple's servers using `gibMacOS` principles.
    *   Supports user selection of macOS versions (aiming for Sequoia, Sonoma, Ventura, Monterey, Big Sur, etc.).
*   **Automated USB Installer Creation:**
    *   **Cross-Platform USB Detection:** Identifies suitable USB drives on Linux, macOS, and Windows (using WMI for more accurate detection on Windows).
    *   **Automated Partitioning:** Creates GUID Partition Table (GPT), an EFI System Partition (FAT32, ~300-550MB), and a main macOS Installer partition (HFS+).
    *   **macOS Installer Layout:** Automatically extracts and lays out downloaded macOS assets (BaseSystem, installer packages, etc.) onto the USB to create a bootable macOS installer volume.
*   **Intelligent OpenCore EFI Setup:**
    *   Assembles a complete OpenCore EFI folder on the USB's EFI partition.
    *   Includes essential drivers, kexts, and ACPI SSDTs for broad compatibility.
    *   **Experimental `config.plist` Auto-Enhancement:**
        *   If enabled by the user (and running the tool on a Linux host for hardware detection):
            *   Gathers host hardware information (iGPU, dGPU, Audio, Ethernet, CPU).
            *   Applies targeted modifications to the `config.plist` to improve compatibility (e.g., Intel iGPU `DeviceProperties`, audio `layout-id`s, enabling Ethernet kexts).
            *   Specific handling for NVIDIA GPUs (e.g., GTX 970) based on target macOS version to allow booting (e.g., `nv_disable=1` for newer macOS if iGPU is primary, or boot-args for OCLP compatibility).
        *   Creates a backup of the original `config.plist` before modification.
*   **Privilege Handling:** Checks for and advises on necessary admin/root privileges for USB writing.
*   **User Guidance:** Provides clear instructions and warnings throughout the process.

## NVIDIA GPU Support Strategy (e.g., GTX 970 on newer macOS)

*   **Installer Phase:** This tool will configure the OpenCore EFI on the USB installer to allow your system to boot with your NVIDIA card.
    *   For macOS High Sierra (or older, if supported by download method): The `config.plist` can be set to enable NVIDIA Web Drivers (e.g., `nvda_drv=1`), assuming you would install them into macOS later.
    *   For macOS Mojave and newer (Sonoma, Sequoia, etc.) where native NVIDIA drivers are absent:
        *   If your system has an Intel iGPU, this tool will aim to configure the iGPU as primary and add `nv_disable=1` to `boot-args` for the NVIDIA card.
        *   If the NVIDIA card is your only graphics output, `nv_disable=1` will not be set, allowing macOS to boot with basic display (no acceleration) from your NVIDIA card.
        *   The `config.plist` will include boot arguments like `amfi_get_out_of_my_way=0x1` to prepare the system for potential use with OpenCore Legacy Patcher.
*   **Post-macOS Installation (User Action for Acceleration):**
    *   To achieve graphics acceleration for unsupported NVIDIA cards (like Maxwell GTX 970 or Pascal GTX 10xx) on macOS Mojave and newer, you will need to run the **OpenCore Legacy Patcher (OCLP)** application on your installed macOS system. OCLP applies necessary system patches to re-enable these drivers.
    *   This tool prepares the USB installer to be compatible with an OCLP workflow but **does not perform the root volume patching itself.**
*   **CUDA Support:** CUDA is dependent on NVIDIA's official driver stack, which is not available for newer macOS versions. Therefore, CUDA support is generally not achievable on macOS Mojave+ for NVIDIA cards.

## Current Status & Known Limitations

*   **Workflow Transition:** The project is currently transitioning from a Docker-OSX based method to a `gibMacOS`-based installer creation method. Not all platform-specific USB writers are fully refactored for this new approach yet.
*   **Windows USB Writing:** Creating the HFS+ macOS installer partition and copying files to it from Windows is complex without native HFS+ write support. The EFI part is automated; the main partition might initially require manual steps or use of `dd` for BaseSystem, with file copying being a challenge.
*   **`config.plist` Enhancement is Experimental:** Hardware detection for this feature is currently Linux-host only. The range of hardware automatically configured is limited to common setups.
*   **Universal Compatibility:** Hackintoshing is inherently hardware-dependent. While this tool aims for broad compatibility, success on every PC configuration cannot be guaranteed.
*   **Dependency on External Projects:** Relies on OpenCore and various community-sourced kexts and configurations. The `gibMacOS.py` script (or its underlying principles) is key for downloading assets.

## Prerequisites

1.  **Python:** Version 3.8 or newer.
2.  **Python Libraries:** `PyQt6`, `psutil`. Install via `pip install PyQt6 psutil`.
3.  **Core Utilities (all platforms, must be in PATH):**
    *   `git` (used by `gibMacOS.py` and potentially for cloning other resources).
    *   `7z` or `7za` (7-Zip command-line tool for archive extraction).
4.  **Platform-Specific CLI Tools for USB Writing:**
    *   **Linux (e.g., Debian 13 "Trixie"):**
        *   `sgdisk`, `parted`, `partprobe` (from `gdisk`, `parted`, `util-linux`)
        *   `mkfs.vfat` (from `dosfstools`)
        *   `mkfs.hfsplus` (from `hfsprogs`)
        *   `rsync`
        *   `dd` (core utility)
        *   `apfs-fuse`: Often requires manual compilation (e.g., from `sgan81/apfs-fuse` on GitHub). Typical build dependencies: `git g++ cmake libfuse3-dev libicu-dev zlib1g-dev libbz2-dev libssl-dev`. Ensure it's in your PATH.
        *   Install most via: `sudo apt update && sudo apt install gdisk parted dosfstools hfsprogs rsync util-linux p7zip-full` (or `p7zip`)
    *   **macOS:**
        *   `diskutil`, `hdiutil`, `rsync`, `cp`, `bless` (standard system tools).
        *   `7z` (e.g., via Homebrew: `brew install p7zip`).
    *   **Windows:**
        *   `diskpart`, `robocopy` (standard system tools).
        *   `7z.exe` (install and add to PATH).
        *   A "dd for Windows" utility (user must install and ensure it's in PATH).

## How to Run (Development Phase)

1.  Ensure all prerequisites for your OS are met.
2.  Clone this repository.
3.  **Crucial:** Clone `corpnewt/gibMacOS` into a `./scripts/gibMacOS/` subdirectory within this project, or ensure `gibMacOS.py` is in the project root or your system PATH and update `GIBMACOS_SCRIPT_PATH` in `main_app.py` if necessary.
4.  Install Python libraries: `pip install PyQt6 psutil`.
5.  Execute `python main_app.py`.
6.  **For USB Writing Operations:**
    *   **Linux:** Run with `sudo python main_app.py`.
    *   **macOS:** Run normally. You may be prompted for your password by system commands like `diskutil` or `sudo rsync`. Ensure the app has Full Disk Access if needed.
    *   **Windows:** Run as Administrator.

## Step-by-Step Usage Guide (New Workflow)

1.  **Step 1: Download macOS Installer Assets**
    *   Launch the "Skyscope macOS on PC USB Creator Tool".
    *   Select your desired macOS version (e.g., Sequoia, Sonoma).
    *   Choose a directory on your computer to save the downloaded assets.
    *   Click "Download macOS Installer Assets". The tool will use `gibMacOS` to fetch the official installer files from Apple. This may take time. Progress will be shown.
2.  **Step 2: Create Bootable USB Installer**
    *   Once downloads are complete, connect your target USB flash drive (16GB+ recommended).
    *   Click "Refresh List" to detect USB drives.
        *   **Linux/macOS:** Select your USB drive from the dropdown. Verify size and identifier carefully.
        *   **Windows:** USB drives detected via WMI will appear in the dropdown. Select the correct one. Ensure it's the `Disk X` number you intend.
    *   **(Optional, Experimental):** Check the "Try to auto-enhance config.plist..." box if you are on a Linux host and wish the tool to attempt automatic `config.plist` modification for your hardware. A backup of the original `config.plist` will be made.
    *   **CRITICAL WARNING:** Double-check your USB selection. The next action will erase the entire USB drive.
    *   Click "Create macOS Installer USB". Confirm the data erasure warning.
    *   The tool will:
        *   Partition and format the USB drive.
        *   Extract and write the macOS BaseSystem to make the USB bootable.
        *   Copy necessary macOS installer packages and files to the USB.
        *   Assemble an OpenCore EFI folder (potentially with your hardware-specific enhancements if enabled) onto the USB's EFI partition.
    *   This is a lengthy process. Monitor progress in the output area and status bar.
3.  **Boot Your PC from the USB!**
    *   Safely eject the USB. Configure your PC's BIOS/UEFI for macOS booting (disable Secure Boot, enable AHCI, XHCI Handoff, etc. - see Dortania guides).
    *   Boot from the USB and proceed with macOS installation onto your PC's internal drive.
4.  **(For Unsupported NVIDIA on newer macOS): Post-Install Patching**
    *   After installing macOS, if you have an unsupported NVIDIA card (like GTX 970 on Sonoma/Sequoia) and want graphics acceleration, you will need to run the **OpenCore Legacy Patcher (OCLP)** application from within your new macOS installation. This tool has prepared the EFI to be generally compatible with OCLP.

## Future Vision & Advanced Capabilities

*   **Fully Automated Windows USB Writing:** Replace the manual `dd` step with a reliable, integrated solution.
*   **Advanced `config.plist` Customization:**
    *   Expand hardware detection for plist enhancement to macOS and Windows hosts.
    *   Provide more granular UI controls for plist enhancements (e.g., preview changes, select specific patches).
    *   Allow users to load/save `config.plist` modification profiles.
*   **Enhanced UI/UX for Progress:** Implement determinate progress bars with percentage completion and more dynamic status updates.
*   **Debian 13 "Trixie" (and other distros) Validation:** Continuous compatibility checks and dependency streamlining.
*   **"Universal" Config Strategy (Research):** Investigate advanced techniques for more adaptive OpenCore configurations, though true universality is a significant challenge.

## Contributing

We are passionate about making Hackintoshing more accessible! Contributions, feedback, and bug reports are highly encouraged.

## License

(To be decided - e.g., MIT or GPLv3)
