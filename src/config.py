"""Chargement de config.yaml + overrides par variables d'environnement."""
import os

import yaml


def load_dotenv():
    """Charge .env s'il existe (dev local uniquement ; jamais présent dans l'image).

    Ne remplace jamais une variable déjà présente dans l'environnement.
    """
    if not os.path.exists(".env"):
        return
    with open(".env", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if value.strip():
                os.environ.setdefault(key.strip(), value.strip())


def load_config(path=None):
    path = path or os.environ.get("CONFIG_PATH") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    env_overrides = {
        "LOCAL_MODEL_PATH": ("local", "model_path"),
        "INPUT_PATH": ("io", "input_path"),
        "OUTPUT_PATH": ("io", "output_path"),
    }
    for var, (section, key) in env_overrides.items():
        if os.environ.get(var):
            cfg[section][key] = os.environ[var]
    return cfg


def by_category(mapping, category):
    """Valeur par catégorie avec repli sur 'default' (max_tokens, thresholds, ...)."""
    if not isinstance(mapping, dict):
        return mapping
    return mapping.get(category, mapping.get("default"))
