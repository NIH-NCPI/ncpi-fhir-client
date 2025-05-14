import logging
import pdb

logger = logging.getLogger(__name__)
# from ncpi_fhir_utility.client import FhirApiClient

from rich import print

from ncpi_fhir_client import requests_retry_session
import subprocess
from time import sleep
from pprint import pformat
from copy import deepcopy
from json import dump, dumps, decoder

from datetime import datetime
from threading import Lock
from pathlib import Path

from ncpi_fhir_client.fhir_auth import get_auth
from ncpi_fhir_client.fhir_result import FhirResult
from ncpi_fhir_client.host_config import get_host_config

from argparse import ArgumentParser, FileType

import urllib3
import sys

import urllib.parse

urllib3.disable_warnings()
http = urllib3.PoolManager(maxsize=64)

# Just make sure our logs aren't unreadable due to threads
log_lock = Lock()


class InvalidCall(Exception):
    def __init__(self, url, response):
        self.status_code = response["status_code"]
        self.url = url
        self.response = response

        super().__init__(f"HTTP {self.status_code} encountered ({url})")


def ExceptOnFailure(success, url, response):
    if not success:
        raise InvalidCall(url, response)


def getIdentifier(resource):
    idnt = resource.get("identifier")

    if type(idnt) is list:
        return idnt[0]
    return idnt


