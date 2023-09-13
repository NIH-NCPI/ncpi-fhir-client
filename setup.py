from pathlib import Path
from setuptools import setup, find_packages

version = {}
with open("ncpi_fhir_client/version.py") as fp:
    exec(fp.read(), version)

req_file = Path(__file__).parent / "requirements.txt"
requirements = open(req_file).read().splitlines()

setup(
    name="ncpi-fhir-client",
    version=version["__version__"],
    description=f"NCPI FHIR Client {version['__version__']}",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    entry_points={"console_scripts": ["fhirq = ncpi_fhir_client.fhir_client:exec"]},
)
