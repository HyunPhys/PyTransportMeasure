import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from pytransport.gui_app import MainWindow, padded_range, run_status_text, same_path, update_plain_text_preserving_scroll


@pytest.fixture
def app():
    existing = QtWidgets.QApplication.instance()
    if existing is not None:
        return existing
    return QtWidgets.QApplication([])


def test_gui_dry_run_model_is_collapsed_by_default(app):
    window = MainWindow()

    assert window.minimumWidth() <= 760
    assert window.minimumHeight() <= 520
    assert window.fake_box.isCheckable()
    assert not window.fake_box.isChecked()
    assert window.fake_scroll.isHidden()

    window.fake_box.setChecked(True)

    assert not window.fake_scroll.isHidden()
    assert window.fake_scroll.widget() is window.fake_content
    assert window.fake_scroll.maximumHeight() >= 160
    window.close()


def test_gui_has_measurement_instrument_and_analysis_workspaces(app):
    window = MainWindow()

    tab_labels = []
    for tabs in window.findChildren(QtWidgets.QTabWidget):
        for index in range(tabs.count()):
            tab_labels.append(tabs.tabText(index))

    assert "Measurement" in tab_labels
    assert "Instruments" in tab_labels
    assert "Analysis" in tab_labels
    assert "Schemes" in tab_labels
    assert "Recipe Overview" in tab_labels
    assert "Recipe Form" in tab_labels
    assert "Doctor" not in tab_labels
    assert window.doctor_button.text() == "Full Doctor"
    assert window.refresh_instruments_button.text() == "Refresh Instruments"
    assert window.test_connection_button.text() == "Test Selected Address"
    assert "Method: Drain I-V (drain_iv)" in window.recipe_overview_text.toPlainText()
    assert window.scheme_step_table.rowCount() >= 2
    assert window.scheme_step_table.columnCount() == 12
    window.close()


def test_gui_recipe_tool_labels_are_distinct(app):
    window = MainWindow()

    assert window.load_editor_button.text() == "Open Recipe File"
    assert window.validate_editor_button.text() == "Check YAML"
    assert window.save_editor_button.text() == "Save YAML As"
    assert window.load_form_button.text() == "YAML -> Form"
    assert window.apply_form_button.text() == "Form -> YAML"
    assert window.instrument_address_combo.currentText()
    assert "Execution source" in window.recipe_sync_status.text()
    assert "Schema" in window.form_status.text() or "form loaded from YAML" in window.form_status.text()
    assert "cooldown_id" in window.form_fields
    assert "contact_geometry" in window.form_fields
    assert "lab_notebook_ref" in window.form_fields
    assert "experiment.cooldown_id" in window.form_fields
    assert "instrument.address" in window.form_fields
    window.close()


def test_gui_recipe_sync_status_tracks_yaml_and_form_edits(app):
    window = MainWindow()

    window.editor_text.appendPlainText("# user note")
    assert "YAML edited" in window.recipe_sync_status.text()
    assert "Recipe Overview" in window.recipe_overview_text.toPlainText()
    assert "[ ] Check YAML" in window.workflow_text.toPlainText()

    field = window.form_fields["measurement_name"]
    field.setText(field.text() + "_edited")
    assert "Form edited" in window.recipe_sync_status.text()

    assert window.apply_form_to_editor()
    assert "YAML regenerated from form" in window.recipe_sync_status.text()
    window.close()


def test_gui_schema_form_supports_non_drain_methods(app):
    window = MainWindow()

    index = window.method_combo.findData("pulse_measurement")
    window.method_combo.setCurrentIndex(index)

    assert "pulse.count" in window.form_fields
    assert "source_instrument.address" in window.form_fields
    window.form_fields["measurement_name"].setText("gui_schema_pulse")
    window.form_fields["pulse.count"].setText("6")

    assert window.apply_form_to_editor()
    text = window.editor_text.toPlainText()

    assert "measurement_name: gui_schema_pulse" in text
    assert "count: 6" in text
    assert "Pulse measurement" in window.recipe_overview_text.toPlainText()
    window.close()


def test_gui_scheme_builder_generates_yaml_and_plan(app):
    window = MainWindow()

    window.scheme_name_edit.setText("gui_test_scheme")
    window.scheme_step_table.setItem(0, 1, QtWidgets.QTableWidgetItem("first_drain"))
    window.scheme_step_table.setItem(0, 6, QtWidgets.QTableWidgetItem("_small"))
    window.scheme_step_table.setItem(0, 7, QtWidgets.QTableWidgetItem("-0.05"))
    window.scheme_step_table.setItem(0, 8, QtWidgets.QTableWidgetItem("0.05"))
    window.scheme_step_table.setItem(0, 9, QtWidgets.QTableWidgetItem("5"))
    assert window.apply_scheme_form_to_yaml()

    text = window.scheme_editor_text.toPlainText()
    assert "name: gui_test_scheme" in text
    assert "label: first_drain" in text
    assert "measurement_suffix: _small" in text
    assert "start_v: -0.05" in text
    assert "points: 5" in text

    assert window.validate_scheme_yaml()
    window.show_scheme_plan()

    assert "Scheme plan" in window.scheme_plan_text.toPlainText()
    assert "first_drain" in window.scheme_plan_text.toPlainText()
    assert "sweep.start_v: -0.05" in window.scheme_plan_text.toPlainText()

    window.scheme_editor_text.setPlainText(
        "name: edited_scheme\n"
        "stop_on_error: true\n"
        "steps:\n"
        "  - type: batch\n"
        "    label: batch_step\n"
        "    batch: ../batches/drain_iv_1k_repeat_linear.yaml\n"
    )
    assert window.load_scheme_form_from_yaml()
    assert window.scheme_name_edit.text() == "edited_scheme"
    assert window.scheme_table_text(0, 0) == "batch"
    assert window.scheme_table_text(0, 1) == "batch_step"
    window.close()


