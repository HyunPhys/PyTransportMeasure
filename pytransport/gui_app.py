"""PySide6 desktop application for PyTransportMeasure."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from .gui_services import (
    DRAIN_IV_FORM_FIELDS,
    GuiFakeSettings,
    available_gui_methods,
    default_recipe_text,
    drain_iv_form_from_text,
    drain_iv_text_from_form,
    format_gui_plan,
    list_gui_runs,
    load_gui_saved_run,
    load_recipe_text,
    primary_plot_path,
    primary_report_path,
    run_gui_dry_run,
    save_recipe_text,
    validate_recipe_text,
)


try:
    from PySide6.QtCore import QThread, Signal, Qt
    from PySide6.QtGui import QAction, QDesktopServices
    from PySide6.QtSvgWidgets import QSvgWidget
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QScrollArea,
        QSpinBox,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised manually.
    class _MissingSignal:
        def connect(self, *_args, **_kwargs):
            return None

        def emit(self, *_args, **_kwargs):
            return None

    class _MissingQt:
        AlignRight = 0
        AlignVCenter = 0

    QThread = object  # type: ignore[misc,assignment]
    Signal = lambda *_args, **_kwargs: _MissingSignal()  # type: ignore[assignment]
    Qt = _MissingQt()  # type: ignore[assignment]
    QAction = QDesktopServices = None  # type: ignore[assignment]
    QApplication = QComboBox = QFileDialog = QFormLayout = QGridLayout = QGroupBox = QHBoxLayout = QLabel = QLineEdit = QMessageBox = QPushButton = QPlainTextEdit = QScrollArea = QSpinBox = QTabWidget = QTableWidget = QTableWidgetItem = QVBoxLayout = QWidget = None  # type: ignore[assignment]
    QMainWindow = object  # type: ignore[assignment]
    QSvgWidget = None  # type: ignore[assignment]


DEFAULT_RECIPES = {
    "drain_iv": "configs/recipes/drain_iv_1k_resistor.yaml",
    "single_gate_sweep": "configs/recipes/single_gate_dry_run.yaml",
    "ac_lockin_sweep": "configs/recipes/ac_lockin_dry_run.yaml",
    "pulse_measurement": "configs/recipes/pulse_dry_run.yaml",
}


class DryRunWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, measurement_type: str, recipe_path: Path, fake: GuiFakeSettings):
        super().__init__()
        self.measurement_type = measurement_type
        self.recipe_path = recipe_path
        self.fake = fake

    def run(self) -> None:
        try:
            self.finished_ok.emit(run_gui_dry_run(self.measurement_type, self.recipe_path, fake=self.fake))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PyTransportMeasure")
        self.resize(1180, 760)
        self.worker: DryRunWorker | None = None
        self.last_result: Any | None = None

        self.method_combo = QComboBox()
        for key, label in available_gui_methods().items():
            self.method_combo.addItem(label, key)
        self.method_combo.currentIndexChanged.connect(self.apply_default_recipe)

        self.recipe_edit = QLineEdit()
        self.recipe_edit.setMinimumWidth(360)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_recipe)

        self.preview_spin = QSpinBox()
        self.preview_spin.setRange(0, 50)
        self.preview_spin.setValue(5)

        self.fake_resistance = QLineEdit("1000000")
        self.fake_noise = QLineEdit("0")
        self.fake_channel_resistance = QLineEdit("1000000")
        self.fake_gate_leak = QLineEdit("1000000000")
        self.fake_gate_modulation = QLineEdit("0")
        self.fake_lockin_r = QLineEdit("0.000001")
        self.fake_lockin_phase = QLineEdit("0")
        self.fake_lockin_noise = QLineEdit("0")

        self.plan_button = QPushButton("Plan")
        self.plan_button.clicked.connect(self.show_plan)
        self.run_button = QPushButton("Dry Run")
        self.run_button.clicked.connect(self.start_dry_run)
        self.load_editor_button = QPushButton("Load Editor")
        self.load_editor_button.clicked.connect(self.load_recipe_into_editor)
        self.validate_editor_button = QPushButton("Validate YAML")
        self.validate_editor_button.clicked.connect(self.validate_editor)
        self.save_editor_button = QPushButton("Save Recipe")
        self.save_editor_button.clicked.connect(self.save_editor_as)
        self.load_form_button = QPushButton("Load Form from YAML")
        self.load_form_button.clicked.connect(self.load_form_from_editor)
        self.apply_form_button = QPushButton("Apply Form to YAML")
        self.apply_form_button.clicked.connect(self.apply_form_to_editor)
        self.open_run_button = QPushButton("Run Folder")
        self.open_run_button.clicked.connect(self.open_run_folder)
        self.open_plot_button = QPushButton("Plot")
        self.open_plot_button.clicked.connect(self.open_plot)
        self.open_report_button = QPushButton("Report")
        self.open_report_button.clicked.connect(self.open_report)
        self.refresh_runs_button = QPushButton("Refresh Runs")
        self.refresh_runs_button.clicked.connect(self.refresh_indexed_runs)
        self.load_run_button = QPushButton("Load Selected")
        self.load_run_button.clicked.connect(self.load_selected_run)
        self.open_run_button.setEnabled(False)
        self.open_plot_button.setEnabled(False)
        self.open_report_button.setEnabled(False)
        self.load_run_button.setEnabled(False)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.plan_text = QPlainTextEdit()
        self.plan_text.setReadOnly(True)
        self.editor_text = QPlainTextEdit()
        self.form_fields: dict[str, Any] = {}
        self.form_status = QLabel("Drain I-V form builder")
        self.validation_text = QPlainTextEdit()
        self.validation_text.setReadOnly(True)
        self.summary_text = QPlainTextEdit()
        self.summary_text.setReadOnly(True)
        self.metadata_text = QPlainTextEdit()
        self.metadata_text.setReadOnly(True)
        self.report_text = QPlainTextEdit()
        self.report_text.setReadOnly(True)
        self.plot_widget = QSvgWidget()
        self.plot_widget.setMinimumSize(760, 480)
        self.plot_scroll = QScrollArea()
        self.plot_scroll.setWidgetResizable(True)
        self.plot_scroll.setWidget(self.plot_widget)
        self.plot_status = QLabel("No plot loaded")
        self.recent_table = QTableWidget(0, 6)
        self.recent_table.setHorizontalHeaderLabels(["Started", "Method", "Name", "Completed", "Points", "Run folder"])
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        self.recent_table.itemSelectionChanged.connect(self.update_selected_run_controls)

        tabs = QTabWidget()
        tabs.addTab(self.plan_text, "Plan")
        tabs.addTab(self.build_drain_iv_form(), "Drain I-V Form")
        tabs.addTab(self.editor_text, "Recipe YAML")
        tabs.addTab(self.validation_text, "Validation")
        tabs.addTab(self.summary_text, "Summary")
        tabs.addTab(self.build_plot_preview(), "Plot Preview")
        tabs.addTab(self.metadata_text, "Metadata")
        tabs.addTab(self.report_text, "Report")
        tabs.addTab(self.recent_table, "Runs")

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(self.build_controls())
        layout.addWidget(tabs, stretch=1)
        layout.addWidget(self.status_label)
        self.setCentralWidget(root)
        self.setStyleSheet(APP_STYLESHEET)
        self.build_menu()
        self.apply_default_recipe()

    def build_controls(self) -> QWidget:
        box = QGroupBox("Measurement")
        layout = QGridLayout(box)
        layout.addWidget(QLabel("Method"), 0, 0)
        layout.addWidget(self.method_combo, 0, 1)
        layout.addWidget(QLabel("Recipe"), 0, 2)
        recipe_row = QHBoxLayout()
        recipe_row.addWidget(self.recipe_edit, stretch=1)
        recipe_row.addWidget(self.browse_button)
        layout.addLayout(recipe_row, 0, 3, 1, 3)
        layout.addWidget(QLabel("Preview"), 0, 6)
        layout.addWidget(self.preview_spin, 0, 7)

        fake_box = QGroupBox("Dry-run Model")
        fake_layout = QFormLayout(fake_box)
        fake_layout.addRow("R source", self.fake_resistance)
        fake_layout.addRow("Noise A", self.fake_noise)
        fake_layout.addRow("R channel", self.fake_channel_resistance)
        fake_layout.addRow("R gate leak", self.fake_gate_leak)
        fake_layout.addRow("Gate mod", self.fake_gate_modulation)
        fake_layout.addRow("Lock-in R", self.fake_lockin_r)
        fake_layout.addRow("Lock-in phase", self.fake_lockin_phase)
        fake_layout.addRow("Lock-in noise", self.fake_lockin_noise)
        layout.addWidget(fake_box, 1, 0, 1, 8)

        button_row = QHBoxLayout()
        button_row.addWidget(self.plan_button)
        button_row.addWidget(self.run_button)
        button_row.addWidget(self.load_editor_button)
        button_row.addWidget(self.validate_editor_button)
        button_row.addWidget(self.save_editor_button)
        button_row.addWidget(self.load_form_button)
        button_row.addWidget(self.apply_form_button)
        button_row.addStretch(1)
        button_row.addWidget(self.refresh_runs_button)
        button_row.addWidget(self.load_run_button)
        button_row.addWidget(self.open_run_button)
        button_row.addWidget(self.open_plot_button)
        button_row.addWidget(self.open_report_button)
        layout.addLayout(button_row, 2, 0, 1, 8)
        return box

    def build_plot_preview(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.plot_status)
        layout.addWidget(self.plot_scroll, stretch=1)
        return container

    def build_drain_iv_form(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.form_status)

        measurement_box = QGroupBox("Measurement")
        measurement_layout = QFormLayout(measurement_box)
        self.add_form_line(measurement_layout, "measurement_name", "Name")
        self.add_form_line(measurement_layout, "sample_id", "Sample")
        self.add_form_line(measurement_layout, "device_id", "Device")
        self.add_form_line(measurement_layout, "operator", "Operator")
        self.add_form_line(measurement_layout, "notes", "Notes")
        self.add_form_line(measurement_layout, "tags", "Tags")
        layout.addWidget(measurement_box)

        instrument_box = QGroupBox("Instrument")
        instrument_layout = QFormLayout(instrument_box)
        self.add_form_line(instrument_layout, "instrument_id", "Instrument ID")
        self.add_form_line(instrument_layout, "address", "VISA address")
        self.add_form_line(instrument_layout, "timeout_ms", "Timeout ms")
        terminal = QComboBox()
        terminal.addItems(["", "FRONT", "REAR"])
        self.form_fields["terminal"] = terminal
        instrument_layout.addRow("Terminal", terminal)
        self.add_form_line(instrument_layout, "voltage_range_v", "Voltage range V")
        self.add_form_line(instrument_layout, "current_range_a", "Current range A")
        layout.addWidget(instrument_box)

        sweep_box = QGroupBox("Sweep")
        sweep_layout = QFormLayout(sweep_box)
        sweep_mode = QComboBox()
        sweep_mode.addItems(["linear_one_way", "forward_backward"])
        self.form_fields["sweep_mode"] = sweep_mode
        sweep_layout.addRow("Mode", sweep_mode)
        self.add_form_line(sweep_layout, "start_v", "Start V")
        self.add_form_line(sweep_layout, "stop_v", "Stop V")
        self.add_form_line(sweep_layout, "points", "Points")
        self.add_form_line(sweep_layout, "delay_s", "Delay s")
        self.add_form_line(sweep_layout, "current_compliance_a", "Compliance A")
        layout.addWidget(sweep_box)

        safety_box = QGroupBox("Safety and Output")
        safety_layout = QFormLayout(safety_box)
        self.add_form_line(safety_layout, "safety_preset", "Safety preset")
        self.add_form_line(safety_layout, "output_directory", "Output dir")
        require_completed = QComboBox()
        require_completed.addItems(["true", "false"])
        self.form_fields["require_completed"] = require_completed
        safety_layout.addRow("Require completed", require_completed)
        self.add_form_line(safety_layout, "min_points", "Min points")
        self.add_form_line(safety_layout, "resistance_min_ohm", "Min R ohm")
        self.add_form_line(safety_layout, "resistance_max_ohm", "Max R ohm")
        layout.addWidget(safety_box)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    def add_form_line(self, layout: Any, key: str, label: str) -> None:
        field = QLineEdit()
        self.form_fields[key] = field
        layout.addRow(label, field)

    def build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        open_recipe = QAction("Open Recipe", self)
        open_recipe.triggered.connect(self.browse_recipe)
        file_menu.addAction(open_recipe)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def current_method(self) -> str:
        return str(self.method_combo.currentData())

    def recipe_path(self) -> Path:
        return Path(self.recipe_edit.text()).expanduser()

    def fake_settings(self) -> GuiFakeSettings:
        return GuiFakeSettings(
            resistance_ohm=float(self.fake_resistance.text()),
            noise_std_a=float(self.fake_noise.text()),
            channel_resistance_ohm=float(self.fake_channel_resistance.text()),
            gate_leak_resistance_ohm=float(self.fake_gate_leak.text()),
            gate_modulation_per_v=float(self.fake_gate_modulation.text()),
            lockin_r_v=float(self.fake_lockin_r.text()),
            lockin_phase_deg=float(self.fake_lockin_phase.text()),
            lockin_noise_std_v=float(self.fake_lockin_noise.text()),
        )

    def apply_default_recipe(self) -> None:
        self.recipe_edit.setText(DEFAULT_RECIPES.get(self.current_method(), ""))
        if hasattr(self, "editor_text"):
            try:
                self.editor_text.setPlainText(default_recipe_text(self.current_method()))
                self.validation_text.clear()
                self.load_form_from_editor(silent=True)
            except Exception:
                pass
        if hasattr(self, "load_form_button"):
            is_drain_iv = self.current_method() == "drain_iv"
            self.load_form_button.setEnabled(is_drain_iv)
            self.apply_form_button.setEnabled(is_drain_iv)
            if not is_drain_iv and hasattr(self, "form_status"):
                self.form_status.setText("Structured form is available for Drain I-V recipes in this phase.")

    def browse_recipe(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "Open Recipe", str(Path("configs/recipes").resolve()), "YAML (*.yaml *.yml)")
        if selected:
            self.recipe_edit.setText(selected)

    def show_plan(self) -> None:
        try:
            plan = format_gui_plan(self.current_method(), self.recipe_path(), preview_points=self.preview_spin.value())
        except Exception as exc:
            self.show_error(exc)
            return
        self.plan_text.setPlainText(plan)
        self.status_label.setText("Plan ready")

    def load_recipe_into_editor(self) -> None:
        try:
            self.editor_text.setPlainText(load_recipe_text(self.recipe_path()))
        except Exception as exc:
            self.show_error(exc)
            return
        self.validation_text.clear()
        self.load_form_from_editor(silent=True)
        self.status_label.setText("Recipe loaded into editor")

    def load_form_from_editor(self, silent: bool = False) -> bool:
        if self.current_method() != "drain_iv":
            self.form_status.setText("Structured form is available for Drain I-V recipes in this phase.")
            return False
        try:
            values = drain_iv_form_from_text(self.editor_text.toPlainText())
            self.set_form_values(values)
        except Exception as exc:
            if not silent:
                self.show_error(exc)
            self.form_status.setText("Could not load Drain I-V form from YAML")
            return False
        self.form_status.setText("Drain I-V form loaded from YAML")
        if not silent:
            self.status_label.setText("Form loaded from YAML")
        return True

    def apply_form_to_editor(self) -> bool:
        if self.current_method() != "drain_iv":
            self.form_status.setText("Structured form is available for Drain I-V recipes in this phase.")
            return False
        try:
            text = drain_iv_text_from_form(self.form_values())
        except Exception as exc:
            self.show_error(exc)
            self.form_status.setText("Could not apply Drain I-V form")
            return False
        self.editor_text.setPlainText(text)
        self.validation_text.clear()
        self.form_status.setText("Drain I-V YAML updated from form")
        self.status_label.setText("YAML updated from form")
        return True

    def form_values(self) -> dict[str, str]:
        values = {}
        for key in DRAIN_IV_FORM_FIELDS:
            widget = self.form_fields.get(key)
            if widget is None:
                values[key] = ""
            elif isinstance(widget, QComboBox):
                values[key] = widget.currentText()
            else:
                values[key] = widget.text()
        return values

    def set_form_values(self, values: dict[str, str]) -> None:
        for key, value in values.items():
            widget = self.form_fields.get(key)
            if widget is None:
                continue
            if isinstance(widget, QComboBox):
                index = widget.findText(value)
                widget.setCurrentIndex(index if index >= 0 else 0)
            else:
                widget.setText(value)

    def validate_editor(self) -> bool:
        ok, message = validate_recipe_text(
            self.current_method(),
            self.editor_text.toPlainText(),
            preview_points=self.preview_spin.value(),
        )
        self.validation_text.setPlainText(message)
        self.status_label.setText("Recipe validation passed" if ok else "Recipe validation failed")
        return ok

    def save_editor_as(self) -> None:
        if not self.validate_editor():
            return
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save Recipe",
            str(Path("configs/recipes").resolve() / "edited_recipe.yaml"),
            "YAML (*.yaml *.yml)",
        )
        if not selected:
            return
        try:
            path = save_recipe_text(self.current_method(), self.editor_text.toPlainText(), selected)
        except Exception as exc:
            self.show_error(exc)
            return
        self.recipe_edit.setText(str(path))
        self.status_label.setText(f"Recipe saved: {path}")

    def start_dry_run(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        try:
            fake = self.fake_settings()
        except Exception as exc:
            self.show_error(exc)
            return
        self.set_running(True)
        self.summary_text.clear()
        self.metadata_text.clear()
        self.report_text.clear()
        self.worker = DryRunWorker(self.current_method(), self.recipe_path(), fake)
        self.worker.finished_ok.connect(self.handle_result)
        self.worker.failed.connect(self.handle_failure)
        self.worker.finished.connect(lambda: self.set_running(False))
        self.worker.start()

    def handle_result(self, result) -> None:
        self.display_result(result, add_to_table=True)

    def display_result(self, result, add_to_table: bool) -> None:
        self.last_result = result
        self.summary_text.setPlainText("\n".join(part for part in [result.summary_text, result.quality_text] if part))
        self.metadata_text.setPlainText(read_text(Path(result.metadata["metadata_path"])))
        report_path = self.report_path()
        if report_path and report_path.exists():
            self.report_text.setPlainText(read_text(report_path))
        self.update_plot_preview()
        if add_to_table:
            self.add_recent_run(result)
        self.open_run_button.setEnabled(True)
        self.open_plot_button.setEnabled(self.plot_path() is not None)
        self.open_report_button.setEnabled(self.report_path() is not None)
        self.status_label.setText(f"Completed: {result.metadata.get('completed')} | {result.run_dir}")

    def handle_failure(self, message: str) -> None:
        self.status_label.setText("Failed")
        QMessageBox.critical(self, "PyTransportMeasure", message)

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.plan_button.setEnabled(not running)
        self.status_label.setText("Running dry-run..." if running else "Ready")

    def add_recent_run(self, result) -> None:
        row = self.recent_table.rowCount()
        self.recent_table.insertRow(row)
        values = [
            result.metadata.get("started_at"),
            result.metadata.get("measurement_type"),
            result.metadata.get("measurement_name"),
            result.metadata.get("completed"),
            result.metadata.get("points_written"),
            result.metadata.get("run_dir"),
        ]
        for column, value in enumerate(values):
            self.recent_table.setItem(row, column, QTableWidgetItem(str(value)))

    def refresh_indexed_runs(self) -> None:
        try:
            records = list_gui_runs()
        except Exception as exc:
            self.show_error(exc)
            return
        self.recent_table.setRowCount(0)
        for record in records:
            row = self.recent_table.rowCount()
            self.recent_table.insertRow(row)
            values = [
                record.get("started_at"),
                record.get("measurement_type"),
                record.get("measurement_name"),
                record.get("completed"),
                record.get("points_written"),
                record.get("run_dir"),
            ]
            for column, value in enumerate(values):
                self.recent_table.setItem(row, column, QTableWidgetItem(str(value)))
        self.status_label.setText(f"Loaded {len(records)} indexed runs")

    def selected_run_dir(self) -> Path | None:
        selected = self.recent_table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.recent_table.item(row, 5)
        if item is None or not item.text():
            return None
        return Path(item.text())

    def update_selected_run_controls(self) -> None:
        self.load_run_button.setEnabled(self.selected_run_dir() is not None)

    def load_selected_run(self) -> None:
        run_dir = self.selected_run_dir()
        if run_dir is None:
            return
        try:
            result = load_gui_saved_run(run_dir)
        except Exception as exc:
            self.show_error(exc)
            return
        self.display_result(result, add_to_table=False)

    def plot_path(self) -> Path | None:
        if self.last_result is None:
            return None
        return primary_plot_path(self.last_result.metadata)

    def report_path(self) -> Path | None:
        if self.last_result is None:
            return None
        return primary_report_path(self.last_result.metadata)

    def update_plot_preview(self) -> None:
        path = self.plot_path()
        if path is None:
            self.plot_status.setText("No plot artifact found")
            self.plot_widget.load(b"")
            return
        self.plot_widget.load(str(path.resolve()))
        self.plot_status.setText(f"Plot preview: {path}")

    def open_run_folder(self) -> None:
        if self.last_result is not None:
            open_path(self.last_result.run_dir)

    def open_plot(self) -> None:
        path = self.plot_path()
        if path is not None:
            open_path(path)

    def open_report(self) -> None:
        path = self.report_path()
        if path is not None:
            open_path(path)

    def show_error(self, exc: Exception) -> None:
        QMessageBox.critical(self, "PyTransportMeasure", f"{type(exc).__name__}: {exc}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def open_path(path: Path) -> None:
    QDesktopServices.openUrl(path.resolve().as_uri())


APP_STYLESHEET = """
* {
  color: #111827;
  selection-background-color: #2563eb;
  selection-color: #ffffff;
}
QMainWindow {
  background: #f5f7fb;
}
QWidget {
  background: #f5f7fb;
}
QMenuBar, QMenu {
  background: #ffffff;
  color: #111827;
}
QMenuBar::item:selected, QMenu::item:selected {
  background: #e5e7eb;
}
QLabel {
  color: #111827;
  background: transparent;
}
QGroupBox {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  margin-top: 10px;
  padding: 10px;
  background: #ffffff;
  color: #111827;
}
QGroupBox::title {
  subcontrol-origin: margin;
  left: 10px;
  padding: 0 4px;
  color: #374151;
  background: #ffffff;
}
QPushButton {
  min-height: 28px;
  padding: 4px 12px;
  border: 1px solid #9ca3af;
  border-radius: 5px;
  background: #f3f4f6;
  color: #111827;
}
QPushButton:hover {
  background: #e5e7eb;
}
QPushButton:pressed {
  background: #d1d5db;
}
QPushButton:disabled {
  color: #9ca3af;
  background: #f9fafb;
  border-color: #d1d5db;
}
QPlainTextEdit, QTableWidget {
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #111827;
  font-family: Consolas, monospace;
  font-size: 10pt;
}
QLineEdit, QComboBox, QSpinBox {
  min-height: 26px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  background: #ffffff;
  color: #111827;
  padding: 2px 6px;
}
QTabWidget::pane {
  border: 1px solid #cbd5e1;
  background: #ffffff;
}
QTabBar::tab {
  background: #e5e7eb;
  color: #111827;
  padding: 7px 12px;
  border: 1px solid #cbd5e1;
  border-bottom: none;
}
QTabBar::tab:selected {
  background: #ffffff;
  color: #111827;
}
QHeaderView::section {
  background: #f3f4f6;
  color: #111827;
  border: 1px solid #d1d5db;
  padding: 4px;
}
"""


def main(argv: list[str] | None = None) -> int:
    if QApplication is None:
        print('PySide6 is not installed. Install it with: pip install -e ".[gui]"', file=sys.stderr)
        return 2
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(argv or sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
