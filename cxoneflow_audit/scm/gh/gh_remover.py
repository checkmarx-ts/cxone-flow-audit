from typing import Any, AsyncGenerator, Dict
from cxoneflow_audit.core import Remover
from cxoneflow_audit.scm.gh.gh_base import GithubBase


class GithubRemover(Remover, GithubBase):

  def __init__(self, app_slug : str, app_key_file : str, *args, **kwargs):
    Remover.__init__(self, *args, **kwargs)
    GithubBase.__init__(self, self.cxone_flow_url, self.scm_base_url,
                        self.scm_pat, self.proxies, self.ignore_ssl_errors,
                        app_slug, app_key_file)

  @property
  def _scm_name(self) -> str:
    return "GitHub"

  def _get_lu_name(self, lu : Any) -> str:
    return lu['login']

  def _get_lu_repr(self, lu : Any) -> str:
    return f"{lu['login']}:{lu['id']}:{lu['url']}"

  async def _lu_iterator(self) -> AsyncGenerator[Dict, None]:
    async for x in await self._organization_iterator():
      yield x

  async def _process_lu(self, lu : Any) -> bool:
    org_name = lu['login']

    noAction = True

    appRemoved = self.check_for_app

    if self.check_for_app:
      try:
        app = await self._get_org_installed_app(org_name)
      except GithubBase.NotFoundException:
        self.log().warning("PAT permissions don't allow app configuration enumeration for organization %s.", org_name)
        app = None
      
      if app is not None:
        install_id = app['id']
        if await self._remove_app(install_id):
          self.log().info("GitHub app with installation id %d removed from organization %s", install_id, org_name)
          noAction = False
        else:
          self.log().warning("Could not remove GitHub app with installation id %d from organization %s", install_id, org_name)
          appRemoved = False

    hookRemoved = True
    try:
      async for hook in await self._organization_hooks_iterator(org_name):
        if self._eval_correct_webhook_url(hook['config']['url']):
          if await self._delete_webhook(org_name, hook['id']):
            self.log().info("Webhook configuration removed from organization %s", org_name)
            noAction = False
          else:
            self.log().warning("Could not remove webhook configuration from organization %s", org_name)
            hookRemoved = False
    except GithubBase.NotFoundException:
        self.log().warning("PAT permissions don't allow webhook configuration enumeration for organization %s.", org_name)


    if noAction:
      self.log().warning("No actions performed for organization %s", org_name)

    return appRemoved and hookRemoved
