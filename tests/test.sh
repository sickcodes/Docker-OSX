#!/usr/bin/bash
#     ____             __             ____  ______  __
#    / __ \____  _____/ /_____  _____/ __ \/ ___/ |/ /
#   / / / / __ \/ ___/ //_/ _ \/ ___/ / / /\__ \|   /
#  / /_/ / /_/ / /__/ ,< /  __/ /  / /_/ /___/ /   |
# /_____/\____/\___/_/|_|\___/_/   \____//____/_/|_| TESTS
#
# Title:            Docker-OSX (Mac on Docker)
# Author:           Sick.Codes https://twitter.com/sickcodes
# Version:          4.2
# License:          GPLv3+
# Repository:       https://github.com/sickcodes/Docker-OSX
# Website:          https://sick.codes
#
# Status:           Used internally to auto build, run and test images on DO.
# 

help_text="Usage: ./test.sh --branch <string> --repo <string>

General options:
    --branch, -b <string>               Git branch, default is master
    --repo, -r <url>                    Alternative link to build
    --mirror-country, -m <SS>           Two letter country code for Arch mirrors
    --docker-username, -u <string>      Docker hub username
    --docker-password, -p <string>      Docker hub password
    --vnc-password, -v <string>         Choose a VNC passwd.

Flags
    --no-cache, -n                      Enable --no-cache (default already)
    --no-no-cache, -nn                  Disable --no-cache docker builds
    --help, -h, help                    Display this help and exit
"

# set -xeuf -o pipefail


# gather arguments
while (( "$#" )); do
    case "${1}"  in

    --help | -h | h | help ) 
                echo "${help_text}" && exit 0
            ;;

    --branch=* | -b=* )
                export BRANCH="${1#*=}"
                shift
            ;;
    --branch* | -b* )
                export BRANCH="${2}"
                shift
                shift
            ;;
    --repo=* | -r=* )
                export REPO="${1#*=}"
                shift
            ;;
    --repo* | -r* )
                export REPO="${2}"
                shift
                shift
            ;;
    --mirror-country=* | -m=* )
                export MIRROR_COUNTRY="${1#*=}"
                shift
            ;;
    --mirror-country* | -m* )
                export MIRROR_COUNTRY="${2}"
                shift
                shift
            ;;
    --vnc-password=* | -v=* | --vnc-passwd=* )
                export VNC_PASSWORD="${1#*=}"
                shift
            ;;
    --vnc-password* | -v* | --vnc-passwd* )
                export VNC_PASSWORD="${2}"
                shift
                shift
            ;;
    --docker-username=* | -u=* )
                export DOCKER_USERNAME="${1#*=}"
                shift
            ;;
    --docker-username* | -u* )
                export DOCKER_USERNAME="${2}"
                shift
                shift
            ;;
    --docker-password=* | -p=* )
                export DOCKER_PASSWORD="${1#*=}"
                shift
            ;;
    --docker-password* | -p* )
                export DOCKER_PASSWORD="${2}"
                shift
                shift
            ;;
    --no-cache | -n )
                export NO_CACHE='--no-cache'
                shift
            ;;
    --no-no-cache | -nn )
                export NO_CACHE=
                shift
            ;;
    *)
                echo "Invalid option: ${1}"
                exit 1
            ;;

    esac
done

BRANCH="${BRANCH:=master}"
REPO="${REPO:=https://github.com/sickcodes/Docker-OSX.git}"
VNC_PASSWORD="${VNC_PASSWORD:=testing}"
MIRROR_COUNTRY="${MIRROR_COUNTRY:=US}"
NO_CACHE="${NO_CACHE:=--no-cache}"


TEST_BUILDS=(
    'docker-osx:naked'
    'docker-osx:naked-auto'
    'docker-osx:auto'
)

TEST_BUILDS=(
    'docker-osx:naked'
    'docker-osx:naked-auto'
    'docker-osx:auto'
)

VERSION_BUILDS=(
    'high-sierra'
    'mojave'
    'catalina'
    'big-sur'
    'monterey'
    'ventura'
    'sonoma'
)

