""" 
Based on the assumption that the first identifier for any given resource
is going to be unique across a given FHIR server, we can trust a full 
load of all identifiers[0] => id for any ID that is present on the 
target server. This means that we can skip the GET when an ID misses
inside our normal cache. That should speed things up when it is we can
use it. 

This cache is not intended to land on the disk but to be rebuilt with
each run. The reason for that is simply because it needs to be guaranteed
to be up to date and it doesn't take too much memory for servers with 
a single largish dataset. The same may not be true for servers with 
large numbers of datasets already on board. 

"""

import sys
import os
import re
from collections import defaultdict
from argparse import ArgumentParser, FileType

from ncpi_fhir_client import default_resources, report_exception
# The get_id will be run inside a thread, so I guess we need to protect it...not really sure
# if the read can be interrupted. Probably not but it should be reasonably fast. 
from threading import Lock
from pprint import pformat
from rich import print
from rich.console import Console
from rich.table import Table
from rich.progress import track

from wstlr.hostfile import load_hosts_file

import pdb


# id_log = open("__ID_LOG.txt", 'wt')

cache_lock = Lock()
_ignored_resource_types = [
    'CodeSystem',
    'ValueSet',
    'Bundle'
]

def get_identifier(resource):
    idnt = resource.get('identifier')

    if type(idnt) is list:
        return idnt[0]
    return idnt

class DuplicateIdentifierFound(Exception):
    def __init__(self, target_system, entity_key, entity_type, target_id):
        self.target_system = target_system
        self.entity_key = entity_key
        self.entity_type = entity_type
        self.target_id = target_id
        super().__init__(self.message())

    def message(self):
        return f"""Duplicate key found for {self.target_system}:{self.entity_key} -> {self.entity_type}/{self.target_id} exists with the same key."""


