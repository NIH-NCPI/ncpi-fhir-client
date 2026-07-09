import pytest

from ncpi_fhir_client import fhir_auth
from ncpi_fhir_client.fhir_auth.auth_basic import AuthBasic


class TestCamelize:
    def test_converts_snake_case_to_camel_case(self):
        assert fhir_auth.camelize("auth_basic") == "AuthBasic"

    def test_handles_multi_word_names(self):
        assert fhir_auth.camelize("auth_gcp_oath2") == "AuthGcpOath2"


class TestGetModules:
    def test_discovers_every_auth_module_by_filename(self):
        modules = fhir_auth.get_modules()
        assert set(modules.keys()) == {
            "auth_basic",
            "auth_gcp_oath2",
            "auth_gcp_target_service",
            "auth_kf_aws",
            "auth_kf_openid",
        }

    def test_maps_module_id_to_its_camel_case_class(self):
        modules = fhir_auth.get_modules()
        assert modules["auth_basic"] is AuthBasic

    def test_result_is_cached_across_calls(self):
        first = fhir_auth.get_modules()
        second = fhir_auth.get_modules()
        assert first is second


class TestGetAuth:
    def test_instantiates_the_matching_auth_class(self):
        auth = fhir_auth.get_auth({"auth_type": "auth_basic", "username": "u", "password": "p"})
        assert isinstance(auth, AuthBasic)

    def test_missing_auth_type_raises(self):
        with pytest.raises(AssertionError):
            fhir_auth.get_auth({})

    def test_unknown_auth_type_raises(self):
        with pytest.raises(AssertionError):
            fhir_auth.get_auth({"auth_type": "not_a_real_scheme"})
