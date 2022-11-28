"""Basic Password authentication

This provides a basic interface expected: 
    * constructor recieves the settings as a dict
    * update request's args to adds username/password details

Support has been added to permit the user to provide a valid filename instead
of the actual password to allow users to store passwords in a private location 
on shared systems. This file must contain ONLY the password and, currently, 
must be accessible vi the python "open" system. So, it can't reside in a cloud
bucket at this time. So, probably a better solution for shared system than a 
cloud based system.
"""
from pathlib import Path

class AuthBasic:
    def __init__(self, cfg):
        self.username = cfg['username']
        self.password = cfg['password']

        # Let the user provide a path to a file for the username
        # to keep it more secure
        if Path(self.password).is_file():
            self.password = Path(self.password).read_text().rstrip()

    @property
    def auth(self):
        return (self.username, self.password)
    
    def update_request_args(self, request_args):
        request_args['auth'] = (self.username, self.password)

    @classmethod
    def example_config(cls, writer, other_entries):
        print(f"""\n# Example of a basic auth configuration
dev:
    auth_type: 'auth_basic'
    username: 'yourusername'
    password: 'yourpassword'""", file=writer)
        for key in other_entries.keys():
            print(f"    {key}: '{other_entries[key]}'", file=writer)


