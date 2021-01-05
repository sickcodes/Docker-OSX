#!/usr/bin/docker
#     ____             __             ____  ______  __
#    / __ \____  _____/ /_____  _____/ __ \/ ___/ |/ /
#   / / / / __ \/ ___/ //_/ _ \/ ___/ / / /\__ \|   / 
#  / /_/ / /_/ / /__/ ,< /  __/ /  / /_/ /___/ /   |  
# /_____/\____/\___/_/|_|\___/_/   \____//____/_/|_|  
# 
# Repo:             https://github.com/sickcodes/Docker-OSX/
# Title:            Mac on Docker (Docker-OSX)
# Author:           Sick.Codes https://sick.codes/ 
# Version:          2.6
# License:          GPLv3+
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
#       
# Basic Run:
#       
#       docker run --device /dev/kvm --device /dev/snd -v /tmp/.X11-unix:/tmp/.X11-unix -e "DISPLAY=${DISPLAY:-:0.0}" sickcodes/docker-osx:latest
#
#
# Run with SSH:
# 
# 
#       docker run --device /dev/kvm --device /dev/snd -e RAM=6 -p 50922:10022 -v /tmp/.X11-unix:/tmp/.X11-unix -e "DISPLAY=${DISPLAY:-:0.0}" sickcodes/docker-osx:latest
#       # ssh fullname@localhost -p 50922
# 
# Optargs:
#       
#       SIZE=200G
#       VERSION=10.15.6
#       ENV RAM=5
#       ENV SMP=4
#       ENV CORES=4
#       ENV EXTRA=
#       ENV INTERNAL_SSH_PORT=10022
#
# Extra QEMU args:
#
#       docker run ... -e EXTRA="-usb -device usb-host,hostbus=1,hostaddr=8" ...
#       # you will also need to pass the device to the container
#

FROM archlinux:latest

MAINTAINER 'https://sick.codes' <https://sick.codes>

# change disk size here or add during build, e.g. --build-arg VERSION=10.14.5 --build-arg SIZE=50G
ARG SIZE=200G
ARG VERSION=10.15.6

ARG RANKMIRRORS=no
ARG MIRROR_COUNTRY=US
ARG MIRROR_COUNT=10

# Arch Linux server mirrors for faster builds
RUN if [[ "${RANKMIRRORS}" = yes ]]; then { pacman -Sy wget --noconfirm || pacman -Syu wget --noconfirm ; } \
    ; wget -O ./rankmirrors "https://raw.githubusercontent.com/sickcodes/Docker-OSX/master/rankmirrors" \
    ; wget -O- "https://www.archlinux.org/mirrorlist/?country=${MIRROR_COUNTRY:-US}&protocol=https&use_mirror_status=on" \
    | sed -e 's/^#Server/Server/' -e '/^#/d' \
    | head -n "$((${MIRROR_COUNT:-10}+1))" \
    | bash ./rankmirrors --verbose --max-time 5 - > /etc/pacman.d/mirrorlist \
    && tee -a /etc/pacman.d/mirrorlist <<< 'Server = http://mirrors.evowise.com/archlinux/$repo/os/$arch' \
    && tee -a /etc/pacman.d/mirrorlist <<< 'Server = http://mirror.rackspace.com/archlinux/$repo/os/$arch' \
    && tee -a /etc/pacman.d/mirrorlist <<< 'Server = https://mirror.rackspace.com/archlinux/$repo/os/$arch' \
    && cat /etc/pacman.d/mirrorlist; fi

# This fails on hub.docker.com, useful for debugging in cloud
# RUN [[ $(egrep -c '(svm|vmx)' /proc/cpuinfo) -gt 0 ]] || { echo KVM not possible on this host && exit 1; }

RUN tee -a /etc/pacman.conf <<< '[community-testing]' \
    && tee -a /etc/pacman.conf <<< 'Include = /etc/pacman.d/mirrorlist'

RUN pacman -Syu --noconfirm \
    && pacman -S sudo git make automake gcc python go autoconf cmake pkgconf alsa-utils fakeroot vim nano --noconfirm \
    && yes | pacman -Scc \
    && ln -s /bin/vim /bin/vi \
    && useradd arch -p arch \
    && tee -a /etc/sudoers <<< 'arch ALL=(ALL) NOPASSWD: ALL' \
    && mkdir /home/arch \
    && chown arch:arch /home/arch

# allow ssh to container
RUN mkdir -m 700 /root/.ssh

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

# download OSX-KVM
RUN git clone --depth 1 https://github.com/kholia/OSX-KVM.git /home/arch/OSX-KVM

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

RUN sudo pacman -Syu qemu libvirt dnsmasq virt-manager bridge-utils flex bison ebtables edk2-ovmf netctl libvirt-dbus libguestfs --noconfirm && yes | sudo pacman -Scc
# RUN sudo systemctl enable libvirtd.service
# RUN sudo systemctl enable virtlogd.service

RUN git clone --depth 1 https://github.com/corpnewt/gibMacOS.git /home/arch/OSX-KVM/gibMacOS

