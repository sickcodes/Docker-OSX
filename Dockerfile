#/usr/bin/docker
#     ____             __             ____  ______  __
#    / __ \____  _____/ /_____  _____/ __ \/ ___/ |/ /
#   / / / / __ \/ ___/ //_/ _ \/ ___/ / / /\__ \|   / 
#  / /_/ / /_/ / /__/ ,< /  __/ /  / /_/ /___/ /   |  
# /_____/\____/\___/_/|_|\___/_/   \____//____/_/|_|  
# 
# Title:            Mac on Docker (Docker-OSX)
# Author:           Sick.Codes https://sick.codes/        
# Version:          1.0
# License:          GPLv3
# 
# All credits for OSX-KVM and the rest at Kholia's repo: https://github.com/kholia/osx-kvm
# OpenCore support go to https://github.com/Leoyzen/KVM-Opencore 
# and https://github.com/thenickdude/KVM-Opencore/
# 
# This Dockerfile automates the installation of Docker-OSX
# It will build a 32GB Mojave Disk, you can change the size using build arguments.
# This file builds on top of the work done by Dhiru Kholia and many others.
#       
# Build:
#
#       docker build -t docker-osx .
# 
#       docker build -t docker-osx --build-arg VERSION=10.14.6 --build-arg SIZE=200G
#       
# Run:
#       
#       docker run --privileged -v /tmp/.X11-unix:/tmp/.X11-unix docker-osx
#      

FROM archlinux:latest

MAINTAINER 'https://sick.codes' <https://sick.codes>

# change disk size here or add during build, e.g. --build-arg VERSION=10.14.6 --build-arg SIZE=50G
ARG SIZE=32G
ARG VERSION=10.14.6

RUN [[ $(egrep -c '(svm|vmx)' /proc/cpuinfo) -gt 0 ]] || { echo KVM not possible on this host && exit 1; }

WORKDIR /root
RUN tee -a /etc/pacman.conf <<< '[community-testing]'
RUN tee -a /etc/pacman.conf <<< 'Include = /etc/pacman.d/mirrorlist'

RUN pacman -Syu --noconfirm
RUN pacman -S sudo git make automake gcc python go autoconf cmake pkgconf alsa-utils fakeroot --noconfirm
RUN useradd arch
RUN echo 'arch ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers
RUN mkdir /home/arch
RUN chown arch:arch /home/arch

USER arch
WORKDIR /home/arch
RUN git clone https://aur.archlinux.org/yay.git
WORKDIR /home/arch/yay
RUN makepkg -si --noconfirm

WORKDIR /home/arch
RUN git clone https://github.com/corpnewt/gibMacOS.git
WORKDIR /home/arch/gibMacOS
RUN perl -p -i -e 's/print("Succeeded:")/exit()/' ./gibMacOS.command

# this command takes a while!
RUN python gibMacOS.command -v "${VERSION}" || echo Done

RUN sudo pacman -S qemu libvirt dnsmasq virt-manager bridge-utils flex bison ebtables edk2-ovmf --noconfirm
RUN sudo systemctl enable libvirtd.service
RUN sudo systemctl enable virtlogd.service

WORKDIR /home/arch
RUN git clone https://github.com/kholia/OSX-KVM.git

RUN sudo pacman -Syu netctl libvirt-dbus libguestfs --noconfirm

WORKDIR /home/arch/OSX-KVM
RUN sed -i -e 's/usb-mouse/usb-tablet/g' OpenCore-Boot.sh
RUN chmod +x OpenCore-Boot.sh

WORKDIR /home/arch/OSX-KVM
RUN qemu-img convert ${HOME}/gibMacOS/macOS\ Downloads/publicrelease/*/BaseSystem.dmg -O raw ${HOME}/OSX-KVM/BaseSystem.img
RUN qemu-img create -f qcow2 mac_hdd_ng.img "${SIZE}"

RUN perl -p -i -e \
's/-netdev tap,id=net0,ifname=tap0,script=no,downscript=no -device vmxnet3,netdev=net0,id=net0,mac=52:54:00:c9:18:27/-netdev user,id=net0 -device vmxnet3,netdev=net0,id=net0,mac=52:54:00:09:49:17/' \
./OpenCore-Boot.sh

ENV DISPLAY :0.0
ENV USER arch
USER arch
VOLUME ["/tmp/.X11-unix"]

CMD ./OpenCore-Boot.sh

