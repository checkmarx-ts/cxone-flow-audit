from .ado_base import AdoBase
from typing import Dict, List, Union
from jsonpath_ng.ext import parse
from asyncio import to_thread
from cxoneflow_audit.util import ScmException
import requests

class AdoServiceManager(AdoBase):

  def __init__(self):
    super().__init__()

  def _find_sub_for_event(self, event_type : str, subs : List[Dict]) -> Union[Dict,None]:
    for found in parse("$[?(@.eventType == '" + event_type + "')]").find(subs):
      return found.value

  async def _create_subscription(self, event_type : str, project_id : str, collection : str,
                                  scm_base_url : str, scm_pat : str, 
                                  cxone_flow_url : str, shared_secret : str,
                                  proxies : Dict, ignore_ssl_errors : bool) -> None:
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
        "url" : self._make_cx_endpoint_url(cxone_flow_url),
        "basicAuthPassword" : shared_secret
      }
    }

    create_url = f"{self._org_url(scm_base_url, collection)}/_apis/hooks/subscriptions"
    resp = await to_thread(requests.request, "POST", create_url, params=self._api_ver_url_params(), json=payload,
      headers=self._required_headers(scm_pat), proxies=proxies, verify=not ignore_ssl_errors)
    
    if not resp.ok:
      self.log().error(f"Response code {resp.status_code} returned for {create_url}")
      raise ScmException(f"Exception trying to create service hook subscriptions for {collection}/{project_id}")


  async def _delete_subscription(self, collection : str, sub_id : str, scm_base_url : str, scm_pat : str, proxies : Dict, ignore_ssl_errors : bool):
    delete_url = f"{self._org_url(scm_base_url, collection)}/_apis/hooks/subscriptions/{sub_id}"

    resp = await to_thread(requests.request, "DELETE", delete_url, params=self._api_ver_url_params(),
                    headers=self._required_headers(scm_pat), proxies=proxies, verify=not ignore_ssl_errors)
    
    if not resp.ok:
      self.log().error(f"Response code {resp.status_code} returned for {delete_url}")
      raise ScmException(f"Exception trying to delete service hook subscription {sub_id} from {collection}")
