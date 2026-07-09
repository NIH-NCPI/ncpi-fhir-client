import pytest

from ncpi_fhir_client.host_config import get_host_config


class TestGetHostConfig:
    def test_parses_an_existing_fhir_hosts_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "fhir_hosts").write_text(
            "dev:\n"
            "  host_desc: Dev\n"
            "  target_service_url: http://example.org/fhir\n"
            "  auth_type: auth_basic\n"
        )

        config = get_host_config()

        assert config == {
            "dev": {
                "host_desc": "Dev",
                "target_service_url": "http://example.org/fhir",
                "auth_type": "auth_basic",
            }
        }

    def test_missing_file_exits(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as excinfo:
            get_host_config()

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "must exist in cwd" in captured.err

    def test_empty_file_is_treated_as_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "fhir_hosts").write_text("")

        with pytest.raises(SystemExit):
            get_host_config()
