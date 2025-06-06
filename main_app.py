# main_app.py
import sys
import subprocess
import os
import psutil
import platform
import ctypes
import json
import re
import traceback # For better error logging
import shutil # For shutil.which

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QMessageBox, QMenuBar,
    QFileDialog, QGroupBox, QLineEdit, QProgressBar, QCheckBox
)
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QObject, QThread, QTimer, Qt

from constants import APP_NAME, DEVELOPER_NAME, BUSINESS_NAME, MACOS_VERSIONS
# DOCKER_IMAGE_BASE and Docker-related utils are no longer primary for this flow.
# utils.py might be refactored or parts removed later.

# Platform specific USB writers
USBWriterLinux = None
USBWriterMacOS = None
USBWriterWindows = None

if platform.system() == "Linux":
    try: from usb_writer_linux import USBWriterLinux
    except ImportError as e: print(f"Could not import USBWriterLinux: {e}")
elif platform.system() == "Darwin":
    try: from usb_writer_macos import USBWriterMacOS
    except ImportError as e: print(f"Could not import USBWriterMacOS: {e}")
elif platform.system() == "Windows":
    try: from usb_writer_windows import USBWriterWindows
    except ImportError as e: print(f"Could not import USBWriterWindows: {e}")

GIBMACOS_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "scripts", "gibMacOS", "gibMacOS.py")
if not os.path.exists(GIBMACOS_SCRIPT_PATH):
    GIBMACOS_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "gibMacOS.py")


class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress_value = pyqtSignal(int)

class GibMacOSWorker(QObject):
    signals = WorkerSignals()
    def __init__(self, version_key: str, download_path: str, catalog_key: str = "publicrelease"):
        super().__init__()
        self.version_key = version_key
        self.download_path = download_path
        self.catalog_key = catalog_key
        self.process = None
        self._is_running = True

    @pyqtSlot()
    def run(self):
        try:
            script_to_run = ""
            if os.path.exists(GIBMACOS_SCRIPT_PATH):
                script_to_run = GIBMACOS_SCRIPT_PATH
            elif shutil.which("gibMacOS.py"): # Check if it's in PATH
                 script_to_run = "gibMacOS.py"
            elif os.path.exists(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "gibMacOS.py")): # Check alongside main_app.py
                 script_to_run = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "gibMacOS.py")
            else:
                self.signals.error.emit(f"gibMacOS.py not found at expected locations or in PATH.")
                return

            version_for_gib = MACOS_VERSIONS.get(self.version_key, self.version_key)
            os.makedirs(self.download_path, exist_ok=True)

            command = [sys.executable, script_to_run, "-n", "-c", self.catalog_key, "-v", version_for_gib, "-d", self.download_path]
            self.signals.progress.emit(f"Downloading macOS '{self.version_key}' (as '{version_for_gib}') installer assets...\nCommand: {' '.join(command)}\nOutput will be in: {self.download_path}\n")

            self.process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ''):
                    if not self._is_running:
                        self.signals.progress.emit("macOS download process stopping at user request.\n")
                        break
                    line_strip = line.strip()
                    self.signals.progress.emit(line_strip)
                    progress_match = re.search(r"(\d+)%", line_strip)
                    if progress_match:
                        try: self.signals.progress_value.emit(int(progress_match.group(1)))
                        except ValueError: pass
                self.process.stdout.close()

            return_code = self.process.wait()

            if not self._is_running and return_code != 0:
                 self.signals.finished.emit(f"macOS download cancelled or stopped early (exit code {return_code}).")
                 return

            if return_code == 0:
                self.signals.finished.emit(f"macOS '{self.version_key}' installer assets downloaded to '{self.download_path}'.")
            else:
                self.signals.error.emit(f"Failed to download macOS '{self.version_key}' (gibMacOS exit code {return_code}). Check logs.")
        except FileNotFoundError:
            self.signals.error.emit(f"Error: Python or gibMacOS.py script not found. Ensure Python is in PATH and gibMacOS script is correctly located.")
        except Exception as e:
            self.signals.error.emit(f"An error occurred during macOS download: {str(e)}\n{traceback.format_exc()}")
        finally:
            self._is_running = False

    def stop(self):
        self._is_running = False
        if self.process and self.process.poll() is None:
            self.signals.progress.emit("Attempting to stop macOS download (may not be effective for active downloads)...\n")
            try:
                self.process.terminate(); self.process.wait(timeout=2)
            except subprocess.TimeoutExpired: self.process.kill()
            self.signals.progress.emit("macOS download process termination requested.\n")


