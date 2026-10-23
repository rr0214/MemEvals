"""Loads KEY=VALUE pairs from a local .env file into the environment (no extra dependency).
Existing environment variables win, so a key set in the terminal is never overwritten."""
import os, pathlib

def load_env(path=pathlib.Path(__file__).parent / ".env"):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
