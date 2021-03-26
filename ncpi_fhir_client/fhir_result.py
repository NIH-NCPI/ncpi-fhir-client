"""

Provide some basic assistance with data responses from the fhir server


"""

import subprocess
from pprint import pformat

class FhirResult:
    """Wrap the return value a bit to make interacting with it a bit more smoother"""
    def __init__(self, payload):
        self.response = payload['response']

        # Always return an array, even if it was a single entry
        if 'entry' in self.response:
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

    def append(self, payload):
        """Extend our entry data by following pagination links"""
        self.response = payload['response']
        self.next = None

        for ref in self.response['link']:
            if ref['relation'] == 'next':
                self.next = ref['url']   

        self.entries += self.response['entry']
        self.entry_count = len(self.entries)  