from pytransport.output_state import (
    all_outputs_off_after_run,
    any_output_enabled,
    command_voltage_with_state,
    initialize_output_state,
    output_off_with_state,
    output_on_with_state,
    zero_before_off_with_state,
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


class BrokenZero(ToggleOutput):
    def set_voltage(self, voltage_v):
        raise RuntimeError("zero failed")


class BrokenCommand(ToggleOutput):
    def set_voltage(self, voltage_v):
        raise RuntimeError("command failed")


class VoltageOutput(ToggleOutput):
    def __init__(self):
        super().__init__()
        self.voltage_v = 1.0

    def set_voltage(self, voltage_v):
        self.voltage_v = voltage_v


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


def test_zero_before_off_state_tracks_success_and_error():
    metadata = {}
    initialize_output_state(metadata, ["source", "gate"])
    source = VoltageOutput()

    zero_before_off_with_state("source", source, metadata)
    zero_before_off_with_state("gate", BrokenZero(), metadata)

    assert source.voltage_v == 0.0
    assert metadata["output_state"]["source"]["zero_before_off_succeeded"] is True
    assert metadata["output_state"]["source"]["zero_before_off_target_v"] == 0.0
    assert metadata["output_state"]["gate"]["zero_before_off_succeeded"] is False
    assert "RuntimeError" in metadata["output_state"]["gate"]["zero_before_off_error"]


def test_voltage_command_state_tracks_last_setpoint_and_error():
    metadata = {}
    initialize_output_state(metadata, ["source", "gate"])
    source = VoltageOutput()

    command_voltage_with_state("source", source, metadata, 0.25)
    command_voltage_with_state("source", source, metadata, -0.1)

    assert metadata["output_state"]["source"]["voltage_command_count"] == 2
    assert metadata["output_state"]["source"]["last_commanded_voltage_v"] == -0.1
    assert metadata["output_state"]["source"]["last_voltage_command_error"] is None

    try:
        command_voltage_with_state("gate", BrokenCommand(), metadata, 0.5)
    except RuntimeError:
        pass

    assert "RuntimeError" in metadata["output_state"]["gate"]["last_voltage_command_error"]
