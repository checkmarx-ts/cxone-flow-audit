# CxOneFlow Audit Tool

This is a command line tool that can be used to audit, configure, and de-configure [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow) event web hooks in an SCM.

This currently only works with Azure DevOps Cloud and Enterprise.

## Installation

Python 3.9+ is required to install and execute `cxoneflow-audit`.  Installation can be performed using `pip` to download
and install the Python package with a command similar to the following:

```
pip install https://github.com/checkmarx-ts/cxone-flow-audit/releases/download/X.X.X/cxoneflow_audit-X.X.X-py3-none-any.whl
```

Please visit the [GitHub Releases](https://github.com/checkmarx-ts/cxone-flow-audit/releases)
to obtain the URL of the latest release binary.


## Executing

There are 3 functions that can be performed by `cxoneflow-audit`:

* Audit: This creates a CSV file showing configuration status for [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow) webhooks.
* Deploy: Deploys required configurations for [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow) webhooks.
* Remove: Removes deployed configurations for [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow) webhooks.

After installation, executing the command `cxoneflow-audit -h` will show detailed help.

The audit function is limited to reading service hook configuration.  It is suggested to
review the audit output before using the deploy or remove functions.

### General Configuration Options

The general options are used for all operations.

#### Informational Options
|Option|Description|
|-|-|
|`-h` or `--help`|Show detailed help and exit.|
|`-v` or `--version`|Show the `cxoneflow-audit` release version and exit.|


#### Logging Options

|Option|Optional|Description|
|-|-|-|
|`--level LOGLEVEL`|Y|Logging output level, defaults to `INFO`.<br>Can be set to: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`|
|`--log-file LOGFILE`|Y|A file where logs are written in addition to displaying logs on the console.|
|`-q`|Y|Do not output logs on the console.|

#### Runtime and Networking Options

|Option|Optional|Description|
|-|-|-|
|`-t THREADS`|Y| The number of concurrent SCM read/write operations. [default: 4]|
|`-k`|Y|Ignore SSL verification failures.|
|`--proxy PROXY_URL`|Y|A proxy server to use for communication.|

#### Filtering Options

These options are mutually exclusive.

|Option|Optional|Description|
|-|-|-|
|`--match-regex M_REGEX`|Y|Regular expression that matches projects/orgs that should be configured to send events to [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow).|
|`--skip-regex S_REGEX`|Y|Regular expression that matches projects/orgs that *should not* be configured to send events to [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow).|

#### CxOneFlow Endpoint Options

|Option|Optional|Description|
|-|-|-|
|`--cx-url CX_URL`|N| The base URL for the [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow) endpoint (e.g. https://cxoneflow.corp.com)|

#### SCM Options

|Option|Optional|Description|
|-|-|-|
|`--pat PAT`|N|An SCM PAT with appropriate privileges to execute the selected `cxoneflow-audit` function.|
|`--pat-env`|N|Obtain the PAT from the environment variable `CX_PAT` instead of providing it on the command line with `--pat`.|
|`--scm-url URL`|N|The URL to the SCM instance.|

SCM URL Examples:                             
* ADO Cloud: https://dev.azure.com
* ADO Enterprise: https://ado.corp.com


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

### Deploy (`--deploy`)

This function sets the webhook configurations on the targets specified. The
options `--skip-regex` and `--match-regex` can control which targets are selected
for deployment.

|Option|Optional|Description|
|-|-|-|
|`--cx-url CX_URL`|N| The base URL for the [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow) endpoint (e.g. https://cxoneflow.corp.com)|
|`--replace`|Y| This forces any existing service hook definitions to be deleted and replaced.|
|`--shared-secret SECRET`|See Note|The shared secret configured in the service hook.
|`--shared-secret-env`|See Note|Obtain the shared secret from the environment variable `CX_SECRET`

Note: One of `--shared-secret` or `--shared-secret-env` is required when using the `--deploy`
function.

### Remove (`--remove`)

This function removes the webhook configurations from the targets specified. The
options `--skip-regex` and `--match-regex` can control which targets are selected
for deployment.


### Azure DevOps (`ado TARGETS...`)

The option `ado TARGETS...` indicates the operation is performed against collections
configured in an Azure DevOps cloud or enterprise instance.
The `TARGETS...` are one or more collections found at the instance URL.  (e.g. `DefaultCollection`, `Corp`, etc).  Service hooks are applied to each project
found in the specified collection.

Projects can be omitted by using the `--skip-regex` option or limited to certain projects
by using the `--match-regex` option.

## SCM Specific Information

### Azure DevOps

Modifying and reading service hook settings is an administrative function.  The user that owns the PAT
must be in the `Project Collection Administrators` group.  The PAT that is used by [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow)
does not need to be in an administrative group.

The PAT used when invoking `cxoneflow-audit` must have these minimum permissions:

* Build::Read
* Code::Read
* Project and Team::Read
* Service Connections::Read & Query

For the following examples, assume there is an Azure DevOps Enterprise instance located at `https://ado.corp.com`
with the following collections defined:

![ADO collections](img/ado_collections.png)

#### Audit Example

An example command line to perform the audit function would be similar to:

```
cxoneflow-audit --cx-url https://cxoneflow.corp.com \
  --pat <your PAT> \
  --scm-url https://ado.corp.com \
  --audit \
  ado DefaultCollection EastCoast WestCoast
```

The default output file `./cxoneflow.csv` would be generated containing the
webhook configuration disposition for all projects found in collections
**DefaultCollection**, **EastCoast**, and **WestCoast**.

A similar example that limits the audit to projects found in the specified collections
that begin with either "New York" or "Los Angeles":

```
cxoneflow-audit --cx-url https://cxoneflow.corp.com \
  --pat <your PAT> \
  --scm-url https://ado.corp.com \
  --match-regex '^New.York|^Los.Angeles' \
  --audit \
  ado DefaultCollection EastCoast WestCoast
```

Note the single-quotes surrounding the regular expression.

This example is similar but will only audit projects that
*do not* begin with "New York" or "Los Angeles":

```
cxoneflow-audit --cx-url https://cxoneflow.corp.com \
  --pat <your PAT> \
  --scm-url https://ado.corp.com \
  --skip-regex '^New.York|^Los.Angeles' \
  ado DefaultCollection EastCoast WestCoast
```

#### Deployment Example

To deploy service hook configurations that point to the [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow) endpoint `https://cxoneflow.corp.com` in **all** projects under the target collections, 
the command line would be similar to the following example:

```
cxoneflow-audit --cx-url https://cxoneflow.corp.com \
  --pat <your PAT> \
  --scm-url https://ado.corp.com \
  --deploy --shared-secret <secret> \
  ado DefaultCollection EastCoast WestCoast
```

In the below example, the service hooks would be deployed only to projects
beginning with "New York" or "Los Angeles":

```
cxoneflow-audit --cx-url https://cxoneflow.corp.com \
  --pat <your PAT> \
  --scm-url https://ado.corp.com \
  --match-regex '^New.York|^Los.Angeles' \
  --deploy --shared-secret <secret> \
  ado DefaultCollection EastCoast WestCoast
```

Note the single-quotes surrounding the regular expression.

The example below is similar but will only deploy service hooks to projects that
*do not* begin with "New York" or "Los Angeles":

```
cxoneflow-audit --cx-url https://cxoneflow.corp.com \
  --pat <your PAT> \
  --scm-url https://ado.corp.com \
  --skip-regex '^New.York|^Los.Angeles' \
  --deploy --shared-secret <secret> \
  ado DefaultCollection EastCoast WestCoast
```

#### Remove Example

To remove **all** service hook configurations that point to the [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow) endpoint `https://cxoneflow.corp.com`,
the command line would be similar to the following example:

```
cxoneflow-audit --cx-url https://cxoneflow.corp.com \
  --pat <your PAT> \
  --scm-url https://ado.corp.com \
  --remove
  ado DefaultCollection EastCoast WestCoast
```

In the below example, the service hooks would be removed only from projects
beginning with "New York" or "Los Angeles":

```
cxoneflow-audit --cx-url https://cxoneflow.corp.com \
  --pat <your PAT> \
  --scm-url https://ado.corp.com \
  --match-regex '^New.York|^Los.Angeles' \
  --remove
  ado DefaultCollection EastCoast WestCoast
```

Note the single-quotes surrounding the regular expression.

The example below is similar but will only remove service hooks from projects that
*do not* begin with "New York" or "Los Angeles":

```
cxoneflow-audit --cx-url https://cxoneflow.corp.com \
  --pat <your PAT> \
  --scm-url https://ado.corp.com \
  --skip-regex '^New.York|^Los.Angeles' \
  --remove \
  ado DefaultCollection EastCoast WestCoast
```


## Troubleshooting

### Azure DevOps

#### Turn on Debug

Use the `--level DEBUG` option to turn on debug output.  Capture the debug log if it is necessary to request
help from Checkmarx Professional Solutions.

#### The audit CSV shows nothing is configured but service hook configurations can be observed.

Check the following:

* The user that owns the PAT is in the `Project Collection Administrators` group for each target collection.
* The PAT has appropriate permissions as specified in [Azure DevOps](#azure-devops).
* The [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow) URL is the base URL for the [CxOneFlow](https://github.com/checkmarx-ts/cxone-flow) endpoint (e.g. without the `/adoe` route at the end)

#### Some, but not all, of the webhook events are rejected by CxOneFlow.

The shared secret that is configured with some service hook configurations may be wrong
or outdated.  Deploy the service hooks while using the `--replace` option to force
the service hook definitions to be updated with the current shared secret.
