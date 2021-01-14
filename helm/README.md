# docker-osx

## Information

This installs `docker-osx` in Kubernetes.

## Features

### What works
1) Setting cpu/memory options
1) Setting VNC password
1) Persistance
1) Setting SMBIOS
1) QEMU/virtio cpu changes
1) Toggling Audio
1) Additional port forwarding
1) Kubernetes resource requests/limits
1) Defining install partition size

### What doesn't/isn't defined
1) Defining a different version of macOS
1) Additional QEMU parameters
1) GPU support

## Requirements

*) Install [host machine requirements](https://github.com/cephasara/Docker-OSX#requirements-kvm-on-the-host)
    *) Ensure you are running QEMU 5.X
*) Kubernetes
*) Helm
*) `sickcodes/docker-osx-vnc` Docker image

### Build `sickcodes/docker-osx-vnc`

1) Go back to the root directory
1) Build docker image

    ```
    docker build \
        -t sickcodes/docker-osx-vnc:latest \
        -f vnc-version/Dockerfile .
    ```

_Do not worry about passing `CPU`, `RAM`, etc as they are handled in `values.yaml` now._