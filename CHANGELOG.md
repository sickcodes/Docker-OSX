|Version|Date|Notes|
|---|---|---|
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

