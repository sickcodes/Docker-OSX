# main_app.py
import sys
import subprocess
import os
import psutil
import platform
import ctypes
import json # For parsing PowerShell JSON output

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QMessageBox, QMenuBar,
    QFileDialog, QGroupBox, QLineEdit, QProgressBar
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal, pyqtSlot, QObject, QThread, QTimer, Qt # Added QTimer

# ... (Worker classes and other imports remain the same) ...
from constants import APP_NAME, DEVELOPER_NAME, BUSINESS_NAME, MACOS_VERSIONS, DOCKER_IMAGE_BASE
from utils import (
    build_docker_command, get_unique_container_name,
    build_docker_cp_command, CONTAINER_MACOS_IMG_PATH, CONTAINER_OPENCORE_QCOW2_PATH,
    build_docker_stop_command, build_docker_rm_command
)

USBWriterLinux = None; USBWriterMacOS = None; USBWriterWindows = None
if platform.system() == "Linux":
    try: from usb_writer_linux import USBWriterLinux
    except ImportError as e: print(f"Could not import USBWriterLinux: {e}")
elif platform.system() == "Darwin":
    try: from usb_writer_macos import USBWriterMacOS
    except ImportError as e: print(f"Could not import USBWriterMacOS: {e}")
elif platform.system() == "Windows":
    try: from usb_writer_windows import USBWriterWindows
    except ImportError as e: print(f"Could not import USBWriterWindows: {e}")

class WorkerSignals(QObject): progress = pyqtSignal(str); finished = pyqtSignal(str); error = pyqtSignal(str)

class DockerPullWorker(QObject): # ... ( 그대로 )
    signals = WorkerSignals()
    def __init__(self, image_name: str): super().__init__(); self.image_name = image_name
    @pyqtSlot()
    def run(self):
        try:
            command = ["docker", "pull", self.image_name]; self.signals.progress.emit(f"Pulling Docker image: {self.image_name}...\n")
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if process.stdout:
                for line in iter(process.stdout.readline, ''): self.signals.progress.emit(line)
                process.stdout.close()
            return_code = process.wait()
            if return_code == 0: self.signals.finished.emit(f"Image '{self.image_name}' pulled successfully or already exists.")
            else: self.signals.error.emit(f"Failed to pull image '{self.image_name}' (exit code {return_code}).")
        except FileNotFoundError: self.signals.error.emit("Error: Docker command not found.")
        except Exception as e: self.signals.error.emit(f"An error occurred during docker pull: {str(e)}")

class DockerRunWorker(QObject): # ... ( 그대로 )
    signals = WorkerSignals()
    def __init__(self, command_list): super().__init__(); self.command_list = command_list; self.process = None; self._is_running = True
    @pyqtSlot()
    def run(self):
        try:
            self.signals.progress.emit(f"Executing: {' '.join(self.command_list)}\n")
            self.process = subprocess.Popen(self.command_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ''):
                    if not self._is_running: self.signals.progress.emit("Docker process stopping at user request.\n"); break
                    self.signals.progress.emit(line)
                self.process.stdout.close()
            return_code = self.process.wait()
            if not self._is_running and return_code != 0 : self.signals.finished.emit(f"Docker process cancelled or stopped early (exit code {return_code})."); return
            if return_code == 0: self.signals.finished.emit("Docker VM process (QEMU) closed by user or completed.")
            else: self.signals.finished.emit(f"Docker VM process exited (code {return_code}). Assuming macOS setup was attempted or QEMU window closed.")
        except FileNotFoundError: self.signals.error.emit("Error: Docker command not found.")
        except Exception as e: self.signals.error.emit(f"An error occurred during Docker run: {str(e)}")
        finally: self._is_running = False
    def stop(self):
        self._is_running = False
        if self.process and self.process.poll() is None:
            self.signals.progress.emit("Attempting to stop Docker process...\n")
            try: self.process.terminate(); self.process.wait(timeout=5)
            except subprocess.TimeoutExpired: self.signals.progress.emit("Process did not terminate gracefully, killing.\n"); self.process.kill()
            self.signals.progress.emit("Docker process stopped.\n")
        elif self.process and self.process.poll() is not None: self.signals.progress.emit("Docker process already stopped.\n")

