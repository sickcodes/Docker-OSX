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

help_text="Usage: ./generate-unique-machine-values.sh

General options:
    --count, -n, -c <count>         Number of serials to generate
    --model, -m <model>             Device model, e.g. 'iMacPro1,1'
    --csv <filename>                Optionally change the CSV output filename
    --tsv <filename>                Optionally change the TSV output filename
    --output-dir <directory>        Optionally change the script output location
    --width <string>                Resolution x axis length in px, default 1920
    --height <string>               Resolution y axis length in px, default 1080
    --kernel-args <string>          Additional boot-args
    --input-plist-url <url>         Specify an alternative master plist, via URL
    --master-plist-url <url>        Same as above.
    --custom-plist <filename>       Optionally change the input plist.
    --master-plist <filename>       Same as above.
    --output-bootdisk <filename>    Optionally change the bootdisk filename
    --create-envs, --envs           Create all corresponding sourcable envs
    --create-plists, --plists       Create all corresponding config.plists
    --create-bootdisks, --bootdisks Create all corresponding bootdisks [SLOW]
    --help, -h, help                Display this help and exit

Additional options only if you are creating ONE serial set:
    --output-bootdisk <filename>    Optionally change the bootdisk filename
    --output-env <filename>         Optionally change the serials env filename

Custom plist placeholders:
    {{DEVICE_MODEL}}, {{SERIAL}}, {{BOARD_SERIAL}},
    {{UUID}}, {{ROM}}, {{WIDTH}}, {{HEIGHT}}, {{KERNEL_ARGS}}

Example:
    ./generate-unique-machine-values.sh --count 1 --plists --bootdisks --envs

Defaults:
    - One serial, for 'iMacPro1,1', in the current working directory
    - CSV and TSV output
    - plists in ./plists/ & bootdisks in ./bootdisks/ & envs in ./envs
    - if you set --bootdisk name, --bootdisks is assumed
    - if you set --custom-plist, --plists is assumed
    - if you set --output-env, --envs is assumed

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

    --count=* | -c=* | -n=* )
                export SERIAL_SET_COUNT="${1#*=}"
                shift
            ;;

    --count* | -c* | -n* )
                export SERIAL_SET_COUNT="${2}"
                shift
                shift
            ;;

    --csv=* )
                export CSV_OUTPUT_FILENAME="${1#*=}"
                shift
            ;;

    --csv* )
                export CSV_OUTPUT_FILENAME="${2}"
                shift
                shift
            ;;

    --tsv=* )
                export TSV_OUTPUT_FILENAME="${1#*=}"
                shift
            ;;

    --tsv* )
                export TSV_OUTPUT_FILENAME="${2}"
                shift
                shift
            ;;

    --output-dir=* )
                export OUTPUT_DIRECTORY="${1#*=}"
                shift
            ;;

    --output-dir* )
                export OUTPUT_DIRECTORY="${2}"
                shift
                shift
            ;;

    --output-bootdisk=* )
                export OUTPUT_BOOTDISK="${1#*=}"
                shift
            ;;

    --output-bootdisk* )
                export OUTPUT_BOOTDISK="${2}"
                shift
                shift
            ;;

    --output-env=* )
                export OUTPUT_ENV="${1#*=}"
                shift
            ;;

    --output-env* )
                export OUTPUT_ENV="${2}"
                shift
                shift
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

    --create-plists | --plists )
                export CREATE_PLISTS=1
                shift
            ;;

    --create-bootdisks | --bootdisks )
                export CREATE_BOOTDISKS=1
                shift
            ;;

    --create-envs | --envs )
                export CREATE_ENVS=1
                shift
            ;;

    *)
                echo "Invalid option. Running with default values..."
                shift
            ;;
    esac
done


build_mac_serial () {
    [ -d ./OpenCorePkg ] ||  git clone --depth 1 https://github.com/acidanthera/OpenCorePkg.git
    make -C ./OpenCorePkg/Utilities/macserial/
    mv ./OpenCorePkg/Utilities/macserial/macserial .
    chmod +x ./macserial
    stat ./macserial
}

