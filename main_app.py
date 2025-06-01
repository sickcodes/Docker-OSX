# main_app.py

import sys
import subprocess
import threading
import os
import psutil
import platform # For OS detection and USB writing logic

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QMessageBox, QMenuBar,
    QFileDialog, QGroupBox
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QObject, QThread

from constants import APP_NAME, DEVELOPER_NAME, BUSINESS_NAME, MACOS_VERSIONS
from utils import (
    build_docker_command, get_unique_container_name,
    build_docker_cp_command, CONTAINER_MACOS_IMG_PATH, CONTAINER_OPENCORE_QCOW2_PATH,
    build_docker_stop_command, build_docker_rm_command
)

# Import the Linux USB writer (conditionally or handle import error)
if platform.system() == "Linux":
    try:
        from usb_writer_linux import USBWriterLinux
    except ImportError:
        USBWriterLinux = None # Flag that it's not available
        print("Could not import USBWriterLinux. USB writing for Linux will be disabled.")
else:
    USBWriterLinux = None


# --- Worker Signals ---
class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

# --- Docker Process Worker ---
class DockerRunWorker(QObject):
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
            if not self._is_running and return_code != 0:
                self.signals.finished.emit("Docker process cancelled by user.")
                return
            if return_code == 0:
                self.signals.finished.emit("Docker VM process (QEMU) closed by user or completed.")
            else:
                self.signals.error.emit(f"Docker VM process exited with code {return_code}. Assuming macOS setup was attempted.")
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

# --- Docker Command Execution Worker ---
class DockerCommandWorker(QObject):
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
            if result.stdout: self.signals.progress.emit(result.stdout)
            if result.stderr: self.signals.progress.emit(f"STDERR: {result.stderr}")
            if result.returncode == 0: self.signals.finished.emit(self.success_message)
            else:
                err_msg = result.stderr or result.stdout or "Unknown error"
                self.signals.error.emit(f"Command failed with code {result.returncode}: {err_msg.strip()}")
        except FileNotFoundError: self.signals.error.emit("Error: Docker command not found.")
        except Exception as e: self.signals.error.emit(f"An error occurred: {str(e)}")