class DockerCommandWorker(QObject): # ... ( 그대로 )
    signals = WorkerSignals()
    def __init__(self, command_list, success_message="Command completed."): super().__init__(); self.command_list = command_list; self.signals = WorkerSignals(); self.success_message = success_message
    @pyqtSlot()
    def run(self):
        try:
            self.signals.progress.emit(f"Executing: {' '.join(self.command_list)}\n"); result = subprocess.run(self.command_list, capture_output=True, text=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if result.stdout and result.stdout.strip(): self.signals.progress.emit(result.stdout)
            if result.stderr and result.stderr.strip(): self.signals.progress.emit(f"STDERR: {result.stderr}")
            if result.returncode == 0: self.signals.finished.emit(self.success_message)
            else: self.signals.error.emit(f"Command failed (code {result.returncode}): {result.stderr or result.stdout or 'Unknown error'}".strip())
        except FileNotFoundError: self.signals.error.emit("Error: Docker command not found.")
        except Exception as e: self.signals.error.emit(f"An error occurred: {str(e)}")

class USBWriterWorker(QObject):
    signals = WorkerSignals()
    def __init__(self, device, opencore_path, macos_path, enhance_plist: bool, target_macos_version: str): # Added new args
        super().__init__()
        self.device = device
        self.opencore_path = opencore_path
        self.macos_path = macos_path
        self.enhance_plist = enhance_plist # Store
        self.target_macos_version = target_macos_version # Store
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

            # Pass new args to platform writer constructor
            self.writer_instance = writer_cls(
                self.device, self.opencore_path, self.macos_path,
                progress_callback=lambda msg: self.signals.progress.emit(msg), # Ensure progress_callback is named if it's a kwarg in writers
                enhance_plist_enabled=self.enhance_plist,
                target_macos_version=self.target_macos_version
            )

            if self.writer_instance.format_and_write():
                self.signals.finished.emit("USB writing process completed successfully.")
            else:
                self.signals.error.emit("USB writing process failed. Check output for details.")
        except Exception as e:
            self.signals.error.emit(f"USB writing preparation error: {str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 800, 900) # Adjusted height for progress bar in status bar

        self.current_container_name = None; self.extracted_main_image_path = None; self.extracted_opencore_image_path = None
        self.extraction_status = {"main": False, "opencore": False}; self.active_worker_thread = None
        self.docker_run_worker_instance = None; self.docker_pull_worker_instance = None # Specific worker instances
        self._current_usb_selection_text = None

        self.spinner_chars = ["|", "/", "-", "\\"]
        self.spinner_index = 0
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self._update_spinner_status)
        self.base_status_message = "Ready." # Default status message

        self._setup_ui() # Call before using self.statusBar
        self.status_bar = self.statusBar() # Initialize status bar early
        self.status_bar.addPermanentWidget(self.progressBar) # Add progress bar to status bar
        self.status_bar.showMessage(self.base_status_message, 5000) # Initial ready message

        self.refresh_usb_drives()

    def _setup_ui(self):
        menubar = self.menuBar(); file_menu = menubar.addMenu("&File"); help_menu = menubar.addMenu("&Help")
        exit_action = QAction("&Exit", self); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
        about_action = QAction("&About", self); about_action.triggered.connect(self.show_about_dialog); help_menu.addAction(about_action)
        central_widget = QWidget(); self.setCentralWidget(central_widget); main_layout = QVBoxLayout(central_widget)

        # Steps 1, 2, 3 remain the same UI structure
        vm_creation_group = QGroupBox("Step 1: Create and Install macOS VM"); vm_layout = QVBoxLayout()
        selection_layout = QHBoxLayout(); self.version_label = QLabel("Select macOS Version:"); self.version_combo = QComboBox()
        self.version_combo.addItems(MACOS_VERSIONS.keys()); selection_layout.addWidget(self.version_label); selection_layout.addWidget(self.version_combo)
        vm_layout.addLayout(selection_layout); self.run_vm_button = QPushButton("Create VM and Start macOS Installation")
        self.run_vm_button.clicked.connect(self.initiate_vm_creation_flow); vm_layout.addWidget(self.run_vm_button)
        self.stop_vm_button = QPushButton("Stop/Cancel Current Docker Operation"); self.stop_vm_button.clicked.connect(self.stop_current_docker_operation)
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

        # Step 4: USB Drive Selection - UI now adapts to Windows
        usb_group = QGroupBox("Step 4: Select Target USB Drive and Write")
        self.usb_layout = QVBoxLayout()

        self.usb_drive_label = QLabel("Available USB Drives:")
        self.usb_layout.addWidget(self.usb_drive_label)

        usb_selection_layout = QHBoxLayout()
        self.usb_drive_combo = QComboBox()
        self.usb_drive_combo.currentIndexChanged.connect(self.update_write_to_usb_button_state)
        usb_selection_layout.addWidget(self.usb_drive_combo)

        self.refresh_usb_button = QPushButton("Refresh List")
        self.refresh_usb_button.clicked.connect(self.refresh_usb_drives)
        usb_selection_layout.addWidget(self.refresh_usb_button)
        self.usb_layout.addLayout(usb_selection_layout)

        # Windows-specific input for disk ID - initially hidden and managed by refresh_usb_drives
        self.windows_usb_guidance_label = QLabel("For Windows: Detected USB Disks (select from dropdown).")
        self.windows_usb_input_label = QLabel("Manual Fallback: Enter USB Disk Number (e.g., 1, 2):")
        self.windows_disk_id_input = QLineEdit()
        self.windows_disk_id_input.setPlaceholderText("Enter Disk Number if dropdown empty")
        self.windows_disk_id_input.textChanged.connect(self.update_write_to_usb_button_state)

        self.usb_layout.addWidget(self.windows_usb_guidance_label)
        self.usb_layout.addWidget(self.windows_usb_input_label)
        self.usb_layout.addWidget(self.windows_disk_id_input)
        # Visibility will be toggled in refresh_usb_drives based on OS

        self.enhance_plist_checkbox = QCheckBox("Try to auto-enhance config.plist for this system's hardware (Experimental, Linux Host Only for detection)")
        self.enhance_plist_checkbox.setChecked(False) # Off by default
        self.enhance_plist_checkbox.setToolTip(
            "If checked, attempts to modify the OpenCore config.plist based on detected host hardware (Linux only for detection part).\n"
            "This might improve compatibility for iGPU, audio, Ethernet. Use with caution."
        )
        self.usb_layout.addWidget(self.enhance_plist_checkbox)

        warning_label = QLabel("WARNING: Selecting a drive and proceeding to write will ERASE ALL DATA on it!")
        warning_label.setStyleSheet("color: red; font-weight: bold;")
        self.usb_layout.addWidget(warning_label)

        self.write_to_usb_button = QPushButton("Write Images to USB Drive")
        self.write_to_usb_button.clicked.connect(self.handle_write_to_usb)
        self.write_to_usb_button.setEnabled(False)
        self.usb_layout.addWidget(self.write_to_usb_button)

        usb_group.setLayout(self.usb_layout)
        main_layout.addWidget(usb_group)

        self.output_area = QTextEdit(); self.output_area.setReadOnly(True); main_layout.addWidget(self.output_area)

        # Status Bar and Progress Bar
        self.statusBar = self.statusBar()
        self.progressBar = QProgressBar(self)
        self.progressBar.setRange(0, 0) # Indeterminate
        self.progressBar.setVisible(False)
        self.statusBar.addPermanentWidget(self.progressBar) # Corrected addPermanentWidget call


    def _set_ui_busy(self, is_busy: bool, status_message: str = "Processing..."): # Default busy message
        """Manages UI element states and progress indicators, including spinner."""
        self.general_interactive_widgets = [
            self.run_vm_button, self.version_combo, self.extract_images_button,
            self.stop_container_button, self.remove_container_button,
            self.usb_drive_combo, self.refresh_usb_button, self.write_to_usb_button,
            self.windows_disk_id_input, self.enhance_plist_checkbox
        ]

        if is_busy:
            self.base_status_message = status_message # Store the core message for spinner
            for widget in self.general_interactive_widgets:
                widget.setEnabled(False)
            # self.stop_vm_button is handled by _start_worker
            self.progressBar.setVisible(True)
            if not self.spinner_timer.isActive(): # Start spinner if not already active
                self.spinner_index = 0
                self.spinner_timer.start(150)
            self._update_spinner_status() # Show initial spinner message
        else:
            self.spinner_timer.stop()
            self.progressBar.setVisible(False)
            self.statusBar.showMessage(status_message or "Ready.", 7000) # Show final message longer
            self.update_all_button_states() # Centralized button state update

    def _update_spinner_status(self):
        """Updates the status bar message with a spinner."""
        if self.spinner_timer.isActive() and self.active_worker_thread and self.active_worker_thread.isRunning():
            char = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
            # Check if current worker is providing determinate progress
            worker_name = self.active_worker_thread.objectName().replace("_thread", "")
            worker_provides_progress = getattr(self, f"{worker_name}_provides_progress", False)

            if worker_provides_progress and self.progressBar.maximum() == 100 and self.progressBar.value() > 0 : # Determinate
                 # For determinate, status bar shows base message, progress bar shows percentage
                 self.statusBar.showMessage(f"{char} {self.base_status_message} ({self.progressBar.value()}%)")
            else: # Indeterminate
                 if self.progressBar.maximum() != 0: self.progressBar.setRange(0,0) # Ensure indeterminate
                 self.statusBar.showMessage(f"{char} {self.base_status_message}")

            self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
        elif not (self.active_worker_thread and self.active_worker_thread.isRunning()): # If timer is somehow active but no worker
            self.spinner_timer.stop()
            # self.statusBar.showMessage(self.base_status_message or "Ready.", 5000) # Show last base message or ready

    def update_all_button_states(self): # Renamed from update_button_states_after_operation
        """Centralized method to update button states based on app's current state."""
        is_worker_running = self.active_worker_thread and self.active_worker_thread.isRunning()

        self.run_vm_button.setEnabled(not is_worker_running)
        self.version_combo.setEnabled(not is_worker_running)

        pull_worker_active = getattr(self, "docker_pull_instance", None) is not None
        run_worker_active = getattr(self, "docker_run_instance", None) is not None
        self.stop_vm_button.setEnabled(is_worker_running and (pull_worker_active or run_worker_active))

        can_extract = self.current_container_name is not None and not is_worker_running
        self.extract_images_button.setEnabled(can_extract)

        can_manage_container = self.current_container_name is not None and not is_worker_running
        self.stop_container_button.setEnabled(can_manage_container)
        # Remove button is enabled if container exists and no worker is running (simplification)
        # A more accurate state for remove_container_button would be if the container is actually stopped.
        # This is typically handled by the finished slot of the stop_container worker.
        # For now, this is a general enablement if not busy.
        self.remove_container_button.setEnabled(can_manage_container)


        self.refresh_usb_button.setEnabled(not is_worker_running)
        self.update_write_to_usb_button_state() # This handles its own complex logic

    def show_about_dialog(self):
        QMessageBox.about(self, f"About {APP_NAME}", f"Version: 0.8.2\nDeveloper: {DEVELOPER_NAME}\nBusiness: {BUSINESS_NAME}\n\nThis tool helps create bootable macOS USB drives using Docker-OSX.")

    def _start_worker(self, worker_instance, on_finished_slot, on_error_slot, worker_name="worker", busy_message="Processing...", provides_progress=False): # Added provides_progress
        if self.active_worker_thread and self.active_worker_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Another operation is in progress."); return False

        self._set_ui_busy(True, busy_message) # This now also starts the spinner

        # Set progress bar type based on worker capability
        if provides_progress:
            self.progress_bar.setRange(0, 100) # Determinate
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setRange(0, 0) # Indeterminate

        # Store if this worker provides progress for spinner logic
        setattr(self, f"{worker_name}_provides_progress", provides_progress)


        if worker_name in ["docker_pull", "docker_run"]:
            self.stop_vm_button.setEnabled(True)
        else:
            self.stop_vm_button.setEnabled(False)

        self.active_worker_thread = QThread(); self.active_worker_thread.setObjectName(worker_name + "_thread"); setattr(self, f"{worker_name}_instance", worker_instance)
        worker_instance.moveToThread(self.active_worker_thread)

        worker_instance.signals.progress.connect(self.update_output)
        if provides_progress: # Connect progress_value only if worker provides it
            worker_instance.signals.progress_value.connect(self.update_progress_bar_value)
        worker_instance.signals.finished.connect(lambda message, wn=worker_name, slot=on_finished_slot: self._handle_worker_finished(message, wn, slot))
        worker_instance.signals.error.connect(lambda error_message, wn=worker_name, slot=on_error_slot: self._handle_worker_error(error_message, wn, slot))

        self.active_worker_thread.finished.connect(self.active_worker_thread.deleteLater)
        self.active_worker_thread.started.connect(worker_instance.run); self.active_worker_thread.start(); return True

    @pyqtSlot(int)
    def update_progress_bar_value(self, value):
        if self.progress_bar.minimum() == 0 and self.progress_bar.maximum() == 0: # If it was indeterminate
            self.progress_bar.setRange(0,100) # Switch to determinate
        self.progress_bar.setValue(value)
        # Spinner will update with percentage from progress_bar.value()

    def _handle_worker_finished(self, message, worker_name, specific_finished_slot):
        final_status_message = f"{worker_name.replace('_', ' ').capitalize()} completed."
        self._clear_worker_instance(worker_name)
        self.active_worker_thread = None
        if specific_finished_slot: specific_finished_slot(message)
        self._set_ui_busy(False, final_status_message)

    def _handle_worker_error(self, error_message, worker_name, specific_error_slot):
        final_status_message = f"{worker_name.replace('_', ' ').capitalize()} failed."
        self._clear_worker_instance(worker_name)
        self.active_worker_thread = None
        if specific_error_slot: specific_error_slot(error_message)
        self._set_ui_busy(False, final_status_message)

    def _clear_worker_instance(self, worker_name):
        attr_name = f"{worker_name}_instance"
        if hasattr(self, attr_name): delattr(self, attr_name)

    def initiate_vm_creation_flow(self):
        self.output_area.clear(); selected_version_name = self.version_combo.currentText(); image_tag = MACOS_VERSIONS.get(selected_version_name)
        if not image_tag: self.handle_error(f"Invalid macOS version: {selected_version_name}"); return
        full_image_name = f"{DOCKER_IMAGE_BASE}:{image_tag}"
        pull_worker = DockerPullWorker(full_image_name)
        self._start_worker(pull_worker,
                           self.docker_pull_finished,
                           self.docker_pull_error,
                           "docker_pull",  # worker_name
                           f"Pulling image {full_image_name}...", # busy_message
                           provides_progress=False) # Docker pull progress is complex to parse reliably for a percentage

    @pyqtSlot(str)
    def docker_pull_finished(self, message): # Specific handler
        self.output_area.append(f"Step 1.2: Proceeding to run Docker container for macOS installation...")
        self.run_macos_vm()

    @pyqtSlot(str)
    def docker_pull_error(self, error_message): # Specific handler
        QMessageBox.critical(self, "Docker Pull Error", error_message)

    def run_macos_vm(self):
        selected_version_name = self.version_combo.currentText(); self.current_container_name = get_unique_container_name()
        try:
            command_list = build_docker_command(selected_version_name, self.current_container_name)
            run_worker = DockerRunWorker(command_list)
            self._start_worker(run_worker,
                               self.docker_run_finished,
                               self.docker_run_error,
                               "docker_run",
                               f"Starting container {self.current_container_name}...",
                               provides_progress=False) # Docker run output is also streamed, not easily percentage
        except ValueError as e: self.handle_error(f"Failed to build command: {str(e)}")
        except Exception as e: self.handle_error(f"An unexpected error: {str(e)}")

    @pyqtSlot(str)
    def update_output(self, text): self.output_area.append(text.strip()); QApplication.processEvents()

    @pyqtSlot(str)
    def docker_run_finished(self, message): # Specific handler
        QMessageBox.information(self, "VM Setup Complete", f"{message}\nYou can now proceed to extract images.")

    @pyqtSlot(str)
    def docker_run_error(self, error_message): # Specific handler
        if "exited" in error_message.lower() and self.current_container_name:
            QMessageBox.warning(self, "VM Setup Ended", f"{error_message}\nAssuming macOS setup was attempted...")
        else:
            QMessageBox.critical(self, "VM Setup Error", error_message)

    def stop_current_docker_operation(self):
        pull_worker = getattr(self, "docker_pull_instance", None); run_worker = getattr(self, "docker_run_instance", None)
        if pull_worker: self.output_area.append("\n--- Docker pull cannot be directly stopped by this button. Close app to abort. ---")
        elif run_worker: self.output_area.append("\n--- Attempting to stop macOS VM creation (docker run) ---"); run_worker.stop()
        else: self.output_area.append("\n--- No stoppable Docker operation active. ---")

    def extract_vm_images(self):
        if not self.current_container_name: QMessageBox.warning(self, "Warning", "No active container."); return
        save_dir = QFileDialog.getExistingDirectory(self, "Select Directory to Save VM Images");
        if not save_dir: return
        self.output_area.append(f"\n--- Starting Image Extraction from {self.current_container_name} to {save_dir} ---"); self.extract_images_button.setEnabled(False); self.write_to_usb_button.setEnabled(False)
        self.extracted_main_image_path = os.path.join(save_dir, "mac_hdd_ng.img"); self.extracted_opencore_image_path = os.path.join(save_dir, "OpenCore.qcow2"); self.extraction_status = {"main": False, "opencore": False}
        cp_main_cmd = build_docker_cp_command(self.current_container_name, CONTAINER_MACOS_IMG_PATH, self.extracted_main_image_path); main_worker = DockerCommandWorker(cp_main_cmd, f"Main macOS image copied to {self.extracted_main_image_path}")
        if not self._start_worker(main_worker, lambda msg: self.docker_utility_finished(msg, "main_img_extract"), lambda err: self.docker_utility_error(err, "main_img_extract_error"), "cp_main_worker"): self.extract_images_button.setEnabled(True); return
        self.output_area.append(f"Extraction for main image started. OpenCore extraction will follow.")

    def _start_opencore_extraction(self):
        if not self.current_container_name or not self.extracted_opencore_image_path: return
        cp_oc_cmd = build_docker_cp_command(self.current_container_name, CONTAINER_OPENCORE_QCOW2_PATH, self.extracted_opencore_image_path); oc_worker = DockerCommandWorker(cp_oc_cmd, f"OpenCore image copied to {self.extracted_opencore_image_path}")
        self._start_worker(oc_worker, lambda msg: self.docker_utility_finished(msg, "oc_img_extract"), lambda err: self.docker_utility_error(err, "oc_img_extract_error"), "cp_oc_worker")

    def stop_persistent_container(self):
        if not self.current_container_name: QMessageBox.warning(self, "Warning", "No container name."); return
        cmd = build_docker_stop_command(self.current_container_name); worker = DockerCommandWorker(cmd, f"Container {self.current_container_name} stopped.")
        if self._start_worker(worker, lambda msg: self.docker_utility_finished(msg, "stop_container"), lambda err: self.docker_utility_error(err, "stop_container_error"), "stop_worker"): self.stop_container_button.setEnabled(False)

    def remove_persistent_container(self):
        if not self.current_container_name: QMessageBox.warning(self, "Warning", "No container name."); return
        reply = QMessageBox.question(self, 'Confirm Remove', f"Remove container '{self.current_container_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        cmd = build_docker_rm_command(self.current_container_name); worker = DockerCommandWorker(cmd, f"Container {self.current_container_name} removed.")
        if self._start_worker(worker, lambda msg: self.docker_utility_finished(msg, "rm_container"), lambda err: self.docker_utility_error(err, "rm_container_error"), "rm_worker"): self.remove_container_button.setEnabled(False)

    def docker_utility_finished(self, message, task_id): # Specific handler
        QMessageBox.information(self, f"Task Complete", message) # Show specific popup
        # Core logic based on task_id
        if task_id == "main_img_extract":
            self.extraction_status["main"] = True
            # _handle_worker_finished (generic) has already reset active_worker_thread.
            self._start_opencore_extraction() # Start the next part of the sequence
            return # Return here as active_worker_thread will be managed by _start_opencore_extraction
        elif task_id == "oc_img_extract":
            self.extraction_status["opencore"] = True

        elif task_id == "rm_container": # Specific logic for after rm
             self.current_container_name = None

        # For other utility tasks (like stop_container), or after oc_img_extract,
        # or after rm_container specific logic, the generic handler _handle_worker_finished
        # (which called this) will then call _set_ui_busy(False) -> update_button_states_after_operation.
        # So, no explicit call to self.update_button_states_after_operation() is needed here
        # unless a state relevant to it changed *within this specific handler*.
        # In case of rm_container, current_container_name changes, so a UI update is good.
        if task_id == "rm_container" or (task_id == "oc_img_extract" and self.extraction_status.get("main")):
            self.update_button_states_after_operation()


    def docker_utility_error(self, error_message, task_id): # Specific handler
        QMessageBox.critical(self, f"Task Error: {task_id}", error_message)
        # UI state reset by generic _handle_worker_error -> _set_ui_busy(False) -> update_button_states_after_operation
        # Task-specific error UI updates if needed can be added here, but usually generic reset is enough.

    def handle_error(self, message): # General error handler for non-worker related setup issues
        self.output_area.append(f"ERROR: {message}"); QMessageBox.critical(self, "Error", message)
        self.run_vm_button.setEnabled(True); self.version_combo.setEnabled(True); self.stop_vm_button.setEnabled(False); self.extract_images_button.setEnabled(False); self.write_to_usb_button.setEnabled(False)
        self.active_worker_thread = None;
        for worker_name_suffix in ["pull", "run", "cp_main_worker", "cp_oc_worker", "stop_worker", "rm_worker", "usb_write_worker"]: self._clear_worker_instance(worker_name_suffix)

    def check_admin_privileges(self) -> bool:
        try:
            if platform.system() == "Windows": return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else: return os.geteuid() == 0
        except Exception as e: self.output_area.append(f"Could not check admin privileges: {e}"); return False

    def refresh_usb_drives(self): # Modified for Windows WMI
        self.usb_drive_combo.clear()
        self._current_usb_selection_text = self.usb_drive_combo.currentText() # Store to reselect if possible
        self.output_area.append("\nScanning for disk devices...")

        current_os = platform.system()
        self.windows_usb_guidance_label.setVisible(current_os == "Windows")
        self.windows_usb_input_label.setVisible(False) # Hide manual input by default
        self.windows_disk_id_input.setVisible(False) # Hide manual input by default
        self.usb_drive_combo.setVisible(True) # Always visible, populated differently

        if current_os == "Windows":
            self.usb_drive_label.setText("Available USB Disks (Windows - WMI):")
            self.refresh_usb_button.setText("Refresh USB List")
            powershell_command = "Get-WmiObject Win32_DiskDrive | Where-Object {$_.InterfaceType -eq 'USB'} | Select-Object DeviceID, Index, Model, @{Name='SizeGB';Expression={[math]::Round($_.Size / 1GB, 2)}} | ConvertTo-Json"
            try:
                process = subprocess.run(["powershell", "-Command", powershell_command], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                disks_data = json.loads(process.stdout)
                if not isinstance(disks_data, list): disks_data = [disks_data] # Ensure it's a list

                if disks_data:
                    for disk in disks_data:
                        if disk.get('DeviceID') is None or disk.get('Index') is None: continue
                        disk_text = f"Disk {disk['Index']}: {disk.get('Model','N/A')} ({disk.get('SizeGB','N/A')} GB) - {disk['DeviceID']}"
                        self.usb_drive_combo.addItem(disk_text, userData=str(disk['Index']))
                    self.output_area.append(f"Found {len(disks_data)} USB disk(s) via WMI. Select from dropdown.")
                    if self._current_usb_selection_text:
                        for i in range(self.usb_drive_combo.count()):
                            if self.usb_drive_combo.itemText(i) == self._current_usb_selection_text: self.usb_drive_combo.setCurrentIndex(i); break
                else:
                    self.output_area.append("No USB disks found via WMI/PowerShell. Manual input field shown as fallback.")
                    self.windows_usb_input_label.setVisible(True); self.windows_disk_id_input.setVisible(True) # Show manual input as fallback
            except Exception as e:
                self.output_area.append(f"Error querying WMI for USB disks: {e}. Manual input field shown.")
                self.windows_usb_input_label.setVisible(True); self.windows_disk_id_input.setVisible(True)
        else: # Linux / macOS
            self.usb_drive_label.setText("Available USB Drives (for Linux/macOS):")
            self.refresh_usb_button.setText("Refresh List")
            try:
                partitions = psutil.disk_partitions(all=False); potential_usbs = []
                for p in partitions:
                    is_removable = 'removable' in p.opts; is_likely_usb = False
                    if current_os == "Darwin" and p.device.startswith("/dev/disk") and 'external' in p.opts.lower() and 'physical' in p.opts.lower(): is_likely_usb = True
                    elif current_os == "Linux" and ((p.mountpoint and ("/media/" in p.mountpoint or "/run/media/" in p.mountpoint)) or (p.device.startswith("/dev/sd") and not p.device.endswith("da"))): is_likely_usb = True
                    if is_removable or is_likely_usb:
                        try: usage = psutil.disk_usage(p.mountpoint); size_gb = usage.total / (1024**3)
                        except Exception: continue
                        if size_gb < 0.1 : continue
                        drive_text = f"{p.device} @ {p.mountpoint} ({p.fstype}, {size_gb:.2f} GB)"
                        potential_usbs.append((drive_text, p.device))
                if potential_usbs:
                    idx_to_select = -1
                    for i, (text, device_path) in enumerate(potential_usbs): self.usb_drive_combo.addItem(text, userData=device_path);
                    if text == self._current_usb_selection_text: idx_to_select = i
                    if idx_to_select != -1: self.usb_drive_combo.setCurrentIndex(idx_to_select)
                    self.output_area.append(f"Found {len(potential_usbs)} potential USB drive(s). Please verify carefully.")
                else: self.output_area.append("No suitable USB drives found for Linux/macOS.")
            except ImportError: self.output_area.append("psutil library not found.")
            except Exception as e: self.output_area.append(f"Error scanning for USB drives: {e}")

        self.update_write_to_usb_button_state()

    def handle_write_to_usb(self): # Modified for Windows WMI
        if not self.check_admin_privileges():
            QMessageBox.warning(self, "Privileges Required", "This operation requires Administrator/root privileges."); return

        current_os = platform.system(); usb_writer_module = None; target_device_id_for_worker = None
        enhance_plist_enabled = self.enhance_plist_checkbox.isChecked() # Get state
        target_macos_ver = self.version_combo.currentText() # Get macOS version

        if current_os == "Windows":
            target_device_id_for_worker = self.usb_drive_combo.currentData() # Disk Index from WMI
            if not target_device_id_for_worker:
                if self.windows_disk_id_input.isVisible():
                    target_device_id_for_worker = self.windows_disk_id_input.text().strip()
                    if not target_device_id_for_worker: QMessageBox.warning(self, "Input Required", "Please select a USB disk or enter its Disk Number."); return
                    if not target_device_id_for_worker.isdigit(): QMessageBox.warning(self, "Input Invalid", "Windows Disk Number must be a digit."); return
                else:
                     QMessageBox.warning(self, "USB Error", "No USB disk selected for Windows."); return
            usb_writer_module = USBWriterWindows
        else: # Linux/macOS
            target_device_id_for_worker = self.usb_drive_combo.currentData()
            if current_os == "Linux": usb_writer_module = USBWriterLinux
            elif current_os == "Darwin": usb_writer_module = USBWriterMacOS

        if not usb_writer_module: QMessageBox.warning(self, "Unsupported Platform", f"USB writing not supported/enabled for {current_os}."); return
        if not (self.extracted_main_image_path and self.extracted_opencore_image_path and self.extraction_status["main"] and self.extraction_status["opencore"]):
            QMessageBox.warning(self, "Missing Images", "Ensure both images are extracted."); return
        if not target_device_id_for_worker: QMessageBox.warning(self, "No USB Selected/Identified", f"Please select/identify target USB for {current_os}."); return

        confirm_msg = (f"WARNING: ALL DATA ON TARGET '{target_device_id_for_worker}' WILL BE ERASED PERMANENTLY.\n"
                       f"Enhance config.plist: {'Yes' if enhance_plist_enabled else 'No'}.\nProceed?")
        reply = QMessageBox.warning(self, "Confirm Write Operation", confirm_msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Cancel: self.output_area.append("\nUSB write cancelled."); return

        self.output_area.append(f"\n--- Starting USB Write for {target_device_id_for_worker} on {current_os} ---")
        if enhance_plist_enabled: self.output_area.append("Attempting config.plist enhancement...")

        usb_worker = USBWriterWorker(
            target_device_id_for_worker,
            self.extracted_opencore_image_path,
            self.extracted_main_image_path,
            enhance_plist_enabled,
            target_macos_ver
        )
        self._start_worker(usb_worker,
                           self.usb_write_finished,
                           self.usb_write_error,
                           "usb_write_worker",
                           f"Writing to USB {target_device_id_for_worker}...")

    @pyqtSlot(str)
    def usb_write_finished(self, message): # Specific handler
        QMessageBox.information(self, "USB Write Complete", message)
        # UI state reset by generic _handle_worker_finished -> _set_ui_busy(False)

    @pyqtSlot(str)
    def usb_write_error(self, error_message): # Specific handler
        QMessageBox.critical(self, "USB Write Error", error_message)
        # UI state reset by generic _handle_worker_error -> _set_ui_busy(False)

    def update_write_to_usb_button_state(self):
        images_ready = self.extraction_status.get("main", False) and self.extraction_status.get("opencore", False); usb_identified = False; current_os = platform.system(); writer_module = None
        if current_os == "Linux": writer_module = USBWriterLinux; usb_identified = bool(self.usb_drive_combo.currentData())
        elif current_os == "Darwin": writer_module = USBWriterMacOS; usb_identified = bool(self.usb_drive_combo.currentData())
        elif current_os == "Windows":
            writer_module = USBWriterWindows
            usb_identified = bool(self.usb_drive_combo.currentData()) or bool(self.windows_disk_id_input.text().strip().isdigit() and self.windows_disk_id_input.isVisible())

        self.write_to_usb_button.setEnabled(images_ready and usb_identified and writer_module is not None)
        tooltip = ""
        if writer_module is None: tooltip = f"USB Writing not supported on {current_os} or module missing."
        elif not images_ready: tooltip = "Extract VM images first."
        elif not usb_identified: tooltip = "Select a USB disk from dropdown (or enter Disk Number if dropdown empty on Windows)."
        else: tooltip = ""
        self.write_to_usb_button.setToolTip(tooltip)

    def closeEvent(self, event):
        self._current_usb_selection_text = self.usb_drive_combo.currentText()
        if self.active_worker_thread and self.active_worker_thread.isRunning():
            reply = QMessageBox.question(self, 'Confirm Exit', "An operation is running. Exit anyway?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                worker_instance_attr_name = self.active_worker_thread.objectName().replace("_thread", "_instance")
                worker_to_stop = getattr(self, worker_instance_attr_name, None)
                if worker_to_stop and hasattr(worker_to_stop, 'stop'): worker_to_stop.stop()
                else: self.active_worker_thread.quit()
                self.active_worker_thread.wait(1000); event.accept()
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
