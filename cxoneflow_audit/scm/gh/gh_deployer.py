from typing import Any, AsyncGenerator, Dict
from cxoneflow_audit.core import Deployer
from cxoneflow_audit.scm.gh.gh_base import GithubBase


class GithubDeployer(Deployer, GithubBase):

  def __init__(self, app_slug : str, *args, **kwargs):
    Deployer.__init__(self, *args, **kwargs)
    GithubBase.__init__(self, self.cxone_flow_url, self.scm_base_url,
                        self.scm_pat, self.proxies, self.ignore_ssl_errors,
                        app_slug, None)
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

    if self.check_for_app:
      if await self._get_org_installed_app(org_name) is not None:
        self.log().warning("The GitHub app is installed in organization %s, skipping webhook deployment.", org_name)
        return False

    existing_def = None
    async for hook in await self._organization_hooks_iterator(org_name):
      if self._eval_correct_webhook_url(hook['config']['url']):
        existing_def = hook
        break

    if existing_def is not None and not self.replace:
      self.log().warning("Existing webhook configuration found in organization %s, no changes made.", org_name)
      return False
    elif existing_def is not None and self.replace:
      if not await self._replace_webhook(org_name, self.shared_secret, existing_def['id']):
        self.log().error("Unable to replace webhook definition %d for organization %s.", existing_def['id'], org_name)
        return False
      else:
        self.log().info("Webhooks definiton %d replaced in organization %s.", existing_def['id'], org_name)
        return True
    elif existing_def is None:
      if not await self._create_webhook(org_name, self.shared_secret):
        self.log().error("Unable to deploy webhook for organization %s.", org_name)
        return False
      else:
        self.log().info("Webhooks deployed in organization %s.", org_name)
        return True
    

