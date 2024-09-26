#!/usr/bin/docker
#     ____             __             ____  ______  __
#    / __ \____  _____/ /_____  _____/ __ \/ ___/ |/ /
#   / / / / __ \/ ___/ //_/ _ \/ ___/ / / /\__ \|   /
#  / /_/ / /_/ / /__/ ,< /  __/ /  / /_/ /___/ /   |
# /_____/\____/\___/_/|_|\___/_/   \____//____/_/|_|
#
# Title:            Docker-OSX (Mac on Docker)
# Author:           Sick.Codes https://twitter.com/sickcodes
# Version:          6.0
# License:          GPLv3+
# Repository:       https://github.com/sickcodes/Docker-OSX
# Website:          https://sick.codes
#
# All credits for OSX-KVM and the rest at @Kholia's repo: https://github.com/kholia/osx-kvm
# OpenCore support go to https://github.com/Leoyzen/KVM-Opencore
# and https://github.com/thenickdude/KVM-Opencore/
#
# This Dockerfile automates the installation of Docker-OSX
# It will build a 200GB container. You can change the size using build arguments.
# This Dockerfile builds on top of the work done by Dhiru Kholia, and many others.
#
# Build:
#
#       docker build -t docker-osx .
#       docker build -t docker-osx --build-arg VERSION=10.15.5 --build-arg SIZE=200G .
#       docker build -t docker-osx-sonoma --build-arg BRANCH=sonoma --build-arg SHORTNAME=sonoma .
#
# Basic Run:
#
#       docker run --device /dev/kvm --device /dev/snd -v /tmp/.X11-unix:/tmp/.X11-unix -e "DISPLAY=${DISPLAY:-:0.0}" sickcodes/docker-osx:latest
#
# Run with SSH:
#
#       docker run --device /dev/kvm --device /dev/snd -e RAM=6 -p 50922:10022 -v /tmp/.X11-unix:/tmp/.X11-unix -e "DISPLAY=${DISPLAY:-:0.0}" sickcodes/docker-osx:latest
#       # ssh fullname@localhost -p 50922
#
# Optargs:
#
#       -v $PWD/disk.img:/image
#       -e SIZE=200G
#       -e VERSION=10.15.6
#       -e RAM=5
#       -e SMP=4
#       -e CORES=4
#       -e EXTRA=
#       -e INTERNAL_SSH_PORT=10022
#       -e MAC_ADDRESS=
#
# Extra QEMU args:
#
#       docker run ... -e EXTRA="-usb -device usb-host,hostbus=1,hostaddr=8" ...
#       # you will also need to pass the device to the container

FROM archlinux:base-devel
LABEL maintainer='https://twitter.com/sickcodes <https://sick.codes>'

SHELL ["/bin/bash", "-c"]

# change disk size here or add during build, e.g. --build-arg VERSION=10.14.5 --build-arg SIZE=50G
ARG SIZE=200G
ARG PARALLEL_DOWNLOADS=30

# OPTIONAL: Arch Linux server mirrors for super fast builds
# set RANKMIRRORS to any value other that nothing, e.g. -e RANKMIRRORS=true
RUN perl -i -p -e s/^\#Color/Color$'\n'ParallelDownloads\ =\ ${PARALLEL_DOWNLOADS:=30}/g /etc/pacman.conf 

ARG RANKMIRRORS
ARG MIRROR_COUNTRY=US
ARG MIRROR_COUNT=10

RUN tee /etc/pacman.d/mirrorlist <<< 'Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch' \
    && tee -a /etc/pacman.d/mirrorlist <<< 'Server = http://mirror.rackspace.com/archlinux/$repo/os/$arch' \
    && tee -a /etc/pacman.d/mirrorlist <<< 'Server = https://mirror.rackspace.com/archlinux/$repo/os/$arch'

# Fixes issue with invalid GPG keys: update the archlinux-keyring package to get the latest keys, then remove and regenerate gnupg keys
RUN pacman -Sy archlinux-keyring --noconfirm \
    && rm -rf /etc/pacman.d/gnupg \
    && pacman-key --init \
    && pacman-key --populate archlinux

