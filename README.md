# Docker-OSX · [Follow @sickcodes on Twitter](https://twitter.com/sickcodes)

![Running Mac OS X in a Docker container](/running-mac-inside-docker-qemu.png?raw=true "OSX KVM DOCKER")

Run Mac OS X in Docker with near-native performance! X11 Forwarding! iMessage security research!

## Author

This project is maintained by [Sick.Codes](https://sick.codes/). [(Twitter)](https://twitter.com/sickcodes)

Additional credits can be found here: https://github.com/sickcodes/Docker-OSX/blob/master/CREDITS.md

Additionally, comprehensive list of all contributors can be found here: https://github.com/sickcodes/Docker-OSX/graphs/contributors

Big thanks to [@kholia](https://twitter.com/kholia) for maintaining the upstream project, which Docker-OSX is built on top of: [OSX-KVM](https://github.com/kholia/OSX-KVM).

Also special thanks to [@thenickdude](https://github.com/thenickdude) who maintains the valuable fork [KVM-OpenCore](https://github.com/thenickdude/KVM-Opencore), which was started by [@Leoyzen](https://github.com/Leoyzen/)!

Extra special thanks to the OpenCore team over at: https://github.com/acidanthera/OpenCorePkg. Their well-maintained bootloader provides much of the great functionality that Docker-OSX users enjoy :)

If you like this project, consider contributing here or upstream!

<a href="https://hub.docker.com/r/sickcodes/docker-osx"><img src="https://dockeri.co/image/sickcodes/docker-osx"/></a>

## Quick Start Docker-OSX

First time here? try [initial setup](#initial-setup), otherwise try the instructions below to use either Catalina or Big Sur.

### Catalina [![https://img.shields.io/docker/image-size/sickcodes/docker-osx/latest?label=sickcodes%2Fdocker-osx%3Alatest](https://img.shields.io/docker/image-size/sickcodes/docker-osx/latest?label=sickcodes%2Fdocker-osx%3Alatest)](https://hub.docker.com/r/sickcodes/docker-osx/tags?page=1&ordering=last_updated)

```bash
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:latest
```
### Big Sur [![https://img.shields.io/docker/image-size/sickcodes/docker-osx/big-sur?label=sickcodes%2Fdocker-osx%3Abig-sur](https://img.shields.io/docker/image-size/sickcodes/docker-osx/big-sur?label=sickcodes%2Fdocker-osx%3Abig-sur)](https://hub.docker.com/r/sickcodes/docker-osx/tags?page=1&ordering=last_updated)

```bash
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -e GENERATE_UNIQUE=true \
    -e MASTER_PLIST_URL=https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-custom.plist \
    sickcodes/docker-osx:big-sur
```

## Make container FASTER

SEE commands in [https://github.com/sickcodes/osx-optimizer](https://github.com/sickcodes/osx-optimizer)!

- Skip the GUI login screen (at your own risk!)
- Disable spotlight indexing on macOS to heavily speed up Virual Instances.
- Disable heavy login screen wallpaper
- Disable updates (at your own risk!)

## Important notices:

**2021-05-04:** Big Sur requires an updated OpenCore.qcow2 image, simply add:

```
# this will not be required after OSX-KVM integrates the changes. No effect if you were already using this method.
    -e GENERATE_UNIQUE=true \
    -e MASTER_PLIST_URL=https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-custom.plist \
```

**2021-05-08:** QEMU 6 VNC changes:

For Docker-OSX users who are using [VNC over QEMU using](#building-a-headless-container-which-allows-insecure-vnc-on-localhost-for-local-use-only) `-e EXTRA=...`

- `password` is now `password=on`
- `change vnc password` now need a username at the end, `change vnc password someuser`

## Technical details

There currently four images, each with different use cases (explained [below](#container-images)):

Catalina make your own image:

[![https://img.shields.io/docker/image-size/sickcodes/docker-osx/latest?label=sickcodes%2Fdocker-osx%3Alatest](https://img.shields.io/docker/image-size/sickcodes/docker-osx/latest?label=sickcodes%2Fdocker-osx%3Alatest)](https://hub.docker.com/r/sickcodes/docker-osx/tags?page=1&ordering=last_updated)

Big-Sur make your own image:

[![https://img.shields.io/docker/image-size/sickcodes/docker-osx/big-sur?label=sickcodes%2Fdocker-osx%3Abig-sur](https://img.shields.io/docker/image-size/sickcodes/docker-osx/big-sur?label=sickcodes%2Fdocker-osx%3Abig-sur)](https://hub.docker.com/r/sickcodes/docker-osx/tags?page=1&ordering=last_updated)

Pre-made system by [Sick.Codes](https://sick.codes): username: `user`, password: `alpine`

[![https://img.shields.io/docker/image-size/sickcodes/docker-osx/auto?label=sickcodes%2Fdocker-osx%3Aauto](https://img.shields.io/docker/image-size/sickcodes/docker-osx/auto?label=sickcodes%2Fdocker-osx%3Aauto)](https://hub.docker.com/r/sickcodes/docker-osx/tags?page=1&ordering=last_updated)

Bring-your-own-image setup (use any of the above first):

[![https://img.shields.io/docker/image-size/sickcodes/docker-osx/naked?label=sickcodes%2Fdocker-osx%3Anaked](https://img.shields.io/docker/image-size/sickcodes/docker-osx/naked?label=sickcodes%2Fdocker-osx%3Anaked)](https://hub.docker.com/r/sickcodes/docker-osx/tags?page=1&ordering=last_updated)

## Capabilities
- SSH enabled (`localhost:50922`)
- VNC enabled (`localhost:8888`) if using ./vnc version
- [serial number generator!](https://github.com/sickcodes/osx-serial-generator)
- X11 forwarding is enabled
- runs on top of QEMU + KVM
- supports Big Sur, custom images, Xvfb headless mode
- you can clone your container with `docker commit`

### Requirements

- 20GB disk space for bare minimum installation
- virtualization should be enabled in your BIOS settings
- a kvm-capable host
- at least 50 GBs for `:auto` (half for the base image, half for your runtime image

### TODO

- documentation for security researchers
- gpu acceleration
- support for virt-manager

## Docker

Images built on top of the contents of this repository are also available on **Docker Hub** for convenience: https://hub.docker.com/r/sickcodes/docker-osx

A comprehensive list of the available Docker images and their intended purpose can be found in the [Instructions](#instructions).

## Kubernetes

Docker-OSX supports Kubernetes.

Kubernetes Helm Chart & Documentation can be found under the [helm directory](helm/README.md).

Thanks [cephasara](https://github.com/cephasara) for contributing this major contribution.

[![Artifact HUB](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/docker-osx)](https://artifacthub.io/packages/search?repo=docker-osx)

## Support

### Small questions & issues

Feel free to open an [issue](https://github.com/sickcodes/Docker-OSX/issues/new/choose), should you come across minor issues with running Docker-OSX or have any questions.

#### Resolved issues

Before you open an issue, however, please check the [closed issues](https://github.com/sickcodes/Docker-OSX/issues?q=is%3Aissue+is%3Aclosed) and confirm that you're using the latest version of this repository — your issues may have already been resolved! You might also see your answer in our questions and answers section [below](#more-questions-and-answers).

### Feature requests and updates

Follow [@sickcodes](https://twitter.com/sickcodes)!

### Professional support

For more sophisticated endeavours, we offer the following support services:

- Enterprise support, business support, or casual support.
- Custom images, custom scripts, consulting (per hour available!)
- One-on-one conversations with you or your development team.

In case you're interested, contact [@sickcodes on Twitter](https://twitter.com/sickcodes) or click [here](https://sick.codes/contact).

## License/Contributing

Docker-OSX is licensed under the [GPL v3+](LICENSE). Contributions are welcomed and immensely appreciated. You are in-fact permitted to use Docker-OSX as a tool to create proprietary software.

### Other cool Docker/QEMU based projects
- [Run Android in a Docker Container with Dock Droid](https://github.com/sickcodes/dock-droid)
- [Run iOS in a Docker container with Docker-eyeOS](https://github.com/sickcodes/Docker-eyeOS) - [https://github.com/sickcodes/Docker-eyeOS](https://github.com/sickcodes/Docker-eyeOS)
- [Run iMessage relayer in Docker with Bluebubbles.app](https://bluebubbles.app/) - [Getting started wiki](https://github.com/BlueBubblesApp/BlueBubbles-Server/wiki/Running-via-Docker)

## Disclaimer

If you are serious about Apple Security, and possibly finding 6-figure bug bounties within the Apple Bug Bounty Program, then you're in the right place! Further notes: [Is Hackintosh, OSX-KVM, or Docker-OSX legal?](https://sick.codes/is-hackintosh-osx-kvm-or-docker-osx-legal/)

Product names, logos, brands and other trademarks referred to within this project are the property of their respective trademark holders. These trademark holders are not affiliated with our repository in any capacity. They do not sponsor or endorse this project in any way.

# Instructions

## Container images

### Already set up or just looking to make a container quickly? Check out our [quick start](#quick-start-docker-osx) or see a bunch more use cases under our [container creation examples](#container-creation-examples) section.

There are several different Docker-OSX images available which are suitable for different purposes.

- `sickcodes/docker-osx:latest` - [I just want to try it out.](#quick-start-docker-osx)
- `sickcodes/docker-osx:latest` - [I want to use Docker-OSX to develop/secure apps in Xcode (sign into Xcode, Transporter)](#quick-start-your-own-image-naked-container-image)
- `sickcodes/docker-osx:naked` - [I want to use Docker-OSX for CI/CD-related purposes (sign into Xcode, Transporter)](#building-a-headless-container-from-a-custom-image)

Create your personal image using `:latest` or `big-sur`. Then, pull the image out the image. Afterwards, you will be able to duplicate that image and import it to the `:naked` container, in order to revert the container to a previous state repeatedly.

- `sickcodes/docker-osx:auto` - [I'm only interested in using the command line (useful for compiling software or using Homebrew headlessly).](#prebuilt-image-with-arbitrary-command-line-arguments)
- `sickcodes/docker-osx:naked` - [I need iMessage/iCloud for security research.](#generating-serial-numbers)
- `sickcodes/docker-osx:big-sur` - [I want to run Big Sur.](#quick-start-docker-osx)

## Initial setup
Before you do anything else, you will need to turn on hardware virtualization in your BIOS. Precisely how will depend on your particular machine (and BIOS), but it should be straightforward.

Then, you'll need QEMU and some other dependencies on your host:

```bash
# ARCH
sudo pacman -S qemu libvirt dnsmasq virt-manager bridge-utils flex bison iptables-nft edk2-ovmf

# UBUNTU DEBIAN
sudo apt install qemu qemu-kvm libvirt-clients libvirt-daemon-system bridge-utils virt-manager libguestfs-tools

# CENTOS RHEL FEDORA
sudo yum install libvirt qemu-kvm
```

Then, enable libvirt and load the KVM kernel module:

```bash
sudo systemctl enable --now libvirtd
sudo systemctl enable --now virtlogd

echo 1 | sudo tee /sys/module/kvm/parameters/ignore_msrs

sudo modprobe kvm
```

## Additional boot instructions for when you are [creating your container](#container-creation-examples)

- Boot the macOS Base System

- Click `Disk Utility`

- Erase the BIGGEST disk (around 200gb default), DO NOT MODIFY THE SMALLER DISKS.
-- if you can't click `erase`, you may need to reduce the disk size by 1kb

- (optional) Create a partition using the unused space to house the OS and your files if you want to limit the capacity. (For Xcode 12 partition at least 60gb.)

- Click `Reinstall macOS`

## Troubleshooting

### Routine checks

This is a great place to start if you are having trouble getting going, especially if you're not that familiar with Docker just yet.

Just looking to make a container quickly? Check out our [container creation examples](#container-creation-examples) section.

More specific/advanced troubleshooting questions and answers may be found in [More Questions and Answers](#more-questions-and-answers). You should also check out the [closed issues](https://github.com/sickcodes/Docker-OSX/issues?q=is%3Aissue+is%3Aclosed). Someone else might have gotten a question like yours answered already even if you can't find it in this document!

#### Confirm that your CPU supports virtualization

See [initial setup](#initial-setup).

#### Confirm your user is part of the the Docker group, KVM group, libvirt group

If you use `sudo dockerd` or dockerd is controlled by systemd/systemctl, then you must be in the Docker group.
If you are not in the Docker group:

```bash
sudo usermod -aG docker "${USER}"
```
and also add yourself to the kvm and libvirt groups if needed:

```bash
sudo usermod -aG libvirt "${USER}"
sudo usermod -aG kvm "${USER}"
```

See also: [initial setup](#initial-setup).

#### Is the docker daemon enabled?

```bash
# enable it in systemd (it will persist across reboots this way)
sudo systemctl enable --now docker

# or just start it as your user with systemd instead of enabling it
systemctl start docker

# or run ad hoc
sudo dockerd

# or daemonize it
sudo nohup dockerd &
```

## More Questions and Answers

Big thank you to our contributors who have worked out almost every conceivable issue so far!

[https://github.com/sickcodes/Docker-OSX/blob/master/CREDITS.md](https://github.com/sickcodes/Docker-OSX/blob/master/CREDITS.md)

### The big-sur image starts slowly after installation. Is this expected?

Automatic updates are still on in the container's settings. You may wish to turn them off. [We have future plans for development around this.](https://github.com/sickcodes/Docker-OSX/issues/227)

### What is `${DISPLAY:-:0.0}`?

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

That way, `${DISPLAY:-:0.0}` will use whatever variable your X11 server has set for you, else `:0.0`

### What is `-v /tmp/.X11-unix:/tmp/.X11-unix`?

`-v` is a Docker command-line option that lets you pass a volume to the container.

The directory that we are letting the Docker container use is a X server display socket.

`/tmp/.X11-unix`

If we let the Docker container use the same display socket as our own environment, then any applications you run inside the Docker container will show up on your screen too! [https://www.x.org/archive/X11R6.8.0/doc/RELNOTES5.html](https://www.x.org/archive/X11R6.8.0/doc/RELNOTES5.html)

### ALSA errors on startup or container creation

You may when initialising or booting into a container see errors from the `(qemu)` console of the following form: 
`ALSA lib blahblahblah: (function name) returned error: no such file or directory`. These are more or less expected. As long as you are able to boot into the container and everything is working, no reason to worry about these.

See also: [here](https://github.com/sickcodes/Docker-OSX/issues/174).

### Start the same container later (persistent disk)

Created a container with `docker run` and want to reuse the underlying image again later? 

NB: see [container creation examples](#container-creation-examples) first for how to get to the point where this is applicable.

This is for when you want to run the SAME container again later. You may need to use `docker commit` to save your container before you can reuse it. Check if your container is persisted with `docker ps --all`.

If you don't run this you will have a new image every time. 

```bash
# look at your recent containers and copy the CONTAINER ID
docker ps --all

# docker start the container ID
docker start -ai abc123xyz567

# if you have many containers, you can try automate it with filters like this
# docker ps --all --filter "ancestor=sickcodes/docker-osx"
# for locally tagged/built containers
# docker ps --all --filter "ancestor=docker-osx"

```

You can also pull the `.img` file out of the container, which is stored in `/var/lib/docker`, and supply it as a runtime argument to the `:naked` Docker image. 

See also: [here](https://github.com/sickcodes/Docker-OSX/issues/197).

### I have used Docker-OSX before and want to restart a container that starts automatically

Containers that use `sickcodes/docker-osx:auto` can be stopped while being started.

```bash
# find last container
docker ps -a

# docker start old container with -i for interactive, -a for attach STDIN/STDOUT
docker start -ai -i <Replace this with your ID>
```

### LibGTK errors

You may see one or more libgtk-related errors if you do not have everything set up for hardware virtualisation yet. If you have not yet done so, check out the [initial setup](#initial-setup) section and the [routine checks](#routine-checks) section as you may have missed a setup step or may not have all the needed Docker dependencies ready to go.

See also: [here](https://github.com/sickcodes/Docker-OSX/issues/174).

#### Permissions denied error

If you have not yet set up xhost, try the following:

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

### RAM over-allocation
You cannot allocate more RAM than your machine has. The default is 3 Gigabytes: `-e RAM=3`.

If you are trying to allocate more RAM to the container than you currently have available, you may see an error like the following: `cannot set up guest memory 'pc.ram': Cannot allocate memory`. See also: [here](https://github.com/sickcodes/Docker-OSX/issues/188), [here](https://github.com/sickcodes/Docker-OSX/pull/189).

For example (below) the `buff/cache` already contains 20 Gigabytes of allocated RAM:

```console
[user@hostname ~]$ free -mh
               total        used        free      shared  buff/cache   available
Mem:            30Gi       3.5Gi       7.0Gi       728Mi        20Gi        26Gi
Swap:           11Gi          0B        11Gi
```

Clear the buffer and the cache:

```bash
sudo tee /proc/sys/vm/drop_caches <<< 3
```

Now check the RAM again:

```console
[user@hostname ~]$ free -mh
               total        used        free      shared  buff/cache   available
Mem:            30Gi       3.3Gi        26Gi       697Mi       1.5Gi        26Gi
Swap:           11Gi          0B        11Gi
```

### PulseAudio

#### Use PulseAudio for sound

Note: [AppleALC](https://github.com/acidanthera/AppleALC), [`alcid`](https://dortania.github.io/OpenCore-Post-Install/universal/audio.html) and [VoodooHDA-OC](https://github.com/chris1111/VoodooHDA-OC) do not have [codec support](https://osy.gitbook.io/hac-mini-guide/details/hda-fix#hda-codec). However, [IORegistryExplorer](https://github.com/vulgo/IORegistryExplorer) does show the controller component working.

```bash
docker run \
    --device /dev/kvm \
    -e AUDIO_DRIVER=pa,server=unix:/tmp/pulseaudio.socket \
    -v "/run/user/$(id -u)/pulse/native:/tmp/pulseaudio.socket" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    sickcodes/docker-osx
```

#### PulseAudio debugging

```bash
docker run \
    --device /dev/kvm \
    -e AUDIO_DRIVER=pa,server=unix:/tmp/pulseaudio.socket \
    -v "/run/user/$(id -u)/pulse/native:/tmp/pulseaudio.socket" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e PULSE_SERVER=unix:/tmp/pulseaudio.socket \
    sickcodes/docker-osx pactl list
```

### Forward additional ports (nginx hosting example)

It's possible to forward additional ports depending on your needs. In this example, we'll use Mac OSX to host nginx:

```
host:10023 <-> 10023:container:10023 <-> 80:guest
```

On the host machine, run:

```bash
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -e ADDITIONAL_PORTS='hostfwd=tcp::10023-:80,' \
    -p 10023:10023 \
    sickcodes/docker-osx:auto
```

In a Terminal session running the container, run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install nginx
sudo sed -i -e 's/8080/80/' /usr/local/etc/nginx/nginx.confcd
# sudo nginx -s stop
sudo nginx
```

**nginx should now be reachable on port 10023.**

Additionally, you can string multiple statements together, for example:

```bash
    -e ADDITIONAL_PORTS='hostfwd=tcp::10023-:80,hostfwd=tcp::10043-:443,'
    -p 10023:10023 \
    -p 10043:10043 \
```

### Bridged networking

You might not need to do anything with the default setup to enable internet connectivity from inside the container. Additionally, `curl` may work even if `ping` doesn't.

See discussion [here](https://github.com/sickcodes/Docker-OSX/issues/177) and [here](https://github.com/sickcodes/Docker-OSX/issues/72) and [here](https://github.com/sickcodes/Docker-OSX/issues/88).

### Enable IPv4 forwarding for bridged network connections for remote installations

This is not required for LOCAL installations.

Additionally note it may [cause the host to leak your IP, even if you're using a VPN in the container](https://sick.codes/cve-2020-15590/).

However, if you're trying to connect to an instance of Docker-OSX remotely (e.g. an instance of Docker-OSX hosted in a datacenter), this may improve your performance:

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

# or edit manually with the editor of your choice
nano /etc/sysctl.conf || vi /etc/sysctl.conf || vim /etc/sysctl.conf

# now reboot
```

### Fedora: enable internet connectivity with a bridged network

Fedora's default firewall settings may prevent Docker's network interface from reaching the internet. In order to reoslve this, you will need to whitelist the interface in your firewall:

```bash
# Set the docker0 bridge to the trusted zone
sudo firewall-cmd --permanent --zone=trusted --add-interface=docker0
sudo firewall-cmd --reload
```

### Nested Hardware Virtualization

Check if your machine has hardware virtualization enabled:

```bash
sudo tee /sys/module/kvm/parameters/ignore_msrs <<< 1

egrep -c '(svm|vmx)' /proc/cpuinfo
```

### Virtual network adapters

#### Fast internet connectivity

`-e NETWORKING=vmxnet3`

#### Slow internet connectivity

`-e NETWORKING=e1000-82545em`

### CI/CD Related Improvements

#### Tips for reducing the size of the image

- Start the container as usual, and remove unnecessary files. A useful way
  to do this is to use `du -sh *` starting from the `/` directory, and find
  large directories where files can be removed. E.g. unnecessary cached files,
  Xcode platforms, etc.
- Once you are satisfied with the amount of free space, enable trim with `sudo trimforce enable`, and reboot.
- Zero out the empty space on the disk with `dd if=/dev/zero of=./empty && rm -f empty`
- Shut down the VM and copy out the qcow image with `docker cp stoppedcontainer:/home/arch/OSX-KVM/mac_hdd_ng.img .`
- Run `qemu-img check -r all mac_hdd_ng.img` to fix any errors.
- Run `qemu-img convert -O qcow2 mac_hdd_ng.img deduped.img` and check for errors again
- **OPTIONAL:** Run `qemu-img convert -c -O qcow2 deduped.img compressed.img` to further compress the image. This may reduce the runtime speed though, but it should reduce the size by roughly 25%.
- Check for errors again, and build a fresh docker image. E.g. with this Dockerfile

```
FROM sickcodes/docker-osx
USER arch
COPY --chown=arch ./deduped.img /home/arch/OSX-KVM/mac_hdd_ng.img
```

### Run Docker-OSX headlessly with Telnet

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

### What mirrors are appropriate to use to build Docker-OSX locally?

If you are building Docker-OSX locally, you'll probably want to use Arch Linux's mirrors.

Mirror locations can be found here (uses two-letter country codes): https://archlinux.org/mirrorlist/all/

```bash
docker build -t docker-osx:latest \
    --build-arg RANKMIRRORS=true \
    --build-arg MIRROR_COUNTRY=US \
    --build-arg MIRROR_COUNT=10 \
    --build-arg VERSION=10.15.6 \
    --build-arg SIZE=200G .
```

### Custom QEMU Arguments (passthrough devices)

Pass any devices/directories to the Docker container & the QEMU arguments using the handy runtime argument provider option `-e EXTRA=`.

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

### Generating serial numbers

Generate serial numbers in `./custom` OR make docker generate them at runtime (see below).

At any time, verify your serial number before logging into iCloud, etc.

```bash
# this is a quick way to check your serial number via cli inside OSX
ioreg -l | grep IOPlatformSerialNumber

# or from the host
sshpass -p 'alpine' ssh user@localhost -p 50922 'ioreg -l | grep IOPlatformSerialNumber'
```

#### Getting started with serial numbers

```bash
# ARCH
pacman -S libguestfs

# UBUNTU DEBIAN
apt install libguestfs -y

# RHEL FEDORA CENTOS
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
#### This example generates a random set of serial numbers at runtime, headlessly

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

#### This example generates a specific set of serial numbers at runtime

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

#### This example generates a specific set of serial numbers at runtime, with your existing image, at 1000x1000 display resolution

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

#### Making serial numbers persist across reboots

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

- `SERIAL`
- `BOARD_SERIAL`
- `UUID`
- `MAC_ADDRESS`

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

### I'd like to run Docker-OSX with WSL2 (Windows, Ubuntu)

Ensure KVM is enabled and `x11-apps` is installed. 

See more in-depth discussion [here](https://github.com/sickcodes/Docker-OSX/issues/17) and [here](https://github.com/sickcodes/Docker-OSX/issues/60).


### Changing display resolution

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

#### Change Docker-OSX Resolution Examples

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

#### This example shows how to change resolution after the container is created.

First step is to stop the docker daemon
```
sudo systemctl stop docker
```
The second step is to change container config in 
```
/var/lib/docker/containers/[container-id]/config.v2.json
```
(Suppose your original WIDTH is 1024 and HEIGHT is 768, you can search 1024 and replace it with the new value. Same for 768.)

The last step is to restart the docker daemon
```
sudo systemctl restart docker
```

### Mounting physical disks in Mac OSX

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

#### Physical disk mounting example

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

See also: [here](https://github.com/sickcodes/Docker-OSX/issues/222).


#### Extracting the APFS disk on Linux

In Docker-OSX, we are using `qcow2` images.

This means the image grows as you use it, but the guest OS thinks you have 200GB available.


**READ ONLY**

```bash
# mount the qemu image like a real disk
sudo modprobe nbd max_part=8
sudo qemu-nbd --connect=/dev/nbd0 ./image.img
sudo fdisk /dev/nbd0 -l

mkdir -p ./mnt
sudo mount /dev/nbd0p1 ./mnt

# inspect partitions (2 partitions)
sudo fdisk /dev/nbd0 -l

# mount using apfs-linux-rw OR apfs-fuse
mkdir -p ./part

sudo mount /dev/nbd0p2 ./part
sudo apfs-fuse -o allow_other /dev/nbd0p2 ./part

```

When you are finishing looking at your disk, you can unmount the partition, the disk, and remove the loopback device:

```bash
sudo umount ./part
sudo umount ./mnt
sudo qemu-nbd --disconnect /dev/nbd0
sudo rmmod nbd
```

### USB Passthrough

Firstly, QEMU must be started as root. 

It is also potentially possible to accomplish USB passthrough by changing the permissions of the device in the container.
See [here](https://www.linuxquestions.org/questions/slackware-14/qemu-usb-permissions-744557/#post3628691).

For example, create a new Dockerfile with the following

```bash
FROM sickcodes/docker-osx
USER arch
RUN sed -i -e s/exec\ qemu/exec\ sudo\ qemu/ ./Launch.sh
COPY --chown=arch ./new_image.img /home/arch/OSX-KVM/mac_hdd_ng.img
```

Where `new_image.img` is the qcow2 image you extracted. Then rebuild with `docker build .`

Next we need to find out the bus and port numbers of the USB device we want to pass through to the VM:

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

## Container creation examples

#### Quick Start your own image (naked container image)

This is my favourite container. You can supply an existing disk image as a Docker command line argument.

- Pull images out using `sudo find /var/lib/docker -size +10G | grep mac_hdd_ng.img`

- Supply your own local image with the command argument `-v "${PWD}/mac_hdd_ng.img:/image"` and use `sickcodes/docker-osx:naked` when instructing Docker to create your container.

  - Naked image is for booting any existing .img file, e.g in the current working directory (`$PWD`)
  - By default, this image has a variable called `NOPICKER` which is `"true"`. This skips the disk selection menu. Use `-e NOPICKER=false` or any other string than the word `true` to enter the boot menu.

    This lets you use other disks instead of skipping the boot menu, e.g. recovery disk or disk utility.

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

### Building an OSX container with video output

The Quick Start command should work out of the box, provided that you keep the following lines. Works in `auto` & `naked` machines:

```
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
```

#### Download the image manually and use it in Docker 

[![https://img.shields.io/docker/image-size/sickcodes/docker-osx/naked?label=sickcodes%2Fdocker-osx%3Anaked](https://img.shields.io/docker/image-size/sickcodes/docker-osx/naked?label=sickcodes%2Fdocker-osx%3Anaked)](https://hub.docker.com/r/sickcodes/docker-osx/tags?page=1&ordering=last_updated)


This is a particularly good way for downloading the container, in case Docker's CDN (or your connection) happens to be slow.

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

#### Prebuilt image with arbitrary command line arguments 

[![https://img.shields.io/docker/image-size/sickcodes/docker-osx/auto?label=sickcodes%2Fdocker-osx%3Aauto](https://img.shields.io/docker/image-size/sickcodes/docker-osx/auto?label=sickcodes%2Fdocker-osx%3Aauto)](https://hub.docker.com/r/sickcodes/docker-osx/tags?page=1&ordering=last_updated)

```bash
docker pull sickcodes/docker-osx:auto

# boot to OS X shell + display + specify commands to run inside OS X!
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -e "OSX_COMMANDS=/bin/bash -c \"pwd && uname -a\"" \
    sickcodes/docker-osx:auto

# Boots in a minute or two!
```

### Further examples

There's a myriad of other potential use cases that can work perfectly with Docker-OSX, some of which you'll see below!

### Building a headless OSX container

For a headless container, **remove** the following two lines from your `docker run` command:

```
    # -v /tmp/.X11-unix:/tmp/.X11-unix \
    # -e "DISPLAY=${DISPLAY:-:0.0}" \
```

#### Building a headless container from a custom image 

[![https://img.shields.io/docker/image-size/sickcodes/docker-osx/naked?label=sickcodes%2Fdocker-osx%3Anaked](https://img.shields.io/docker/image-size/sickcodes/docker-osx/naked?label=sickcodes%2Fdocker-osx%3Anaked)](https://hub.docker.com/r/sickcodes/docker-osx/tags?page=1&ordering=last_updated)

This is particularly helpful for CI/CD pipelines.

```bash
# run your own image headless + SSH
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v "${PWD}/mac_hdd_ng.img:/image" \
    sickcodes/docker-osx:naked
```

### Building a headless container which allows insecure VNC on localhost (!for local use only!)

**Must change -it to -i to be able to interact with the QEMU console**

**To exit a container using -i you must `docker kill <containerid>`. For example, to kill everything, `docker ps | xargs docker kill`.**

Native QEMU VNC example

```bash
docker run -i \
    --device /dev/kvm \
    -p 50922:10022 \
    -p 5999:5999 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    -e EXTRA="-display none -vnc 0.0.0.0:99,password=on" \
    sickcodes/docker-osx:big-sur

# type `change vnc password myvncusername` into the docker terminal and set a password
# connect to localhost:5999 using VNC
# qemu 6 seems to require a username for vnc now
```

**NOT TLS/HTTPS Encrypted at all!**

Or `ssh -N root@1.1.1.1 -L  5999:127.0.0.1:5999`, where `1.1.1.1` is your remote server IP.

(Note: if you close port 5999 and use the SSH tunnel, this becomes secure.)

### Building a headless container to run remotely with secure VNC

Add the following line:

`-e EXTRA="-display none -vnc 0.0.0.0:99,password=on"`

In the Docker terminal, press `enter` until you see `(qemu)`.

Type `change vnc password someusername`

Enter a password for your new vnc username^.

You also need the container IP: `docker inspect <containerid> | jq -r '.[0].NetworkSettings.IPAddress'`

Or `ip n` will usually show the container IP first.

Now VNC connect using the Docker container IP, for example `172.17.0.2:5999`

Remote VNC over SSH: `ssh -N root@1.1.1.1 -L  5999:172.17.0.2:5999`, where `1.1.1.1` is your remote server IP and `172.17.0.2` is your LAN container IP.

Now you can direct connect VNC to any container built with this command!

### I'd like to use SPICE instead of VNC

Optionally, you can enable the SPICE protocol, which allows use of `remote-viewer` to access your OSX container rather than VNC.

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

#### Creating images based on an already configured and set up container
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

#### Run Catalina Pre-Installed [![https://img.shields.io/docker/image-size/sickcodes/docker-osx/auto?label=sickcodes%2Fdocker-osx%3Aauto](https://img.shields.io/docker/image-size/sickcodes/docker-osx/auto?label=sickcodes%2Fdocker-osx%3Aauto)](https://hub.docker.com/r/sickcodes/docker-osx/tags?page=1&ordering=last_updated)

```bash
docker pull sickcodes/docker-osx:auto

# boot directly into a real OS X shell with a visual display [NOT HEADLESS]
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:auto

# username is user
# passsword is alpine
```

```bash
docker pull sickcodes/docker-osx:auto

# boot directly into a real OS X shell with no display (Xvfb) [HEADLESS]
docker run -it \
    --device /dev/kvm \
    -p 50922:10022 \
    sickcodes/docker-osx:auto

# username is user
# passsword is alpine
# Wait 2-3 minutes until you drop into the shell.
```

#### Run the original version of Docker-OSX

```bash

docker pull sickcodes/docker-osx:latest

docker run -it \
    --device /dev/kvm \
    --device /dev/snd \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:latest

# press CTRL + G if your mouse gets stuck
# scroll down to troubleshooting if you have problems
# need more RAM and SSH on localhost -p 50922?
```

#### Run but enable SSH in OS X (Original Version)!

```bash
docker run -it \
    --device /dev/kvm \
    --device /dev/snd \
    -p 50922:10022 \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e "DISPLAY=${DISPLAY:-:0.0}" \
    sickcodes/docker-osx:latest

# turn on SSH after you've installed OS X in the "Sharing" settings.
ssh user@localhost -p 50922
```

#### Autoboot into OS X after you've installed everything

Add the extra option `-e NOPICKER=true`.

Old machines:

```bash
# find your containerID
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
