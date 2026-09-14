"""Guard test: .env.example must not ship a password that actually works.

Issue #124: repom shipped working default credentials (repom_dev / admin /
no Redis password). .env.example now documents CHANGE_ME / an empty value
for every *_PASSWORD setting, and repom.credentials.reject_default_credential
must reject each one, so copying the file verbatim fails loudly instead of
standing up a service with a known password.
"""

from pathlib import Path

import pytest

from repom.credentials import reject_default_credential

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PASSWORD_KEYS = ("POSTGRES_PASSWORD", "PGADMIN_DEFAULT_PASSWORD", "REDIS_PASSWORD")


def test_env_example_contains_no_working_credential():
    lines = (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()

    found = set()
    for line in lines:
        stripped = line.strip().lstrip("#").strip()
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key not in PASSWORD_KEYS:
            continue
        found.add(key)
        with pytest.raises(ValueError, match=key):
            reject_default_credential(value.strip(), env_var=key)

    assert found == set(PASSWORD_KEYS)
