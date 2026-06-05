import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from pytransport.gui_app import MainWindow, update_plain_text_preserving_scroll


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
    assert window.fake_content.isHidden()

    window.fake_box.setChecked(True)

    assert not window.fake_content.isHidden()
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