RUN if [[ "${RANKMIRRORS}" ]]; then \
        { pacman -Sy wget --noconfirm || pacman -Syu wget --noconfirm ; } \
        ; wget -O ./rankmirrors "https://raw.githubusercontent.com/sickcodes/Docker-OSX/${BRANCH:=master}/rankmirrors" \
        ; wget -O- "https://www.archlinux.org/mirrorlist/?country=${MIRROR_COUNTRY:-US}&protocol=https&use_mirror_status=on" \
        | sed -e 's/^#Server/Server/' -e '/^#/d' \
        | head -n "$((${MIRROR_COUNT:-10}+1))" \
        | bash ./rankmirrors --verbose --max-time 5 - > /etc/pacman.d/mirrorlist \
        && cat /etc/pacman.d/mirrorlist \
    ; fi

RUN tee -a /etc/pacman.d/gnupg/gpg.conf <<< 'keyserver hkp://keyserver.ubuntu.com' \
    && tee -a /etc/pacman.d/gnupg/gpg.conf <<< 'keyserver hkps://hkps.pool.sks-keyservers.net:443' \
    && tee -a /etc/pacman.d/gnupg/gpg.conf <<< 'keyserver hkp://pgp.mit.edu:11371' \
    && tee -a /etc/pacman.d/gnupg/gpg.conf <<< 'keyserver hkps://keys.openpgp.org' \
    && tee -a /etc/pacman.d/gnupg/gpg.conf <<< 'keyserver hkps://keys.mailvelope.com'

# This fails on hub.docker.com, useful for debugging in cloud
# RUN [[ $(egrep -c '(svm|vmx)' /proc/cpuinfo) -gt 0 ]] || { echo KVM not possible on this host && exit 1; }

# RUN tee -a /etc/pacman.conf <<< '[community-testing]' \
#     && tee -a /etc/pacman.conf <<< 'Include = /etc/pacman.d/mirrorlist'

RUN pacman -Syu git zip vim nano alsa-utils openssh --noconfirm \
    && ln -s /bin/vim /bin/vi \
    && useradd arch -p arch \
    && tee -a /etc/sudoers <<< 'arch ALL=(ALL) NOPASSWD: ALL' \
    && mkdir -p /home/arch \
    && chown arch:arch /home/arch

# allow ssh to container
RUN mkdir -p -m 700 /root/.ssh

WORKDIR /root/.ssh
RUN touch authorized_keys \
    && chmod 644 authorized_keys

WORKDIR /etc/ssh
RUN tee -a sshd_config <<< 'AllowTcpForwarding yes' \
    && tee -a sshd_config <<< 'PermitTunnel yes' \
    && tee -a sshd_config <<< 'X11Forwarding yes' \
    && tee -a sshd_config <<< 'PasswordAuthentication yes' \
    && tee -a sshd_config <<< 'PermitRootLogin yes' \
    && tee -a sshd_config <<< 'PubkeyAuthentication yes' \
    && tee -a sshd_config <<< 'HostKey /etc/ssh/ssh_host_rsa_key' \
    && tee -a sshd_config <<< 'HostKey /etc/ssh/ssh_host_ecdsa_key' \
    && tee -a sshd_config <<< 'HostKey /etc/ssh/ssh_host_ed25519_key'

USER arch

# download OSX-KVM for the submodules
RUN git clone --recurse-submodules --depth 1 https://github.com/kholia/OSX-KVM.git /home/arch/OSX-KVM

# enable ssh
# docker exec .... ./enable-ssh.sh
USER arch

WORKDIR /home/arch/OSX-KVM

RUN touch enable-ssh.sh \
    && chmod +x ./enable-ssh.sh \
    && tee -a enable-ssh.sh <<< '[[ -f /etc/ssh/ssh_host_rsa_key ]] || \' \
    && tee -a enable-ssh.sh <<< '[[ -f /etc/ssh/ssh_host_ed25519_key ]] || \' \
    && tee -a enable-ssh.sh <<< '[[ -f /etc/ssh/ssh_host_ed25519_key ]] || \' \
    && tee -a enable-ssh.sh <<< 'sudo /usr/bin/ssh-keygen -A' \
    && tee -a enable-ssh.sh <<< 'nohup sudo /usr/bin/sshd -D &'

