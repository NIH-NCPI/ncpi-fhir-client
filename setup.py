import os
from setuptools import setup, find_packages

from ncpi_fhir_client import __version__

"""root_dir = os.path.dirname(os.path.abspath(__file__))
req_file = os.path.join(root_dir, "requirements.txt")
with open(req_file) as f:
    requirements = f.read().splitlines()"""
setup(
    name="ncpi-fhir-client",
    version = __version__,
    description=f"NCPI FHIR Client {__version__}",
    packages=find_packages(),
    include_package_data=True,
    install_requires=["requests", "jwt"]
)
