import urllib.parse
from cxoneflow_audit.core.common import ConfigState
from dataclasses import dataclass
from typing import Dict
import base64

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

  def _auth_headers(self, scm_pat : str) -> Dict:
    auth_b64 = base64.b64encode(f":{scm_pat}".encode("UTF-8")).decode()
    return { "Authorization" : f"Basic {auth_b64}" }

  def _api_ver_url_params(self, version : str) -> str:
    return {"api-version" : version}

  def _org_url(self, base_url : str, collection : str) -> str:
    return f"{base_url}/{urllib.parse.quote_plus(collection)}"

  async def _evaluate_state(self, data : HookData) -> ConfigState:
    if data.hasEventPrCreate and data.hasEventPrUpdate and data.hasEventPush:
      return ConfigState.CONFIGURED
    elif not ((data.hasEventPrCreate and data.hasEventPrUpdate and data.hasEventPush) 
              or data.hasEventPrCreate or data.hasEventPrUpdate or data.hasEventPush):
      return ConfigState.NOT_CONFIGURED
    else:
      return ConfigState.PARTIAL_CONFIG

