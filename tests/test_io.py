from pytransport.io import RunWriter, unique_run_dir


def test_unique_run_dir_adds_suffix_when_base_exists(tmp_path):
    (tmp_path / "run").mkdir()

    assert unique_run_dir(tmp_path, "run") == tmp_path / "run_02"


def test_run_writer_avoids_same_second_name_collision(tmp_path):
    first = RunWriter(tmp_path, "same_name")
    try:
        second = RunWriter(tmp_path, "same_name")
        try:
            assert first.run_dir != second.run_dir
            assert second.run_dir.name.endswith("_02")
        finally:
            second.close()
    finally:
        first.close()
