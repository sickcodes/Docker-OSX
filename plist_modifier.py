# plist_modifier.py
import plistlib
import platform
import shutil # For backup
import os # For path operations

# Attempt to import hardware info, will only work if run in an environment
# where linux_hardware_info.py is accessible and on Linux.
if platform.system() == "Linux":
    try:
        from linux_hardware_info import get_pci_devices_info, get_cpu_info
    except ImportError:
        print("Warning: linux_hardware_info.py not found. Plist enhancement will be limited.")
        get_pci_devices_info = lambda: [] # Dummy function
        get_cpu_info = lambda: {}       # Dummy function
else: # For other OS, create dummy functions so the rest of the module can be parsed
    print(f"Warning: Hardware info gathering not implemented for {platform.system()} in plist_modifier.")
    get_pci_devices_info = lambda: []
    get_cpu_info = lambda: {}

# --- Illustrative Mappings (Proof of Concept) ---
# Keys are VENDOR_ID:DEVICE_ID (lowercase)
INTEL_IGPU_DEFAULTS = {
    # Coffee Lake Desktop (UHD 630)
    "8086:3e9b": {"AAPL,ig-platform-id": b"\x07\x00\x9B\x3E", "device-id": b"\x9B\x3E\x00\x00", "framebuffer-patch-enable": b"\x01\x00\x00\x00"},
    # Kaby Lake Desktop (HD 630)
    "8086:5912": {"AAPL,ig-platform-id": b"\x05\x00\x12\x59", "device-id": b"\x12\x59\x00\x00", "framebuffer-patch-enable": b"\x01\x00\x00\x00"},
    # Skylake Desktop (HD 530)
    "8086:1912": {"AAPL,ig-platform-id": b"\x00\x00\x12\x19", "device-id": b"\x12\x19\x00\x00", "framebuffer-patch-enable": b"\x01\x00\x00\x00"},
}
INTEL_IGPU_PCI_PATH = "PciRoot(0x0)/Pci(0x2,0x0)"

AUDIO_LAYOUTS = {
    # Intel HDA - common controllers, layout 1 is a frequent default
    "8086:a170": 1, # Sunrise Point-H HD Audio
    "8086:a2f0": 1, # Series 200 HD Audio
    "8086:a348": 3, # Cannon Point-LP HD Audio
    "8086:f0c8": 3, # Comet Lake HD Audio
    # Realtek Codecs (often on Intel HDA controller, actual codec detection is harder)
    # If a Realtek PCI ID is found for audio, one of these layouts might work.
    # This map is simplified; usually, you detect the codec name (e.g. ALC255, ALC892)
    "10ec:0255": 3, # ALC255 Example
    "10ec:0892": 1, # ALC892 Example
}
AUDIO_PCI_PATH_FALLBACK = "PciRoot(0x0)/Pci(0x1f,0x3)" # Common, but needs verification

ETHERNET_KEXT_MAP = {
    "8086:15b8": "IntelMausi.kext",      # Intel I219-V
    "8086:153a": "IntelMausi.kext",      # Intel I217-V
    "8086:10f0": "IntelMausi.kext",      # Intel 82579LM
    "10ec:8168": "RealtekRTL8111.kext",  # Realtek RTL8111/8168
    "10ec:8111": "RealtekRTL8111.kext",
    "14e4:1686": "AirportBrcmFixup.kext", # Example Broadcom Wi-Fi (though kext name might be BrcmPatchRAM related)
                                         # Proper Ethernet kext for Broadcom depends on model e.g. AppleBCM5701Ethernet.kext
}


def _get_pci_path_for_device(pci_devices, target_vendor_id, target_device_id_prefix):
    # This is a placeholder. A real implementation would need to parse lspci's bus info (00:1f.3)
    # and convert that to an OpenCore PciRoot string. For now, uses fallbacks.
    # Example: lspci output "00:1f.3 Audio device [0403]: Intel Corporation Sunrise Point-H HD Audio [8086:a170] (rev 31)"
    # PciRoot(0x0)/Pci(0x1f,0x3)
    # For now, this function is not fully implemented and we'll use hardcoded common paths.
    return None


