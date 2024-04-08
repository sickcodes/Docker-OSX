#!/bin/bash
# Author:       Sick.Codes https://twitter.com/sickcodes
# Contact:      https://github.com/sickcodes, https://sick.codes
# Copyright:    sickcodes (C) 2021
# License:      GPLv3+
# Title:        Docker-OSX (Mac on Docker)
# Repository:   https://github.com/sickcodes/Docker-OSX
# Website:      https://sick.codes
#
# Status:       Used internally to run each image and take screenshots until they match the pngs in this folder.
# 

# note to self: # to get master images, boot each image, then screen shot using DISPLAY=:99 in the test.sh script
# scrot -o high-sierra_master.png
# scrot -o mojave_master.png
# scrot -o catalina_master.png
# scrot -o big-sur_master.png
# scrot -o monterey_master.png
# scrot -o ventura_master.png
# scrot --overwrite --display :99 --file ~/${TEST}.png
# pull off remote server to the tests folder
# REMOTE_SERVER=
# scp root@"${REMOTE_SERVER}":~/*_master.png .

export DISPLAY=:99

TESTS=(
    high-sierra
    mojave
    catalina
    big-sur
    monterey
    ventura
    sonoma
)

# test each docker image to see if they boot to their unique respective installation screens.

for TEST in "${TESTS[@]}"; do
    # run the image detached
    docker run --rm -d \
        --device /dev/kvm \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -e "DISPLAY=:99" \
        "sickcodes/docker-osx:${TEST}"

    # imcat the expected test screenshot to ./"${TEST}_master.txt" 
    imcat ~/Docker-OSX/tests/${TEST}_master.png > ./"${TEST}_master.txt"

    # run until the screen matches the expected screen
    while :; do
        sleep 5
        # screenshot the Xvfb
        scrotcat > ./"${TEST}.txt"
        # diff the low res txt files created from imcat
        diff "./${TEST}.txt" ./"${TEST}_master.txt" && break
        scrotcat
    done

    # kill any containers
    docker kill "$(docker ps --format "{{.ID}}")"
    
    # ensure all containers are dead
    until [[ "$(docker ps | wc -l)" = 1 ]]; do
        sleep 1
        docker ps | xargs docker kill
    done

done

exit 0
