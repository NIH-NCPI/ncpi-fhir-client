import logging
import pdb

logger = logging.getLogger(__name__)
from ncpi_fhir_utility.client import FhirApiClient
import subprocess
from time import sleep
from pprint import pformat
from copy import deepcopy
from json import dumps

from ncpi_fhir_client.fhir_auth import get_auth
from ncpi_fhir_client.fhir_result import FhirResult

class InvalidCall(Exception):
    def __init__(self, url, response):
        self.status_code = response['status_code']
        self.url = url
        self.response = response

        super().__init__(f"HTTP {self.status_code} encountered ({url})")

def ExceptOnFailure(success, url, response):
    if not success:
        raise InvalidCall(url, response)


class FhirClient:
    def __init__(self, cfg):
        """cfg is a dictionary containing all relevant details suitable for host and authentication"""
        self.host_desc = cfg.get('host_desc')
        self.auth = get_auth(cfg)
        self.logger = logger

        if self.host_desc is None:
            self.host_desc = 'No Description'

        # URL associated with the host. If it's a non-standard port, use appropriate URL:XXXXX format
        self.target_service_url = cfg.get('target_service_url')

        self.is_valid = False
        self._client = None         # Cache the client so we don't have to rebuild it between calls

        self.is_valid = self.auth is not None

        # Make the host desc suitable for filenames
        self.host_desc = self.host_desc.replace("/", "-").replace(" ", "_").lower()

        # will remain None until a bundle file is initialized
        self.bundle = None
        
    def init_log(self):
        """make sure this uses the current logging, which probably changes based on user's input"""
        self.logger = logging.getLogger(__name__)


    def init_bundle(self, bundle_filename, bundle_id):
        self.bundle = open(bundle_filename, 'wt')
        self.bundle.write("""{
    "resourceType": "Bundle",
    "id": \"""" + bundle_id + """\",
    "type": "transaction",
    "entry": [
""")
        self.write_comma = False

    def write_to_bundle(self, resource):
        response = deepcopy(resource)
        if self.bundle:
            # For now, let's just skip the ID so that it works in a more general sense
            destination = f"{resource['resourceType']}" #/{resource['id']}"
            if self.write_comma: 
                self.bundle.write(",")
            self.write_comma = True
            #pdb.set_trace()
            resource_data = dumps(resource)
            full_url = f"""{self.target_service_url}/{resource['resourceType']}/{resource['id']}"""
            self.bundle.write("""    {
      "fullUrl": \"""" + full_url + """\",
      "resource": """ + resource_data + """,
      "request": {
          "method": "POST",
          "url": \"""" + destination + """\"
      }
    }""")
        return response

    def close_bundle(self):
        if self.bundle:
            self.bundle.write("""
    ]
}""")
            self.bundle.close()


    def client(self):
        """Return cached client object, creating it if necessary"""
        if self._client is None:
            self._client = FhirApiClient(
                base_url=self.target_service_url) #, auth=self.auth.auth)

        return self._client

    def get_login_header(self, headers = {}):
        """Just emulating what the fhir tools library does, but it's easy to find if we decide to add to it"""
        if "Content-Type" not in headers:
            headers.update(self.client()._fhir_version_headers())
        return headers

    def delete_by_query(self, resource, qry):
        reqargs = {}
        pdb.set_trace()
        responses = []
        for response in self.get(f"{resource}?{qry}").entries:
            if "resource" in response:
                responses.append(self.delete_by_record_id(resource, response['resource']['id']))

        if len(responses) == 1:
            return responses[0]
        return responses

    def send_request(self, verb, api_path, body, reqargs=None, headers=None):
        if headers is None:
            headers = {}
        if reqargs is None:
            reqargs = {'headers': headers}

        #headers = self.get_login_header(headers)
        self.auth.update_request_args(reqargs)
        headers = self.get_login_header(reqargs['headers'])
        #pdb.set_trace()
        return self.client().send_request(verb, api_path, json=body, headers=headers)

    def delete_by_record_id(self, resource, id):
        """Just a basic delete wrapper"""
        reqargs = {        }
        #pdb.set_trace()
        self.auth.update_request_args(reqargs)
        endpoint = f"{self.target_service_url}/{resource}/{id}"
        success, result = self.client().send_request("delete", endpoint, **reqargs)
        if not success:
            self.logger.error(pformat(result))
        return result

    # TODO: Allow this function to pull the data first and merge changes in
    def update(self, resource, id, data):
        """Update the current instance by overwriting it. """
        endpoint = f"{self.target_service_url}/{resource}/{id}"
        reqargs = {
            'json': data
        }
        self.auth.update_request_args(reqargs)
        success, result = self.client().send_request(
                                "put", endpoint, 
                                **reqargs)

        return result

    def patch(self, resource, id, data):
        """Patch in partial changes to an existing record rather than overwriting everything. 
        
           Please note that this accepts json-patch data and not a traditional fhir record"""
        headers = self.get_login_header()
        headers['Content-Type'] = 'application/json-patch+json'
        headers['Prefer'] = 'return=representation'
        reqargs = {
            'headers': headers,
            'json': data
        }
        self.auth.update_request_args(reqargs)
        endpoint = f"{self.target_service_url}/{resource}/{id}"
        success, result = self.client().send_request(
                                "patch", 
                                endpoint, 
                                **reqargs)

        return result        

    def load(self, resource, data, validate_only=False, skip_insert_if_present=False):
        objs = data

        if not isinstance(objs, list):
            objs = [data]

        for obj in objs:
            verb = "POST"     
            endpoint = f"{self.target_service_url}/{resource}"

            # Certainly don't want to delete anything if we are just validating something
            # that may coincidentally overlap with the current resource's URL
            if not validate_only:
                # First thing, let's go ahead and try deleting 
                assert 'url' in obj
                url = obj['url']

                responses = []
                for response in self.get(f"{resource}?url={url}").entries:
                    if "resource" in response:
                        if skip_insert_if_present:
                            return {'status_code': 201, 'response':response}
                        if 'id' not in obj:
                            obj['id'] = response['resource']['id']
                            verb = 'PUT'
                            endpoint =  f"{self.target_service_url}/{resource}/{obj['id']}"
                        else:
                            # Only delete if we encounter the same thing more than once
                            responses.append(self.delete_by_record_id(resource, response['resource']['id']))

            kwargs = {
                'json': obj
            }

            self.auth.update_request_args(kwargs)       
            if validate_only:
                endpoint += "/$validate"

            success, result = self.client().send_request(
                                verb, 
                                endpoint, 
                                **kwargs)

            return result        

    def post(self, resource, data, validate_only=False, identifier=None, identifier_type='identifier'):
        """Basic POST wrapper
        
           validate_only will append the $validate to the end of the final url
           
           providing an identifier will result in querying for an existing record
           and replacing it.
           
           If identifier finds a match or the resource object itself contains
           an id, the endpoint will become an overwrite using PUT instead of POST """
        objs = data

        if not isinstance(objs, list):
            objs = [data]

        for obj in objs:
            kwargs = {
                'json': obj
            }
            
            self.auth.update_request_args(kwargs)            
            endpoint = f"{self.target_service_url}/{resource}"
            if resource == 'Bundle':
                endpoint = self.target_service_url
            if validate_only:
                endpoint += "/$validate"

            verb = "POST"
            if identifier is not None:
                #pdb.set_trace()
                result = self.get(f"{resource}?{identifier_type}={identifier}")
                # If it wasn't found, then we just plan to create
                if result.success():
                    if result.entry_count > 0:
                        entry = result.entries[0]
                        id = entry['resource']['id']
                        print(f"Reusing the existing resource at {resource}:{id}")
                        obj['id'] = id
 
            if 'id' in obj and resource != "Bundle":
                verb = "PUT"
                #pdb.set_trace()
                endpoint = f"{self.target_service_url}/{resource}/{obj['id']}"
                kwargs['json'] = obj

            success, result = self.client().send_request(
                                verb, 
                                endpoint, 
                                **kwargs)

            return result

    def get(self, resource, recurse=True, rec_count=-1, raw_result=False, reqargs=None):
        """Wrapper for basic http:get

        :param resource: FHIR Resource type 
        :param recurse: Aggregate responses across pages, defaults to True
        :type recurse: Boolean
        :param rec_count: records per page, defaults to 250
        :type rec_count: int
        :param raw_result: Return the actual result from the server instead of wrapping it as a FhirResult, defaults to False
        :type raw_result: Boolean
        :return: zero or more records inside a FhirResult (or raw response from server)
        :rtype: FhirResult

        TODO This works well for valid queries and Resource/id requests, but probably needs some
        attention for less straightforward queries
        """

        count=""
        if rec_count > 0:
            count = f"?_count={rec_count}"

            if "?" in resource:
                count = f"&_count={rec_count}"

        if reqargs is None:
            reqargs = {}

        self.auth.update_request_args(reqargs)    

        if resource[0:4] == "http":
            url = f"{resource}{count}"
        else:
            url = f"{self.target_service_url}/{resource}{count}"
        #if 'headers' in reqargs:
        #    print(f"Header for {url} : {reqargs['headers']}")
        success, result = self.client().send_request("GET", f"{url}", **reqargs)
       
        if not success:
            print("There was a problem with the request for the GET")
            print(pformat(result))

        # For now, let's just give up if there was a problem
        ExceptOnFailure(success, url, result)

        if raw_result:
            return result
        content = FhirResult(result)

        # Follow paginated results if so desired
        while recurse and content.next is not None:
            params = content.next.split("?")[1]

            success, result = self.client().send_request("GET", f"{self.target_service_url}?{params}", **reqargs)
            ExceptOnFailure(success, url, result)
            content.append(result)
        return content

    def sleep_until(self, endpt_orig, target_count, sleep_time=5, timeout=360, message=""):
        endpt = endpt_orig

        n = 0
        while True:
            response = self.get(endpt, rec_count=-1)
            entries = response.entries

            if len(entries) > 0:
                #pdb.set_trace()
                # May (or may not) be a bundle...
                if 'resourceType' in entries[0]:
                    if entries[0]['resourceType'] == 'Bundle':
                        if 'entry' in entries[0]:
                            entries = entries[0]['entry']
                        else:
                            entries = []

            #if len(entries) == target_count or n >= timeout:
            #    return response
            entry_count = len(entries)
            if 'total' in response.response:
                entry_count = response.response['total']
            if entry_count == target_count or n >= timeout:
                if n > 0:
                    print(f"{n} seconds. ")
                return response
            if n == 0:
                print(f"{message} - Waiting for {target_count}. Sleeping {sleep_time}", end='', flush=True)
            n += sleep_time
            sleep(sleep_time)
            print(".", end='', flush=True)