def enhance_config_plist(plist_path: str, target_macos_version_name: str, progress_callback=None) -> bool:
    """
    Loads a config.plist, gathers hardware info (Linux only for now),
    applies targeted enhancements, and saves it back.
    Args:
        plist_path: Path to the config.plist file.
        target_macos_version_name: e.g., "Sonoma", "High Sierra". Used for version-specific logic.
        progress_callback: Optional function to report progress.
    Returns:
        True if successful, False otherwise.
    """
    def _report(msg):
        if progress_callback: progress_callback(f"[PlistModifier] {msg}")
        else: print(f"[PlistModifier] {msg}")

    _report(f"Starting config.plist enhancement for: {plist_path}")
    _report(f"Target macOS version: {target_macos_version_name}")

    if not os.path.exists(plist_path):
        _report(f"Error: Plist file not found at {plist_path}")
        return False

    # Create a backup
    backup_plist_path = plist_path + ".backup"
    try:
        shutil.copy2(plist_path, backup_plist_path)
        _report(f"Created backup of config.plist at: {backup_plist_path}")
    except Exception as e:
        _report(f"Error creating backup for {plist_path}: {e}. Proceeding without backup.")
        # Decide if this should be a fatal error for the modification step
        # For now, we'll proceed cautiously.

    if platform.system() != "Linux":
        _report("Hardware detection for plist enhancement currently only supported on Linux. Skipping hardware-specific modifications.")
        # Still load and save to ensure plist is valid, but no hardware changes.
        try:
            with open(plist_path, 'rb') as f: config_data = plistlib.load(f)
            # No changes made, so just confirm it's okay.
            # If we wanted to ensure it's valid and resave (pretty print), we could do:
            # with open(plist_path, 'wb') as f: plistlib.dump(config_data, f, sort_keys=True)
            _report("Plist not modified on non-Linux host (hardware detection skipped).")
            return True
        except Exception as e:
            _report(f"Error processing plist file {plist_path} even without hardware changes: {e}")
            return False


    try:
        with open(plist_path, 'rb') as f:
            config_data = plistlib.load(f)
    except Exception as e:
        _report(f"Error loading plist file {plist_path} for modification: {e}")
        return False

    pci_devices = get_pci_devices_info()
    cpu_info = get_cpu_info() # Currently not used in logic below but fetched

    if not pci_devices: # cpu_info might be empty too
        _report("Could not retrieve PCI hardware information. Skipping most plist enhancements.")
        # Still try to save (pretty-print/validate) the plist if loaded.
        try:
            with open(plist_path, 'wb') as f: plistlib.dump(config_data, f, sort_keys=True)
            _report("Plist re-saved (no hardware changes applied due to missing PCI info).")
            return True
        except Exception as e:
            _report(f"Error re-saving plist file {plist_path}: {e}")
            return False

    # Ensure sections exist
    dev_props = config_data.setdefault("DeviceProperties", {}).setdefault("Add", {})
    kernel_add = config_data.setdefault("Kernel", {}).setdefault("Add", [])
    nvram_add = config_data.setdefault("NVRAM", {}).setdefault("Add", {})
    boot_args_uuid = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
    boot_args_section = nvram_add.setdefault(boot_args_uuid, {})
    current_boot_args_str = boot_args_section.get("boot-args", "")
    boot_args = set(current_boot_args_str.split())
    modified = False # Flag to track if any changes were made

    # 1. Intel iGPU Enhancement
    intel_igpu_device_id_on_host = None
    for dev in pci_devices:
        if dev['type'] == 'VGA' and dev['vendor_id'] == '8086': # Intel iGPU
            intel_igpu_device_id_on_host = dev['device_id']
            lookup_key = f"{dev['vendor_id']}:{dev['device_id']}"
            if lookup_key in INTEL_IGPU_DEFAULTS:
                _report(f"Found Intel iGPU: {dev['description']}. Applying properties.")
                igpu_path_properties = dev_props.setdefault(INTEL_IGPU_PCI_PATH, {})
                for key, value in INTEL_IGPU_DEFAULTS[lookup_key].items():
                    igpu_path_properties[key] = value
                    _report(f"  Set {INTEL_IGPU_PCI_PATH} -> {key}")
            else:
                _report(f"Found Intel iGPU: {dev['description']} ({lookup_key}) but no default properties defined for it.")
            break # Assume only one active iGPU for primary display configuration

    # 2. Audio Enhancement (Layout ID)
    audio_device_path_in_plist = AUDIO_PCI_PATH_FALLBACK # Default, may need to be dynamic
    for dev in pci_devices:
        if dev['type'] == 'Audio':
            lookup_key = f"{dev['vendor_id']}:{dev['device_id']}"
            if lookup_key in AUDIO_LAYOUTS:
                layout_id = AUDIO_LAYOUTS[lookup_key]
                _report(f"Found Audio device: {dev['description']}. Setting layout-id to {layout_id}.")
                audio_path_properties = dev_props.setdefault(audio_device_path_in_plist, {})
                new_layout_data = plistlib.Data(layout_id.to_bytes(1, 'little')) # Common layout IDs are small integers
                if audio_path_properties.get("layout-id") != new_layout_data:
                    audio_path_properties["layout-id"] = new_layout_data
                    _report(f"  Set {audio_device_path_in_plist} -> layout-id = {layout_id}")
                    modified = True
                for kext in kernel_add: # Ensure AppleALC is enabled
                    if isinstance(kext, dict) and kext.get("BundlePath") == "AppleALC.kext":
                        if not kext.get("Enabled", False):
                            kext["Enabled"] = True; _report("  Ensured AppleALC.kext is enabled."); modified = True
                        break
                break

    # 3. Ethernet Kext Enablement
    for dev in pci_devices:
        if dev['type'] == 'Ethernet':
            lookup_key = f"{dev['vendor_id']}:{dev['device_id']}"
            if lookup_key in ETHERNET_KEXT_MAP:
                kext_name = ETHERNET_KEXT_MAP[lookup_key]; _report(f"Found Ethernet device: {dev['description']}. Will ensure {kext_name} is enabled.")
                kext_found_and_enabled_or_modified = False
                for kext_entry in kernel_add:
                    if isinstance(kext_entry, dict) and kext_entry.get("BundlePath") == kext_name:
                        if not kext_entry.get("Enabled", False):
                            kext_entry["Enabled"] = True; _report(f"  Enabled {kext_name}."); modified = True
                        else:
                            _report(f"  {kext_name} already enabled.")
                        kext_found_and_enabled_or_modified = True; break
                if not kext_found_and_enabled_or_modified: _report(f"  Warning: {kext_name} for {dev['description']} not in Kernel->Add.")
                break

    # 4. NVIDIA GTX 970 Specific Adjustments
    gtx_970_present = any(dev['vendor_id'] == '10de' and dev['device_id'] == '13c2' for dev in pci_devices)
    if gtx_970_present:
        _report("NVIDIA GTX 970 detected.")
        is_high_sierra_or_older = target_macos_version_name.lower() in ["high sierra"]
        original_boot_args_len = len(boot_args) # To check if boot_args actually change
        if is_high_sierra_or_older:
            boot_args.add('nvda_drv=1'); boot_args.discard('nv_disable=1')
            _report("  Configured for NVIDIA Web Drivers (High Sierra target).")
        else:
            boot_args.discard('nvda_drv=1')
            if intel_igpu_device_id_on_host:
                boot_args.add('nv_disable=1'); _report(f"  Added nv_disable=1 for {target_macos_version_name} to prioritize iGPU.")
            else:
                boot_args.discard('nv_disable=1'); _report(f"  GTX 970 likely only GPU for {target_macos_version_name}. `nv_disable=1` not forced.")
        # Check if boot_args actually changed before setting modified = True
        if len(boot_args) != original_boot_args_len or ' '.join(sorted(list(boot_args))) != current_boot_args_str : modified = True

    final_boot_args = ' '.join(sorted(list(boot_args)))
    if final_boot_args != current_boot_args_str: # Check if boot-args actually changed
        boot_args_section['boot-args'] = final_boot_args
        _report(f"Updated boot-args to: '{final_boot_args}'")
        modified = True # Ensure modified is true if boot_args changed

    if not modified:
        _report("No changes made to config.plist based on detected hardware or existing settings.")
        return True # Successful in the sense that no changes were needed or applied.

    # Save the modified plist
    try:
        with open(plist_path, 'wb') as f:
            plistlib.dump(config_data, f, sort_keys=True)
        _report(f"Successfully saved enhanced config.plist to {plist_path}")
        return True
    except Exception as e:
        _report(f"Error saving modified plist file {plist_path}: {e}")
        _report(f"Attempting to restore backup to {plist_path}...")
        try:
            shutil.copy2(backup_plist_path, plist_path)
            _report("Restored backup successfully.")
        except Exception as backup_error:
            _report(f"CRITICAL: FAILED TO RESTORE BACKUP. {plist_path} may be corrupt. Backup is at {backup_plist_path}. Error: {backup_error}")
        return False

