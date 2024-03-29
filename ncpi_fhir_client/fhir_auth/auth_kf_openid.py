"""KF open ID based authentication. 


"""

import json
import datetime
import requests
from rich import print


class AuthKfOpenid:
    def __init__(self, cfg):
        self.client_id = cfg["client_id"]
        self.client_secret = cfg["client_secret"]
        self.token_url = cfg["token_url"]
        self.token_expire = datetime.datetime.now()
        self.token = None

    def access_token(self, lifetime=60):
        curtime = datetime.datetime.now()

        if curtime >= self.token_expire:
            response = requests.post(
                self.token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )

            response = response.json()
            self.token = response["access_token"]
            self.token_expire = curtime + datetime.timedelta(
                seconds=response["expires_in"]
            )

        return self.token

    def update_request_args(self, request_args):
        """Add the bearer token to the header based on the token provided"""
        if "headers" not in request_args:
            request_args["headers"] = {}
        request_args["headers"]["Authorization"] = "Bearer " + self.access_token()

    @classmethod
    def example_config(cls, writer, other_entries):
        print(
            f"""\n# Example of a basic auth configuration
dev-kf2:
    auth_type: "auth_kf_openid"
    client_id: "your-client-id"
    client_secret: "your-client-secret"
    token_url: "token-url-provided-by-dev-ops"
    target_service_url: "https://the.server.url/fhir"
qa-kf2-inc:""",
            file=writer,
        )
        for key in other_entries.keys():
            print(f"    {key}: '{other_entries[key]}'", file=writer)