class RIdCache:
    def __init__(self, study_id=None, resource_types = None, valid_patterns = None):
        """
        :param resource_types: List of FHIR Resource types expected to be encountered
        :type resource_types: List of strings
        :param valid_patterns: List of text strings which can be expected to be found in the identifiers
        :type valid_patterns: List of strings

        The client's target host will be used in the db schema to allow us 
        to use a single database for persistance. The client object itself will
        be used to grab the identities and ids from the remote host.

        If resourceTypes is None, we'll use the default list of resources
        """
        self.resource_types = resource_types
        self.valid_patterns = []
        self.study_id = study_id
        # log IDs encountered which don't conform to the whistle 
        # format 
        self.malformed_ids = set()      

        if valid_patterns is not None:
            for pattern in valid_patterns:
                self.valid_patterns.append(re.compile(pattern, re.I))
        # pdb.set_trace()

        # resourceType=>system=>value = ID
        self.cache = defaultdict(lambda: defaultdict(dict))

        self.missing_identifiers = defaultdict(list)
    
    def load_ids_from_host(self, fhir_client, exit_on_dupes=False):
        """
        Loads ids from the host via the client object and stores them inside the cache
        
        :param fhirclient: the FHIR client that will be used to query data
        :type fhirclient: FhirClient
        """

        if self.resource_types is None:
            self.resource_types = default_resources(fhir_client, ignore_resources=_ignored_resource_types)

        table = Table(title=f"Resource Loading: {fhir_client.target_service_url}")
        table.add_column("Resource Type", justify = "right", style="cyan")
        table.add_column("ID Count", justify="left", style="yellow")
        ids_found = 0
        for resource_type in track(self.resource_types, f"Loading IDs for {len(self.resource_types)} resource types"):
            try:
                id_count = self.load_ids_for_resource_type(fhir_client, resource_type, exit_on_dupes=exit_on_dupes)
                if id_count > 0:
                    table.add_row(resource_type, str(id_count))
                ids_found += id_count
            except DuplicateIdentifierFound as e:
                pdb.set_trace()
                os._exit(1)
        console = Console()
        console.print(table, justify="center")

        print(f"{len(self.resource_types)} Resource types found: {ids_found} ids.")

        if len(self.malformed_ids) > 0:
            table = Table(title=f"{len(self.malformed_ids)} malformed IDs found")
            table.add_column("system", justify = "right", style="blue")
            table.add_column("ID", justify = "right", style="yellow")
            for id in sorted(list(self.malformed_ids))[0:5]:
                system, resource_id = id.split("|")
                table.add_row(system, resource_id)
            console.print(table, justify="center")

        if len(self.missing_identifiers) > 0:
            table = Table(title=f"{len(self.missing_identifiers)} resources had missing Identifiers")
            table.add_column("Resource Type", justify = "right", style="cyan")
            table.add_column("Resource Count", justify = "left", style="yellow")

            for resourceType in self.missing_identifiers.keys():
                table.add_row(resourceType, str(len(self.missing_identifiers[resourceType])))

            console.print(table, justify="center")

    def valid_system(self, target_system):
        if len(self.valid_patterns) == 0:
            return True
        
        for pattern in self.valid_patterns:
            if pattern.search(target_system):
                return True
        return False

    def load_ids_for_resource_type(self, fhir_client, resource_type, exit_on_dupes=False):
        #print(f"{resource_type}?_tag={self.study_id}&_elements=identifier,id&_count=200")
        #if resource_type == "Observation":
        #    print("Observing the observations")
        #    pdb.set_trace()
        params = ["_elements=identifier,id","_count=200"]
        if self.study_id is not None:
            params = [f"_tag={self.study_id}"] + params
            
        params = "&".join(params)
        #result = fhir_client.get(f"{resource_type}?_tag={self.study_id}&_elements=identifier,id&_count=200")

        result = fhir_client.get(f"{resource_type}?{params}")
        #pdb.set_trace()
        record_count = 0
        if result.success():
            for entity in result.entries:
                if 'resource' not in entity:
                    print(pformat(entity))
                    pdb.set_trace()

                resource = entity['resource']
                if resource['resourceType'] != resource_type:
                    print(f"Here is an issue: {resource['resourceType']} ~= {resource_type}")
                    #pdb.set_trace()
                else:
                    target_id = resource['id']
                    try:
                        target_system = get_identifier(resource)['system']
                        if self.valid_system(target_system):
                            entity_key =get_identifier(resource)['value']
                            self.store_id(resource_type, target_system, entity_key, target_id, exit_on_dupes=exit_on_dupes)
                            record_count += 1
                    except:
                        self.missing_identifiers[resource_type].append(resource)

        return record_count


    def get_id(self, target_system, entity_key, resource_type=None):
        """
        Retrieve the target service ID for a given source unique key.

        :param target_system: the system associated with the key identifier (first)
        :type target_system: str
        :param entity_key: source unique key for this entity
        :type entity_key: str
        """
        try:
            result = self.cache[target_system].get(entity_key)
        except Exception as ex:
            report_exception(ex, msg=f"{target_system} : {entity_key}")

        if resource_type is not None and result is not None:
            assert resource_type == result[0], f"{resource_type} != {result[0]}"

            return result[1]
        return result

    def store_id(
        self, entity_type, target_system, entity_key, target_id, no_db=False, exit_on_dupes=False
    ):
        """
        Cache the relationship between a source unique key and its corresponding
        target service ID.

        :param entity_type: the name of this type of entity
        :type entity_type: str
        :param entity_key: source unique key for this entity
        :type entity_key: str
        :param target_id: target service ID for this entity
        :type target_id: str
        :param no_db: only store in the RAM cache, not in the db
        :type no_db: bool
        """
        with cache_lock:
            self._store_id(entity_type, target_system, entity_key, target_id, exit_on_dupes=exit_on_dupes)

    def _store_id(
        self, entity_type, target_system, entity_key, target_id, exit_on_dupes=False
    ):
        """
        Cache the relationship between a source unique key and its corresponding
        target service ID. This version doesn't use locks so it should not be 
        used inside a thread

        :param entity_type: the name of this type of entity
        :type entity_type: str
        :param entity_key: source unique key for this entity
        :type entity_key: str
        :param target_id: target service ID for this entity
        :type target_id: str
        :param no_db: only store in the RAM cache, not in the db
        :type no_db: bool
        """
        if target_system.split("/")[-1] != entity_type.lower():
            self.malformed_ids.add(f"{target_system}|{entity_key}")
            #print(f"Attempting to cache IDs that don't conform with Whistler format:")
            #print(f"System: {target_system}  Key: {entity_key}  Type: {entity_type} ID: {target_id}")
            #pdb.set_trace()
        
        if entity_key in self.cache[target_system]:
            if exit_on_dupes:
                sys.stderr.write(f"""Duplicate key found for {target_system}:{entity_key} 
    -> {entity_type}/{target_id} exists with the same key.\n""")
                # This is a bit harsh, but 
                os._exit(1)

        self.cache[target_system][entity_key] = (entity_type, target_id)
        # id_log.write(f"{target_system}\t{entity_key}\t{entity_type}\t{target_id}\n")

def exec():
    from ncpi_fhir_client.fhir_client import FhirClient

    host_config = load_hosts_file()

    env_options = sorted(host_config.keys())

    parser = ArgumentParser(description="Pull Identity and IDs from a FHIR server")
    parser.add_argument(
        "-e",
        "--env",
        choices=env_options,
        required=True,
        help=f"Remote configuration to be used to access the FHIR server. If no environment is provided, the system will stop after generating the whistle output (no validation, no loading)",
    )
    parser.add_argument(
        "-p", 
        "--system-pattern",
        type=str,
        action='append',
        help="Strings that identifier systems can match to be of interest. If none are provided all systems will 'match'"    
    )
    args = parser.parse_args(sys.argv[1:])

    fhir_client = FhirClient(host_config[args.env])

    idcache = RIdCache(valid_patterns=args.system_pattern)
    idcache.load_ids_from_host(fhir_client)

if __name__ == "__main__":
    exec()
