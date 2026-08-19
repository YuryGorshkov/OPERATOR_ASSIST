"""Compatibility shim for legacy imports.

The canonical base runtime now lives in operator_assist_runtime/base_runtime.py.
This file is intentionally kept as a fallback entry point so older wrappers or
local scripts do not break during the repository cleanup.
"""

from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
root_text = str(ROOT_DIR)
if root_text not in sys.path:
    sys.path.insert(0, root_text)

from operator_assist_runtime.base_runtime import *  # noqa: F401,F403
