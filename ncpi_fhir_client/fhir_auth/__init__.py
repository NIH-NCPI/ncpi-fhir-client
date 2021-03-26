"""Provide a function to identify authentication schemes available at runtime and instantiatiate an appropriate object based on the configuration details provided"""
import logging
logger = logging.getLogger(__name__)

from pathlib import Path
from importlib import import_module

def camelize(val):
    """Convert a snake-case filename to it's CameCase object name"""
    return val.title().replace("_", "")

# Cache the authentication modules in case we need to generate more than one
_authentication_modules = None

def get_modules():
    """Return the available auth modules, scanning the fhir_auth directory if necessary to find all modules."""
    global _authentication_modules

    # We'll cache the scan to avoid having to redo this work over again
    if _authentication_modules is None:
        _authentication_modules = {}
        # Discover all of the authentication modules
        mod_dir = Path(__file__).parent

        module_files = mod_dir.glob("auth_*.py")
        for module in module_files:
            # IDs are just the name of the module's filename without path or extension
            module_id = module.stem
            module_name = f"ncpi_fhir_client.fhir_auth.{module_id}"
            mod = import_module(module_name)

            # The class is presumed to be the camelcase version of the filename 
            # TODO Decide if its better to drop the Auth from those camel case classnames?
            module_class_name = camelize(module_id)
            auth_class = getattr(mod, module_class_name)

            # Add the class to the cache so that we can instantiate it if need be
            _authentication_modules[module_id] = auth_class

        logging.info(f"{len(_authentication_modules)} auth modules found.")
    return _authentication_modules

def get_auth(cfg):
    """return an apprpriate authorization object based on the details inside cfg"""
    assert('auth_type') in cfg, "host configuration must have a valid auth_type associated with it"

    modules = get_modules()
    assert(cfg['auth_type'] in modules), f"The auth_type indicated, {cfg['auth_type']}, is unknown"

    # Instantiate the requested object
    return modules[cfg['auth_type']](cfg)

