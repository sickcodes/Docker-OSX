# main_app.py
import sys
import subprocess
import os
import psutil
import platform

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QMessageBox, QMenuBar,
    QFileDialog, QGroupBox, QLineEdit # Added QLineEdit
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QObject, QThread

from constants import APP_NAME, DEVELOPER_NAME, BUSINESS_NAME, MACOS_VERSIONS
from utils import (
    build_docker_command, get_unique_container_name,
    build_docker_cp_command, CONTAINER_MACOS_IMG_PATH, CONTAINER_OPENCORE_QCOW2_PATH,
    build_docker_stop_command, build_docker_rm_command
)

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

class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

class DockerRunWorker(QObject): # ... (same as before)
    def __init__(self, command_list):
        super().__init__()
        self.command_list = command_list
        self.signals = WorkerSignals()
        self.process = None
        self._is_running = True

    @pyqtSlot()
    def run(self):
        try:
            self.signals.progress.emit(f"Executing: {' '.join(self.command_list)}\n")
            self.process = subprocess.Popen(
                self.command_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ''):
                    if not self._is_running:
                        self.signals.progress.emit("Docker process stopping at user request.\n")
                        break
                    self.signals.progress.emit(line)
                self.process.stdout.close()
            return_code = self.process.wait()
            if not self._is_running and return_code != 0 :
                 self.signals.finished.emit(f"Docker process cancelled or stopped early (exit code {return_code}).")
                 return
            if return_code == 0:
                self.signals.finished.emit("Docker VM process (QEMU) closed by user or completed.")
            else:
                self.signals.finished.emit(f"Docker VM process exited (code {return_code}). Assuming macOS setup was attempted or QEMU window closed.")
        except FileNotFoundError: self.signals.error.emit("Error: Docker command not found.")
        except Exception as e: self.signals.error.emit(f"An error occurred during Docker run: {str(e)}")
        finally: self._is_running = False

    def stop(self):
        self._is_running = False
        if self.process and self.process.poll() is None:
            self.signals.progress.emit("Attempting to stop Docker process...\n")
            try:
                self.process.terminate()
                try: self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.signals.progress.emit("Process did not terminate gracefully, killing.\n")
                    self.process.kill()
                self.signals.progress.emit("Docker process stopped.\n")
            except Exception as e: self.signals.error.emit(f"Error stopping process: {str(e)}\n")

