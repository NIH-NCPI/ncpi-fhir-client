"""KF open ID based authentication. 


"""

import json
import datetime
import requests
from rich import print

class AuthKfOpenid:
    def __init__(self, cfg):
        self.client_id = cfg['client_id']
        self.client_secret = cfg['client_secret']
        self.token_url = cfg['token_url']
        self.token_expire = datetime.datetime.now()
        self.token = None

    def access_token(self, lifetime=60):
        curtime = datetime.datetime.now()

        if curtime >= self.token_expire:
            response = requests.post(self.token_url, 
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded"
                        },
                        data={
                            "grant_type": "client_credentials",
                            "client_id": self.client_id,
                            "client_secret": self.client_secret
                        })
            
            response = response.json()
            self.token = response['access_token']
            self.token_expire = curtime + datetime.timedelta(seconds=response['expires_in'])

        return self.token

    def update_request_args(self, request_args):
        """Add the bearer token to the header based on the token provided"""
        if 'headers' not in request_args:
            request_args['headers'] = {}
        request_args['headers']['Authorization'] = "Bearer " + self.access_token()
