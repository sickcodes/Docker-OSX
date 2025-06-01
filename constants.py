# constants.py

APP_NAME = "Skyscope macOS on PC USB Creator Tool"
DEVELOPER_NAME = "Miss Casey Jay Topojani"
BUSINESS_NAME = "Skyscope Sentinel Intelligence"

MACOS_VERSIONS = {
    "Sonoma": "sonoma",
    "Ventura": "ventura",
    "Monterey": "monterey",
    "Big Sur": "big-sur",
    "Catalina": "catalina"
}

# Docker image base name
DOCKER_IMAGE_BASE = "sickcodes/docker-osx"

# Default Docker command parameters (some will be overridden)
DEFAULT_DOCKER_PARAMS = {
    "--device": "/dev/kvm",
    "-p": "50922:10022", # For SSH access to the container
    "-v": "/tmp/.X11-unix:/tmp/.X11-unix", # For GUI display
    "-e": "DISPLAY=${DISPLAY:-:0.0}",
    "-e GENERATE_UNIQUE": "true", # Crucial for unique OpenCore
    # Sonoma-specific, will need to be conditional or use a base plist
    # that works for all, or fetch the correct one per version.
    # For now, let's use a generic one if possible, or the Sonoma one as a placeholder.
    # The original issue used a Sonoma-specific one.
    "-e CPU": "'Haswell-noTSX'",
    "-e CPUID_FLAGS": "'kvm=on,vendor=GenuineIntel,+invtsc,vmware-cpuid-freq=on'",
    "-e MASTER_PLIST_URL": "'https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-custom-sonoma.plist'"
}

# Parameters that might change per macOS version or user setting
VERSION_SPECIFIC_PARAMS = {
    "Sonoma": {
        "-e SHORTNAME": "sonoma",
        "-e MASTER_PLIST_URL": "'https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-custom-sonoma.plist'"
    },
    "Ventura": {
        "-e SHORTNAME": "ventura",
        "-e MASTER_PLIST_URL": "'https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-custom.plist'" # Needs verification if different for Ventura
    },
    "Monterey": {
        "-e SHORTNAME": "monterey",
        "-e MASTER_PLIST_URL": "'https://raw.githubusercontent.com/sickcodes/osx-serial-generator/master/config-custom.plist'" # Needs verification
    },
    "Big Sur": {
        "-e SHORTNAME": "big-sur",
        # Big Sur might not use/need MASTER_PLIST_URL in the same way or has a different default
    },
    "Catalina": {
        # Catalina might not use/need MASTER_PLIST_URL
    }
}
