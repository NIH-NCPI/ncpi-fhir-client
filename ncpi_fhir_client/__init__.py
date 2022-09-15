import pdb

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
    