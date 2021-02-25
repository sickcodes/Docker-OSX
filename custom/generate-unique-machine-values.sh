#!/bin/bash
#     ____             __             ____  ______  __
#    / __ \____  _____/ /_____  _____/ __ \/ ___/ |/ /
#   / / / / __ \/ ___/ //_/ _ \/ ___/ / / /\__ \|   /
#  / /_/ / /_/ / /__/ ,< /  __/ /  / /_/ /___/ /   |
# /_____/\____/\___/_/|_|\___/_/   \____//____/_/|_| SERIALIZER
#
# Repo:             https://github.com/sickcodes/Docker-OSX/
# Title:            Mac on Docker (Docker-OSX)
# Author:           Sick.Codes https://sick.codes/
# Version:          3.1
# License:          GPLv3+

help_text="Usage: generate-unique-machine-values.sh

General options:
    --count, -n, -c <count>         Number of serials to generate
    --model, -m <model>             Device model, e.g. 'iMacPro1,1'
    --csv <filename>                Optionally change the CSV output filename.
    --tsv <filename>                Optionally change the TSV output filename.
    --output-bootdisk <filename>    Optionally change the bootdisk qcow output filename. Useless when count > 1.
    --output-env <filename>         Optionally change the bootdisk env filename. Useless when count > 1.
    --output-dir <directory>        Optionally change the script output location.

    --help, -h, help                Display this help and exit
    --plists                        Create corresponding config.plists for each serial set.
    --bootdisks                     [SLOW] Create corresponding boot disk images for each serial set.

Example:
    ./generate-unique-machine-values.sh --count 1 --model='iMacPro1,1' --plists --bootdisks

        The above example will generate a
            - serial
            - board serial
            - uuid
            - MAC address
            - ROM value based on lowercase MAC address
            - Boot disk qcow image.
            - config.plist

Notes:
    - Default is 1 serial for 'iMacPro1,1' in the current working directory.
    - Default output is CSV, whereas setting the TSV option will output as tab-separated.
    - CSV is double quoted.
    - If you do not set a CSV filename, the output will be sent to the output-dir.
    - If you do not set an output-dir, the current directory will be the output directory.
    - Sourcable environment variable shell files will be written to a folder, 'envs'.
    - config.plist files will be written to a folder, 'plists'.

Author:  Sick.Codes https://sick.codes/
Project: https://github.com/sickcodes/Docker-OSX/
"

MACINFOPKG_VERSION=2.1.2
PLIST_MASTER=config-nopicker-custom.plist

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
                export OUTPUT_QCOW="${1#*=}"
                shift
            ;;
    --output-bootdisk* )
                export OUTPUT_QCOW="${2}"
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

    --plists )
                export CREATE_PLISTS=1
                shift
            ;;
    --bootdisks ) 
                export CREATE_QCOWS=1
                shift
            ;;

    *)
                echo "Invalid option. Running with default values..."
                shift
            ;;
    esac
done


build_mac_serial () {
    export MACINFOPKG_VERSION="${MACINFOPKG_VERSION:=2.1.2}"
    wget -O "${TARBALL:=./MacInfoPkg.tar.gz}" \
        "https://github.com/acidanthera/MacInfoPkg/archive/${MACINFOPKG_VERSION}.tar.gz"
    tar -xzvf "${TARBALL}"
    cd "./MacInfoPkg-${MACINFOPKG_VERSION}/macserial" \
        && ./build.tool \
        && cd -
    mv "./MacInfoPkg-${MACINFOPKG_VERSION}/macserial/bin/macserial" .
    rm -f "${TARBALL}"
    rm -rf "./MacInfoPkg-${MACINFOPKG_VERSION}/"
    chmod +x ./macserial
    stat ./macserial
}

download_vendor_mac_addresses () {
    # download the MAC Address vendor list
    [[ -e "${MAC_ADDRESSES_FILE:=vendor_macs.tsv}" ]] || wget -O "${MAC_ADDRESSES_FILE}" https://gitlab.com/wireshark/wireshark/-/raw/master/manuf
}

