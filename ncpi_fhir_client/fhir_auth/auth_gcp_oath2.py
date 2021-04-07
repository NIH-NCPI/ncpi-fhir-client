""" GCP Target Service Token based auth

The configuration here will point to a token file as can be downloded from the GCP console

For systems that employ expirey tokens, the objects can perform whatever
refresh is needed prior to each update_headers returns
"""

from ncpi_fhir_client.fhir_auth.google_auth import GoogleAuth

class AuthGcpOath2:
    def __init__(self, cfg):
        self.token = cfg['oa2_client_token']
        self.gauth = GoogleAuth(oa2_client=self.token)

    def update_request_args(self, request_args):
        """Use a bearer token based on the openauth token provided"""
        if 'headers' not in request_args:
            request_args['headers'] = {}
        request_args['headers']['Authorization'] = "Bearer " + self.gauth.access_token()

    @classmethod
    def example_config(cls, writer, other_entries):
        print(f"""\n# Example configuration for gcp + open auth2
dev-oath2:
    auth_type: 'auth_gcp_oath2'
    oa2_client_token: 'path-to-token'""", file=writer)
        for key in other_entries.keys():
            print(f"    {key}: '{other_entries[key]}'", file=writer)
