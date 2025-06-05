# plist_modifier.py
import plistlib
import platform
import shutil
import os
import re # For parsing codec names

if platform.system() == "Linux":
    try:
        from linux_hardware_info import get_pci_devices_info, get_cpu_info, get_audio_codecs
    except ImportError:
        print("Warning: linux_hardware_info.py not found. Plist enhancement will be limited.")
        get_pci_devices_info = lambda: []
        get_cpu_info = lambda: {}
        get_audio_codecs = lambda: []
else:
    print(f"Warning: Hardware info gathering not implemented for {platform.system()} in plist_modifier.")
    get_pci_devices_info = lambda: []
    get_cpu_info = lambda: {}
    get_audio_codecs = lambda: [] # Dummy function for non-Linux

# --- Mappings ---
# Values are typically byte-swapped for device-id and some ig-platform-id representations in OpenCore
# For AAPL,ig-platform-id, the first two bytes are often the device-id (swapped), last two are platform related.
# Example: UHD 630 (Desktop Coffee Lake) device-id 0x3E9B -> data <9B3E0000>
#          ig-platform-id commonly 0x3E9B0007 -> data <07009B3E> (or other variants)

INTEL_IGPU_DEFAULTS = {
    # Coffee Lake Desktop (UHD 630) - Common
    "8086:3e9b": {"AAPL,ig-platform-id": b"\x07\x00\x9B\x3E", "device-id": b"\x9B\x3E\x00\x00", "framebuffer-patch-enable": b"\x01\x00\x00\x00"},
    # Kaby Lake Desktop (HD 630) - Common
    "8086:5912": {"AAPL,ig-platform-id": b"\x05\x00\x12\x59", "device-id": b"\x12\x59\x00\x00", "framebuffer-patch-enable": b"\x01\x00\x00\x00"},
    # Skylake Desktop (HD 530) - Common
    "8086:1912": {"AAPL,ig-platform-id": b"\x00\x00\x12\x19", "device-id": b"\x12\x19\x00\x00", "framebuffer-patch-enable": b"\x01\x00\x00\x00"},

    # Alder Lake-S Desktop (UHD 730/750/770) - device-id often needs to be accurate
    "8086:4680": {"AAPL,ig-platform-id": b"\x0A\x00\x9B\x46", "device-id": b"\x80\x46\x00\x00", "enable-hdmi20": b"\x01\x00\x00\x00"}, # e.g. i9-12900K UHD 770 (0x4680) -> common platform ID for iGPU only
    "8086:4690": {"AAPL,ig-platform-id": b"\x0A\x00\x9B\x46", "device-id": b"\x90\x46\x00\x00", "enable-hdmi20": b"\x01\x00\x00\x00"}, # e.g. i5-12600K UHD 770 (0x4690)
    "8086:4692": {"AAPL,ig-platform-id": b"\x0A\x00\x9B\x46", "device-id": b"\x92\x46\x00\x00", "enable-hdmi20": b"\x01\x00\x00\x00"}, # e.g. i5-12400 UHD 730 (0x4692)
    # Alternative Alder Lake platform-id (often when dGPU is primary)
    "8086:4680_dgpu": {"AAPL,ig-platform-id": b"\x04\x00\x12\x40", "device-id": b"\x80\x46\x00\x00", "enable-hdmi20": b"\x01\x00\x00\x00"}, # Using a suffix for internal logic, not a real PCI ID
    "8086:4690_dgpu": {"AAPL,ig-platform-id": b"\x04\x00\x12\x40", "device-id": b"\x90\x46\x00\x00", "enable-hdmi20": b"\x01\x00\x00\x00"},
    "8086:4692_dgpu": {"AAPL,ig-platform-id": b"\x04\x00\x12\x40", "device-id": b"\x92\x46\x00\x00", "enable-hdmi20": b"\x01\x00\x00\x00"},
}
INTEL_IGPU_PCI_PATH = "PciRoot(0x0)/Pci(0x2,0x0)"

