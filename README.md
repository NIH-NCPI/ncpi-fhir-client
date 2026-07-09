# ncpi-fhir-client

[![Tests](https://github.com/NIH-NCPI/ncpi-fhir-client/actions/workflows/tests.yml/badge.svg)](https://github.com/NIH-NCPI/ncpi-fhir-client/actions/workflows/tests.yml)
[![GitHub release](https://img.shields.io/github/v/release/NIH-NCPI/ncpi-fhir-client)](https://github.com/NIH-NCPI/ncpi-fhir-client/releases)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](pyproject.toml)

A lightweight FHIR client with pluggable, convention-discovered authentication. It lets tools built on top of it (like [NCPI Whistler](https://github.com/NIH-NCPI/ncpi-whistler)) run the same code unchanged against FHIR servers with completely different auth schemes — Basic Auth, GCP OAuth2, GCP target-service tokens, Kids First's cookie-based auth, and Kids First OpenID — just by pointing at a different entry in a `fhir_hosts` config file.

## Quick Start

```bash
pip install .
```

```python
from ncpi_fhir_client.host_config import get_host_config
from ncpi_fhir_client.fhir_client import FhirClient

host_config = get_host_config()  # reads ./fhir_hosts
client = FhirClient(host_config["dev"])

result = client.get("Patient/12345")
if result.success():
    print(result.entries)
```

Or use the bundled CLI, `fhirq`, to query a server without writing any code — see [fhirq below](#fhirq---cli-fhir-query).

If there's no `fhir_hosts` file yet in the current directory, both the library and `fhirq` will print an example configuration (one entry per available auth module) to help you get started.

## Auth Modules

Authentication is pluggable and discovered by convention rather than registered explicitly — drop a new module in and it's picked up automatically:

* Each module lives in `ncpi_fhir_client.fhir_auth`, in a snake_case file starting with `auth_` (e.g. `auth_basic.py`).
* The module must contain a class named for the CamelCase version of the filename (e.g. `auth_basic.py` → `AuthBasic`).
* That class doesn't need to derive from any base class, but must structurally satisfy `ncpi_fhir_client.fhir_auth.AuthModule`:
  * `__init__(self, cfg)` — accepts the host's full config dict (including keys unrelated to auth).
  * `update_request_args(self, request_args)` — mutates the outgoing request's kwargs (e.g. `headers`, `auth`) as needed.
  * `example_config(cls, writer, other_entries)` — a classmethod that writes a sample `fhir_hosts` entry, used to generate the example configuration mentioned above.

To instantiate the right auth object for a host, call `ncpi_fhir_client.fhir_auth.get_auth(cfg)`. It reads `cfg['auth_type']`, matches it against the discovered module names, and instantiates the corresponding class.

## fhirq - CLI FHIR Query
__fhirq__ is a simple command-line utility that can be used to run queries against a FHIR server with a valid host entry inside the current directory's __fhir_hosts__ file. The utility employs the ncpi_fhir_client to handle authentication for you, so as long as your fhir_hosts file is up to date with any necessary credentials, it will run the queries and return the results.

### Hosts File
The file, __fhir_hosts__, is integral for NCPI FHIR Client to work. It provides all the necessary information for the client to a) Find the server (target service URL), b) recognize the authorization scheme and c) relevant credentials required for authorization. By putting these details into a file, applications using the NCPI FHIR Client can abstract away details relating to the server itself and focus on whatever it is they are intended to do.

This file is a simple YAML configuration file and can have as many __hosts__ as the user needs. For instance, for one of my NCPI Whistler projects, I have 7 different entries: 1 local dev, 3 v1 servers (DEV/QA/PROD) and 3 v2 servers (DEV/QA/PROD). Each of the 3 v1 and v2 servers have different login details (v1 and v2 authorization schemes are very different as well). By keeping this information together in the one file, I simply change a single argument in my command line call and it knows which server to use and how to gain authorization to load the data into the server.

When you run fhirq inside a directory where there is no __fhir_hosts__ file, it will pull together an example entry for each of the current authorization schemes and stream it to stdout. You can redirect this to the file, __fhir_hosts__ in your current working directory and find the appropriate entry that matches your server's authorization scheme and provide the correct details (and deleting all of the others).

For more information about the __fhir_hosts__ file, please see its entry in the [NCPI Whistler tutorial](https://nih-ncpi.github.io/ncpi-whistler/#/?id=fhir-hosts).

#### Security Concerns with fhir_hosts
Because the fhir_hosts file may refer to local files (such as google service token JSON files), secrets or username/passwords, they should NEVER get checked into a version control repository. Typically, the first thing I do when I start a new project is add the fhir_hosts file to my .gitignore file (along with some other things).

### Queries
There are two ways to run queries using fhirq, via one or more queries provided using the --query (-q) option, or interactively. Queries do not require the entire endpoint URL, only the portion of the query starting with the ResourceType: So, to query for a specific patient, your "query" might be something like:
>Patient/12345

Where the patient resource's id is 12345.

If no --query arguments are provided, the application provides an input box into which the user should enter queries, each separated by the return. The example above is considered a single query. To exit the interactive query loop, simply type 'exit' or return with no text.

When providing queries on the command line using the --query argument, keep in mind that spaces are generally considered to be relevant argument delimiters. So, if your query contains spaces, they should either be escaped or the entire query should be enclosed in double quotes.

The queries can be complex, however, do keep in mind that characters other than the space may be interpreted by the shell, such as the '&'. In general, I recommend enclosing anything other than the most basic queries in quotes, or using the interactive shell.

### Output
By default, the results of the queries are streamed to stdout (dumped directly to your terminal's output). However, if you want to direct them to a log, provide a filename for the "--out" (-o) argument. This will create a JSON object containing details about each query including how long the query took to run, the query itself and the results (called "entries"). The first 2 "entries" are also sent to your terminal's display in addition to the file.

## Development

```bash
pip install -e ".[test]"
pytest
```

Type hints are being added incrementally, module by module. Checked modules are enforced in CI via `mypy`; run it locally with:

```bash
pip install -e ".[dev]"
mypy
```
