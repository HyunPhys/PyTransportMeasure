import json

from pytransport.run_index import (
    append_run_index,
    build_index_record,
    filter_run_index,
    format_run_index,
    read_run_index,
    rebuild_run_index,
)


def make_metadata(run_dir="data/raw/run1"):
    return {
        "started_at": "2026-05-26T15:00:00",
        "finished_at": "2026-05-26T15:00:02",
        "measurement_name": "test",
        "completed": True,
        "interrupted": False,
        "error_type": None,
        "points_written": 21,
        "run_dir": run_dir,
        "metadata_path": f"{run_dir}/metadata.json",
        "csv_path": f"{run_dir}/points.csv",
        "plot_path": f"{run_dir}/iv_plot.svg",
        "recipe_path": "configs/recipes/drain_iv_1k_resistor.yaml",
        "recipe": {
            "experiment": {
                "sample_id": "sample",
                "device_id": "device",
                "cooldown_id": "cooldown-1",
                "contact_geometry": "hall bar",
                "lab_notebook_ref": "ELN-1",
                "tags": ["smoke-test"],
            }
        },
    }


def make_record(**overrides):
    record = build_index_record(make_metadata())
    record.update(overrides)
    return record


def test_build_index_record_extracts_search_fields():
    record = build_index_record(make_metadata())

    assert record["sample_id"] == "sample"
    assert record["device_id"] == "device"
    assert record["cooldown_id"] == "cooldown-1"
    assert record["contact_geometry"] == "hall bar"
    assert record["lab_notebook_ref"] == "ELN-1"
    assert record["tags"] == ["smoke-test"]
    assert record["measurement_type"] == "drain_iv"


def test_build_index_record_keeps_single_gate_artifacts():
    record = build_index_record(
        make_metadata()
        | {
            "measurement_type": "single_gate_sweep",
            "single_gate_heatmap_path": "run/single_gate_heatmap.svg",
            "single_gate_report_path": "run/single_gate_report.md",
            "single_gate_stats_path": "run/single_gate_stats.csv",
        }
    )

    assert record["measurement_type"] == "single_gate_sweep"
    assert record["single_gate_heatmap_path"].endswith("single_gate_heatmap.svg")


def test_build_index_record_keeps_dual_gate_artifacts():
    record = build_index_record(
        make_metadata()
        | {
            "measurement_type": "dual_gate_sweep",
            "dual_gate_heatmap_path": "run/dual_gate_heatmap.svg",
            "dual_gate_report_path": "run/dual_gate_report.md",
            "dual_gate_stats_path": "run/dual_gate_stats.csv",
        }
    )

    assert record["measurement_type"] == "dual_gate_sweep"
    assert record["dual_gate_heatmap_path"].endswith("dual_gate_heatmap.svg")


def test_build_index_record_keeps_dual_gate_lockin_artifacts():
    record = build_index_record(
        make_metadata()
        | {
            "measurement_type": "dual_gate_lockin_sweep",
            "dual_gate_lockin_heatmap_path": "run/dual_gate_lockin_heatmap.svg",
            "dual_gate_lockin_report_path": "run/dual_gate_lockin_report.md",
            "dual_gate_lockin_stats_path": "run/dual_gate_lockin_stats.csv",
        }
    )

    assert record["measurement_type"] == "dual_gate_lockin_sweep"
    assert record["dual_gate_lockin_heatmap_path"].endswith("dual_gate_lockin_heatmap.svg")


def test_append_and_read_run_index(tmp_path):
    index_path = tmp_path / "run_index.jsonl"
    append_run_index(make_metadata("run-a"), index_path)
    append_run_index(make_metadata("run-b"), index_path)

    records = read_run_index(index_path)

    assert [record["run_dir"] for record in records] == ["run-a", "run-b"]
    text = format_run_index(records, limit=1)
    assert "run-b" in text
    assert "run-a" not in text
    assert "cooldown=cooldown-1" in text
    assert "tags=smoke-test" in text


def test_read_run_index_accepts_utf8_bom(tmp_path):
    index_path = tmp_path / "run_index.jsonl"
    index_path.write_text(
        '\ufeff{"measurement_name": "bom_run", "measurement_type": "drain_iv"}\n',
        encoding="utf-8",
    )

    records = read_run_index(index_path)

    assert records[0]["measurement_name"] == "bom_run"


def test_rebuild_run_index_from_metadata_files(tmp_path):
    raw_dir = tmp_path / "raw"
    run_b = raw_dir / "run-b"
    run_a = raw_dir / "run-a"
    run_b.mkdir(parents=True)
    run_a.mkdir(parents=True)
    (run_b / "metadata.json").write_text(
        json.dumps(make_metadata("run-b") | {"started_at": "2026-05-26T15:00:02"}),
        encoding="utf-8",
    )
    (run_a / "metadata.json").write_text(
        json.dumps(make_metadata("run-a") | {"started_at": "2026-05-26T15:00:01"}),
        encoding="utf-8",
    )

    index_path, count = rebuild_run_index(raw_dir, tmp_path / "run_index.jsonl")

    assert count == 2
    assert [record["run_dir"] for record in read_run_index(index_path)] == ["run-a", "run-b"]


def test_filter_run_index_by_sample_device_tag_and_state():
    records = [
        make_record(run_dir="a", sample_id="sample-a", device_id="device-a", cooldown_id="cd-a", tags=["x"], completed=True),
        make_record(run_dir="b", sample_id="sample-b", device_id="device-b", cooldown_id="cd-b", tags=["y"], completed=False, error_type="SafetyLimitError"),
        make_record(run_dir="c", sample_id="sample-a", device_id="device-c", cooldown_id="cd-a", tags=["x", "z"], completed=False, interrupted=True),
    ]

    assert [record["run_dir"] for record in filter_run_index(records, sample_id="sample-a")] == ["a", "c"]
    assert [record["run_dir"] for record in filter_run_index(records, device_id="device-b")] == ["b"]
    assert [record["run_dir"] for record in filter_run_index(records, cooldown_id="cd-a")] == ["a", "c"]
    assert [record["run_dir"] for record in filter_run_index(records, tag="z")] == ["c"]
    assert [record["run_dir"] for record in filter_run_index(records, measurement_type="drain_iv")] == ["a", "b", "c"]
    assert [record["run_dir"] for record in filter_run_index(records, completed=True)] == ["a"]
    assert [record["run_dir"] for record in filter_run_index(records, failed=True)] == ["b"]
    assert [record["run_dir"] for record in filter_run_index(records, interrupted=True)] == ["c"]


def test_filter_run_index_by_measurement_type():
    records = [
        make_record(run_dir="iv", measurement_type="drain_iv"),
        make_record(run_dir="gate", measurement_type="single_gate_sweep"),
    ]

    assert [record["run_dir"] for record in filter_run_index(records, measurement_type="single_gate_sweep")] == ["gate"]
    assert "type=single_gate_sweep" in format_run_index(records, limit=1)
