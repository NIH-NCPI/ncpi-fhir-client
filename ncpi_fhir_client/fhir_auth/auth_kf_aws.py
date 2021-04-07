""" Cookie based authentication as required by the shared server set up by the kids first team

This authorization technique assumes that the user has already extracted a valid cookie as per 
instructions from the team. So, it is up to the user, at this time, to periodically change the
cookie once the old one expires. 

TODO: Add support to allow the program to prompt the user for the cookie if it is found to 
      be invalid
"""

class AuthKfAws:
    def __init__(self, cfg):
        self.cookie = cfg['cookie']

    def update_request_args(self, request_args):
        """Add cookie details to the header"""
        if 'headers' not in request_args:
            request_args['headers'] = {}
        request_args['headers']['cookie'] = self.cookie

    @classmethod
    def example_config(cls, writer, other_entries):
        print(f"""\n# Example configuration for cookie based authentication
dev-kf-aws:
    auth_type: 'auth_kf_aws'
    cookie: 'AWSELBAuthSessionCookie-0=FDSAFDSACookieContentsASDFASDF'""", file=writer)
        for key in other_entries.keys():
            print(f"    {key}: '{other_entries[key]}'", file=writer)