warning () {
    clear
    for j in {15..1}; do 
        echo "############# WARNING: THIS SCRIPT IS NOT INTENDED FOR USE BY ################"
        echo "############# IT IS USED BY THE PROJECT TO BUILD AND PUSH TO DOCKERHUB #######"
        echo ""
        echo "                     Press Ctrl C to stop.       "
        MAX_COLS=$((${COLUMNS}/2))
        printf "$j %.0s" {1..20}
        echo
        sleep 1
    done
}

install_docker () {
    apt remove docker docker-engine docker.io containerd runc -y \
    ; apt install apt-transport-https ca-certificates curl gnupg-agent software-properties-common -y \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg |  apt-key add - \
    && apt-key fingerprint 0EBFCD88 \
    && > /etc/apt/sources.list.d/docker.list \
    && add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    && apt update -y \
    && apt install docker-ce docker-ce-cli containerd.io -y \
    && usermod -aG docker "${USER}" \
    && su hook docker run --rm hello-world
}

install_vnc () {
    apt update -y \
        && apt install xorg openbox tigervnc-standalone-server tigervnc-common tigervnc-xorg-extension tigervnc-viewer -y \
        && mkdir -p ${HOME}/.vnc \
        && touch ~/.vnc/config \
        && tee -a ~/.vnc/config <<< 'geometry=1920x1080' \
        && tee -a ~/.vnc/config <<< 'localhost' \
        && tee -a ~/.vnc/config <<< 'alwaysshared' \
        && touch ./vnc.sh \
        && printf '\n%s\n' \
            'sudo rm -f /tmp/.X99-lock' \
            'export DISPLAY=:99' \
            '/usr/bin/Xvnc -geometry 1920x1080 -rfbauth ~/.vnc/passwd :99 &' > ./vnc.sh \
        && tee vncpasswd_file <<< "${VNC_PASSWORD:=testing}" && echo "${VNC_PASSWORD:="$(tr -dc '[:graph:]' </dev/urandom | head -c8)"}" \
        && vncpasswd -f < vncpasswd_file > ${HOME}/.vnc/passwd \
        && chmod 600 ~/.vnc/passwd \
        && apt install qemu qemu-kvm libvirt-clients libvirt-daemon-system bridge-utils virt-manager -y \
        && sudo systemctl enable libvirtd.service \
        && sudo systemctl enable virtlogd.service \
        && echo 1 | sudo tee /sys/module/kvm/parameters/ignore_msrs \
        && sudo modprobe kvm \
        && echo 'export DISPLAY=:99' >> ~/.bashrc \
        && printf '\n\n\n\n%s\n%s\n\n\n\n' '===========VNC_PASSWORD========== ' "$(<vncpasswd_file)"
    # ufw allow 5999
}

install_scrotcat () {
    apt update -y
    apt install git curl wget vim xvfb scrot build-essential sshpass -y
    git clone https://github.com/stolk/imcat.git
    make -C ./imcat
    sudo cp ./imcat/imcat /usr/bin/imcat
    touch /usr/bin/scrotcat
    tee  /usr/bin/scrotcat <<< '/usr/bin/imcat <(scrot -o /dev/stdout)'
    chmod +x /usr/bin/scrotcat
}

export_display_99 () {
    touch ~/.bashrc
    tee -a ~/.bashrc <<< 'export DISPLAY=:99'
    export DISPLAY=:99
}

start_xvfb () {
    nohup Xvfb :99 -screen 0 1920x1080x16 &
}

start_vnc () {
    nohup bash vnc.sh &
}

enable_kvm () {
    echo 1 | tee /sys/module/kvm/parameters/ignore_msrs
}

clone_repo () {
    git clone --branch="${1}" "${2}" Docker-OSX
}

docker-osx:naked () {
    docker build ${NO_CACHE} \
        --squash \
        --build-arg RANKMIRRORS=true \
        --build-arg MIRROR_COUNTRY="${MIRROR_COUNTRY}" \
        -f ./Dockerfile.naked \
        -t docker-osx:naked .
    docker tag docker-osx:naked sickcodes/docker-osx:naked
}

