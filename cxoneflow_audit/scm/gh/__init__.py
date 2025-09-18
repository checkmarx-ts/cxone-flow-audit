from cxoneflow_audit.scm.common import SCMTool
from cxoneflow_audit.scm.gh.gh_auditor import GithubAuditor
from typing import List

class GithubTool(SCMTool):

  def __init__(self, **kwargs):
     super().__init__(audit=self.gh_audit, deploy=self.gh_deploy, remove=self.gh_remove, kickoff=self.gh_kickoff, **kwargs)

  async def gh_audit(self, args : List[str], help : bool = False):
    """Usage: cxoneflow-audit gh audit [--no-config] [--outfile CSVFILE] 
                      [--match-regex M_REGEX | --skip-regex S_REGEX]
                      [--app-id ID | --app-slug SLUG]
                      [--app-key KEYFILE]
                      (--pat PAT | --pat-env) (--scm-api-url URL)
                      (--cx-url CX_URL)
    
    Deployment Options

    --cx-url CX_URL             The base URL for the CxOneFlow endpoint 
                                (e.g. https://cxoneflow.corp.com)

    Output Options

    --outfile CSVFILE          The path to a file where the audit CSV will be
                               written. [default: ./cxoneflow.csv]

    --no-config                Only include projects that are not configured.

    Filtering Options

    --match-regex M_REGEX      Regular expression matching organization names that
                               should be configured to send events to CxOneFlow.

    --skip-regex S_REGEX       Regular expression matching organization names that
                               should not be configured to send events to CxOneFlow.

    SCM Options

    --pat PAT                  An SCM PAT with appropriate privileges.

    --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

    --scm-api-url URL          The URL to the SCM's API endpoint 
                               (e.g. https://api.github.com, https://github.corp.com/api/v3/)
    
    Github App Options
  
    --app-slug SLUG             The Github app slug for the CxOneFlow app.

    --app-key KEYFILE           The path to the app private key file.
    """
    args = self._get_opts(self.gh_audit.__doc__, ["gh", "audit"] + args, help)

    return await GithubAuditor(outfile=args['--outfile'], only_not_cfg=args['--no-config'], 
                            targets=None,
                            concurrency=self.concurrency, proxy=self.proxy,
                            ignore_ssl_errors=self.ssl_ignore,
                            match=self._matcher_factory(args['--skip-regex'], args['--match-regex']),
                            pat=SCMTool.resolve_from_env(args['--pat'], "CX_PAT"),
                            cx_url=args['--cx-url'], scm_url=args['--scm-api-url'],
                            app_slug=args['--app-slug'], app_key_file=args['--app-key']).execute()

  async def gh_deploy(self, args : List[str], help : bool = False):
    """Usage: cxoneflow-audit gh deploy
                      (--shared-secret SECRET | --shared-secret-env) [--replace]
                      (--pat PAT | --pat-env) (--scm-api-url URL)
                      (--cx-url CX_URL)
    

    Deployment Options

    --cx-url CX_URL             The base URL for the CxOneFlow endpoint 
                                (e.g. https://cxoneflow.corp.com)

    --shared-secret SECRET     The shared secret configured in the service hook

    --shared-secret-env        Obtain the shared secret from the environment variable 'CX_SECRET'

    --replace                  If an existing webhook subscription is found, replace it.

    SCM Options

    --pat PAT                  An SCM PAT with appropriate privileges.

    --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

    --scm-api-url URL          The URL to the SCM's API endpoint 
                               (e.g. https://api.github.com, https://github.corp.com/api/v3/)

    """
    args = self._get_opts(self.gh_deploy.__doc__, ["gh", "deploy"] + args, help)
    pass

  async def gh_remove(self, args : List[str], help : bool = False):
    pass

  async def gh_kickoff(self, args : List[str], help : bool = False):
    pass

  async def __call__(self, args : List[str], help : bool = False):
    """Usage: cxoneflow-audit gh <command> [<args>...]

    <command> can be one of:
    audit       Execute an audit for CxOneFlow webhook or GitHub app deployment.

    deploy      Deploy CxOneFlow webhooks on the projects in the specified organizations.

    remove      Remove CxOneFlow webhooks on the projects in the specified organizations.

    kickoff     Iterate through repositories in the specified orginizations
                and perform an initial scan on the default branch.

    Use "cxoneflow-audit help gh <command>" for further help.
    """
    tool = [] if help else ["gh"]
    return await self._dispatch(self.__call__.__doc__, "<command>", "<args>", tool + args, help)
  
