import pdb


import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import traceback
import sys

from pathlib import Path
from yaml import safe_load
from rich import print

__version__ = "0.1.1"

_default_resources = None

# Google seems to respond with some resources that it doesn't support queries for, 
# so, since we are in a bit of a hurry, I'm just stashing those types here until
# I can dig deeper into a possible way to identify resources that aren't queryable
_invalid_resource_types = ['DomainResource', 'Resource']
import pdb

def default_resources(host, ignore_resources=['Bundle'], reset=False):
    global _default_resources 

    if reset or (_default_resources is not None and len(_default_resources) == 0):
        _default_resources = None

    if _default_resources is None:
        response = host.get("metadata")
        _default_resources = []

        cs = response.entries[0]
        for restful_entry in cs['rest']:
            if 'resource' in restful_entry:
                for resource in restful_entry['resource']:
                    # pdb.set_trace()
                    if resource['type'] not in _invalid_resource_types:
                        _default_resources.append(resource['type'])

    return [x for x in _default_resources if x not in ignore_resources]

def report_exception(ex, msg):
    tb_lines = traceback.format_exception(ex.__class__, ex, ex.__traceback__)
    tb_text = ''.join(tb_lines)
    print(tb_text)
    print(f"\n\n{msg}")
    sys.exit(1)

# Stolen from KF FHIR Utility: 
def requests_retry_session(
    session=None,
    total=10,
    read=10,
    connect=1,
    status=10,
    backoff_factor=5,
    status_forcelist=(500, 502, 503, 504),
):
    """
    Send an http request and retry on failures or redirects

    See urllib3.Retry docs for details on all kwargs except `session`
    Modified source: https://www.peterbe.com/plog/best-practice-with-retries-with-requests # noqa E501

    :param session: the requests.Session to use
    :param total: total retry attempts
    :param read: total retries on read errors
    :param connect: total retries on connection errors
    :param status: total retries on bad status codes defined in
    `status_forcelist`
    :param backoff_factor: affects sleep time between retries
    :param status_forcelist: list of HTTP status codes that force retry
    """
    session = session or requests.Session()

    retry = Retry(
        total=total,
        read=read,
        connect=connect,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        method_whitelist=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

def die_if(do_die, msg, errnum=1):
    if do_die:
        sys.stderr.write(msg + "\n")
        sys.exit(errnum)
