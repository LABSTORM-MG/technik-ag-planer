import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent


def _load_settings(module, extra_env):
    env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
    env.update(extra_env)
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", f"import {module}"],
        cwd=APP_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_prod_settings_require_secret_key():
    result = _load_settings(
        "config.settings.prod",
        {"DJANGO_ALLOWED_HOSTS": "planer.example.org", "DJANGO_READ_ENV_FILE": "false"},
    )

    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr


def test_prod_settings_load_with_secret_key():
    result = _load_settings(
        "config.settings.prod",
        {
            "DJANGO_ALLOWED_HOSTS": "planer.example.org",
            "DJANGO_SECRET_KEY": "x" * 50,
            "DJANGO_READ_ENV_FILE": "false",
        },
    )

    assert result.returncode == 0, result.stderr


def test_german_locale(settings):
    assert settings.LANGUAGE_CODE == "de"
    assert settings.TIME_ZONE == "Europe/Berlin"
