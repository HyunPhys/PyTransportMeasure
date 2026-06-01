"""VISA utility functions."""

from __future__ import annotations


def list_resources() -> tuple[str, ...]:
    import pyvisa

    rm = pyvisa.ResourceManager()
    try:
        return tuple(str(item) for item in rm.list_resources())
    finally:
        rm.close()
