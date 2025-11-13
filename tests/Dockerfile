#!/usr/bin/docker
#     ____             __             ____  ______  __
#    / __ \____  _____/ /_____  _____/ __ \/ ___/ |/ /
#   / / / / __ \/ ___/ //_/ _ \/ ___/ / / /\__ \|   /
#  / /_/ / /_/ / /__/ ,< /  __/ /  / /_/ /___/ /   |
# /_____/\____/\___/_/|_|\___/_/   \____//____/_/|_| TEST SUITE FOR TESTING SMALL CHANGES
#
# Title:            Docker-OSX (Mac on Docker)
# Author:           Sick.Codes https://twitter.com/sickcodes
# Version:          6.0
# License:          GPLv3+
# Repository:       https://github.com/sickcodes/Docker-OSX
# Website:          https://sick.codes
#

FROM sickcodes/docker-osx:latest

RUN echo "Replace me" && exit 1

#### SPECIAL RUNTIME ARGUMENTS BELOW

# env -e ADDITIONAL_PORTS with a comma
# for example, -e ADDITIONAL_PORTS=hostfwd=tcp::23-:23,
ENV ADDITIONAL_PORTS=

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

ENV MASTER_PLIST_URL="https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-nopicker-custom.plist"

# Add NETDEV for bridged networking option, see https://github.com/sickcodes/Docker-OSX/issues/72
# ENV NETDEV='tap,id=net0,ifname=tap0,script=no,downscript=no'
# ENV NETDEV='user,id=net0,hostfwd=tcp::${INTERNAL_SSH_PORT:-10022}-:22,hostfwd=tcp::${SCREEN_SHARE_PORT:-5900}-:5900,${ADDITIONAL_PORTS}'

# ENV NETWORKING=e1000-82545em
# renamed to NETWORKING_DEVICE, but not deprecated
ENV NETWORKING=vmxnet3
ENV NETWORKING_DEVICE=${NETWORKING}

# boolean for skipping the disk selection menu at in the boot process
ENV NOPICKER=false

# dynamic RAM options for runtime
ENV RAM=3
# ENV RAM=max
# ENV RAM=half

# The x and y coordinates for resolution.
# Must be used with either -e GENERATE_UNIQUE=true or -e GENERATE_SPECIFIC=true.
ENV WIDTH=1920
ENV HEIGHT=1080

# libguestfs verbose
ENV LIBGUESTFS_DEBUG=1
ENV LIBGUESTFS_TRACE=1

VOLUME ["/tmp/.X11-unix"]

CMD sudo touch /dev/kvm /dev/snd "${IMAGE_PATH}" "${BOOTDISK}" "${ENV}" 2>/dev/null || true \
    ; sudo chown -R $(id -u):$(id -g) /dev/kvm /dev/snd "${IMAGE_PATH}" "${BOOTDISK}" "${ENV}" 2>/dev/null || true \
    ; [[ "${NOPICKER}" == true ]] && { \
        sed -i '/^.*InstallMedia.*/d' Launch.sh \
        && export BOOTDISK="${BOOTDISK:=/home/arch/OSX-KVM/OpenCore-Catalina/OpenCore-nopicker.qcow2}" \
    ; } \
    || export BOOTDISK="${BOOTDISK:=/home/arch/OSX-KVM/OpenCore-Catalina/OpenCore.qcow2}" \
    ; [[ "${GENERATE_UNIQUE}" == true ]] && { \
        ./Docker-OSX/osx-serial-generator/generate-unique-machine-values.sh \
            --master-plist-url="${MASTER_PLIST_URL}" \
            --count 1 \
            --tsv ./serial.tsv \
            --bootdisks \
            --width "${WIDTH:-1920}" \
            --height "${HEIGHT:-1080}" \
            --output-bootdisk "${BOOTDISK:=/home/arch/OSX-KVM/OpenCore-Catalina/OpenCore.qcow2}" \
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
            --output-bootdisk "${BOOTDISK:=/home/arch/OSX-KVM/OpenCore-Catalina/OpenCore.qcow2}" \
    || exit 1 ; } \
    ; ./enable-ssh.sh && /bin/bash -c ./Launch.sh
