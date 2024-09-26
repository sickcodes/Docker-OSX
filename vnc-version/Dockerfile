#!/usr/bin/docker
#     ____             __             ____  ______  __
#    / __ \____  _____/ /_____  _____/ __ \/ ___/ |/ /
#   / / / / __ \/ ___/ //_/ _ \/ ___/ / / /\__ \|   / 
#  / /_/ / /_/ / /__/ ,< /  __/ /  / /_/ /___/ /   |  
# /_____/\____/\___/_/|_|\___/_/   \____//____/_/|_|  VNC EDITION
# 
# Title:            Mac on Docker (Docker-OSX) [VNC EDITION]
# Author:           Sick.Codes https://sick.codes/        
# Version:          3.1
# License:          GPLv3+
# 
# All credits for OSX-KVM and the rest at Kholia's repo: https://github.com/kholia/osx-kvm
# OpenCore support go to https://github.com/Leoyzen/KVM-Opencore 
# and https://github.com/thenickdude/KVM-Opencore/
# 
# This Dockerfile automates the installation of Docker-OSX
# It will build a 32GB Mojave Disk, you can change the size using build arguments.
# This file builds on top of the work done by Dhiru Kholia and many others.
#       
#
# Build:
#
#       # write down the password at the end
#       docker build -t docker-osx-vnc .
# 
# Run:
#       
#       docker run --device /dev/kvm --device /dev/snd -p 8888:5999 -p 50922:10022 -d --privileged docker-osx-vnc:latest
#
#
# Optional:
# 
#       -v $PWD/disk.img:/image
# 
# Connect locally (safe):
#
#       VNC Host:     localhost:8888
#
#
# Connect remotely (safe):
#
#
#       # Open a terminal and make an SSH tunnel on port 8888 to your server
#       ssh -N root@111.222.33.44 -L  8888:127.0.0.1:8888
#       
#       # now you can connect like a local
#       VNC Host:     localhost:8888
#
#
# Connect remotely (unsafe):
#
#       VNC Host:     remotehost:8888
#
#
# Security:
#
#       - Think what would happen if someone was in your App Store.
#       - Keep port 8888 closed to external internet traffic, allow local IP's only.
#       - All traffic is insecurely transmitted in plain text, try to use an SSH tunnel.
#       - Everything you write can be sniffed along the way.
#       - VNC Password is only 8 characters.
#
# Show VNC password again:
#
#       docker ps
#       # copy container ID and then 
#       docker exec abc123fgh456 tail vncpasswd_file
#
# VNC Version
# Let's piggyback the other image:

ARG BASE_IMAGE=sickcodes/docker-osx:latest
FROM ${BASE_IMAGE}

MAINTAINER 'https://twitter.com/sickcodes' <https://sick.codes>

USER root

# OPTIONAL: Arch Linux server mirrors for super fast builds
# set RANKMIRRORS to any value other that nothing, e.g. -e RANKMIRRORS=true
ARG RANKMIRRORS
ARG MIRROR_COUNTRY=US
ARG MIRROR_COUNT=10
RUN if [[ "${RANKMIRRORS}" ]]; then { pacman -Sy wget --noconfirm || pacman -Syu wget --noconfirm ; } \
    ; wget -O ./rankmirrors "https://raw.githubusercontent.com/sickcodes/Docker-OSX/master/rankmirrors" \
    ; wget -O- "https://www.archlinux.org/mirrorlist/?country=${MIRROR_COUNTRY:-US}&protocol=https&use_mirror_status=on" \
    | sed -e 's/^#Server/Server/' -e '/^#/d' \
    | head -n "$((${MIRROR_COUNT:-10}+1))" \
    | bash ./rankmirrors --verbose --max-time 5 - > /etc/pacman.d/mirrorlist \
    && tee -a /etc/pacman.d/mirrorlist <<< 'Server = http://mirrors.evowise.com/archlinux/$repo/os/$arch' \
    && tee -a /etc/pacman.d/mirrorlist <<< 'Server = http://mirror.rackspace.com/archlinux/$repo/os/$arch' \
    && tee -a /etc/pacman.d/mirrorlist <<< 'Server = https://mirror.rackspace.com/archlinux/$repo/os/$arch' \
    && cat /etc/pacman.d/mirrorlist ; fi

# Fixes issue with invalid GPG keys: update the archlinux-keyring package to get the latest keys, then remove and regenerate gnupg keys
RUN pacman -Sy archlinux-keyring --noconfirm && rm -rf /etc/pacman.d/gnupg && pacman-key --init && pacman-key --populate

USER arch

RUN yes | sudo pacman -Syyuu --noconfirm \
    && yes | sudo pacman -S tigervnc xterm xorg-xhost xdotool ufw --noconfirm \
    && mkdir -p ${HOME}/.vnc \
    && touch ~/.vnc/config \
    && tee -a ~/.vnc/config <<< 'geometry=1920x1080' \
    && tee -a ~/.vnc/config <<< 'localhost' \
    && tee -a ~/.vnc/config <<< 'alwaysshared'

# this won't work if you have 99 monitors, 98 monitors is fine though
# don't forget to remove the lock file incase you shut down incorrectly or create an image.
RUN printf '\n%s\n' \
'sudo rm -f /tmp/.X99-lock' \
'export DISPLAY=:99' \
'/usr/bin/Xvnc -geometry 1920x1080 -rfbauth "${HOME}/.vnc/passwd" :99 &' > vnc.sh

RUN cat vnc.sh Launch.sh > Launch_custom.sh

RUN chmod +x Launch_custom.sh

RUN tee vncpasswd_file <<< "${VNC_PASSWORD:="$(tr -dc '[:graph:]' </dev/urandom | head -c8)"}"
RUN vncpasswd -f < vncpasswd_file > ${HOME}/.vnc/passwd

RUN chmod 600 ~/.vnc/passwd
RUN printf '\n\n\n\n%s\n%s\n\n\n\n' '===========VNC_PASSWORD========== ' "$(<vncpasswd_file)"

WORKDIR /home/arch/OSX-KVM

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
    ; ./enable-ssh.sh && envsubst < ./Launch_custom.sh | bash
