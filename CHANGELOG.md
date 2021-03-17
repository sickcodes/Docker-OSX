|Version|Date|Notes|
|---|---|---|
|   |2021-03-17|Add RAM=max and RAM=half to dynamically select ram at runtime (DEFAULT).|
|   |2021-03-06|Change envs to require --envs. Automatically enable --envs if --output-env is used. Same for plists, bootdisks. Fix help ugliness and sanity of generate serial scripts. Fix bootdisk not getting written to persistent file when using NOPICKER=true. NOPICKER=true is overridden by a custom plist now anyway. Remove useless case statements. Allow -e HEADLESS=true as human readable alternative to -e DISPLAY=:99.|
|4.1|2021-03-04|Add `-e MASTER_PLIST_URL` to all images to allow using your own remote plist.|
|   |2021-03-03|Add `WIDTH` and `HEIGHT` to set the x and y resolutions, use in conjuction with serial numbers.|
|   |2021-03-02|Add ADDITIONAL_PORTS, for example `-e ADDITIONAL_PORTS='hostfwd=tcp::23-:23,'`|
|4.0|2021-02-27|Add big-sur support. Use `sickcodes/docker-osx:big-sur` or build using `--build-arg VERSION=11`|
|   |2021-02-26|Change `-e NOPICKER=true` to simply do `sed -i '/^.*InstallMedia.*/d' Launch.sh` and `export BOOTDISK=/home/arch/OSX-KVM/OpenCore-Catalina/OpenCore-nopicker.qcow2`.|
|3.2|2021-02-25|Add a script to generate unique machine serial numbers. Add a script to generate a bootdisk from given serial numbers. Add Linux for libguestfs which allows the docker container to make QEMU bootdisks with specific serial numbers.|
|   |2021-02-21|Add NOPICKER environment variable to ALL images.|
|3.1|2021-02-21|Remove testing repos. Switch to base-devel. We shouldn't be using testing repos in a Dockerfile for light increase in stability. Add the mandatory glibc patch to every pacman until someone upstream fixes it.|
|   |2021-02-07|Add NOPICKER environment variable to :naked image for effortless boot toggling.|
|   |2021-02-07|Add MAC_ADDRESS environment variable.|
|   |2021-02-03|Employ wget --no-verbose to avoid buffer overload in hub.docker.com.|
|   |2021-02-03|Reduce build size.|
|   |2021-01-27|Add OSX_COMMANDS to allow runtime commands on :auto image.|
|   |2021-01-26|Removed most pointless VOLUME build commands.|
|3.0|2021-01-23|Add fast mode boot straight to shell. And -v $PWD/disk.img:/image for all Dockerfiles|
|   |2021-01-22|Add additional helm chart instructions and files.|
|   |2021-01-15|Fix helm initial disk creation process and add installation instructions.|
|   |2021-01-14|Add Helm Chart for Kubernetes support.|
|   |2021-01-08|Use IMAGE_PATH as a variable during envsubst for the full path of mac_hdd_ng.img. In preparation for full auto.|
|   |2021-01-07|Fix sounds errors and sshd missing on latest build.|
|2.7|2021-01-05|Add rankmirrors. Remove gibMacOS. Replace iptables with iptables-nft. Remove libguestfs.|
|   |2020-12-17|Remove unnecessary WORKDIR commands.|
|   |2020-12-16|Reduce image size by cloning OSX-KVM to only 1 depth level. Simplify mkdir && chown to mkdir -m|
|   |2020-10-06|Add the ability to skip the boot screen with ./Launch-nopicker.sh|
|   |2020-10-05|Add vim/vi and nano to the container.|
|2.6|2020-09-26|Increase version.|
|   |2020-09-25|Add some WORKDIR fixes.|
|   |2020-09-24|Clear pacman cache after use to reduce disk size significantly. Add various shell expansions to inline variables. Add set -eu to Launch.sh. Add a shebang to Launch.sh. Add tcg acceleration as a fallback to kvm. Remove need for display **(This change is reverted later)**. Chown /dev/kvm and /dev/snd. Remove --privileged by specifying required passthroughs. Add audio driver arguments to satisfy QEMU **(USB SoundCard recommended)**. Tidy Launch.sh to reduce image by 2.5GB (from 6GB).  |
|2.5|2020-09-20|Critical changes to TigerVNC due to upstream overhaul in TigerVNC.|
|   |2020-09-20|Replace ebtables with iptables-nft.|
|   |2020-08-29|Increase default OSX to 10.15.6 and add SCREEN_SHARE_PORT=5900 ENV variable.|
|   |2020-08-23|Add OSX Screen Sharing port forwarding.|
|   |2020-08-23|Clear /tmp/.X99-lock before starting the VNC version.|
|   |2020-07-02|Refresh the docker-compose file.|
|   |2020-06-22|Add some mirrors to the container.|
|   |2020-06-22|Add more force updates to pacman.|
|   |2020-06-18|Significantly reduce image layer count by concatenating groups of commands.|
|   |2020-06-18|Use the mainline image as the base image for the VNC version.|
|2.0|2020-06-15|Change  default OSX version from 10.14.6 to 10.15.5. Add SSH port forwarding inside the container thru to the guest. Increase default arbitrary disk size to 200G. Force update pacman to prevent old mirror links. Add custom Launch.sh script. Add customizable RAM, SMP, CORES, EXTRA and INTERNAL_SSH_PORT|
|   |2020-06-14|Remove yay|
|   |2020-06-10|Add an OR for attemping to kill non-existent VNC lock files.|
|   |2020-06-09|Instruct gibMacOS to download recovery disk only.|
|   |2020-06-09|Remove VNC lockfile from killed containers preventing a restart.|
|   |2020-06-08|Add docker-compose.yml|
|   |2020-06-07|Add VNC version inside the vnc folder.|
|   |2020-06-05|Remove systemctl enable libvirtd.service/virtlogd.service since Docker doesn't have systemd|
|   |2020-06-04|Removed svm\|vmx via /proc/cpuinfo check which fails on hub.docker.com|
|1.0|2020-06-04|Initial Release|