# QEMU CONFIGURATOR
# set optional ram at runtime -e RAM=16
# set optional cores at runtime -e SMP=4 -e CORES=2
# add any additional commands in QEMU cli format -e EXTRA="-usb -device usb-host,hostbus=1,hostaddr=8"

# default env vars, RUNTIME ONLY, not for editing in build time.

# RUN yes | sudo pacman -Syu qemu libvirt dnsmasq virt-manager bridge-utils edk2-ovmf netctl libvirt-dbus --overwrite --noconfirm

RUN yes | sudo pacman -Syu bc qemu-desktop libvirt dnsmasq virt-manager bridge-utils openresolv jack2 ebtables edk2-ovmf netctl libvirt-dbus wget scrot --overwrite --noconfirm \
    && yes | sudo pacman -Scc

WORKDIR /home/arch/OSX-KVM

# fix invalid signature on old libguestfs
ARG SIGLEVEL=Never

RUN sudo tee -a /etc/pacman.conf <<< "SigLevel = ${SIGLEVEL}" \
    && sudo tee -a /etc/pacman.conf <<< 'RemoteFileSigLevel = Optional' \
    && sudo sed -i -e 's/^\#RemoteFileSigLevel/RemoteFileSigLevel/g' /etc/pacman.conf

ARG LINUX=true

# required to use libguestfs inside a docker container, to create bootdisks for docker-osx on-the-fly
# reminder this is what makes :naked image larger than expected
RUN if [[ "${LINUX}" == true ]]; then \
        sudo pacman -Syu linux linux-headers archlinux-keyring guestfs-tools mkinitcpio pcre pcre2 --noconfirm \
        && libguestfs-test-tool \
        && rm -rf /var/tmp/.guestfs-* \
        && yes | sudo pacman -Scc \
    ; fi

# optional --build-arg to change branches for testing
ARG BRANCH=master
ARG REPO='https://github.com/sickcodes/Docker-OSX.git'
RUN git clone --recurse-submodules --depth 1 --branch "${BRANCH:=master}" "${REPO:=https://github.com/sickcodes/Docker-OSX.git}"