# Primary keys are now Codec Names. PCI IDs are secondary/fallback.
AUDIO_LAYOUTS = {
    # Codec Names (Prefer these) - Extracted from "Codec: Realtek ALCXXX" or similar
    "Realtek ALC221": 11, "Realtek ALC233": 11, "Realtek ALC235": 28,
    "Realtek ALC255": 11, "Realtek ALC256": 11, "Realtek ALC257": 11,
    "Realtek ALC269": 11, "Realtek ALC271": 11, "Realtek ALC282": 11,
    "Realtek ALC283": 11, "Realtek ALC285": 11, "Realtek ALC289": 11,
    "Realtek ALC295": 11,
    "Realtek ALC662": 5, "Realtek ALC671": 11,
    "Realtek ALC887": 7, "Realtek ALC888": 7,
    "Realtek ALC892": 1, "Realtek ALC897": 11, # Common, 11 often works
    "Realtek ALC1150": 1,
    "Realtek ALC1200": 7,
    "Realtek ALC1220": 7, "Realtek ALC1220-VB": 7, # VB variant often uses same layouts
    "Conexant CX20756": 3, # Example Conexant
    # Fallback PCI IDs for generic Intel HDA controllers if codec name not matched
    "pci_8086:a170": 1, # Sunrise Point-H HD Audio
    "pci_8086:a2f0": 1, # Series 200 HD Audio (Kaby Lake)
    "pci_8086:a348": 3, # Cannon Point-LP HD Audio
    "pci_8086:f0c8": 3, # Comet Lake HD Audio (Series 400)
    "pci_8086:43c8": 11,# Tiger Lake-H HD Audio (Series 500)
    "pci_8086:7ad0": 11,# Alder Lake PCH-P HD Audio
}
AUDIO_PCI_PATH_FALLBACK = "PciRoot(0x0)/Pci(0x1f,0x3)"

ETHERNET_KEXT_MAP = { # vendor_id:device_id -> kext_name
    "8086:15b8": "IntelMausi.kext", "8086:153a": "IntelMausi.kext", "8086:10f0": "IntelMausi.kext",
    "8086:15be": "IntelMausi.kext", "8086:0d4f": "IntelMausi.kext", "8086:15b7": "IntelMausi.kext", # I219-V(3)
    "8086:1a1c": "IntelMausi.kext", # Comet Lake-S vPro (I219-LM)
    "10ec:8168": "RealtekRTL8111.kext", "10ec:8111": "RealtekRTL8111.kext",
    "10ec:2502": "LucyRTL8125Ethernet.kext", # Realtek RTL8125 2.5GbE
    "10ec:2600": "LucyRTL8125Ethernet.kext", # Realtek RTL8125B 2.5GbE
    "8086:15ec": "AppleIntelI210Ethernet.kext", # I225-V (Often needs AppleIGB.kext or specific patches)
    "8086:15f3": "AppleIntelI210Ethernet.kext", # I225-V / I226-V
    "14e4:1686": "AirportBrcmFixup.kext", # Placeholder for Broadcom Wi-Fi, actual kext depends on model
}


