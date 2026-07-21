from typing import Dict, AsyncGenerator, Any, List
import csv
from asyncio import Lock
import requests.auth
from dataclasses import dataclass, field
from enum import Enum
from cxoneflow_audit.core.common import ConfigState
from cxoneflow_audit.core import Auditor
from .consts import BBC_API_URL

class HookScope(Enum):
  def __str__(self):
    return str(self.value)

  WORKSPACE = "Workspace"
  REPO = "Repository"
  NONE = "N/A"

@dataclass(frozen=False)
class HookData:
  lu : str
  configState : ConfigState
  configScope : HookScope = HookScope.NONE
  missingEvents : List[str] = field(default_factory=list)
  hookUrl : str = ""
  active : bool = False
  secretSet : bool = False
  issues : List[str] = field(default_factory=list)


class BitBucketCloudAuditor(Auditor):
  __repo_required_events = [
                "pullrequest:approved",
                "pullrequest:created",
                "pullrequest:changes_request_created",
                "pullrequest:fulfilled",
                "pullrequest:push",
                "repo:push",
                "pullrequest:rejected",
                "pullrequest:changes_request_removed",
                "pullrequest:unapproved",
                "pullrequest:updated",
                "repo:updated"
  ]

  __ws_required_events = __repo_required_events + ["project:updated"]

  def __init__(self, auth : requests.auth.AuthBase, *args, **kwargs):
    Auditor.__init__(self, scm_url=BBC_API_URL, *args, **kwargs)
    self.__auth = auth
    self.__lock = Lock()
    self.__data = []

  @property
  def _scm_name(self) -> str:
    return "BitBucket Cloud"

  def _get_lu_name(self, lu : Any) -> str:
    return lu.get("workspace", {}).get("slug", "UNKNOWN")

  def _get_lu_repr(self, lu : Any) -> str:
    return f"{self._get_lu_name(lu)}:{lu.get("workspace", {}).get("links", {}).get("self", {}).get("href")}"

  async def __call_paginated_api(self, api_path : str, **kwargs):
    page = 1
    end = False

    values = []


    while True:
      if len(values) == 0:
        
        if end:
          return
        
        resp = await self._scm_api_call(api_path, query_args = kwargs.get("query_args", {}).update({"page" : page}), **kwargs)
        page += 1

        if not resp.ok:
          return
        
        ret_dict = resp.json()
        if "next" not in ret_dict.keys():
          end = True
        values = ret_dict.get("values")

      if len(values) > 0:
        yield values.pop()
        
  async def _lu_iterator(self) -> AsyncGenerator[Dict, None]:
    async for x in self.__call_paginated_api(api_path="/user/workspaces", auth=self.__auth):
      yield x


  async def _process_lu(self, lu : Any) -> bool:
    self.log().debug(f"Processing: {self._get_lu_repr(lu)}")

    lu_workspace_hook_found = False
    lu_workspace_hook_configured = False

    # Start at workspace scope
    async for ws in self.__call_paginated_api(api_path=f"/workspaces/{self._get_lu_name(lu)}/hooks", auth=self.__auth):
      ws_config = HookData(lu=self._get_lu_repr(lu), configScope = HookScope.WORKSPACE, 
                           configState = ConfigState.NOT_CONFIGURED, hookUrl=ws.get("url", ""))

      endpoint = False
      ssl_verify = False

      if ws_config.hookUrl.startswith(self.cxone_flow_url):
        if not ws.get("url", "").startswith(self.cxone_flow_url.rstrip("/") + "/bbc"):
          ws_config.configState = ConfigState.MISCONFIG
          ws_config.issues.append("CxOneFlow endpoint should be /bbc")
        else:
          endpoint = True


        ws_config.active = ws.get("active", False)
        if not ws_config.active:
          ws_config.configState = ConfigState.MISCONFIG
          ws_config.issues.append("CxOneFlow webhook is configured but not active")

        ssl_verify = not ws.get("skip_cert_verification")
        if not ssl_verify:
          ws_config.configState = ConfigState.MISCONFIG
          ws_config.issues.append("CxOneFlow SSL certificate validation is turned off")

        ws_config.secretSet = ws.get("secret_set")
        if not ws_config.secretSet:
          ws_config.configState = ConfigState.MISCONFIG
          ws_config.issues.append("Webhook secret is not set")


        missing_events = [ev for ev in BitBucketCloudAuditor.__ws_required_events if ev not in ws.get("events")]
        if len(missing_events) > 0:
          ws_config.configState = ConfigState.MISCONFIG
          ws_config.missingEvents = missing_events
          ws_config.issues.append("Not all required events are being sent by the webhook")
      else:
        continue

      if ws_config.configState == ConfigState.NOT_CONFIGURED:
        if ws_config.active and endpoint and ssl_verify and ws_config.secretSet and len(ws_config.missingEvents) == 0:
          ws_config.configState = ConfigState.CONFIGURED
          lu_workspace_hook_configured = True
        else:
          ws_config.configState = ConfigState.PARTIAL_CONFIG

      async with self.__lock:
        self.__data.append(ws_config)
    
    if not lu_workspace_hook_configured:
      async with self.__lock:
        self.__data.append(HookData(lu=self._get_lu_repr(lu), configScope = HookScope.WORKSPACE, configState = ConfigState.NOT_CONFIGURED))

    return len(self.__data) > 0

  async def execute(self) -> int:

    result = await super().execute()

    with open(self.outfile, "wt", encoding="UTF-8") as csv_dest:
      writer = csv.writer(csv_dest, lineterminator="\n", quoting=csv.QUOTE_ALL)
      # pylint: disable=E1101
      sorted_fields = sorted(list(HookData.__dataclass_fields__.keys()))
      writer.writerow(sorted_fields)
      for row in self.__data:
        if not (self.skip_configured and row.configState == ConfigState.CONFIGURED):
          writer.writerow([row.__dict__[x] for x in sorted_fields])

    return result
