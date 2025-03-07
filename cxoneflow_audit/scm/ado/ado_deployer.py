from cxoneflow_audit.core import Deployer
from cxoneflow_audit.core.common import ConfigState
from typing import Any, Dict, AsyncGenerator
from asyncio import wait, get_running_loop
from .ado_servicemgr import AdoServiceManager

class AdoDeployer(Deployer, AdoServiceManager):

  def __init__(self, *args):
    Deployer.__init__(self, *args)
    AdoServiceManager.__init__(self)

  @property
  def _scm_name(self) -> str:
    return "ADO"

  def _get_lu_name(self, lu : Any) -> str:
    return self._render_lu_name(lu)

  def _get_lu_repr(self, lu : Any) -> str:
    return self._render_lu_repr(lu)

  async def _lu_iterator(self) -> AsyncGenerator[Dict, None]:
    async for x in self._lu_iterator_delegate(self.scm_base_url, self.targets, self.scm_pat, self.proxies, self.ignore_ssl_errors):
      yield x

  async def _process_lu(self, lu : Any) -> bool:
    subs = self._get_subs_for_project(await self._list_lu_webhook_subscriptions(self.scm_base_url, lu['collection'], 
                                self.scm_pat, self.proxies, self.ignore_ssl_errors), 
                                 lu['id'], self._make_cx_endpoint_url(self.cxone_flow_url), self.ADO_EVENT_TYPES)
    
    hook_data = self._hook_data_from_lu_factory(lu)

    for event in self.ADO_EVENT_TYPES:
      sub = self._find_sub_for_event(event, subs)
      if sub:
        self._update_hook_by_event_type(event, hook_data, sub)

    if await self._evaluate_subscription_state(hook_data) == ConfigState.CONFIGURED and not self.replace:
      self.log().warning(f"{self._get_lu_repr(lu)} is already configured, no changes made.")
      return True
    
    self.log().info(f"Configuring {self._get_lu_repr(lu)}")

    sub_ids = [s['id'] for s in subs]
    if len(sub_ids) > 0:
      await wait([get_running_loop().create_task(
        self._delete_subscription(lu['collection'], sub_id, self.scm_base_url, 
                                   self.scm_pat, self.proxies, self.ignore_ssl_errors)) for sub_id in sub_ids])

    await wait([get_running_loop().create_task(
      self._create_subscription(event, lu['id'], lu['collection'], self.scm_base_url, self.scm_pat, self.cxone_flow_url,
                                 self.shared_secret, self.proxies, self.ignore_ssl_errors)) for event in self.ADO_EVENT_TYPES])
    
    return True