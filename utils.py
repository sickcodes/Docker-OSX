# utils.py

import time
import uuid
from constants import (
    DOCKER_IMAGE_BASE,
    DEFAULT_DOCKER_PARAMS,
    VERSION_SPECIFIC_PARAMS,
    MACOS_VERSIONS
)

# Path to the generated images inside the Docker container
CONTAINER_MACOS_IMG_PATH = "/home/arch/OSX-KVM/mac_hdd_ng.img"
# The OpenCore.qcow2 path can vary if BOOTDISK env var is used.
# The default generated one by the scripts (if not overridden by BOOTDISK) is:
CONTAINER_OPENCORE_QCOW2_PATH = "/home/arch/OSX-KVM/OpenCore/OpenCore.qcow2"


def get_unique_container_name() -> str:
    """Generates a unique Docker container name."""
    return f"skyscope-osx-vm-{uuid.uuid4().hex[:8]}"

def build_docker_command(macos_version_name: str, container_name: str) -> list[str]:
    """
    Builds the docker run command arguments as a list.

    Args:
        macos_version_name: The display name of the macOS version (e.g., "Sonoma").
        container_name: The unique name for the Docker container.

    Returns:
        A list of strings representing the docker command and its arguments.
    """
    if macos_version_name not in MACOS_VERSIONS:
        raise ValueError(f"Unsupported macOS version: {macos_version_name}")

    image_tag = MACOS_VERSIONS[macos_version_name]
    full_image_name = f"{DOCKER_IMAGE_BASE}:{image_tag}"

    # Removed --rm: we need the container to persist for file extraction
    final_command_args = ["docker", "run", "-it", "--name", container_name]

    # Base parameters for the docker command
    run_params = DEFAULT_DOCKER_PARAMS.copy()

    # Override/extend with version-specific parameters
    if macos_version_name in VERSION_SPECIFIC_PARAMS:
        version_specific = VERSION_SPECIFIC_PARAMS[macos_version_name]

        # More robustly handle environment variables (-e)
        # Collect all -e keys from defaults and version-specific
        default_env_vars = {k.split(" ", 1)[1].split("=")[0]: v for k, v in DEFAULT_DOCKER_PARAMS.items() if k.startswith("-e ")}
        version_env_vars = {k.split(" ", 1)[1].split("=")[0]: v for k, v in version_specific.items() if k.startswith("-e ")}

        merged_env_vars = {**default_env_vars, **version_env_vars}

        # Remove all old -e params from run_params before adding merged ones
        keys_to_remove_from_run_params = [k_param for k_param in run_params if k_param.startswith("-e ")]
        for k_rem in keys_to_remove_from_run_params:
            del run_params[k_rem]

        # Add merged env vars back with the "-e VAR_NAME" format for keys
        for env_name, env_val_str in merged_env_vars.items():
            run_params[f"-e {env_name}"] = env_val_str

        # Add other non -e version-specific params
        for k, v in version_specific.items():
            if not k.startswith("-e "):
                run_params[k] = v

    # Construct the command list
    for key, value in run_params.items():
        if key.startswith("-e "):
            # Key is like "-e VARNAME", value is the actual value string like "'data'" or "GENERATE_UNIQUE='true'"
            env_var_name_from_key = key.split(" ", 1)[1] # e.g. GENERATE_UNIQUE or CPU

            # If value string itself contains '=', it's likely the full 'VAR=val' form
            if isinstance(value, str) and '=' in value and value.strip("'").upper().startswith(env_var_name_from_key.upper()):
                # e.g. value is "GENERATE_UNIQUE='true'"
                final_env_val = value.strip("'")
            else:
                # e.g. value is "'true'" for key "-e GENERATE_UNIQUE"
                final_env_val = f"{env_var_name_from_key}={value.strip("'")}"
            final_command_args.extend(["-e", final_env_val])
        else: # for --device, -p, -v
            final_command_args.extend([key, value.strip("'")]) # Strip quotes for safety

    final_command_args.append(full_image_name)

    return final_command_args

def build_docker_cp_command(container_name_or_id: str, container_path: str, host_path: str) -> list[str]:
    """Builds the 'docker cp' command."""
    return ["docker", "cp", f"{container_name_or_id}:{container_path}", host_path]

def build_docker_stop_command(container_name_or_id: str) -> list[str]:
    """Builds the 'docker stop' command."""
    return ["docker", "stop", container_name_or_id]

def build_docker_rm_command(container_name_or_id: str) -> list[str]:
    """Builds the 'docker rm' command."""
    return ["docker", "rm", container_name_or_id]


if __name__ == '__main__':
    # Test the functions
    container_name = get_unique_container_name()
    print(f"Generated container name: {container_name}")

    for version_name_key in MACOS_VERSIONS.keys():
        print(f"Command for {version_name_key}:")
        cmd_list = build_docker_command(version_name_key, container_name)
        print(" ".join(cmd_list))
        print("-" * 20)

    test_container_id = container_name # or an actual ID
    print(f"CP Main Image: {' '.join(build_docker_cp_command(test_container_id, CONTAINER_MACOS_IMG_PATH, './mac_hdd_ng.img'))}")
    print(f"CP OpenCore Image: {' '.join(build_docker_cp_command(test_container_id, CONTAINER_OPENCORE_QCOW2_PATH, './OpenCore.qcow2'))}")
    print(f"Stop Command: {' '.join(build_docker_stop_command(test_container_id))}")
    print(f"Remove Command: {' '.join(build_docker_rm_command(test_container_id))}")

    # Test with a non-existent version
    try:
        build_docker_command("NonExistentVersion", container_name)
    except ValueError as e:
        print(e)
