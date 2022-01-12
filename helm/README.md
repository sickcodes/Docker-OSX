# docker-osx

Docker-OSX Helm Chart for Kubernetes.

Project page: https://github.com/sickcodes/docker-osx

Available now on Artifact HUB
[![Artifact HUB](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/docker-osx)](https://artifacthub.io/packages/search?repo=docker-osx)

## Information

This installs `docker-osx` in Kubernetes.

## Features

### What works
1) Setting cpu/memory options
1) Setting VNC password
1) Persistance
1) Setting SMBIOS
1) QEMU/virtio cpu/software gpu changes
1) Toggling Audio
1) Additional port forwarding
1) Kubernetes resource requests/limits
1) Defining version of macOS to install
1) Defining install partition size
1) Defining a different version of macOS
1) Additional QEMU parameters
1) GPU support

### What doesn't
1) Simultaneous VNC + GPU IOMMU (this is a limitation of QEMU :( unfortunately)

## Requirements

* Install [host machine requirements](#INSTALL-QEMU-AND-GPU-IOMMU.md)
    * Ensure you are running QEMU 5.X
* Kubernetes
* Helm v2
* `sickcodes/docker-osx-vnc` Docker image

### Build `sickcodes/docker-osx-vnc`

1) Go back to the root directory
1) Build docker image

    ```
    docker build \
        -t sickcodes/docker-osx-vnc:latest \
        -f helm/Dockerfile .
    ```

    _Please ensure you are using the Dockerfile in the `helm` folder_

_Do not worry about passing `CPU`, `RAM`, etc as they are handled in `values.yaml` now._

### Installation

If planning on using a GPU with IOMMU passthrough it is recommended to configure it first and install macOS--otherwise installing may take a very long time depending on your hardware. Please see `qemu.systemInstaller.downloadDelay`, `qemu.systemInstaller.cache`, `qemu.systemDisk.downloadDelay`, and `qemu.systemDisk.cache` for possibly reducing installation time. It has taken me over three hours to install on some occasions with a NVMe secondary disk without GPU passthrough configured.. 

In `values.yaml`..

1) Set a unique password for `vnc.password`.
1) Re-generate SMBIOS `configPlist.MLB`, `configPlist.SystemSerialNumber`, and `configPlist.SystemUUID` for iServices to work.
1) Update `serverName` to reflect the unique name (in the case more than one deployment is required).
1) Configure `qemu.systemInstaller.downloadDelay` (in a period of seconds) that reflects how long your internet connection will download
    around 500MB (BaseSystem.dmg) + uncompress the file (which took about the same time for me to download on a 1gig internet connection).
1) Set `service.ip` to reflect an IP address of your choice, or use ingress.
1) Update `extraVolumes.hostPath.path` to something useful for you.

Optionally..
1) Install kexts to `kexts.path` and enable.
1) Adjust `openCore.boot.timeout` if desire for macOS to load automatically.
1) Add usb devices with `qemu.usb` or `qemu.extraArgs` if desired.
1) Add more ports for portforwarding services if needed.

Afterwards..

1) Launch your VNC viewer of choice and connect to the IP/hostname you defined + the port `8888` with the password specified
    for `vnc.password`.
1) Install macOS like usual.

_Please note, after you have installed macOS feel free to set `qemu.systemInstaller.downloadDelay` to nothing, as BaseSystem.dmg will be stored in the path defined for `extraVolumes.hostPath.path`_

#### Resources

Please note, resource limits may vary based on hardware. The ones currently defined are ones that worked for me personally.
