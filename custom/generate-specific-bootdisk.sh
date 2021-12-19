#!/bin/bash
#   ___  _____  __  ___          _      _    ___                       _           
#  / _ \/ __\ \/ / / __| ___ _ _(_)__ _| |  / __|___ _ _  ___ _ _ __ _| |_ ___ _ _ 
# | (_) \__ \>  <  \__ \/ -_) '_| / _` | | | (_ / -_) ' \/ -_) '_/ _` |  _/ _ \ '_|
#  \___/|___/_/\_\ |___/\___|_| |_\__,_|_|  \___\___|_||_\___|_| \__,_|\__\___/_|  
#
# Repo:             https://github.com/sickcodes/osx-serial-generator/
# Title:            OSX Serial Generator
# Author:           Sick.Codes https://sick.codes/
# Version:          3.1
# License:          GPLv3+

set -e

help_text="Usage: ./generate-specific-bootdisk.sh 

Required options:
    --model <string>                Device model, e.g. 'iMacPro1,1'
    --serial <string>               Device Serial number
    --board-serial <string>         Main Logic Board Serial number (MLB)
    --uuid <string>                 SMBIOS UUID (SmUUID)
    --mac-address <string>          Used for both the MAC address and to set ROM
                                    ROM is lowercased sans any colons
Optional options:
    --width <integer>               Resolution x axis length in px, default 1920
    --height <integer>              Resolution y axis length in px, default 1080
    --kernel-args <string>          Additional boot-args
    --input-plist-url <url>         Specify an alternative master plist, via URL
    --master-plist-url <url>        Same as above.
    --custom-plist <filename>       Optionally change the input plist.
    --master-plist <filename>       Same as above.
    --output-bootdisk <filename>    Optionally change the bootdisk filename
    --output-plist <filename>       Optionally change the output plist filename
    --help, -h, help                Display this help and exit

Placeholders:   {{DEVICE_MODEL}}, {{SERIAL}}, {{BOARD_SERIAL}}, {{UUID}},
                {{ROM}}, {{WIDTH}}, {{HEIGHT}}

Example:
    ./generate-specific-bootdisk.sh \\
        --model iMacPro1,1 \\
        --serial C02TW0WAHX87 \\
        --board-serial C027251024NJG36UE \\
        --uuid 5CCB366D-9118-4C61-A00A-E5BAF3BED451 \\
        --mac-address A8:5C:2C:9A:46:2F \\
        --output-bootdisk ./OpenCore-nopicker.qcow2 \\
        --width 1920 \\
        --height 1080

Author:  Sick.Codes https://sick.codes/
Project: https://github.com/sickcodes/osx-serial-generator/
License: GPLv3+
"

OPENCORE_IMAGE_MAKER_URL='https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/opencore-image-ng.sh'
MASTER_PLIST_URL='https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-nopicker-custom.plist'

# gather arguments
while (( "$#" )); do
    case "${1}"  in

    --help | -h | h | help ) 
                echo "${help_text}" && exit 0
            ;;

    --model=* | -m=* )
                export DEVICE_MODEL="${1#*=}"
                shift
            ;;

    --model* | -m* ) 
                export DEVICE_MODEL="${2}"
                shift
                shift
            ;;

    --serial=* )
                export SERIAL="${1#*=}"
                shift
            ;;

    --serial* )
                export SERIAL="${2}"
                shift
                shift
            ;;

    --board-serial=* )
                export BOARD_SERIAL="${1#*=}"
                shift
            ;;

    --board-serial* )
                export BOARD_SERIAL="${2}"
                shift
                shift
            ;;

    --uuid=* )
                export UUID="${1#*=}"
                shift
            ;;

    --uuid* )
                export UUID="${2}"
                shift
                shift
            ;;

    --mac-address=* )
                export MAC_ADDRESS="${1#*=}"
                shift
            ;;

    --mac-address* )
                export MAC_ADDRESS="${2}"
                shift
                shift
            ;;

    --width=* )
                export WIDTH="${1#*=}"
                shift
            ;;

    --width* )
                export WIDTH="${2}"
                shift
                shift
            ;;

    --height=* )
                export HEIGHT="${1#*=}"
                shift
            ;;

    --height* )
                export HEIGHT="${2}"
                shift
                shift
            ;;

    --output-bootdisk=* )
                export OUTPUT_QCOW="${1#*=}"
                shift
            ;;

    --output-bootdisk* )
                export OUTPUT_QCOW="${2}"
                shift
                shift
            ;;

    --output-plist=* )
                export OUTPUT_PLIST="${1#*=}"
                shift
            ;;

    --output-plist* )
                export OUTPUT_PLIST="${2}"
                shift
                shift
            ;;

    --master-plist-url=* | --input-plist-url=* | --custom-plist-url=* )
                export MASTER_PLIST_URL="${1#*=}"
                shift
            ;;

    --master-plist-url* | --input-plist-url* | --custom-plist-url* )
                export MASTER_PLIST_URL="${2}"
                shift
                shift
            ;;

    --master-plist=* | --input-plist=* | --custom-plist=* )
                export MASTER_PLIST="${1#*=}"
                shift
            ;;

    --master-plist* | --input-plist* | --custom-plist* )
                export MASTER_PLIST="${2}"
                shift
                shift
            ;;

    *)
                echo "Invalid option ${1}. Running with default values..."
                shift
            ;;
    esac
