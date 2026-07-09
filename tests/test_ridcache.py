import pytest

from ncpi_fhir_client import ridcache
from ncpi_fhir_client.ridcache import RIdCache, get_identifier


class TestGetIdentifier:
    def test_returns_the_first_identifier_when_given_a_list(self):
        resource = {"identifier": [{"system": "s", "value": "v"}, {"system": "s2", "value": "v2"}]}
        assert get_identifier(resource) == {"system": "s", "value": "v"}

    def test_returns_the_identifier_directly_when_not_a_list(self):
        resource = {"identifier": {"system": "s", "value": "v"}}
        assert get_identifier(resource) == {"system": "s", "value": "v"}

    def test_returns_none_when_no_identifier_present(self):
        assert get_identifier({}) is None


class TestValidSystem:
    def test_no_patterns_means_everything_is_valid(self):
        cache = RIdCache()
        assert cache.valid_system("http://anything") is True

    def test_matches_against_configured_patterns(self):
        cache = RIdCache(valid_patterns=["whistler"])
        assert cache.valid_system("http://example.org/whistler/Patient") is True
        assert cache.valid_system("http://example.org/other/Patient") is False


class TestStoreAndGetId:
    def test_stores_and_retrieves_an_id(self):
        cache = RIdCache()
        cache._store_id("Patient", "http://sys/patient", "key1", "id1")

        assert cache.get_id("http://sys/patient", "key1") == ("Patient", "id1")
        assert cache.get_id("http://sys/patient", "key1", resource_type="Patient") == "id1"

    def test_get_id_asserts_resource_type_matches(self):
        cache = RIdCache()
        cache._store_id("Patient", "http://sys/patient", "key1", "id1")

        with pytest.raises(AssertionError):
            cache.get_id("http://sys/patient", "key1", resource_type="Observation")

    def test_get_id_returns_none_for_unknown_key(self):
        cache = RIdCache()
        assert cache.get_id("http://sys/patient", "missing") is None

    def test_flags_malformed_ids_when_system_does_not_match_entity_type(self):
        cache = RIdCache()
        cache._store_id("Patient", "http://sys/observation", "key1", "id1")
        assert cache.malformed_ids == {"http://sys/observation|key1"}

    def test_well_formed_ids_are_not_flagged(self):
        cache = RIdCache()
        cache._store_id("Patient", "http://sys/patient", "key1", "id1")
        assert cache.malformed_ids == set()

    def test_restoring_the_same_key_overwrites_without_exit_on_dupes(self):
        cache = RIdCache()
        cache._store_id("Patient", "http://sys/patient", "key1", "id1")
        cache._store_id("Patient", "http://sys/patient", "key1", "id2", exit_on_dupes=False)

        assert cache.get_id("http://sys/patient", "key1") == ("Patient", "id2")

    def test_duplicate_key_with_exit_on_dupes_terminates_the_process(self, monkeypatch):
        calls = []

        def fake_exit(code):
            calls.append(code)
            raise SystemExit(code)

        monkeypatch.setattr(ridcache.os, "_exit", fake_exit)

        cache = RIdCache()
        cache._store_id("Patient", "http://sys/patient", "key1", "id1")

        with pytest.raises(SystemExit):
            cache._store_id("Patient", "http://sys/patient", "key1", "id2", exit_on_dupes=True)

        assert calls == [1]
