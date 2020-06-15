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
# Version:          2.0
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
#       docker run --privileged -e "DISPLAY=${DISPLAY:-:0.0}" -v /tmp/.X11-unix:/tmp/.X11-unix docker-osx
#
#
# Run with SSH:
# 
# 
#       docker run -e RAM=6 --privileged -p 50922:10022 -e "DISPLAY=${DISPLAY:-:0.0}" -v /tmp/.X11-unix:/tmp/.X11-unix docker-osx:latest
#       # ssh fullname@localhost -p 50922
# 
# Optargs:
#       
#       SIZE=200G
#       VERSION=10.15.5
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
#
# Other permissions:
#
#       docker run --privileged --net host -e "DISPLAY=${DISPLAY:-:0.0}" -e RAM=6 --cap-add=ALL -v /tmp/.X11-unix:/tmp/.X11-unix -v /dev:/dev -v /lib/modules:/lib/modules  -v /var/run/libvirt/libvirt-sock:/var/run/libvirt/libvirt-sock docker-osx:latest

FROM archlinux:latest

MAINTAINER 'https://sick.codes' <https://sick.codes>

# change disk size here or add during build, e.g. --build-arg VERSION=10.14.5 --build-arg SIZE=50G
ARG SIZE=200G
ARG VERSION=10.15.5

# This fails on hub.docker.com, useful for debugging in cloud
# RUN [[ $(egrep -c '(svm|vmx)' /proc/cpuinfo) -gt 0 ]] || { echo KVM not possible on this host && exit 1; }

WORKDIR /root
RUN tee -a /etc/pacman.conf <<< '[community-testing]'
RUN tee -a /etc/pacman.conf <<< 'Include = /etc/pacman.d/mirrorlist'

RUN pacman -Syu --noconfirm
RUN pacman -S sudo git make automake gcc python go autoconf cmake pkgconf alsa-utils fakeroot --noconfirm
RUN useradd arch -p arch
RUN tee -a /etc/sudoers <<< 'arch ALL=(ALL) NOPASSWD: ALL'
RUN mkdir /home/arch
RUN chown arch:arch /home/arch

# allow ssh to container
WORKDIR /root
RUN mkdir .ssh
RUN chmod 700 .ssh

WORKDIR /root/.ssh
RUN touch authorized_keys
RUN chmod 644 authorized_keys

WORKDIR /etc/ssh
RUN tee -a sshd_config <<< 'AllowTcpForwarding yes'
RUN tee -a sshd_config <<< 'PermitTunnel yes'
RUN tee -a sshd_config <<< 'X11Forwarding yes'
RUN tee -a sshd_config <<< 'PasswordAuthentication yes'
RUN tee -a sshd_config <<< 'PermitRootLogin yes'
RUN tee -a sshd_config <<< 'PubkeyAuthentication yes'
RUN tee -a sshd_config <<< 'HostKey /etc/ssh/ssh_host_rsa_key'
RUN tee -a sshd_config <<< 'HostKey /etc/ssh/ssh_host_ecdsa_key'
RUN tee -a sshd_config <<< 'HostKey /etc/ssh/ssh_host_ed25519_key'

USER arch
WORKDIR /home/arch
RUN git clone https://github.com/corpnewt/gibMacOS.git
WORKDIR /home/arch/gibMacOS
RUN perl -p -i -e 's/print("Succeeded:")/exit()/' ./gibMacOS.command

# this command takes a while!
RUN python gibMacOS.command -v "${VERSION}" -d || echo Done

RUN sudo pacman -Syu qemu libvirt dnsmasq virt-manager bridge-utils flex bison ebtables edk2-ovmf netctl libvirt-dbus libguestfs --noconfirm
# RUN sudo systemctl enable libvirtd.service
# RUN sudo systemctl enable virtlogd.service

# download OSX-KVM
WORKDIR /home/arch
RUN git clone https://github.com/kholia/OSX-KVM.git

