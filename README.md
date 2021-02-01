# Docker-OSX
## [Follow @sickcodes on Twitter](https://twitter.com/sickcodes)

![Running mac osx in a docker container](/running-mac-inside-docker-qemu.png?raw=true "OSX KVM DOCKER")

Run Mac in a Docker container! Run near native OSX-KVM in Docker! X11 Forwarding!

Author: Sick.Codes https://sick.codes/ & https://twitter.com/sickcodes

PR & Contributor Credits: https://github.com/sickcodes/Docker-OSX/blob/master/CREDITS.md

Docker Hub: https://hub.docker.com/r/sickcodes/docker-osx

- sickcodes/docker-osx:latest - base recovery image

- sickcodes/docker-osx:naked - supply your own .img file

- sickcodes/docker-osx:auto - 22gb image boot to OSX shell

#### Follow [@sickcodes on Twitter](https://twitter.com/sickcodes) for updates or feature requests!

# Quick Start Docker-OSX

```bash

docker pull sickcodes/docker-osx:latest

docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:latest

# Wait 2-3 minutes until you see the logo.

```

# Quick Start 22GB Pre-Made Image


You will need around 50GB of space: half for the base image + half for your runtime image.

If you run out of space, you can nuke your Docker images/history/cache by simply deleting `/var/lib/docker`

```bash

docker pull sickcodes/docker-osx:auto

# boot straight to OSX shell with no display (19GB)
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    sickcodes/docker-osx:auto

# Wait 2-3 minutes until you drop into the shell.
```
```bash

# boot to OSX shell + display (19GB) + commands to run inside OSX
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

```bash
# find last container
docker ps -a

# docker start old container with -i for interactive
docker start -i containerid

```

# Quick Start Own Image


Supply your image with `-v "${PWD}/mac_hdd_ng.img:/image"` and use `sickcodes/docker-osx:naked`

```bash
docker pull sickcodes/docker-osx:naked

# run your own image + SSH
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v "${PWD}/mac_hdd_ng.img:/image" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:naked
```
```bash
# run your own image headless + SSH
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v "${PWD}/mac_hdd_ng.img:/image" \
    sickcodes/docker-osx:naked
```

# Features In Docker-OSX v3.0
- Full auto mode: boot straight to OSX shell.
- sickcodes/docker-osx:latest - original base recovery image (safe)
- sickcodes/docker-osx:naked - supply your own .img file (safe)
- sickcodes/docker-osx:auto - 22gb image boot to OSX shell (must trust @sickcodes)
- Supply your own image using -v $PWD/disk.img:/image
- Kubernetes Helm Chart. [See ./helm](https://github.com/sickcodes/Docker-OSX/tree/master/helm)
- OSX-KVM
- X11 Forwarding
- SSH on localhost:50922
- QEMU
- VNC on localhost:8888 [vnc version is inside a separate directory](https://github.com/sickcodes/Docker-OSX/blob/master/vnc-version/Dockerfile)
- Create an ARMY using `docker commit`
- XFVB HEADLESS (use vnc)

### All Pull Requests Welcome!

Docker-OSX is a GPLv3+ Dockerfile and we need contributors just like you :).

Upstream: https://github.com/kholia/OSX-KVM && the great guy [@kholia](https://twitter.com/kholia)

Upstream Credits (OSX-KVM project) among many others: https://github.com/kholia/OSX-KVM/blob/master/CREDITS.md

# Download The Image for sickcodes/docker-osx:naked

```bash
wget https://images2.sick.codes/mac_hdd_ng_auto.img.zst

zstd -d mac_hdd_ng_auto.img.zst

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
    -e RAM=4 \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:latest

# turn on SSH after you've installed OSX in the "Sharing" settings.
ssh fullname@localhost -p 50922

```

# Autoboot into OSX after you've installed everything

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

sudo modprobe kvm

# reboot
```

# Start the same container later (persistent disk)

This is for when you want to run the SAME container again later.

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

You do not have to reinstall everything, you can simply:

- start a new container

- overwrite the .img in the new container with your big old one

```bash

# start a new docker-osx container
# you can start with ssh, without, or vnc, because they are all interchangable.

# get the NEW container id
docker ps

# docker cp your OLD disk into the NEW container
docker cp ./mac_hdd_ng.img newcontainerid:/home/arch/OSX-KVM/mac_hdd_ng.img

# kill the NEW container
docker kill newcontainerid

# start the NEW container and it just works
docker start newcontainerid

```

# DESTROY: Wipe old images to free disk space

This is useful for getting disk space back.

It will delete ALL your old (and new) docker containers.

```bash
# WARNING deletes all old images, but saves disk space if you make too many containers
# The following command will make your containers RIP
docker system prune --all
docker image prune --all
```

# INSTANT OSX-KVM in a BOX!
This Dockerfile automates the installation of OSX-KVM inside a docker container.

It will build a Catalina Disk with up to 200GB of space.

You can change the size and version using build arguments (see below).

This file builds on top of the work done by Dhiru Kholia and many others on the OSX-KVM project.

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
* OPTIONAL: Run `qemu-img -c -O qcow2 deduped.img compressed.img` to further compress the image. This may reduce the runtime speed though, but it should reduce the size by roughly 25%.
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
docker run \
    -e RAM=4 \
    -e SMP=4 \
    -e CORES=4 \
    -e EXTRA='-usb -device usb-host,hostbus=1,hostaddr=8' \
    -e INTERNAL_SSH_PORT=23 \
    --device /dev/kvm \
    --device /dev/snd \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    docker-osx:latest

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


## Todo:
```
- Security Documentation
- GPU Acceleration: Coming Soon
- Virt-manager
```
