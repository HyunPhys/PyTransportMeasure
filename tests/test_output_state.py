from pytransport.output_state import (
    all_outputs_off_after_run,
    any_output_enabled,
    initialize_output_state,
    output_off_with_state,
    output_on_with_state,
)


class ToggleOutput:
    def __init__(self):
        self.enabled = False

    def output_on(self):
        self.enabled = True

    def output_off(self):
        self.enabled = False


class BrokenOff(ToggleOutput):
    def output_off(self):
        raise RuntimeError("off failed")


def test_output_state_tracks_on_off_success():
    metadata = {}
    smu = ToggleOutput()
    initialize_output_state(metadata, ["source"])

    output_on_with_state("source", smu, metadata)
    assert metadata["output_state"]["source"]["enabled"] is True
    assert any_output_enabled(metadata) is True

    output_off_with_state("source", smu, metadata)
    assert metadata["output_state"]["source"]["enabled"] is False
    assert metadata["output_state"]["source"]["off_after_run"] is True
    assert all_outputs_off_after_run(metadata, ["source"]) is True


def test_output_state_records_off_error_without_hiding_other_outputs():
    metadata = {}
    initialize_output_state(metadata, ["gate1", "gate2"])
    output_on_with_state("gate1", ToggleOutput(), metadata)
    output_on_with_state("gate2", ToggleOutput(), metadata)

    output_off_with_state("gate1", BrokenOff(), metadata)
    output_off_with_state("gate2", ToggleOutput(), metadata)

    assert metadata["output_state"]["gate1"]["off_after_run"] is False
    assert "RuntimeError" in metadata["output_state"]["gate1"]["output_off_error"]
    assert metadata["output_state"]["gate2"]["off_after_run"] is True
    assert all_outputs_off_after_run(metadata, ["gate1", "gate2"]) is False
