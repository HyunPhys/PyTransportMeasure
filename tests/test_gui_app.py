import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from pytransport.gui_app import MainWindow, padded_range, update_plain_text_preserving_scroll


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
    assert "Doctor" not in tab_labels
    assert window.doctor_button.text() == "Full Doctor"
    assert window.refresh_instruments_button.text() == "Refresh Instruments"
    assert window.test_connection_button.text() == "Test Selected Address"
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
    window.close()


def test_gui_recipe_sync_status_tracks_yaml_and_form_edits(app):
    window = MainWindow()

    window.editor_text.appendPlainText("# user note")
    assert "YAML edited" in window.recipe_sync_status.text()
    assert "[ ] Check YAML" in window.workflow_text.toPlainText()

    field = window.form_fields["measurement_name"]
    field.setText(field.text() + "_edited")
    assert "Form edited" in window.recipe_sync_status.text()

    assert window.apply_form_to_editor()
    assert "YAML regenerated from form" in window.recipe_sync_status.text()
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
