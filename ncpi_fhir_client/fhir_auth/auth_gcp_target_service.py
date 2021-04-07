""" GCP Target Service Token based auth

The configuration here will point to a target service token file as can be 
downloded from the GCP console

"""

from ncpi_fhir_client.fhir_auth.google_auth import GoogleAuth

class AuthGcpTargetService:
    def __init__(self, cfg):
        self.token = cfg['service_account_token']
        self.gauth = GoogleAuth(target_service=self.token)

    def update_request_args(self, request_args):
        """Add the bearer token to the header based on the token provided"""
        if 'headers' not in request_args:
            request_args['headers'] = {}
        request_args['headers']['Authorization'] = "Bearer " + self.gauth.access_token()

    @classmethod
    def example_config(cls, writer, other_entries):
        print(f"""\n# Example configuration for gcp target-service
dev-service-token:
    auth_type: 'auth_gcp_target_service'
    service_account_token: 'path-to-token'""", file=writer)
        for key in other_entries.keys():
            print(f"    {key}: '{other_entries[key]}'", file=writer)

