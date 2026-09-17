"""Stand-in child process for pg_dump/psql/pg_restore, used by streaming tests.

Runs as a real subprocess (``sys.executable -c SCRIPT``) so tests exercise the
actual Popen-based streaming path in ``_backup_utils.run_streaming_command``
end to end - real OS pipes, a real background thread draining stderr - rather
than mocking ``subprocess.Popen`` with an object shaped like the old
line-buffered / whole-buffer implementation. Every knob is passed as an
environment variable so it reaches the child through both the host command's
inherited-and-extended env and the Docker command's inherited (``env=None``)
one.
"""

import sys

SCRIPT = """
import os
import sys

env_sink = os.environ.get("FAKE_CHILD_ECHO_ENV_SINK")
env_keys = os.environ.get("FAKE_CHILD_ECHO_ENV_KEYS")
if env_sink and env_keys:
    with open(env_sink, "w", encoding="utf-8") as f:
        for key in env_keys.split(","):
            f.write(f"{key}={os.environ.get(key, '')}\\n")

sink = os.environ.get("FAKE_CHILD_STDIN_SINK")
if sink:
    with open(sink, "wb") as f:
        f.write(sys.stdin.buffer.read())

stdout_size = int(os.environ.get("FAKE_CHILD_STDOUT_BYTES", "0"))
if stdout_size:
    sys.stdout.buffer.write(b"o" * stdout_size)
    sys.stdout.buffer.flush()

stderr_text = os.environ.get("FAKE_CHILD_STDERR_TEXT")
stderr_size = int(os.environ.get("FAKE_CHILD_STDERR_BYTES", "0"))
if stderr_text:
    sys.stderr.write(stderr_text)
    sys.stderr.flush()
elif stderr_size:
    sys.stderr.buffer.write(b"e" * stderr_size)
    sys.stderr.buffer.flush()

sys.exit(int(os.environ.get("FAKE_CHILD_EXIT_CODE", "0")))
"""


def fake_client_command() -> list[str]:
    """Return argv for the fake child process (stands in for pg_dump/psql)."""
    return [sys.executable, "-c", SCRIPT]


def missing_binary_command() -> list[str]:
    """Return argv naming a binary that cannot exist, to trigger a real
    FileNotFoundError from subprocess.Popen without mocking it."""
    return ["repom-test-nonexistent-pg-client-binary"]