# if __name__ == '__main__': (Keep the same test block as before)
if __name__ == '__main__':
    print("Plist Modifier Standalone Test")
    dummy_plist_path = "test_config.plist"
    dummy_data = {
        "Kernel": {"Add": [
            {"BundlePath": "Lilu.kext", "Enabled": True, "Arch": "Any", "Comment": "", "ExecutablePath": "Contents/MacOS/Lilu", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"},
            {"BundlePath": "WhateverGreen.kext", "Enabled": True, "Arch": "Any", "Comment": "", "ExecutablePath": "Contents/MacOS/WhateverGreen", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"},
            {"BundlePath": "AppleALC.kext", "Enabled": False, "Arch": "Any", "Comment": "", "ExecutablePath": "Contents/MacOS/AppleALC", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"},
            {"BundlePath": "IntelMausi.kext", "Enabled": False, "Arch": "Any", "Comment": "", "ExecutablePath": "Contents/MacOS/IntelMausi", "MaxKernel": "", "MinKernel": "", "PlistPath": "Contents/Info.plist"},
        ]},
        "NVRAM": {"Add": {"7C436110-AB2A-4BBB-A880-FE41995C9F82": {"boot-args": "-v"}}}
    }
    with open(dummy_plist_path, 'wb') as f:
        plistlib.dump(dummy_data, f)
    print(f"Created dummy {dummy_plist_path} for testing.")

    original_get_pci = get_pci_devices_info; original_get_cpu = get_cpu_info # Store originals

    needs_mocking = platform.system() != "Linux"
    if not needs_mocking:
        try:
            get_pci_devices_info()
        except Exception:
            print("Hardware info functions seem problematic, forcing mock.")
            needs_mocking = True


    if needs_mocking:
        print("Mocking hardware info for non-Linux or if module not loaded properly.")

        get_pci_devices_info = lambda: [
            {'type': 'VGA', 'vendor_id': '8086', 'device_id': '3e9b', 'description': 'Intel UHD Graphics 630 (Desktop Coffee Lake)', 'full_lspci_line':''},
            {'type': 'Audio', 'vendor_id': '8086', 'device_id': 'a348', 'description': 'Intel Cannon Point-LP HD Audio', 'full_lspci_line':''},
            {'type': 'Ethernet', 'vendor_id': '8086', 'device_id': '15b8', 'description': 'Intel I219-V Ethernet', 'full_lspci_line':''},
        ]
        get_cpu_info = lambda: {"Model name": "Intel(R) Core(TM) i7-8700K CPU @ 3.70GHz", "Flags": "avx avx2"}

    success = enhance_config_plist(dummy_plist_path, "Sonoma", print)
    print(f"Plist enhancement {'succeeded' if success else 'failed'}.")
    if success:
        with open(dummy_plist_path, 'rb') as f:
            modified_data = plistlib.load(f)
            print("\n--- Modified Plist Content (first level keys) ---")
            for k,v in modified_data.items(): print(f"{k}: {type(v)}")

    if needs_mocking:
        get_pci_devices_info = original_get_pci; get_cpu_info = original_get_cpu

    if os.path.exists(dummy_plist_path): os.remove(dummy_plist_path)
    if os.path.exists(dummy_plist_path + ".backup"): os.remove(dummy_plist_path + ".backup")
    print(f"Cleaned up dummy plist and backup.")