def enhance_config_plist(plist_path: str, target_macos_version_name: str, progress_callback=None) -> bool:
    def _report(msg):
        if progress_callback: progress_callback(f"[PlistModifier] {msg}")
        else: print(f"[PlistModifier] {msg}")
    # ... (backup logic same as before) ...
    _report(f"Starting config.plist enhancement for: {plist_path}"); _report(f"Target macOS version: {target_macos_version_name.lower()}")
    if not os.path.exists(plist_path): _report(f"Error: Plist file not found at {plist_path}"); return False
    backup_plist_path = plist_path + ".backup"
    try: shutil.copy2(plist_path, backup_plist_path); _report(f"Created backup: {backup_plist_path}")
    except Exception as e: _report(f"Error creating backup for {plist_path}: {e}. Proceeding cautiously.")

    config_data = {};
    try:
        with open(plist_path, 'rb') as f: config_data = plistlib.load(f)
    except Exception as e: _report(f"Error loading plist {plist_path}: {e}"); return False

    pci_devices = []; cpu_info = {}; audio_codecs_detected = []
    if platform.system() == "Linux":
        pci_devices = get_pci_devices_info(); cpu_info = get_cpu_info(); audio_codecs_detected = get_audio_codecs()
        if not pci_devices: _report("Warning: Could not retrieve PCI hardware info on Linux.")
        if not audio_codecs_detected: _report("Warning: Could not detect specific audio codecs on Linux.")
    else: _report("Hardware detection for plist enhancement Linux-host only. Skipping hardware-specific mods.")

    dev_props = config_data.setdefault("DeviceProperties", {}).setdefault("Add", {})
    kernel_add = config_data.setdefault("Kernel", {}).setdefault("Add", [])
    nvram_add = config_data.setdefault("NVRAM", {}).setdefault("Add", {})
    boot_args_uuid = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
    boot_args_section = nvram_add.setdefault(boot_args_uuid, {})
    current_boot_args_str = boot_args_section.get("boot-args", ""); boot_args = set(current_boot_args_str.split())
    modified_plist = False

    # 1. Intel iGPU
    intel_igpu_on_host = next((dev for dev in pci_devices if dev['type'] == 'VGA' and dev['vendor_id'] == '8086'), None)
    dgpu_present = any(dev['type'] == 'VGA' and dev['vendor_id'] != '8086' for dev in pci_devices)

    if intel_igpu_on_host:
        lookup_key = f"{intel_igpu_on_host['vendor_id']}:{intel_igpu_on_host['device_id']}"
        # For Alder Lake, if a dGPU is also present, a different platform-id might be preferred.
        if lookup_key.startswith("8086:46") and dgpu_present: # Basic check for Alder Lake iGPU + dGPU
            lookup_key_dgpu = f"{lookup_key}_dgpu"
            if lookup_key_dgpu in INTEL_IGPU_DEFAULTS:
                lookup_key = lookup_key_dgpu
                _report(f"Intel Alder Lake iGPU ({intel_igpu_on_host['description']}) detected with a dGPU. Using dGPU-specific properties if available.")

        if lookup_key in INTEL_IGPU_DEFAULTS:
            _report(f"Applying properties for Intel iGPU: {intel_igpu_on_host['description']} ({lookup_key}).")
            igpu_path_properties = dev_props.setdefault(INTEL_IGPU_PCI_PATH, {})
            for key, value in INTEL_IGPU_DEFAULTS[lookup_key].items():
                if igpu_path_properties.get(key) != value: igpu_path_properties[key] = value; _report(f"  Set {INTEL_IGPU_PCI_PATH} -> {key}"); modified_plist = True
        else: _report(f"Found Intel iGPU: {intel_igpu_on_host['description']} ({lookup_key}) but no default properties in map.")

    # 2. Audio Enhancement - Prioritize detected codec name
    audio_device_pci_path_to_patch = AUDIO_PCI_PATH_FALLBACK # Default
    audio_layout_set = False
    if audio_codecs_detected:
        _report(f"Detected audio codecs: {audio_codecs_detected}")
        for codec_name_full in audio_codecs_detected:
            # Try to match known parts of codec names, e.g. "Realtek ALC897" from "Codec: Realtek ALC897"
            # Or "ALC897" if that's how it's stored in AUDIO_LAYOUTS keys
            for known_codec_key, layout_id in AUDIO_LAYOUTS.items():
                if not known_codec_key.startswith("pci_"): # Ensure we are checking codec names, not PCI IDs
                    # Simple substring match or more specific regex
                    # Example: "Realtek ALC255" should match "ALC255" if key is "ALC255"
                    # Or if key is "Realtek ALC255" it matches directly
                    # For "Codec: Realtek ALC255" we might want to extract "Realtek ALC255"

                    # Attempt to extract the core codec part (e.g., "ALC255", "CX20756")
                    simple_codec_name_match = re.search(r"(ALC\d{3,4}(?:-VB)?|CX\d{4,})", codec_name_full, re.IGNORECASE)
                    simple_codec_name = simple_codec_name_match.group(1) if simple_codec_name_match else None

                    if (known_codec_key in codec_name_full) or \
                       (simple_codec_name and known_codec_key in simple_codec_name) or \
                       (known_codec_key.replace("Realtek ", "") in codec_name_full.replace("Realtek ", "")): # Try matching without "Realtek "

                        _report(f"Matched Audio Codec: '{codec_name_full}' (using key '{known_codec_key}'). Setting layout-id to {layout_id}.")
                        audio_path_properties = dev_props.setdefault(audio_device_pci_path_to_patch, {})
                        new_layout_data = plistlib.Data(layout_id.to_bytes(1, 'little'))
                        if audio_path_properties.get("layout-id") != new_layout_data:
                            audio_path_properties["layout-id"] = new_layout_data; _report(f"  Set {audio_device_pci_path_to_patch} -> layout-id = {layout_id}"); modified_plist = True
                        audio_layout_set = True; break
            if audio_layout_set: break

    if not audio_layout_set: # Fallback to PCI ID of audio controller
        _report("No specific audio codec match found or no codecs detected. Falling back to PCI ID for audio controller.")
        for dev in pci_devices:
            if dev['type'] == 'Audio':
                lookup_key = f"pci_{dev['vendor_id']}:{dev['device_id']}" # PCI ID keys are prefixed
                if lookup_key in AUDIO_LAYOUTS:
                    layout_id = AUDIO_LAYOUTS[lookup_key]
                    _report(f"Found Audio device (PCI): {dev['description']}. Setting layout-id to {layout_id} via PCI ID map.")
                    audio_path_properties = dev_props.setdefault(audio_device_pci_path_to_patch, {})
                    new_layout_data = plistlib.Data(layout_id.to_bytes(1, 'little'))
                    if audio_path_properties.get("layout-id") != new_layout_data:
                         audio_path_properties["layout-id"] = new_layout_data; _report(f"  Set {audio_device_pci_path_to_patch} -> layout-id = {layout_id}"); modified_plist = True
                    audio_layout_set = True; break

    if audio_layout_set: # Common action if any layout was set
        for kext_entry in kernel_add:
            if isinstance(kext_entry, dict) and kext_entry.get("BundlePath") == "AppleALC.kext":
                if not kext_entry.get("Enabled", False): kext_entry["Enabled"] = True; _report("  Ensured AppleALC.kext is enabled."); modified_plist = True
                break

    # 3. Ethernet Kext Enablement (same logic as before)
    for dev in pci_devices:
        if dev['type'] == 'Ethernet':
            lookup_key = f"{dev['vendor_id']}:{dev['device_id']}"
            if lookup_key in ETHERNET_KEXT_MAP:
                kext_name = ETHERNET_KEXT_MAP[lookup_key]; _report(f"Found Ethernet: {dev['description']}. Ensuring {kext_name} is enabled.")
                kext_modified_in_plist = False
                for kext_entry in kernel_add:
                    if isinstance(kext_entry, dict) and kext_entry.get("BundlePath") == kext_name:
                        if not kext_entry.get("Enabled", False): kext_entry["Enabled"] = True; _report(f"  Enabled {kext_name}."); modified_plist = True
                        else: _report(f"  {kext_name} already enabled.")
                        kext_modified_in_plist = True; break
                if not kext_modified_in_plist: _report(f"  Warning: {kext_name} for {dev['description']} not in Kernel->Add list of config.plist.")
                break

    # 4. NVIDIA GTX 970 Specific Adjustments
    gtx_970_present = any(dev['vendor_id'] == '10de' and dev['device_id'] == '13c2' for dev in pci_devices)
    if gtx_970_present:
        _report("NVIDIA GTX 970 detected.")
        high_sierra_and_older_versions = ["high sierra", "sierra", "el capitan"]
        is_high_sierra_or_older_target = target_macos_version_name.lower() in high_sierra_and_older_versions

        original_boot_args_set = set(boot_args)

        if is_high_sierra_or_older_target:
            boot_args.add('nvda_drv=1'); boot_args.discard('nv_disable=1')
            _report("  Configured for NVIDIA Web Drivers (High Sierra or older target).")
        else: # Mojave and newer
            boot_args.discard('nvda_drv=1')
            if intel_igpu_on_host:
                boot_args.add('nv_disable=1')
                _report(f"  Added nv_disable=1 for {target_macos_version_name} to prioritize detected host iGPU over GTX 970.")
            else:
                boot_args.discard('nv_disable=1')
                _report(f"  GTX 970 is likely only GPU. `nv_disable=1` not forced for {target_macos_version_name}. Basic display expected.")
        if boot_args != original_boot_args_set: modified_plist = True

    final_boot_args_str = ' '.join(sorted(list(boot_args)))
    if boot_args_section.get('boot-args') != final_boot_args_str:
        boot_args_section['boot-args'] = final_boot_args_str
        _report(f"Updated boot-args to: '{final_boot_args_str}'")
        modified_plist = True

    if not modified_plist:
         _report("No changes made to config.plist based on detected hardware or existing settings were different from defaults.")
         # If no hardware changes on non-Linux, this is expected.
         if platform.system() != "Linux" and not pci_devices : return True # No error, just no action

    try:
        with open(plist_path, 'wb') as f:
            plistlib.dump(config_data, f, sort_keys=True, fmt=plistlib.PlistFormat.XML) # Ensure XML format
        _report(f"Successfully saved config.plist to {plist_path}")
        return True
    except Exception as e: # ... (restore backup logic same as before)
        _report(f"Error saving modified plist file {plist_path}: {e}")
        try: shutil.copy2(backup_plist_path, plist_path); _report("Restored backup successfully.")
        except Exception as backup_error: _report(f"CRITICAL: FAILED TO RESTORE BACKUP. {plist_path} may be corrupt. Backup is at {backup_plist_path}. Error: {backup_error}")
        return False

