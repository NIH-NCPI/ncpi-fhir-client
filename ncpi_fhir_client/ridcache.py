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
import re
from collections import defaultdict
from argparse import ArgumentParser, FileType

# The get_id will be run inside a thread, so I guess we need to protect it...not really sure
# if the read can be interrupted. Probably not but it should be reasonably fast. 
from threading import Lock

from wstlr.hostfile import load_hosts_file

import pdb

cache_lock = Lock()

# We are treating CodeSystems and ValueSets differently, so let's not bother caching those
_default_resource_types = [
    'ObservationDefinition',
    'ActivityDefinition',
    'Patient',
    'Condition',
    'Observation',
    'Specimen',
    'ResearchSubject',
    'ResearchStudy'
]

class RIdCache:
    def __init__(self, resource_types = None, valid_patterns = None):
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

        if valid_patterns is not None:
            for pattern in valid_patterns:
                self.valid_patterns.append(re.compile(pattern, re.I))
        # pdb.set_trace()
        if self.resource_types is None:
            self.resource_types = _default_resource_types

        # resourceType=>system=>value = ID
        self.cache = defaultdict(lambda: defaultdict(dict))

        self.missing_identifiers = defaultdict(list)
    
    def load_ids_from_host(self, fhir_client):
        """
        Loads ids from the host via the client object and stores them inside the cache
        
        :param fhirclient: the FHIR client that will be used to query data
        :type fhirclient: FhirClient
        """
        for resource_type in self.resource_types:
            self.load_ids_for_resource_type(fhir_client, resource_type)

        if len(self.missing_identifiers) > 0:
            print("\n** Some resourceTypes had records without valid identifiers:")
            for resourceType in self.missing_identifiers.keys():
                print(f"\t{resourceType} : {len(self.missing_identifiers[resourceType])}")

    def valid_system(self, target_system):
        if len(self.valid_patterns) == 0:
            return True
        
        for pattern in self.valid_patterns:
            if pattern.search(target_system):
                return True
        return False

    def load_ids_for_resource_type(self, fhir_client, resource_type):
        result = fhir_client.get(f"{resource_type}?_elements=identifier,id&_count=200")
        record_count = 0
        if result.success():
            for entity in result.entries:
                resource = entity['resource']
                
                target_id = resource['id']
                try:
                    target_system = resource['identifier'][0]['system']
                    if self.valid_system(target_system):
                        entity_key = resource['identifier'][0]['value']
                        self._store_id(resource_type, target_system, entity_key, target_id)
                        record_count += 1
                except:
                    self.missing_identifiers[resource_type].append(resource)
        print(f"{record_count} ids found for {resource_type}")


    def get_id(self, target_system, entity_key, resource_type=None):
        """
        Retrieve the target service ID for a given source unique key.

        :param target_system: the system associated with the key identifier (first)
        :type target_system: str
        :param entity_key: source unique key for this entity
        :type entity_key: str
        """
        result = self.cache[target_system].get(entity_key)

        if resource_type is not None and result is not None:
            assert resource_type == result[0], f"{resource_type} != {result[0]}"

            return result[1]
        return result

    def store_id(
        self, entity_type, target_system, entity_key, target_id, no_db=False
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
            self._store_id(entity_type, target_system, entity_key, target_id)

    def _store_id(
        self, entity_type, target_system, entity_key, target_id
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
        self.cache[target_system][entity_key] = (entity_type, target_id)

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
