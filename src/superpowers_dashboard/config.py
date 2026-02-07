"""Configuration loading for superpowers-dashboard."""
import tomllib
from pathlib import Path

DEFAULT_PRICING = {
    "claude-opus-4-6": {
        "input": 5.0,
        "output": 25.0,
        "cache_read": 0.5,
        "cache_write": 6.25,
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.3,
        "cache_write": 3.75,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.0,
        "output": 5.0,
        "cache_read": 0.1,
        "cache_write": 1.25,
    },
}

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "superpowers-dashboard" / "config.toml"


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load config from TOML file, falling back to defaults."""
    config = {"pricing": dict(DEFAULT_PRICING)}

    if config_path.exists():
        with open(config_path, "rb") as f:
            user_config = tomllib.load(f)
        if "pricing" in user_config:
            config["pricing"].update(user_config["pricing"])

    return config