download_vendor_mac_addresses () {
    # download the MAC Address vendor list
    [ -e "${MAC_ADDRESSES_FILE:=vendor_macs.tsv}" ] || wget -O "${MAC_ADDRESSES_FILE}" https://www.wireshark.org/download/automated/data/manuf
}

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


generate_serial_sets () {


    
    if [ "${CSV_OUTPUT_FILENAME}" ]; then
        [ "${CSV_OUTPUT_FILENAME}" ] && export CSV_SERIAL_SETS_FILE="${CSV_OUTPUT_FILENAME}"
    else
        export CSV_SERIAL_SETS_FILE="${OUTPUT_DIRECTORY}/serial_sets-${DATE_NOW}.csv"
    fi

    if [ "${TSV_OUTPUT_FILENAME}" ]; then
        [ "${TSV_OUTPUT_FILENAME}" ] && export TSV_SERIAL_SETS_FILE="${TSV_OUTPUT_FILENAME}"
    else
        export TSV_SERIAL_SETS_FILE="${OUTPUT_DIRECTORY}/serial_sets-${DATE_NOW}.tsv"
    fi

    
    ./macserial \
        --num "${SERIAL_SET_COUNT}" \
        --model "${DEVICE_MODEL}" \
        | while IFS='\ \|\ ' read -r SERIAL BOARD_SERIAL; do
            # make a uuid...
            UUID="$(uuidgen)"
            # bash 3-5 compatible
            # UUID="${UUID^^}"
            UUID="$(tr '[:lower:]' '[:upper:]' <<< "${UUID}")"

            # get a random vendor specific MAC address.
            RANDOM_MAC_PREFIX="$(grep -e "${VENDOR_REGEX}" < "${MAC_ADDRESSES_FILE:=vendor_macs.tsv}" | sort --random-sort | head -n1)"
            RANDOM_MAC_PREFIX="$(cut -d$'\t' -f1 <<< "${RANDOM_MAC_PREFIX}")"
            MAC_ADDRESS="$(printf "${RANDOM_MAC_PREFIX}:%02X:%02X:%02X" "$((RANDOM%256))" "$((RANDOM%256))" "$((RANDOM%256))")"

            [ -z "${WIDTH}" ] && WIDTH=1920
            [ -z "${HEIGHT}" ] && HEIGHT=1080

            # append to csv file
            tee -a "${CSV_SERIAL_SETS_FILE}" <<EOF
"${DEVICE_MODEL}","${SERIAL}","${BOARD_SERIAL}","${UUID}","${MAC_ADDRESS}","${WIDTH}","${HEIGHT}","${KERNEL_ARGS}"
EOF
            echo "Wrote CSV to: ${CSV_SERIAL_SETS_FILE}"

            # append to tsv file
            T=$'\t'
            tee -a "${TSV_SERIAL_SETS_FILE}" <<EOF
${DEVICE_MODEL}${T}${SERIAL}${T}${BOARD_SERIAL}${T}${UUID}${T}${MAC_ADDRESS}${T}${WIDTH}${T}${HEIGHT}${T}${KERNEL_ARGS}
EOF
            echo "Wrote TSV to: ${TSV_SERIAL_SETS_FILE}"

            # if any of these are on, we need the env file.
            if [ "${CREATE_ENVS}" ] || [ "${CREATE_PLISTS}" ] || [ "${CREATE_BOOTDISKS}" ] || [ "${OUTPUT_BOOTDISK}" ] || [ "${OUTPUT_ENV}" ]; then
                mkdir -p "${OUTPUT_DIRECTORY}/envs"
                OUTPUT_ENV_FILE="${OUTPUT_ENV:-"${OUTPUT_DIRECTORY}/envs/${SERIAL}.env.sh"}"
                touch "${OUTPUT_ENV_FILE}"
                cat <<EOF > "${OUTPUT_ENV_FILE}"
export DEVICE_MODEL="${DEVICE_MODEL}"
export SERIAL="${SERIAL}"
export BOARD_SERIAL="${BOARD_SERIAL}"
export UUID="${UUID}"
export MAC_ADDRESS="${MAC_ADDRESS}"
export WIDTH="${WIDTH}"
export HEIGHT="${HEIGHT}"
EOF

            fi

            # plist required for bootdisks, so create anyway.
            if [ "${CREATE_PLISTS}" ] || [ "${CREATE_BOOTDISKS}" ]; then

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

                mkdir -p "${OUTPUT_DIRECTORY}/plists"
                source "${OUTPUT_ENV_FILE}"
                ROM="${MAC_ADDRESS//\:/}"
                ROM="${ROM,,}"
                sed -e s/\{\{DEVICE_MODEL\}\}/"${DEVICE_MODEL}"/g \
                    -e s/\{\{SERIAL\}\}/"${SERIAL}"/g \
                    -e s/\{\{BOARD_SERIAL\}\}/"${BOARD_SERIAL}"/g \
                    -e s/\{\{UUID\}\}/"${UUID}"/g \
                    -e s/\{\{ROM\}\}/"${ROM}"/g \
                    -e s/\{\{WIDTH\}\}/"${WIDTH}"/g \
                    -e s/\{\{HEIGHT\}\}/"${HEIGHT}"/g \
                    -e s/\{\{KERNEL_ARGS\}\}/"${KERNEL_ARGS:-}"/g \
                    "${MASTER_PLIST}" > "${OUTPUT_DIRECTORY}/plists/${SERIAL}.config.plist" || exit 1
            fi

            # make bootdisk qcow2 format if --bootdisks, but also if you set the bootdisk filename
            if [ "${CREATE_BOOTDISKS}" ] || [ "${OUTPUT_BOOTDISK}" ]; then
                [ -e ./opencore-image-ng.sh ] \
                    || { wget "${OPENCORE_IMAGE_MAKER_URL}" \
                        && chmod +x opencore-image-ng.sh ; }
                mkdir -p "${OUTPUT_DIRECTORY}/bootdisks"
                ./opencore-image-ng.sh \
                    --cfg "${OUTPUT_DIRECTORY}/plists/${SERIAL}.config.plist" \
                    --img "${OUTPUT_BOOTDISK:-${OUTPUT_DIRECTORY}/bootdisks/${SERIAL}.OpenCore-nopicker.qcow2}" || exit 1
            fi

        done

        [ -e "${CSV_SERIAL_SETS_FILE}" ] && \
            cat <(echo "DEVICE_MODEL,SERIAL,BOARD_SERIAL,UUID,MAC_ADDRESS,WIDTH,HEIGHT,KERNEL_ARGS") "${CSV_SERIAL_SETS_FILE}"


        [ -e "${TSV_SERIAL_SETS_FILE}" ] && \
            cat <(printf "DEVICE_MODEL\tSERIAL\tBOARD_SERIAL\tUUID\tMAC_ADDRESS\tWIDTH\tHEIGHT\tKERNEL_ARGS\n") "${TSV_SERIAL_SETS_FILE}"

}

main () {
    # setting default variables if there are no options
    export DATE_NOW="$(date +%F-%T)"
    export DEVICE_MODEL="${DEVICE_MODEL:=iMacPro1,1}"
    export VENDOR_REGEX="${VENDOR_REGEX:=Apple, Inc.}"
    export SERIAL_SET_COUNT="${SERIAL_SET_COUNT:=1}"
    export OUTPUT_DIRECTORY="${OUTPUT_DIRECTORY:=.}"
    cat <<EOF
DEVICE_MODEL:       ${DEVICE_MODEL}
SERIAL_SET_COUNT:   ${SERIAL_SET_COUNT}
OUTPUT_DIRECTORY:   ${OUTPUT_DIRECTORY}
EOF
    [ -d "${OUTPUT_DIRECTORY}" ] || mkdir -p "${OUTPUT_DIRECTORY}"
    [ -e ./macserial ] || build_mac_serial
    download_vendor_mac_addresses
    if [ "${CREATE_BOOTDISKS}" ] || [ "${OUTPUT_BOOTDISK}" ]; then
        download_qcow_efi_folder
    fi
    generate_serial_sets
    echo "${SERIAL_SETS_FILE}"    
}

main

