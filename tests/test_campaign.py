import csv
import json
import zipfile

import pytest

from pytransport.campaign import (
    CampaignFilters,
    build_campaign_manifest,
    campaign_stats_rows,
    create_campaign,
    export_campaign_bundle,
    filter_runs,
    write_campaign_resistance_histogram_svg,
    write_campaign_stats_csv,
)


def write_run(
    run_dir,
    name,
    completed=True,
    quality_status="PASS",
    sample_id="sample",
    device_id="device",
    tags=None,
    resistance_ohm=1000,
    error_type=None,
):
    tags = ["tag1", "tag2"] if tags is None else tags
    run_dir.mkdir(parents=True)
    with (run_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "measurement_name": name,
                "started_at": "start",
                "finished_at": "finish",
                "completed": completed,
                "interrupted": False,
                "error_type": error_type,
                "error_message": None,
                "points_written": 3,
                "recipe_path": "recipe.yaml",
                "quality": {"status": quality_status, "results": []},
                "recipe": {
                    "experiment": {
                        "sample_id": sample_id,
                        "device_id": device_id,
                        "operator": "operator",
                        "tags": tags,
                    }
                },
            },
            handle,
        )
    with (run_dir / "points.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["index", "voltage_v", "current_a", "elapsed_s", "resistance_ohm", "compliance_hit"],
        )
        writer.writeheader()
        for index, voltage in enumerate([-0.1, 0.0, 0.1]):
            current = 0.0 if voltage == 0 else voltage / resistance_ohm
            writer.writerow(
                {
                    "index": index,
                    "voltage_v": voltage,
                    "current_a": current,
                    "elapsed_s": index * 0.1,
                    "resistance_ohm": "" if current == 0 else voltage / current,
                    "compliance_hit": False,
                }
            )
    (run_dir / "recipe_snapshot.yaml").write_text("measurement_name: test\n", encoding="utf-8")
    (run_dir / "safety_snapshot.yaml").write_text("name: test_safety\n", encoding="utf-8")
    (run_dir / "iv_plot.svg").write_text("<svg></svg>\n", encoding="utf-8")
    (run_dir / "report.md").write_text("# report\n", encoding="utf-8")


def write_single_gate_run(run_dir, name="single_gate", completed=True):
    run_dir.mkdir(parents=True)
    with (run_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "measurement_name": name,
                "measurement_type": "single_gate_sweep",
                "started_at": "start",
                "finished_at": "finish",
                "completed": completed,
                "interrupted": False,
                "error_type": None,
                "error_message": None,
                "points_written": 6,
                "recipe_path": "single_gate.yaml",
                "recipe": {
                    "experiment": {
                        "sample_id": "sample",
                        "device_id": "fet",
                        "operator": "operator",
                        "tags": ["single-gate"],
                    }
                },
            },
            handle,
        )
    with (run_dir / "points.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "index",
                "gate_index",
                "drain_index",
                "gate_voltage_v",
                "drain_voltage_v",
                "drain_current_a",
                "gate_current_a",
                "elapsed_s",
                "drain_resistance_ohm",
                "drain_compliance_hit",
                "gate_compliance_hit",
            ],
        )
        writer.writeheader()
        index = 0
        for gate_index, gate_voltage in enumerate([-0.5, 0.5]):
            for drain_index, drain_voltage in enumerate([-0.1, 0.0, 0.1]):
                writer.writerow(
                    {
                        "index": index,
                        "gate_index": gate_index,
                        "drain_index": drain_index,
                        "gate_voltage_v": gate_voltage,
                        "drain_voltage_v": drain_voltage,
                        "drain_current_a": drain_voltage / 1_000_000,
                        "gate_current_a": gate_voltage / 1_000_000_000,
                        "elapsed_s": index * 0.1,
                        "drain_resistance_ohm": "" if drain_voltage == 0 else 1_000_000,
                        "drain_compliance_hit": False,
                        "gate_compliance_hit": False,
                    }
                )
                index += 1
    (run_dir / "recipe_snapshot.yaml").write_text("measurement_name: single_gate\n", encoding="utf-8")
    (run_dir / "safety_snapshot.yaml").write_text("name: safe\n", encoding="utf-8")
    (run_dir / "single_gate_heatmap.svg").write_text("<svg></svg>\n", encoding="utf-8")
    (run_dir / "single_gate_stats.csv").write_text("gate_index\n0\n", encoding="utf-8")
    (run_dir / "single_gate_report.md").write_text("# single gate report\n", encoding="utf-8")