RUN touch Launch.sh \
    && chmod +x ./Launch.sh \
    && tee -a Launch.sh <<< '#!/bin/bash' \
    && tee -a Launch.sh <<< 'set -eux' \
    && tee -a Launch.sh <<< 'sudo chown    $(id -u):$(id -g) /dev/kvm 2>/dev/null || true' \
    && tee -a Launch.sh <<< 'sudo chown -R $(id -u):$(id -g) /dev/snd 2>/dev/null || true' \
    && tee -a Launch.sh <<< '[[ "${RAM}" = max ]] && export RAM="$(("$(head -n1 /proc/meminfo | tr -dc "[:digit:]") / 1000000"))"' \
    && tee -a Launch.sh <<< '[[ "${RAM}" = half ]] && export RAM="$(("$(head -n1 /proc/meminfo | tr -dc "[:digit:]") / 2000000"))"' \
    && tee -a Launch.sh <<< 'sudo chown -R $(id -u):$(id -g) /dev/snd 2>/dev/null || true' \
    && tee -a Launch.sh <<< 'exec qemu-system-x86_64 -m ${RAM:-4}000 \' \
    && tee -a Launch.sh <<< '-cpu ${CPU:-Penryn},${CPUID_FLAGS:-vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on,+ssse3,+sse4.2,+popcnt,+avx,+aes,+xsave,+xsaveopt,check,}${BOOT_ARGS} \' \
    && tee -a Launch.sh <<< '-machine q35,${KVM-"accel=kvm:tcg"} \' \
    && tee -a Launch.sh <<< '-smp ${CPU_STRING:-${SMP:-4},cores=${CORES:-4}} \' \
    && tee -a Launch.sh <<< '-device qemu-xhci,id=xhci \' \
    && tee -a Launch.sh <<< '-device usb-kbd,bus=xhci.0 -device usb-tablet,bus=xhci.0 \' \
    && tee -a Launch.sh <<< '-device isa-applesmc,osk=ourhardworkbythesewordsguardedpleasedontsteal\(c\)AppleComputerInc \' \
    && tee -a Launch.sh <<< '-drive if=pflash,format=raw,readonly=on,file=/home/arch/OSX-KVM/OVMF_CODE.fd \' \
    && tee -a Launch.sh <<< '-drive if=pflash,format=raw,file=/home/arch/OSX-KVM/OVMF_VARS-1024x768.fd \' \
    && tee -a Launch.sh <<< '-smbios type=2 \' \
    && tee -a Launch.sh <<< '-audiodev ${AUDIO_DRIVER:-alsa},id=hda -device ich9-intel-hda -device hda-duplex,audiodev=hda \' \
    && tee -a Launch.sh <<< '-device ich9-ahci,id=sata \' \
    && tee -a Launch.sh <<< '-drive id=OpenCoreBoot,if=none,snapshot=on,format=qcow2,file=${BOOTDISK:-/home/arch/OSX-KVM/OpenCore/OpenCore.qcow2} \' \
    && tee -a Launch.sh <<< '-device ide-hd,bus=sata.2,drive=OpenCoreBoot \' \
    && tee -a Launch.sh <<< '-device ide-hd,bus=sata.3,drive=InstallMedia \' \
    && tee -a Launch.sh <<< '-drive id=InstallMedia,if=none,file=/home/arch/OSX-KVM/BaseSystem.img,format=${BASESYSTEM_FORMAT:-qcow2} \' \
    && tee -a Launch.sh <<< '-drive id=MacHDD,if=none,file=${IMAGE_PATH:-/home/arch/OSX-KVM/mac_hdd_ng.img},format=${IMAGE_FORMAT:-qcow2} \' \
    && tee -a Launch.sh <<< '-device ide-hd,bus=sata.4,drive=MacHDD \' \
    && tee -a Launch.sh <<< '-netdev user,id=net0,hostfwd=tcp::${INTERNAL_SSH_PORT:-10022}-:22,hostfwd=tcp::${SCREEN_SHARE_PORT:-5900}-:5900,${ADDITIONAL_PORTS} \' \
    && tee -a Launch.sh <<< '-device ${NETWORKING:-vmxnet3},netdev=net0,id=net0,mac=${MAC_ADDRESS:-52:54:00:09:49:17} \' \
    && tee -a Launch.sh <<< '-monitor stdio \' \
    && tee -a Launch.sh <<< '-boot menu=on \' \
    && tee -a Launch.sh <<< '-vga vmware \' \
    && tee -a Launch.sh <<< '${EXTRA:-}'

# docker exec containerid mv ./Launch-nopicker.sh ./Launch.sh
# This is now a legacy command.
# You can use -e BOOTDISK=/bootdisk with -v ./bootdisk.img:/bootdisk

### LEGACY CODE
RUN grep -v InstallMedia ./Launch.sh > ./Launch-nopicker.sh \
    && chmod +x ./Launch-nopicker.sh \
    && sed -i -e s/OpenCore\.qcow2/OpenCore\-nopicker\.qcow2/ ./Launch-nopicker.sh
###

USER arch

ENV USER=arch

# These are hardcoded serials for non-iMessage related research
# Overwritten by using GENERATE_UNIQUE=true
# Upstream removed nopicker, so we are adding it back in, at build time
# Once again, this is just for the Docker build so there is a default nopicker image there

# libguestfs verbose
ENV LIBGUESTFS_DEBUG=1
ENV LIBGUESTFS_TRACE=1

ARG STOCK_DEVICE_MODEL=iMacPro1,1
ARG STOCK_SERIAL=C02TM2ZBHX87
ARG STOCK_BOARD_SERIAL=C02717306J9JG361M
ARG STOCK_UUID=007076A6-F2A2-4461-BBE5-BAD019F8025A
ARG STOCK_MAC_ADDRESS=00:0A:27:00:00:00
ARG STOCK_WIDTH=1920
ARG STOCK_HEIGHT=1080
ARG STOCK_MASTER_PLIST_URL=https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-custom.plist
ARG STOCK_MASTER_PLIST_URL_NOPICKER=https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-nopicker-custom.plist
ARG STOCK_BOOTDISK=/home/arch/OSX-KVM/OpenCore/OpenCore.qcow2
ARG STOCK_BOOTDISK_NOPICKER=/home/arch/OSX-KVM/OpenCore/OpenCore-nopicker.qcow2

