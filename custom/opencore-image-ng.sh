#!/usr/bin/env bash

# https://github.com/kraxel/imagefish

######################################################################
# defaults

iso=""
img=""
cfg=""

######################################################################
# create work dir

function msg() {
	local txt="$1"
	local bold="\x1b[1m"
	local normal="\x1b[0m"
	echo -e "${bold}### ${txt}${normal}"
}

function do_cleanup() {
	msg "cleaning up ..."
	if test "$GUESTFISH_PID" != ""; then
		guestfish --remote -- exit >/dev/null 2>&1 || true
	fi
	sudo rm -rf "$WORK"
}

WORK="${TMPDIR-/var/tmp}/${0##*/}-$$"
mkdir "$WORK" || exit 1
trap 'do_cleanup' EXIT

BASE="$(dirname $0)"

######################################################################
# parse args

function print_help() {
cat <<EOF
usage: $0 [ options ]
options:
    --iso <iso-image>
    --img <disk-image>
    --cfg <clover-config>
EOF
}

while test "$1" != ""; do
	case "$1" in
	--iso)
		iso="$2"
		shift; shift
		;;
	--img)
		img="$2"
		shift; shift
		;;
	--cfg)
		cfg="$2"
		shift; shift
		;;
	esac
done

######################################################################
# guestfish script helpers

function fish() {
	echo "#" "$@"
	guestfish --remote -- "$@"		|| exit 1
}

function fish_init() {
	local format

	case "$img" in
	*.raw)	format="raw" ;;
	*)	format="qcow2";;
	esac

	msg "creating and adding disk image"
	fish disk-create $img $format 384M
	fish add $img
	fish run
}

function fish_fini() {
	fish umount-all
}

# disabled by @sickcodes to allow unattended image overwrites
######################################################################
# sanity checks

# if test ! -f "$cfg"; then
# 	echo "ERROR: cfg not found: $cfg"
# 	exit 1
# fi
# if test -f "$img"; then
# 	if test "$allow_override" = "yes"; then
# 		rm -f "$img"
# 	else
# 		echo "ERROR: image exists: $img"
# 		exit 1
# 	fi
# fi

######################################################################
# go!

msg "copy files from local folder"
BASE="$(dirname $0)"
cp -a $BASE/EFI $WORK
find "$WORK"

#msg "[debug] list drivers in EFI/OC"
#(cd $WORK/EFI/OC; find driver* -print)

export LIBGUESTFS_BACKEND=direct
eval $(guestfish --listen)
if test "$GUESTFISH_PID" = ""; then
	echo "ERROR: starting guestfish failed"
	exit 1
fi

fish_init

msg "partition disk image"
fish part-init /dev/sda gpt
fish part-add /dev/sda p 2048 300000
fish part-add /dev/sda p 302048 -2048
fish part-set-gpt-type /dev/sda 1 C12A7328-F81F-11D2-BA4B-00A0C93EC93B
fish part-set-bootable /dev/sda 1 true
fish mkfs vfat /dev/sda1 label:EFI
fish mkfs vfat /dev/sda2 label:OpenCore
fish mount /dev/sda2 /
fish mkdir /ESP
fish mount /dev/sda1 /ESP

msg "copy files to disk image"
cp -v "$cfg" $WORK/config.plist
fish mkdir /ESP/EFI
fish mkdir /ESP/EFI/OC
fish mkdir /ESP/EFI/OC/Kexts
fish mkdir /ESP/EFI/OC/ACPI
fish mkdir /ESP/EFI/OC/Resources
fish mkdir /ESP/EFI/OC/Tools
fish copy-in $WORK/EFI/BOOT /ESP/EFI
fish copy-in $WORK/EFI/OC/OpenCore.efi /ESP/EFI/OC
fish copy-in $WORK/EFI/OC/Drivers /ESP/EFI/OC/
fish copy-in $WORK/EFI/OC/Kexts /ESP/EFI/OC/
fish copy-in $WORK/EFI/OC/ACPI /ESP/EFI/OC/
fish copy-in $BASE/resources/OcBinaryData/Resources /ESP/EFI/OC/
fish copy-in $WORK/EFI/OC/Tools /ESP/EFI/OC/

# Note
fish copy-in startup.nsh /

BASE="$(dirname $0)"
fish copy-in "$WORK/config.plist"               /ESP/EFI/OC/

fish find /ESP/
fish_fini