def write_batch(batch_dir):
    batch_dir.mkdir(parents=True)
    (batch_dir / "batch_summary.json").write_text(
        json.dumps(
            {
                "batch_name": "batch",
                "batch_path": "batch.yaml",
                "started_at": "start",
                "finished_at": "finish",
                "dry_run": True,
                "completed": True,
                "quality": {"status": "PASS"},
                "runs": [{"completed": True}, {"completed": True}],
            }
        ),
        encoding="utf-8",
    )


def write_scheme(scheme_dir):
    scheme_dir.mkdir(parents=True)
    (scheme_dir / "scheme_summary.json").write_text(
        json.dumps(
            {
                "scheme_name": "scheme",
                "scheme_path": "scheme.yaml",
                "started_at": "start",
                "finished_at": "finish",
                "dry_run": True,
                "completed": True,
                "quality": {"status": "PASS"},
                "steps": [{"completed": True}],
            }
        ),
        encoding="utf-8",
    )


def test_build_campaign_manifest_collects_runs_batches_and_schemes(tmp_path):
    raw_dir = tmp_path / "raw"
    batch_dir = tmp_path / "batches"
    scheme_dir = tmp_path / "schemes"
    write_run(raw_dir / "run1", "run1")
    write_batch(batch_dir / "batch1")
    write_scheme(scheme_dir / "scheme1")

    manifest = build_campaign_manifest("test", raw_dir, batch_dir, scheme_dir)

    assert manifest["campaign_name"] == "test"
    assert manifest["counts"]["runs"] == 1
    assert manifest["counts"]["completed_runs"] == 1
    assert manifest["counts"]["batches"] == 1
    assert manifest["counts"]["schemes"] == 1
    assert manifest["runs"][0]["fitted_resistance_ohm"] == pytest.approx(1000)
    assert manifest["runs"][0]["tags"] == ["tag1", "tag2"]


def test_campaign_manifest_collects_single_gate_runs(tmp_path):
    raw_dir = tmp_path / "raw"
    write_run(raw_dir / "iv", "iv")
    write_single_gate_run(raw_dir / "gate", "gate")

    manifest = build_campaign_manifest("mixed", raw_dir, tmp_path / "batches", tmp_path / "schemes")
    gate_run = next(run for run in manifest["runs"] if run["measurement_type"] == "single_gate_sweep")

    assert manifest["counts"]["runs"] == 2
    assert manifest["counts"]["run_types"]["drain_iv"] == 1
    assert manifest["counts"]["run_types"]["single_gate_sweep"] == 1
    assert gate_run["points"] == 6
    assert gate_run["gate_points"] == 2
    assert gate_run["drain_points"] == 3
    assert gate_run["gate_leakage_abs_max_a"] == pytest.approx(5e-10)
    assert gate_run.get("summary_error") is None


def test_single_gate_only_campaign_analytics_skips_histogram(tmp_path):
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "campaigns"
    write_single_gate_run(raw_dir / "gate", "gate")

    paths = create_campaign("single_gate_only", raw_dir, tmp_path / "batches", tmp_path / "schemes", output_dir, analytics=True)

    assert paths.stats_csv_path is not None and paths.stats_csv_path.exists()
    assert paths.histogram_path is None
    assert paths.report_path.exists()


def test_create_campaign_writes_manifest_csv_and_report(tmp_path):
    raw_dir = tmp_path / "raw"
    batch_dir = tmp_path / "batches"
    scheme_dir = tmp_path / "schemes"
    output_dir = tmp_path / "campaigns"
    write_run(raw_dir / "run1", "run1")
    write_batch(batch_dir / "batch1")
    write_scheme(scheme_dir / "scheme1")

    paths = create_campaign("test", raw_dir, batch_dir, scheme_dir, output_dir, analytics=True)

    assert paths.manifest_path.exists()
    assert paths.runs_csv_path.exists()
    assert paths.report_path.exists()
    assert paths.stats_csv_path is not None and paths.stats_csv_path.exists()
    assert paths.histogram_path is not None and paths.histogram_path.exists()
    assert "# test" in paths.report_path.read_text(encoding="utf-8")
    assert "## Resistance Stats" in paths.report_path.read_text(encoding="utf-8")
    assert "run1" in paths.runs_csv_path.read_text(encoding="utf-8")


