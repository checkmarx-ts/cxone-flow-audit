from cxoneflow_audit.scm.common import SCMTool
from typing import List

class GithubTool(SCMTool):

  def __init__(self, **kwargs):
     super().__init__(audit=self.gh_audit, deploy=self.gh_deploy, remove=self.gh_remove, kickoff=self.gh_kickoff, **kwargs)

  async def gh_audit(self, args : List[str], help : bool = False):
    pass

  async def gh_deploy(self, args : List[str], help : bool = False):
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
  
