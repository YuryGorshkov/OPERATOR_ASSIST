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


def runtime_layout(base_dir, *, bundle_dir=None, frozen=None):
    base_path = Path(base_dir).resolve()
    bundle_path = Path(bundle_dir).resolve() if bundle_dir is not None else base_path
    packaged = is_frozen() if frozen is None else bool(frozen)

    if packaged:
        data_dir = base_path / "data"
        config_dir = base_path / "config"
        support_dir = base_path / "support"
        assets_dir = bundle_path / "assets"
    else:
        data_dir = base_path
        config_dir = base_path
        support_dir = base_path
        assets_dir = base_path / "assets"

    return {
        "packaged": packaged,
        "base_dir": base_path,
        "bundle_dir": bundle_path,
        "data_dir": data_dir,
        "config_dir": config_dir,
        "support_dir": support_dir,
        "assets_dir": assets_dir,
        "models_dir": data_dir / "models",
        "logs_dir": data_dir / "logs",
        "transcripts_dir": data_dir / "transcripts",
        "scripts_dir": support_dir / "scripts",
        "settings_path": config_dir / "operator_assist_settings.json",
        "prompt_template_path": config_dir / "chatgpt_prompt_template.txt",
        "technical_terms_path": config_dir / "technical_terms.json",
        "bridge_script_path": support_dir / "scripts" / "paste_to_chat_window.vbs",
    }