def test_gui_workflow_guide_tracks_steps_and_recipe_resets(app):
    window = MainWindow()

    text = window.workflow_text.toPlainText()
    assert "PyTransportMeasure GUI Workflow" in text
    assert "[ ] Check YAML" in text
    assert "Recipe YAML is what Plan, Dry Run, Preflight, and Hardware Run use." in text

    window.mark_workflow("yaml_checked", True, "ok")
    window.mark_workflow("instrument_refreshed", True, "resources")
    window.mark_workflow("communication_tested", True, "idn ok")

    text = window.workflow_text.toPlainText()
    assert "[x] Check YAML" in text
    assert "[x] Refresh Instruments" in text
    assert "[x] Test Selected Address" in text

    window.reset_workflow_after_recipe_change("changed")
    text = window.workflow_text.toPlainText()
    assert "[ ] Check YAML" in text
    assert "[x] Refresh Instruments" in text
    assert "[x] Test Selected Address" in text
    assert "changed" in text
    window.close()


def test_gui_stop_run_button_requests_active_worker_stop(app):
    class FakeWorker:
        def __init__(self):
            self.stop_requested = False

        def isRunning(self):
            return True

        def request_stop(self):
            self.stop_requested = True

    window = MainWindow()
    worker = FakeWorker()
    window.worker = worker
    window.set_running(True)

    assert window.stop_run_button.isEnabled()

    window.request_stop_run()

    assert worker.stop_requested is True
    assert not window.stop_run_button.isEnabled()
    assert "Stop requested" in window.progress_text.toPlainText()
    window.close()


def test_gui_analysis_filters_and_run_table_columns(app):
    window = MainWindow()
    record = {
        "started_at": "2026-06-05T12:00:00",
        "measurement_type": "drain_iv",
        "measurement_name": "filtered_run",
        "completed": True,
        "points_written": 3,
        "sample_id": "sample-a",
        "device_id": "dev-1",
        "cooldown_id": "cd-1",
        "lab_notebook_ref": "ELN-1",
        "tags": ["keep"],
        "run_dir": "data/raw/filtered_run",
    }

    window.add_run_record_to_table(record)

    assert window.recent_table.columnCount() == 11
    assert window.recent_table.isSortingEnabled()
    assert window.recent_table.item(0, 3).text() == "Completed"
    assert window.recent_table.item(0, 7).text() == "cd-1"
    assert window.recent_table.item(0, 10).text() == "data/raw/filtered_run"
    window.recent_table.selectRow(0)
    assert str(window.selected_run_dir()) == "data\\raw\\filtered_run" or str(window.selected_run_dir()) == "data/raw/filtered_run"
    window.loaded_run_dir = window.selected_run_dir()
    window.highlight_loaded_run_row()
    assert window.recent_table.item(0, 0).background().color().name() == "#dbeafe"

    window.run_filter_sample.setText("sample-a")
    window.run_filter_device.setText("dev-1")
    window.run_filter_cooldown.setText("cd-1")
    window.run_filter_tag.setText("keep")
    window.run_filter_method.setText("drain_iv")
    window.run_filter_status.setCurrentText("Completed")
    assert window.run_status_filter_kwargs() == {"completed": True}

    window.clear_run_filters()
    assert window.run_filter_sample.text() == ""
    assert window.run_filter_status.currentText() == "Any status"
    window.close()


def test_same_path_handles_equivalent_relative_paths():
    assert same_path(Path("data/raw"), Path("data") / "raw")


def test_run_status_text_prefers_interrupted_and_errors():
    assert run_status_text({"completed": True}) == "Completed"
    assert run_status_text({"completed": False}) == "Incomplete"
    assert run_status_text({"error_type": "SafetyLimitError"}) == "Failed: SafetyLimitError"
    assert run_status_text({"interrupted": True, "error_type": "KeyboardInterrupt"}) == "Interrupted"


def test_qt_plot_widget_stores_saved_and_live_points(app):
    window = MainWindow()

    window.saved_plot_canvas.plot_points([(0.0, 0.0), (1.0, 1e-6)], "saved")
    window.live_plot_canvas.reset_live("live")
    point = type("Point", (), {"index": 0, "voltage_v": 0.1, "current_a": 1e-7})()
    window.append_live_point(point, 3)

    assert window.saved_plot_canvas.title == "saved"
    assert window.saved_plot_canvas.points == [(0.0, 0.0), (1.0, 1e-6)]
    assert window.live_plot_canvas.points == [(0.1, 1e-7)]
    assert padded_range(1.0, 1.0) == (0.95, 1.05)
    window.close()


def test_log_text_sticks_to_bottom_only_when_already_at_bottom(app):
    text_edit = QtWidgets.QPlainTextEdit()
    text_edit.resize(320, 120)
    text_edit.show()

    update_plain_text_preserving_scroll(text_edit, "\n".join(f"line {index}" for index in range(60)))
    bottom_after_first_write = text_edit.verticalScrollBar().value()
    assert bottom_after_first_write == text_edit.verticalScrollBar().maximum()

    text_edit.verticalScrollBar().setValue(10)
    update_plain_text_preserving_scroll(text_edit, "\n".join(f"line {index}" for index in range(80)))

    assert text_edit.verticalScrollBar().value() == 10

    text_edit.verticalScrollBar().setValue(text_edit.verticalScrollBar().maximum())
    update_plain_text_preserving_scroll(text_edit, "\n".join(f"line {index}" for index in range(100)))

    assert text_edit.verticalScrollBar().value() == text_edit.verticalScrollBar().maximum()
    text_edit.close()
