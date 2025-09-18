import json
from pathlib import Path, PurePath

# The physical location of the configuration file
CONFIG_FILE_PATH = Path(__file__).parent / "config.json"


# --- NEW: A custom encoder to handle Path objects ---
class PathEncoder(json.JSONEncoder):
    """A JSON encoder that converts Path objects to strings."""

    def default(self, obj):
        if isinstance(obj, PurePath):
            return str(obj)
        return super().default(obj)


def load_config_loud():
    """Loads configuration, creating it if it doesn't exist. Prints to console."""
    if not CONFIG_FILE_PATH.exists():
        print("No config.json found. Creating one...")
        with open(CONFIG_FILE_PATH, "w") as f:
            # FIX: Convert Path objects to strings before initial save
            default_path = str(Path(".").expanduser().absolute())
            json.dump(
                {
                    "allowed_paths": [default_path],
                    "media_index_allowed_paths": [default_path],
                },
                f,
                indent=4,
            )
        print(f"Created config.json at {CONFIG_FILE_PATH}")

    with open(CONFIG_FILE_PATH, "r") as f:
        config = json.load(f)

    # The rest of this function correctly handles loading strings and converting to Paths
    if not config.get("allowed_paths"):
        print("⚠️ No allowed paths found in config.json. Using current directory.")
        config["allowed_paths"] = [Path(".").expanduser().absolute()]
    else:
        config["allowed_paths"] = [
            Path(p).expanduser().absolute() for p in config["allowed_paths"]
        ]

    if not config.get("media_index_allowed_paths"):
        print("⚠️ No media index paths found. Using current directory.")
        config["media_index_allowed_paths"] = [Path(".").expanduser().absolute()]
    else:
        config["media_index_allowed_paths"] = [
            Path(p).expanduser().absolute() for p in config["media_index_allowed_paths"]
        ]

    return config


def load_config():
    """Loads configuration, creating it if it doesn't exist."""
    if not CONFIG_FILE_PATH.exists():
        with open(CONFIG_FILE_PATH, "w") as f:
            # FIX: Convert Path objects to strings before initial save
            default_path = str(Path(".").expanduser().absolute())
            json.dump(
                {
                    "allowed_paths": [default_path],
                    "media_index_allowed_paths": [default_path],
                },
                f,
                indent=4,
            )

    with open(CONFIG_FILE_PATH, "r") as f:
        config = json.load(f)

    # This logic is fine, it reads strings and returns Path objects for the app
    if not config.get("allowed_paths"):
        config["allowed_paths"] = [Path(".").expanduser().absolute()]
    else:
        config["allowed_paths"] = [
            Path(p).expanduser().absolute() for p in config["allowed_paths"]
        ]

    if not config.get("media_index_allowed_paths"):
        config["media_index_allowed_paths"] = [Path(".").expanduser().absolute()]
    else:
        config["media_index_allowed_paths"] = [
            Path(p).expanduser().absolute() for p in config["media_index_allowed_paths"]
        ]

    return config


def save_config(config):
    """Saves the configuration dictionary to the JSON file."""
    with open(CONFIG_FILE_PATH, "w") as f:
        json.dump(config, f, indent=4, cls=PathEncoder)