class FhirClient:
    retry_post_count = 5
    fhir_version = "4.0.1"
    # fhir_version = "4.3.0"

    resource_logging = {
        "skipped_params": set(["auth"]),
        "methods": set(["POST", "PUT", "DELETE", "PATCH"]),
    }

    def __init__(self, cfg, idcache=None, cmdlog=None, exit_on_dupes=False):
        """cfg is a dictionary containing all relevant details suitable for host and authentication

        idcache is an optional substitute for the GET behavior we use when an entry isn't in our
        dbcache. This will allow us to get ALL ids at the start and determine right away if it is
        present or not without the extra HTTP call. As long as new entries are going into a normal
        ID cache, all should be fine (i.e. we can safely ignore ids that are added by the current
        application because those should be cached by another, more permanent mechanism)

        When idcache is not in use, we'll fall back onto the GET approach
        """

        self.host_desc = cfg.get("host_desc")
        self.auth = get_auth(cfg)
        self.logger = logger

        self.rest_log = None

        self.session = requests_retry_session()
        if cmdlog is not None:
            log_dir = Path(cmdlog).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            self.rest_log = open(cmdlog, "wt")

        if self.host_desc is None:
            self.host_desc = "No Description"

        self.idcache = idcache

        # URL associated with the host. If it's a non-standard port, use appropriate URL:XXXXX format
        self.target_service_url = cfg.get("target_service_url")

        self.is_valid = False
        self._client = (
            None  # Cache the client so we don't have to rebuild it between calls
        )

        self.is_valid = self.auth is not None

        # Make the host desc suitable for filenames
        self.host_desc = self.host_desc.replace("/", "-").replace(" ", "_").lower()

        # will remain None until a bundle file is initialized
        self.bundle = None

        if self.idcache is not None:
            self.idcache.load_ids_from_host(self, exit_on_dupes=exit_on_dupes)

            print("Cache loaded")

    def logwrite(self, method, url, response, **kwargs):
        if self.rest_log:
            if method in FhirClient.resource_logging["methods"]:
                logentry = {
                    "method": method,
                    "url": url,
                    "timestamp": str(datetime.now()),
                    "response": response,
                }
                for k, v in kwargs.items():
                    if k not in FhirClient.resource_logging["skipped_params"]:
                        logentry[k] = v
                self.rest_log.write(dumps(logentry, sort_keys=True, indent=2) + "\n")

    def init_log(self):
        """make sure this uses the current logging, which probably changes based on user's input"""
        self.logger = logging.getLogger(__name__)

    def init_bundle(self, bundle_filename, bundle_id):
        self.bundle = open(bundle_filename, "wt")
        self.bundle.write(
            """{
    "resourceType": "Bundle",
    "id": \""""
            + bundle_id
            + """\",
    "type": "transaction",
    "entry": [
"""
        )
        self.write_comma = False

    def write_to_bundle(self, resource):
        response = deepcopy(resource)
        if self.bundle:
            # For now, let's just skip the ID so that it works in a more general sense
            destination = f"{resource['resourceType']}"  # /{resource['id']}"
            if self.write_comma:
                self.bundle.write(",")
            self.write_comma = True
            resource_data = dumps(resource)
            full_url = f"""{self.target_service_url}/{resource['resourceType']}/{resource['id']}"""
            self.bundle.write(
                """    {
      "fullUrl": \""""
                + full_url
                + """\",
      "resource": """
                + resource_data
                + """,
      "request": {
          "method": "POST",
          "url": \""""
                + destination
                + """\"
      }
    }"""
            )
        return response

    def close_bundle(self):
        if self.bundle:
            self.bundle.write(
                """
    ]
}"""
            )
            self.bundle.close()

    def get_login_header(self, headers=None):
        """Just emulating what the fhir tools library does, but it's easy to find if we decide to add to it"""

        if headers is None:
            headers = {}

        if "Content-Type" not in headers:
            major_version = FhirClient.fhir_version.split(".")[0]
            base_fhir_headers = {
                "Content-Type": f"application/fhir+json; fhirVersion={major_version}.0"
            }
            headers.update(base_fhir_headers)
        return headers

    def delete_by_query(self, resource, qry):
        responses = []
        for response in self.get(f"{resource}?{qry}").entries:
            if "resource" in response:
                responses.append(
                    self.delete_by_record_id(resource, response["resource"]["id"])
                )
        if len(responses) == 1:
            return responses[0]
        return responses

    def send_request_(self, verb, api_path, body=None, headers=None):
        if headers is None:
            headers = {}

        # Auth requires different components of the request, depending on the
        # auth type, so we need to pass the entire
        if reqargs is None:
            reqargs = {"headers": self.get_login_header(headers)}

        self.auth.update_request_args(reqargs)

        return self.client().send_request(verb, api_path, json=body, headers=headers)

    def delete_by_record_id(self, resource, id, silence_warnings=False):
        """Just a basic delete wrapper"""
        endpoint = f"{self.target_service_url}/{resource}/{id}"
        success, result = self.send_request("delete", endpoint)
        if not success and not silence_warnings:
            with log_lock:
                self.logger.error(pformat(result))
        return result

    # TODO: Allow this function to pull the data first and merge changes in
    def update(self, resource, id, data):
        """Update the current instance by overwriting it."""
        endpoint = f"{self.target_service_url}/{resource}/{id}"

        success, result = self.send_request("put", endpoint, json=data)

        return result

    def patch(self, resource, id, data):
        """Patch in partial changes to an existing record rather than overwriting everything.

        Please note that this accepts json-patch data and not a traditional fhir record
        """
        headers = {
            "Content-Type": "application/json-patch+json",
            "Prefer": "return=representation",
        }

        endpoint = f"{self.target_service_url}/{resource}/{id}"
        success, result = self.client().send_request(
            "patch", endpoint, json=data, headers=headers
        )

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
                assert "url" in obj
                url = obj["url"]

                responses = []
                gendpoint = f"{resource}?url={url}"
                entries = self.get(gendpoint).entries
                for response in entries:

                    if "resource" in response:
                        if skip_insert_if_present:
                            return {"status_code": 201, "response": response}
                        if "id" not in obj:
                            obj["id"] = response["resource"]["id"]
                        else:
                            # Only delete if we encounter the same thing more than once
                            del_response = None
                            retry_count = 1
                            delrsp = self.delete_by_record_id(
                                resource, response["resource"]["id"]
                            )
                            fresponse = self.sleep_until(
                                gendpoint,
                                0,
                                message=f"Deleting {response['resource']['id']} / {gendpoint}",
                            )
                            if fresponse.success:
                                responses.append(fresponse)
                            else:
                                print(
                                    f"There was a problem deleting the resource, {response['resource']['id']} / {gendpoint}"
                                )

            if validate_only:
                endpoint += "/$validate"
            else:
                # The Publisher does assign ids which are used by the
                # ImplementationGuide.json resource
                if "id" in obj:
                    verb = "PUT"
                    endpoint = f"{self.target_service_url}/{resource}/{obj['id']}"

            success, result = self.send_request(verb, endpoint, json=obj)

            return result

    # WARNING- This is experimental
    def basic_post(self, command="$reindex", data=None):
        # if the command is a fully formed URL, no need to change it
        if command[0:4] == "http":
            endpoint = command

        else:
            endpoint_pieces = [self.target_service_url, command]
            sep = "/"
            if command[0] == ":":
                sep = ""

            endpoint = sep.join(endpoint_pieces)
        verb = "POST"
        # pdb.set_trace()
        success, result = self.send_request(verb, endpoint, json=data)
        print(result)
        # pdb.set_trace()

        if not success:
            print("There was a problem with the request for the GET")
            pdb.set_trace()

    def post(
        self,
        resource,
        data,
        validate_only=False,
        identifier=None,
        identifier_system=None,
        identifier_type="identifier",
        retry_count=None,
        skip_insert_if_present=False,
    ):
        """Basic POST wrapper

        validate_only will append the $validate to the end of the final url

        providing an identifier will result in querying for an existing record
        and replacing it.

        If identifier finds a match or the resource object itself contains
        an id, the endpoint will become an overwrite using PUT instead of POST"""
        objs = data

        if not isinstance(objs, list):
            objs = [data]

        for obj in objs:
            endpoint = f"{self.target_service_url}/{resource}"
            if resource == "Bundle":
                endpoint = self.target_service_url

            if validate_only:
                endpoint += "/$validate"
                # Currently assuming only one profile
                if "profile" in data["meta"]:
                    profile = data["meta"]["profile"][0]

                    endpoint = f"{endpoint}?profile={profile}"
                    print(f"Woohoo! {endpoint}")

            verb = "POST"
            if not validate_only:
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
                            obj["id"] = id
                        else:
                            pass

                    else:
                        result = self.get(f"{resource}?{identifier_type}={identifier}")
                        # If it wasn't found, then we just plan to create
                        if result.success():
                            if result.entry_count > 0:
                                print(
                                    f"get returned more than one ({result.entry_count}) resource: {identifier}"
                                )
                                # pdb.set_trace()
                                entry = result.entries[0]
                                id = entry["resource"]["id"]
                                obj["id"] = id
                                if skip_insert_if_present:
                                    # Just fake a successful create
                                    return {"status_code": 200}

                if "id" in obj and resource != "Bundle":
                    verb = "PUT"

                    endpoint = f"{self.target_service_url}/{resource}/{obj['id']}"

            if retry_count is None:
                retry_count = FhirClient.retry_post_count

            while retry_count > 0:
                success, result = self.send_request(verb, endpoint, json=obj)

                # 422 just means something was preventing it from succeeding, so
                # it could be the db hasn't caught up yet, so we'll sleep for a second and
                # try again. 409 means there is a conflict, which is probably some
                # data that is duplicated (such as ds-connect surveys that occur
                # more than once)
                if result["status_code"] not in [422, 409]:
                    retry_count = 0
                else:
                    print(f"Request failed with {result['status_code']}")
                    # pdb.set_trace()

                    sleep(1)
                    print(pformat(data))
                    print("------------------")
                    for issue in result["response"]["issue"]:
                        if issue["severity"] == "error":
                            print(pformat(issue))
                    retry_count -= 1
                    print(f"{result['status_code']} - {getIdentifier(obj)['value']}")
                    if retry_count > 0:
                        print(f"Retrying {retry_count} more times")

            return result

    def get(
        self,
        resource,
        recurse=True,
        rec_count=-1,
        raw_result=False,
        elements=None,
        headers=None,
        except_on_error=True,
    ):
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

        count = ""
        if rec_count > 0:
            count = f"?_count={rec_count}"

            if "?" in resource:
                count = f"&_count={rec_count}"

        if elements is not None:
            if "?" in resource or "?" in count:
                count = f"{count}&_elements={elements}"
            else:
                count = f"?_elements={elements}"

        if resource[0:4] == "http":
            url = f"{resource}{count}"
        else:
            url = f"{self.target_service_url}/{resource}{count}"

        success, result = self.send_request("GET", f"{url}", headers=headers)

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
            # print(content.next)
            success, result = self.send_request("GET", content.next, headers=headers)

            ExceptOnFailure(success, url, result)
            content.append(result)
        return content

    def sleep_until(
        self, endpt_orig, target_count, sleep_time=5, timeout=360, message=""
    ):
        endpt = endpt_orig

        n = 0
        while True:
            response = self.get(endpt, rec_count=-1)
            entries = response.entries

            if len(entries) > 0:
                # May (or may not) be a bundle...
                if "resourceType" in entries[0]:
                    if entries[0]["resourceType"] == "Bundle":
                        if "entry" in entries[0]:
                            entries = entries[0]["entry"]
                        else:
                            entries = []

            entry_count = len(entries)
            if "total" in response.response:
                entry_count = response.response["total"]
            if entry_count == target_count or n >= timeout:
                if n > 0:
                    print(f"{n} seconds. ")
                return response
            if n == 0:
                print(
                    f"{message} - Waiting for {target_count}. Sleeping {sleep_time}",
                    end="",
                    flush=True,
                )
            n += sleep_time
            sleep(sleep_time)
            print(".", end="", flush=True)

    # The next few methods are pulled form the KF client object. These should be
    # revisited to make sure we really need them and that they work as well as
    # they can, but for now, they are used by the send_request function.
    def _errors_from_response(self, response_body):
        """
        Comb list of issues in FHIR response and return the ones marked error
        """
        response_body = response_body or {}
        try:
            return [
                issue
                for issue in response_body.get("issue", [])
                if issue["severity"] == "error"
            ]
        except:
            print(response_body)
            # pdb.set_trace()

    def _response_content(self, response):
        """
        Try to parse response body as JSON, otherwise return the
        text version of body
        """
        try:
            resp_content = response.json()
        except decoder.JSONDecodeError:
            resp_content = response.text
        return resp_content

    def send_request(self, request_method_name, url, **request_kwargs):
        """
        Send request to the FHIR validation server. Return a tuple
        (success boolean, result dict).

        The success boolean represents whether the request was sucessful AND
        valid by the FHIR specification. The request is valid if there are no
        errors in the issues list of the response.

        The result dict looks like this:

            {
                'status_code': response.status_code,
                'response': response.json() or response.text,
                'response_headers': response.headers,
            }

        :param request_method_name: requests method name
        :type request_method_name: str
        :param url: FHIR url
        :type url: str
        :param request_kwargs: optional request keyword args
        :type request_kwargs: key, value pairs
        :returns: tuple of the form
        (success boolean, result dict)
        """
        success = False

        headers = self.get_login_header(headers=request_kwargs.get("headers"))

        # EST 2025-05-13
        # Holding off on adding the security labels until we meet with a larger
        # group to discuss these issues
        # SECURITY_LABEL
        # https://smilecdr.com/docs/fhir_repository/updating_data.html#tag-retention
        headers["X-Meta-Snapshot-Mode"] = "TAG, PROFILE"        
        request_kwargs["headers"] = headers
        self.auth.update_request_args(request_kwargs)

        # Send request
        request_method = getattr(self.session, request_method_name.lower())

        response = request_method(url, **request_kwargs)
        resp_content = self._response_content(response)

        # Determine success and log result
        request_method_name = request_method_name.upper()
        request_url = urllib.parse.unquote(response.url)

        if response.ok:
            errors = self._errors_from_response(resp_content)
            if not errors:
                success = True
                self.logwrite(
                    request_method_name, url, response.status_code, **request_kwargs
                )
                self.logger.info(f"{request_method_name} {request_url} succeeded. ")
            else:
                self.logwrite(request_method_name, url, errors, **request_kwargs)
                print(request_kwargs["json"])
                self.logger.error(f"{request_method_name} {request_url} failed. ")
        else:
            self.logwrite(
                request_method_name, url, response.status_code, **request_kwargs
            )
            self.logwrite(request_method_name, url, resp_content, **request_kwargs)

            if request_method_name.lower() == "POST":
                print(
                    pformat(
                        f"There was an issue with the POST: \n{request_kwargs['json']}"
                    )
                )
                print(pformat(response.json()))
            self.logger.error(
                f"{request_method_name} {request_url} failed, "
                f"status {response.status_code}. "
            )

        return (
            success,
            {
                "status_code": response.status_code,
                "request_url": request_url,
                "response": resp_content,
                "response_headers": response.headers,
            },
        )

    def send_raw_request(self, verb, url, header, data=None, parameters=None):
        request_kwargs = {"headers": self.get_login_header(headers=header)}
        self.auth.update_request_args(request_kwargs)
        headers = request_kwargs["headers"]

        curlit = ["curl -X POST"]
        for header in headers:
            curlit.append(f" -H '{header}: {headers[header]}'")
        curlit.append(f"--data {data}")
        curlit.append(url)
        print("-----------------------")
        print(" ".join(curlit))
        print("-----------------------")
        print(headers)
        print(data)
        print(headers)
        response = self.session.request(verb, url, headers=headers, json=data)
        resp_content = self._response_content(response)
        print(resp_content)

        return resp_content


