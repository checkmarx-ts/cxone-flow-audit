from cxoneflow_audit.core import Deployer
from cxoneflow_audit.core.common import ConfigState
from cxoneflow_audit.util import ScmException
from .ado_base import AdoBase
from typing import Dict, AsyncGenerator, Any, Union, List
from jsonpath_ng.ext import parse
from asyncio import to_thread, wait, get_running_loop
import requests

class AdoDeployer(Deployer, AdoBase):

  def __init__(self, *args):
    Deployer.__init__(self, *args)
    AdoBase.__init__(self)

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

  def __find_sub_for_event(self, event_type : str, subs : List[Dict]) -> Union[Dict,None]:
    for found in parse("$[?(@.eventType == '" + event_type + "')]").find(subs):
      return found.value


  async def __create_subscription(self, event_type : str, project_id : str, collection : str) -> None:
    payload = {
      "publisherId" : "tfs",
      "eventType" : event_type,
      "resourceVersion" : "1.0",
      "consumerId" : "webHooks",
      "consumerActionId" : "httpRequest",
      "publisherInputs" : {
        "projectId" : project_id
      },
      "consumerInputs" : {
        "url" : self._make_cx_endpoint_url(self.cxone_flow_url),
        "basicAuthPassword" : self.shared_secret
      }
    }

    create_url = f"{self._org_url(self.scm_base_url, collection)}/_apis/hooks/subscriptions"
    resp = await to_thread(requests.request, "POST", create_url, params=self._api_ver_url_params(), json=payload,
      headers=self._auth_headers(self.scm_pat), proxies=self.proxies, verify=not self.ignore_ssl_errors)
    
    if not resp.ok:
      self.log().error(f"Response code {resp.status_code} returned for {create_url}")
      raise ScmException(f"Exception trying to create service hook subscriptions for {collection}/{project_id}")

  async def __delete_subscription(self, collection : str, sub_id : str):
    delete_url = f"{self._org_url(self.scm_base_url, collection)}/_apis/hooks/subscriptions/{sub_id}"

    resp = await to_thread(requests.request, "DELETE", delete_url, params=self._api_ver_url_params(),
                    headers=self._auth_headers(self.scm_pat), proxies=self.proxies, verify=not self.ignore_ssl_errors)
    
    if not resp.ok:
      self.log().error(f"Response code {resp.status_code} returned for {delete_url}")
      raise ScmException(f"Exception trying to delete service hook subscription {sub_id} from {collection}")

  async def _process_lu(self, lu : Any) -> bool:
    subs = self._get_subs_for_project(await self._list_lu_webhook_subscriptions(self.scm_base_url, lu['collection'], 
                                self.scm_pat, self.proxies, self.ignore_ssl_errors), 
                                 lu['id'], self._make_cx_endpoint_url(self.cxone_flow_url), AdoBase.ADO_EVENT_TYPES)
    
    hook_data = self._hook_data_from_lu_factory(lu)

    for event in AdoBase.ADO_EVENT_TYPES:
      sub = self.__find_sub_for_event(event, subs)
      if sub:
        self._update_hook_by_event_type(event, hook_data, sub)

    if await self._evaluate_subscription_state(hook_data) == ConfigState.CONFIGURED and not self.replace:
      self.log().warning(f"{self._get_lu_repr(lu)} is already configured, no changes made.")
      return True
    
    self.log().info(f"Configuring {self._get_lu_repr(lu)}")

    sub_ids = [s['id'] for s in subs]
    if len(sub_ids) > 0:
      await wait([get_running_loop().create_task(self.__delete_subscription(lu['collection'], sub_id)) for sub_id in sub_ids])

    await wait([get_running_loop().create_task(self.__create_subscription(event, lu['id'], lu['collection'])) for event in AdoBase.ADO_EVENT_TYPES])
    
    return True