RUN ./Docker-OSX/osx-serial-generator/generate-specific-bootdisk.sh \
    --master-plist-url="${STOCK_MASTER_PLIST_URL}" \
    --model "${STOCK_DEVICE_MODEL}" \
    --serial "${STOCK_SERIAL}" \
    --board-serial "${STOCK_BOARD_SERIAL}" \
    --uuid "${STOCK_UUID}" \
    --mac-address "${STOCK_MAC_ADDRESS}" \
    --width "${STOCK_WIDTH}" \
    --height "${STOCK_HEIGHT}" \
    --output-bootdisk "${STOCK_BOOTDISK}" || exit 1 \
    ; rm -rf /var/tmp/.guestfs-*

RUN ./Docker-OSX/osx-serial-generator/generate-specific-bootdisk.sh \
    --master-plist-url="${STOCK_MASTER_PLIST_URL_NOPICKER}" \
    --model "${STOCK_DEVICE_MODEL}" \
    --serial "${STOCK_SERIAL}" \
    --board-serial "${STOCK_BOARD_SERIAL}" \
    --uuid "${STOCK_UUID}" \
    --mac-address "${STOCK_MAC_ADDRESS}" \
    --width "${STOCK_WIDTH}" \
    --height "${STOCK_HEIGHT}" \
    --output-bootdisk "${STOCK_BOOTDISK_NOPICKER}" || exit 1 \
    ; rm -rf /var/tmp/.guestfs-*

### symlink the old directory as upstream has renamed a directory. Symlinking purely for backwards compatability!
RUN ln -s /home/arch/OSX-KVM/OpenCore /home/arch/OSX-KVM/OpenCore-Catalina || true
####

#### SPECIAL RUNTIME ARGUMENTS BELOW
# env -e ADDITIONAL_PORTS with a comma
# for example, -e ADDITIONAL_PORTS=hostfwd=tcp::23-:23,
ENV ADDITIONAL_PORTS=

# since the Makefile uses raw, and raw uses the full disk amount
# we want to use a compressed qcow2
# ENV BASESYSTEM_FORMAT=raw
ENV BASESYSTEM_FORMAT=qcow2

# add additional QEMU boot arguments
ENV BOOT_ARGS=

ENV BOOTDISK=

# edit the CPU that is being emulated
ENV CPU=Penryn
ENV CPUID_FLAGS='vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on,+ssse3,+sse4.2,+popcnt,+avx,+aes,+xsave,+xsaveopt,check,'

ENV DISPLAY=:0.0

# Deprecated
ENV ENV=/env

# Boolean for generating a bootdisk with new random serials.
ENV GENERATE_UNIQUE=false

# Boolean for generating a bootdisk with specific serials.
ENV GENERATE_SPECIFIC=false

ENV IMAGE_PATH=/home/arch/OSX-KVM/mac_hdd_ng.img
ENV IMAGE_FORMAT=qcow2

ENV KVM='accel=kvm:tcg'

ENV MASTER_PLIST_URL="https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-custom.plist"

# ENV NETWORKING=e1000-82545em
ENV NETWORKING=vmxnet3

# boolean for skipping the disk selection menu at in the boot process
ENV NOPICKER=false

# dynamic RAM options for runtime
ENV RAM=4
# ENV RAM=max
# ENV RAM=half

# The x and y coordinates for resolution.
# Must be used with either -e GENERATE_UNIQUE=true or -e GENERATE_SPECIFIC=true.
ENV WIDTH=1920
ENV HEIGHT=1080

VOLUME ["/tmp/.X11-unix"]

