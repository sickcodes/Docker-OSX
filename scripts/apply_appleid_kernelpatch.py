#!/usr/bin/env python3
import plistlib
import base64
import os
import sys

def add_kernel_patches(config_path):
    # Make a backup of the original file
    backup_path = config_path + '.backup'
    os.system(f'cp "{config_path}" "{backup_path}"')
    print(f"Backup created at {backup_path}")
    
    # Read the plist file
    with open(config_path, 'rb') as f:
        config = plistlib.load(f)
    
    # Prepare the patch entries
    patch1 = {
        'Arch': 'x86_64',
        'Base': '',
        'Comment': 'Sonoma VM BT Enabler - PART 1 of 2 - Patch kern.hv_vmm_present=0',
        'Count': 1,
        'Enabled': True,
        'Find': base64.b64decode('aGliZXJuYXRlaGlkcmVhZHkAaGliZXJuYXRlY291bnQA'),
        'Identifier': 'kernel',
        'Limit': 0,
        'Mask': b'',
        'MaxKernel': '',
        'MinKernel': '20.4.0',
        'Replace': base64.b64decode('aGliZXJuYXRlaGlkcmVhZHkAaHZfdm1tX3ByZXNlbnQA'),
        'ReplaceMask': b'',
        'Skip': 0,
    }
    
    patch2 = {
        'Arch': 'x86_64',
        'Base': '',
        'Comment': 'Sonoma VM BT Enabler - PART 2 of 2 - Patch kern.hv_vmm_present=0',
        'Count': 1,
        'Enabled': True,
        'Find': base64.b64decode('Ym9vdCBzZXNzaW9uIFVVSUQAaHZfdm1tX3ByZXNlbnQA'),
        'Identifier': 'kernel',
        'Limit': 0,
        'Mask': b'',
        'MaxKernel': '',
        'MinKernel': '22.0.0',
        'Replace': base64.b64decode('Ym9vdCBzZXNzaW9uIFVVSUQAaGliZXJuYXRlY291bnQA'),
        'ReplaceMask': b'',
        'Skip': 0,
    }
    
    # Add patches to the kernel patch section
    if 'Kernel' in config and 'Patch' in config['Kernel']:
        # Check if patches already exist
        patch_exists = False
        for patch in config['Kernel']['Patch']:
            if isinstance(patch, dict) and 'Comment' in patch:
                if 'Sonoma VM BT Enabler' in patch['Comment']:
                    patch_exists = True
                    print(f"Patch already exists: {patch['Comment']}")
        
        if not patch_exists:
            config['Kernel']['Patch'].append(patch1)
            config['Kernel']['Patch'].append(patch2)
            print("Added both Sonoma VM BT Enabler patches to config.plist")
        
    else:
        print("Error: Could not find Kernel -> Patch section in config.plist")
        return False
    
    # Write the updated plist file
    with open(config_path, 'wb') as f:
        plistlib.dump(config, f)
    
    print(f"Successfully updated {config_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python apply_appleid_kernelpatch.py /path/to/config.plist")
        sys.exit(1)
    
    config_path = sys.argv[1]
    if not os.path.exists(config_path):
        print(f"Error: File {config_path} does not exist")
        sys.exit(1)
    
    success = add_kernel_patches(config_path)
    if success:
        print("Patches applied successfully. Please reboot to apply changes.")
    else:
        print("Failed to apply patches.")