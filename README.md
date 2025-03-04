# CxOneFlow Audit Tool

This tool can be used to audit, configured, and de-configure CxOneFlow event web hooks in an SCM.

This currently only works with Azure DevOps Cloud and Enterprise.

## Installation

Coming soon...

## Executing

TODO: Show help output here

### General Configuration Options

TODO

### Audit (`--audit`)

When the `--audit` parameter is selected, a CSV of configured web hooks
for the SCM is generated.  The configuration is performed at the "organization" level
(with the concept of "organization" varying by SCM) so the audit will not
show web hook configurations set on individual repositories.

Parameters that can be used with `--audit`:

|Parameter|Optional|Description|
|-|-|-|
| `--outfile CSVFILE` |Y|If provided, sets the path to the CSV file created.  Default: ./cxoneflow.csv |
| `--no-config` |Y|The output of the CSV will contain only those organizations that are not configured or are partially configured.|


## AzureDevOps

### Audit ADO Token Permissions

**Minimum PAT Permissions**
* Build : Read
* Code : Read
* Project and Team : Read
* Service Connections : Read & Query