# if __name__ == '__main__': (Keep the same test block as before, ensure dummy data for kexts is complete)
if __name__ == '__main__':
    print("Plist Modifier Standalone Test") # ... (rest of test block as in previous version)
    dummy_plist_path = "test_config.plist"
    dummy_data = {
        "DeviceProperties": {"Add": {}},
        "Kernel": {"Add": [
            {"Arch": "Any", "BundlePath": "Lilu.kext", "Comment": "Lilu", "Enabled": True, "ExecutablePath": "Contents/MacOS/Lilu", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"},
            {"Arch": "Any", "BundlePath": "WhateverGreen.kext", "Comment": "WG", "Enabled": True, "ExecutablePath": "Contents/MacOS/WhateverGreen", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"},
            {"Arch": "Any", "BundlePath": "AppleALC.kext", "Comment": "AppleALC", "Enabled": False, "ExecutablePath": "Contents/MacOS/AppleALC", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"},
            {"Arch": "Any", "BundlePath": "IntelMausi.kext", "Comment": "IntelMausi", "Enabled": False, "ExecutablePath": "Contents/MacOS/IntelMausi", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"},
            {"Arch": "Any", "BundlePath": "RealtekRTL8111.kext", "Comment": "Realtek", "Enabled": False, "ExecutablePath": "Contents/MacOS/RealtekRTL8111", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"},
            {"Arch": "Any", "BundlePath": "LucyRTL8125Ethernet.kext", "Comment": "LucyRealtek", "Enabled": False, "ExecutablePath": "Contents/MacOS/LucyRTL8125Ethernet", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"},
        ]},
        "NVRAM": {"Add": {"7C436110-AB2A-4BBB-A880-FE41995C9F82": {"boot-args": "-v debug=0x100"}}}
    }
    with open(dummy_plist_path, 'wb') as f: plistlib.dump(dummy_data, f)
    print(f"Created dummy {dummy_plist_path} for testing.")

    original_get_pci = get_pci_devices_info; original_get_cpu = get_cpu_info; original_get_audio_codecs = get_audio_codecs
    if platform.system() != "Linux":
        print("Mocking hardware info for non-Linux.")
        get_pci_devices_info = lambda: [
            {'type': 'VGA', 'vendor_id': '8086', 'device_id': '4680', 'description': 'Alder Lake UHD 770', 'full_lspci_line':''},
            {'type': 'Audio', 'vendor_id': '8086', 'device_id': '7ad0', 'description': 'Alder Lake PCH-P HD Audio', 'full_lspci_line':''},
            {'type': 'Ethernet', 'vendor_id': '10ec', 'device_id': '2502', 'description': 'Realtek RTL8125', 'full_lspci_line':''},
        ]
        get_cpu_info = lambda: {"Model name": "12th Gen Intel(R) Core(TM) i7-12700K", "Flags": "avx avx2"}
        get_audio_codecs = lambda: ["Realtek ALC1220", "Intel Alder Lake-S HDMI"]


    print("\n--- Testing with Sonoma (should enable iGPU, audio [ALC1220 layout 7], ethernet [LucyRTL8125]) ---")
    success_sonoma = enhance_config_plist(dummy_plist_path, "Sonoma", print)
    print(f"Plist enhancement for Sonoma {'succeeded' if success_sonoma else 'failed'}.")
    if success_sonoma:
        with open(dummy_plist_path, 'rb') as f: modified_data = plistlib.load(f)
        print(f"  Sonoma boot-args: {modified_data.get('NVRAM',{}).get('Add',{}).get(boot_args_uuid,{}).get('boot-args')}")
        print(f"  Sonoma iGPU props: {modified_data.get('DeviceProperties',{}).get('Add',{}).get(INTEL_IGPU_PCI_PATH)}")
        print(f"  Sonoma Audio props: {modified_data.get('DeviceProperties',{}).get('Add',{}).get(AUDIO_PCI_PATH_FALLBACK)}")
        for kext in modified_data.get("Kernel",{}).get("Add",[]):
            if "LucyRTL8125Ethernet.kext" in kext.get("BundlePath",""): print(f"  LucyRTL8125Ethernet.kext Enabled: {kext.get('Enabled')}")
            if "AppleALC.kext" in kext.get("BundlePath",""): print(f"  AppleALC.kext Enabled: {kext.get('Enabled')}")


    if platform.system() != "Linux":
        get_pci_devices_info = original_get_pci; get_cpu_info = original_get_cpu; get_audio_codecs = original_get_audio_codecs

    if os.path.exists(dummy_plist_path): os.remove(dummy_plist_path)
    if os.path.exists(dummy_plist_path + ".backup"): os.remove(dummy_plist_path + ".backup")
    print(f"Cleaned up dummy plist and backup.")
