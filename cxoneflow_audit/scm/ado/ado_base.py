import urllib.parse
from cxoneflow_audit.core.common import ConfigState
from cxoneflow_audit.util import ScmException
from dataclasses import dataclass
from typing import Dict, AsyncGenerator, List, Any
from asyncio import to_thread, gather, Lock
import base64, requests, logging
from jsonpath_ng.ext import parse

@dataclass(frozen=False)
class HookData:
  projectCollection : str
  projectName : str
  projectUrl : str
  projectVisibility : str

  hasEventPrCreate : bool = False
  prCreateEventCreateDate : str = None
  prCreateEventCreatedBy : str = None
  prCreateEventModDate : str = None
  prCreateEventModBy : str = None
  prCreateEventStatus : str = None

  hasEventPrUpdate : bool = False
  prUpdateEventCreateDate : str = None
  prUpdateEventCreatedBy : str = None
  prUpdateEventModDate : str = None
  prUpdateEventModBy : str = None
  prUpdateEventStatus : str = None

  hasEventPush : bool = False
  pushEventCreateDate : str = None
  pushEventCreatedBy : str = None
  pushEventModDate : str = None
  pushEventModBy : str = None
  pushEventStatus : str = None

class AdoBase:

  ADO_API_VERSION = "7.1"

  ADO_EVENT_TYPES = ["git.push", "git.pullrequest.created", "git.pullrequest.updated"]

  def __init__(self):
    self.__lock = Lock()
    self.__sub_cache = {}

  @classmethod
  def log(clazz) -> logging.Logger:
      return logging.getLogger(clazz.__name__)
  
  def _render_lu_name(self, lu : Any) -> str:
    return lu['name']

  def _render_lu_repr(self, lu : Any) -> str:
    return f"ADO:{lu['collection']}:{lu['name']}:{lu['visibility']}:{lu['url']}"


  def __project_list_url_params(self, skip : int) -> str:
    ret = {"$skip" : str(skip)}
    ret.update(self._api_ver_url_params())
    return ret

  def _make_cx_endpoint_url(self, base_url : str) -> str:
    u = base_url.rstrip('/')
    return f"{u}/adoe"

  def _auth_headers(self, scm_pat : str) -> Dict:
    auth_b64 = base64.b64encode(f":{scm_pat}".encode("UTF-8")).decode()
    return { "Authorization" : f"Basic {auth_b64}" }

  def _api_ver_url_params(self, version : str = ADO_API_VERSION) -> str:
    return {"api-version" : version}

  def _org_url(self, base_url : str, collection : str) -> str:
    return f"{base_url}/{urllib.parse.quote_plus(collection)}"

  async def _evaluate_subscription_state(self, data : HookData) -> ConfigState:
    if data.hasEventPrCreate and data.hasEventPrUpdate and data.hasEventPush:
      return ConfigState.CONFIGURED
    elif not ((data.hasEventPrCreate and data.hasEventPrUpdate and data.hasEventPush) 
              or data.hasEventPrCreate or data.hasEventPrUpdate or data.hasEventPush):
      return ConfigState.NOT_CONFIGURED
    else:
      return ConfigState.PARTIAL_CONFIG

  @staticmethod
  def _update_hook_push_from_sub_json(data : HookData, sub_json : Dict) -> None:
      data.hasEventPush = (sub_json['status'] == "enabled")
      data.pushEventCreateDate = sub_json['createdDate']
      data.pushEventCreatedBy = sub_json['createdBy']['uniqueName']
      data.pushEventModDate = sub_json['modifiedDate']
      data.pushEventModBy = sub_json['modifiedBy']['uniqueName']
      data.pushEventStatus = sub_json['status']

  @staticmethod
  def _update_hook_pr_create_from_sub_json(data : HookData, sub_json : Dict) -> None:
      data.hasEventPrCreate = (sub_json['status'] == "enabled")
      data.prCreateEventCreateDate = sub_json['createdDate']
      data.prCreateEventCreatedBy = sub_json['createdBy']['uniqueName']
      data.prCreateEventModDate = sub_json['modifiedDate']
      data.prCreateEventModBy = sub_json['modifiedBy']['uniqueName']
      data.prCreateEventStatus = sub_json['status']

  @staticmethod
  def _update_hook_pr_update_from_sub_json(data : HookData, sub_json : Dict) -> None:
      data.hasEventPrUpdate = (sub_json['status'] == "enabled")
      data.prUpdateEventCreateDate = sub_json['createdDate']
      data.prUpdateEventCreatedBy = sub_json['createdBy']['uniqueName']
      data.prUpdateEventModDate = sub_json['modifiedDate']
      data.prUpdateEventModBy = sub_json['modifiedBy']['uniqueName']
      data.prUpdateEventStatus = sub_json['status']

  @staticmethod
  def _update_hook_by_event_type(event_type : str, data : HookData, sub_json : Dict) -> None:
    return AdoBase.__update_map[event_type](data, sub_json)

  def _hook_data_from_lu_factory(self, lu_json : Dict) -> HookData:
    return HookData( projectCollection=lu_json['collection'], 
          projectName=lu_json['name'], projectUrl= lu_json['url'], projectVisibility=lu_json['visibility'])
      

  def _get_subs_for_project(self, sub : str, project_id : str, cx_adoe_ep_url : str, event_types : List[str]) -> List[Dict]:
    event_regex = "|".join(event_types)

    query_str = "$.value[?(@.publisherInputs.projectId == '" + project_id + "' & @.consumerInputs.url =~ '" + cx_adoe_ep_url + \
                  "' & @.eventType =~ '" + event_regex + "')]"

    return [q.value for q in parse(query_str).find(sub)]


  async def _list_lu_webhook_subscriptions(self, scm_base_url :str, collection : str, scm_pat : str, proxies : Dict, ignore_ssl_errors : bool) -> Dict:
    async with self.__lock:
      if collection in self.__sub_cache.keys():
        self.log().debug(f"Subscription cache hit for {collection}")
        return self.__sub_cache[collection]

    service_hooks_url = f"{self._org_url(scm_base_url, collection)}/_apis/hooks/subscriptions"
    service_params = { 
      "organization" : collection,
      "consumerActionId" : "httpRequest",
      "consumerId" : "webHooks",
      }

    service_params.update(self._api_ver_url_params())

    resp = await to_thread(requests.request, "GET", service_hooks_url, params=service_params,
                     headers=self._auth_headers(scm_pat), proxies=proxies, verify=not ignore_ssl_errors)
    
    if not resp.ok:
      self.log().error(f"Response of {resp.status_code} trying to retrieve service hook data from: {service_hooks_url}")
    else:
      async with self.__lock:
        self.__sub_cache[collection] = resp.json()
      return resp.json()

  async def _lu_iterator_delegate(self, scm_base_url : str, targets : List[str], scm_pat : str, proxies : Dict, ignore_ssl_errors : bool) -> AsyncGenerator[Dict, None]:

    for t in targets:
      skip = 0

      project_list_url = f"{self._org_url(scm_base_url, t)}/_apis/projects"

      while True:

        resp = await to_thread(requests.request, "GET", project_list_url, params=self.__project_list_url_params(skip), 
                            headers=self._auth_headers(scm_pat), proxies=proxies, verify=not ignore_ssl_errors)

        if resp.ok:
          json = resp.json()
          skip = json['count']
          if skip == 0:
            break
          for v in json['value']:
            ret_val = dict(v)
            ret_val['collection'] = t
            yield ret_val
        else:
          msg = f"Response of {resp.status_code} invoking {project_list_url}."
          self.log().error(msg)
          raise ScmException(msg)

  __update_map = {
    "git.pullrequest.updated" : _update_hook_pr_update_from_sub_json,
    "git.pullrequest.created" : _update_hook_pr_create_from_sub_json,
    "git.push" : _update_hook_push_from_sub_json,
  }