WORKDIR /home/arch/OSX-KVM/gibMacOS

# this command takes a while!
RUN perl -p -i -e 's/print("Succeeded:")/exit()/' ./gibMacOS.command \
	&& { python gibMacOS.command -v "${VERSION}" -d || echo Done; } \
	&& qemu-img convert /home/arch/OSX-KVM/gibMacOS/macOS\ Downloads/publicrelease/*/BaseSystem.dmg -O qcow2 -p -c /home/arch/OSX-KVM/BaseSystem.img \
	&& qemu-img create -f qcow2 /home/arch/OSX-KVM/mac_hdd_ng.img "${SIZE}" \
	&& rm /home/arch/OSX-KVM/gibMacOS/macOS\ Downloads/publicrelease/*/BaseSystem.dmg

# > Launch.sh
# > Docker-OSX.xml

WORKDIR /home/arch/OSX-KVM

RUN touch Launch.sh \
    && chmod +x ./Launch.sh \
    && tee -a Launch.sh <<< '#!/bin/sh' \
    && tee -a Launch.sh <<< 'set -eu' \
    && tee -a Launch.sh <<< 'sudo chown    $(id -u):$(id -g) /dev/kvm 2>/dev/null || true' \
    && tee -a Launch.sh <<< 'sudo chown -R $(id -u):$(id -g) /dev/snd 2>/dev/null || true' \
    && tee -a Launch.sh <<< 'exec qemu-system-x86_64 -m ${RAM:-8}000 \' \
    && tee -a Launch.sh <<< '-cpu Penryn,vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on,+pcid,+ssse3,+sse4.2,+popcnt,+avx,+aes,+xsave,+xsaveopt,check \' \
    && tee -a Launch.sh <<< '-machine q35,accel=kvm:tcg \' \
    && tee -a Launch.sh <<< '-smp ${SMP:-4},cores=${CORES:-4} \' \
    && tee -a Launch.sh <<< '-usb -device usb-kbd -device usb-tablet \' \
    && tee -a Launch.sh <<< '-device isa-applesmc,osk=ourhardworkbythesewordsguardedpleasedontsteal\(c\)AppleComputerInc \' \
    && tee -a Launch.sh <<< '-drive if=pflash,format=raw,readonly,file=/home/arch/OSX-KVM/OVMF_CODE.fd \' \
    && tee -a Launch.sh <<< '-drive if=pflash,format=raw,file=/home/arch/OSX-KVM/OVMF_VARS-1024x768.fd \' \
    && tee -a Launch.sh <<< '-smbios type=2 \' \
    && tee -a Launch.sh <<< '-audiodev ${AUDIO_DRIVER:-alsa},id=hda -device ich9-intel-hda -device hda-duplex,audiodev=hda \' \
    && tee -a Launch.sh <<< '-device ich9-ahci,id=sata \' \
    && tee -a Launch.sh <<< '-drive id=OpenCoreBoot,if=none,snapshot=on,format=qcow2,file=/home/arch/OSX-KVM/OpenCore-Catalina/OpenCore.qcow2 \' \
    && tee -a Launch.sh <<< '-device ide-hd,bus=sata.2,drive=OpenCoreBoot \' \
    && tee -a Launch.sh <<< '-device ide-hd,bus=sata.3,drive=InstallMedia \' \
    && tee -a Launch.sh <<< '-drive id=InstallMedia,if=none,file=/home/arch/OSX-KVM/BaseSystem.img,format=qcow2 \' \
    && tee -a Launch.sh <<< '-drive id=MacHDD,if=none,file=/home/arch/OSX-KVM/mac_hdd_ng.img,format=qcow2 \' \
    && tee -a Launch.sh <<< '-device ide-hd,bus=sata.4,drive=MacHDD \' \
    && tee -a Launch.sh <<< '-netdev user,id=net0,hostfwd=tcp::${INTERNAL_SSH_PORT:-10022}-:22,hostfwd=tcp::${SCREEN_SHARE_PORT:-5900}-:5900, -device e1000-82545em,netdev=net0,id=net0,mac=52:54:00:09:49:17 \' \
    && tee -a Launch.sh <<< '-monitor stdio \' \
    && tee -a Launch.sh <<< '-vga vmware \' \
    && tee -a Launch.sh <<< '${EXTRA:-}'

# docker exec containerid mv ./Launch-nopicker.sh ./Launch.sh
RUN grep -v InstallMedia ./Launch.sh > ./Launch-nopicker.sh \
    && chmod +x ./Launch-nopicker.sh \
    && sed -i -e s/OpenCore\.qcow2/OpenCore\-nopicker\.qcow2/ ./Launch-nopicker.sh

ENV USER arch

ENV DISPLAY=:0.0

USER arch

VOLUME ["/tmp/.X11-unix"]

CMD ./enable-ssh.sh && envsubst < ./Launch.sh | bash

# virt-manager mode: eta son
# CMD virsh define <(envsubst < Docker-OSX.xml) && virt-manager || virt-manager
# CMD virsh define <(envsubst < macOS-libvirt-Catalina.xml) && virt-manager || virt-manager
