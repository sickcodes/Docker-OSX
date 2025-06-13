# usb_writer_linux.py (Finalizing installer asset copying - refined)
import subprocess
import os
import time
import shutil
import glob
import re
import plistlib
import traceback

try:
    from plist_modifier import enhance_config_plist
except ImportError:
    enhance_config_plist = None
# from constants import MACOS_VERSIONS # Imported in _get_gibmacos_product_folder

OC_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "EFI_template_installer")

class USBWriterLinux:
    def __init__(self, device: str, macos_download_path: str,
                 progress_callback=None, enhance_plist_enabled: bool = False,
                 target_macos_version: str = ""):
        self.device = device; self.macos_download_path = macos_download_path
        self.progress_callback = progress_callback; self.enhance_plist_enabled = enhance_plist_enabled
        self.target_macos_version = target_macos_version; pid = os.getpid()
        self.temp_basesystem_hfs_path = f"temp_basesystem_{pid}.hfs"
        self.temp_efi_build_dir = f"temp_efi_build_{pid}"
        self.mount_point_usb_esp = f"/mnt/usb_esp_temp_skyscope_{pid}"
        self.mount_point_usb_macos_target = f"/mnt/usb_macos_target_temp_skyscope_{pid}"
        self.temp_shared_support_mount = f"/mnt/shared_support_temp_{pid}"
        self.temp_dmg_extract_dir = f"temp_dmg_extract_{pid}" # Added for _extract_hfs_from_dmg_or_pkg

        self.temp_files_to_clean = [self.temp_basesystem_hfs_path]
        self.temp_dirs_to_clean = [
            self.temp_efi_build_dir, self.mount_point_usb_esp,
            self.mount_point_usb_macos_target, self.temp_shared_support_mount,
            self.temp_dmg_extract_dir # Ensure this is cleaned
        ]

    def _report_progress(self, message: str, is_rsync_line: bool = False):
        if is_rsync_line:
            match = re.search(r"(\d+)%\s+", message)
            if match:
                try: percentage = int(match.group(1)); self.progress_callback(f"PROGRESS_VALUE:{percentage}")
                except ValueError: pass
            if self.progress_callback: self.progress_callback(message)
            else: print(message)
        else:
            if self.progress_callback: self.progress_callback(message)
            else: print(message)

    def _run_command(self, command: list[str] | str, check=True, capture_output=False, timeout=None, shell=False, working_dir=None, stream_rsync_progress=False):
        cmd_list = command if isinstance(command, list) else command.split()
        is_rsync_progress_command = stream_rsync_progress and "rsync" in cmd_list[0 if cmd_list[0] != "sudo" else (1 if len(cmd_list) > 1 else 0)]

        if is_rsync_progress_command:
            effective_cmd_list = list(cmd_list)
            rsync_idx = -1
            for i, arg in enumerate(effective_cmd_list):
                if "rsync" in arg: rsync_idx = i; break
            if rsync_idx != -1:
                conflicting_flags = ["-P", "--progress"]; effective_cmd_list = [arg for arg in effective_cmd_list if arg not in conflicting_flags]
                actual_rsync_cmd_index_in_list = -1
                for i, arg_part in enumerate(effective_cmd_list):
                    if "rsync" in os.path.basename(arg_part): actual_rsync_cmd_index_in_list = i; break
                if actual_rsync_cmd_index_in_list != -1:
                    if "--info=progress2" not in effective_cmd_list: effective_cmd_list.insert(actual_rsync_cmd_index_in_list + 1, "--info=progress2")
                    if "--no-inc-recursive" not in effective_cmd_list : effective_cmd_list.insert(actual_rsync_cmd_index_in_list + 1, "--no-inc-recursive")
                else: self._report_progress("Warning: rsync command part not found for progress flag insertion.")
            self._report_progress(f"Executing (with progress streaming): {' '.join(effective_cmd_list)}")
            process = subprocess.Popen(effective_cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True, cwd=working_dir)
            stdout_lines, stderr_lines = [], []
            if process.stdout:
                for line in iter(process.stdout.readline, ''): line_strip = line.strip(); self._report_progress(line_strip, is_rsync_line=True); stdout_lines.append(line_strip)
                process.stdout.close()
            if process.stderr:
                for line in iter(process.stderr.readline, ''): line_strip = line.strip(); self._report_progress(f"STDERR: {line_strip}"); stderr_lines.append(line_strip)
                process.stderr.close()
            return_code = process.wait(timeout=timeout);
            if check and return_code != 0: raise subprocess.CalledProcessError(return_code, effective_cmd_list, output="\n".join(stdout_lines), stderr="\n".join(stderr_lines))
            return subprocess.CompletedProcess(args=effective_cmd_list, returncode=return_code, stdout="\n".join(stdout_lines), stderr="\n".join(stderr_lines))
        else:
            self._report_progress(f"Executing: {' '.join(cmd_list)}")
            try:
                process = subprocess.run(cmd_list, check=check, capture_output=capture_output, text=True, timeout=timeout, shell=shell, cwd=working_dir, creationflags=0)
                if capture_output:
                    if process.stdout and process.stdout.strip(): self._report_progress(f"STDOUT: {process.stdout.strip()}")
                    if process.stderr and process.stderr.strip(): self._report_progress(f"STDERR: {process.stderr.strip()}")
                return process
            except subprocess.TimeoutExpired: self._report_progress(f"Command timed out after {timeout} seconds."); raise
            except subprocess.CalledProcessError as e: self._report_progress(f"Error executing (code {e.returncode}): {e.stderr or e.stdout or str(e)}"); raise
            except FileNotFoundError: self._report_progress(f"Error: Command '{cmd_list[0]}' not found."); raise

    def _cleanup_temp_files_and_dirs(self):
        self._report_progress("Cleaning up...")
        for mp in self.temp_dirs_to_clean:
            if os.path.ismount(mp): self._run_command(["sudo", "umount", "-lf", mp], check=False, timeout=15)
        for f_path in self.temp_files_to_clean:
            if os.path.exists(f_path):
                try: self._run_command(["sudo", "rm", "-f", f_path], check=False)
                except Exception as e: self._report_progress(f"Error removing temp file {f_path}: {e}")
        for d_path in self.temp_dirs_to_clean:
            if os.path.exists(d_path):
                try: self._run_command(["sudo", "rm", "-rf", d_path], check=False)
                except Exception as e: self._report_progress(f"Error removing temp dir {d_path}: {e}")

    def check_dependencies(self): self._report_progress("Checking deps...");deps=["sgdisk","parted","mkfs.vfat","mkfs.hfsplus","7z","rsync","dd"];m=[d for d in deps if not shutil.which(d)]; assert not m, f"Missing: {', '.join(m)}. Install hfsprogs for mkfs.hfsplus, p7zip for 7z."; return True

    def _find_gibmacos_asset(self, asset_patterns: list[str] | str, product_folder_path: str | None = None, search_deep=True) -> str | None:
        if isinstance(asset_patterns, str): asset_patterns = [asset_patterns]
        search_base = product_folder_path or self.macos_download_path
        self._report_progress(f"Searching for {asset_patterns} in {search_base} and subdirectories...")
        for pattern in asset_patterns:
            common_subdirs_for_pattern = ["", "SharedSupport", f"Install macOS {self.target_macos_version}.app/Contents/SharedSupport", f"Install macOS {self.target_macos_version}.app/Contents/Resources"]
            for sub_dir_pattern in common_subdirs_for_pattern:
                current_search_base = os.path.join(search_base, sub_dir_pattern)
                # Escape special characters for glob, but allow wildcards in pattern itself
                # This simple escape might not be perfect for all glob patterns.
                glob_pattern = os.path.join(glob.escape(current_search_base), pattern)

                found_files = glob.glob(glob_pattern, recursive=False)
                if found_files:
                    found_files.sort(key=os.path.getsize, reverse=True)
                    self._report_progress(f"Found '{pattern}' at: {found_files[0]} (in {current_search_base})")
                    return found_files[0]

            if search_deep:
                deep_search_pattern = os.path.join(glob.escape(search_base), "**", pattern)
                found_files_deep = sorted(glob.glob(deep_search_pattern, recursive=True), key=len)
                if found_files_deep:
                    self._report_progress(f"Found '{pattern}' via deep search at: {found_files_deep[0]}")
                    return found_files_deep[0]

        self._report_progress(f"Warning: Asset matching patterns '{asset_patterns}' not found in {search_base}.")
        return None

    def _get_gibmacos_product_folder(self) -> str | None:
        from constants import MACOS_VERSIONS
        base_path = os.path.join(self.macos_download_path, "macOS Downloads", "publicrelease")
        if not os.path.isdir(base_path): base_path = self.macos_download_path
        if os.path.isdir(base_path):
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                version_tag_from_constants = MACOS_VERSIONS.get(self.target_macos_version, self.target_macos_version).lower()
                if os.path.isdir(item_path) and (self.target_macos_version.lower() in item.lower() or version_tag_from_constants in item.lower()):
                    self._report_progress(f"Identified gibMacOS product folder: {item_path}"); return item_path
        self._report_progress(f"Could not identify a specific product folder for '{self.target_macos_version}'. Using general download path: {self.macos_download_path}"); return self.macos_download_path

    def _extract_hfs_from_dmg_or_pkg(self, dmg_or_pkg_path: str, output_hfs_path: str) -> bool:
        os.makedirs(self.temp_dmg_extract_dir, exist_ok=True); current_target = dmg_or_pkg_path
        try:
            if dmg_or_pkg_path.endswith(".pkg"): self._report_progress(f"Extracting DMG from PKG {current_target}..."); self._run_command(["7z", "e", "-txar", current_target, "*.dmg", f"-o{self.temp_dmg_extract_dir}"], check=True); dmgs_in_pkg = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*.dmg")); assert dmgs_in_pkg, "No DMG in PKG."; current_target = max(dmgs_in_pkg, key=os.path.getsize, default=dmgs_in_pkg[0]); assert current_target, "No primary DMG in PKG."; self._report_progress(f"Using DMG from PKG: {current_target}")
            assert current_target and current_target.endswith(".dmg"), f"Not a valid DMG: {current_target}"
            basesystem_dmg_to_process = current_target
            if "basesystem.dmg" not in os.path.basename(current_target).lower(): self._report_progress(f"Extracting BaseSystem.dmg from {current_target}..."); self._run_command(["7z", "e", current_target, "*/BaseSystem.dmg", "-r", f"-o{self.temp_dmg_extract_dir}"], check=True); found_bs_dmg = glob.glob(os.path.join(self.temp_dmg_extract_dir, "**", "*BaseSystem.dmg"), recursive=True); assert found_bs_dmg, f"No BaseSystem.dmg from {current_target}"; basesystem_dmg_to_process = found_bs_dmg[0]
            self._report_progress(f"Extracting HFS+ partition image from {basesystem_dmg_to_process}..."); self._run_command(["7z", "e", "-tdmg", basesystem_dmg_to_process, "*.hfs", f"-o{self.temp_dmg_extract_dir}"], check=True); hfs_files = glob.glob(os.path.join(self.temp_dmg_extract_dir, "*.hfs"));
            if not hfs_files: self._run_command(["7z", "e", "-tdmg", basesystem_dmg_to_process, "*", f"-o{self.temp_dmg_extract_dir}"], check=True); hfs_files = [os.path.join(self.temp_dmg_extract_dir, f) for f in os.listdir(self.temp_dmg_extract_dir) if not f.lower().endswith((".xml",".chunklist",".plist")) and os.path.isfile(os.path.join(self.temp_dmg_extract_dir,f)) and os.path.getsize(os.path.join(self.temp_dmg_extract_dir,f)) > 2*1024*1024*1024] # Min 2GB HFS for BaseSystem
            assert hfs_files, f"No suitable HFS+ image file found after extracting {basesystem_dmg_to_process}"
            final_hfs_file = max(hfs_files, key=os.path.getsize); self._report_progress(f"Found HFS+ image: {final_hfs_file}. Moving to {output_hfs_path}"); shutil.move(final_hfs_file, output_hfs_path); return True
        except Exception as e: self._report_progress(f"Error during HFS extraction: {e}\n{traceback.format_exc()}"); return False
        finally:
            if os.path.exists(self.temp_dmg_extract_dir): shutil.rmtree(self.temp_dmg_extract_dir, ignore_errors=True)

    def _create_minimal_efi_template(self, efi_dir_path):
        self._report_progress(f"Minimal EFI template directory not found or empty. Creating basic structure at {efi_dir_path}"); oc_dir=os.path.join(efi_dir_path,"EFI","OC");os.makedirs(os.path.join(efi_dir_path,"EFI","BOOT"),exist_ok=True);os.makedirs(oc_dir,exist_ok=True);[os.makedirs(os.path.join(oc_dir,s),exist_ok=True) for s in ["Drivers","Kexts","ACPI","Tools","Resources"]];open(os.path.join(efi_dir_path,"EFI","BOOT","BOOTx64.efi"),"w").close();open(os.path.join(oc_dir,"OpenCore.efi"),"w").close();bc={"#Comment":"Basic config","Misc":{"Security":{"ScanPolicy":0,"SecureBootModel":"Disabled"}},"PlatformInfo":{"Generic":{"MLB":"CHANGE_ME_MLB","SystemSerialNumber":"CHANGE_ME_SERIAL","SystemUUID":"CHANGE_ME_UUID","ROM":b"\0"*6}}};plistlib.dump(bc,open(os.path.join(oc_dir,"config.plist"),'wb'),fmt=plistlib.PlistFormat.XML)

    def format_and_write(self) -> bool:
        try:
            self.check_dependencies(); self._cleanup_temp_files_and_dirs();
            for mp_dir in [self.mount_point_usb_esp, self.mount_point_usb_macos_target, self.temp_efi_build_dir]: self._run_command(["sudo", "mkdir", "-p", mp_dir])
            self._report_progress(f"WARNING: ALL DATA ON {self.device} WILL BE ERASED!");
            for i in range(1, 10): self._run_command(["sudo", "umount", "-lf", f"{self.device}{i}"], check=False, timeout=5); self._run_command(["sudo", "umount", "-lf", f"{self.device}p{i}"], check=False, timeout=5)

            self._report_progress(f"Partitioning {self.device} with GPT (sgdisk)...")
            self._run_command(["sudo", "sgdisk", "--zap-all", self.device])
            self._run_command(["sudo", "sgdisk", "-n", "0:0:+551MiB", "-t", "0:ef00", "-c", "0:EFI", self.device])
            usb_vol_name = f"Install macOS {self.target_macos_version}"
            self._run_command(["sudo", "sgdisk", "-n", "0:0:0",      "-t", "0:af00", "-c", f"0:{usb_vol_name[:11]}" , self.device])
            self._run_command(["sudo", "partprobe", self.device], timeout=10); time.sleep(3)
            esp_dev=f"{self.device}1" if os.path.exists(f"{self.device}1") else f"{self.device}p1"; macos_part=f"{self.device}2" if os.path.exists(f"{self.device}2") else f"{self.device}p2"; assert os.path.exists(esp_dev) and os.path.exists(macos_part), "Partitions not found."
            self._report_progress(f"Formatting ESP {esp_dev}..."); self._run_command(["sudo", "mkfs.vfat", "-F", "32", "-n", "EFI", esp_dev])
            self._report_progress(f"Formatting macOS partition {macos_part}..."); self._run_command(["sudo", "mkfs.hfsplus", "-v", usb_vol_name, macos_part])

            product_folder_path = self._get_gibmacos_product_folder()
            basesystem_source_dmg_or_pkg = self._find_gibmacos_asset(["BaseSystem.dmg", "InstallESD.dmg", "SharedSupport.dmg", "InstallAssistant.pkg"], product_folder_path, "BaseSystem.dmg (or source like InstallESD.dmg/SharedSupport.dmg/InstallAssistant.pkg)")
            if not basesystem_source_dmg_or_pkg: raise RuntimeError("Essential macOS DMG/PKG for BaseSystem extraction not found in download path.")
            if not self._extract_hfs_from_dmg_or_pkg(basesystem_source_dmg_or_pkg, self.temp_basesystem_hfs_path):
                raise RuntimeError("Failed to extract HFS+ image from BaseSystem assets.")
            self._report_progress(f"Writing BaseSystem to {macos_part}..."); self._run_command(["sudo","dd",f"if={self.temp_basesystem_hfs_path}",f"of={macos_part}","bs=4M","status=progress","oflag=sync"])
            self._report_progress("Mounting macOS USB partition..."); self._run_command(["sudo","mount",macos_part,self.mount_point_usb_macos_target])

            # --- Finalizing macOS Installer Content on USB's HFS+ partition ---
            self._report_progress("Finalizing macOS installer content on USB...")
            usb_target_root = self.mount_point_usb_macos_target

            app_bundle_name = f"Install macOS {self.target_macos_version}.app"
            app_bundle_path_usb = os.path.join(usb_target_root, app_bundle_name)
            contents_path_usb = os.path.join(app_bundle_path_usb, "Contents")
            shared_support_path_usb_app = os.path.join(contents_path_usb, "SharedSupport")
            resources_path_usb_app = os.path.join(contents_path_usb, "Resources") # For createinstallmedia structure
            sys_install_pkgs_usb = os.path.join(usb_target_root, "System", "Installation", "Packages")
            coreservices_path_usb = os.path.join(usb_target_root, "System", "Library", "CoreServices")

            for p in [shared_support_path_usb_app, resources_path_usb_app, coreservices_path_usb, sys_install_pkgs_usb]:
                self._run_command(["sudo", "mkdir", "-p", p])

            # Copy BaseSystem.dmg & BaseSystem.chunklist
            bs_dmg_src = self._find_gibmacos_asset("BaseSystem.dmg", product_folder_path, search_deep=True)
            bs_chunklist_src = self._find_gibmacos_asset("BaseSystem.chunklist", product_folder_path, search_deep=True)
            if bs_dmg_src:
                self._report_progress(f"Copying BaseSystem.dmg to USB CoreServices and App SharedSupport...")
                self._run_command(["sudo", "cp", bs_dmg_src, os.path.join(coreservices_path_usb, "BaseSystem.dmg")])
                self._run_command(["sudo", "cp", bs_dmg_src, os.path.join(shared_support_path_usb_app, "BaseSystem.dmg")])
            if bs_chunklist_src:
                self._report_progress(f"Copying BaseSystem.chunklist to USB CoreServices and App SharedSupport...")
                self._run_command(["sudo", "cp", bs_chunklist_src, os.path.join(coreservices_path_usb, "BaseSystem.chunklist")])
                self._run_command(["sudo", "cp", bs_chunklist_src, os.path.join(shared_support_path_usb_app, "BaseSystem.chunklist")])
            if not bs_dmg_src or not bs_chunklist_src: self._report_progress("Warning: BaseSystem.dmg or .chunklist not found in product folder.")

            # Copy InstallInfo.plist
            installinfo_src = self._find_gibmacos_asset("InstallInfo.plist", product_folder_path, search_deep=True)
            if installinfo_src:
                self._report_progress(f"Copying InstallInfo.plist...")
                self._run_command(["sudo", "cp", installinfo_src, os.path.join(contents_path_usb, "Info.plist")])
                self._run_command(["sudo", "cp", installinfo_src, os.path.join(usb_target_root, "InstallInfo.plist")])
            else: self._report_progress("Warning: InstallInfo.plist (source) not found.")

            # Copy main installer package(s)
            main_pkg_src = self._find_gibmacos_asset("InstallAssistant.pkg", product_folder_path, search_deep=True) or                            self._find_gibmacos_asset("InstallESD.dmg", product_folder_path, search_deep=True)
            if main_pkg_src:
                pkg_basename = os.path.basename(main_pkg_src)
                self._report_progress(f"Copying main payload '{pkg_basename}' to App SharedSupport and System Packages...")
                self._run_command(["sudo", "cp", main_pkg_src, os.path.join(shared_support_path_usb_app, pkg_basename)])
                self._run_command(["sudo", "cp", main_pkg_src, os.path.join(sys_install_pkgs_usb, pkg_basename)])
            else: self._report_progress("Warning: Main installer package (InstallAssistant.pkg/InstallESD.dmg) not found.")

            diag_src = self._find_gibmacos_asset("AppleDiagnostics.dmg", product_folder_path, search_deep=True)
            if diag_src: self._run_command(["sudo", "cp", diag_src, os.path.join(shared_support_path_usb_app, "AppleDiagnostics.dmg")])

            template_boot_efi = os.path.join(OC_TEMPLATE_DIR, "EFI", "BOOT", "BOOTx64.efi")
            if os.path.exists(template_boot_efi) and os.path.getsize(template_boot_efi) > 0:
                self._run_command(["sudo", "cp", template_boot_efi, os.path.join(coreservices_path_usb, "boot.efi")])
            else: self._report_progress(f"Warning: Template BOOTx64.efi for installer's boot.efi not found or empty.")

            # Create .IAProductInfo (Simplified XML string to avoid f-string issues in tool call)
            ia_product_info_path = os.path.join(usb_target_root, ".IAProductInfo")
            ia_content_xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\"><plist version=\"1.0\"><dict><key>Product ID</key><string>com.apple.pkg.InstallAssistant</string><key>Product Path</key><string>" + app_bundle_name + "/Contents/SharedSupport/InstallAssistant.pkg</string></dict></plist>"
            temp_ia_path = f"temp_iaproductinfo_{pid}.plist"
            with open(temp_ia_path, "w") as f: f.write(ia_content_xml)
            self._run_command(["sudo", "cp", temp_ia_path, ia_product_info_path])
            if os.path.exists(temp_ia_path): os.remove(temp_ia_path)
            self._report_progress("Created .IAProductInfo.")
            self._report_progress("macOS installer assets fully copied to USB.")

            # --- OpenCore EFI Setup ---
            self._report_progress("Setting up OpenCore EFI on ESP..."); self._run_command(["sudo", "mount", esp_dev, self.mount_point_usb_esp])
            if not os.path.isdir(OC_TEMPLATE_DIR) or not os.listdir(OC_TEMPLATE_DIR): self._create_minimal_efi_template(self.temp_efi_build_dir)
            else: self._run_command(["sudo", "cp", "-a", f"{OC_TEMPLATE_DIR}/.", self.temp_efi_build_dir])
            temp_config_plist_path = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config.plist")
            if not os.path.exists(temp_config_plist_path):
                template_plist = os.path.join(self.temp_efi_build_dir, "EFI", "OC", "config-template.plist")
                if os.path.exists(template_plist): shutil.copy2(template_plist, temp_config_plist_path)
                else: plistlib.dump({"#Comment": "Basic config by Skyscope"}, open(temp_config_plist_path, 'wb'), fmt=plistlib.PlistFormat.XML)
            if self.enhance_plist_enabled and enhance_config_plist:
                self._report_progress("Attempting to enhance config.plist...")
                if enhance_config_plist(temp_config_plist_path, self.target_macos_version, self._report_progress): self._report_progress("config.plist enhancement processing complete.")
                else: self._report_progress("config.plist enhancement call failed or had issues.")
            self._report_progress(f"Copying final EFI folder to USB ESP ({self.mount_point_usb_esp})...")
            self._run_command(["sudo", "rsync", "-avh", "--delete", f"{self.temp_efi_build_dir}/EFI/", f"{self.mount_point_usb_esp}/EFI/"], stream_rsync_progress=True)

            self._report_progress("USB Installer creation process completed successfully.")
            return True
        except Exception as e:
            self._report_progress(f"An error occurred during USB writing: {e}"); self._report_progress(traceback.format_exc())
            return False
        finally:
            self._cleanup_temp_files_and_dirs()

