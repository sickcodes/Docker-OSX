#!/bin/bash

echo "${BOILERPLATE}" \
    ; [[ "${TERMS_OF_USE}" = i_agree ]] || exit 1 \
    ; echo "Disk is being copied between layers... Please wait a minute..." \
    ; sudo touch /dev/kvm /dev/snd "${IMAGE_PATH}" "${BOOTDISK}" "${ENV}" 2>/dev/null || true \
    ; sudo chown -R $(id -u):$(id -g) /dev/kvm /dev/snd "${IMAGE_PATH}" "${BOOTDISK}" "${ENV}" 2>/dev/null || true \
    ; [[ "${NOPICKER}" == true ]] && { \
        sed -i '/^.*InstallMedia.*/d' Launch.sh \
        && export BOOTDISK="${BOOTDISK:=/home/arch/OSX-KVM/OpenCore/OpenCore-nopicker.qcow2}" \
    ; } \
    || export BOOTDISK="${BOOTDISK:=/home/arch/OSX-KVM/OpenCore/OpenCore.qcow2}" \
    ; [[ "${GENERATE_UNIQUE}" == true ]] && { \
        ./Docker-OSX/osx-serial-generator/generate-unique-machine-values.sh \
            --master-plist-url="${MASTER_PLIST_URL}" \
            --count 1 \
            --tsv ./serial.tsv \
            --bootdisks \
            --width "${WIDTH:-1920}" \
            --height "${HEIGHT:-1080}" \
            --output-bootdisk "${BOOTDISK:=/home/arch/OSX-KVM/OpenCore/OpenCore.qcow2}" \
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
            --output-bootdisk "${BOOTDISK:=/home/arch/OSX-KVM/OpenCore/OpenCore.qcow2}" \
    || exit 1 ; } \
    ; { [[ "${DISPLAY}" = ':99' ]] || [[ "${HEADLESS}" == true ]] ; } && { \
        nohup Xvfb :99 -screen 0 1920x1080x16 \
        & until [[ "$(xrandr --query 2>/dev/null)" ]]; do sleep 1 ; done \
    ; } \
    ; stat "${IMAGE_PATH}" \
    ; echo "Large image is being copied between layers, please wait a minute..." \
    ; ./enable-ssh.sh \
    ; [[ -e ~/.ssh/id_docker_osx ]] || { \
        /usr/bin/ssh-keygen -t rsa -f ~/.ssh/id_docker_osx -q -N "" \
        && chmod 600 ~/.ssh/id_docker_osx \
    ; } \
    ; /bin/bash -c ./Launch.sh \
    & echo "Booting Docker-OSX in the background. Please wait..." \
    ; until [[ "$(sshpass -p${PASSWORD:=alpine} ssh-copy-id -f -i ~/.ssh/id_docker_osx.pub -p 10022 ${USERNAME:=user}@127.0.0.1)" ]]; do \
        echo "Disk is being copied between layers. Repeating until able to copy SSH key into OSX..." \
        ; sleep 1 \
    ; done \
    ; grep id_docker_osx ~/.ssh/config || { \
        tee -a ~/.ssh/config <<< 'Host 127.0.0.1' \
        ; tee -a ~/.ssh/config <<< "    User ${USERNAME:=user}" \
        ; tee -a ~/.ssh/config <<< '    Port 10022' \
        ; tee -a ~/.ssh/config <<< '    IdentityFile ~/.ssh/id_docker_osx' \
        ; tee -a ~/.ssh/config <<< '    StrictHostKeyChecking no' \
        ; tee -a ~/.ssh/config <<< '    UserKnownHostsFile=/dev/null' \
    ; } \
    && ssh -i ~/.ssh/id_docker_osx ${USERNAME:=user}@127.0.0.1 -p 10022 "${OSX_COMMANDS}"
