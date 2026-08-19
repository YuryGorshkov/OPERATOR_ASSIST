"""Runtime path helpers for source and frozen OPERATOR_ASSIST builds."""

from pathlib import Path
import sys


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def bundle_root(anchor_file):
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
        return Path(sys.executable).resolve().parent
    return Path(anchor_file).resolve().parent


def application_root(anchor_file, levels_up=0):
    if is_frozen():
        return Path(sys.executable).resolve().parent

    anchor_path = Path(anchor_file).resolve()
    if levels_up < 0:
        raise ValueError("levels_up must be non-negative")
    return anchor_path.parents[levels_up]