class USBWriterWorker(QObject):
    signals = WorkerSignals()
    def __init__(self, device: str, macos_download_path: str,
                 enhance_plist: bool, target_macos_version: str):
        super().__init__()
        self.device = device
        self.macos_download_path = macos_download_path
        self.enhance_plist = enhance_plist
        self.target_macos_version = target_macos_version
        self.writer_instance = None

    @pyqtSlot()
    def run(self):
        current_os = platform.system()
        try:
            writer_cls = None
            if current_os == "Linux": writer_cls = USBWriterLinux
            elif current_os == "Darwin": writer_cls = USBWriterMacOS
            elif current_os == "Windows": writer_cls = USBWriterWindows

            if writer_cls is None:
                self.signals.error.emit(f"{current_os} USB writer module not available or OS not supported."); return

            # Platform writers' __init__ will need to be updated for macos_download_path
            # This assumes usb_writer_*.py __init__ signatures are now:
            # __init__(self, device, macos_download_path, progress_callback, enhance_plist_enabled, target_macos_version)
            self.writer_instance = writer_cls(
                device=self.device,
                macos_download_path=self.macos_download_path,
                progress_callback=lambda msg: self.signals.progress.emit(msg),
                enhance_plist_enabled=self.enhance_plist,
                target_macos_version=self.target_macos_version
            )

            if self.writer_instance.format_and_write():
                self.signals.finished.emit("USB writing process completed successfully.")
            else:
                self.signals.error.emit("USB writing process failed. Check output for details.")
        except Exception as e:
            self.signals.error.emit(f"USB writing preparation error: {str(e)}\n{traceback.format_exc()}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 800, 700) # Adjusted height

        self.active_worker_thread = None
        self.macos_download_path = None
        self.current_worker_instance = None

        self.spinner_chars = ["|", "/", "-", "\\"]; self.spinner_index = 0
        self.spinner_timer = QTimer(self); self.spinner_timer.timeout.connect(self._update_spinner_status)
        self.base_status_message = "Ready."

        self._setup_ui()
        self.status_bar = self.statusBar()
        # self.status_bar.addPermanentWidget(self.progress_bar) # Progress bar now in main layout
        self.status_bar.showMessage(self.base_status_message, 5000)
        self.refresh_usb_drives()

    def _setup_ui(self):
        menubar = self.menuBar(); file_menu = menubar.addMenu("&File"); help_menu = menubar.addMenu("&Help")
        exit_action = QAction("&Exit", self); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
        about_action = QAction("&About", self); about_action.triggered.connect(self.show_about_dialog); help_menu.addAction(about_action)
        central_widget = QWidget(); self.setCentralWidget(central_widget); main_layout = QVBoxLayout(central_widget)

        # Step 1: Download macOS
        download_group = QGroupBox("Step 1: Download macOS Installer Assets")
        download_layout = QVBoxLayout()
        selection_layout = QHBoxLayout(); self.version_label = QLabel("Select macOS Version:"); self.version_combo = QComboBox()
        self.version_combo.addItems(MACOS_VERSIONS.keys()); selection_layout.addWidget(self.version_label); selection_layout.addWidget(self.version_combo)
        download_layout.addLayout(selection_layout)

        self.download_macos_button = QPushButton("Download macOS Installer Assets")
        self.download_macos_button.clicked.connect(self.start_macos_download_flow)
        download_layout.addWidget(self.download_macos_button)

        self.cancel_operation_button = QPushButton("Cancel Current Operation")
        self.cancel_operation_button.clicked.connect(self.stop_current_operation)
        self.cancel_operation_button.setEnabled(False)
        download_layout.addWidget(self.cancel_operation_button)
        download_group.setLayout(download_layout)
        main_layout.addWidget(download_group)

        # Step 2: USB Drive Selection & Writing
        usb_group = QGroupBox("Step 2: Create Bootable USB Installer")
        self.usb_layout = QVBoxLayout()
        self.usb_drive_label = QLabel("Available USB Drives:"); self.usb_layout.addWidget(self.usb_drive_label)
        usb_selection_layout = QHBoxLayout(); self.usb_drive_combo = QComboBox(); self.usb_drive_combo.currentIndexChanged.connect(self.update_all_button_states)
        usb_selection_layout.addWidget(self.usb_drive_combo); self.refresh_usb_button = QPushButton("Refresh List"); self.refresh_usb_button.clicked.connect(self.refresh_usb_drives)
        usb_selection_layout.addWidget(self.refresh_usb_button); self.usb_layout.addLayout(usb_selection_layout)
        self.windows_usb_guidance_label = QLabel("For Windows: Select USB disk from dropdown (WMI). Manual input below if empty/unreliable.")
        self.windows_disk_id_input = QLineEdit(); self.windows_disk_id_input.setPlaceholderText("Disk No. (e.g., 1)"); self.windows_disk_id_input.textChanged.connect(self.update_all_button_states)
        if platform.system() == "Windows": self.usb_layout.addWidget(self.windows_usb_guidance_label); self.usb_layout.addWidget(self.windows_disk_id_input); self.windows_usb_guidance_label.setVisible(True); self.windows_disk_id_input.setVisible(True)
        else: self.windows_usb_guidance_label.setVisible(False); self.windows_disk_id_input.setVisible(False)
        self.enhance_plist_checkbox = QCheckBox("Try to auto-enhance config.plist for this system's hardware (Experimental, Linux Host Only for detection)")
        self.enhance_plist_checkbox.setChecked(False); self.usb_layout.addWidget(self.enhance_plist_checkbox)
        warning_label = QLabel("WARNING: USB drive will be ERASED!"); warning_label.setStyleSheet("color: red; font-weight: bold;"); self.usb_layout.addWidget(warning_label)
        self.write_to_usb_button = QPushButton("Create macOS Installer USB"); self.write_to_usb_button.clicked.connect(self.handle_write_to_usb)
        self.write_to_usb_button.setEnabled(False); self.usb_layout.addWidget(self.write_to_usb_button); usb_group.setLayout(self.usb_layout); main_layout.addWidget(usb_group)

        self.progress_bar = QProgressBar(self); self.progress_bar.setRange(0, 0); self.progress_bar.setVisible(False); main_layout.addWidget(self.progress_bar)
        self.output_area = QTextEdit(); self.output_area.setReadOnly(True); main_layout.addWidget(self.output_area)
        self.update_all_button_states()

    def show_about_dialog(self): QMessageBox.about(self, f"About {APP_NAME}", f"Version: 1.0.0 (Installer Flow)\nDeveloper: {DEVELOPER_NAME}\nBusiness: {BUSINESS_NAME}\n\nThis tool helps create bootable macOS USB drives using gibMacOS and OpenCore.")

    def _set_ui_busy(self, busy_status: bool, message: str = "Processing..."):
        self.progress_bar.setVisible(busy_status)
        if busy_status:
            self.base_status_message = message
            if not self.spinner_timer.isActive(): self.spinner_timer.start(150)
            self._update_spinner_status()
            self.progress_bar.setRange(0,0)
        else:
            self.spinner_timer.stop()
            self.status_bar.showMessage(message or "Ready.", 7000)
        self.update_all_button_states()


    def _update_spinner_status(self):
        if self.spinner_timer.isActive():
            char = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
            active_worker_provides_progress = False
            if self.active_worker_thread and self.active_worker_thread.isRunning():
                 active_worker_provides_progress = getattr(self.active_worker_thread, "provides_progress", False)

            if active_worker_provides_progress and self.progress_bar.maximum() == 100: # Determinate
                 self.status_bar.showMessage(f"{char} {self.base_status_message} ({self.progress_bar.value()}%)")
            else:
                 if self.progress_bar.maximum() != 0: self.progress_bar.setRange(0,0)
                 self.status_bar.showMessage(f"{char} {self.base_status_message}")
            self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
        elif not (self.active_worker_thread and self.active_worker_thread.isRunning()):
             self.spinner_timer.stop()

    def update_all_button_states(self):
        is_worker_active = self.active_worker_thread is not None and self.active_worker_thread.isRunning()

        self.download_macos_button.setEnabled(not is_worker_active)
        self.version_combo.setEnabled(not is_worker_active)
        self.cancel_operation_button.setEnabled(is_worker_active and self.current_worker_instance is not None)

        self.refresh_usb_button.setEnabled(not is_worker_active)
        self.usb_drive_combo.setEnabled(not is_worker_active)
        if platform.system() == "Windows": self.windows_disk_id_input.setEnabled(not is_worker_active)
        self.enhance_plist_checkbox.setEnabled(not is_worker_active)

        # Write to USB button logic
        macos_assets_ready = bool(self.macos_download_path and os.path.isdir(self.macos_download_path))
        usb_identified = False
        current_os = platform.system(); writer_module = None
        if current_os == "Linux": writer_module = USBWriterLinux; usb_identified = bool(self.usb_drive_combo.currentData())
        elif current_os == "Darwin": writer_module = USBWriterMacOS; usb_identified = bool(self.usb_drive_combo.currentData())
        elif current_os == "Windows":
            writer_module = USBWriterWindows
            usb_identified = bool(self.usb_drive_combo.currentData()) or bool(self.windows_disk_id_input.text().strip())

        self.write_to_usb_button.setEnabled(not is_worker_active and macos_assets_ready and usb_identified and writer_module is not None)
        tooltip = ""
        if writer_module is None: tooltip = f"USB Writing not supported on {current_os} or module missing."
        elif not macos_assets_ready: tooltip = "Download macOS installer assets first (Step 1)."
        elif not usb_identified: tooltip = "Select or identify a target USB drive."
        else: tooltip = ""
        self.write_to_usb_button.setToolTip(tooltip)


    def _start_worker(self, worker_instance, on_finished_slot, on_error_slot, worker_name="worker", provides_progress=False):
        if self.active_worker_thread and self.active_worker_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Another operation is in progress."); return False

        self._set_ui_busy(True, f"Starting {worker_name.replace('_', ' ')}...")
        self.current_worker_instance = worker_instance

        if provides_progress:
            self.progress_bar.setRange(0,100)
            worker_instance.signals.progress_value.connect(self.update_progress_bar_value)
        else:
            self.progress_bar.setRange(0,0)

        self.active_worker_thread = QThread(); self.active_worker_thread.setObjectName(worker_name + "_thread")
        setattr(self.active_worker_thread, "provides_progress", provides_progress)

        worker_instance.moveToThread(self.active_worker_thread)
        worker_instance.signals.progress.connect(self.update_output)
        worker_instance.signals.finished.connect(lambda msg, wn=worker_name, slot=on_finished_slot: self._handle_worker_finished(msg, wn, slot))
        worker_instance.signals.error.connect(lambda err, wn=worker_name, slot=on_error_slot: self._handle_worker_error(err, wn, slot))
        self.active_worker_thread.finished.connect(self.active_worker_thread.deleteLater)
        self.active_worker_thread.started.connect(worker_instance.run)
        self.active_worker_thread.start()
        return True

    @pyqtSlot(int)
    def update_progress_bar_value(self, value):
        if self.progress_bar.maximum() == 0: self.progress_bar.setRange(0,100)
        self.progress_bar.setValue(value)
        # Spinner update will happen on its timer, it can check progress_bar.value()

    def _handle_worker_finished(self, message, worker_name, specific_finished_slot):
        final_msg = f"{worker_name.replace('_', ' ').capitalize()} completed."
        self.current_worker_instance = None # Clear current worker
        self.active_worker_thread = None
        if specific_finished_slot: specific_finished_slot(message)
        self._set_ui_busy(False, final_msg)

    def _handle_worker_error(self, error_message, worker_name, specific_error_slot):
        final_msg = f"{worker_name.replace('_', ' ').capitalize()} failed."
        self.current_worker_instance = None # Clear current worker
        self.active_worker_thread = None
        if specific_error_slot: specific_error_slot(error_message)
        self._set_ui_busy(False, final_msg)

    def start_macos_download_flow(self):
        self.output_area.clear(); selected_version_name = self.version_combo.currentText()
        gibmacos_version_arg = MACOS_VERSIONS.get(selected_version_name, selected_version_name)

        chosen_path = QFileDialog.getExistingDirectory(self, "Select Directory to Download macOS Installer Assets")
        if not chosen_path: self.output_area.append("Download directory selection cancelled."); return
        self.macos_download_path = chosen_path

        worker = GibMacOSWorker(gibmacos_version_arg, self.macos_download_path)
        if not self._start_worker(worker, self.macos_download_finished, self.macos_download_error,
                                  "macos_download",
                                  f"Downloading macOS {selected_version_name} assets...",
                                  provides_progress=True): # Assuming GibMacOSWorker will emit progress_value
            self._set_ui_busy(False, "Failed to start macOS download operation.")


    @pyqtSlot(str)
    def macos_download_finished(self, message):
        QMessageBox.information(self, "Download Complete", message)
        # self.macos_download_path is set. UI update handled by generic handler.

    @pyqtSlot(str)
    def macos_download_error(self, error_message):
        QMessageBox.critical(self, "Download Error", error_message)
        self.macos_download_path = None
        # UI reset by generic handler.

    def stop_current_operation(self):
        if self.current_worker_instance and hasattr(self.current_worker_instance, 'stop'):
            self.output_area.append(f"
--- Attempting to stop {self.active_worker_thread.objectName().replace('_thread','')} ---")
            self.current_worker_instance.stop()
        else:
            self.output_area.append("
--- No active stoppable operation or stop method not implemented for current worker. ---")

    def handle_error(self, message):
        self.output_area.append(f"ERROR: {message}"); QMessageBox.critical(self, "Error", message)
        self._set_ui_busy(False, "Error occurred.")

    def check_admin_privileges(self) -> bool: # ... (same)
        try:
            if platform.system() == "Windows": return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else: return os.geteuid() == 0
        except Exception as e: self.output_area.append(f"Could not check admin privileges: {e}"); return False

    def refresh_usb_drives(self): # ... (same logic as before)
        self.usb_drive_combo.clear(); current_selection_text = getattr(self, '_current_usb_selection_text', None)
        self.output_area.append("
Scanning for disk devices...")
        if platform.system() == "Windows":
            self.usb_drive_label.setText("Available USB Disks (Windows - via WMI/PowerShell):")
            self.windows_usb_guidance_label.setVisible(True); self.windows_disk_id_input.setVisible(False);
            powershell_command = "Get-WmiObject Win32_DiskDrive | Where-Object {$_.InterfaceType -eq 'USB'} | Select-Object DeviceID, Index, Model, @{Name='SizeGB';Expression={[math]::Round($_.Size / 1GB, 2)}} | ConvertTo-Json"
            try:
                process = subprocess.run(["powershell", "-Command", powershell_command], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                disks_data = json.loads(process.stdout); disks_json = disks_data if isinstance(disks_data, list) else [disks_data] if disks_data else []
                if disks_json:
                    for disk in disks_json:
                        if disk.get('DeviceID') is None or disk.get('Index') is None: continue
                        disk_text = f"Disk {disk['Index']}: {disk.get('Model','N/A')} ({disk.get('SizeGB','N/A')} GB) - {disk['DeviceID']}"
                        self.usb_drive_combo.addItem(disk_text, userData=str(disk['Index']))
                    self.output_area.append(f"Found {len(disks_json)} USB disk(s) via WMI.");
                    if current_selection_text:
                        for i in range(self.usb_drive_combo.count()):
                            if self.usb_drive_combo.itemText(i) == current_selection_text: self.usb_drive_combo.setCurrentIndex(i); break
                else: self.output_area.append("No USB disks found via WMI/PowerShell. Manual input field shown as fallback."); self.windows_disk_id_input.setVisible(True)
            except Exception as e: self.output_area.append(f"Error scanning Windows USBs with PowerShell: {e}"); self.windows_disk_id_input.setVisible(True)
        else:
            self.usb_drive_label.setText("Available USB Drives (for Linux/macOS):")
            self.windows_usb_guidance_label.setVisible(False); self.windows_disk_id_input.setVisible(False)
            try:
                partitions = psutil.disk_partitions(all=False); potential_usbs = []
                for p in partitions:
                    is_removable = 'removable' in p.opts; is_likely_usb = False
                    if platform.system() == "Darwin" and p.device.startswith("/dev/disk") and 'external' in p.opts.lower() and 'physical' in p.opts.lower(): is_likely_usb = True
                    elif platform.system() == "Linux" and ((p.mountpoint and ("/media/" in p.mountpoint or "/run/media/" in p.mountpoint)) or                        (p.device.startswith("/dev/sd") and not p.device.endswith("da"))): is_likely_usb = True
                    if is_removable or is_likely_usb:
                        try: usage = psutil.disk_usage(p.mountpoint); size_gb = usage.total / (1024**3)
                        except Exception: continue
                        if size_gb < 0.1 : continue
                        drive_text = f"{p.device} @ {p.mountpoint} ({p.fstype}, {size_gb:.2f} GB)"
                        potential_usbs.append((drive_text, p.device))
                if potential_usbs:
                    idx_to_select = -1
                    for i, (text, device_path) in enumerate(potential_usbs): self.usb_drive_combo.addItem(text, userData=device_path);
                    if text == current_selection_text: idx_to_select = i
                    if idx_to_select != -1: self.usb_drive_combo.setCurrentIndex(idx_to_select)
                    self.output_area.append(f"Found {len(potential_usbs)} potential USB drive(s). Please verify carefully.")
                else: self.output_area.append("No suitable USB drives found for Linux/macOS.")
            except ImportError: self.output_area.append("psutil library not found.")
            except Exception as e: self.output_area.append(f"Error scanning for USB drives: {e}")
        self.update_all_button_states()


    def handle_write_to_usb(self):
        if not self.check_admin_privileges(): QMessageBox.warning(self, "Privileges Required", "This operation requires Administrator/root privileges."); return
        if not self.macos_download_path or not os.path.isdir(self.macos_download_path): QMessageBox.warning(self, "Missing macOS Assets", "Download macOS installer assets first."); return
        current_os = platform.system(); usb_writer_module = None; target_device_id_for_worker = None
        if current_os == "Windows": target_device_id_for_worker = self.usb_drive_combo.currentData() or self.windows_disk_id_input.text().strip(); usb_writer_module = USBWriterWindows
        else: target_device_id_for_worker = self.usb_drive_combo.currentData(); usb_writer_module = USBWriterLinux if current_os == "Linux" else USBWriterMacOS if current_os == "Darwin" else None
        if not usb_writer_module: QMessageBox.warning(self, "Unsupported Platform", f"USB writing not supported for {current_os}."); return
        if not target_device_id_for_worker: QMessageBox.warning(self, "No USB Selected/Identified", f"Please select/identify target USB."); return
        if current_os == "Windows" and target_device_id_for_worker.isdigit(): target_device_id_for_worker = f"disk {target_device_id_for_worker}"

        enhance_plist_state = self.enhance_plist_checkbox.isChecked()
        target_macos_name = self.version_combo.currentText()
        reply = QMessageBox.warning(self, "Confirm Write Operation", f"WARNING: ALL DATA ON TARGET '{target_device_id_for_worker}' WILL BE ERASED.
Proceed?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Cancel: self.output_area.append("
USB write cancelled."); return

        # USBWriterWorker now needs different args
        # The platform specific writers (USBWriterLinux etc) will need to be updated to accept macos_download_path
        # and use it to find BaseSystem.dmg, EFI/OC etc. instead of opencore_qcow2_path, macos_qcow2_path
        usb_worker_adapted = USBWriterWorker(
            device=target_device_id_for_worker,
            macos_download_path=self.macos_download_path,
            enhance_plist=enhance_plist_state,
            target_macos_version=target_macos_name
        )

        if not self._start_worker(usb_worker_adapted, self.usb_write_finished, self.usb_write_error, "usb_write_worker",
                                  busy_message=f"Creating USB for {target_device_id_for_worker}...",
                                  provides_progress=False): # USB writing can be long, but progress parsing is per-platform script.
            self._set_ui_busy(False, "Failed to start USB write operation.")

    @pyqtSlot(str)
    def usb_write_finished(self, message): QMessageBox.information(self, "USB Write Complete", message)
    @pyqtSlot(str)
    def usb_write_error(self, error_message): QMessageBox.critical(self, "USB Write Error", error_message)

    def closeEvent(self, event): # ... (same logic)
        self._current_usb_selection_text = self.usb_drive_combo.currentText()
        if self.active_worker_thread and self.active_worker_thread.isRunning():
            reply = QMessageBox.question(self, 'Confirm Exit', "An operation is running. Exit anyway?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if self.current_worker_instance and hasattr(self.current_worker_instance, 'stop'): self.current_worker_instance.stop()
                else: self.active_worker_thread.quit()
                self.active_worker_thread.wait(1000); event.accept()
            else: event.ignore(); return
        else: event.accept()


if __name__ == "__main__":
    import traceback # Ensure traceback is available for GibMacOSWorker
    import shutil # Ensure shutil is available for GibMacOSWorker path check
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
