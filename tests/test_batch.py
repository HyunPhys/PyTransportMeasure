import json

from pytransport.batch import (
    create_batch_summary,
    finish_batch_summary,
    format_batch_plan,
    load_batch,
    resolve_batch_entries,
    safe_name,
)


def test_load_and_format_1k_smoke_batch():
    batch_path = "configs/batches/drain_iv_1k_smoke_suite.yaml"
    batch = load_batch(batch_path)
    entries = resolve_batch_entries(batch, batch_path)
    text = format_batch_plan(batch, batch_path)

    assert batch.name == "drain_iv_1k_smoke_suite"
    assert len(entries) == 3
    assert entries[0].label == "linear"
    assert entries[0].recipe_path.name == "drain_iv_1k_resistor.yaml"
    assert "Batch plan" in text
    assert "Enabled recipes: 3" in text
    assert "=== Recipe 1/3: linear ===" in text
    assert "=== Recipe 3/3: multi_segment ===" in text


def test_repeat_batch_expands_entries():
    batch_path = "configs/batches/drain_iv_1k_repeat_linear.yaml"
    batch = load_batch(batch_path)
    entries = resolve_batch_entries(batch, batch_path)
    text = format_batch_plan(batch, batch_path)

    assert len(entries) == 3
    assert entries[0].label == "linear_repeat_rep01"
    assert entries[1].repeat_index == 2
    assert entries[2].repeat_count == 3
    assert entries[0].interval_s == 0.5
    assert batch.checks is not None
    assert batch.checks.max_relative_std_percent == 2.0
    assert "Recipe entries: 1" in text
    assert "=== Recipe 3/3: linear_repeat_rep03 ===" in text


def test_batch_summary_records_completion(tmp_path):
    batch = load_batch("configs/batches/drain_iv_1k_smoke_suite.yaml")
    batch_dir, summary = create_batch_summary(batch, "batch.yaml", dry_run=True, output_dir=tmp_path)
    summary["runs"].append({"completed": True})

    summary_path = finish_batch_summary(batch_dir, summary)
    saved = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary_path.name == "batch_summary.json"
    assert saved["batch_name"] == "drain_iv_1k_smoke_suite"
    assert saved["dry_run"] is True
    assert saved["completed"] is True


def test_safe_name_removes_path_hostile_characters():
    assert safe_name("bad/name:with spaces") == "bad_name_with_spaces"
