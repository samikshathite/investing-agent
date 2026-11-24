from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None):
    path = Path(path) if path else ROOT / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def data_path(cfg, key):
    p = Path(cfg["data"][key])
    return p if p.is_absolute() else ROOT / p
