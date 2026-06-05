"""PySide6 desktop application for PyTransportMeasure."""

from __future__ import annotations

import os
import sys
import csv
from pathlib import Path
from typing import Any

from .gui_session import GuiSessionLogger
from .gui_services import (
    GuiFakeSettings,
    GuiSchemaField,
    GuiSchemeStepDraft,
    available_gui_methods,
    create_gui_feedback_bundle,
    default_recipe_text,
    default_scheme_text,
    format_hardware_confirmation_text,
    format_gui_plan_text,
    format_gui_progress,
    format_scheme_plan_text,
    format_recipe_overview_text,
    list_gui_runs,
    load_gui_saved_run,
    load_recipe_from_text,
    load_recipe_text,
    primary_plot_path,
    primary_report_path,
    refresh_gui_instruments,
    run_gui_communication_test,
    run_gui_doctor_text,
    run_gui_preflight_text,
    run_gui_hardware_text,
    run_gui_dry_run_text,
    save_recipe_text,
    schema_form_from_text,
    schema_form_text_from_values,
    scheme_builder_from_text,
    scheme_text_from_builder,
    validate_scheme_text,
    validate_recipe_text,
)


try:
    from PySide6.QtCore import QThread, Signal, Qt
    from PySide6.QtGui import QAction, QColor, QDesktopServices, QPainter, QPen
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
    QColor = QPainter = QPen = None  # type: ignore[assignment]
    QApplication = QComboBox = QFileDialog = QFormLayout = QGridLayout = QGroupBox = QHBoxLayout = QLabel = QLineEdit = QMessageBox = QPushButton = QPlainTextEdit = QScrollArea = QSpinBox = QTabWidget = QTableWidget = QTableWidgetItem = QVBoxLayout = QWidget = None  # type: ignore[assignment]
    QMainWindow = object  # type: ignore[assignment]


DEFAULT_RECIPES = {
    "drain_iv": "configs/recipes/drain_iv_1k_resistor.yaml",
    "single_gate_sweep": "configs/recipes/single_gate_dry_run.yaml",
    "ac_lockin_sweep": "configs/recipes/ac_lockin_dry_run.yaml",
    "pulse_measurement": "configs/recipes/pulse_dry_run.yaml",
}


if QTableWidgetItem is not None:
    class SortableTableWidgetItem(QTableWidgetItem):
        def __init__(self, text: str, sort_key: Any | None = None):
            super().__init__(text)
            self.sort_key = text.lower() if sort_key is None else sort_key

        def __lt__(self, other: Any) -> bool:
            other_key = getattr(other, "sort_key", other.text().lower() if hasattr(other, "text") else other)
            return self.sort_key < other_key
else:  # pragma: no cover - PySide6 missing fallback.
    SortableTableWidgetItem = object  # type: ignore[assignment]


class DryRunWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    point_progress = Signal(object, int)

    def __init__(self, measurement_type: str, recipe_text: str, fake: GuiFakeSettings):
        super().__init__()
        self.measurement_type = measurement_type
        self.recipe_text = recipe_text
        self.fake = fake
        self._stop_requested = False

    def run(self) -> None:
        try:
            self.finished_ok.emit(
                run_gui_dry_run_text(
                    self.measurement_type,
                    self.recipe_text,
                    fake=self.fake,
                    progress_callback=self.emit_progress,
                    stop_requested=self.is_stop_requested,
                )
            )
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def emit_progress(self, point: Any, total: int) -> None:
        self.progress.emit(format_gui_progress(point, total))
        self.point_progress.emit(point, total)

    def request_stop(self) -> None:
        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        return self._stop_requested


class PreflightWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, measurement_type: str, recipe_text: str):
        super().__init__()
        self.measurement_type = measurement_type
        self.recipe_text = recipe_text

    def run(self) -> None:
        try:
            self.finished_ok.emit(run_gui_preflight_text(self.measurement_type, self.recipe_text))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class DoctorWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, measurement_type: str, recipe_text: str):
        super().__init__()
        self.measurement_type = measurement_type
        self.recipe_text = recipe_text

    def run(self) -> None:
        try:
            self.finished_ok.emit(run_gui_doctor_text(self.measurement_type, self.recipe_text))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class InstrumentRefreshWorker(QThread):
    finished_ok = Signal(object, str)
    failed = Signal(str)

    def run(self) -> None:
        try:
            resources, text = refresh_gui_instruments()
            self.finished_ok.emit(resources, text)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class CommunicationTestWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, address: str, timeout_ms: int):
        super().__init__()
        self.address = address
        self.timeout_ms = timeout_ms

    def run(self) -> None:
        try:
            self.finished_ok.emit(run_gui_communication_test(self.address, timeout_ms=self.timeout_ms))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class HardwareRunWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    point_progress = Signal(object, int)

    def __init__(self, measurement_type: str, recipe_text: str):
        super().__init__()
        self.measurement_type = measurement_type
        self.recipe_text = recipe_text
        self._stop_requested = False

    def run(self) -> None:
        try:
            self.finished_ok.emit(
                run_gui_hardware_text(
                    self.measurement_type,
                    self.recipe_text,
                    progress_callback=self.emit_progress,
                    stop_requested=self.is_stop_requested,
                )
            )
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def emit_progress(self, point: Any, total: int) -> None:
        self.progress.emit(format_gui_progress(point, total))
        self.point_progress.emit(point, total)

    def request_stop(self) -> None:
        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        return self._stop_requested


class IvPlotCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(320, 240)
        self.live_voltage: list[float] = []
        self.live_current: list[float] = []
        self.points: list[tuple[float, float]] = []
        self.title = "No data"

    def clear(self, title: str = "No data") -> None:
        self.title = title
        self.points = []
        self.update()

    def plot_points(self, points: list[tuple[float, float]], title: str) -> None:
        if not points:
            self.clear("No point data")
            return
        self.points = list(points)
        self.title = title
        self.update()

    def reset_live(self, title: str) -> None:
        self.live_voltage = []
        self.live_current = []
        self.clear(title)

    def append_live_point(self, point: Any, title: str) -> None:
        if not hasattr(point, "voltage_v") or not hasattr(point, "current_a"):
            return
        self.live_voltage.append(float(point.voltage_v))
        self.live_current.append(float(point.current_a))
        self.points = list(zip(self.live_voltage, self.live_current))
        self.title = title
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        margin_left = 64
        margin_right = 18
        margin_top = 38
        margin_bottom = 46
        plot_left = margin_left
        plot_top = margin_top
        plot_right = max(plot_left + 20, self.width() - margin_right)
        plot_bottom = max(plot_top + 20, self.height() - margin_bottom)
        plot_width = plot_right - plot_left
        plot_height = plot_bottom - plot_top

        painter.setPen(QPen(QColor("#111827"), 1))
        painter.drawText(12, 22, self.title)
        painter.setPen(QPen(QColor("#cbd5e1"), 1))
        painter.drawRect(plot_left, plot_top, plot_width, plot_height)
        painter.drawText(plot_left + max(0, plot_width // 2 - 38), self.height() - 12, "Voltage (V)")
        painter.save()
        painter.translate(16, plot_top + max(0, plot_height // 2 + 34))
        painter.rotate(-90)
        painter.drawText(0, 0, "Current (A)")
        painter.restore()

        if not self.points:
            painter.setPen(QPen(QColor("#6b7280"), 1))
            painter.drawText(plot_left + 12, plot_top + 24, "No point data")
            return

        voltages = [point[0] for point in self.points]
        currents = [point[1] for point in self.points]
        min_v, max_v = padded_range(min(voltages), max(voltages))
        min_i, max_i = padded_range(min(currents), max(currents))

        painter.setPen(QPen(QColor("#e5e7eb"), 1))
        for step in range(1, 4):
            x = plot_left + int(plot_width * step / 4)
            y = plot_top + int(plot_height * step / 4)
            painter.drawLine(x, plot_top, x, plot_bottom)
            painter.drawLine(plot_left, y, plot_right, y)

        mapped = [
            (
                plot_left + int((voltage - min_v) / (max_v - min_v) * plot_width),
                plot_bottom - int((current - min_i) / (max_i - min_i) * plot_height),
            )
            for voltage, current in self.points
        ]
        painter.setPen(QPen(QColor("#2563eb"), 2))
        for start, end in zip(mapped, mapped[1:]):
            painter.drawLine(start[0], start[1], end[0], end[1])
        painter.setPen(QPen(QColor("#1d4ed8"), 1))
        painter.setBrush(QColor("#60a5fa"))
        for x, y in mapped:
            painter.drawEllipse(x - 3, y - 3, 6, 6)

        painter.setPen(QPen(QColor("#374151"), 1))
        painter.drawText(plot_left, plot_bottom + 18, f"{min_v:.3g}")
        painter.drawText(plot_right - 48, plot_bottom + 18, f"{max_v:.3g}")
        painter.drawText(18, plot_bottom, f"{min_i:.3g}")
        painter.drawText(18, plot_top + 8, f"{max_i:.3g}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PyTransportMeasure")
        self.resize(1180, 760)
        self.setMinimumSize(760, 520)
        self.worker: DryRunWorker | None = None
        self.doctor_worker: DoctorWorker | None = None
        self.instrument_refresh_worker: InstrumentRefreshWorker | None = None
        self.communication_test_worker: CommunicationTestWorker | None = None
        self.preflight_worker: PreflightWorker | None = None
        self.hardware_worker: HardwareRunWorker | None = None
        self.last_result: Any | None = None
        self._syncing_recipe_widgets = False
        self.workflow_state: dict[str, bool] = {
            "yaml_checked": False,
            "instrument_refreshed": False,
            "communication_tested": False,
            "plan_ready": False,
            "dry_run_completed": False,
            "preflight_passed": False,
            "hardware_completed": False,
        }
        self.session_logger = GuiSessionLogger.create()

        self.method_combo = QComboBox()
        for key, label in available_gui_methods().items():
            self.method_combo.addItem(label, key)
        self.method_combo.currentIndexChanged.connect(self.apply_default_recipe)

        self.recipe_edit = QLineEdit()
        self.recipe_edit.setMinimumWidth(220)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_recipe)

        self.preview_spin = QSpinBox()
        self.preview_spin.setRange(0, 50)
        self.preview_spin.setValue(5)
        self.preview_spin.setToolTip("Number of sweep points shown in the Plan preview. Use 0 to show all points.")

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
        self.stop_run_button = QPushButton("Stop Run")
        self.stop_run_button.clicked.connect(self.request_stop_run)
        self.stop_run_button.setEnabled(False)
        self.doctor_button = QPushButton("Full Doctor")
        self.doctor_button.clicked.connect(self.start_doctor)
        self.preflight_button = QPushButton("Preflight")
        self.preflight_button.clicked.connect(self.start_preflight)
        self.hardware_run_button = QPushButton("Hardware Run")
        self.hardware_run_button.clicked.connect(self.confirm_and_start_hardware_run)
        self.load_editor_button = QPushButton("Open Recipe File")
        self.load_editor_button.clicked.connect(self.load_recipe_into_editor)
        self.validate_editor_button = QPushButton("Check YAML")
        self.validate_editor_button.clicked.connect(self.validate_editor)
        self.save_editor_button = QPushButton("Save YAML As")
        self.save_editor_button.clicked.connect(self.save_editor_as)
        self.load_form_button = QPushButton("YAML -> Form")
        self.load_form_button.clicked.connect(self.load_form_from_editor)
        self.apply_form_button = QPushButton("Form -> YAML")
        self.apply_form_button.clicked.connect(self.apply_form_to_editor)
        self.open_run_button = QPushButton("Run Folder")
        self.open_run_button.clicked.connect(self.open_run_folder)
        self.open_plot_button = QPushButton("Plot")
        self.open_plot_button.clicked.connect(self.open_plot)
        self.open_report_button = QPushButton("Report")
        self.open_report_button.clicked.connect(self.open_report)
        self.feedback_bundle_button = QPushButton("Feedback Bundle")
        self.feedback_bundle_button.clicked.connect(self.create_feedback_bundle)
        self.open_log_button = QPushButton("Open Log")
        self.open_log_button.clicked.connect(self.open_session_log_folder)
        self.refresh_instruments_button = QPushButton("Refresh Instruments")
        self.refresh_instruments_button.clicked.connect(self.start_instrument_refresh)
        self.test_connection_button = QPushButton("Test Selected Address")
        self.test_connection_button.clicked.connect(self.start_communication_test)
        self.instrument_address_combo = QComboBox()
        self.instrument_address_combo.setEditable(True)
        self.instrument_address_combo.setMinimumWidth(260)
        self.instrument_address_combo.setToolTip("VISA resource to probe. Refresh fills this list; the current recipe address is used as a fallback.")
        self.refresh_runs_button = QPushButton("Refresh Runs")
        self.refresh_runs_button.clicked.connect(self.refresh_indexed_runs)
        self.load_run_button = QPushButton("Load Selected")
        self.load_run_button.clicked.connect(self.load_selected_run)
        self.run_source_dir = QLineEdit("data/raw")
        self.run_source_dir.setPlaceholderText("run source folder")
        self.run_source_dir.setMinimumWidth(220)
        self.browse_run_source_button = QPushButton("Source Folder")
        self.browse_run_source_button.clicked.connect(self.browse_run_source_folder)
        self.run_filter_sample = QLineEdit()
        self.run_filter_sample.setPlaceholderText("sample")
        self.run_filter_device = QLineEdit()
        self.run_filter_device.setPlaceholderText("device")
        self.run_filter_cooldown = QLineEdit()
        self.run_filter_cooldown.setPlaceholderText("cooldown")
        self.run_filter_tag = QLineEdit()
        self.run_filter_tag.setPlaceholderText("tag")
        self.run_filter_method = QLineEdit()
        self.run_filter_method.setPlaceholderText("method")
        self.run_filter_status = QComboBox()
        self.run_filter_status.addItems(["Any status", "Completed", "Incomplete", "Failed", "Interrupted"])
        self.clear_run_filters_button = QPushButton("Clear Filters")
        self.clear_run_filters_button.clicked.connect(self.clear_run_filters)
        self.open_run_button.setEnabled(False)
        self.open_plot_button.setEnabled(False)
        self.open_report_button.setEnabled(False)
        self.feedback_bundle_button.setEnabled(False)
        self.load_run_button.setEnabled(False)
        self.loaded_run_dir: Path | None = None

        self.scheme_path_edit = QLineEdit("configs/schemes/gui_scheme.yaml")
        self.scheme_path_edit.setMinimumWidth(260)
        self.scheme_name_edit = QLineEdit("gui_scheme")
        self.scheme_stop_on_error = QComboBox()
        self.scheme_stop_on_error.addItems(["true", "false"])
        self.add_scheme_step_button = QPushButton("Add Step")
        self.add_scheme_step_button.clicked.connect(self.add_default_scheme_step)
        self.remove_scheme_step_button = QPushButton("Remove Selected")
        self.remove_scheme_step_button.clicked.connect(self.remove_selected_scheme_steps)
        self.scheme_form_to_yaml_button = QPushButton("Form -> Scheme YAML")
        self.scheme_form_to_yaml_button.clicked.connect(self.apply_scheme_form_to_yaml)
        self.scheme_yaml_to_form_button = QPushButton("Scheme YAML -> Form")
        self.scheme_yaml_to_form_button.clicked.connect(self.load_scheme_form_from_yaml)
        self.validate_scheme_button = QPushButton("Check Scheme")
        self.validate_scheme_button.clicked.connect(self.validate_scheme_yaml)
        self.plan_scheme_button = QPushButton("Scheme Plan")
        self.plan_scheme_button.clicked.connect(self.show_scheme_plan)
        self.save_scheme_button = QPushButton("Save Scheme As")
        self.save_scheme_button.clicked.connect(self.save_scheme_as)

        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.plan_text = QPlainTextEdit()
        self.plan_text.setReadOnly(True)
        self.recipe_overview_text = QPlainTextEdit()
        self.recipe_overview_text.setReadOnly(True)
        self.workflow_text = QPlainTextEdit()
        self.workflow_text.setReadOnly(True)
        self.editor_text = QPlainTextEdit()
        self.form_fields: dict[str, Any] = {}
        self.form_field_paths: list[str] = []
        self.form_status = QLabel("Schema-driven recipe form")
        self.recipe_sync_status = QLabel("Execution source: Recipe YAML. Form is generated from the current recipe schema.")
        self.validation_text = QPlainTextEdit()
        self.validation_text.setReadOnly(True)
        self.doctor_text = QPlainTextEdit()
        self.doctor_text.setReadOnly(True)
        self.instrument_status_text = self.doctor_text
        self.preflight_text = QPlainTextEdit()
        self.preflight_text.setReadOnly(True)
        self.progress_text = QPlainTextEdit()
        self.progress_text.setReadOnly(True)
        self.session_log_text = QPlainTextEdit()
        self.session_log_text.setReadOnly(True)
        self.summary_text = QPlainTextEdit()
        self.summary_text.setReadOnly(True)
        self.metadata_text = QPlainTextEdit()
        self.metadata_text.setReadOnly(True)
        self.report_text = QPlainTextEdit()
        self.report_text.setReadOnly(True)
        self.scheme_editor_text = QPlainTextEdit()
        self.scheme_plan_text = QPlainTextEdit()
        self.scheme_plan_text.setReadOnly(True)
        self.scheme_validation_text = QPlainTextEdit()
        self.scheme_validation_text.setReadOnly(True)
        self.scheme_step_table = QTableWidget(0, 12)
        self.scheme_step_table.setHorizontalHeaderLabels(
            [
                "Type",
                "Label",
                "Path",
                "Enabled",
                "Repeat",
                "Interval s",
                "Suffix",
                "Start V",
                "Stop V",
                "Points",
                "Delay s",
                "Compliance A",
            ]
        )
        self.scheme_step_table.horizontalHeader().setStretchLastSection(True)
        self.saved_plot_canvas = IvPlotCanvas()
        self.live_plot_canvas = IvPlotCanvas()
        self.plot_status = QLabel("No plot loaded")
        self.recent_table = QTableWidget(0, 11)
        self.recent_table.setHorizontalHeaderLabels(
            [
                "Started",
                "Method",
                "Name",
                "Status",
                "Points",
                "Sample",
                "Device",
                "Cooldown",
                "Notebook",
                "Tags",
                "Run folder",
            ]
        )
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        self.recent_table.setSortingEnabled(True)
        self.recent_table.itemSelectionChanged.connect(self.update_selected_run_controls)

        workspace_tabs = QTabWidget()
        workspace_tabs.addTab(self.build_measurement_workspace(), "Measurement")
        workspace_tabs.addTab(self.build_instrument_workspace(), "Instruments")
        workspace_tabs.addTab(self.build_analysis_workspace(), "Analysis")
        workspace_tabs.addTab(self.build_scheme_workspace(), "Schemes")

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(workspace_tabs, stretch=1)
        layout.addWidget(self.status_label)
        self.setCentralWidget(root)
        self.setStyleSheet(APP_STYLESHEET)
        self.build_menu()
        self.connect_recipe_sync_signals()
        self.apply_default_recipe()
        self.apply_default_scheme()
        self.update_workflow_guide("Start by checking YAML, then confirm instruments before hardware.")
        self.log_session(f"Session log path: {self.session_logger.path}")

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
        preview_label = QLabel("Plan lines")
        preview_label.setToolTip("Number of sweep points shown in the Plan preview. Use 0 to show all points.")
        layout.addWidget(preview_label, 0, 6)
        layout.addWidget(self.preview_spin, 0, 7)

        self.fake_box = QGroupBox("Dry-run Model")
        self.fake_box.setCheckable(True)
        self.fake_box.setChecked(False)
        fake_content = QWidget()
        self.fake_content = fake_content
        fake_layout = QFormLayout(fake_content)
        fake_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        fake_layout.setVerticalSpacing(8)
        fake_layout.addRow("R source", self.fake_resistance)
        fake_layout.addRow("Noise A", self.fake_noise)
        fake_layout.addRow("R channel", self.fake_channel_resistance)
        fake_layout.addRow("R gate leak", self.fake_gate_leak)
        fake_layout.addRow("Gate mod", self.fake_gate_modulation)
        fake_layout.addRow("Lock-in R", self.fake_lockin_r)
        fake_layout.addRow("Lock-in phase", self.fake_lockin_phase)
        fake_layout.addRow("Lock-in noise", self.fake_lockin_noise)
        fake_content.setMinimumHeight(fake_content.sizeHint().height())
        fake_scroll = QScrollArea()
        self.fake_scroll = fake_scroll
        fake_scroll.setWidgetResizable(True)
        fake_scroll.setWidget(fake_content)
        fake_scroll.setMinimumHeight(120)
        fake_scroll.setMaximumHeight(190)
        fake_box_layout = QVBoxLayout(self.fake_box)
        fake_box_layout.addWidget(fake_scroll)
        fake_scroll.setVisible(False)
        self.fake_box.toggled.connect(fake_scroll.setVisible)
        layout.addWidget(self.fake_box, 1, 0, 1, 8)

        run_button_row = QHBoxLayout()
        run_button_row.addWidget(self.plan_button)
        run_button_row.addWidget(self.run_button)
        run_button_row.addWidget(self.stop_run_button)
        run_button_row.addWidget(self.preflight_button)
        run_button_row.addWidget(self.hardware_run_button)
        run_button_row.addStretch(1)
        layout.addLayout(run_button_row, 2, 0, 1, 8)
        return box

    def build_recipe_tools(self) -> QWidget:
        box = QGroupBox("Recipe Tools")
        layout = QVBoxLayout(box)
        help_label = QLabel("File: open/save YAML. Form sync: copy values between the structured form and YAML editor.")
        self.recipe_sync_status.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(self.load_editor_button)
        row.addWidget(self.validate_editor_button)
        row.addWidget(self.save_editor_button)
        row.addWidget(self.load_form_button)
        row.addWidget(self.apply_form_button)
        row.addStretch(1)
        layout.addWidget(help_label)
        layout.addWidget(self.recipe_sync_status)
        layout.addLayout(row)
        return box

    def build_measurement_workspace(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.build_controls())
        measurement_tabs = QTabWidget()
        measurement_tabs.addTab(self.workflow_text, "Workflow")
        measurement_tabs.addTab(self.recipe_overview_text, "Recipe Overview")
        measurement_tabs.addTab(self.plan_text, "Plan")
        measurement_tabs.addTab(self.build_drain_iv_form(), "Recipe Form")
        measurement_tabs.addTab(self.editor_text, "Recipe YAML")
        measurement_tabs.addTab(self.validation_text, "Validation")
        measurement_tabs.addTab(self.preflight_text, "Preflight")
        measurement_tabs.addTab(self.progress_text, "Progress")
        measurement_tabs.addTab(self.build_live_plot(), "Live Plot")
        measurement_tabs.addTab(self.session_log_text, "Session Log")
        layout.addWidget(measurement_tabs, stretch=1)
        layout.addWidget(self.build_recipe_tools())
        return container

    def build_instrument_workspace(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        controls = QGroupBox("Instrument Status")
        controls_layout = QHBoxLayout(controls)
        controls_layout.addWidget(self.refresh_instruments_button)
        controls_layout.addWidget(QLabel("Address"))
        controls_layout.addWidget(self.instrument_address_combo, stretch=1)
        controls_layout.addWidget(self.test_connection_button)
        controls_layout.addWidget(self.doctor_button)
        controls_layout.addWidget(self.open_log_button)
        layout.addWidget(controls)
        layout.addWidget(self.instrument_status_text, stretch=1)
        return container

    def build_analysis_workspace(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        controls = QGroupBox("Run Analysis")
        controls_layout = QVBoxLayout(controls)
        action_row = QHBoxLayout()
        action_row.addWidget(self.refresh_runs_button)
        action_row.addWidget(self.load_run_button)
        action_row.addStretch(1)
        action_row.addWidget(self.open_run_button)
        action_row.addWidget(self.open_plot_button)
        action_row.addWidget(self.open_report_button)
        action_row.addWidget(self.feedback_bundle_button)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filters"))
        filter_row.addWidget(self.run_filter_sample)
        filter_row.addWidget(self.run_filter_device)
        filter_row.addWidget(self.run_filter_cooldown)
        filter_row.addWidget(self.run_filter_tag)
        filter_row.addWidget(self.run_filter_method)
        filter_row.addWidget(self.run_filter_status)
        filter_row.addWidget(self.clear_run_filters_button)
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source"))
        source_row.addWidget(self.run_source_dir, stretch=1)
        source_row.addWidget(self.browse_run_source_button)
        controls_layout.addLayout(action_row)
        controls_layout.addLayout(source_row)
        controls_layout.addLayout(filter_row)
        layout.addWidget(controls)
        analysis_tabs = QTabWidget()
        analysis_tabs.addTab(self.recent_table, "Runs")
        analysis_tabs.addTab(self.summary_text, "Summary")
        analysis_tabs.addTab(self.build_plot_preview(), "Plot")
        analysis_tabs.addTab(self.metadata_text, "Metadata")
        analysis_tabs.addTab(self.report_text, "Report")
        layout.addWidget(analysis_tabs, stretch=1)
        return container

    def build_scheme_workspace(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        controls = QGroupBox("Scheme Builder")
        controls_layout = QVBoxLayout(controls)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Name"))
        top_row.addWidget(self.scheme_name_edit)
        top_row.addWidget(QLabel("Path"))
        top_row.addWidget(self.scheme_path_edit, stretch=1)
        top_row.addWidget(QLabel("Stop on error"))
        top_row.addWidget(self.scheme_stop_on_error)

        action_row = QHBoxLayout()
        action_row.addWidget(self.add_scheme_step_button)
        action_row.addWidget(self.remove_scheme_step_button)
        action_row.addStretch(1)
        action_row.addWidget(self.scheme_yaml_to_form_button)
        action_row.addWidget(self.scheme_form_to_yaml_button)
        action_row.addWidget(self.validate_scheme_button)
        action_row.addWidget(self.plan_scheme_button)
        action_row.addWidget(self.save_scheme_button)

        controls_layout.addLayout(top_row)
        controls_layout.addLayout(action_row)
        layout.addWidget(controls)
        layout.addWidget(self.scheme_step_table, stretch=1)

        scheme_tabs = QTabWidget()
        scheme_tabs.addTab(self.scheme_editor_text, "Scheme YAML")
        scheme_tabs.addTab(self.scheme_plan_text, "Plan")
        scheme_tabs.addTab(self.scheme_validation_text, "Validation")
        layout.addWidget(scheme_tabs, stretch=1)
        return container

    def build_plot_preview(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.plot_status)
        layout.addWidget(self.saved_plot_canvas, stretch=1)
        return container

    def build_live_plot(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel("Live Drain I-V points"))
        layout.addWidget(self.live_plot_canvas, stretch=1)
        return container

    def build_drain_iv_form(self) -> QWidget:
        container = QWidget()
        self.schema_form_container = container
        layout = QVBoxLayout(container)
        self.schema_form_layout = layout
        layout.addWidget(self.form_status)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    def add_form_line(self, layout: Any, key: str, label: str) -> None:
        field = QLineEdit()
        self.form_fields[key] = field
        layout.addRow(label, field)

    def connect_recipe_sync_signals(self) -> None:
        self.editor_text.textChanged.connect(self.handle_yaml_text_changed)

    def handle_yaml_text_changed(self) -> None:
        if self._syncing_recipe_widgets:
            return
        self.validation_text.clear()
        self.update_recipe_overview()
        self.recipe_sync_status.setText(
            "YAML edited. YAML is the execution source. Use YAML -> Form if the form should mirror these edits."
        )
        self.reset_workflow_after_recipe_change("YAML edited. Click Check YAML before running.")

    def handle_form_value_changed(self) -> None:
        if self._syncing_recipe_widgets:
            return
        self.recipe_sync_status.setText(
            "Form edited. These values are not used until you click Form -> YAML."
        )
        self.reset_workflow_after_recipe_change("Form edited. Click Form -> YAML, then Check YAML.")

    def reset_workflow_after_recipe_change(self, note: str) -> None:
        for key in ["yaml_checked", "plan_ready", "dry_run_completed", "preflight_passed", "hardware_completed"]:
            self.workflow_state[key] = False
        self.update_workflow_guide(note)

    def mark_workflow(self, key: str, value: bool, note: str) -> None:
        self.workflow_state[key] = value
        self.update_workflow_guide(note)

    def update_workflow_guide(self, note: str = "") -> None:
        lines = [
            "PyTransportMeasure GUI Workflow",
            "",
            f"{workflow_mark(self.workflow_state['yaml_checked'])} Check YAML: validate the recipe that will actually run.",
            f"{workflow_mark(self.workflow_state['instrument_refreshed'])} Refresh Instruments: list currently visible VISA resources.",
            f"{workflow_mark(self.workflow_state['communication_tested'])} Test Selected Address: verify communication before output.",
            f"{workflow_mark(self.workflow_state['plan_ready'])} Plan: inspect sweep points and safety context.",
            f"{workflow_mark(self.workflow_state['dry_run_completed'])} Dry Run: verify artifacts and live plot without hardware.",
            f"{workflow_mark(self.workflow_state['preflight_passed'])} Preflight: final hardware-readiness gate.",
            f"{workflow_mark(self.workflow_state['hardware_completed'])} Hardware Run: guarded real measurement.",
            "",
            "Current note:",
            f"- {note or self.next_workflow_hint()}",
            "",
            "Execution source:",
            "- Recipe YAML is what Plan, Dry Run, Preflight, and Hardware Run use.",
            "- Form edits must be applied with Form -> YAML before they affect runs.",
        ]
        self.workflow_text.setPlainText("\n".join(lines))

    def update_recipe_overview(self) -> None:
        if not hasattr(self, "recipe_overview_text"):
            return
        try:
            text = format_recipe_overview_text(self.current_method(), self.editor_text.toPlainText())
        except Exception as exc:
            text = "\n".join(
                [
                    "Recipe Overview",
                    "",
                    "Current YAML cannot be summarized yet.",
                    f"{type(exc).__name__}: {exc}",
                ]
            )
        self.recipe_overview_text.setPlainText(text)

    def next_workflow_hint(self) -> str:
        if not self.workflow_state["yaml_checked"]:
            return "Click Check YAML."
        if not self.workflow_state["instrument_refreshed"]:
            return "Open Instruments and click Refresh Instruments."
        if not self.workflow_state["communication_tested"]:
            return "Select the intended address and click Test Selected Address."
        if not self.workflow_state["plan_ready"]:
            return "Click Plan and inspect the sweep."
        if not self.workflow_state["dry_run_completed"]:
            return "Run a Dry Run before touching hardware."
        if not self.workflow_state["preflight_passed"]:
            return "Click Preflight immediately before hardware."
        return "Ready for guarded Hardware Run."

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

    def scheme_path(self) -> Path:
        return Path(self.scheme_path_edit.text()).expanduser()

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
                self._syncing_recipe_widgets = True
                self.editor_text.setPlainText(default_recipe_text(self.current_method()))
                self.validation_text.clear()
                self.load_form_from_editor(silent=True)
                self.sync_recipe_address_to_instrument_combo()
                self.update_recipe_overview()
                self.recipe_sync_status.setText(
                    "Execution source: Recipe YAML. Form is synced from the default recipe."
                )
            except Exception:
                pass
            finally:
                self._syncing_recipe_widgets = False
        if hasattr(self, "load_form_button"):
            is_drain_iv = self.current_method() == "drain_iv"
            self.load_form_button.setEnabled(True)
            self.apply_form_button.setEnabled(True)
            self.preflight_button.setEnabled(is_drain_iv)
            self.hardware_run_button.setEnabled(is_drain_iv)
        if hasattr(self, "workflow_text"):
            self.reset_workflow_after_recipe_change("Default recipe loaded. Click Check YAML.")

    def apply_default_scheme(self) -> None:
        if not hasattr(self, "scheme_editor_text"):
            return
        self.scheme_editor_text.setPlainText(default_scheme_text())
        self.load_scheme_form_from_yaml(silent=True)

    def add_default_scheme_step(self) -> None:
        self.add_scheme_row(GuiSchemeStepDraft("drain_iv", "new_step", "../recipes/drain_iv_1k_resistor.yaml"))

    def add_scheme_row(self, step: GuiSchemeStepDraft) -> None:
        row = self.scheme_step_table.rowCount()
        self.scheme_step_table.insertRow(row)
        for column, text in enumerate(
            [
                step.type,
                step.label,
                step.path,
                str(step.enabled).lower(),
                str(step.repeat),
                f"{step.interval_s:g}",
                step.measurement_suffix,
                step.sweep_start_v,
                step.sweep_stop_v,
                step.sweep_points,
                step.sweep_delay_s,
                step.sweep_current_compliance_a,
            ]
        ):
            self.scheme_step_table.setItem(row, column, QTableWidgetItem(text))

    def remove_selected_scheme_steps(self) -> None:
        rows = sorted({index.row() for index in self.scheme_step_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.scheme_step_table.removeRow(row)

    def scheme_rows_from_table(self) -> list[GuiSchemeStepDraft]:
        rows: list[GuiSchemeStepDraft] = []
        for row in range(self.scheme_step_table.rowCount()):
            step_type = self.scheme_table_text(row, 0) or "drain_iv"
            if step_type not in {"drain_iv", "single_gate", "batch"}:
                raise ValueError("scheme step type must be drain_iv, single_gate, or batch")
            rows.append(
                GuiSchemeStepDraft(
                    type=step_type,
                    label=self.scheme_table_text(row, 1),
                    path=self.scheme_table_text(row, 2),
                    enabled=self.scheme_table_text(row, 3).lower() not in {"false", "0", "no", "n"},
                    repeat=int(self.scheme_table_text(row, 4) or "1"),
                    interval_s=float(self.scheme_table_text(row, 5) or "0"),
                    measurement_suffix=self.scheme_table_text(row, 6),
                    sweep_start_v=self.scheme_table_text(row, 7),
                    sweep_stop_v=self.scheme_table_text(row, 8),
                    sweep_points=self.scheme_table_text(row, 9),
                    sweep_delay_s=self.scheme_table_text(row, 10),
                    sweep_current_compliance_a=self.scheme_table_text(row, 11),
                )
            )
        return rows

    def scheme_table_text(self, row: int, column: int) -> str:
        item = self.scheme_step_table.item(row, column)
        return "" if item is None else item.text().strip()

    def load_scheme_form_from_yaml(self, silent: bool = False) -> bool:
        try:
            name, stop_on_error, steps = scheme_builder_from_text(self.scheme_editor_text.toPlainText())
        except Exception as exc:
            if not silent:
                self.show_error(exc)
            self.scheme_validation_text.setPlainText(f"Could not load scheme form\n{type(exc).__name__}: {exc}")
            return False
        self.scheme_name_edit.setText(name)
        self.scheme_stop_on_error.setCurrentText(str(stop_on_error).lower())
        self.scheme_step_table.setRowCount(0)
        for step in steps:
            self.add_scheme_row(step)
        if not silent:
            self.status_label.setText("Scheme form loaded from YAML")
        return True

    def apply_scheme_form_to_yaml(self) -> bool:
        try:
            text = scheme_text_from_builder(
                self.scheme_name_edit.text(),
                self.scheme_stop_on_error.currentText() == "true",
                self.scheme_rows_from_table(),
            )
        except Exception as exc:
            self.show_error(exc)
            self.scheme_validation_text.setPlainText(f"Could not generate scheme YAML\n{type(exc).__name__}: {exc}")
            return False
        self.scheme_editor_text.setPlainText(text)
        self.scheme_validation_text.clear()
        self.status_label.setText("Scheme YAML generated from form")
        self.log_session("Scheme form applied to YAML editor")
        return True

    def validate_scheme_yaml(self) -> bool:
        ok, message = validate_scheme_text(
            self.scheme_editor_text.toPlainText(),
            scheme_path=self.scheme_path(),
            preview_points=self.preview_spin.value(),
        )
        self.scheme_validation_text.setPlainText(message)
        self.status_label.setText("Scheme validation passed" if ok else "Scheme validation failed")
        self.log_session(f"Scheme validation {'passed' if ok else 'failed'}")
        return ok

    def show_scheme_plan(self) -> None:
        try:
            plan = format_scheme_plan_text(
                self.scheme_editor_text.toPlainText(),
                scheme_path=self.scheme_path(),
                preview_points=self.preview_spin.value(),
            )
        except Exception as exc:
            self.show_error(exc)
            return
        self.scheme_plan_text.setPlainText(plan)
        self.status_label.setText("Scheme plan ready")
        self.log_session("Scheme plan generated")

    def save_scheme_as(self) -> None:
        if not self.validate_scheme_yaml():
            return
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scheme As",
            str(Path("configs/schemes").resolve() / "gui_scheme.yaml"),
            "YAML (*.yaml *.yml)",
        )
        if not selected:
            return
        path = Path(selected)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.scheme_editor_text.toPlainText(), encoding="utf-8")
        self.scheme_path_edit.setText(str(path))
        self.status_label.setText(f"Scheme saved: {path}")
        self.log_session(f"Scheme saved: {path}")

    def browse_recipe(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "Open Recipe", str(Path("configs/recipes").resolve()), "YAML (*.yaml *.yml)")
        if selected:
            self.recipe_edit.setText(selected)

    def show_plan(self) -> None:
        try:
            plan = format_gui_plan_text(
                self.current_method(),
                self.editor_text.toPlainText(),
                preview_points=self.preview_spin.value(),
            )
        except Exception as exc:
            self.show_error(exc)
            return
        self.plan_text.setPlainText(plan)
        self.update_recipe_overview()
        self.status_label.setText("Plan ready from editor YAML")
        self.mark_workflow("plan_ready", True, "Plan generated. Inspect sweep points before running.")
        self.log_session(f"Plan generated for {self.current_method()}")

    def load_recipe_into_editor(self) -> None:
        try:
            self._syncing_recipe_widgets = True
            self.editor_text.setPlainText(load_recipe_text(self.recipe_path()))
        except Exception as exc:
            self.show_error(exc)
            return
        finally:
            self._syncing_recipe_widgets = False
        self.validation_text.clear()
        self.load_form_from_editor(silent=True)
        self.sync_recipe_address_to_instrument_combo()
        self.update_recipe_overview()
        self.recipe_sync_status.setText("Recipe file loaded. YAML is the execution source; form is synced from YAML.")
        self.reset_workflow_after_recipe_change("Recipe file loaded. Click Check YAML.")
        self.status_label.setText("Recipe loaded into editor")
        self.log_session(f"Recipe loaded into editor: {self.recipe_path()}")

    def load_form_from_editor(self, silent: bool = False) -> bool:
        try:
            was_syncing = self._syncing_recipe_widgets
            self._syncing_recipe_widgets = True
            sections = schema_form_from_text(self.current_method(), self.editor_text.toPlainText())
            self.rebuild_schema_form(sections)
        except Exception as exc:
            if not silent:
                self.show_error(exc)
            self.form_status.setText("Could not load schema form from YAML")
            return False
        finally:
            self._syncing_recipe_widgets = was_syncing if "was_syncing" in locals() else False
        self.form_status.setText(f"{available_gui_methods().get(self.current_method(), self.current_method())} form loaded from YAML")
        self.recipe_sync_status.setText("Form is synced from YAML. YAML remains the execution source.")
        if not silent:
            self.status_label.setText("Form loaded from YAML")
        return True

    def apply_form_to_editor(self) -> bool:
        try:
            text = schema_form_text_from_values(self.current_method(), self.editor_text.toPlainText(), self.form_values())
        except Exception as exc:
            self.show_error(exc)
            self.form_status.setText("Could not apply schema form")
            return False
        try:
            self._syncing_recipe_widgets = True
            self.editor_text.setPlainText(text)
        finally:
            self._syncing_recipe_widgets = False
        self.validation_text.clear()
        self.sync_recipe_address_to_instrument_combo()
        self.update_recipe_overview()
        self.load_form_from_editor(silent=True)
        self.form_status.setText("YAML updated from schema form")
        self.recipe_sync_status.setText("YAML regenerated from form. YAML is now the execution source for runs.")
        self.reset_workflow_after_recipe_change("YAML regenerated from form. Click Check YAML next.")
        self.status_label.setText("YAML updated from form")
        self.log_session(f"Schema form applied to YAML editor for {self.current_method()}")
        return True

    def form_values(self) -> dict[str, str]:
        values = {}
        for key in self.form_field_paths:
            widget = self.form_fields.get(key)
            if widget is None:
                values[key] = ""
            elif isinstance(widget, QComboBox):
                values[key] = widget.currentText()
            else:
                values[key] = widget.text()
        return values

    def rebuild_schema_form(self, sections: Any) -> None:
        if not hasattr(self, "schema_form_layout"):
            return
        while self.schema_form_layout.count():
            item = self.schema_form_layout.takeAt(0)
            widget = item.widget()
            if widget is self.form_status:
                widget.setParent(None)
            elif widget is not None:
                widget.deleteLater()
        self.form_fields = {}
        self.form_field_paths = []
        self.schema_form_layout.addWidget(self.form_status)
        for section in sections:
            box = QGroupBox(section.title)
            form_layout = QFormLayout(box)
            form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            for field in section.fields:
                widget = self.schema_widget_for_field(field)
                label = field.label + (" *" if field.required else "")
                form_layout.addRow(label, widget)
                self.form_fields[field.path] = widget
                self.form_field_paths.append(field.path)
                leaf = field.path.split(".")[-1]
                if leaf not in self.form_fields:
                    self.form_fields[leaf] = widget
                if isinstance(widget, QComboBox):
                    widget.currentTextChanged.connect(self.handle_form_value_changed)
                else:
                    widget.textChanged.connect(self.handle_form_value_changed)
            self.schema_form_layout.addWidget(box)
        self.schema_form_layout.addStretch(1)

    def schema_widget_for_field(self, field: GuiSchemaField) -> Any:
        if field.kind == "choice":
            widget = QComboBox()
            widget.addItems(list(field.choices))
            index = widget.findText(field.value)
            widget.setCurrentIndex(index if index >= 0 else 0)
            return widget
        if field.kind == "bool":
            widget = QComboBox()
            widget.addItems(["true", "false"])
            widget.setCurrentIndex(0 if field.value.lower() == "true" else 1)
            return widget
        widget = QLineEdit(field.value)
        widget.setToolTip(field.path)
        return widget

    def validate_editor(self) -> bool:
        ok, message = validate_recipe_text(
            self.current_method(),
            self.editor_text.toPlainText(),
            preview_points=self.preview_spin.value(),
        )
        self.validation_text.setPlainText(message)
        self.update_recipe_overview()
        self.status_label.setText("Recipe validation passed" if ok else "Recipe validation failed")
        self.mark_workflow(
            "yaml_checked",
            ok,
            "YAML check passed." if ok else "YAML check failed. Fix recipe before continuing.",
        )
        self.log_session(f"Recipe validation {'passed' if ok else 'failed'} for {self.current_method()}")
        return ok

    def save_editor_as(self) -> None:
        if not self.validate_editor():
            return
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save YAML As",
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
        self.log_session(f"Recipe saved: {path}")

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
        self.progress_text.setPlainText("Dry-run starting...")
        self.live_plot_canvas.reset_live("Live dry-run Drain I-V")
        self.log_session(f"Dry-run starting: {self.current_method()}")
        self.worker = DryRunWorker(self.current_method(), self.editor_text.toPlainText(), fake)
        self.worker.progress.connect(self.append_progress)
        self.worker.point_progress.connect(self.append_live_point)
        self.worker.finished_ok.connect(self.handle_result)
        self.worker.failed.connect(self.handle_failure)
        self.worker.finished.connect(lambda: self.set_running(False))
        self.worker.start()

    def request_stop_run(self) -> None:
        requested = False
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            requested = True
        if self.hardware_worker is not None and self.hardware_worker.isRunning():
            self.hardware_worker.request_stop()
            requested = True
        if requested:
            self.stop_run_button.setEnabled(False)
            self.progress_text.appendPlainText("Stop requested. The run will stop at the next safe checkpoint.")
            self.status_label.setText("Stop requested")
            self.log_session("Stop requested for active run")

    def start_preflight(self) -> None:
        if self.preflight_worker is not None and self.preflight_worker.isRunning():
            return
        self.set_preflighting(True)
        self.preflight_text.setPlainText("Preflight running...")
        self.log_session(f"Preflight starting: {self.current_method()}")
        self.preflight_worker = PreflightWorker(self.current_method(), self.editor_text.toPlainText())
        self.preflight_worker.finished_ok.connect(self.handle_preflight_result)
        self.preflight_worker.failed.connect(self.handle_preflight_failure)
        self.preflight_worker.finished.connect(lambda: self.set_preflighting(False))
        self.preflight_worker.start()

    def start_doctor(self) -> None:
        if self.doctor_worker is not None and self.doctor_worker.isRunning():
            return
        self.set_doctor_running(True)
        self.doctor_text.setPlainText("Doctor running...")
        self.log_session(f"Doctor starting: {self.current_method()}")
        self.doctor_worker = DoctorWorker(self.current_method(), self.editor_text.toPlainText())
        self.doctor_worker.finished_ok.connect(self.handle_doctor_result)
        self.doctor_worker.failed.connect(self.handle_doctor_failure)
        self.doctor_worker.finished.connect(lambda: self.set_doctor_running(False))
        self.doctor_worker.start()

    def start_instrument_refresh(self) -> None:
        if self.instrument_refresh_worker is not None and self.instrument_refresh_worker.isRunning():
            return
        self.set_instrument_refreshing(True)
        self.instrument_status_text.setPlainText("Refreshing VISA resources...")
        self.log_session("Instrument refresh starting")
        self.instrument_refresh_worker = InstrumentRefreshWorker()
        self.instrument_refresh_worker.finished_ok.connect(self.handle_instrument_refresh_result)
        self.instrument_refresh_worker.failed.connect(self.handle_instrument_refresh_failure)
        self.instrument_refresh_worker.finished.connect(lambda: self.set_instrument_refreshing(False))
        self.instrument_refresh_worker.start()

    def handle_instrument_refresh_result(self, resources: tuple[str, ...], text: str) -> None:
        self.populate_instrument_addresses(resources)
        self.instrument_status_text.setPlainText(text)
        self.status_label.setText(f"Detected {len(resources)} VISA resource(s)")
        self.mark_workflow("instrument_refreshed", True, f"Detected {len(resources)} VISA resource(s).")
        self.log_session(f"Instrument refresh finished: {len(resources)} resource(s)")

    def handle_instrument_refresh_failure(self, message: str) -> None:
        self.instrument_status_text.setPlainText(f"Instrument refresh failed\n\n{message}")
        self.status_label.setText("Instrument refresh failed")
        self.mark_workflow("instrument_refreshed", False, "Instrument refresh failed.")
        self.log_session(f"Instrument refresh failed: {message}")
        QMessageBox.critical(self, "PyTransportMeasure", message)

    def start_communication_test(self) -> None:
        if self.communication_test_worker is not None and self.communication_test_worker.isRunning():
            return
        try:
            address = self.selected_instrument_address()
            timeout_ms = self.selected_instrument_timeout_ms()
        except Exception as exc:
            self.show_error(exc)
            return
        self.set_communication_testing(True)
        self.instrument_status_text.setPlainText(f"Testing communication with {address}...")
        self.log_session(f"Communication test starting: {address}")
        self.communication_test_worker = CommunicationTestWorker(address, timeout_ms)
        self.communication_test_worker.finished_ok.connect(self.handle_communication_test_result)
        self.communication_test_worker.failed.connect(self.handle_communication_test_failure)
        self.communication_test_worker.finished.connect(lambda: self.set_communication_testing(False))
        self.communication_test_worker.start()

    def handle_communication_test_result(self, text: str) -> None:
        passed = "OK: True" in text
        self.instrument_status_text.setPlainText(text)
        self.status_label.setText("Communication test passed" if passed else "Communication test found an issue")
        self.mark_workflow(
            "communication_tested",
            passed,
            "Communication test passed." if passed else "Communication test found an issue.",
        )
        self.log_session("Communication test finished")
        self.log_session(text)

    def handle_communication_test_failure(self, message: str) -> None:
        self.instrument_status_text.setPlainText(f"Communication test failed\n\n{message}")
        self.status_label.setText("Communication test failed")
        self.mark_workflow("communication_tested", False, "Communication test failed.")
        self.log_session(f"Communication test failed: {message}")
        QMessageBox.critical(self, "PyTransportMeasure", message)

    def handle_doctor_result(self, text: str) -> None:
        self.doctor_text.setPlainText(text)
        self.status_label.setText("Doctor passed" if "OK: True" in text else "Doctor found an issue")
        self.log_session("Doctor finished")
        self.log_session(text)

    def handle_doctor_failure(self, message: str) -> None:
        self.doctor_text.setPlainText(f"Doctor failed\n\n{message}")
        self.status_label.setText("Doctor failed")
        self.log_session(f"Doctor failed: {message}")
        QMessageBox.critical(self, "PyTransportMeasure", message)

    def confirm_and_start_hardware_run(self) -> None:
        if self.hardware_worker is not None and self.hardware_worker.isRunning():
            return
        try:
            message = format_hardware_confirmation_text(self.current_method(), self.editor_text.toPlainText())
        except Exception as exc:
            self.show_error(exc)
            return
        answer = QMessageBox.warning(
            self,
            "Confirm Hardware Run",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self.status_label.setText("Hardware run cancelled")
            self.log_session("Hardware run cancelled at confirmation dialog")
            return
        self.start_hardware_run()

    def start_hardware_run(self) -> None:
        self.set_hardware_running(True)
        self.summary_text.clear()
        self.metadata_text.clear()
        self.report_text.clear()
        self.progress_text.setPlainText("Hardware run starting...")
        self.preflight_text.setPlainText("Hardware run starting. Preflight will run before output is enabled.")
        self.live_plot_canvas.reset_live("Live hardware Drain I-V")
        self.log_session(f"Hardware run starting: {self.current_method()}")
        self.hardware_worker = HardwareRunWorker(self.current_method(), self.editor_text.toPlainText())
        self.hardware_worker.progress.connect(self.append_progress)
        self.hardware_worker.point_progress.connect(self.append_live_point)
        self.hardware_worker.finished_ok.connect(self.handle_hardware_result)
        self.hardware_worker.failed.connect(self.handle_hardware_failure)
        self.hardware_worker.finished.connect(lambda: self.set_hardware_running(False))
        self.hardware_worker.start()

    def handle_hardware_result(self, result) -> None:
        self.display_result(result, add_to_table=True)
        self.status_label.setText(f"Hardware run completed: {result.metadata.get('completed')} | {result.run_dir}")
        completed = bool(result.metadata.get("completed"))
        self.mark_workflow(
            "hardware_completed",
            completed,
            "Hardware run completed." if completed else "Hardware run finished incomplete.",
        )
        self.log_session(f"Hardware run finished: completed={result.metadata.get('completed')} | {result.run_dir}")

    def handle_hardware_failure(self, message: str) -> None:
        self.preflight_text.setPlainText(message)
        self.progress_text.appendPlainText(f"Hardware run failed or blocked: {message}")
        self.status_label.setText("Hardware run failed or blocked")
        self.mark_workflow("hardware_completed", False, "Hardware run failed or was blocked.")
        self.log_session(f"Hardware run failed or blocked: {message}")
        QMessageBox.critical(self, "PyTransportMeasure", message)

    def append_progress(self, line: str) -> None:
        self.progress_text.appendPlainText(line)
        self.log_session(f"Progress: {line}")

    def append_live_point(self, point: Any, total_points: int) -> None:
        title = f"Live Drain I-V ({int(getattr(point, 'index', 0)) + 1}/{total_points})"
        self.live_plot_canvas.append_live_point(point, title)

    def handle_preflight_result(self, text: str) -> None:
        self.preflight_text.setPlainText(text)
        passed = "Preflight OK: True" in text
        status = "Preflight passed" if passed else "Preflight failed"
        self.status_label.setText(status)
        self.mark_workflow(
            "preflight_passed",
            passed,
            "Preflight passed." if passed else "Preflight failed. Fix readiness issues before hardware.",
        )
        self.log_session(status)
        self.log_session(text)

    def handle_preflight_failure(self, message: str) -> None:
        self.preflight_text.setPlainText(f"Preflight failed\n\n{message}")
        self.status_label.setText("Preflight failed")
        self.mark_workflow("preflight_passed", False, "Preflight failed.")
        self.log_session(f"Preflight failed: {message}")
        QMessageBox.critical(self, "PyTransportMeasure", message)

    def handle_result(self, result) -> None:
        self.display_result(result, add_to_table=True)
        completed = bool(result.metadata.get("completed"))
        self.mark_workflow(
            "dry_run_completed",
            completed,
            "Dry-run completed." if completed else "Dry-run finished incomplete.",
        )
        self.log_session(f"Dry-run finished: completed={result.metadata.get('completed')} | {result.run_dir}")

    def display_result(self, result, add_to_table: bool) -> None:
        self.last_result = result
        self.loaded_run_dir = result.run_dir
        self.summary_text.setPlainText("\n".join(part for part in [result.summary_text, result.quality_text] if part))
        self.metadata_text.setPlainText(read_text(Path(result.metadata["metadata_path"])))
        report_path = self.report_path()
        if report_path and report_path.exists():
            self.report_text.setPlainText(read_text(report_path))
        self.update_plot_preview()
        if add_to_table:
            self.add_recent_run(result)
        else:
            self.highlight_loaded_run_row()
        self.open_run_button.setEnabled(True)
        self.open_plot_button.setEnabled(self.plot_path() is not None)
        self.open_report_button.setEnabled(self.report_path() is not None)
        self.feedback_bundle_button.setEnabled(True)
        self.status_label.setText(f"Completed: {result.metadata.get('completed')} | {result.run_dir}")
        self.log_session(f"Displayed run: completed={result.metadata.get('completed')} | {result.run_dir}")

    def handle_failure(self, message: str) -> None:
        self.progress_text.appendPlainText(f"Run failed: {message}")
        self.status_label.setText("Failed")
        self.mark_workflow("dry_run_completed", False, "Run failed.")
        self.log_session(f"Run failed: {message}")
        QMessageBox.critical(self, "PyTransportMeasure", message)

    def set_running(self, running: bool) -> None:
        is_drain_iv = self.current_method() == "drain_iv"
        self.run_button.setEnabled(not running)
        self.stop_run_button.setEnabled(running)
        self.doctor_button.setEnabled(not running)
        self.refresh_instruments_button.setEnabled(not running)
        self.test_connection_button.setEnabled(not running)
        self.plan_button.setEnabled(not running)
        self.preflight_button.setEnabled(is_drain_iv and not running)
        self.hardware_run_button.setEnabled(is_drain_iv and not running)
        if running:
            self.status_label.setText("Running dry-run...")

    def set_preflighting(self, running: bool) -> None:
        is_drain_iv = self.current_method() == "drain_iv"
        self.stop_run_button.setEnabled(False)
        self.preflight_button.setEnabled(is_drain_iv and not running)
        self.plan_button.setEnabled(not running)
        self.doctor_button.setEnabled(not running)
        self.refresh_instruments_button.setEnabled(not running)
        self.test_connection_button.setEnabled(not running)
        self.run_button.setEnabled(not running)
        self.hardware_run_button.setEnabled(is_drain_iv and not running)
        if running:
            self.status_label.setText("Running preflight...")

    def set_hardware_running(self, running: bool) -> None:
        is_drain_iv = self.current_method() == "drain_iv"
        self.hardware_run_button.setEnabled(is_drain_iv and not running)
        self.stop_run_button.setEnabled(running)
        self.preflight_button.setEnabled(is_drain_iv and not running)
        self.doctor_button.setEnabled(not running)
        self.refresh_instruments_button.setEnabled(not running)
        self.test_connection_button.setEnabled(not running)
        self.run_button.setEnabled(not running)
        self.plan_button.setEnabled(not running)
        if running:
            self.status_label.setText("Running hardware measurement...")

    def set_doctor_running(self, running: bool) -> None:
        is_drain_iv = self.current_method() == "drain_iv"
        self.stop_run_button.setEnabled(False)
        self.doctor_button.setEnabled(not running)
        self.refresh_instruments_button.setEnabled(not running)
        self.test_connection_button.setEnabled(not running)
        self.preflight_button.setEnabled(is_drain_iv and not running)
        self.hardware_run_button.setEnabled(is_drain_iv and not running)
        self.run_button.setEnabled(not running)
        self.plan_button.setEnabled(not running)
        if running:
            self.status_label.setText("Running doctor...")

    def set_instrument_refreshing(self, running: bool) -> None:
        self.stop_run_button.setEnabled(False)
        self.refresh_instruments_button.setEnabled(not running)
        self.test_connection_button.setEnabled(not running)
        self.doctor_button.setEnabled(not running)
        if running:
            self.status_label.setText("Refreshing instruments...")

    def set_communication_testing(self, running: bool) -> None:
        self.stop_run_button.setEnabled(False)
        self.test_connection_button.setEnabled(not running)
        self.refresh_instruments_button.setEnabled(not running)
        self.doctor_button.setEnabled(not running)
        if running:
            self.status_label.setText("Testing instrument communication...")

    def populate_instrument_addresses(self, resources: tuple[str, ...]) -> None:
        current = self.selected_instrument_address(fallback_to_recipe=False)
        recipe_address = self.recipe_instrument_address()
        addresses = list(resources)
        if recipe_address and recipe_address not in addresses:
            addresses.insert(0, recipe_address)
        self.instrument_address_combo.clear()
        self.instrument_address_combo.addItems(addresses)
        preferred = current or recipe_address
        if preferred:
            index = self.instrument_address_combo.findText(preferred)
            if index >= 0:
                self.instrument_address_combo.setCurrentIndex(index)
            else:
                self.instrument_address_combo.setEditText(preferred)

    def sync_recipe_address_to_instrument_combo(self) -> None:
        address = self.recipe_instrument_address()
        if not address or not hasattr(self, "instrument_address_combo"):
            return
        if self.instrument_address_combo.findText(address) < 0:
            self.instrument_address_combo.insertItem(0, address)
        self.instrument_address_combo.setCurrentText(address)

    def selected_instrument_address(self, fallback_to_recipe: bool = True) -> str:
        address = self.instrument_address_combo.currentText().strip()
        if not address and fallback_to_recipe:
            address = self.recipe_instrument_address()
        if not address:
            raise ValueError("No VISA address selected")
        return address

    def selected_instrument_timeout_ms(self) -> int:
        try:
            recipe = load_recipe_from_editor_safely(self.current_method(), self.editor_text.toPlainText())
            return int(getattr(getattr(recipe, "instrument", None), "timeout_ms", 10000))
        except Exception:
            return 10000

    def recipe_instrument_address(self) -> str:
        try:
            recipe = load_recipe_from_editor_safely(self.current_method(), self.editor_text.toPlainText())
        except Exception:
            return ""
        instrument = getattr(recipe, "instrument", None) or getattr(recipe, "drain_instrument", None) or getattr(recipe, "source_instrument", None)
        return str(getattr(instrument, "address", "") or "")

    def add_recent_run(self, result) -> None:
        recipe = result.metadata.get("recipe") or {}
        experiment = recipe.get("experiment") or {}
        record = {
            "started_at": result.metadata.get("started_at"),
            "measurement_type": result.metadata.get("measurement_type"),
            "measurement_name": result.metadata.get("measurement_name"),
            "completed": result.metadata.get("completed"),
            "interrupted": result.metadata.get("interrupted"),
            "error_type": result.metadata.get("error_type"),
            "points_written": result.metadata.get("points_written"),
            "sample_id": experiment.get("sample_id"),
            "device_id": experiment.get("device_id"),
            "cooldown_id": experiment.get("cooldown_id"),
            "lab_notebook_ref": experiment.get("lab_notebook_ref"),
            "tags": experiment.get("tags") or [],
            "run_dir": result.metadata.get("run_dir"),
        }
        self.add_run_record_to_table(record)

    def add_run_record_to_table(self, record: dict[str, Any]) -> None:
        row = self.recent_table.rowCount()
        self.recent_table.insertRow(row)
        values = [
            record.get("started_at"),
            record.get("measurement_type"),
            record.get("measurement_name"),
            run_status_text(record),
            record.get("points_written"),
            record.get("sample_id"),
            record.get("device_id"),
            record.get("cooldown_id"),
            record.get("lab_notebook_ref"),
            ", ".join(record.get("tags") or []),
            record.get("run_dir"),
        ]
        for column, value in enumerate(values):
            text = "" if value is None else str(value)
            item = SortableTableWidgetItem(text, run_table_sort_key(column, value))
            self.recent_table.setItem(row, column, item)
        self.apply_loaded_run_highlight_to_row(row)

    def refresh_indexed_runs(self) -> None:
        try:
            records = list_gui_runs(
                source_dir=self.run_source_dir.text(),
                sample_id=self.run_filter_sample.text(),
                device_id=self.run_filter_device.text(),
                cooldown_id=self.run_filter_cooldown.text(),
                tag=self.run_filter_tag.text(),
                measurement_type=self.run_filter_method.text(),
                **self.run_status_filter_kwargs(),
            )
        except Exception as exc:
            self.show_error(exc)
            return
        self.recent_table.setSortingEnabled(False)
        self.recent_table.setRowCount(0)
        for record in records:
            self.add_run_record_to_table(record)
        self.recent_table.setSortingEnabled(True)
        self.highlight_loaded_run_row()
        self.status_label.setText(f"Loaded {len(records)} indexed runs")
        self.log_session(f"Indexed runs refreshed: {len(records)} records")

    def run_status_filter_kwargs(self) -> dict[str, Any]:
        status = self.run_filter_status.currentText()
        if status == "Completed":
            return {"completed": True}
        if status == "Incomplete":
            return {"completed": False}
        if status == "Failed":
            return {"failed": True}
        if status == "Interrupted":
            return {"interrupted": True}
        return {}

    def clear_run_filters(self) -> None:
        for field in [
            self.run_filter_sample,
            self.run_filter_device,
            self.run_filter_cooldown,
            self.run_filter_tag,
            self.run_filter_method,
        ]:
            field.clear()
        self.run_filter_status.setCurrentIndex(0)
        self.refresh_indexed_runs()

    def browse_run_source_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select Run Source Folder", str(Path(self.run_source_dir.text() or "data/raw").resolve()))
        if selected:
            self.run_source_dir.setText(selected)
            self.refresh_indexed_runs()

    def selected_run_dir(self) -> Path | None:
        selected = self.recent_table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.recent_table.item(row, 10)
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
        self.loaded_run_dir = result.run_dir
        self.display_result(result, add_to_table=False)
        self.highlight_loaded_run_row()
        self.log_session(f"Saved run loaded: {run_dir}")

    def highlight_loaded_run_row(self) -> None:
        for row in range(self.recent_table.rowCount()):
            self.apply_loaded_run_highlight_to_row(row)

    def apply_loaded_run_highlight_to_row(self, row: int) -> None:
        is_loaded = False
        item = self.recent_table.item(row, 10)
        if item is not None and item.text() and self.loaded_run_dir is not None:
            is_loaded = same_path(Path(item.text()), self.loaded_run_dir)
        color = QColor("#dbeafe") if is_loaded else QColor("#ffffff")
        for column in range(self.recent_table.columnCount()):
            cell = self.recent_table.item(row, column)
            if cell is not None:
                cell.setBackground(color)

    def plot_path(self) -> Path | None:
        if self.last_result is None:
            return None
        return primary_plot_path(self.last_result.metadata)

    def report_path(self) -> Path | None:
        if self.last_result is None:
            return None
        return primary_report_path(self.last_result.metadata)

    def update_plot_preview(self) -> None:
        if self.last_result is None:
            self.plot_status.setText("No run loaded")
            self.saved_plot_canvas.clear("No run loaded")
            return
        points_path = self.last_result.run_dir / "points.csv"
        if not points_path.exists():
            self.plot_status.setText("No points.csv found for plot preview")
            self.saved_plot_canvas.clear("No point data")
            return
        points = load_iv_points(points_path)
        title = str(self.last_result.metadata.get("measurement_name") or self.last_result.run_dir.name)
        self.saved_plot_canvas.plot_points(points, title)
        artifact = self.plot_path()
        if artifact is None:
            self.plot_status.setText(f"Plot preview from {points_path}")
        else:
            self.plot_status.setText(f"Plot preview from points.csv | saved artifact: {artifact}")

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

    def create_feedback_bundle(self) -> None:
        if self.last_result is None:
            return
        try:
            zip_path = create_gui_feedback_bundle(
                self.last_result.run_dir,
                extra_files=[self.session_logger.path],
            )
        except Exception as exc:
            self.show_error(exc)
            return
        self.status_label.setText(f"Feedback bundle: {zip_path}")
        self.log_session(f"Feedback bundle created: {zip_path}")
        open_path(zip_path.parent)

    def show_error(self, exc: Exception) -> None:
        self.log_session(f"Error dialog: {type(exc).__name__}: {exc}")
        QMessageBox.critical(self, "PyTransportMeasure", f"{type(exc).__name__}: {exc}")

    def open_session_log_folder(self) -> None:
        open_path(self.session_logger.path.parent)

    def log_session(self, message: str) -> None:
        self.session_logger.write(message)
        if hasattr(self, "session_log_text"):
            update_plain_text_preserving_scroll(self.session_log_text, self.session_logger.read_text())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_recipe_from_editor_safely(measurement_type: str, text: str) -> Any:
    return load_recipe_from_text(measurement_type, text)


def update_plain_text_preserving_scroll(text_edit: Any, text: str) -> None:
    scrollbar = text_edit.verticalScrollBar()
    previous_value = scrollbar.value()
    was_at_bottom = previous_value >= scrollbar.maximum() - 2
    text_edit.setPlainText(text)
    if was_at_bottom:
        scrollbar.setValue(scrollbar.maximum())
    else:
        scrollbar.setValue(min(previous_value, scrollbar.maximum()))


def load_iv_points(path: Path) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            try:
                points.append((float(row["voltage_v"]), float(row["current_a"])))
            except (KeyError, TypeError, ValueError):
                continue
    return points


def padded_range(minimum: float, maximum: float) -> tuple[float, float]:
    if minimum == maximum:
        padding = abs(minimum) * 0.05 or 1.0
        return minimum - padding, maximum + padding
    padding = (maximum - minimum) * 0.05
    return minimum - padding, maximum + padding


def workflow_mark(value: bool) -> str:
    return "[x]" if value else "[ ]"


def run_status_text(record: dict[str, Any]) -> str:
    if record.get("interrupted"):
        return "Interrupted"
    if record.get("error_type"):
        return f"Failed: {record.get('error_type')}"
    if record.get("completed") is True:
        return "Completed"
    if record.get("completed") is False:
        return "Incomplete"
    return "Unknown"


def run_table_sort_key(column: int, value: Any) -> Any:
    if value is None:
        return ""
    if column == 4:
        try:
            return int(value)
        except (TypeError, ValueError):
            return -1
    return str(value).lower()


def same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return str(left) == str(right)


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
