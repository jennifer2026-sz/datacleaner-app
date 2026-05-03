"""Configuration management for DataCleaner CLI."""

import os
import yaml
from pathlib import Path


DEFAULT_CONFIG = {
    "ollama": {
        "model": "qwen3.5:9b",
        "host": "http://localhost:11434",
        "timeout": 120,
    },
    "scanning": {
        "chunk_size": 2000,
        "chunk_overlap": 200,
        "confidence_threshold": 0.7,
        "max_file_size_mb": 100,
    },
    "redaction": {
        "style": "block",          # "block" | "placeholder" | "mask"
        "placeholder_text": "[REDACTED]",
        "audit_log": True,
    },
    "license": {
        "key": "",
        "verified": False,
    },
    "output": {
        "format": "txt",           # "txt" | "json" | "csv"
        "audit_dir": "~/.datacleaner/audit/",
    },
}

CONFIG_DIR = Path.home() / ".datacleaner"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def load_config() -> dict:
    """Load configuration, merging user overrides with defaults."""
    config = DEFAULT_CONFIG.copy()

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                user_config = yaml.safe_load(f) or {}
            _deep_merge(config, user_config)
        except Exception:
            pass

    # Env var overrides
    if os.getenv("DC_OLLAMA_MODEL"):
        config["ollama"]["model"] = os.getenv("DC_OLLAMA_MODEL")
    if os.getenv("DC_LICENSE_KEY"):
        config["license"]["key"] = os.getenv("DC_LICENSE_KEY")

    return config


def save_config(config: dict) -> None:
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base dict in-place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
