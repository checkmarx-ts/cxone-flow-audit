from cxoneflow_audit.scm.gh.gh_base import GithubBase
from cxoneflow_audit.core import Kicker
from typing import AsyncGenerator, Dict, Any, Union, Tuple
from cxoneflow_kickoff_api import GithubKickoffMsg
from asyncio import to_thread

class GithubKicker(Kicker, GithubBase):
  def __init__(self, app_slug : str, *args, **kwargs):
    Kicker.__init__(self, *args, **kwargs)
    GithubBase.__init__(self, self.cxone_flow_url, self.scm_base_url,
                        self.scm_pat, self.proxies, self.ignore_ssl_errors,
                        app_slug, None)

  @property
  def _scm_name(self) -> str:
    return "Github"

  @property
  def scm_key(self) -> str:
    return "gh"

  def _get_lu_name(self, lu : Any) -> str:
    return lu['login']

  def _get_lu_repr(self, lu : Any) -> str:
    return f"{lu['login']}:{lu['id']}:{lu['url']}"

  async def _lu_iterator(self) -> AsyncGenerator[Dict, None]:
    async for x in await self._organization_iterator():
      yield x

  async def _process_lu(self, lu : Any) -> bool:
    org_name = lu['login']

    app_id = None
    install_id = None
    if self.check_for_app:
      try:
        installed_app = await self._get_org_installed_app(org_name)
        if installed_app is not None:
          app_id = installed_app['app_id']
          install_id = installed_app['id']
      except GithubBase.NotFoundException:
        self.log().warning("App information for organization %s not found. Scans will be attempted but may fail without the app install id.", org_name)

    async for repo in self._repo_iterator(org_name):
      await self._exec_kickoff(repo['clone_url'],
        GithubKickoffMsg(
          clone_urls=[repo['clone_url'], f"ssh://{repo['ssh_url']}"],
          branch_name=repo['default_branch'],
          sha=await self._get_latest_repo_commit(org_name, repo['name'], repo['default_branch']),
          repo_organization_name=org_name,
          repo_name=repo['name'],
          install_id=install_id,
          app_id=app_id))
