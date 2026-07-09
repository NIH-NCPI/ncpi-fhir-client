from ncpi_fhir_client.fhir_auth.auth_basic import AuthBasic


class TestAuthBasic:
    def test_auth_property_returns_username_password_tuple(self):
        auth = AuthBasic({"username": "u", "password": "p"})
        assert auth.auth == ("u", "p")

    def test_update_request_args_sets_auth_tuple(self):
        auth = AuthBasic({"username": "u", "password": "p"})
        request_args = {}
        auth.update_request_args(request_args)
        assert request_args == {"auth": ("u", "p")}

    def test_password_can_be_loaded_from_a_file(self, tmp_path):
        password_file = tmp_path / "password.txt"
        password_file.write_text("secretpw\n")

        auth = AuthBasic({"username": "u", "password": str(password_file)})

        assert auth.password == "secretpw"

    def test_password_is_used_literally_when_not_a_file(self):
        auth = AuthBasic({"username": "u", "password": "plainpassword"})
        assert auth.password == "plainpassword"
