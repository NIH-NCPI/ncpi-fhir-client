"""

Provide some basic assistance with data responses from the fhir server


"""
import pdb
import subprocess
from pprint import pformat

from collections import defaultdict

class FhirResult:
    """Wrap the return value a bit to make interacting with it a bit more smoother"""
    def __init__(self, payload):
        self.status_code = payload['status_code']
        self.request_url = payload['request_url']
        self.response = payload['response']

        #pdb.set_trace()
        # Empty bundles don't have an entry
        if 'total' in self.response and self.response['total'] == 0:
            self.entries = []

        # Always return an array, even if it was a single entry
        elif 'entry' in self.response:
            self.entries = self.response['entry']
        else:
            self.entries = [self.response]

        # If there is pagination, this will capture the "next" url to traverse 
        # large returns
        self.next = None

        self.entry_count = len(self.entries)

        if "link" in self.response:
            for ref in self.response['link']:
                if ref['relation'] == 'next':
                    self.next = ref['url']       

    def success(self, dump_error=False):
        is_good = self.status_code > 199 and self.status_code < 300

        if not is_good and dump_error:
            print()
            print(pformat(self.response))
            print(f"{self.request_url} returned error code {self.status_code}")

        return is_good

    def append(self, payload):
        """Extend our entry data by following pagination links"""

        self.response = payload['response']
        self.next = None

        for ref in self.response['link']:
            if ref['relation'] == 'next':
                self.next = ref['url']   

        if 'entry' not in self.response:
            print(self.response)
            pdb.set_trace()
            print("There is a problem with the response")
        self.entries += self.response['entry']
        self.entry_count = len(self.entries)  

    