import logging
import pdb

logger = logging.getLogger(__name__)
from ncpi_fhir_utility.client import FhirApiClient
import subprocess
from time import sleep
from pprint import pformat
from copy import deepcopy
from json import dumps

from threading import Lock
from pathlib import Path

from ncpi_fhir_client.fhir_auth import get_auth
from ncpi_fhir_client.fhir_result import FhirResult

import urllib3

urllib3.disable_warnings()
http = urllib3.PoolManager(maxsize=64)

# Just make sure our logs aren't unreadable due to threads
log_lock = Lock()


class InvalidCall(Exception):
    def __init__(self, url, response):
        self.status_code = response['status_code']
        self.url = url
        self.response = response

        super().__init__(f"HTTP {self.status_code} encountered ({url})")

def ExceptOnFailure(success, url, response):
    if not success:
        raise InvalidCall(url, response)

def getIdentifier(resource):
    idnt = resource.get('identifier')

    if type(idnt) is list:
        return idnt[0]
    return idnt

class FhirClient:
    retry_post_count = 5
    def __init__(self, cfg, idcache=None, cmdlog=None):
        """cfg is a dictionary containing all relevant details suitable for host and authentication
        
        idcache is an optional substitute for the GET behavior we use when an entry isn't in our 
        dbcache. This will allow us to get ALL ids at the start and determine right away if it is
        present or not without the extra HTTP call. As long as new entries are going into a normal 
        ID cache, all should be fine (i.e. we can safely ignore ids that are added by the current
        application because those should be cached by another, more permanent mechanism)

        When idcache is not in use, we'll fall back onto the GET approach
        """
        self.host_desc = cfg.get('host_desc')
        self.auth = get_auth(cfg)
        self.logger = logger

        self.rest_log = None

        if cmdlog is not None:
            log_dir = Path(cmdlog).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            self.rest_log = open(cmdlog, 'wt')

        if self.host_desc is None:
            self.host_desc = 'No Description'

        self.idcache = idcache

        # URL associated with the host. If it's a non-standard port, use appropriate URL:XXXXX format
        self.target_service_url = cfg.get('target_service_url')

        self.is_valid = False
        self._client = None         # Cache the client so we don't have to rebuild it between calls

        self.is_valid = self.auth is not None

        # Make the host desc suitable for filenames
        self.host_desc = self.host_desc.replace("/", "-").replace(" ", "_").lower()

        # will remain None until a bundle file is initialized
        self.bundle = None

        if self.idcache is not None:
            self.idcache.load_ids_from_host(self)
        
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

        self.auth.update_request_args(reqargs)
        headers = self.get_login_header(reqargs['headers'])

        return self.client().send_request(verb, api_path, json=body, headers=headers)

    def delete_by_record_id(self, resource, id, silence_warnings=False):
        """Just a basic delete wrapper"""
        reqargs = {        }

        self.auth.update_request_args(reqargs)
        endpoint = f"{self.target_service_url}/{resource}/{id}"
        success, result = self.client().send_request("delete", endpoint, **reqargs)
        if not success and not silence_warnings:
            with log_lock:
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
                gendpoint = f"{resource}?url={url}"
                entries = self.get(gendpoint).entries
                for response in entries:
                    #pdb.set_trace()
                    if "resource" in response:
                        if skip_insert_if_present:
                            return {'status_code': 201, 'response':response}
                        if 'id' not in obj:
                            obj['id'] = response['resource']['id']
                            verb = 'PUT'
                            endpoint =  f"{self.target_service_url}/{resource}/{obj['id']}"
                        else:
                            # Only delete if we encounter the same thing more than once
                            del_response = None
                            retry_count = 1
                            delrsp = self.delete_by_record_id(resource, response['resource']['id'])
                            fresponse = self.sleep_until(gendpoint, 0, message=f"Deleting {response['resource']['id']} / {gendpoint}")
                            if fresponse.success:
                                responses.append(fresponse)
                            else:
                                print(f"There was a problem deleting the resource, {response['resource']['id']} / {gendpoint}")

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

    def post(self, resource, data, validate_only=False, identifier=None, identifier_system=None, identifier_type='identifier'):
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

                if self.idcache:
                    if identifier_system is not None:
                        id_system = identifier_system
                        id_value = identifier
                    else:
                        id_system = identifier.split("|")[0]
                        id_value = "|".join(identifier.split("|")[1:])
                    id = self.idcache.get_id(id_system, id_value, resource)
                    if id is not None:
                        obj['id'] = id

                else:
                    result = self.get(f"{resource}?{identifier_type}={identifier}")
                    # If it wasn't found, then we just plan to create
                    if result.success():
                        if result.entry_count > 0:
                            entry = result.entries[0]
                            id = entry['resource']['id']
                            obj['id'] = id
    
            if 'id' in obj and resource != "Bundle":
                verb = "PUT"

                endpoint = f"{self.target_service_url}/{resource}/{obj['id']}"
                kwargs['json'] = obj

            retry_count = FhirClient.retry_post_count
            while retry_count > 0:
                success, result = self.client().send_request(
                                    verb, 
                                    endpoint, 
                                    **kwargs)

                # 422 just means something was preventing it from succeeding, so 
                # it could be the db hasn't caught up yet, so we'll sleep for a second and
                # try again. 409 means there is a conflict, which is probably some 
                # data that is duplicated (such as ds-connect surveys that occur 
                # more than once)
                if result['status_code'] not in [422, 409] :
                    retry_count = 0
                else:
                    sleep(1)
                    print(pformat(data))
                    print("------------------")
                    for issue in result['response']['issue']:
                        if issue['severity'] == "error":
                            print(pformat(issue))
                    print(f"{result['status_code']} - {getIdentifier(obj)['value']} -- Retrying {retry_count} more times" )
                    pdb.set_trace()

                    retry_count -= 1 
            return result

    def get(self, resource, recurse=True, rec_count=-1, raw_result=False, reqargs=None, except_on_error=True):
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

        success, result = self.client().send_request("GET", f"{url}", **reqargs)

        # We'll skip printing this if we return the error to the calling function
        if not success and except_on_error:
            print("There was a problem with the request for the GET")
            print(pformat(result))

        # For now, let's just give up if there was a problem
        if except_on_error:
            ExceptOnFailure(success, url, result)

        if raw_result:
            return result
        content = FhirResult(result)

        # Follow paginated results if so desired
        while recurse and content.next is not None:
            success, result = self.client().send_request("GET", content.next,  **reqargs)

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
                # May (or may not) be a bundle...
                if 'resourceType' in entries[0]:
                    if entries[0]['resourceType'] == 'Bundle':
                        if 'entry' in entries[0]:
                            entries = entries[0]['entry']
                        else:
                            entries = []

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

