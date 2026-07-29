from typing import Dict, AsyncGenerator, Any, List
from enum import Enum
from dataclasses import dataclass, field
import requests.auth
from cxoneflow_audit.core.common import ConfigState
from cxoneflow_audit.scm import SCMAPIService

BBC_API_URL = "https://api.bitbucket.org/2.0"


class HookScope(Enum):
    def __str__(self):
        return str(self.value)

    WORKSPACE = "Workspace"
    REPO = "Repository"
    NONE = "N/A"


@dataclass(frozen=False)
class HookData:
    lu: str
    configState: ConfigState
    configScope: HookScope = HookScope.NONE
    missingEvents: List[str] = field(default_factory=list)
    hookUrl: str = ""
    active: bool = False
    secretSet: bool = False
    issues: List[str] = field(default_factory=list)


class BBCWorkspaceService(SCMAPIService):
    def __init__(self, auth: requests.auth.HTTPBasicAuth, *args, **kwargs):
        SCMAPIService.__init__(self, api_base_url=BBC_API_URL, *args, **kwargs)
        self.__auth = auth

    @property
    def auth(self) -> requests.auth.HTTPBasicAuth:
        return self.__auth

    async def call_paginated_api(self, api_path: str, query_args: Dict = {}, **kwargs):
        page = 1
        end = False

        values = []

        while True:
            if len(values) == 0:

                if end:
                    return

                query_args["page"] = page
                resp = await self._scm_api_call(
                    api_path,
                    query_args=query_args,
                    auth=self.__auth,
                    **kwargs,
                )
                page += 1

                if not resp.ok:
                    return

                ret_dict = resp.json()
                if "next" not in ret_dict.keys():
                    end = True
                values = ret_dict.get("values")

            if len(values) > 0:
                yield values.pop()

    async def lu_iterator(self) -> AsyncGenerator[Dict, None]:
        async for x in self.call_paginated_api(api_path="/user/workspaces"):
            yield x

    @property
    def scm_name(self) -> str:
        return "BitBucket Cloud"

    def get_lu_name(self, lu: Any) -> str:
        return lu.get("workspace", {}).get("slug", "UNKNOWN")

    def get_lu_repr(self, lu: Any) -> str:
        return f"{self.get_lu_name(lu)}:{lu.get('workspace', {}).get('links', {}).get('self', {}).get('href')}"