download_qcow_efi_folder () {
    git clone --depth 1 https://github.com/kholia/OSX-KVM.git
    cp -ra ./OSX-KVM/OpenCore-Catalina/EFI .
    mkdir -p ./EFI/OC/Resources
    # clone some Apple drivers
    git clone --depth 1 https://github.com/acidanthera/OcBinaryData.git
    # copy said drivers into EFI/OC/Resources
    cp -a ./OcBinaryData/Resources/* ./EFI/OC/Resources
    # EFI Shell commands
    touch startup.nsh && echo 'fs0:\EFI\BOOT\BOOTx64.efi' > startup.nsh
}


generate_serial_sets () {
    mkdir -p "${OUTPUT_DIRECTORY}/envs"
    export DATE_NOW="$(date +%F-%T)"
    export DEVICE_MODEL="${DEVICE_MODEL:=iMacPro1,1}"
    export VENDOR_REGEX="${VENDOR_REGEX:=Apple, Inc.}"
    
    if [[ "${CSV_OUTPUT_FILENAME}" ]] || [[ "${TSV_OUTPUT_FILENAME}" ]]; then
        [[ ${CSV_OUTPUT_FILENAME} ]] && export CSV_SERIAL_SETS_FILE="${CSV_OUTPUT_FILENAME}"
        [[ ${TSV_OUTPUT_FILENAME} ]] && export TSV_SERIAL_SETS_FILE="${TSV_OUTPUT_FILENAME}"
    else
        export SERIAL_SETS_FILE="${OUTPUT_DIRECTORY}/serial_sets-${DATE_NOW}.csv"
    fi
    
    touch "${SERIAL_SETS_FILE}"
    echo "Writing serial sets to ${SERIAL_SETS_FILE}"

    ./macserial \
        --num "${SERIAL_SET_COUNT:=1}" \
        --model "${DEVICE_MODEL}" \
        | while IFS='\ \|\ ' read -r SERIAL BOARD_SERIAL; do
            # make a uuid...
            UUID="$(uuidgen)"
            UUID="${UUID^^}"

            # get a random vendor specific MAC address.
            RANDOM_MAC_PREFIX="$(grep -e "${VENDOR_REGEX}" < "${MAC_ADDRESSES_FILE:=vendor_macs.tsv}" | sort --random-sort | head -n1)"
            RANDOM_MAC_PREFIX="$(cut -d$'\t' -f1 <<< "${RANDOM_MAC_PREFIX}")"
            MAC_ADDRESS="$(printf "${RANDOM_MAC_PREFIX}:%02X:%02X:%02X" $[RANDOM%256] $[RANDOM%256] $[RANDOM%256])"

            # append to csv file
            if [[ "${CSV_SERIAL_SETS_FILE}" ]]; then
                echo "\"${DEVICE_MODEL}\",\"${SERIAL}\",\"${BOARD_SERIAL}\",\"${UUID}\",\"${MAC_ADDRESS}\"" >> "${CSV_SERIAL_SETS_FILE}"
            fi

            # append to tsv file
            if [[ "${TSV_SERIAL_SETS_FILE}" ]]; then
                printf "${DEVICE_MODEL}\t${SERIAL}\t${BOARD_SERIAL}\t${UUID}\t${MAC_ADDRESS}\n" >> "${TSV_SERIAL_SETS_FILE}"
            fi 

            OUTPUT_ENV_FILE="${OUTPUT_ENV:-"${OUTPUT_DIRECTORY}/envs/${SERIAL}.env.sh"}"
            touch "${OUTPUT_ENV_FILE}"
            cat <<EOF > "${OUTPUT_ENV_FILE}"
export DEVICE_MODEL="${DEVICE_MODEL}"
export SERIAL="${SERIAL}"
export BOARD_SERIAL="${BOARD_SERIAL}"
export UUID="${UUID}"
export MAC_ADDRESS="${MAC_ADDRESS}"
EOF

            # plist required for bootdisks, so create anyway.
            if [[ "${CREATE_PLISTS}" ]] || [[ "${CREATE_QCOWS}" ]]; then
                mkdir -p "${OUTPUT_DIRECTORY}/plists"
                source "${OUTPUT_ENV_FILE}"
                ROM_VALUE="${MAC_ADDRESS//\:/}"
                ROM_VALUE="${ROM_VALUE,,}"
                sed -e s/{{DEVICE_MODEL}}/"${DEVICE_MODEL}"/g \
                    -e s/{{SERIAL}}/"${SERIAL}"/g \
                    -e s/{{BOARD_SERIAL}}/"${BOARD_SERIAL}"/g \
                    -e s/{{UUID}}/"${UUID}"/g \
                    -e s/{{ROM}}/"${ROM}"/g \
                    "${PLIST_MASTER}" > "${OUTPUT_DIRECTORY}/plists/${SERIAL}.config.plist" || exit 1
            fi

            if [[ "${CREATE_QCOWS}" ]]; then
                mkdir -p "${OUTPUT_DIRECTORY}/qcows"
                ./opencore-image-ng.sh \
                    --cfg "${OUTPUT_DIRECTORY}/plists/${SERIAL}.config.plist" \
                    --img "${OUTPUT_QCOW:-${OUTPUT_DIRECTORY}/qcows/${SERIAL}.OpenCore-nopicker.qcow2}" || exit 1
            fi

        done

        [[ -e "${CSV_SERIAL_SETS_FILE}" ]] && \
            cat <(echo "DEVICE_MODEL,SERIAL,BOARD_SERIAL,UUID,MAC_ADDRESS") "${CSV_SERIAL_SETS_FILE}"


        [[ -e "${TSV_SERIAL_SETS_FILE}" ]] && \
            cat <(printf "DEVICE_MODEL\tSERIAL\BOARD_SERIAL\tUUID\tMAC_ADDRESS\n") "${TSV_SERIAL_SETS_FILE}"
    
}

main () {
    # setting default variables if there are no options
    export DEVICE_MODEL="${DEVICE_MODEL:=iMacPro1,1}"
    export SERIAL_SET_COUNT="${SERIAL_SET_COUNT:=1}"
    export OUTPUT_DIRECTORY="${OUTPUT_DIRECTORY:=.}"
    cat <<EOF
DEVICE_MODEL:       ${DEVICE_MODEL}
SERIAL_SET_COUNT:   ${SERIAL_SET_COUNT}
OUTPUT_DIRECTORY:   ${OUTPUT_DIRECTORY}
EOF
    [[ -d "${OUTPUT_DIRECTORY}" ]] || mkdir -p "${OUTPUT_DIRECTORY}"
    [[ -e ./macserial ]] || build_mac_serial
    download_vendor_mac_addresses
    download_qcow_efi_folder
    generate_serial_sets
    echo "${SERIAL_SETS_FILE}"    
}

main

