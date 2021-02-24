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

Example:
    ./generate-unique-machine-values.sh --count 1 --model="iMacPro1,1"

General options:
    --count, -n, -c <count>         Number of serials to generate
    --model, -m <model>             Device model, e.g. "iMacPro1,1"
    --csv <filename>                Optionally change the CSV output filename.
    --output-dir <directory>        Optionally change the script output location.
    --help, -h, help                Display this help and exit

Notes:
    - Default is 1 serial for "iMacPro1,1" in the current working directory.
    - CSV is double quoted.
    - If you do not set a CSV filename, the output will be sent to the output-dir.
    - If you do not set an output-dir, the current directory will be the output directory.
    - Sourcable environment variable shell files will be written to a folder, "envs".

Author:  Sick.Codes https://sick.codes/
Project: https://github.com/sickcodes/Docker-OSX/
"

MACINFOPKG_VERSION=2.1.2

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

    --output-dir=* )
                export OUTPUT_DIRECTORY="${1#*=}"
                shift
            ;;
    --output-dir* )
                export OUTPUT_DIRECTORY="${2}"
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

    *)
                echo "Invalid option. Running with default values..."
                shift
            ;;
    esac
done


build_mac_serial () {
    MACINFOPKG_VERSION="${MACINFOPKG_VERSION:=2.1.2}"
    wget -O "${TARBALL:=./MacInfoPkg.tar.gz}" \
        "https://github.com/acidanthera/MacInfoPkg/archive/${MACINFOPKG_VERSION:=2.1.2}.tar.gz"
    tar -xzvf "${TARBALL}"
    cd "./MacInfoPkg-${MACINFOPKG_VERSION}/macserial" \
        && ./build.tool 2>/dev/null \
        && cd -
    mv "./MacInfoPkg-${MACINFOPKG_VERSION}/macserial/bin/macserial" .
    rm -f "${TARBALL}"
    rm -rf "./MacInfoPkg-${MACINFOPKG_VERSION}/"
    chmod +x macserial
    stat ./macserial
}

download_vendor_mac_addresses () {
    # download the MAC Address vendor list
    [[ -e "${MAC_ADDRESSES_FILE:=vendor_macs.tsv}" ]] || wget -O "${MAC_ADDRESSES_FILE}" https://gitlab.com/wireshark/wireshark/-/raw/master/manuf
}

generate_serial_sets () {
    mkdir -p "${OUTPUT_DIRECTORY}/envs"
    export DATE_NOW="$(date +%F-%T)"
    export DEVICE_MODEL="${DEVICE_MODEL:=iMacPro1,1}"
    export VENDOR_REGEX="${VENDOR_REGEX:=Apple, Inc.}"
    
    if [[ "${CSV_OUTPUT_FILENAME}" ]]; then
        export SERIAL_SETS_FILE="${CSV_OUTPUT_FILENAME}"
    else
        export SERIAL_SETS_FILE="${OUTPUT_DIRECTORY}/serial_sets-${DATE_NOW}.csv"
    fi
    
    touch "${SERIAL_SETS_FILE}"
    echo "Writing serial sets to ${SERIAL_SETS_FILE}"

    ./macserial \
        --num "${SERIAL_SET_COUNT:=1}" \
        --model "${DEVICE_MODEL}" \
        | while IFS='\ \|\ ' read -r Serial BoardSerial; do
            # make a uuid...
            SmUUID="$(uuidgen)"
            SmUUID="${SmUUID^^}"

            # get a random vendor specific MAC address.
            RANDOM_MAC_PREFIX="$(grep -e "${VENDOR_REGEX}" < "${MAC_ADDRESSES_FILE:=vendor_macs.tsv}" | sort --random-sort | head -n1)"
            RANDOM_MAC_PREFIX="$(cut -d$'\t' -f1 <<< "${RANDOM_MAC_PREFIX}")"
            MacAddress="$(printf "${RANDOM_MAC_PREFIX}:%02X:%02X:%02X" $[RANDOM%256] $[RANDOM%256] $[RANDOM%256])"

            echo "\"${DEVICE_MODEL}\",\"${Serial}\",\"${BoardSerial}\",\"${SmUUID}\",\"${MacAddress}\"" >> "${SERIAL_SETS_FILE}"
            touch "${OUTPUT_DIRECTORY}/envs/${Serial}.env.sh"
            cat <<EOF > "${OUTPUT_DIRECTORY}/envs/${Serial}.env.sh"
export Type=${DEVICE_MODEL}
export Serial=${Serial}
export BoardSerial=${BoardSerial}
export SmUUID=${SmUUID}
export MacAddress=${MacAddress}
EOF
    done

    cat <(echo "Type,Serial,BoardSerial,SmUUID,MacAddress") "${SERIAL_SETS_FILE}"
}

main () {
    # setting default variables if there are no options
    cat <<EOF
DEVICE_MODEL:       ${DEVICE_MODEL:=iMacPro1,1}
SERIAL_SET_COUNT:   ${SERIAL_SET_COUNT:=1}
OUTPUT_DIRECTORY:   ${OUTPUT_DIRECTORY:=.}
EOF
    [[ -d "${OUTPUT_DIRECTORY}" ]] || mkdir -p "${OUTPUT_DIRECTORY}"
    [[ -e ./macserial ]] || build_mac_serial
    download_vendor_mac_addresses
    generate_serial_sets
    echo "${SERIAL_SETS_FILE}"    
}

main