done


download_qcow_efi_folder () {

    export EFI_FOLDER=./OpenCore/EFI
    export RESOURCES_FOLDER=./resources/OcBinaryData/Resources

    # check if we are inside OSX-KVM already
    # if not, download OSX-KVM locally
    [ -d ./OpenCore/EFI/ ] || {
        [ -d ./OSX-KVM/ ] || git clone --recurse-submodules --depth 1 https://github.com/kholia/OSX-KVM.git
        export EFI_FOLDER="./OSX-KVM/${EFI_FOLDER}"
    }
    
    [ -d ./resources/OcBinaryData/Resources/ ] || {
        export RESOURCES_FOLDER="./OSX-KVM/${RESOURCES_FOLDER}"
    }

    # EFI Shell commands
    touch startup.nsh && echo 'fs0:\EFI\BOOT\BOOTx64.efi' > startup.nsh

    cp -a "${EFI_FOLDER}" .

    mkdir -p ./EFI/OC/Resources

    # copy Apple drivers into EFI/OC/Resources
    cp -a "${RESOURCES_FOLDER}"/* ./EFI/OC/Resources
}

generate_bootdisk () {

    # need a config.plist
    if [ "${MASTER_PLIST}" ]; then
        [ -e "${MASTER_PLIST}" ] || echo "Could not find: ${MASTER_PLIST}"
    elif [ "${MASTER_PLIST}" ] && [ "${MASTER_PLIST_URL}" ]; then
        echo 'You specified both a custom plist FILE & custom plist URL.'
        echo 'Use only one of those options.'
    elif [ "${MASTER_PLIST_URL}" ]; then
        wget -O "${MASTER_PLIST:=./config-custom.plist}" "${MASTER_PLIST_URL}"
    else
        # default is config-nopicker-custom.plist from OSX-KVM with placeholders used in Docker-OSX
        wget -O "${MASTER_PLIST:=./config-nopicker-custom.plist}" "${MASTER_PLIST_URL}"
    fi

    [ -e ./opencore-image-ng.sh ] \
        || { wget "${OPENCORE_IMAGE_MAKER_URL}" \
            && chmod +x opencore-image-ng.sh ; }

    # plist required for bootdisks, so create anyway.
    if [ "${DEVICE_MODEL}" ] \
            && [ "${SERIAL}" ] \
            && [ "${BOARD_SERIAL}" ] \
            && [ "${UUID}" ] \
            && [ "${MAC_ADDRESS}" ]; then
        ROM="${MAC_ADDRESS//\:/}"
        ROM="${ROM,,}"
        sed -e s/\{\{DEVICE_MODEL\}\}/"${DEVICE_MODEL}"/g \
            -e s/\{\{SERIAL\}\}/"${SERIAL}"/g \
            -e s/\{\{BOARD_SERIAL\}\}/"${BOARD_SERIAL}"/g \
            -e s/\{\{UUID\}\}/"${UUID}"/g \
            -e s/\{\{ROM\}\}/"${ROM}"/g \
            -e s/\{\{WIDTH\}\}/"${WIDTH:-1920}"/g \
            -e s/\{\{HEIGHT\}\}/"${HEIGHT:-1080}"/g \
            -e s/\{\{KERNEL_ARGS\}\}/"${KERNEL_ARGS:-}"/g \
            "${MASTER_PLIST}" > ./tmp.config.plist || exit 1
    else
        cat <<EOF && exit 1
Error: one of the following values is missing:

--model "${DEVICE_MODEL:-MISSING}"
--serial "${SERIAL:-MISSING}"
--board-serial "${BOARD_SERIAL:-MISSING}"
--uuid "${UUID:-MISSING}"
--mac-address "${MAC_ADDRESS:-MISSING}"

Optional:

--width "${WIDTH:-1920}"
--height "${HEIGHT:-1080}"
--kernel-args "${KERNEL_ARGS:-}"

EOF
    fi

    ./opencore-image-ng.sh \
        --cfg "./tmp.config.plist" \
        --img "${OUTPUT_QCOW:-./${SERIAL}.OpenCore-nopicker.qcow2}" || exit 1
        rm ./tmp.config.plist

}

main () {
    download_qcow_efi_folder
    generate_bootdisk
}

main

