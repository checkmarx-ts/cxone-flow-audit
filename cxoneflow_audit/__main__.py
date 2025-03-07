import asyncio, logging, re, os
from asyncio import Semaphore
from docopt import docopt, DocoptExit
from cxoneflow_audit.__version__ import __version__
from cxoneflow_audit.log import bootstrap
from cxoneflow_audit.scm import scm_map
from cxoneflow_audit.util import NameMatcher
import requests
# pylint: disable=E1101
requests.packages.urllib3.disable_warnings()

DEFAULT_LOGLEVEL="INFO"
PROGNAME=f"cxoneflow-audit {__version__}"

def resolve_from_env(value, env_key):
  if value is not None:
    return value
  elif env_key in os.environ.keys():
    return os.environ[env_key]
  else:
    return None


async def dispatch(args) -> int:
  concurrency = Semaphore(int(args['-t']))
  proxy = { "http" : args['--proxy'], "https" : args['--proxy']} if args['--proxy'] is not None else None

  if args['--skip-regex'] is not None:
    matcher = NameMatcher.create_as_skip(args['--skip-regex'])
  elif args['--match-regex'] is not None:
    matcher = NameMatcher.create_as_match(args['--match-regex'])
  else:
    matcher = NameMatcher.create_as_match(".*")

  if args['ado']:
    scm_key = "ado"
  else:
    raise Exception("Unknown SCM")
  
  common_args = [args['TARGETS'], concurrency, matcher, 
                  resolve_from_env(args['--pat'], 'CX_PAT'), 
                  args['--cx-url'],
                  args['--scm-url'], proxy, args['-k'] ]
  
  op = None
  if args["--audit"]:
    # pylint: disable=E1102
    op = scm_map[scm_key].Auditor(args['--outfile'], args['--no-config'], *common_args)
  elif args["--deploy"]:
    # pylint: disable=E1102
    op = scm_map[scm_key].Deployer(resolve_from_env(args['--shared-secret'], 'CX_SECRET'), args['--replace'],  *common_args)
  elif args["--remove"]:
    # pylint: disable=E1102
    op = scm_map[scm_key].Remover(*common_args)
  else:
    raise Exception("Unknown action!")
  
  return await op.execute()


async def main():
  """Usage: cxoneflow-audit [-h | --help | -v | --version] [-t THREADS]
                            [--level LOGLEVEL] [--log-file LOGFILE] [-qk] [--proxy IP:PORT]
                            [--match-regex M_REGEX | --skip-regex S_REGEX] 
                            (--audit [--outfile CSVFILE] [--no-config] 
                              | --remove 
                              | --deploy (--shared-secret SECRET | --shared-secret-env) [--replace])
                            (--cx-url URL --scm-url SCMURL (--pat PAT | --pat-env) )
                            (ado TARGETS...)

                            
  TARGETS...                One or more logical unit names where service hook
                            configurations will be created

                            For Azure DevOps, collection names are targets

  Global Options

  -h --help                 Show this help.

  -v --version              Show version and exit.
  

  Run Configuration

  --level LOGLEVEL          Log level [default: INFO]
                            Use: DEBUG, INFO, WARNING, ERROR, CRITICAL
  
  --log-file LOGFILE        A file where logs are written.

  -q                        Do not output logs to the console.
                            
  -t THREADS                The number of concurrent SCM read/write operations. [default: 4]
  
  Network Configuration

  -k                        Ignore SSL verification failures. 

  --proxy PROXY_URL         A proxy server to use for communication.


  Filtering Options

  --match-regex M_REGEX      Regular expression that matches projects/orgs that
                             should be configured to send events to CxOneFlow

  --skip-regex S_REGEX       Regular expression that matches projects/orgs that
                             *should not* be configured to send events to CxOneFlow
  
  Webhook Configuration Parameters
  
  --cx-url CX_URL            The base URL for the CxOneFlow endpoint 
                             (e.g. https://cxoneflow.corp.com)

  
  Action Options

  --audit                    Create a CSV that lists CxOneFlow event configuration status of each
                             project/organization.

  --deploy                   Configure matching projects/orgs to send events to CxOneFlow
  
  --remove                   Remove CxOneFlow webhook configuration for matching projects/orgs

  
  Options for --audit

  --outfile CSVFILE          The path to a file where the audit CSV will be
                             written. [default: ./cxoneflow.csv]

  --no-config                Only include projects that are not configured
                             or are partially configured.

  Options for --deploy

  --shared-secret SECRET     The shared secret configured in the service hook

  --shared-secret-env        Obtain the shared secret from the environment variable 'CX_SECRET'

  --replace                  If an existing webhook subscription is found, replace it.

  SCM Options

  --pat PAT                  An SCM PAT with appropriate privileges.

  --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

  --scm-url URL              The URL to the SCM instance
                             
                             ADO Cloud Example: https://dev.azure.com
                             ADO Enterprise Example: https://ado.corp.com
  """
  try:
    can_log = False

    args = docopt(main.__doc__, version=PROGNAME)

    bootstrap(DEFAULT_LOGLEVEL if args['--level'] is None else args['--level'], 
              not args['-q'], args['--log-file'])
    
    _log = logging.getLogger("main")
    can_log = True
    _log.info(PROGNAME)
    _log.debug(f"{PROGNAME} START")


    result = await dispatch(args)

    _log.debug(f"{PROGNAME} END with exit code {result}")

    exit (result)
  except DocoptExit as bad_args:
    if can_log:
      _log.exception(bad_args)
    else:
      print("Incorrect arguments provided.")
      print(bad_args)
    exit(1)
  except NotImplementedError as ni:
    if can_log:
      _log.exception(ni)
    else:
      print(f"Not implemented: {ni}")
    exit(1)
  except SystemExit:
    pass
  except BaseException as ex:
    if can_log:
      _log.exception(ex)
    else:
      print(ex)
    exit(1)

if __name__ == "__main__":
  asyncio.run(main())

def cli_entry():
  asyncio.run(main())

