import logging
import pdb

logger = logging.getLogger(__name__)
from ncpi_fhir_utility.client import FhirApiClient
import subprocess
from pprint import pformat

from ncpi_fhir_client.fhir_auth import get_auth
from ncpi_fhir_client.fhir_result import FhirResult

class InvalidCall(Exception):
    def __init__(self, url, response):
        self.status_code = response['status_code']
        self.url = url
        self.response = response

        super().__init__(f"HTTP {self.status_code} encountered")

def ExceptOnFailure(success, url, response):
    if not success:
        raise InvalidCall(url, response)


class FhirClient:
    def __init__(self, cfg):
        """cfg is a dictionary containing all relevant details suitable for host and authentication"""
        self.host_desc = cfg.get('host_desc')
        self.auth = get_auth(cfg)

        if self.host_desc is None:
            self.host_desc = 'No Description'

        # URL associated with the host. If it's a non-standard port, use appropriate URL:XXXXX format
        self.target_service_url = cfg.get('target_service_url')

        self.is_valid = False
        self._client = None         # Cache the client so we don't have to rebuild it between calls

        self.is_valid = self.auth is not None

        # Make the host desc suitable for filenames
        self.host_desc = self.host_desc.replace("/", "-").replace(" ", "_").lower()

    def init_log(self):
        """make sure this uses the current logging, which probably changes based on user's input"""
        self.logger = logging.getLogger(__name__)

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

    def delete_by_record_id(self, resource, id):
        """Just a basic delete wrapper"""
        reqargs = {        }
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

    def post(self, resource, data, validate_only=False):
        """Basic POST wrapper
        
           validate_only will append the $validate to the end of the final url"""
        objs = data

        if not isinstance(objs, list):
            objs = [data]

        for obj in objs:
            kwargs = {
                'json': data
            }
            
            self.auth.update_request_args(kwargs)            
            endpoint = f"{self.target_service_url}/{resource}"
            if validate_only:
                endpoint += "/$validate"

            success, result = self.client().send_request(
                                "POST", 
                                endpoint, 
                                **kwargs)

            return result

    def get(self, resource, recurse=True, rec_count=250, raw_result=False):
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

        reqargs = {}
        self.auth.update_request_args(reqargs)    

        url = f"{self.target_service_url}/{resource}{count}"
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