# --- USB Writing Worker ---
class USBWriterWorker(QObject):
    signals = WorkerSignals()

    def __init__(self, device, opencore_path, macos_path):
        super().__init__()
        self.device = device
        self.opencore_path = opencore_path
        self.macos_path = macos_path
        self.writer_instance = None

    @pyqtSlot()
    def run(self):
        try:
            if platform.system() == "Linux":
                if USBWriterLinux is None:
                    self.signals.error.emit("USBWriterLinux module not loaded. Cannot write to USB on this system.")
                    return

                self.writer_instance = USBWriterLinux(
                    self.device, self.opencore_path, self.macos_path,
                    progress_callback=lambda msg: self.signals.progress.emit(msg)
                )
                # Dependency check is called within format_and_write
                if self.writer_instance.format_and_write():
                    self.signals.finished.emit("USB writing process completed successfully.")
                else:
                    # Error message should have been emitted by the writer via progress_callback
                    self.signals.error.emit("USB writing process failed. Check output for details.")
            else:
                self.signals.error.emit(f"USB writing is not currently supported on {platform.system()}.")
        except Exception as e:
            self.signals.error.emit(f"An unexpected error occurred during USB writing preparation: {str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 800, 800)
        self.current_container_name = None
        self.extracted_main_image_path = None
        self.extracted_opencore_image_path = None
        self.extraction_status = {"main": False, "opencore": False}
        self.active_worker_thread = None # To manage various worker threads one at a time
        self._setup_ui()
        self.refresh_usb_drives()

    def _setup_ui(self):
        # ... (menu bar setup - same as before) ...
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        help_menu = menubar.addMenu("&Help")
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Step 1
        vm_creation_group = QGroupBox("Step 1: Create and Install macOS VM")
        vm_layout = QVBoxLayout()
        selection_layout = QHBoxLayout()
        self.version_label = QLabel("Select macOS Version:")
        self.version_combo = QComboBox()
        self.version_combo.addItems(MACOS_VERSIONS.keys())
        selection_layout.addWidget(self.version_label)
        selection_layout.addWidget(self.version_combo)
        vm_layout.addLayout(selection_layout)
        self.run_vm_button = QPushButton("Create VM and Start macOS Installation")
        self.run_vm_button.clicked.connect(self.run_macos_vm)
        vm_layout.addWidget(self.run_vm_button)
        self.stop_vm_button = QPushButton("Stop/Cancel VM Creation")
        self.stop_vm_button.clicked.connect(self.stop_docker_run_process)
        self.stop_vm_button.setEnabled(False)
        vm_layout.addWidget(self.stop_vm_button)
        vm_creation_group.setLayout(vm_layout)
        main_layout.addWidget(vm_creation_group)

        # Step 2
        extraction_group = QGroupBox("Step 2: Extract VM Images")
        ext_layout = QVBoxLayout()
        self.extract_images_button = QPushButton("Extract Images from Container")
        self.extract_images_button.clicked.connect(self.extract_vm_images)
        self.extract_images_button.setEnabled(False)
        ext_layout.addWidget(self.extract_images_button)
        extraction_group.setLayout(ext_layout)
        main_layout.addWidget(extraction_group)

        # Step 3
        mgmt_group = QGroupBox("Step 3: Container Management (Optional)")
        mgmt_layout = QHBoxLayout()
        self.stop_container_button = QPushButton("Stop Container")
        self.stop_container_button.clicked.connect(self.stop_persistent_container)
        self.stop_container_button.setEnabled(False)
        mgmt_layout.addWidget(self.stop_container_button)
        self.remove_container_button = QPushButton("Remove Container")
        self.remove_container_button.clicked.connect(self.remove_persistent_container)
        self.remove_container_button.setEnabled(False)
        mgmt_layout.addWidget(self.remove_container_button)
        mgmt_group.setLayout(mgmt_layout)
        main_layout.addWidget(mgmt_group)

        # Step 4: USB Drive Selection
        usb_group = QGroupBox("Step 4: Select Target USB Drive and Write") # Title updated
        usb_layout = QVBoxLayout()
        usb_selection_layout = QHBoxLayout()
        self.usb_drive_combo = QComboBox()
        self.usb_drive_combo.currentIndexChanged.connect(self.update_write_to_usb_button_state)
        usb_selection_layout.addWidget(QLabel("Available USB Drives:"))
        usb_selection_layout.addWidget(self.usb_drive_combo)
        self.refresh_usb_button = QPushButton("Refresh List")
        self.refresh_usb_button.clicked.connect(self.refresh_usb_drives)
        usb_selection_layout.addWidget(self.refresh_usb_button)
        usb_layout.addLayout(usb_selection_layout)
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

    def show_about_dialog(self):
        QMessageBox.about(self, f"About {APP_NAME}",
                          f"Version: 0.4.0\nDeveloper: {DEVELOPER_NAME}\nBusiness: {BUSINESS_NAME}\n\n"
                          "This tool helps create bootable macOS USB drives using Docker-OSX.")

    def _start_worker(self, worker_instance, on_finished_slot, on_error_slot):
        if self.active_worker_thread and self.active_worker_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Another operation is already in progress. Please wait.")
            return False

        self.active_worker_thread = QThread()
        worker_instance.moveToThread(self.active_worker_thread)

        worker_instance.signals.progress.connect(self.update_output)
        worker_instance.signals.finished.connect(on_finished_slot)
        worker_instance.signals.error.connect(on_error_slot)

        # Cleanup thread when worker is done
        worker_instance.signals.finished.connect(self.active_worker_thread.quit)
        worker_instance.signals.error.connect(self.active_worker_thread.quit)
        self.active_worker_thread.finished.connect(self.active_worker_thread.deleteLater)

        self.active_worker_thread.started.connect(worker_instance.run)
        self.active_worker_thread.start()
        return True

    def run_macos_vm(self):
        selected_version_name = self.version_combo.currentText()
        self.current_container_name = get_unique_container_name()
        try:
            command_list = build_docker_command(selected_version_name, self.current_container_name)
            self.output_area.clear()
            self.output_area.append(f"Starting macOS VM creation for {selected_version_name}...")
            self.output_area.append(f"Container name: {self.current_container_name}")
            self.output_area.append(f"Command: {' '.join(command_list)}\n")
            self.output_area.append("The macOS installation will occur in a QEMU window...\n")

            self.docker_run_worker_instance = DockerRunWorker(command_list) # Store instance
            if self._start_worker(self.docker_run_worker_instance, self.docker_run_finished, self.docker_run_error):
                self.run_vm_button.setEnabled(False)
                self.version_combo.setEnabled(False)
                self.stop_vm_button.setEnabled(True)
                self.extract_images_button.setEnabled(False)
                self.write_to_usb_button.setEnabled(False)
        except ValueError as e: self.handle_error(f"Failed to build command: {str(e)}")
        except Exception as e: self.handle_error(f"An unexpected error: {str(e)}")

    @pyqtSlot(str)
    def update_output(self, text):
        self.output_area.append(text.strip()) # append automatically scrolls
        QApplication.processEvents() # Keep UI responsive during rapid updates

    @pyqtSlot(str)
    def docker_run_finished(self, message):
        self.output_area.append(f"\n--- macOS VM Setup Process Finished ---\n{message}")
        QMessageBox.information(self, "VM Setup Complete", f"{message}\nYou can now proceed to extract images.")
        self.run_vm_button.setEnabled(True)
        self.version_combo.setEnabled(True)
        self.stop_vm_button.setEnabled(False)
        self.extract_images_button.setEnabled(True)
        self.stop_container_button.setEnabled(True)
        self.active_worker_thread = None # Allow new worker

    @pyqtSlot(str)
    def docker_run_error(self, error_message):
        self.output_area.append(f"\n--- macOS VM Setup Process Error ---\n{error_message}")
        if "exited with code" in error_message and self.current_container_name:
             QMessageBox.warning(self, "VM Setup Ended", f"{error_message}\nAssuming macOS setup was attempted...")
             self.extract_images_button.setEnabled(True)
             self.stop_container_button.setEnabled(True)
        else: QMessageBox.critical(self, "VM Setup Error", error_message)
        self.run_vm_button.setEnabled(True); self.version_combo.setEnabled(True); self.stop_vm_button.setEnabled(False)
        self.active_worker_thread = None

    def stop_docker_run_process(self):
        if hasattr(self, 'docker_run_worker_instance') and self.docker_run_worker_instance:
            self.output_area.append("\n--- Attempting to stop macOS VM creation ---")
            self.docker_run_worker_instance.stop() # Worker should handle signal emission
        self.stop_vm_button.setEnabled(False) # Disable to prevent multiple clicks

    def extract_vm_images(self):
        if not self.current_container_name:
            QMessageBox.warning(self, "Warning", "No active container specified for extraction."); return
        save_dir = QFileDialog.getExistingDirectory(self, "Select Directory to Save VM Images")
        if not save_dir: return

        self.output_area.append(f"\n--- Starting Image Extraction from {self.current_container_name} to {save_dir} ---")
        self.extract_images_button.setEnabled(False); self.write_to_usb_button.setEnabled(False)

        self.extracted_main_image_path = os.path.join(save_dir, "mac_hdd_ng.img")
        self.extracted_opencore_image_path = os.path.join(save_dir, "OpenCore.qcow2")
        self.extraction_status = {"main": False, "opencore": False}

        cp_main_cmd = build_docker_cp_command(self.current_container_name, CONTAINER_MACOS_IMG_PATH, self.extracted_main_image_path)
        main_worker = DockerCommandWorker(cp_main_cmd, f"Main macOS image copied to {self.extracted_main_image_path}")
        if not self._start_worker(main_worker,
                                  lambda msg: self.docker_utility_finished(msg, "main_img_extract"),
                                  lambda err: self.docker_utility_error(err, "main_img_extract_error")):
            self.extract_images_button.setEnabled(True) # Re-enable if start failed
            return # Don't proceed to second if first failed to start

        self.output_area.append(f"Extraction for main image started. OpenCore extraction will follow.")


    def _start_opencore_extraction(self): # Called after main image extraction finishes
        if not self.current_container_name or not self.extracted_opencore_image_path: return

        cp_oc_cmd = build_docker_cp_command(self.current_container_name, CONTAINER_OPENCORE_QCOW2_PATH, self.extracted_opencore_image_path)
        oc_worker = DockerCommandWorker(cp_oc_cmd, f"OpenCore image copied to {self.extracted_opencore_image_path}")
        self._start_worker(oc_worker,
                           lambda msg: self.docker_utility_finished(msg, "oc_img_extract"),
                           lambda err: self.docker_utility_error(err, "oc_img_extract_error"))


    def stop_persistent_container(self):
        if not self.current_container_name: QMessageBox.warning(self, "Warning", "No container name."); return
        self.output_area.append(f"\n--- Stopping container {self.current_container_name} ---")
        cmd = build_docker_stop_command(self.current_container_name)
        worker = DockerCommandWorker(cmd, f"Container {self.current_container_name} stopped.")
        if self._start_worker(worker, lambda msg: self.docker_utility_finished(msg, "stop_container"),
                                  lambda err: self.docker_utility_error(err, "stop_container_error")):
            self.stop_container_button.setEnabled(False)


    def remove_persistent_container(self):
        if not self.current_container_name: QMessageBox.warning(self, "Warning", "No container name."); return
        reply = QMessageBox.question(self, 'Confirm Remove', f"Remove container '{self.current_container_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        self.output_area.append(f"\n--- Removing container {self.current_container_name} ---")
        cmd = build_docker_rm_command(self.current_container_name)
        worker = DockerCommandWorker(cmd, f"Container {self.current_container_name} removed.")
        if self._start_worker(worker, lambda msg: self.docker_utility_finished(msg, "rm_container"),
                                  lambda err: self.docker_utility_error(err, "rm_container_error")):
            self.remove_container_button.setEnabled(False)


    def docker_utility_finished(self, message, task_id):
        self.output_area.append(f"\n--- Task '{task_id}' Succeeded ---\n{message}")
        QMessageBox.information(self, f"Task Complete", message)
        self.active_worker_thread = None # Allow new worker

        if task_id == "main_img_extract":
            self.extraction_status["main"] = True
            self._start_opencore_extraction() # Start next part of extraction
        elif task_id == "oc_img_extract":
            self.extraction_status["opencore"] = True

        if self.extraction_status.get("main") and self.extraction_status.get("opencore"):
            self.output_area.append("\nBoth VM images extracted successfully.")
            self.update_write_to_usb_button_state()
            self.extract_images_button.setEnabled(True)
        elif task_id.startswith("extract"): # If one part finished but not both
            self.extract_images_button.setEnabled(True)

        if task_id == "stop_container":
            self.remove_container_button.setEnabled(True)
        if task_id == "rm_container":
             self.current_container_name = None
             self.stop_container_button.setEnabled(False)
             self.extract_images_button.setEnabled(False)
             self.update_write_to_usb_button_state() # Should disable it


    def docker_utility_error(self, error_message, task_id):
        self.output_area.append(f"\n--- Task '{task_id}' Error ---\n{error_message}")
        QMessageBox.critical(self, f"Task Error", error_message)
        self.active_worker_thread = None
        if task_id.startswith("extract"): self.extract_images_button.setEnabled(True)
        if task_id == "stop_container": self.stop_container_button.setEnabled(True) # Allow retry
        if task_id == "rm_container": self.remove_container_button.setEnabled(True) # Allow retry


    def handle_error(self, message):
        self.output_area.append(f"ERROR: {message}")
        QMessageBox.critical(self, "Error", message)
        self.run_vm_button.setEnabled(True); self.version_combo.setEnabled(True)
        self.stop_vm_button.setEnabled(False); self.extract_images_button.setEnabled(False)
        self.write_to_usb_button.setEnabled(False)
        self.active_worker_thread = None

    def refresh_usb_drives(self):
        self.usb_drive_combo.clear()
        self._current_usb_selection_path = self.usb_drive_combo.currentData() # Save current selection
        self.output_area.append("\nScanning for USB drives...")
        try:
            partitions = psutil.disk_partitions(all=False)
            potential_usbs = []
            for p in partitions:
                is_removable = 'removable' in p.opts
                is_likely_usb = False

                if platform.system() == "Windows":
                    # A more reliable method for Windows would involve WMI or ctypes to query drive types.
                    # This is a basic filter.
                    if p.mountpoint and p.fstype and p.fstype.lower() not in ['ntfs', 'refs', 'cdfs'] and len(p.mountpoint) <= 3: # e.g. E:\
                        is_likely_usb = True
                elif platform.system() == "Darwin":
                    if p.device.startswith("/dev/disk") and (os.path.exists(f"/sys/block/{os.path.basename(p.device)}/removable") or "external" in p.opts.lower()): # Check 'external' from mount options
                         is_likely_usb = True
                elif platform.system() == "Linux":
                    # Check if /sys/block/sdX/removable exists and is 1
                    try:
                        with open(f"/sys/block/{os.path.basename(p.device)}/removable", "r") as f:
                            if f.read().strip() == "1":
                                is_likely_usb = True
                    except IOError: # If the removable file doesn't exist, it's likely not a USB mass storage
                        pass
                    if not is_likely_usb and (p.mountpoint and ("/media/" in p.mountpoint or "/run/media/" in p.mountpoint)): # Fallback to mountpoint
                        is_likely_usb = True

                if is_removable or is_likely_usb:
                    try:
                        # Attempt to get disk usage. If it fails, it might be an unformatted or problematic drive.
                        usage = psutil.disk_usage(p.mountpoint)
                        size_gb = usage.total / (1024**3)
                        if size_gb < 0.1 : continue
                        drive_text = f"{p.device} @ {p.mountpoint} ({p.fstype}, {size_gb:.2f} GB)"
                        potential_usbs.append((drive_text, p.device))
                    except Exception: pass

            idx_to_select = -1
            if potential_usbs:
                for i, (text, device_path) in enumerate(potential_usbs):
                    self.usb_drive_combo.addItem(text, userData=device_path)
                    if device_path == self._current_usb_selection_path:
                        idx_to_select = i
                self.output_area.append(f"Found {len(potential_usbs)} potential USB drive(s). Please verify carefully.")
            else: self.output_area.append("No suitable USB drives found. Ensure drive is connected, formatted, and mounted.")

            if idx_to_select != -1: self.usb_drive_combo.setCurrentIndex(idx_to_select)

        except ImportError: self.output_area.append("psutil library not found. USB detection disabled.")
        except Exception as e: self.output_area.append(f"Error scanning for USB drives: {e}")
        self.update_write_to_usb_button_state()


    def handle_write_to_usb(self):
        if platform.system() != "Linux":
            QMessageBox.warning(self, "Unsupported Platform", f"USB writing is currently only implemented for Linux. Your system: {platform.system()}")
            return

        if USBWriterLinux is None:
            QMessageBox.critical(self, "Error", "USBWriterLinux module could not be loaded. Cannot write to USB.")
            return

        selected_drive_device = self.usb_drive_combo.currentData()
        if not self.extracted_main_image_path or not self.extracted_opencore_image_path or            not self.extraction_status["main"] or not self.extraction_status["opencore"]:
            QMessageBox.warning(self, "Missing Images", "Ensure both images are extracted."); return
        if not selected_drive_device:
            QMessageBox.warning(self, "No USB Selected", "Please select a target USB drive."); return

        confirm_msg = (f"WARNING: ALL DATA ON {selected_drive_device} WILL BE ERASED PERMANENTLY.\n"
                       "Are you absolutely sure you want to proceed?")
        reply = QMessageBox.warning(self, "Confirm Write Operation", confirm_msg,
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                    QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Cancel:
            self.output_area.append("\nUSB write operation cancelled by user."); return

        self.output_area.append(f"\n--- Starting USB Write Process for {selected_drive_device} ---")
        self.output_area.append("This will take a long time and requires sudo privileges for underlying commands.")

        usb_worker = USBWriterWorker(selected_drive_device, self.extracted_opencore_image_path, self.extracted_main_image_path)
        if self._start_worker(usb_worker, self.usb_write_finished, self.usb_write_error):
            self.write_to_usb_button.setEnabled(False) # Disable during write
            self.refresh_usb_button.setEnabled(False)
        else: # Failed to start worker (another is running)
            pass # Message already shown by _start_worker


    @pyqtSlot(str)
    def usb_write_finished(self, message):
        self.output_area.append(f"\n--- USB Write Process Finished ---\n{message}")
        QMessageBox.information(self, "USB Write Complete", message)
        self.write_to_usb_button.setEnabled(True) # Re-enable after completion
        self.refresh_usb_button.setEnabled(True)
        self.active_worker_thread = None

    @pyqtSlot(str)
    def usb_write_error(self, error_message):
        self.output_area.append(f"\n--- USB Write Process Error ---\n{error_message}")
        QMessageBox.critical(self, "USB Write Error", error_message)
        self.write_to_usb_button.setEnabled(True) # Re-enable after error
        self.refresh_usb_button.setEnabled(True)
        self.active_worker_thread = None

    def update_write_to_usb_button_state(self):
        images_ready = self.extraction_status.get("main", False) and self.extraction_status.get("opencore", False)
        usb_selected = bool(self.usb_drive_combo.currentData())
        can_write_on_platform = platform.system() == "Linux" and USBWriterLinux is not None

        self.write_to_usb_button.setEnabled(images_ready and usb_selected and can_write_on_platform)
        if not can_write_on_platform and usb_selected and images_ready:
            self.write_to_usb_button.setToolTip("USB writing currently only supported on Linux with all dependencies.")
        else:
            self.write_to_usb_button.setToolTip("")


    def closeEvent(self, event):
        if self.active_worker_thread and self.active_worker_thread.isRunning():
            reply = QMessageBox.question(self, 'Confirm Exit', "An operation is running. Exit anyway?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # Attempt to stop the specific worker if identifiable, or just quit thread
                # For DockerRunWorker:
                if hasattr(self, 'docker_run_worker_instance') and self.active_worker_thread.findChild(DockerRunWorker):
                     self.docker_run_worker_instance.stop()
                # For USBWriterWorker, it doesn't have an explicit stop, rely on thread termination.

                self.active_worker_thread.quit()
                if not self.active_worker_thread.wait(1000): # brief wait
                    self.output_area.append("Worker thread did not terminate gracefully. Forcing exit.")
                event.accept()
            else: event.ignore()
        elif self.current_container_name and self.stop_container_button.isEnabled(): # Check only if stop button is enabled (meaning container might be running or exists)
            reply = QMessageBox.question(self, 'Confirm Exit', f"Container '{self.current_container_name}' may still exist or be running. It's recommended to stop and remove it using the GUI buttons. Exit anyway?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes: event.accept()
            else: event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