class DockerCommandWorker(QObject): # ... (same as before)
    def __init__(self, command_list, success_message="Command completed."):
        super().__init__()
        self.command_list = command_list
        self.signals = WorkerSignals()
        self.success_message = success_message

    @pyqtSlot()
    def run(self):
        try:
            self.signals.progress.emit(f"Executing: {' '.join(self.command_list)}\n")
            result = subprocess.run(
                self.command_list, capture_output=True, text=True, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if result.stdout and result.stdout.strip(): self.signals.progress.emit(result.stdout)
            if result.stderr and result.stderr.strip(): self.signals.progress.emit(f"STDERR: {result.stderr}")
            if result.returncode == 0: self.signals.finished.emit(self.success_message)
            else:
                err_msg = result.stderr or result.stdout or "Unknown error"
                self.signals.error.emit(f"Command failed with code {result.returncode}: {err_msg.strip()}")
        except FileNotFoundError: self.signals.error.emit("Error: Docker command not found.")
        except Exception as e: self.signals.error.emit(f"An error occurred: {str(e)}")

class USBWriterWorker(QObject): # ... (same as before, uses platform check)
    signals = WorkerSignals()
    def __init__(self, device, opencore_path, macos_path):
        super().__init__()
        self.device = device
        self.opencore_path = opencore_path
        self.macos_path = macos_path
        self.writer_instance = None

    @pyqtSlot()
    def run(self):
        current_os = platform.system()
        try:
            if current_os == "Linux":
                if USBWriterLinux is None: self.signals.error.emit("USBWriterLinux module not available."); return
                self.writer_instance = USBWriterLinux(self.device, self.opencore_path, self.macos_path, lambda msg: self.signals.progress.emit(msg))
            elif current_os == "Darwin":
                if USBWriterMacOS is None: self.signals.error.emit("USBWriterMacOS module not available."); return
                self.writer_instance = USBWriterMacOS(self.device, self.opencore_path, self.macos_path, lambda msg: self.signals.progress.emit(msg))
            elif current_os == "Windows":
                if USBWriterWindows is None: self.signals.error.emit("USBWriterWindows module not available."); return
                self.writer_instance = USBWriterWindows(self.device, self.opencore_path, self.macos_path, lambda msg: self.signals.progress.emit(msg))
            else:
                self.signals.error.emit(f"USB writing not supported on {current_os}."); return

            if self.writer_instance.format_and_write():
                self.signals.finished.emit("USB writing process completed successfully.")
            else:
                self.signals.error.emit("USB writing process failed. Check output for details.")
        except Exception as e:
            self.signals.error.emit(f"USB writing preparation error: {str(e)}")


class MainWindow(QMainWindow): # ... (init and _setup_ui need changes for Windows USB input)
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 800, 850) # Adjusted height
        self.current_container_name = None
        self.extracted_main_image_path = None
        self.extracted_opencore_image_path = None
        self.extraction_status = {"main": False, "opencore": False}
        self.active_worker_thread = None
        self.docker_run_worker_instance = None
        self._setup_ui()
        self.refresh_usb_drives()

    def _setup_ui(self):
        # ... (Menu bar, Step 1, 2, 3 groups - same as before) ...
        menubar = self.menuBar(); file_menu = menubar.addMenu("&File"); help_menu = menubar.addMenu("&Help")
        exit_action = QAction("&Exit", self); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
        about_action = QAction("&About", self); about_action.triggered.connect(self.show_about_dialog); help_menu.addAction(about_action)
        central_widget = QWidget(); self.setCentralWidget(central_widget); main_layout = QVBoxLayout(central_widget)
        vm_creation_group = QGroupBox("Step 1: Create and Install macOS VM"); vm_layout = QVBoxLayout()
        selection_layout = QHBoxLayout(); self.version_label = QLabel("Select macOS Version:"); self.version_combo = QComboBox()
        self.version_combo.addItems(MACOS_VERSIONS.keys()); selection_layout.addWidget(self.version_label); selection_layout.addWidget(self.version_combo)
        vm_layout.addLayout(selection_layout); self.run_vm_button = QPushButton("Create VM and Start macOS Installation")
        self.run_vm_button.clicked.connect(self.run_macos_vm); vm_layout.addWidget(self.run_vm_button)
        self.stop_vm_button = QPushButton("Stop/Cancel VM Creation"); self.stop_vm_button.clicked.connect(self.stop_docker_run_process)
        self.stop_vm_button.setEnabled(False); vm_layout.addWidget(self.stop_vm_button); vm_creation_group.setLayout(vm_layout)
        main_layout.addWidget(vm_creation_group)
        extraction_group = QGroupBox("Step 2: Extract VM Images"); ext_layout = QVBoxLayout()
        self.extract_images_button = QPushButton("Extract Images from Container"); self.extract_images_button.clicked.connect(self.extract_vm_images)
        self.extract_images_button.setEnabled(False); ext_layout.addWidget(self.extract_images_button); extraction_group.setLayout(ext_layout)
        main_layout.addWidget(extraction_group)
        mgmt_group = QGroupBox("Step 3: Container Management (Optional)"); mgmt_layout = QHBoxLayout()
        self.stop_container_button = QPushButton("Stop Container"); self.stop_container_button.clicked.connect(self.stop_persistent_container)
        self.stop_container_button.setEnabled(False); mgmt_layout.addWidget(self.stop_container_button)
        self.remove_container_button = QPushButton("Remove Container"); self.remove_container_button.clicked.connect(self.remove_persistent_container)
        self.remove_container_button.setEnabled(False); mgmt_layout.addWidget(self.remove_container_button); mgmt_group.setLayout(mgmt_layout)
        main_layout.addWidget(mgmt_group)

        # Step 4: USB Drive Selection - Modified for Windows
        usb_group = QGroupBox("Step 4: Select Target USB Drive and Write")
        usb_layout = QVBoxLayout()

        self.usb_drive_label = QLabel("Available USB Drives (for Linux/macOS):")
        usb_layout.addWidget(self.usb_drive_label)

        usb_selection_layout = QHBoxLayout()
        self.usb_drive_combo = QComboBox()
        self.usb_drive_combo.currentIndexChanged.connect(self.update_write_to_usb_button_state)
        usb_selection_layout.addWidget(self.usb_drive_combo)

        self.refresh_usb_button = QPushButton("Refresh List")
        self.refresh_usb_button.clicked.connect(self.refresh_usb_drives)
        usb_selection_layout.addWidget(self.refresh_usb_button)
        usb_layout.addLayout(usb_selection_layout)

        # Windows-specific input for disk ID
        self.windows_usb_input_label = QLabel("For Windows: Enter USB Disk Number (e.g., 1, 2). Use 'diskpart' -> 'list disk' in an Admin CMD to find it.")
        self.windows_disk_id_input = QLineEdit()
        self.windows_disk_id_input.setPlaceholderText("Enter Disk Number (e.g., 1)")
        self.windows_disk_id_input.textChanged.connect(self.update_write_to_usb_button_state)

        if platform.system() == "Windows":
            self.usb_drive_label.setText("Detected Mountable Partitions (for reference only for writing):")
            usb_layout.addWidget(self.windows_usb_input_label)
            usb_layout.addWidget(self.windows_disk_id_input)
        else:
            self.windows_usb_input_label.setVisible(False)
            self.windows_disk_id_input.setVisible(False)

        warning_label = QLabel("WARNING: Selecting a drive and proceeding to write will ERASE ALL DATA on it!")
        warning_label.setStyleSheet("color: red; font-weight: bold;")
        usb_layout.addWidget(warning_label)

        self.write_to_usb_button = QPushButton("Write Images to USB Drive")
        self.write_to_usb_button.clicked.connect(self.handle_write_to_usb)
        self.write_to_usb_button.setEnabled(False)
        usb_layout.addWidget(self.write_to_usb_button)

        usb_group.setLayout(usb_layout)
        main_layout.addWidget(usb_group)

        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        main_layout.addWidget(self.output_area)

    def show_about_dialog(self): # ... (same as before, update version)
        QMessageBox.about(self, f"About {APP_NAME}",
                          f"Version: 0.6.0\nDeveloper: {DEVELOPER_NAME}\nBusiness: {BUSINESS_NAME}\n\n"
                          "This tool helps create bootable macOS USB drives using Docker-OSX.")

    def _start_worker(self, worker_instance, on_finished_slot, on_error_slot, worker_name="worker"): # ... (same as before)
        if self.active_worker_thread and self.active_worker_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Another operation is already in progress. Please wait.")
            return False
        self.active_worker_thread = QThread()
        self.active_worker_thread.setObjectName(worker_name + "_thread")
        setattr(self, f"{worker_name}_instance", worker_instance)
        worker_instance.moveToThread(self.active_worker_thread)
        worker_instance.signals.progress.connect(self.update_output)
        worker_instance.signals.finished.connect(on_finished_slot)
        worker_instance.signals.error.connect(on_error_slot)
        worker_instance.signals.finished.connect(self.active_worker_thread.quit)
        worker_instance.signals.error.connect(self.active_worker_thread.quit)
        self.active_worker_thread.finished.connect(self.active_worker_thread.deleteLater)
        self.active_worker_thread.finished.connect(lambda: self._clear_worker_instance(worker_name)) # Use new clear method
        self.active_worker_thread.started.connect(worker_instance.run)
        self.active_worker_thread.start()
        return True

    def _clear_worker_instance(self, worker_name): # New method to clean up worker instance from self
        attr_name = f"{worker_name}_instance"
        if hasattr(self, attr_name):
            delattr(self, attr_name)

    def run_macos_vm(self): # ... (same as before, ensure worker_name matches for _clear_worker_instance)
        selected_version_name = self.version_combo.currentText()
        self.current_container_name = get_unique_container_name()
        try:
            command_list = build_docker_command(selected_version_name, self.current_container_name)
            self.output_area.clear()
            self.output_area.append(f"Starting macOS VM creation for {selected_version_name}...") # ... rest of messages

            docker_run_worker = DockerRunWorker(command_list) # Local var, instance stored by _start_worker
            if self._start_worker(docker_run_worker, self.docker_run_finished, self.docker_run_error, "docker_run"):
                self.run_vm_button.setEnabled(False); self.version_combo.setEnabled(False)
                self.stop_vm_button.setEnabled(True); self.extract_images_button.setEnabled(False)
                self.write_to_usb_button.setEnabled(False)
        except ValueError as e: self.handle_error(f"Failed to build command: {str(e)}")
        except Exception as e: self.handle_error(f"An unexpected error: {str(e)}")

    @pyqtSlot(str)
    def update_output(self, text): # ... (same as before)
        self.output_area.append(text.strip()); QApplication.processEvents()

    @pyqtSlot(str)
    def docker_run_finished(self, message): # ... (same as before)
        self.output_area.append(f"\n--- macOS VM Setup Process Finished ---\n{message}")
        QMessageBox.information(self, "VM Setup Complete", f"{message}\nYou can now proceed to extract images.")
        self.run_vm_button.setEnabled(True); self.version_combo.setEnabled(True)
        self.stop_vm_button.setEnabled(False); self.extract_images_button.setEnabled(True)
        self.stop_container_button.setEnabled(True)
        self.active_worker_thread = None # Cleared by _start_worker's finished connection


    @pyqtSlot(str)
    def docker_run_error(self, error_message): # ... (same as before)
        self.output_area.append(f"\n--- macOS VM Setup Process Error ---\n{error_message}")
        if "exited" in error_message.lower() and self.current_container_name:
             QMessageBox.warning(self, "VM Setup Ended", f"{error_message}\nAssuming macOS setup was attempted...")
             self.extract_images_button.setEnabled(True); self.stop_container_button.setEnabled(True)
        else: QMessageBox.critical(self, "VM Setup Error", error_message)
        self.run_vm_button.setEnabled(True); self.version_combo.setEnabled(True); self.stop_vm_button.setEnabled(False)
        self.active_worker_thread = None


    def stop_docker_run_process(self):
        docker_run_worker_inst = getattr(self, "docker_run_instance", None) # Use specific name
        if docker_run_worker_inst:
            self.output_area.append("\n--- Attempting to stop macOS VM creation ---")
            docker_run_worker_inst.stop()
        self.stop_vm_button.setEnabled(False)

    def extract_vm_images(self): # ... (same as before, ensure worker_names are unique)
        if not self.current_container_name: QMessageBox.warning(self, "Warning", "No active container."); return
        save_dir = QFileDialog.getExistingDirectory(self, "Select Directory to Save VM Images")
        if not save_dir: return
        self.output_area.append(f"\n--- Starting Image Extraction from {self.current_container_name} to {save_dir} ---")
        self.extract_images_button.setEnabled(False); self.write_to_usb_button.setEnabled(False)
        self.extracted_main_image_path = os.path.join(save_dir, "mac_hdd_ng.img")
        self.extracted_opencore_image_path = os.path.join(save_dir, "OpenCore.qcow2")
        self.extraction_status = {"main": False, "opencore": False}
        cp_main_cmd = build_docker_cp_command(self.current_container_name, CONTAINER_MACOS_IMG_PATH, self.extracted_main_image_path)
        main_worker = DockerCommandWorker(cp_main_cmd, f"Main macOS image copied to {self.extracted_main_image_path}")
        if not self._start_worker(main_worker, lambda msg: self.docker_utility_finished(msg, "main_img_extract"),
                                  lambda err: self.docker_utility_error(err, "main_img_extract_error"), "cp_main"): # Unique name
            self.extract_images_button.setEnabled(True); return
        self.output_area.append(f"Extraction for main image started. OpenCore extraction will follow.")


    def _start_opencore_extraction(self): # ... (same as before, ensure worker_name is unique)
        if not self.current_container_name or not self.extracted_opencore_image_path: return
        cp_oc_cmd = build_docker_cp_command(self.current_container_name, CONTAINER_OPENCORE_QCOW2_PATH, self.extracted_opencore_image_path)
        oc_worker = DockerCommandWorker(cp_oc_cmd, f"OpenCore image copied to {self.extracted_opencore_image_path}")
        self._start_worker(oc_worker, lambda msg: self.docker_utility_finished(msg, "oc_img_extract"),
                           lambda err: self.docker_utility_error(err, "oc_img_extract_error"), "cp_oc") # Unique name

    def stop_persistent_container(self): # ... (same as before, ensure worker_name is unique)
        if not self.current_container_name: QMessageBox.warning(self, "Warning", "No container name."); return
        cmd = build_docker_stop_command(self.current_container_name)
        worker = DockerCommandWorker(cmd, f"Container {self.current_container_name} stopped.")
        if self._start_worker(worker, lambda msg: self.docker_utility_finished(msg, "stop_container"),
                                  lambda err: self.docker_utility_error(err, "stop_container_error"), "stop_docker"): # Unique name
            self.stop_container_button.setEnabled(False)


    def remove_persistent_container(self): # ... (same as before, ensure worker_name is unique)
        if not self.current_container_name: QMessageBox.warning(self, "Warning", "No container name."); return
        reply = QMessageBox.question(self, 'Confirm Remove', f"Remove container '{self.current_container_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        cmd = build_docker_rm_command(self.current_container_name)
        worker = DockerCommandWorker(cmd, f"Container {self.current_container_name} removed.")
        if self._start_worker(worker, lambda msg: self.docker_utility_finished(msg, "rm_container"),
                                  lambda err: self.docker_utility_error(err, "rm_container_error"), "rm_docker"): # Unique name
            self.remove_container_button.setEnabled(False)

    def docker_utility_finished(self, message, task_id): # ... (same as before)
        self.output_area.append(f"\n--- Task '{task_id}' Succeeded ---\n{message}"); QMessageBox.information(self, f"Task Complete", message)
        if task_id == "main_img_extract": self.extraction_status["main"] = True; self._start_opencore_extraction(); return
        elif task_id == "oc_img_extract": self.extraction_status["opencore"] = True
        self.active_worker_thread = None # Cleared by _start_worker's finished connection
        if self.extraction_status.get("main") and self.extraction_status.get("opencore"):
            self.output_area.append("\nBoth VM images extracted successfully."); self.update_write_to_usb_button_state(); self.extract_images_button.setEnabled(True)
        elif task_id.startswith("extract"): self.extract_images_button.setEnabled(True)
        if task_id == "stop_container": self.remove_container_button.setEnabled(True)
        if task_id == "rm_container":
             self.current_container_name = None; self.stop_container_button.setEnabled(False)
             self.extract_images_button.setEnabled(False); self.update_write_to_usb_button_state()


    def docker_utility_error(self, error_message, task_id): # ... (same as before)
        self.output_area.append(f"\n--- Task '{task_id}' Error ---\n{error_message}"); QMessageBox.critical(self, f"Task Error", error_message)
        self.active_worker_thread = None
        if task_id.startswith("extract"): self.extract_images_button.setEnabled(True)
        if task_id == "stop_container": self.stop_container_button.setEnabled(True)
        if task_id == "rm_container": self.remove_container_button.setEnabled(True)


    def handle_error(self, message): # ... (same as before)
        self.output_area.append(f"ERROR: {message}"); QMessageBox.critical(self, "Error", message)
        self.run_vm_button.setEnabled(True); self.version_combo.setEnabled(True); self.stop_vm_button.setEnabled(False)
        self.extract_images_button.setEnabled(False); self.write_to_usb_button.setEnabled(False)
        self.active_worker_thread = None; # Clear active thread
        # Clear all potential worker instances
        for attr_name in list(self.__dict__.keys()):
            if attr_name.endswith("_instance") and isinstance(getattr(self,attr_name,None), QObject):
                setattr(self,attr_name,None)


    def refresh_usb_drives(self): # Modified for Windows
        self.usb_drive_combo.clear()
        current_selection_text = getattr(self, '_current_usb_selection_text', None)
        self.output_area.append("\nScanning for disk devices...")

        current_os = platform.system()
        if current_os == "Windows":
            self.usb_drive_label.setText("For Windows, identify Physical Disk number (e.g., 1, 2) using Disk Management or 'diskpart > list disk'. Input below.")
            self.windows_disk_id_input.setVisible(True)
            self.windows_usb_input_label.setVisible(True)
            self.usb_drive_combo.setVisible(False) # Hide combo for windows as input is manual
            self.refresh_usb_button.setText("List Partitions (Ref.)") # Change button text
            try:
                partitions = psutil.disk_partitions(all=True)
                ref_text = "Reference - Detected partitions/mounts:\n"
                for p in partitions:
                    try:
                        usage = psutil.disk_usage(p.mountpoint)
                        size_gb = usage.total / (1024**3)
                        ref_text += f"  {p.device} @ {p.mountpoint} ({p.fstype}, {size_gb:.2f} GB)\n"
                    except Exception:
                        ref_text += f"  {p.device} ({p.fstype}) - could not get usage/mountpoint\n"
                self.output_area.append(ref_text)
            except Exception as e:
                self.output_area.append(f"Error listing partitions for reference: {e}")
        else:
            self.usb_drive_label.setText("Available USB Drives (for Linux/macOS):")
            self.windows_disk_id_input.setVisible(False)
            self.windows_usb_input_label.setVisible(False)
            self.usb_drive_combo.setVisible(True)
            self.refresh_usb_button.setText("Refresh List")
            try: # psutil logic for Linux/macOS
                partitions = psutil.disk_partitions(all=False)
                potential_usbs = []
                for p in partitions:
                    is_removable = 'removable' in p.opts
                    is_likely_usb = False
                    if current_os == "Darwin":
                        if p.device.startswith("/dev/disk") and 'external' in p.opts.lower() and 'physical' in p.opts.lower(): is_likely_usb = True
                    elif current_os == "Linux":
                        if (p.mountpoint and ("/media/" in p.mountpoint or "/run/media/" in p.mountpoint)) or                            (p.device.startswith("/dev/sd") and not p.device.endswith("da")): is_likely_usb = True
                    if is_removable or is_likely_usb:
                        try:
                            usage = psutil.disk_usage(p.mountpoint)
                            size_gb = usage.total / (1024**3);
                            if size_gb < 0.1 : continue
                            drive_text = f"{p.device} @ {p.mountpoint} ({p.fstype}, {size_gb:.2f} GB)"
                            potential_usbs.append((drive_text, p.device))
                        except Exception: pass

                if potential_usbs:
                    idx_to_select = -1
                    for i, (text, device_path) in enumerate(potential_usbs):
                        self.usb_drive_combo.addItem(text, userData=device_path)
                        if text == current_selection_text: idx_to_select = i
                    if idx_to_select != -1: self.usb_drive_combo.setCurrentIndex(idx_to_select)
                    self.output_area.append(f"Found {len(potential_usbs)} potential USB drive(s). Please verify carefully.")
                else: self.output_area.append("No suitable USB drives found for Linux/macOS.")
            except ImportError: self.output_area.append("psutil library not found.")
            except Exception as e: self.output_area.append(f"Error scanning for USB drives: {e}")

        self.update_write_to_usb_button_state()


    def handle_write_to_usb(self): # Modified for Windows
        current_os = platform.system()
        usb_writer_module = None
        target_device_id_for_worker = None

        if current_os == "Linux":
            usb_writer_module = USBWriterLinux
            target_device_id_for_worker = self.usb_drive_combo.currentData()
        elif current_os == "Darwin":
            usb_writer_module = USBWriterMacOS
            target_device_id_for_worker = self.usb_drive_combo.currentData()
        elif current_os == "Windows":
            usb_writer_module = USBWriterWindows
            # For Windows, device_id for USBWriterWindows is the disk number string
            target_device_id_for_worker = self.windows_disk_id_input.text().strip()
            if not target_device_id_for_worker.isdigit(): # Basic validation
                 QMessageBox.warning(self, "Input Required", "Please enter a valid Windows Disk Number (e.g., 1, 2)."); return
            # USBWriterWindows expects just the number, it constructs \\.\PhysicalDriveX itself.

        if not usb_writer_module:
            QMessageBox.warning(self, "Unsupported Platform", f"USB writing not supported/enabled for {current_os}."); return

        if not self.extracted_main_image_path or not self.extracted_opencore_image_path or            not self.extraction_status["main"] or not self.extraction_status["opencore"]:
            QMessageBox.warning(self, "Missing Images", "Ensure both images are extracted."); return
        if not target_device_id_for_worker: # Should catch empty input for Windows here too
            QMessageBox.warning(self, "No USB Selected/Identified", f"Please select/identify the target USB drive for {current_os}."); return

        confirm_msg = (f"WARNING: ALL DATA ON TARGET '{target_device_id_for_worker}' WILL BE ERASED PERMANENTLY.
"
                       "Are you absolutely sure you want to proceed?")
        reply = QMessageBox.warning(self, "Confirm Write Operation", confirm_msg,
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                    QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Cancel:
            self.output_area.append("
USB write operation cancelled by user."); return

        self.output_area.append(f"
--- Starting USB Write Process for {target_device_id_for_worker} on {current_os} ---")
        self.write_to_usb_button.setEnabled(False); self.refresh_usb_button.setEnabled(False)

        usb_worker = USBWriterWorker(target_device_id_for_worker, self.extracted_opencore_image_path, self.extracted_main_image_path)
        if not self._start_worker(usb_worker, self.usb_write_finished, self.usb_write_error, "usb_write"): # worker_name "usb_write"
            self.write_to_usb_button.setEnabled(True); self.refresh_usb_button.setEnabled(True)

    @pyqtSlot(str)
    def usb_write_finished(self, message): # ... (same as before)
        self.output_area.append(f"
--- USB Write Process Finished ---
{message}"); QMessageBox.information(self, "USB Write Complete", message)
        self.write_to_usb_button.setEnabled(True); self.refresh_usb_button.setEnabled(True)
        self.active_worker_thread = None; setattr(self, "usb_write_instance", None)


    @pyqtSlot(str)
    def usb_write_error(self, error_message): # ... (same as before)
        self.output_area.append(f"
--- USB Write Process Error ---
{error_message}"); QMessageBox.critical(self, "USB Write Error", error_message)
        self.write_to_usb_button.setEnabled(True); self.refresh_usb_button.setEnabled(True)
        self.active_worker_thread = None; setattr(self, "usb_write_instance", None)

    def update_write_to_usb_button_state(self): # Modified for Windows
        images_ready = self.extraction_status.get("main", False) and self.extraction_status.get("opencore", False)
        usb_identified = False
        current_os = platform.system()
        writer_module = None

        if current_os == "Linux": writer_module = USBWriterLinux
        elif current_os == "Darwin": writer_module = USBWriterMacOS
        elif current_os == "Windows": writer_module = USBWriterWindows

        if current_os == "Windows":
            usb_identified = bool(self.windows_disk_id_input.text().strip().isdigit()) # Must be a digit for disk ID
        else:
            usb_identified = bool(self.usb_drive_combo.currentData())

        self.write_to_usb_button.setEnabled(images_ready and usb_identified and writer_module is not None)
        # ... (Tooltip logic same as before) ...
        if writer_module is None: self.write_to_usb_button.setToolTip(f"USB Writing not supported on {current_os} or module missing.")
        elif not images_ready: self.write_to_usb_button.setToolTip("Extract VM images first.")
        elif not usb_identified:
            if current_os == "Windows": self.write_to_usb_button.setToolTip("Enter a valid Windows Disk Number.")
            else: self.write_to_usb_button.setToolTip("Select a target USB drive.")
        else: self.write_to_usb_button.setToolTip("")


    def closeEvent(self, event): # ... (same as before)
        self._current_usb_selection_text = self.usb_drive_combo.currentText()
        if self.active_worker_thread and self.active_worker_thread.isRunning():
            reply = QMessageBox.question(self, 'Confirm Exit', "An operation is running. Exit anyway?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                worker_instance_attr_name = self.active_worker_thread.objectName().replace("_thread", "_instance")
                worker_to_stop = getattr(self, worker_instance_attr_name, None)
                if worker_to_stop and hasattr(worker_to_stop, 'stop'): worker_to_stop.stop()
                else: self.active_worker_thread.quit()
                self.active_worker_thread.wait(1000)
                event.accept()
            else: event.ignore(); return
        elif self.current_container_name and self.stop_container_button.isEnabled():
            reply = QMessageBox.question(self, 'Confirm Exit', f"Container '{self.current_container_name}' may still exist. Exit anyway?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes: event.accept()
            else: event.ignore()
        else: event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
