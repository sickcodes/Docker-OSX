#!/usr/bin/docker
#     ____             __             ____  ______  __
#    / __ \____  _____/ /_____  _____/ __ \/ ___/ |/ /
#   / / / / __ \/ ___/ //_/ _ \/ ___/ / / /\__ \|   / 
#  / /_/ / /_/ / /__/ ,< /  __/ /  / /_/ /___/ /   |  
# /_____/\____/\___/_/|_|\___/_/   \____//____/_/|_|  VNC EDITION
# 
# Title:            Mac on Docker (Docker-OSX) [VNC EDITION]
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
#
# Build:
#
#       # write down the password at the end
#       docker build -t docker-osx-vnc .
# 
# Run:
#       
#       docker run -p 8888:5999 -p 50922:10022 -d --privileged docker-osx-vnc:latest
#
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
# 
# Optional:
#       
#       You can set VNC color depth with -e DEPTH=24, it's not pretty though.
#
#
# VNC Version
# Let's piggyback the other image:

FROM sickcodes/docker-osx:latest

MAINTAINER 'https://sick.codes' <https://sick.codes>

USER arch

RUN sudo pacman -Syu
RUN sudo pacman -S tigervnc xterm xorg-xhost xdotool ufw --noconfirm

RUN mkdir ${HOME}/.vnc

RUN printf '%s\n' \
'xinit &' \
'xterm &' > ~/.vnc/xstartup

# this won't work if you have 99 monitors, 98 monitors is fine though
RUN printf '%s\n%s\n%s\n\n' \
'export DISPLAY=:99' \
'vncserver -kill :99 || true' \
'vncserver -geometry 1920x1080 -depth ${DEPTH} -xstartup ~/.vnc/xstartup :99' > vnc.sh

RUN cat vnc.sh Launch.sh > Launch_custom.sh

RUN chmod +x Launch_custom.sh

RUN tee vncpasswd_file <<< "${VNC_PASSWORD:=$(openssl rand -hex 4)}"
RUN vncpasswd -f < vncpasswd_file > ${HOME}/.vnc/passwd

RUN chmod 600 ~/.vnc/passwd
RUN printf '\n\n\n\n%s\n%s\n\n\n\n' '===========VNC_PASSWORD========== ' "$(<vncpasswd_file)"

ENV DEPTH=24

WORKDIR /home/arch/OSX-KVM
USER arch

CMD ./enable-ssh.sh && envsubst < ./Launch_custom.sh | bash
