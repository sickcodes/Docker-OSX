# linux_hardware_info.py
import subprocess
import re
import os # For listing /proc/asound
import glob # For wildcard matching in /proc/asound

def _run_command(command: list[str], check_stderr_for_error=False) -> tuple[str, str, int]:
    """
    Helper to run a command and return its stdout, stderr, and return code.
    Args:
        check_stderr_for_error: If True, treat any output on stderr as an error condition for return code.
    Returns:
        (stdout, stderr, return_code)
    """
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=False) # check=False to handle errors manually

        # Some tools (like lspci without -k if no driver) might return 0 but print to stderr.
        # However, for most tools here, a non-zero return code is the primary error indicator.
        # If check_stderr_for_error is True and stderr has content, consider it an error for simplicity here.
        # effective_return_code = process.returncode
        # if check_stderr_for_error and process.stderr and process.returncode == 0:
        #     effective_return_code = 1 # Treat as error

        return process.stdout, process.stderr, process.returncode
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found.")
        return "", f"Command not found: {command[0]}", 127 # Standard exit code for command not found
    except Exception as e:
        print(f"An unexpected error occurred with command {' '.join(command)}: {e}")
        return "", str(e), 1


def get_pci_devices_info() -> list[dict]:
    """
    Gets a list of dictionaries, each containing info about a PCI device,
    focusing on VGA, Audio, and Ethernet controllers using lspci.
    """
    stdout, stderr, return_code = _run_command(["lspci", "-nnk"])
    if return_code != 0 or not stdout:
        print(f"lspci command failed or produced no output. stderr: {stderr}")
        return []

    devices = []
    regex = re.compile(
        r"^[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.\d\s+"
        r"(.+?)\s+"
        r"\[([0-9a-fA-F]{4})\]:\s+" # Class Code in hex, like 0300 for VGA
        r"(.+?)\s+"
        r"\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]"  # Vendor and Device ID
    )

    for line in stdout.splitlines():
        match = regex.search(line)
        if match:
            class_desc = match.group(1).strip()
            # class_code = match.group(2).strip() # Not directly used yet but captured
            full_desc = match.group(3).strip()
            vendor_id = match.group(4).lower()
            device_id = match.group(5).lower()

            device_type = None
            if "VGA compatible controller" in class_desc or "3D controller" in class_desc:
                device_type = "VGA"
            elif "Audio device" in class_desc:
                device_type = "Audio"
            elif "Ethernet controller" in class_desc:
                device_type = "Ethernet"
            elif "Network controller" in class_desc:
                device_type = "Network (Wi-Fi?)"

            if device_type:
                cleaned_desc = full_desc
                # Simple cleanup attempts (can be expanded)
                vendors_to_strip = ["Intel Corporation", "NVIDIA Corporation", "Advanced Micro Devices, Inc. [AMD/ATI]", "AMD [ATI]", "Realtek Semiconductor Co., Ltd."]
                for v_strip in vendors_to_strip:
                    if cleaned_desc.startswith(v_strip):
                        cleaned_desc = cleaned_desc[len(v_strip):].strip()
                        break
                # Remove revision if present at end, e.g. (rev 31)
                cleaned_desc = re.sub(r'\s*\(rev [0-9a-fA-F]{2}\)$', '', cleaned_desc)


                devices.append({
                    "type": device_type,
                    "vendor_id": vendor_id,
                    "device_id": device_id,
                    "description": cleaned_desc.strip() if cleaned_desc else full_desc, # Fallback to full_desc
                    "full_lspci_line": line.strip()
                })
    return devices

def get_cpu_info() -> dict:
    """
    Gets CPU information using lscpu.
    """
    stdout, stderr, return_code = _run_command(["lscpu"])
    if return_code != 0 or not stdout:
        print(f"lscpu command failed or produced no output. stderr: {stderr}")
        return {}

    info = {}
    regex = re.compile(r"^(CPU family|Model name|Vendor ID|Model|Stepping|Flags|Architecture):\s+(.*)$")
    for line in stdout.splitlines():
        match = regex.match(line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            info[key] = value
    return info

def get_audio_codecs() -> list[str]:
    """
    Detects audio codec names by parsing /proc/asound/card*/codec#*.
    Returns a list of unique codec name strings.
    E.g., ["Realtek ALC897", "Intel Kaby Lake HDMI"]
    """
    codec_files = glob.glob("/proc/asound/card*/codec#*")
    if not codec_files:
        # Fallback for systems where codec#* might not exist, try card*/id
        codec_files = glob.glob("/proc/asound/card*/id")

    codecs = set() # Use a set to store unique codec names

    for codec_file_path in codec_files:
        try:
            with open(codec_file_path, 'r') as f:
                content = f.read()
                # For codec#* files
                codec_match = re.search(r"Codec:\s*(.*)", content)
                if codec_match:
                    codecs.add(codec_match.group(1).strip())

                # For card*/id files (often just the card name, but sometimes hints at codec)
                # This is a weaker source but a fallback.
                if "/id" in codec_file_path and not codec_match: # Only if no "Codec:" line found
                     # The content of /id is usually the card name, e.g. "HDA Intel PCH"
                     # This might not be the specific codec chip but can be a hint.
                     # For now, let's only add if it seems like a specific codec name.
                     # This part needs more refinement if used as a primary source.
                     # For now, we prioritize "Codec: " lines.
                     if "ALC" in content or "CS" in content or "AD" in content: # Common codec prefixes
                         codecs.add(content.strip())


        except Exception as e:
            print(f"Error reading or parsing codec file {codec_file_path}: {e}")

    if not codecs and not codec_files: # If no files found at all
        print("No /proc/asound/card*/codec#* or /proc/asound/card*/id files found. Cannot detect audio codecs this way.")

    return sorted(list(codecs))


if __name__ == '__main__':
    print("--- CPU Info ---")
    cpu_info = get_cpu_info()
    if cpu_info:
        for key, value in cpu_info.items():
            print(f"  {key}: {value}")
    else: print("  Could not retrieve CPU info.")

    print("\n--- PCI Devices ---")
    pci_devs = get_pci_devices_info()
    if pci_devs:
        for dev in pci_devs:
            print(f"  Type: {dev['type']}, Vendor: {dev['vendor_id']}, Device: {dev['device_id']}, Desc: {dev['description']}")
    else: print("  No relevant PCI devices found or lspci not available.")

    print("\n--- Audio Codecs ---")
    audio_codecs = get_audio_codecs()
    if audio_codecs:
        for codec in audio_codecs:
            print(f"  Detected Codec: {codec}")
    else:
        print("  No specific audio codecs detected via /proc/asound.")
