from pytransport.gui_session import GuiSessionLogger


def test_gui_session_logger_writes_timestamped_lines(tmp_path):
    logger = GuiSessionLogger.create(tmp_path / "logs")

    logger.write("Doctor starting\nDoctor finished")

    text = logger.read_text()
    assert logger.path.exists()
    assert "GUI session started" in text
    assert "Doctor starting" in text
    assert "Doctor finished" in text
    assert " | " in text
