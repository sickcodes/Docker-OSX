#!/usr/bin/docker
#
# This Dockerfile is to be consumed with the docker_osx helm templates. It consumes the
#  Ubuntu image so that OpenCore.qcow2 can be re-generated (which happens in Kube itself),
#  not to mention that OSX-KVM was written for Ubuntu. This was not designed to be run in Docker
#  by itself.. very well anyway.
#

FROM ubuntu:21.04

SHELL ["/bin/bash", "-c"]

# this has to match .Values.image.userName in helm template
ARG USER=ubuntu
# this installs the kvm linux kernel in the docker container so that OpenCore.qcow2 boot images
#  can be built.
ARG DOCKER_KERNEL_VERSION=linux-image-kvm

ENV TZ=America/Los_Angeles
ARG DEBIAN_FRONTEND=noninteractive

RUN DEBCONF_FRONTEND=noninteractive apt update \
        && apt install \
            bridge-utils \
            fish \
            git wget \
            libguestfs-tools \
            libvirt-daemon-system \
            $DOCKER_KERNEL_VERSION \
            p7zip-full \
            qemu \
            sudo \
            uml-utilities \
            virt-manager \
            -y

# Configure SSH
RUN apt install git vim nano alsa-utils openssh-server -y

# Create user and grant sudo privledges
RUN adduser --disabled-password \
        --gecos '' $USER \
        && echo "$USER ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/$USER \
        && chmod 0440 /etc/sudoers.d/$USER

# Configure VNC for user
RUN apt install \
        dbus-x11 \
        openbox \
        tigervnc-common \
        tigervnc-standalone-server \
        xfce4 \
        xfce4-goodies \
        x11-xserver-utils \
        xdotool \
        xorg \
        xterm \
        ufw \
        -y

USER $USER

# only create ~/.vnc as helm will build out ~/.vnc/config
RUN mkdir -p ${HOME}/.vnc

RUN git clone --depth 1 https://github.com/kholia/OSX-KVM.git /home/$USER/OSX-KVM

VOLUME ["/tmp/.X11-unix"]

WORKDIR /home/$USER/OSX-KVM
# helm will build out ./Launch_custom.sh
CMD envsubst < ./Launch_custom.sh | bash
