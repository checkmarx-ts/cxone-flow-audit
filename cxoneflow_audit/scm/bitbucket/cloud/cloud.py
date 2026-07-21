from typing import List
from cxoneflow_audit.scm.common import SCMTool
from .bbc_auditor import BitBucketCloudAuditor
from requests.auth import HTTPBasicAuth


class BitBucketCloudTool(SCMTool):


  def __init__(self, **kwargs):
     super().__init__(audit=self.bbc_audit, deploy=self.bbc_deploy, remove=self.bbc_remove, kickoff=self.bbc_kickoff, **kwargs)


  async def bbc_audit(self, args : List[str], help : bool = False):
    """Usage: cxoneflow-audit bbc audit [--no-config] [--outfile CSVFILE] 
                      [--match-regex M_REGEX | --skip-regex S_REGEX]
                      (--api-token TOKEN | --api-token-env)
                      (--api-token-email EMAIL)
                      (--cx-url CX_URL)
    
    Deployment Options

    --cx-url CX_URL             The base URL for the CxOneFlow endpoint 
                                (e.g. https://cxoneflow.corp.com)

    Output Options

    --outfile CSVFILE          The path to a file where the audit CSV will be
                               written. [default: ./cxoneflow.csv]

    --no-config                Only include workspaces or repositories that are not
                               configured.

    Filtering Options

    --match-regex M_REGEX      Regular expression matching workspace slugs that should
                               be configured to send events to CxOneFlow.

    --skip-regex S_REGEX       Regular expression matching workspace slugs that should
                               not be configured to send events to CxOneFlow.

    SCM Options

    --api-token TOKEN          An API token with appropriate privileges.

    --api-token-env            Obtain the API token from the environment variable 'CX_APITOKEN'

    --api-token-email EMAIL    The Atlassian email address for the account for the API token
  
    """
    args = self._get_opts(self.bbc_audit.__doc__, ["bbc", "audit"] + args, help)
    
    return await BitBucketCloudAuditor(outfile=args['--outfile'], only_not_cfg=args['--no-config'],
                                       targets=None,
                                       concurrency=self.concurrency, proxy=self.proxy,
                                       ignore_ssl_errors=self.ssl_ignore,
                                       match=self._matcher_factory(args['--skip-regex'], args['--match-regex']),
                                       auth=HTTPBasicAuth(args['--api-token-email'],
                                                          SCMTool.resolve_from_env(args['--api-token'], "CX_APITOKEN")),
                                       cx_url=args['--cx-url']).execute()

  async def bbc_deploy(self, args : List[str], help : bool = False):
     pass


  async def bbc_remove(self, args : List[str], help : bool = False):
     pass

  async def bbc_kickoff(self, args : List[str], help : bool = False):
     pass


  async def __call__(self, args : List[str], help : bool = False):
    """Usage: cxoneflow-audit bbc <command> [<args>...]

    <command> can be one of:
    audit       Execute an audit for CxOneFlow webhook deployment.

    deploy      Deploy CxOneFlow webhooks for the specified workspaces.

    remove      Remove CxOneFlow webhooks from the specified workspaces.

    kickoff     Iterate through repositories in the specified workspaces
                and perform an initial scan on the production branch.

    Use "cxoneflow-audit help bbc <command>" for further help.
    """
    tool = [] if help else ["bbc"]
    return await self._dispatch(self.__call__.__doc__, "<command>", "<args>", tool + args, help)
