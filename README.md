# ncpi-fhir-client
Provide basic fhir client with built-in modular authentication

This is largely a wrapper around the ncpi-fhir-utility client module, with a few convenience functions as well as a modular authentication scheme which should allow users to seamlessy run the same programs against different fhir platforms with no code changes. 

# Developing auth modules
The design assumes that the modules need only append some entries to the request's headers. What those entries are and how the data that is added is up to the individual authorization schemes. 

## Convention Based Discovery
The rules are pretty simple: 
* Each module should be added to the ncpi_fhir_client.fhir_auth module under a snake-cased filename starting with auth_ 

* Inside the module should exist at least one class whose name is the CameCase variant of the files module name (i.e. no path, no extension). 

* This class doesn't need to be derived from any particular base class, but it must provide the following interface: 
	* Constructor -- accepts a dict file containing all configuration settings (as well as settings that may not specifically apply to the authorization)
	* update_request_args function -- This should accept one argument, the request's arguments as a dictionary. The function will update whichever arguments are appropriate such as key/values inside the 'headers' or possibly adding information to the 'auth' component.

# Creating an Auth Object
To instantiate an auth object, the function, ncpi_fhir_client.fhir_auth.get_auth will accept the config object which contains all necessary parameters to build desired object, but also the additional key, 'auth_type'. The value found for that key must match one of the auth module's snake case names. This will be used to instantiate to correct object. 
