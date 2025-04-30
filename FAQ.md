# Frequently Asked Questions

These questions come up regularly, so here are the answers.

## Basics

### Is this legal?

The [macOS software license](https://www.apple.com/legal/sla/) allows running (some versions of) macOS in a virtual machine only on Apple hardware. The [Apple Security Bounty terms and conditions](https://security.apple.com/terms-and-conditions/) make an exception to that (and essentially anything in the macOS software license) under some specific circumstances.

Therefore, yes, there is a legal use for Docker-OSX. If your use doesn't fall under the license or the security bounty terms, then you are/will be violating the macOS software license. **Note that this is not provided as legal advice, and you should consult with your own counsel for legal guidance.**

You may also be interested in this [deeper dive into the subject](https://sick.codes/is-hackintosh-osx-kvm-or-docker-osx-legal/).

### What does Docker-OSX do?

Docker-OSX is an approach to setting up and launching a macOS virtual machine (VM) under [docker](https://en.wikipedia.org/wiki/Docker_(software)). The [Dockerfile](Dockerfile) is essentially a docker image building script that:
1. validates a few things about the environment
2. installs VM software (qemu) and creates a virtual disk within the docker container
3. generates a serial number and firmware to make the VM look (enough) like Mac hardware
4. downloads a macOS installer disk image
5. generates a shell script to start the VM

The default configuration is intended to create an ephemeral but repeatably bootable macOS that can be probed for security research.

### Why docker?

Docker provides a straightforward way to package a flexible turnkey solution to setting up a macOS VM. It is not the only way to do so, nor is it necessarily the best approach to setting up a long-lived, persistent macOS VM. You may prefer to study the [Dockerfile](Dockerfile) and/or [OSX-KVM](https://github.com/kholia/OSX-KVM) to prepare a VM to run under [proxmox](https://en.wikipedia.org/wiki/Proxmox_Virtual_Environment) or [libvirt](https://en.wikipedia.org/wiki/Libvirt).

## Can I...

### ...run BlueBubbles/AirMessage/Beeper on it?

Yes. Make sure you [make serial numbers persist across reboots](README.md#making-serial-numbers-persist-across-reboots) after generating a unique serial number for yourself; don't use the default serial number. There is, of course, no guarantee that Apple won't block/disable your account, or inflict other consequences. See also the [legal considerations](#is-this-legal).

### ...develop iPhone apps on it?

Yes. You will probably find Xcode's UI frustratingly slow, but yes. Compiling apps (e.g. React Native) from the command line is likely to be less frustrating. There is, of course, no guarantee that Apple won't block/disable your account, remove you from the Apple Developer program, or inflict other consequences. See also the [legal considerations](#is-this-legal).

### ...connect my iPhone or other USB device to it?

Yes, at least if your host OS is Linux. See [instructions](README.md#vfio-iphone-usb-passthrough-vfio). It may or may not be possible if your host OS is Windows.

### ...run CI/CD processes with it?

Maybe, but there are several reasons not to:
1. There are [legal considerations](#is-this-legal).
2. Nested virtualization is generally unavailable on cloud-hosted CI/CD and therefore Docker-OSX doesn't run.
3. You are almost always better off using your own macOS runners (on virtual or actual Mac hardware) rather than trying to make the square peg of Docker-OSX fit the round hole of macOS-specific CI/CD.

You absolutely can install runners on the macOS VM itself (which does not get around the legal considerations mentioned above), but [Docker-OSX may not be the best approach](#why-docker).

### ...run on Linux but with Wayland?

Yes, but your Wayland server must support X11 connections (or you can [use VNC instead](README.md#building-a-headless-container-that-allows-insecure-vnc-on-localhost-for-local-use-only)).

### ...run on Windows?

Yes, as long as you have a new enough version of Windows 11 and have WSL2 set up. See [this section of the README](README.md#id-like-to-run-docker-osx-on-windows) for details. No, it will not work under Windows 10. Not even if you have WSL2 set up.

### ...run on macOS?

If you have a Mac with Apple Silicon you are better served by [UTM](https://apps.apple.com/us/app/utm-virtual-machines/id1538878817?mt=12).

If you have an Intel Mac you can install and run docker (either [Docker Desktop](https://www.docker.com/products/docker-desktop/) or [colima](https://github.com/abiosoft/colima)). In either case, docker will be running under a Linux VM, which complicates things. You are likely to encounter one or more of the [common errors](#common-errors) below. Consider using qemu directly with HVF acceleration (e.g. with [libvirt](https://libvirt.org/macos.html)) instead.

### ...run on cloud services?

Cloud providers typically run their various services within virtual machines running on top of their actual hardware. These VMs typically are not set up to provide nested virtualization, which means KVM is unavailable so Docker-OSX will not work. This is _especially and specifically_ the case on CI/CD runners such as GitHub Actions, Azure DevOps Pipelines, CircleCI, GitLab CI/CD, etc. (however, see [running CI/CD](#run-cicd-processes-with-it)). Some cloud providers offer services that do allow virtualization, such as [Amazon's EC2 Bare Metal Instances](https://aws.amazon.com/about-aws/whats-new/2018/05/announcing-general-availability-of-amazon-ec2-bare-metal-instances/), but often at a significant premium.

In short, probably not.

## Common Errors

### Docker Errors

If you get an error like `docker: command not found` then you don't have docker installed and none of this works. Try [Docker Desktop](https://www.docker.com/products/docker-desktop/) on Windows or your distribution's normal package manager on Linux.

If you get an error like `docker: Got permission denied while trying to connect to the Docker daemon` or `docker: unknown server OS: .` the mostly likely explanation is that your user isn't in the `docker` Unix group. You'll need to add yourself to the `docker` group, log out, and log back in.

If you get an error like `Cannot connect to the Docker daemon at unix://var/run/docker.sock. Is the docker daemon running?` then `dockerd` isn't running. On most Linux distributions you should be able to start it with `sudo systemctl enable docker --now`.

### GTK Initialization Failed

This is an X11 error and means that the arguments to qemu are telling it to connect to an X11 display that it either can't connect to at all or doesn't have permission to connect to. In the latter case, this can usually be fixed by running `xhost +` on the host running the X11 server.

In many cases, however, it is preferable to tell qemu to listen for a VNC connection instead of trying to connect to X11; see [this section of the README](README.md#building-a-headless-container-that-allows-insecure-vnc-on-localhost-for-local-use-only) for instructions.

### KVM Error

If you get an error like `error gathering device information while adding custom device "/dev/kvm": no such file or directory` that means KVM is not available/working on the Linux kernel on which you are running docker. This could be because you are attempting to run somewhere that doesn't support nested virtualization (see [above](#can-i-run-this-on)), or because your BIOS does not have virtualization extensions turned on, or because your CPU is too old to support virtualization extensions, or your Linux kernel does not have KVM support loaded/enabled. Fixing KVM issues is well beyond the scope of this document, but you can [start here](https://www.linux-kvm.org/page/FAQ).

### ALSA Error

You might get an error like this:
```
(qemu) ALSA lib confmisc.c:767:(parse_card) cannot find card '0'
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_card_driver returned error: No such file or directory
ALSA lib confmisc.c:392:(snd_func_concat) error evaluating strings
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_concat returned error: No such file or directory
ALSA lib confmisc.c:1246:(snd_func_refer) error evaluating name
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5233:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2660:(snd_pcm_open_noupdate) Unknown PCM default
alsa: Could not initialize DAC
alsa: Failed to open `default':
alsa: Reason: No such file or directory
ALSA lib confmisc.c:767:(parse_card) cannot find card '0'
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_card_driver returned error: No such file or directory
ALSA lib confmisc.c:392:(snd_func_concat) error evaluating strings
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_concat returned error: No such file or directory
ALSA lib confmisc.c:1246:(snd_func_refer) error evaluating name
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5233:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2660:(snd_pcm_open_noupdate) Unknown PCM default
alsa: Could not initialize DAC
alsa: Failed to open `default':
alsa: Reason: No such file or directory
audio: Failed to create voice `dac'
ALSA lib confmisc.c:767:(parse_card) cannot find card '0'
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_card_driver returned error: No such file or directory
ALSA lib confmisc.c:392:(snd_func_concat) error evaluating strings
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_concat returned error: No such file or directory
ALSA lib confmisc.c:1246:(snd_func_refer) error evaluating name
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5233:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2660:(snd_pcm_open_noupdate) Unknown PCM default
alsa: Could not initialize ADC
alsa: Failed to open `default':
alsa: Reason: No such file or directory
ALSA lib confmisc.c:767:(parse_card) cannot find card '0'
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_card_driver returned error: No such file or directory
ALSA lib confmisc.c:392:(snd_func_concat) error evaluating strings
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_concat returned error: No such file or directory
ALSA lib confmisc.c:1246:(snd_func_refer) error evaluating name
ALSA lib conf.c:4745:(_snd_config_evaluate) function snd_func_refer returned error: No such file or directory
ALSA lib conf.c:5233:(snd_config_expand) Evaluate error: No such file or directory
ALSA lib pcm.c:2660:(snd_pcm_open_noupdate) Unknown PCM default
alsa: Could not initialize ADC
alsa: Failed to open `default':
alsa: Reason: No such file or directory
audio: Failed to create voice `adc'
```

Docker-OSX defaults to telling qemu to use ALSA for audio output. Your host system may be using PulseAudio instead (see [PulseAudio](README.md#pulseaudio)), but you may not need audio output at all. You can pass `-e AUDIO_DRIVER="id=none,driver=none"` to disable audio output.

### No Disk to Install On

If you have launched the installer but don't see a disk to install macOS on, it probably means you skipped the step where you run Disk Utility to format the virtual disk. See the [README](README.md#additional-boot-instructions-for-when-you-are-creating-your-container).

### Slow Installation

This is not unique to virtual hardware. The macOS installation process gives apparently random and dependably incorrect time estimates, and can often appear to have completely frozen. Just be patient. It could take hours, maybe even more than a day.

### Installer After Completing Install

If you wind up in the installer again after you've installed macOS it means you booted from the installer disk instead of the disk you installed macOS on. Reboot and make sure you choose the correct disk to boot.

## Next Steps

Congratulations, you got a macOS VM up and running! Now what?

# Fixing Apple ID Login Issues in macOS Virtual Machines

## Problem Overview

When running macOS in a virtual machine, you may encounter problems logging into Apple services including:
- Apple ID
- iMessage
- iCloud
- App Store

This happens because Apple's services can detect that macOS is running in a virtual environment and block access. The solution is to apply a kernel patch that hides the VM presence from Apple's detection mechanism.

NOTE as per forum post: Unfortunately, this would very possibly break qemu-guest-agent, which is necessary for the host getting VM status or taking hot snapshot while the VM is running. This is because qemu-guest-agent also checks the hv_vmm_present flag, but only works if it is true (=1).

Use at your own risk. Hope it would help.

## Solution: Kernel Patching

This guide provides three methods to apply the necessary kernel patch. All methods implement the same fix originally described in [this forum post](https://forum.proxmox.com/threads/anyone-can-make-bluetooth-work-on-sonoma.153301/#post-697832).

### Prerequisites

Before proceeding with any method:
- Make sure you can access your EFI partition
- Locate your OpenCore `config.plist` file (typically in the `EFI/OC` folder)
- Back up your current `config.plist` before making changes

## Method 1: Using the Utility Script (Simplest Approach)

This is the fastest and easiest way to apply the patch.

1. Mount your EFI partition using Clover Configurator or another EFI mounting tool
2. Download the patch script:
   ```bash
   wget https://raw.githubusercontent.com/sickcodes/Docker-OSX/scripts/apply_appleid_kernelpatch.py
   ```
3. Run the script with your `config.plist` file path:
   ```bash
   python3 apply_appleid_kernelpatch.py /path/to/config.plist
   ```

**Pro Tip**: You can drag and drop the `config.plist` file into your terminal after typing `python3 apply_appleid_kernelpatch.py` for an easy path insertion.

**Note**: If you encounter a "permission denied" error, run the command with `sudo`:
```bash
sudo python3 apply_appleid_kernelpatch.py /path/to/config.plist
```

## Method 2: Using OCAT (OpenCore Auxiliary Tools) GUI

If you prefer a graphical approach:

1. Open OCAT and load your `config.plist`
2. Navigate to the **Kernel** section
3. Go to the **Patch** subsection
4. Add two new patch entries with the following details:

### Patch 1
| Setting | Value |
|---------|-------|
| **Identifier** | `kernel` |
| **Base** | *(leave empty)* |
| **Count** | `1` |
| **Find (Hex)** | `68696265726E61746568696472656164790068696265726E617465636F756E7400` |
| **Limit** | `0` |
| **Mask** | *(leave empty)* |
| **Replace (Hex)** | `68696265726E61746568696472656164790068765F766D6D5F70726573656E7400` |
| **Skip** | `0` |
| **Arch** | `x86_64` |
| **MinKernel** | `20.4.0` |
| **MaxKernel** | *(leave empty)* |
| **Enabled** | `True` |
| **Comment** | `Sonoma VM BT Enabler - PART 1 of 2 - Patch kern.hv_vmm_present=0` |

### Patch 2
| Setting | Value |
|---------|-------|
| **Identifier** | `kernel` |
| **Base** | *(leave empty)* |
| **Count** | `1` |
| **Find (Hex)** | `626F6F742073657373696F6E20555549440068765F766D6D5F70726573656E7400` |
| **Limit** | `0` |
| **Mask** | *(leave empty)* |
| **Replace (Hex)** | `626F6F742073657373696F6E20555549440068696265726E617465636F756E7400` |
| **Skip** | `0` |
| **Arch** | `x86_64` |
| **MinKernel** | `22.0.0` |
| **MaxKernel** | *(leave empty)* |
| **Enabled** | `True` |
| **Comment** | `Sonoma VM BT Enabler - PART 2 of 2 - Patch kern.hv_vmm_present=0` |

5. Save the configuration
6. Reboot your VM

## Method 3: Direct `config.plist` Editing

For users who prefer to manually edit the configuration file:

1. Mount your EFI partition
2. Locate and open your `config.plist` file in a text editor
3. Find the `<key>Kernel</key>` → `<dict>` → `<key>Patch</key>` → `<array>` section
4. Add these two `<dict>` entries within the `<array>`:

```xml
<dict>
    <key>Arch</key>
    <string>x86_64</string>
    <key>Base</key>
    <string></string>
    <key>Comment</key>
    <string>Sonoma VM BT Enabler - PART 1 of 2 - Patch kern.hv_vmm_present=0</string>
    <key>Count</key>
    <integer>1</integer>
    <key>Enabled</key>
    <true/>
    <key>Find</key>
    <data>aGliZXJuYXRlaGlkcmVhZHkAaGliZXJuYXRlY291bnQA</data>
    <key>Identifier</key>
    <string>kernel</string>
    <key>Limit</key>
    <integer>0</integer>
    <key>Mask</key>
    <data></data>
    <key>MaxKernel</key>
    <string></string>
    <key>MinKernel</key>
    <string>20.4.0</string>
    <key>Replace</key>
    <data>aGliZXJuYXRlaGlkcmVhZHkAaHZfdm1tX3ByZXNlbnQA</data>
    <key>ReplaceMask</key>
    <data></data>
    <key>Skip</key>
    <integer>0</integer>
</dict>
<dict>
    <key>Arch</key>
    <string>x86_64</string>
    <key>Base</key>
    <string></string>
    <key>Comment</key>
    <string>Sonoma VM BT Enabler - PART 2 of 2 - Patch kern.hv_vmm_present=0</string>
    <key>Count</key>
    <integer>1</integer>
    <key>Enabled</key>
    <true/>
    <key>Find</key>
    <data>Ym9vdCBzZXNzaW9uIFVVSUQAaHZfdm1tX3ByZXNlbnQA</data>
    <key>Identifier</key>
    <string>kernel</string>
    <key>Limit</key>
    <integer>0</integer>
    <key>Mask</key>
    <data></data>
    <key>MaxKernel</key>
    <string></string>
    <key>MinKernel</key>
    <string>22.0.0</string>
    <key>Replace</key>
    <data>Ym9vdCBzZXNzaW9uIFVVSUQAaGliZXJuYXRlY291bnQA</data>
    <key>ReplaceMask</key>
    <data></data>
    <key>Skip</key>
    <integer>0</integer>
</dict>
```

5. Save the file
6. Reboot your VM

## Important Notes

- The `MinKernel` values (`20.4.0` and `22.0.0`) may need adjustment depending on your specific macOS version (Monterey, Ventura, Sonoma, etc.)
- If you encounter issues, consult the [OpenCore documentation](https://dortania.github.io/docs/) for appropriate values for your setup
- Always back up your configuration before making changes
- After applying the patch and rebooting, try signing into Apple services again

## What This Patch Does

This patch tricks macOS into believing it's running on physical hardware by redirecting the `hv_vmm_present` kernel variable, which normally indicates VM presence. After applying the patch, Apple services should function normally within your virtual environment.
### Slow UI

The macOS UI expects and relies on GPU acceleration, and there is (currently) no way to provide GPU acceleration in the virtual hardware. See [osx-optimizer](https://github.com/sickcodes/osx-optimizer) for macOS configuration to speed things up.

### Extract the Virtual Disk

With the container stopped, `sudo find /var/lib/docker -size +10G -name mac_hdd_ng.img` to find the disk image then copy it where you want it.

### Disk Space

Is your host machine's disk, specifically `/var` (because of `/var/lib/docker`), getting full? [Fix it](README.md#increase-disk-space-by-moving-varlibdocker-to-external-drive-block-storage-nfs-or-any-other-location-conceivable).

### Increase RAM or CPUs/cores

The `RAM`, `SMP`, and `CORES` options are all docker environment variables, which means it uses whatever you provide any time you start a container.

