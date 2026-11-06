"""Configuration loader supporting environment variable substitution and YAML parsing."""

import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict

_CONFIG_CACHE: Dict[str, Any] = {}

ENV_PATTERN = re.compile(r"\$\{([^}^{]+)\}")


def _substitute_env_vars(val: Any) -> Any:
    """Recursively replaces ${VAR:default} or ${VAR} with environment variable values."""
    if isinstance(val, str):
        match = ENV_PATTERN.fullmatch(val.strip())
        if match:
            expression = match.group(1)
            if ":" in expression:
                var_name, default_val = expression.split(":", 1)
                return os.environ.get(var_name, default_val)
            return os.environ.get(expression, "")
        # Partial inline match
        def _repl(m):
            expr = m.group(1)
            if ":" in expr:
                k, d = expr.split(":", 1)
                return os.environ.get(k, d)
            return os.environ.get(expr, "")
        return ENV_PATTERN.sub(_repl, val)
    elif isinstance(val, dict):
        return {k: _substitute_env_vars(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_substitute_env_vars(item) for item in val]
    return val


def load_config(config_path: str = None) -> Dict[str, Any]:
    """Loads configuration from YAML file with environment variable expansion."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE:
        return _CONFIG_CACHE

    if config_path is None:
        root_dir = Path(__file__).resolve().parent.parent
        active_config = root_dir / "config" / "settings.yaml"
        example_config = root_dir / "config" / "settings.example.yaml"
        config_path = active_config if active_config.exists() else example_config

    with open(config_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f) or {}

    _CONFIG_CACHE = _substitute_env_vars(raw_data)
    return _CONFIG_CACHE


get_config = load_config

