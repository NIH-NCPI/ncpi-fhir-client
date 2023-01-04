from pathlib import Path
from setuptools import setup, find_packages

from ncpi_fhir_client import __version__

req_file = Path(__file__).parent / "requirements.txt" 
requirements = open(req_file).read().splitlines()

setup(
    name="ncpi-fhir-client",
    version = __version__,
    description=f"NCPI FHIR Client {__version__}",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements
)
