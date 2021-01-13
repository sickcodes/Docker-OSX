# docker-osx

## Information

This installs `docker-osx` in Kubernetes.

## Requirements

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