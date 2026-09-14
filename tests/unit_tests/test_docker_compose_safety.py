"""Tests for repom.docker_compose_safety."""

import os
import stat

import pytest

from repom.docker_compose_safety import (
    format_bound_port,
    format_env_file,
    quote_yaml_string,
    reject_control_characters,
    write_secret_file,
)


class TestRejectControlCharacters:
    def test_returns_value_unchanged_when_clean(self):
        assert reject_control_characters("repom", field_name="user") == "repom"

    @pytest.mark.parametrize("character", ["\n", "\r", "\x00"])
    def test_raises_for_each_forbidden_character(self, character):
        with pytest.raises(ValueError, match="field"):
            reject_control_characters(f"repom{character}oops", field_name="field")

    def test_error_message_includes_field_name(self):
        with pytest.raises(ValueError, match="postgres.user"):
            reject_control_characters("a\nb", field_name="postgres.user")


class TestQuoteYamlString:
    def test_wraps_plain_value_in_double_quotes(self):
        assert quote_yaml_string("repom") == '"repom"'

    def test_escapes_backslash(self):
        assert quote_yaml_string("a\\b") == '"a\\\\b"'

    def test_escapes_double_quote(self):
        assert quote_yaml_string('a"b') == '"a\\"b"'

    def test_escapes_newline_without_emitting_a_raw_newline(self):
        quoted = quote_yaml_string("a\nb")
        assert quoted == '"a\\nb"'
        assert "\n" not in quoted

    def test_escapes_carriage_return_and_tab(self):
        quoted = quote_yaml_string("a\rb\tc")
        assert quoted == '"a\\rb\\tc"'
        assert "\r" not in quoted
        assert "\t" not in quoted

    def test_a_hostile_payload_cannot_add_a_yaml_key(self):
        quoted = quote_yaml_string("hostile\nPOSTGRES_HOST_AUTH_METHOD: trust")
        line = f"      POSTGRES_PASSWORD: {quoted}"

        # The whole payload, key and all, stays inside one quoted scalar on
        # one line, so it can never start a second top-level YAML key.
        assert line.count("\n") == 0
        assert line == (
            '      POSTGRES_PASSWORD: '
            '"hostile\\nPOSTGRES_HOST_AUTH_METHOD: trust"'
        )


class TestFormatBoundPort:
    def test_binds_loopback_by_default(self):
        assert format_bound_port(5432, 5432, expose_to_lan=False) == "127.0.0.1:5432:5432"

    def test_binds_all_interfaces_when_opted_in(self):
        assert format_bound_port(5432, 5432, expose_to_lan=True) == "0.0.0.0:5432:5432"


class TestFormatEnvFile:
    def test_renders_key_value_lines(self):
        content = format_env_file({"A": "1", "B": "2"})
        assert content == 'A="1"\nB="2"\n'

    def test_empty_mapping_returns_empty_string(self):
        assert format_env_file({}) == ""

    def test_rejects_control_characters_in_value(self):
        with pytest.raises(ValueError, match="PASSWORD"):
            format_env_file({"PASSWORD": "a\nb"})

    def test_quotes_and_escapes_a_hostile_value(self):
        """A space, ``#``, ``$``, ``"`` and ``\\`` must all survive Compose's
        env-file interpolation unchanged."""
        content = format_env_file({"PASSWORD": 'a b#c$d"e\\f'})
        assert content == 'PASSWORD="a b#c$$d\\"e\\\\f"\n'


class TestWriteSecretFile:
    @pytest.mark.skipif(
        os.name != "posix",
        reason="POSIX permission bits are not enforced on Windows",
    )
    def test_writes_content_and_restricts_permissions(self, tmp_path):
        path = tmp_path / "secret.env"
        write_secret_file(path, "VALUE=1\n")

        assert path.read_text() == "VALUE=1\n"
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