def exec():
    host_config = get_host_config()
    # Just capture the available environments to let the user
    # make the selection at runtime
    env_options = sorted(host_config.keys())

    parser = ArgumentParser(description="Basic FHIR Query tool. ")
    parser.add_argument(
        "--host",
        choices=env_options,
        default=None,
        required=True,
        help=f"Remote configuration to be used to access the FHIR server. If no environment is provided, the system will stop after generating the whistle output (no validation, no loading)",
    )
    parser.add_argument(
        "--out",
        "-o",
        type=FileType("wt"),
        help=f"Output log (will be JSON file format) for resources matching queries. If not provided, the output is only streamed to standard out.",
    )

    parser.add_argument(
        "-q",
        "--query",
        action="append",
        type=str,
        help="A query to pass to the host. You need only the portion starting with the resource type. ",
    )

    args = parser.parse_args(sys.argv[1:])
    fhir_client = FhirClient(host_config[args.host])

    print(f"FHIR Server: {fhir_client.target_service_url}")

    out_log = args.out
    if out_log is None:
        out_log = sys.stdout
    if args.out is not None:
        out_log.write("[\n  ")
        dump(
            {
                "FHIR Server": fhir_client.target_service_url,
                "Time Stamp": str(datetime.now()),
            },
            out_log,
            indent=2,
        )
        out_log.write(",\n  ")

    do_continue = True
    query_count = 0

    while do_continue:
        try:
            if args.query is None or len(args.query) == 0:
                qry = input("FHIR Query (or 'exit'): ")
                do_continue = qry.lower() != "exit"
            else:
                qry = args.query[query_count]

            if do_continue:
                start_time = datetime.now()
                # pdb.set_trace()
                response = fhir_client.get(qry, except_on_error=False)
                query_time = datetime.now()

                if args.out is not None:
                    if query_count > 0:
                        out_log.write(",\n")
                    out_log.write("  ")

                if response.success():
                    dump(
                        {
                            "Query": qry,
                            "Query Time": str(query_time - start_time),
                            "Time Stamp": str(datetime.now()),
                            "Status Code": response.status_code,
                            "Record Count": len(response.entries),
                            "Entries": response.entries,
                        },
                        out_log,
                        indent=2,
                    )
                    if args.out is not None:
                        print(response.entries[0:2])
                        print(f"Total Responses: {len(response.entries)}")
                else:
                    dump(
                        {
                            "Query": qry,
                            "Query Time": str(query_time - start_time),
                            "Time Stamp": str(datetime.now()),
                            "Status Code": response.status_code,
                            "Response": response.response,
                        },
                        out_log,
                        indent=2,
                    )
                    print(f"ERROR: {response.response['issue']}")
                query_count += 1

        except:
            do_continue = False

    if args.out:
        out_log.write("\n]\n")