# check if /image is a disk image or a directory. This allows you to optionally use -v disk.img:/image
# NOPICKER is used to skip the disk selection screen
# GENERATE_UNIQUE is used to generate serial numbers on boot.
# /env is a file that you can generate and save using -v source.sh:/env
# the env file is a file that you can carry to the next container which will supply the serials numbers.
# GENERATE_SPECIFIC is used to either accept the env serial numbers OR you can supply using:
    # -e DEVICE_MODEL="iMacPro1,1" \
    # -e SERIAL="C02TW0WAHX87" \
    # -e BOARD_SERIAL="C027251024NJG36UE" \
    # -e UUID="5CCB366D-9118-4C61-A00A-E5BAF3BED451" \
    # -e MAC_ADDRESS="A8:5C:2C:9A:46:2F" \

# the output will be /bootdisk.
# /bootdisk is a useful persistent place to store the 15Mb serial number bootdisk.

# if you don't set any of the above:
# the default serial numbers are already contained in ./OpenCore/OpenCore.qcow2
# And the default serial numbers

# DMCA compliant download process
# If BaseSystem.img does not exist, download ${SHORTNAME}

# shortname default is catalina, which means :latest is catalina
ENV SHORTNAME=sonoma

ENV BASESYSTEM_IMAGE=BaseSystem.img

CMD ! [[ -e "${BASESYSTEM_IMAGE:-BaseSystem.img}" ]] \
        && printf '%s\n' "No BaseSystem.img available, downloading ${SHORTNAME}" \
        && make \
        && qemu-img convert BaseSystem.dmg -O qcow2 -p -c ${BASESYSTEM_IMAGE:-BaseSystem.img} \
        && rm ./BaseSystem.dmg \
    ; sudo touch /dev/kvm /dev/snd "${IMAGE_PATH}" "${BOOTDISK}" "${ENV}" 2>/dev/null || true \
    ; sudo chown -R $(id -u):$(id -g) /dev/kvm /dev/snd "${IMAGE_PATH}" "${BOOTDISK}" "${ENV}" 2>/dev/null || true \
    ; [[ "${NOPICKER}" == true ]] && { \
        sed -i '/^.*InstallMedia.*/d' Launch.sh \
        && export BOOTDISK="${BOOTDISK:=/home/arch/OSX-KVM/OpenCore/OpenCore-nopicker.qcow2}" \
    ; } \
    || export BOOTDISK="${BOOTDISK:=/home/arch/OSX-KVM/OpenCore/OpenCore.qcow2}" \
    ; [[ "${GENERATE_UNIQUE}" == true ]] && { \
        ./Docker-OSX/osx-serial-generator/generate-unique-machine-values.sh \
            --master-plist-url="${MASTER_PLIST_URL}" \
            --count 1 \
            --tsv ./serial.tsv \
            --bootdisks \
            --width "${WIDTH:-1920}" \
            --height "${HEIGHT:-1080}" \
            --output-bootdisk "${BOOTDISK:=/home/arch/OSX-KVM/OpenCore/OpenCore.qcow2}" \
            --output-env "${ENV:=/env}" \
    || exit 1 ; } \
    ; [[ "${GENERATE_SPECIFIC}" == true ]] && { \
            source "${ENV:=/env}" 2>/dev/null \
            ; ./Docker-OSX/osx-serial-generator/generate-specific-bootdisk.sh \
            --master-plist-url="${MASTER_PLIST_URL}" \
            --model "${DEVICE_MODEL}" \
            --serial "${SERIAL}" \
            --board-serial "${BOARD_SERIAL}" \
            --uuid "${UUID}" \
            --mac-address "${MAC_ADDRESS}" \
            --width "${WIDTH:-1920}" \
            --height "${HEIGHT:-1080}" \
            --output-bootdisk "${BOOTDISK:=/home/arch/OSX-KVM/OpenCore/OpenCore.qcow2}" \
    || exit 1 ; } \
    ; ./enable-ssh.sh && /bin/bash -c ./Launch.sh

# virt-manager mode: eta son
# CMD virsh define <(envsubst < Docker-OSX.xml) && virt-manager || virt-manager
# CMD virsh define <(envsubst < macOS-libvirt-Catalina.xml) && virt-manager || virt-manager