def test_campaign_filters_runs(tmp_path):
    raw_dir = tmp_path / "raw"
    write_run(raw_dir / "pass_1k", "pass_1k", sample_id="sample-a", tags=["keep"], resistance_ohm=1000)
    write_run(raw_dir / "fail_10k", "fail_10k", sample_id="sample-a", tags=["keep"], quality_status="FAIL", resistance_ohm=10000)
    write_run(raw_dir / "other", "other", sample_id="sample-b", tags=["drop"], resistance_ohm=1000)

    manifest = build_campaign_manifest(
        "filtered",
        raw_dir,
        tmp_path / "batches",
        tmp_path / "schemes",
        CampaignFilters(
            sample_id="sample-a",
            tag="keep",
            quality_status="PASS",
            min_resistance_ohm=900,
            max_resistance_ohm=1100,
        ),
    )

    assert manifest["source_counts"]["runs"] == 3
    assert manifest["counts"]["runs"] == 1
    assert manifest["runs"][0]["measurement_name"] == "pass_1k"
    assert manifest["filters"]["sample_id"] == "sample-a"


def test_filter_runs_failed_only():
    runs = [
        {"measurement_name": "ok", "error_type": None},
        {"measurement_name": "bad", "error_type": "RuntimeError"},
    ]

    assert [run["measurement_name"] for run in filter_runs(runs, CampaignFilters(failed_only=True))] == ["bad"]


def test_campaign_analytics_exports(tmp_path):
    raw_dir = tmp_path / "raw"
    write_run(raw_dir / "run1", "iv", sample_id="sample", device_id="dev", resistance_ohm=1000)
    write_run(raw_dir / "run2", "iv", sample_id="sample", device_id="dev", resistance_ohm=1010)
    manifest = build_campaign_manifest("analytics", raw_dir, tmp_path / "batches", tmp_path / "schemes")

    rows = campaign_stats_rows(manifest)
    stats_path = write_campaign_stats_csv(manifest, tmp_path / "stats.csv")
    histogram_path = write_campaign_resistance_histogram_svg(manifest, tmp_path / "hist.svg", bins=4)

    assert len(rows) == 1
    assert rows[0]["runs"] == 2
    assert rows[0]["mean_fitted_resistance_ohm"] == pytest.approx(1005)
    assert stats_path.exists()
    assert "mean_fitted_resistance_ohm" in stats_path.read_text(encoding="utf-8")
    assert histogram_path.exists()
    assert "fitted resistance histogram" in histogram_path.read_text(encoding="utf-8")


def test_export_campaign_bundle_copies_core_files_and_zips(tmp_path):
    raw_dir = tmp_path / "raw"
    batch_dir = tmp_path / "batches"
    scheme_dir = tmp_path / "schemes"
    output_dir = tmp_path / "campaigns"
    export_dir = tmp_path / "exports"
    write_run(raw_dir / "run1", "run1")
    write_single_gate_run(raw_dir / "gate1", "gate1")
    write_batch(batch_dir / "batch1")
    write_scheme(scheme_dir / "scheme1")
    paths = create_campaign("bundle", raw_dir, batch_dir, scheme_dir, output_dir, analytics=True)

    bundle = export_campaign_bundle(paths.campaign_dir, output_dir=export_dir)
    bundle_manifest = json.loads(bundle.bundle_manifest_path.read_text(encoding="utf-8"))

    assert bundle.bundle_dir.exists()
    assert bundle.bundle_manifest_path.exists()
    assert bundle.zip_path.exists()
    assert (bundle.bundle_dir / "campaign" / "campaign_manifest.json").exists()
    assert (bundle.bundle_dir / "campaign" / "campaign_stats.csv").exists()
    assert list((bundle.bundle_dir / "runs").glob("*/metadata.json"))
    assert list((bundle.bundle_dir / "runs").glob("*/points.csv"))
    assert list((bundle.bundle_dir / "runs").glob("*/single_gate_heatmap.svg"))
    assert list((bundle.bundle_dir / "runs").glob("*/single_gate_stats.csv"))
    assert list((bundle.bundle_dir / "runs").glob("*/single_gate_report.md"))
    assert list((bundle.bundle_dir / "summaries" / "batches").glob("*batch_summary.json"))
    assert bundle_manifest["include_points"] is True
    with zipfile.ZipFile(bundle.zip_path) as archive:
        names = set(archive.namelist())
    assert "campaign/campaign_manifest.json" in names
    assert "bundle_manifest.json" in names


def test_export_campaign_bundle_can_skip_large_files(tmp_path):
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "campaigns"
    export_dir = tmp_path / "exports"
    write_run(raw_dir / "run1", "run1")
    paths = create_campaign("small_bundle", raw_dir, tmp_path / "batches", tmp_path / "schemes", output_dir)

    bundle = export_campaign_bundle(paths.manifest_path, output_dir=export_dir, include_points=False, include_plots=False)

    assert list((bundle.bundle_dir / "runs").glob("*/metadata.json"))
    assert not list((bundle.bundle_dir / "runs").glob("*/points.csv"))
    assert not list((bundle.bundle_dir / "runs").glob("*/iv_plot.svg"))