# create disk
WORKDIR /home/arch/OSX-KVM
RUN qemu-img convert ${HOME}/gibMacOS/macOS\ Downloads/publicrelease/*/BaseSystem.dmg -O raw ${HOME}/OSX-KVM/BaseSystem.img
RUN qemu-img create -f qcow2 mac_hdd_ng.img "${SIZE}"

# enable ssh
# docker exec .... ./enable-ssh.sh
USER arch
RUN touch enable-ssh.sh
RUN chmod +x ./enable-ssh.sh
RUN tee -a enable-ssh.sh <<< '[[ -f /etc/ssh/ssh_host_rsa_key ]] || \'
RUN tee -a enable-ssh.sh <<< '[[ -f /etc/ssh/ssh_host_ed25519_key ]] || \'
RUN tee -a enable-ssh.sh <<< '[[ -f /etc/ssh/ssh_host_ed25519_key ]] || \'
RUN tee -a enable-ssh.sh <<< 'sudo /usr/bin/ssh-keygen -A'
RUN tee -a enable-ssh.sh <<< 'nohup sudo /usr/bin/sshd -D &'

# QEMU CONFIGURATOR
# set optional ram at runtime -e RAM=16
# set optional cores at runtime -e SMP=4 -e CORES=2
# add any additional commands in QEMU cli format -e EXTRA="-usb -device usb-host,hostbus=1,hostaddr=8"

# default env vars, RUNTIME ONLY, not for editing in build time.

# > Launch.sh
# > Docker-OSX.xml

RUN touch Launch.sh
RUN chmod +x ./Launch.sh
RUN tee -a Launch.sh <<< 'qemu-system-x86_64 -enable-kvm -m ${RAM}000 \'
RUN tee -a Launch.sh <<< '-cpu Penryn,kvm=on,vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on,+pcid,+ssse3,+sse4.2,+popcnt,+avx,+aes,+xsave,+xsaveopt,check \'
RUN tee -a Launch.sh <<< '-machine q35 \'
RUN tee -a Launch.sh <<< '-smp ${SMP},cores=${CORES} \'
RUN tee -a Launch.sh <<< '-usb -device usb-kbd -device usb-tablet \'
RUN tee -a Launch.sh <<< '-device isa-applesmc,osk=ourhardworkbythesewordsguardedpleasedontsteal\(c\)AppleComputerInc \'
RUN tee -a Launch.sh <<< '-drive if=pflash,format=raw,readonly,file=/home/arch/OSX-KVM/OVMF_CODE.fd \'
RUN tee -a Launch.sh <<< '-drive if=pflash,format=raw,file=./OVMF_VARS-1024x768.fd \'
RUN tee -a Launch.sh <<< '-smbios type=2 \'
RUN tee -a Launch.sh <<< '-device ich9-intel-hda -device hda-duplex \'
RUN tee -a Launch.sh <<< '-device ich9-ahci,id=sata \'
RUN tee -a Launch.sh <<< '-drive id=OpenCoreBoot,if=none,snapshot=on,format=qcow2,file=/home/arch/OSX-KVM/OpenCore-Catalina/OpenCore.qcow2 \'
RUN tee -a Launch.sh <<< '-device ide-hd,bus=sata.2,drive=OpenCoreBoot \'
RUN tee -a Launch.sh <<< '-device ide-hd,bus=sata.3,drive=InstallMedia \'
RUN tee -a Launch.sh <<< '-drive id=InstallMedia,if=none,file=BaseSystem.img,format=raw \'
RUN tee -a Launch.sh <<< '-drive id=MacHDD,if=none,file=/home/arch/OSX-KVM/mac_hdd_ng.img,format=qcow2 \'
RUN tee -a Launch.sh <<< '-device ide-hd,bus=sata.4,drive=MacHDD \'
RUN tee -a Launch.sh <<< '-netdev user,id=net0,hostfwd=tcp::${INTERNAL_SSH_PORT}-:22, -device e1000-82545em,netdev=net0,id=net0,mac=52:54:00:09:49:17 \'
RUN tee -a Launch.sh <<< '-monitor stdio \'
RUN tee -a Launch.sh <<< '-vga vmware \'
RUN tee -a Launch.sh <<< '${EXTRA}'

ENV USER arch

ENV RAM=5
ENV SMP=4
ENV CORES=4
ENV EXTRA=
ENV INTERNAL_SSH_PORT=10022

# if you're in the shell, export these variables to use then in envsubst
# export RAM=5
# export SMP=4
# export CORES=4
# export EXTRA=
# export INTERNAL_SSH_PORT=10022

USER arch
VOLUME ["/tmp/.X11-unix"]

CMD ./enable-ssh.sh && envsubst < ./Launch.sh | bash

# virt-manager mode: eta son
# CMD virsh define <(envsubst < Docker-OSX.xml) && virt-manager || virt-manager
# CMD virsh define <(envsubst < macOS-libvirt-Catalina.xml) && virt-manager || virt-manager


# all perms
# 