if __name__ == '__main__':
    import traceback; from constants import MACOS_VERSIONS
    if os.geteuid() != 0: print("Please run this script as root (sudo) for testing."); exit(1)
    print("USB Writer Linux Standalone Test - Installer Method (Fuller Asset Copying Logic)")
    mock_download_dir = f"temp_macos_download_skyscope_{os.getpid()}"; os.makedirs(mock_download_dir, exist_ok=True)
    target_version_cli = sys.argv[1] if len(sys.argv) > 1 else "Sonoma"
    mock_product_name_segment = MACOS_VERSIONS.get(target_version_cli, target_version_cli).lower()
    mock_product_name = f"012-34567 - macOS {target_version_cli} {mock_product_name_segment}.x.x"
    specific_product_folder = os.path.join(mock_download_dir, "macOS Downloads", "publicrelease", mock_product_name)
    os.makedirs(os.path.join(specific_product_folder, "SharedSupport"), exist_ok=True); os.makedirs(specific_product_folder, exist_ok=True)
    with open(os.path.join(specific_product_folder, "SharedSupport", "BaseSystem.dmg"), "wb") as f: f.write(os.urandom(10*1024*1024))
    with open(os.path.join(specific_product_folder, "SharedSupport", "BaseSystem.chunklist"), "w") as f: f.write("dummy chunklist")
    with open(os.path.join(specific_product_folder, "InstallInfo.plist"), "wb") as f: plistlib.dump({"DisplayName":f"macOS {target_version_cli}"},f)
    with open(os.path.join(specific_product_folder, "InstallAssistant.pkg"), "wb") as f: f.write(os.urandom(1024))
    with open(os.path.join(specific_product_folder, "SharedSupport", "AppleDiagnostics.dmg"), "wb") as f: f.write(os.urandom(1024))
    if not os.path.exists(OC_TEMPLATE_DIR): os.makedirs(OC_TEMPLATE_DIR, exist_ok=True)
    if not os.path.exists(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC")): os.makedirs(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC"), exist_ok=True)
    if not os.path.exists(os.path.join(OC_TEMPLATE_DIR, "EFI", "BOOT")): os.makedirs(os.path.join(OC_TEMPLATE_DIR, "EFI", "BOOT"), exist_ok=True)
    with open(os.path.join(OC_TEMPLATE_DIR, "EFI", "OC", "config-template.plist"), "wb") as f: plistlib.dump({"Test":True}, f, fmt=plistlib.PlistFormat.XML)
    with open(os.path.join(OC_TEMPLATE_DIR, "EFI", "BOOT", "BOOTx64.efi"), "w") as f: f.write("dummy bootx64.efi")
    print("\nAvailable block devices (be careful!):"); subprocess.run(["lsblk", "-d", "-o", "NAME,SIZE,MODEL"], check=True)
    test_device = input("\nEnter target device (e.g., /dev/sdX). THIS DEVICE WILL BE WIPED: ")
    if not test_device or not test_device.startswith("/dev/"): print("Invalid device."); shutil.rmtree(mock_download_dir); shutil.rmtree(OC_TEMPLATE_DIR, ignore_errors=True); exit(1)
    if input(f"Sure to wipe {test_device}? (yes/NO): ").lower() == 'yes':
        writer = USBWriterLinux(test_device, mock_download_dir, print, True, target_version_cli)
        writer.format_and_write()
    else: print("Test cancelled.")
    shutil.rmtree(mock_download_dir, ignore_errors=True);
    # shutil.rmtree(OC_TEMPLATE_DIR, ignore_errors=True) # Usually keep template dir for other tests
    print("Mock download dir cleaned up.")
