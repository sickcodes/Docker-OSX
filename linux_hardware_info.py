# linux_hardware_info.py
import subprocess
import re

def _run_command(command: list[str]) -> str:
    """Helper to run a command and return its stdout."""
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        return process.stdout
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found. Is 'pciutils' (for lspci) installed?")
        return ""
    except subprocess.CalledProcessError as e:
        print(f"Error executing {' '.join(command)}: {e.stderr}")
        return ""
    except Exception as e:
        print(f"An unexpected error occurred with command {' '.join(command)}: {e}")
        return ""

def get_pci_devices_info() -> list[dict]:
    """
    Gets a list of dictionaries, each containing info about a PCI device,
    focusing on VGA, Audio, and Ethernet controllers.
    Output format for relevant devices:
    {'type': 'VGA', 'vendor_id': '10de', 'device_id': '13c2', 'description': 'NVIDIA GTX 970'}
    {'type': 'Audio', 'vendor_id': '8086', 'device_id': 'a170', 'description': 'Intel Sunrise Point-H HD Audio'}
    {'type': 'Ethernet', 'vendor_id': '8086', 'device_id': '15b8', 'description': 'Intel Ethernet Connection I219-V'}
    """
    output = _run_command(["lspci", "-nnk"])
    if not output:
        return []

    devices = []
    # Regex to capture device type (from description), description, and [vendor:device]
    # Example line: 01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GM204 [GeForce GTX 970] [10de:13c2] (rev a1)
    # Example line: 00:1f.3 Audio device [0403]: Intel Corporation Sunrise Point-H HD Audio [8086:a170] (rev 31)
    # Example line: 00:1f.6 Ethernet controller [0200]: Intel Corporation Ethernet Connection (2) I219-V [8086:15b8] (rev 31)

    # More robust regex:
    # It captures the class description (like "VGA compatible controller", "Audio device")
    # and the main device description (like "NVIDIA Corporation GM204 [GeForce GTX 970]")
    # and the vendor/device IDs like "[10de:13c2]"
    regex = re.compile(
        r"^[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.\d\s+"  # PCI Address (e.g., 01:00.0 )
        r"(.+?)\s+"                              # Class Description (e.g., "VGA compatible controller")
        r"\[[0-9a-fA-F]{4}\]:\s+"                 # PCI Class Code (e.g., [0300]: )
        r"(.+?)\s+"                              # Full Device Description (e.g., "NVIDIA Corporation GM204 [GeForce GTX 970]")
        r"\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]"  # Vendor and Device ID (e.g., [10de:13c2])
    )

    for line in output.splitlines():
        match = regex.search(line)
        if match:
            class_desc = match.group(1).strip()
            full_desc = match.group(2).strip()
            vendor_id = match.group(3).lower()
            device_id = match.group(4).lower()

            device_type = None
            if "VGA compatible controller" in class_desc or "3D controller" in class_desc:
                device_type = "VGA"
            elif "Audio device" in class_desc:
                device_type = "Audio"
            elif "Ethernet controller" in class_desc:
                device_type = "Ethernet"
            elif "Network controller" in class_desc: # Could be Wi-Fi
                device_type = "Network (Wi-Fi?)"


            if device_type:
                # Try to get a cleaner description if possible, removing vendor name if it's at the start
                # e.g. "Intel Corporation Ethernet Connection (2) I219-V" -> "Ethernet Connection (2) I219-V"
                # This is a simple attempt.
                cleaned_desc = full_desc
                if full_desc.lower().startswith("intel corporation "):
                    cleaned_desc = full_desc[len("intel corporation "):]
                elif full_desc.lower().startswith("nvidia corporation "):
                    cleaned_desc = full_desc[len("nvidia corporation "):]
                elif full_desc.lower().startswith("advanced micro devices, inc.") or full_desc.lower().startswith("amd"):
                    # Handle different AMD namings
                    if full_desc.lower().startswith("advanced micro devices, inc."):
                        cleaned_desc = re.sub(r"Advanced Micro Devices, Inc\.\s*\[AMD/ATI\]\s*", "", full_desc, flags=re.IGNORECASE)
                    else: # Starts with AMD
                         cleaned_desc = re.sub(r"AMD\s*\[ATI\]\s*", "", full_desc, flags=re.IGNORECASE)
                elif full_desc.lower().startswith("realtek semiconductor co., ltd."):
                     cleaned_desc = full_desc[len("realtek semiconductor co., ltd. "):]


                devices.append({
                    "type": device_type,
                    "vendor_id": vendor_id,
                    "device_id": device_id,
                    "description": cleaned_desc.strip(),
                    "full_lspci_line": line.strip() # For debugging or more info
                })
    return devices

def get_cpu_info() -> dict:
    """
    Gets CPU information using lscpu.
    Returns a dictionary with 'Model name', 'Vendor ID', 'CPU family', 'Model', 'Stepping', 'Flags'.
    """
    output = _run_command(["lscpu"])
    if not output:
        return {}

    info = {}
    # Regex to capture key-value pairs from lscpu output
    # Handles spaces in values for "Model name"
    regex = re.compile(r"^(CPU family|Model name|Vendor ID|Model|Stepping|Flags):\s+(.*)$")
    for line in output.splitlines():
        match = regex.match(line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            info[key] = value
    return info


if __name__ == '__main__':
    print("--- PCI Devices ---")
    pci_devs = get_pci_devices_info()
    if pci_devs:
        for dev in pci_devs:
            print(f"  Type: {dev['type']}")
            print(f"    Vendor ID: {dev['vendor_id']}")
            print(f"    Device ID: {dev['device_id']}")
            print(f"    Description: {dev['description']}")
            # print(f"    Full Line: {dev['full_lspci_line']}")
    else:
        print("  No relevant PCI devices found or lspci not available.")

    print("\n--- CPU Info ---")
    cpu_info = get_cpu_info()
    if cpu_info:
        for key, value in cpu_info.items():
            print(f"  {key}: {value}")
    else:
        print("  Could not retrieve CPU info or lscpu not available.")
