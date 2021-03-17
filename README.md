# Docker-OSX
## [Follow @sickcodes on Twitter](https://twitter.com/sickcodes)

![Running mac osx in a docker container](/running-mac-inside-docker-qemu.png?raw=true "OSX KVM DOCKER")

Run Mac in a Docker container! Run near native OSX-KVM in Docker! X11 Forwarding! iMessage security research!

Author: Sick.Codes https://sick.codes/ & https://twitter.com/sickcodes

Documentation: everything is on this page!

### PR & Contributor Credits

https://github.com/sickcodes/Docker-OSX/blob/master/CREDITS.md

Docker Hub: https://hub.docker.com/r/sickcodes/docker-osx

- sickcodes/docker-osx:latest - base recovery image (10)

- sickcodes/docker-osx:big-sur - base recovery image (11)

- sickcodes/docker-osx:naked - supply your own .img file

- sickcodes/docker-osx:auto - 17.5GB image boot to OSX shell

## Professional Support Available!

Small questions & issues: open an issue!

For big projects, DM on Twitter [@sickcodes on Twitter](https://twitter.com/sickcodes) or write to us at https://sick.codes/contact.

- Enterprise support, Business support, or casual support.
- Custom images, custom scripts, consulting (per hour available!)
- One-on-one with you, or your development team.

## Kubernetes Support

Kubernetes Helm Chart & Documentation [available at ./helm](https://github.com/sickcodes/Docker-OSX/tree/master/helm)

Thank you to @cephasara for this major contribution.

[![Artifact HUB](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/docker-osx)](https://artifacthub.io/packages/search?repo=docker-osx)

#### Follow [@sickcodes on Twitter](https://twitter.com/sickcodes) for updates or feature requests!

# Basic Quick Start Docker-OSX

```bash

docker pull sickcodes/docker-osx:latest

# Catalina
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:latest

# Big Sur
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:big-sur

# Wait 2-3 minutes until you see the logo.

```

# How to use

### There are 3 images: **latest**, **auto** and **naked**.

`sickcodes/docker-osx:latest` - [I want to try it out.](https://github.com/sickcodes/Docker-OSX#quick-start-large-pre-made-image)

`sickcodes/docker-osx:latest` - [I want to use Docker-OSX to develop/secure Apps in Xcode (sign into Xcode, Transporter)](https://github.com/sickcodes/Docker-OSX#basic-quick-start-docker-osx)

`sickcodes/docker-osx:naked` - [I want to use Docker-OSX in CI/CD (sign into Xcode, Transporter)](https://github.com/sickcodes/Docker-OSX#fully-headless-using-my-own-image-for-cicd)
Create your personal image using `:latest`. And then pull your image out. And then use duplicate that image again & again for use in `:naked`.

`sickcodes/docker-osx:auto` - [I want to boot into command line only. (compile software, homebrew headless).](https://github.com/sickcodes/Docker-OSX#pre-built-image-arbitrary-command-line-arguments)

`sickcodes/docker-osx:naked` - [I need iMessage/iCloud for security research.](https://github.com/sickcodes/Docker-OSX#serial-numbers)

#### I need a screen.
**KEEP** these two lines are in your command. Works in `auto` & `naked` machines:
```dockerfile
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
```

#### I need headless.
**REMOVE** these two lines from `auto` or `naked` machines:
```dockerfile
    # -v /tmp/.X11-unix:/tmp/.X11-unix \
    # -e "DISPLAY=${DISPLAY:-:0.0}" \
```

#### I have used it already, and want to copy this image.
Use `docker commit`, copy the ID, and then `docker start ID`

**OR**

[Pull out the .img file](https://github.com/sickcodes/Docker-OSX#backup-the-disk-wheres-my-disk), and then use that [.img file with :naked](https://github.com/sickcodes/Docker-OSX#quick-start-own-image-naked-container-image)


# Quick Start Large Pre-Made Image

Current large image size: 17.5GB

This starts a container with an existing installation. This special auto image was made by @sickcodes:

- SSH enabled
- username is `user`
- password is `alpine`
- auto-updates off

You will need around *50GB* of space to run this image: half for the base image + half for your runtime image.

If you run out of space, you can delete all your old Docker images/history/cache by simply deleting `/var/lib/docker`, and restarting `dockerd`.

```bash

docker pull sickcodes/docker-osx:auto

# boot directly into a real OSX shell with no display (Xvfb) [HEADLESS]
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    sickcodes/docker-osx:auto

# Wait 2-3 minutes until you drop into the shell.
```

```bash

docker pull sickcodes/docker-osx:auto

# boot directly into a real OSX shell with a visual display [NOT HEADLESS]
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:auto

```
### Pre-built Image + Arbitrary Command Line Arguments.

```bash

docker pull sickcodes/docker-osx:auto

# boot to OSX shell + display + specify commands to run inside OSX!
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -e "OSX_COMMANDS=/bin/bash -c \"pwd && uname -a\"" \
    sickcodes/docker-osx:auto

# Boots in a minute or two!

```
### Restart an auto container

Containers that use `sickcodes/docker-osx:auto` can be stopped at started.

```bash
# find last container
docker ps -a

# docker start old container with -i for interactive
docker start -i containerid

```

# Quick Start Own Image (naked container image)

This is my favourite container. You can supply an existing disk image as a docker command line argument.

Pull images out using `sudo find /var/lib/docker -size +10G | grep mac_hdd_ng.img` 

Supply your own local image with `-v "${PWD}/mac_hdd_ng.img:/image"` and use `sickcodes/docker-osx:naked`

- Naked image is for booting any existing .img file, e.g in the current working directory (`$PWD`)

- By default, this image has a variable called `NOPICKER` which is `"true"`. This skips the disk selection menu. Use `-e NOPICKER=false` or any other string than the word `true` to enter the boot menu. This lets you use other disks instead of skipping the boot menu, e.g. recovery disk or disk utility.

```bash
docker pull sickcodes/docker-osx:naked

# run your own image + SSH
# change mac_hdd_ng.img
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v "${PWD}/mac_hdd_ng.img:/image" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:naked

# run local copy of the auto image + SSH + Boot menu
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v "${PWD}/mac_hdd_ng_auto.img:/image" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -e "NOPICKER=false" \
    sickcodes/docker-osx:naked

```

### Fully Headless, using my own image, for CI/CD

```bash
# run your own image headless + SSH
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v "${PWD}/mac_hdd_ng.img:/image" \
    sickcodes/docker-osx:naked
```

# Features In Docker-OSX v4
- `sickcodes/docker-osx:big-sur` - original base recovery image for latest OS (safe)
- Serial number generators. [See below or ./custom](https://github.com/sickcodes/Docker-OSX/tree/master/custom)
- Full auto mode: boot straight to OSX shell and even run commands as runtime arguments!
- `sickcodes/docker-osx:latest` - original base recovery image (safe)
- `sickcodes/docker-osx:naked` - supply your own .img file (safe)
- `sickcodes/docker-osx:auto` - Large docker image that boots to OSX shell (must trust @sickcodes)
- Supply your own image using `-v "${PWD}/disk.img:/image"`
- Kubernetes Helm Chart. [See ./helm](https://github.com/sickcodes/Docker-OSX/tree/master/helm)
- [OSX-KVM](https://github.com/kholia/OSX-KVM) inside a Docker container!
- X11 Forwarding
- SSH on `localhost:50922`
- QEMU + KVM!
- VNC version on `localhost:8888` [vnc version is inside a separate directory, there are security risks involved with using VNC, see insid the Dockerfile](https://github.com/sickcodes/Docker-OSX/blob/master/vnc-version/Dockerfile)
- Create an ARMY of the same exact container using `docker commit`
- Xfvb headless mode

### All Pull Requests Welcome!

Docker-OSX is a GPLv3+ Dockerfile and we need contributors just like you :)

Upstream: https://github.com/kholia/OSX-KVM && the great guy [@kholia](https://twitter.com/kholia)

Upstream Credits (OSX-KVM project) among many others: https://github.com/kholia/OSX-KVM/blob/master/CREDITS.md

# Download The Image for sickcodes/docker-osx:naked

This is the current automated image. Username is `user`, passsword is `alpine`, SSH is on, and auto-updates are off.

If the download is slow, just get the image from `docker pull sickcodes/docker-osx:auto` and find it in `/var/lib/docker`.

```bash
wget https://images2.sick.codes/mac_hdd_ng_auto.img

docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v "${PWD}/mac_hdd_ng_auto.img:/image" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:naked

```

### Other cool Docker-QEMU based projects:

[Run iOS in a Docker with Docker-eyeOS](https://github.com/sickcodes/Docker-eyeOS) - [https://github.com/sickcodes/Docker-eyeOS](https://github.com/sickcodes/Docker-eyeOS)

# Run Docker-OSX (Original Version)

```bash

docker pull sickcodes/docker-osx:latest

docker run -it \
    --device /dev/kvm \
    --device /dev/snd \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:latest

# press ctrl G if your mouse gets stuck

# scroll down to troubleshooting if you have problems

# need more RAM and SSH on localhost -p 50922?

```

# Run but allow SSH into OSX (Original Version)!

```bash
docker run -it \
    --device /dev/kvm \
    --device /dev/snd \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:latest

# turn on SSH after you've installed OSX in the "Sharing" settings.
ssh fullname@localhost -p 50922

```

# Autoboot into OSX after you've installed everything

You can use `-e NOPICKER=true`.

Old machines:

```bash
# find you containerID
docker ps

# move the no picker script on top of the Launch script
# NEW CONTAINERS
docker exec containerID mv ./Launch-nopicker.sh ./Launch.sh

# VNC-VERSION-CONTAINER
docker exec containerID mv ./Launch-nopicker.sh ./Launch_custom.sh

# LEGACY CONTAINERS
docker exec containerID bash -c "grep -v InstallMedia ./Launch.sh > ./Launch-nopicker.sh
chmod +x ./Launch-nopicker.sh
sed -i -e s/OpenCore\.qcow2/OpenCore\-nopicker\.qcow2/ ./Launch-nopicker.sh
"
```

# Requirements: KVM on the host
Need to turn on hardware virtualization in your BIOS, very easy to do.

Then have QEMU on the host if you haven't already

```bash
# ARCH
sudo pacman -S qemu libvirt dnsmasq virt-manager bridge-utils flex bison iptables-nft edk2-ovmf

# UBUNTU DEBIAN
sudo apt install qemu qemu-kvm libvirt-clients libvirt-daemon-system bridge-utils virt-manager

# CENTOS RHEL FEDORA
sudo yum install libvirt qemu-kvm

# then run
sudo systemctl enable libvirtd.service
sudo systemctl enable virtlogd.service

echo 1 | sudo tee /sys/module/kvm/parameters/ignore_msrs

sudo modprobe kvm

# reboot
```

# Start the same container later (persistent disk)

1. You can now pull the `.img` file out of the container, which is stored in `/var/lib/docker`, and supply it as a runtime argument to the `:naked` Docker image. See above.

2. This is for when you want to run the SAME container again later.

If you don't run this you will have a new image every time.

```bash
# look at your recent containers and copy the CONTAINER ID
docker ps --all

# docker start the container ID
docker start abc123xyz567

# if you have many containers, you can try automate it with filters like this
# docker ps --all --filter "ancestor=sickcodes/docker-osx"
# for locally tagged/built containers
# docker ps --all --filter "ancestor=docker-osx"

```

# Additional Boot Instructions

- Boot the macOS Base System

- Click `Disk Utility`

- Erase the BIGGEST disk (around 200gb default), DO NOT MODIFY THE SMALLER DISKS.
-- if you can't click `erase`, you may need to reduce the disk size by 1kb

- (optional) Create a partition using the unused space to house the OS and your files if you want to limit the capacity. (For Xcode 12 partition at least 60gb.)

- Click `Reinstall macOS`


## Creating images:
```bash
# You can create an image of an already configured and setup container.
# This allows you to effectively duplicate a system.
# To do this, run the following commands

# make note of your container id
docker ps --all
docker commit containerid newImageName

# To run this image do the following
docker run \
    --device /dev/kvm \
    --device /dev/snd \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    newImageName
```

# Troubleshooting

libgtk permissions denied error, thanks @raoulh + @arsham
```bash
echo $DISPLAY

# ARCH
sudo pacman -S xorg-xhost

# UBUNTU DEBIAN
sudo apt install x11-xserver-utils

# CENTOS RHEL FEDORA
sudo yum install xorg-x11-server-utils

# then run
xhost +

```

PulseAudio for sound (note neither [AppleALC](https://github.com/acidanthera/AppleALC) and varying [`alcid`](https://dortania.github.io/OpenCore-Post-Install/universal/audio.html) or [VoodooHDA-OC](https://github.com/chris1111/VoodooHDA-OC) have [codec support](https://osy.gitbook.io/hac-mini-guide/details/hda-fix#hda-codec) though [IORegistryExplorer](https://github.com/vulgo/IORegistryExplorer) does show the controller component working):

```bash
docker run \
    --device /dev/kvm \
    -e AUDIO_DRIVER=pa,server=unix:/tmp/pulseaudio.socket \
    -v "/run/user/$(id -u)/pulse/native:/tmp/pulseaudio.socket" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    sickcodes/docker-osx
```

PulseAudio debugging:
```bash
docker run \
    --device /dev/kvm \
    -e AUDIO_DRIVER=pa,server=unix:/tmp/pulseaudio.socket \
    -v "/run/user/$(id -u)/pulse/native:/tmp/pulseaudio.socket" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e PULSE_SERVER=unix:/tmp/pulseaudio.socket \
    sickcodes/docker-osx pactl list
```

Alternative run, thanks @roryrjb

```bash
docker run \
    --privileged \
    --net host \
    --cap-add=ALL \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v /dev:/dev \
    -v /lib/modules:/lib/modules \
    sickcodes/docker-osx
```

Check if your hardware virt is on

```bash
egrep -c '(svm|vmx)' /proc/cpuinfo
```

Try adding yourself to the docker group

```bash
sudo usermod -aG docker "${USER}"
```

Turn on docker daemon

```bash
# run ad hoc
sudo dockerd

# or daemonize it
sudo nohup dockerd &

# or enable it in systemd
sudo systemctl enable docker
```

# How to Forward Additional Ports from the guest.

This is how it visually looks:

`host:10023 <-> 10023:container:10023 <-> 80:guest`

```bash
On the host
```bash
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -e ADDITIONAL_PORTS='hostfwd=tcp::10023-:80,' \
    -p 10023:10023 \
    sickcodes/docker-osx:auto
```

Inside the container:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install nginx
sudo sed -i -e 's/8080/80/' /usr/local/etc/nginx/nginx.confcd
# sudo nginx -s stop
sudo nginx
```

nginx should appear on the host at port 10023.

You can string multiple statements, for example:

```bash
    -e ADDITIONAL_PORTS='hostfwd=tcp::10023-:80,hostfwd=tcp::10043-:443,'
    -p 10023:10023 \
    -p 10043:10043 \
```

# How to Enable Network Forwarding

Allow ipv4 forwarding for bridged networking connections:

This is not required for LOCAL installations and may cause containers behind [VPN's to leak host IP](https://sick.codes/cve-2020-15590/).

If you are connecting to a REMOTE Docker-OSX, e.g. a "Mac Mini" in a datacenter, then this may boost networking:

```bash
# enable for current session
sudo sysctl -w net.ipv4.ip_forward=1

# OR
# sudo tee /proc/sys/net/ipv4/ip_forward <<< 1

# enable permanently
sudo touch /etc/sysctl.conf
sudo tee -a /etc/sysctl.conf <<EOF
net.ipv4.ip_forward = 1
EOF

# OR edit manually
nano /etc/sysctl.conf || vi /etc/sysctl.conf || vim /etc/sysctl.conf

# now reboot
```

# How to install Docker if you don't have Docker already

```bash
### Arch
sudo pacman -S docker
sudo groupadd docker
sudo usermod -aG docker "${USER}"

### Ubuntu

sudo apt remove docker docker-engine docker.io containerd runc -y
sudo apt install apt-transport-https ca-certificates curl gnupg-agent software-properties-common -y
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
apt-key fingerprint 0EBFCD88
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update -y
sudo apt install docker-ce docker-ce-cli containerd.io -y
sudo groupadd docker
sudo usermod -aG docker "${USER}"


```

### Fedora: if you have no internet connectivity from the VM, and you are using bridge networking:

```bash
# Set the docker0 bridge to the trusted zone
sudo firewall-cmd --permanent --zone=trusted --add-interface=docker0
sudo firewall-cmd --reload
```

# Backup the disk (Where's my disk?)

You can use `docker cp`

```bash
# docker copy your image OUT of your container (warning, double disk space)
docker cp oldcontainerid:/home/arch/OSX-KVM/mac_hdd_ng.img .
```

Or if you lost your container, find it with this:

```bash
# fast way, find 10 gigabyte OSX disks hiding in your docker container storage
sudo find /var/lib/docker -size +10G | grep mac_hdd_ng.img

# you can move (mv) it somewhere, using cp can take loads of disk space
sudo mv somedir/mac_hdd_ng.img .

```

# Use an Old Docker-OSX Disk in a Fresh Container (Replication)

[Use the sickcodes/docker-osx:naked image.](https://github.com/sickcodes/Docker-OSX/tree/master#quick-start-own-image)

# Internet Speeds

### FAST internet
`-e NETWORKING=vmxnet3`

### SLOW internet
`-e NETWORKING=e1000-82545em`

# DESTROY: Wipe old images to free disk space

The easiest way to clean out your entire Docker (ALL images, layers, and containers) is to `sudo rm -rf /var/lib/docker`

This is useful for getting disk space back.

It will delete ALL your old (and new) docker containers.

```bash
# WARNING deletes all old images, but saves disk space if you make too many containers
# The following command will make your containers RIP
docker system prune --all
docker image prune --all
```

# CI/CD Related Improvements
## How to reduce the size of the image
* Start up the container as usual, and remove unnecessary files. A useful way
  to do this is to use `du -sh *` starting from the `/` directory, and find
  large directories where files can be removed. E.g. unnecessary cached files,
  Xcode platforms, etc.
* Once you are satisfied with the amount of free space, enable trim with `sudo trimforce enable`, and reboot.
* Zero out the empty space on the disk with `dd if=/dev/zero of=./empty && rm -f empty`
* Shut down the VM and copy out the qcow image with `docker cp stoppedcontainer:/home/arch/OSX-KVM/mac_hdd_ng.img .`
* Run `qemu-img check -r all mac_hdd_ng.img` to fix any errors.
* Run `qemu-img convert -O qcow2 mac_hdd_ng.img deduped.img` and check for errors again
* OPTIONAL: Run `qemu-img convert -c -O qcow2 deduped.img compressed.img` to further compress the image. This may reduce the runtime speed though, but it should reduce the size by roughly 25%.
* Check for errors again, and build a fresh docker image. E.g. with this Dockerfile

```
FROM sickcodes/docker-osx
USER arch
COPY --chown=arch ./deduped.img /home/arch/OSX-KVM/mac_hdd_ng.img
```

## How to run in headless mode
First make sure [autoboot is enabled](#autoboot-into-osx-after-youve-installed-everything)

Next, you will want to set up SSH to be automatically started.

```bash
sudo systemsetup -setremotelogin on
```

Make sure to commit the new docker image and save it, or rebuild as described in the [section on reducing disk space](#how-to-reduce-the-size-of-the-image).

Then run it with these arguments.

```bash
# Run with the -nographic flag, and enable a telnet interface
  docker run \
    --device /dev/kvm \
    -p 50922:10022 \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -e EXTRA="-monitor telnet::45454,server,nowait -nographic -serial null" \
    mycustomimage
```

Optionally, you can enable the SPICE protocol, which allows you to use `remote-viewer` to access it rather than VNC.

Note: `-disable-ticketing` will allow unauthenticated access to the VM. See the [spice manual](https://www.spice-space.org/spice-user-manual.html) for help setting up authenticated access ("Ticketing").

```bash
  docker run \
    --device /dev/kvm \
    -p 50922:10022 \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -e EXTRA="-monitor telnet::45454,server,nowait -nographic -serial null -spice disable-ticketing,port=3001" \
    mycustomimage
```

Then simply do `remote-viewer spice://localhost:3001` and add `--spice-debug` for debugging.


# Custom Build or Local Development

If you are building Docker-OSX locally, you will want to use Arch Linux mirrors.

Mirror locations can be found here (use 2 letter country codes): https://archlinux.org/mirrorlist/all/

```bash
docker build -t docker-osx:latest \
    --build-arg RANKMIRRORS=true \
    --build-arg MIRROR_COUNTRY=US \
    --build-arg MIRROR_COUNT=10 \
    --build-arg VERSION=10.15.6 \
    --build-arg SIZE=200G .
```

# Custom QEMU Arguments (passthrough devices)

Pass any devices/directories to the Docker container & the QEMU arguments using the handy `-e EXTRA=` runtime options.

```bash
# example customizations
docker run \
    -e RAM=4 \
    -e SMP=4 \
    -e CORES=4 \
    -e EXTRA='-usb -device usb-host,hostbus=1,hostaddr=8' \
    -e INTERNAL_SSH_PORT=23 \
    -e MAC_ADDRESS="$(xxd -c1 -p -l 6 /dev/urandom | tr '\n' ':' | cut -c1-17)" \
    -e AUDIO_DRIVER=alsa \
    -e IMAGE_PATH=/image \
    -e SCREEN_SHARE_PORT=5900 \
    -e DISPLAY=:0 \
    -e NETWORKING=vmxnet3 \
    --device /dev/kvm \
    --device /dev/snd \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    docker-osx:latest

```

# Serial Numbers

The easiest way to show you is by these examples.

For serial numbers, generate them in `./custom` OR make docker generate them at runtime (see below).

At any time, verify your serial number before logging in iCloud, etc.

```bash
# this is a quick way to check your serial number via cli inside OSX
ioreg -l | grep IOPlatformSerialNumber

# or from the host
sshpass -p 'alpine' ssh user@localhost -p 50922 'ioreg -l | grep IOPlatformSerialNumber'
```
# This example generates a random set of serial numbers at runtime, headlessly

```bash
# proof of concept only, generates random serial numbers, headlessly, and quits right after.
docker run --rm -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -e NOPICKER=true \
    -e GENERATE_UNIQUE=true \
    -e DEVICE_MODEL="iMacPro1,1" \
    -e OSX_COMMANDS='ioreg -l | grep IOPlatformSerialNumber' \
    sickcodes/docker-osx:auto
```

# This example generates a specific set of serial numbers at runtime

```bash
# run the same as above 17gb auto image, with SSH, with nopicker, and save the bootdisk for later.
# you don't need to save the bootdisk IF you supply specific serial numbers!

docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -e NOPICKER=true \
    -e GENERATE_SPECIFIC=true \
    -e DEVICE_MODEL="iMacPro1,1" \
    -e SERIAL="C02TW0WAHX87" \
    -e BOARD_SERIAL="C027251024NJG36UE" \
    -e UUID="5CCB366D-9118-4C61-A00A-E5BAF3BED451" \
    -e MAC_ADDRESS="A8:5C:2C:9A:46:2F" \
    -e OSX_COMMANDS='ioreg -l | grep IOPlatformSerialNumber' \
    sickcodes/docker-osx:auto
```

### This example generates a specific set of serial numbers at runtime, with your existing image, at 1000x1000 display resolution.

```bash
# run an existing image in current directory, with a screen, with SSH, with nopicker.

stat mac_hdd_ng.img # make sure you have an image if you're using :naked

docker run -it \
    -v "${PWD}/mac_hdd_ng.img:/image" \
    --device /dev/kvm \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -p 50922:10022 \
    -e NOPICKER=true \
    -e GENERATE_SPECIFIC=true \
    -e DEVICE_MODEL="iMacPro1,1" \
    -e SERIAL="C02TW0WAHX87" \
    -e BOARD_SERIAL="C027251024NJG36UE" \
    -e UUID="5CCB366D-9118-4C61-A00A-E5BAF3BED451" \
    -e MAC_ADDRESS="A8:5C:2C:9A:46:2F" \
    -e WIDTH=1000 \
    -e HEIGHT=1000 \
    sickcodes/docker-osx:naked
```

If you want to generate serial numbers, either make them at runtime using
`    -e GENERATE_UNIQUE=true \`

Or you can generate them inside the `./custom` folder. And then use:
```bash
    -e GENERATE_SPECIFIC=true \
    -e SERIAL="" \
    -e BOARD_SERIAL="" \
    -e UUID="" \
    -e MAC_ADDRESS="" \
```

#### Persistence from generating serial numbers is obviously ideal:

```bash

stat mac_hdd_ng_testing.img
touch ./output.env

# generate fresh random serial numbers, with a screen, using your own image, and save env file with your new serial numbers for later.

docker run -it \
    --device /dev/kvm \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -p 50922:10022 \
    -e NOPICKER=true \
    -e GENERATE_UNIQUE=true \
    -e GENERATE_SPECIFIC=true \
    -e DEVICE_MODEL="iMacPro1,1" \
    -v "${PWD}/output.env:/env" \
    -v "${PWD}/mac_hdd_ng_testing.img:/image" \
    sickcodes/docker-osx:naked
```

To use iMessage or iCloud you need to change `5` values.

`SERIAL`

`BOARD_SERIAL`

`UUID`

`MAC_ADDRESS`

_`ROM` is just the lowercased mac address, without `:` between each word._

You can tell the container to generate them for you using `-e GENERATE_UNIQUE=true`

Or tell the container to use specific ones using `-e GENERATE_SPECIFIC=true`

```bash
    -e GENERATE_SPECIFIC=true \
    -e DEVICE_MODEL="iMacPro1,1" \
    -e SERIAL="C02TW0WAHX87" \
    -e BOARD_SERIAL="C027251024NJG36UE" \
    -e UUID="5CCB366D-9118-4C61-A00A-E5BAF3BED451" \
    -e MAC_ADDRESS="A8:5C:2C:9A:46:2F" \
```

### Where do you get the serial numbers?

```bash
apt install libguestfs -y
pacman -S libguestfs
yum install libguestfs -y
```

Inside the `./custom` folder you will find `4` scripts.

- `config-nopicker-custom.plist`
- `opencore-image-ng.sh`
These two files are from OSX-KVM.

You don't need to touch these two files.

The config.plist has 5 values replaced with placeholders. [Click here to see those values for no reason.](https://github.com/sickcodes/Docker-OSX/blob/master/custom/config-nopicker-custom.plist#L705)

- `generate-unique-machine-values.sh`
This script will generate serial numbers, with Mac Addresses, plus output to CSV/TSV, plus make a `bootdisk image`.

You can create hundreds, `./custom/generate-unique-machine-values.sh --help`

```bash
./custom/generate-unique-machine-values.sh \
    --count 1 \
    --tsv ./serial.tsv \
    --bootdisks \
    --output-bootdisk OpenCore.qcow2 \
    --output-env source.env.sh
```

Or if you have some specific serial numbers...

- `generate-specific-bootdisk.sh`
```bash
generate-specific-bootdisk.sh \
    --model "${DEVICE_MODEL}" \
    --serial "${SERIAL}" \
    --board-serial "${BOARD_SERIAL}" \
    --uuid "${UUID}" \
    --mac-address "${MAC_ADDRESS}" \
    --output-bootdisk OpenCore-nopicker.qcow2
```

# Change Resolution Docker-OSX - change resolution OpenCore OSX-KVM 

The display resolution is controlled by this line:

https://github.com/sickcodes/Docker-OSX/blob/master/custom/config-nopicker-custom.plist#L819

Instead of mounting that disk, Docker-OSX will generate a new `OpenCore.qcow2` by using this one cool trick:

```bash
-e GENERATE_UNIQUE=true \
-e WIDTH=800 \
-e HEIGHT=600 \
```

To use `WIDTH`/`HEIGHT`, you must use with either `-e GENERATE_UNIQUE=true` or `-e GENERATE_SPECIFIC=true`.

It will take around 30 seconds longer to boot because it needs to make a new boot partition using `libguestfs`.

```bash
-e GENERATE_SPECIFIC=true \
-e WIDTH=1920 \
-e HEIGHT=1080 \
-e SERIAL="" \
-e BOARD_SERIAL="" \
-e UUID="" \
-e MAC_ADDRESS="" \
```

## Change Docker-OSX Resolution Examples

```bash
# using an image in your current directory
stat mac_hdd_ng.img

docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v "${PWD}/mac_hdd_ng.img:/image" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -e GENERATE_SPECIFIC=true \
    -e DEVICE_MODEL="iMacPro1,1" \
    -e SERIAL="C02TW0WAHX87" \
    -e BOARD_SERIAL="C027251024NJG36UE" \
    -e UUID="5CCB366D-9118-4C61-A00A-E5BAF3BED451" \
    -e MAC_ADDRESS="A8:5C:2C:9A:46:2F" \
    -e MASTER_PLIST_URL=https://raw.githubusercontent.com/sickcodes/Docker-OSX/master/custom/config-nopicker-custom.plist \
    -e WIDTH=1600 \
    -e HEIGHT=900 \
    sickcodes/docker-osx:naked
```

```bash
# generating random serial numbers, using the DIY installer, along with the screen resolution changes.
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -e GENERATE_UNIQUE=true \
    -e WIDTH=800 \
    -e HEIGHT=600 \
    sickcodes/docker-osx:latest


```


Here's a few other resolutions! If you resolution is invalid, it will default to 800x600.

```
    -e WIDTH=800 \
    -e HEIGHT=600 \
```
```
    -e WIDTH=1280 \
    -e HEIGHT=768 \
```
```
    -e WIDTH=1600 \
    -e HEIGHT=900 \
```
```
    -e WIDTH=1920 \
    -e HEIGHT=1080 \
```
```
    -e WIDTH=2560 \
    -e HEIGHT=1600 \
```

# Mount a disk inside OSX from the host

Pass the disk into the container as a volume and then pass the disk again into QEMU command line extras with.

Use the `config-custom.plist` because you probably want to see the boot menu, otherwise omit the first line:

```bash
DISK_TWO="${PWD}/mount_me.img"
```
```dockerfile
-e MASTER_PLIST_URL='https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-custom.plist' \
-v "${DISK_TWO}:/disktwo" \
-e EXTRA='-device ide-hd,bus=sata.5,drive=DISK-TWO -drive id=DISK-TWO,if=none,file=/disktwo,format=qcow2' \
```

Example:

```bash
OSX_IMAGE="${PWD}/mac_hdd_ng_xcode_bigsur.img"
DISK_TWO="${PWD}/mount_me.img"

docker run -it \
    --device /dev/kvm \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e MASTER_PLIST_URL='https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-custom.plist' \
    -v "${OSX_IMAGE}":/image \
    -v "${DISK_TWO}":/disktwo \
    -e EXTRA='-device ide-hd,bus=sata.5,drive=DISK-TWO -drive id=DISK-TWO,if=none,file=/disktwo,format=qcow2' \
    sickcodes/docker-osx:naked
```


# Allow USB passthrough

The simplest way to do this is the following:

First of all, in order to do this, QEMU must be started as root. It is also potentially possible to do this by changing the permissions of the device in the container.
See [here](https://www.linuxquestions.org/questions/slackware-14/qemu-usb-permissions-744557/#post3628691).

For example, create a new Dockerfile with the following

```bash
FROM sickcodes/docker-osx
USER arch
RUN sed -i -e s/exec\ qemu/exec\ sudo\ qemu/ ./Launch.sh
COPY --chown=arch ./new_image.img /home/arch/OSX-KVM/mac_hdd_ng.img
```

Where `new_image.img` is the qcow2 image you extracted. Then rebuild with `docker build .`

Find out the bus and port numbers of your USB device which you want to pass through to the VM.

```bash
lsusb -t
/:  Bus 02.Port 1: Dev 1, Class=root_hub, Driver=xhci_hcd/6p, 5000M
/:  Bus 01.Port 1: Dev 1, Class=root_hub, Driver=xhci_hcd/12p, 480M
    |__ Port 2: Dev 5, If 0, Class=Human Interface Device, Driver=usbhid, 12M
    |__ Port 2: Dev 5, If 1, Class=Chip/SmartCard, Driver=, 12M
    |__ Port 3: Dev 2, If 0, Class=Wireless, Driver=, 12M
    |__ Port 3: Dev 2, If 1, Class=Wireless, Driver=, 12M
    |__ Port 5: Dev 3, If 0, Class=Video, Driver=uvcvideo, 480M
    |__ Port 5: Dev 3, If 1, Class=Video, Driver=uvcvideo, 480M
```

In this example, we want to pass through a smartcard device. The device we want is on bus 1 and port 2.

There may also be differences if your device is usb 2.0 (ehci) vs usb 3.0 (xhci).
See [here](https://unix.stackexchange.com/a/452946/101044) for more details.


```bash
# hostbus and hostport correspond to the numbers from lsusb
# runs in privileged mode to enable access to the usb devices.
docker run \
  --privileged \
  --device /dev/kvm \
  -e RAM=4 \
  -p 50922:10022 \
  -e "DISPLAY=${DISPLAY:-:0.0}" \
  -e EXTRA="-device virtio-serial-pci -device usb-host,hostbus=1,hostport=2" \
  mycustomimage
```

You should see the device show up when you do `system_profiler SPUSBDataType` in the MacOS shell.

Important Note: this will cause the host system to lose access to the USB device while the VM is running!

## What is `${DISPLAY:-:0.0}`?

`$DISPLAY` is the shell variable that refers to your X11 display server.

`${DISPLAY}` is the same, but allows you to join variables like this:

- e.g. `${DISPLAY}_${DISPLAY}` would print `:0.0_:0.0`
- e.g. `$DISPLAY_$DISPLAY`     would print `:0.0`

...because `$DISPLAY_` is not `$DISPLAY`

`${variable:-fallback}` allows you to set a "fallback" variable to be substituted if `$variable` is not set.

You can also use `${variable:=fallback}` to set that variable (in your current terminal).

In Docker-OSX, we assume, `:0.0` is your default `$DISPLAY` variable.

You can see what yours is
```bash
echo $DISPLAY
```
Hence, `${DISPLAY:-:0.0}` will use whatever variable your X11 server has set for you, else `:0.0`

## What is `-v /tmp/.X11-unix:/tmp/.X11-unix`?

`-v` is a Docker command-line option that lets you pass a volume to the container.

The directory that we are letting the Docker container use is a X server display socket.

`/tmp/.X11-unix`

If we let the Docker container use the same display socket as our own environment, then any applications you run inside the Docker container will show up on your screen too! [https://www.x.org/archive/X11R6.8.0/doc/RELNOTES5.html](https://www.x.org/archive/X11R6.8.0/doc/RELNOTES5.html)


## TODO:
```
- Security Documentation
- GPU Acceleration: Coming Soon
- Virt-manager
```
