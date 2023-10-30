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

# fhirq - CLI FHIR Query 
''fhirq'' is a simple command-line utility that can be used to run queries against a FHIR server with a valid host entry inside the current directory's ''fhir_hosts'' file. The utility employs the ncpi_fhir_client to handle authentication for you, so as long as your fhir_hosts file is up to date with any necessary credentials, it will run the queries and return the results. 

## Hosts File
The file, ''fhir_hosts'', is integral for NCPI FHIR Client to work. It provides all the necessary information for the client to a) Find the server (target service URL), b) recognize the authorization scheme and c) relevant credentials required for authorization. By putting these details into a file, applications using the NCPI FHIR Client can abstract away details relating to the server itself and focus on whatever it is they are intended to do. 

This file is a simple YAML configuration file and can have as many ''hosts'' as the user needs. For instance, for one of my NCPI Whistler projects, I have 7 different entries: 1 local dev, 3 v1 servers (DEV/QA/PROD) and 3 v2 servers (DEV/QA/PROD). Each of the 3 v1 and v2 servers have different login details (v1 and v2 authorization schemes are very different as well). By keeping this information together in the one file, I simply change a single argument in my command line call and it knows which server to use and how to gain authorization to load the data into the server. 

When you run fhirq inside a directory where there is no ''fhir_hosts'' file, it will pull together an example entry for each of the current authorization schemes and stream it to stdout. You can redirect this to the file, ''fhir_hosts'' in your current working directory and find the appropriate entry that matches your server's authorization scheme and provide the correct details (and deleting all of the others). 

For more information about the ''fhir_hosts'' file, please see it's entry in the [NCPI Whistler tutorial](https://nih-ncpi.github.io/ncpi-whistler/#/?id=fhir-hosts). 

### Security Concerns with fhir_hosts
Because the fhir_hosts file may refer to local files (such as google service token JSON files), secrets or username/passwords, they should NEVER get checked into a version control repository. Typically, the first thing I do when I start a new project is add the fhir_hosts file to my .gitignore file (along with some other things). 

## Queries
There are two ways to run queries using fhirq, via one or more queries provided using the --query (-q) option, or interactively. Queries do not require the entire endpoint URL, only the portion of the query starting with the ResourceType: So, to query for a specific patient, your "query" might be something like: 
>Patient/12345

Where the patient resource's id is 12345. 

If no --query arguments are provided, the application provides an input box into which the user should enter queries, each separated by the return. The example above is considered a single query. To exit the interactive query loop, simply type 'exit' or return with no text. 

When providing queries on the command line using the --query argument, keep in mind that spaces are generally considered to be relevant argument delimiters. So, if your query contains spaces, they should either be escaped or the entire query should be enclosed in double quotes.

The queries can be complex, however, do keep in mind that characters other than the space may be interpreted by the shell, such as the '&'. In general, I recommend enclosing anything other than the most basic queries in quotes, or using the interactive shell. 

## Output
By default, the results of the queries are streamed to stdout (dumped directly to your terminal's output). However, if you want to direct them to a log, provide a filename for the "--out" (-o) argument. This will create a JSON object containing details about each query including how long the query took to run, the query itself and the results (called "entries"). The first 2 "entries" are also sent to your terminal's display in addition to the file. 


