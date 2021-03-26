"""Wrapper to generate the authentication token

This will generate bearer tokens based on either OA2 or target service 

For OA2, the library will prompt the user to visit a webpage and enter the 
code generated once they grant the program permission to act on their behalf.

Please note that OA2 requires that the client program and the user granting 
permission both have permission to access the FHIR server. 

TODO: There is no caching of these tokens, so permission will be required each
      time the a new instance of this object is created (i.e. each time the 
      client program is run unless the object is destroyed and recreated)
"""

import jwt
import json
import datetime
import subprocess
import requests
from pathlib import Path

import pdb

# TODO: these do time-out periodicallly (max lifetime is 1hr)
# So, probably need keep the expiry so that the token can be 
# regenerated prio to expiration. 
class GoogleAuth(object):
    def __init__(self, target_service = None, oa2_client=None):
        "Optionally choose between target service or open auth2"
        self.target_service = target_service
        self.oa2_client = oa2_client

        # Target Service is probably the most appropriate way to 
        # ingest or run tests
        if target_service:
            with open(target_service, 'rt') as f:
                data=f.read()
                data = json.loads(data)
                self.account = data['client_email']
                self.private_key = data['private_key']
                self.algorithm = 'RS256'
                self.token_uri = data['token_uri']
                self.target_data = data
        self.scope = "https://www.googleapis.com/auth/cloud-platform"
        self.credentials = None

        # Open Auth is probably more appropriate for queries and use by/for
        # researchers 
        if oa2_client:
            with open(oa2_client, 'rt') as f:
                data = f.read()
                data= json.loads(data)

                self.client_id = data['installed']['client_id']
                self.project_id = data['installed']['project_id']
                self.auth_uri = data['installed']['auth_uri']
                self.token_uri = data['installed']['token_uri']
                self.client_secret = data['installed']['client_secret']
                self.credentials = None

    def access_token(self, lifetime=60):
        """Generate the token that is to be used to access the server"""
        if self.target_service:
            claim_set = {
                "iss": self.account,
                "scope": self.scope,
                "aud": self.token_uri,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=lifetime),
                "iat": datetime.datetime.utcnow()
            }

            signature = jwt.encode(claim_set, self.private_key, algorithm=self.algorithm)
            req = requests.post(self.token_uri, 
                            data={
                                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                                'assertion': signature,
                                'response_type': 'code'
                                }
                            )
            return req.json()['access_token']
        elif self.oa2_client:

            if self.credentials is None or self.credentials.expired:
                from google_auth_oauthlib.flow import InstalledAppFlow

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.oa2_client,
                    scopes=[self.scope]) 
                self.credentials = flow.run_console()        
            return self.credentials.token