docker-osx:naked-auto () {
    docker build ${NO_CACHE} \
        --squash \
        --build-arg RANKMIRRORS=true \
        --build-arg MIRROR_COUNTRY="${MIRROR_COUNTRY}" \
        -f ./Dockerfile.naked-auto \
        -t docker-osx:naked-auto .
    docker tag docker-osx:naked-auto sickcodes/docker-osx:naked-auto
}

docker-osx:auto () {
    docker build ${NO_CACHE} \
        --build-arg RANKMIRRORS=true \
        --build-arg MIRROR_COUNTRY="${MIRROR_COUNTRY}" \
        -f ./Dockerfile.auto \
        -t docker-osx:auto .
    docker tag docker-osx:auto sickcodes/docker-osx:auto
}

# docker-osx:auto-big-sur () {
#     docker build ${NO_CACHE} \
#         --build-arg RANKMIRRORS=true \
#         --build-arg MIRROR_COUNTRY="${MIRROR_COUNTRY}" \
#         --build-arg IMAGE_URL='https://images.sick.codes/mac_hdd_ng_auto_big_sur.img' \
#         -f ./Dockerfile.auto \
#         -t docker-osx:auto-big-sur .
#     docker tag docker-osx:auto-big-sur sickcodes/docker-osx:auto-big-sur
# }

docker-osx:version () {
    SHORTNAME="${1}"
    docker build ${NO_CACHE} \
        --build-arg BRANCH="${BRANCH}" \
        --build-arg RANKMIRRORS=true \
        --build-arg SHORTNAME="${SHORTNAME}" \
        --build-arg MIRROR_COUNTRY="${MIRROR_COUNTRY}" \
        -f ./Dockerfile \
        -t "docker-osx:${SHORTNAME}" .
    docker tag "docker-osx:${SHORTNAME}" "sickcodes/docker-osx:${SHORTNAME}"
}

reset_docker_hard () {

    tee /etc/docker/daemon.json <<'EOF'
{
    "experimental": true
}
EOF
    systemctl disable --now docker
    systemctl disable --now docker.socket
    systemctl stop docker
    systemctl stop docker.socket
    rm -rf /var/lib/docker
    systemctl enable --now docker
}

warning
tee -a ~/.bashrc <<EOF
export DEBIAN_FRONTEND=noninteractive
export TZ=UTC
EOF
export DEBIAN_FRONTEND=noninteractive
export TZ=UTC
ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime
tee -a /etc/timezone <<< "${TZ}"
apt update -y
apt-get install keyboard-configuration -y
docker -v | grep '\ 20\.\|\ 19\.' || install_docker
yes | apt install -y --no-install-recommends tzdata -y
install_scrotcat
yes | install_vnc
export_display_99
apt install xvfb -y
start_xvfb
# start_vnc
enable_kvm
reset_docker_hard
# echo killall Xvfb
clone_repo "${BRANCH}" "${REPO}"
cd ./Docker-OSX
git pull

for SHORTNAME in "${VERSION_BUILDS[@]}"; do
    docker-osx:version "${SHORTNAME}"
done

docker tag docker-osx:catalina sickcodes/docker-osx:latest

for TEST_BUILD in "${TEST_BUILDS[@]}"; do
    "${TEST_BUILD}"
done

# boot each image and test
bash ./tests/boot-images.sh || exit 1

if [[ "${DOCKER_USERNAME}" ]] && [[ "${DOCKER_PASSWORD}" ]]; then
    docker login --username "${DOCKER_USERNAME}" --password "${DOCKER_PASSWORD}" \
        && for SHORTNAME in "${VERSION_BUILDS[@]}"; do
            docker push "sickcodes/docker-osx:${SHORTNAME}"
        done \
        && touch PUSHED
    docker push sickcodes/docker-osx:naked
    docker push sickcodes/docker-osx:auto
    docker push sickcodes/docker-osx:naked-auto

fi

# connect remotely to your server to use VNC
# ssh -N root@1.1.1.1 -L  5999:127.0.0.1:5999

