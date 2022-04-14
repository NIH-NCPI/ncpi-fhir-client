import pdb

__version__ = "0.1.1"

_default_resources = None

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
                    _default_resources.append(resource['type'])

    return [x for x in _default_resources if x not in ignore_resources]
    