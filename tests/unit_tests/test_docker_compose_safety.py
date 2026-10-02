"""Tests for repom.docker_compose_safety."""

import os
import stat

import pytest

from repom.docker_compose_safety import (
    format_bound_port,
    format_env_file,
    parse_env_file,
    quote_yaml_string,
    reject_control_characters,
    validate_stored_secret_values,
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

    def test_parse_env_file_round_trips_format_env_file(self):
        values = {
            "PLAIN": "value",
            "SPECIAL": 'a b#c$d"e\\f\t',
            "SEPARATORS": "vertical\vform\frecord\x1cnext\x85line\u2028item",
            "EMPTY": "",
        }

        assert parse_env_file(format_env_file(values)) == values

    @pytest.mark.parametrize(
        "content",
        [
            "INVALID\n",
            'PASSWORD="unescaped"quote"\n',
            'PASSWORD="single$sign"\n',
            'PASSWORD="bad\\qescape"\n',
        ],
    )
    def test_parse_env_file_rejects_content_outside_generated_format(self, content):
        with pytest.raises(ValueError):
            parse_env_file(content)


class TestValidateStoredSecretValues:
    def test_stored_secret_is_authoritative_for_unset_or_placeholder_values(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text(format_env_file({"PASSWORD": "saved-secret"}), encoding="utf-8")

        validate_stored_secret_values(
            path,
            {"PASSWORD": "CHANGE_ME"},
            default_credential_placeholder="CHANGE_ME",
            rotation_commands=("rotate_password",),
            generate_command="service_generate",
        )

    def test_refusal_names_file_and_recovery_commands_without_secrets(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text(format_env_file({"PASSWORD": "saved-secret"}), encoding="utf-8")

        with pytest.raises(ValueError) as excinfo:
            validate_stored_secret_values(
                path,
                {"PASSWORD": "different-secret"},
                default_credential_placeholder="CHANGE_ME",
                rotation_commands=("rotate_password",),
                generate_command="service_generate",
            )

        message = str(excinfo.value)
        assert str(path) in message
        assert "rotate_password" in message
        assert "service_generate --force-regenerate" in message
        assert "saved-secret" not in message
        assert "different-secret" not in message


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

    @pytest.mark.skipif(
        os.name != "posix",
        reason="POSIX permission bits are not enforced on Windows",
    )
    def test_backup_keeps_latest_prior_content_across_rewrites(self, tmp_path):
        path = tmp_path / ".env"
        backup_path = tmp_path / ".env.bak"

        write_secret_file(path, "SECRET=A\n")
        write_secret_file(path, "SECRET=B\n")
        write_secret_file(path, "SECRET=C\n")

        assert path.read_text() == "SECRET=C\n"
        assert backup_path.read_text() == "SECRET=B\n"
        assert stat.S_IMODE(backup_path.stat().st_mode) == 0o600

    def test_identical_rewrite_does_not_create_or_change_backup(self, tmp_path):
        path = tmp_path / ".env"
        backup_path = tmp_path / ".env.bak"

        write_secret_file(path, "SECRET=A\n")
        write_secret_file(path, "SECRET=A\n")
        assert not backup_path.exists()

        backup_path.write_text("OLDER=backup\n", encoding="utf-8")
        write_secret_file(path, "SECRET=A\n")
        assert backup_path.read_text(encoding="utf-8") == "OLDER=backup\n"
