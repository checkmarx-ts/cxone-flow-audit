from cxoneflow_audit.core import Auditor
from cxoneflow_audit.core.common import ConfigState
from typing import Dict, AsyncGenerator, Any, Awaitable
from asyncio import to_thread, gather, Lock
import requests, csv
from jsonpath_ng.ext import parse
from .ado_base import AdoBase, HookData

class AdoAuditor(Auditor, AdoBase):

  @property
  def __endpoint_url(self) -> str:
    u = self.cxone_flow_url.rstrip('/')
    return f"{u}/adoe"
  
  @property
  def _scm_name(self) -> str:
    return "ADO"

  def __project_list_url_params(self, skip : int) -> str:
    ret = {"$skip" : str(skip)}
    ret.update(self._api_ver_url_params("7.1"))
    return ret

  async def _evaluate_state(self, project_id : str) -> ConfigState:
    if project_id not in self.__data.keys():
      return ConfigState.NOT_CONFIGURED

    return await super()._evaluate_state(self.__data[project_id])
  
  async def __record_pr_create(self, project_id : str, sub_json : Dict) -> None:
    async with self.__lock:
      self.__data[project_id].hasEventPrCreate = True & (sub_json.value['status'] == "enabled")
      self.__data[project_id].prCreateEventCreateDate = sub_json.value['createdDate']
      self.__data[project_id].prCreateEventCreatedBy = sub_json.value['createdBy']['uniqueName']
      self.__data[project_id].prCreateEventModDate = sub_json.value['modifiedDate']
      self.__data[project_id].prCreateEventModBy = sub_json.value['modifiedBy']['uniqueName']
      self.__data[project_id].prCreateEventStatus = sub_json.value['status']

  async def __record_pr_update(self, project_id : str, sub_json : Dict) -> None:
    async with self.__lock:
      self.__data[project_id].hasEventPrUpdate = True & (sub_json.value['status'] == "enabled")
      self.__data[project_id].prUpdateEventCreateDate = sub_json.value['createdDate']
      self.__data[project_id].prUpdateEventCreatedBy = sub_json.value['createdBy']['uniqueName']
      self.__data[project_id].prUpdateEventModDate = sub_json.value['modifiedDate']
      self.__data[project_id].prUpdateEventModBy = sub_json.value['modifiedBy']['uniqueName']
      self.__data[project_id].prUpdateEventStatus = sub_json.value['status']

  async def __record_push(self, project_id : str, sub_json : Dict) -> None:
    async with self.__lock:
      self.__data[project_id].hasEventPush = True & (sub_json.value['status'] == "enabled")
      self.__data[project_id].pushEventCreateDate = sub_json.value['createdDate']
      self.__data[project_id].pushEventCreatedBy = sub_json.value['createdBy']['uniqueName']
      self.__data[project_id].pushEventModDate = sub_json.value['modifiedDate']
      self.__data[project_id].pushEventModBy = sub_json.value['modifiedBy']['uniqueName']
      self.__data[project_id].pushEventStatus = sub_json.value['status']

  async def __validate_event_set(self, project_id : str, event_name : str, record_lambda : Awaitable, url : str, common_params : Dict) -> None:
    query = parse("$.value[?(@.publisherInputs.projectId == '" + project_id + 
                  "' & @.consumerInputs.url =~ '" + self.__endpoint_url + "')]")

    params = {"eventType" : event_name}
    params.update(common_params)

    resp = await to_thread(requests.request, "GET", url, params=params,
                     headers=self._auth_headers(self.scm_pat), proxies=self.proxies, verify=not self.ignore_ssl_errors)
    
    if not resp.ok:
      self.log().error(f"Response of {resp.status_code} trying to retrieve service hook data from: {url}")
    else:
      for sub in query.find(resp.json()):
        await record_lambda(project_id, sub)

  async def _process_lu(self, lu_data : Any) -> bool:
    self.log().debug(f"Processing: {self._get_lu_repr(lu_data)}")

    async with self.__lock:
      if lu_data['id'] not in self.__data.keys():
        self.__data[lu_data['id']] = HookData(
          projectCollection=lu_data['collection'], 
          projectName=lu_data['name'], 
          projectUrl= lu_data['url'],
          projectVisibility=lu_data['visibility'])


    service_hooks_url = f"{self._org_url(self.scm_base_url, lu_data['collection'])}/_apis/hooks/subscriptions"
    common_service_params = { 
      "organization" : lu_data['collection'],
      "consumerActionId" : "httpRequest",
      "consumerId" : "webHooks",
      }
    
    common_service_params.update(self._api_ver_url_params("7.1"))

    await gather(
      self.__validate_event_set(lu_data['id'], "git.pullrequest.created", self.__record_pr_create, service_hooks_url, common_service_params),
      self.__validate_event_set(lu_data['id'], "git.pullrequest.updated", self.__record_pr_update, service_hooks_url, common_service_params),
      self.__validate_event_set(lu_data['id'], "git.push", self.__record_push, service_hooks_url, common_service_params))
    
    return True
    

  def _get_lu_name(self, lu : Any) -> str:
    return lu['name']

  def _get_lu_repr(self, lu : Any) -> str:
    return f"{self._scm_name}:{lu['collection']}:{lu['name']}:{lu['visibility']}:{lu['url']}"

  async def _lu_iterator(self) -> AsyncGenerator[Dict, None]:

    for t in self.targets:
      skip = 0

      project_list_url = f"{self._org_url(self.scm_base_url, t)}/_apis/projects"

      while True:

        resp = await to_thread(requests.request, "GET", project_list_url, params=self.__project_list_url_params(skip), 
                            headers=self._auth_headers(self.scm_pat), proxies=self.proxies, verify=not self.ignore_ssl_errors)

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
          self.log().error(f"Response of {resp.status_code} invoking {project_list_url}.")
          break

  async def execute(self) -> int:
    self.__data = {}
    self.__lock = Lock()


    result = await super().execute()

    with open(self.outfile, "wt") as csv_dest:
      writer = csv.writer(csv_dest, lineterminator="\n", quoting=csv.QUOTE_ALL)
      # pylint: disable=E1101
      sorted_fields = sorted(list(HookData.__dataclass_fields__.keys()))
      headers = ["state"] + sorted_fields
      writer.writerow(headers)
      for pid in self.__data.keys():
        state = await self._evaluate_state(pid)
        if not (self.skip_configured and state == ConfigState.CONFIGURED):
          writer.writerow([state] + [self.__data[pid].__dict__[x] for x in sorted_fields])

    return result
  
