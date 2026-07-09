from ncpi_fhir_client.fhir_auth.auth_kf_aws import AuthKfAws


class TestAuthKfAws:
    def test_update_request_args_sets_cookie_header(self):
        auth = AuthKfAws({"cookie": "abc123"})
        request_args = {}
        auth.update_request_args(request_args)
        assert request_args == {"headers": {"cookie": "abc123"}}

    def test_preserves_existing_headers(self):
        auth = AuthKfAws({"cookie": "abc123"})
        request_args = {"headers": {"accept": "application/json"}}
        auth.update_request_args(request_args)
        assert request_args["headers"] == {
            "accept": "application/json",
            "cookie": "abc123",
        }

    def test_no_basic_auth_when_username_absent(self):
        auth = AuthKfAws({"cookie": "abc123"})
        request_args = {}
        auth.update_request_args(request_args)
        assert "auth" not in request_args

    def test_adds_basic_auth_when_username_present(self):
        auth = AuthKfAws({"cookie": "abc123", "username": "u", "password": "p"})
        request_args = {}
        auth.update_request_args(request_args)
        assert request_args["auth"] == ("u", "p")
