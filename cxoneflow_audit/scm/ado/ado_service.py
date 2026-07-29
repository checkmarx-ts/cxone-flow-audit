import base64, requests
from requests.auth import AuthBase
from asyncio import Lock, to_thread
from datetime import datetime, timedelta, timezone
import datetime as datetime_module
import urllib.parse
from dataclasses import dataclass
from typing import Dict, AsyncGenerator, List, Any, Union
from jsonpath_ng.ext import parse
from cxoneflow_audit.__version__ import PROGNAME
from cxoneflow_audit.util import ScmException
from cxoneflow_audit.core.common import ConfigState
from cxoneflow_audit.scm import SCMAPIService, HTTPTokenBasicAuth, HTTPBearerAuth
from cxoneflow_audit.util import ScmException, ServicePrincipalAuthException

# Python 3.10 compatibility
UTC = getattr(datetime_module, "UTC", timezone.utc)


@dataclass(frozen=False)
class HookData:
    projectCollection: str
    projectName: str
    projectUrl: str
    projectVisibility: str

    hasEventPrCreate: bool = False
    prCreateEventCreateDate: str = None
    prCreateEventCreatedBy: str = None
    prCreateEventModDate: str = None
    prCreateEventModBy: str = None
    prCreateEventStatus: str = None

    hasEventPrUpdate: bool = False
    prUpdateEventCreateDate: str = None
    prUpdateEventCreatedBy: str = None
    prUpdateEventModDate: str = None
    prUpdateEventModBy: str = None
    prUpdateEventStatus: str = None

    hasEventPush: bool = False
    pushEventCreateDate: str = None
    pushEventCreatedBy: str = None
    pushEventModDate: str = None
    pushEventModBy: str = None
    pushEventStatus: str = None


class ADOService(SCMAPIService):

    ADO_API_VERSION = "7.1"

    ADO_EVENT_TYPES = ["git.push", "git.pullrequest.created", "git.pullrequest.updated"]

    def __init__(self, targets: List[str], *args, **kwargs):
        SCMAPIService.__init__(self, *args, **kwargs)
        self.__lock = Lock()
        self.__sub_cache = {}
        self.__targets = targets

    async def _get_auth(self, force_reauth=False) -> AuthBase:
        raise NotImplementedError("_get_auth")

    def _encode(self, value: str) -> str:
        return f"{urllib.parse.quote(value)}"

    async def _scm_api_call(
        self, query_args: Dict = {}, *args, **kwargs
    ) -> requests.Response:
        retry = True

        query_args.update(self._api_ver_url_params())

        while True:
            resp = await SCMAPIService._scm_api_call(
                self,
                auth=await self._get_auth(not retry),
                query_args=query_args,
                *args,
                **kwargs,
            )

            if retry and resp.status_code == 401:
                retry = False
            else:
                return resp

    @property
    def scm_name(self) -> str:
        return "ADO"

    def get_lu_name(self, lu: Any) -> str:
        return lu["name"]

    def get_lu_repr(self, lu: Any) -> str:
        return f"ADO:{lu['collection']}:{lu['name']}:{lu['visibility']}:{lu['url']}"

    def __project_list_url_params(self, skip: int) -> str:
        ret = {"$skip": str(skip)}
        ret.update(self._api_ver_url_params())
        return ret

    def make_cx_endpoint_url(self, base_url: str) -> str:
        u = base_url.rstrip("/")
        return f"{u}/adoe"

    def _required_headers(self, scm_pat: str) -> Dict:
        auth_b64 = base64.b64encode(f":{scm_pat}".encode("UTF-8")).decode()
        return {"Authorization": f"Basic {auth_b64}", "User-Agent": PROGNAME}

    def _api_ver_url_params(self, version: str = ADO_API_VERSION) -> str:
        return {"api-version": version}

    def org_url(self, collection: str) -> str:
        return f"{urllib.parse.quote(collection)}"

    async def evaluate_subscription_state(self, data: HookData) -> ConfigState:
        if data.hasEventPrCreate and data.hasEventPrUpdate and data.hasEventPush:
            return ConfigState.CONFIGURED
        elif not (
            (data.hasEventPrCreate and data.hasEventPrUpdate and data.hasEventPush)
            or data.hasEventPrCreate
            or data.hasEventPrUpdate
            or data.hasEventPush
        ):
            return ConfigState.NOT_CONFIGURED
        else:
            return ConfigState.PARTIAL_CONFIG

    @staticmethod
    def update_hook_push_from_sub_json(data: HookData, sub_json: Dict) -> None:
        data.hasEventPush = sub_json["status"] == "enabled"
        data.pushEventCreateDate = sub_json["createdDate"]
        data.pushEventCreatedBy = sub_json["createdBy"]["uniqueName"]
        data.pushEventModDate = sub_json["modifiedDate"]
        data.pushEventModBy = sub_json["modifiedBy"]["uniqueName"]
        data.pushEventStatus = sub_json["status"]

    @staticmethod
    def update_hook_pr_create_from_sub_json(data: HookData, sub_json: Dict) -> None:
        data.hasEventPrCreate = sub_json["status"] == "enabled"
        data.prCreateEventCreateDate = sub_json["createdDate"]
        data.prCreateEventCreatedBy = sub_json["createdBy"]["uniqueName"]
        data.prCreateEventModDate = sub_json["modifiedDate"]
        data.prCreateEventModBy = sub_json["modifiedBy"]["uniqueName"]
        data.prCreateEventStatus = sub_json["status"]

    @staticmethod
    def update_hook_pr_update_from_sub_json(data: HookData, sub_json: Dict) -> None:
        data.hasEventPrUpdate = sub_json["status"] == "enabled"
        data.prUpdateEventCreateDate = sub_json["createdDate"]
        data.prUpdateEventCreatedBy = sub_json["createdBy"]["uniqueName"]
        data.prUpdateEventModDate = sub_json["modifiedDate"]
        data.prUpdateEventModBy = sub_json["modifiedBy"]["uniqueName"]
        data.prUpdateEventStatus = sub_json["status"]

    @staticmethod
    def update_hook_by_event_type(
        event_type: str, data: HookData, sub_json: Dict
    ) -> None:
        return ADOService.__update_map[event_type](data, sub_json)

    def hook_data_from_lu_factory(self, lu_json: Dict) -> HookData:
        return HookData(
            projectCollection=lu_json["collection"],
            projectName=lu_json["name"],
            projectUrl=lu_json["url"],
            projectVisibility=lu_json["visibility"],
        )

    def get_subs_for_project(
        self, sub: str, project_id: str, cx_adoe_ep_url: str, event_types: List[str]
    ) -> List[Dict]:
        event_regex = "|".join(event_types)

        query_str = (
            "$.value[?(@.publisherInputs.projectId == '"
            + project_id
            + "' & @.consumerInputs.url =~ '"
            + cx_adoe_ep_url
            + "' & @.eventType =~ '"
            + event_regex
            + "')]"
        )

        return [q.value for q in parse(query_str).find(sub)]

    async def list_lu_webhook_subscriptions(
        self,
        collection: str,
    ) -> Dict:
        async with self.__lock:
            if collection in self.__sub_cache.keys():
                self.log().debug(f"Subscription cache hit for {collection}")
                return self.__sub_cache[collection]

        service_params = {
            "organization": collection,
            "consumerActionId": "httpRequest",
            "consumerId": "webHooks",
        }

        service_params.update(self._api_ver_url_params())

        resp = await self._scm_api_call(
            api_path=f"{self._encode(collection)}/_apis/hooks/subscriptions",
            query_args=service_params,
        )

        if resp.ok:
            async with self.__lock:
                self.__sub_cache[collection] = resp.json()
            return resp.json()

    async def lu_iterator(
        self,
    ) -> AsyncGenerator[Dict, None]:

        for t in self.__targets:
            skip = 0

            while True:

                resp = await self._scm_api_call(
                    api_path=f"{self._encode(t)}/_apis/projects",
                    query_args=self.__project_list_url_params(skip),
                )

                if resp.ok:
                    json = resp.json()
                    skip = json["count"]
                    if skip == 0:
                        break
                    for v in json["value"]:
                        ret_val = dict(v)
                        ret_val["collection"] = t
                        yield ret_val
                else:
                    raise ScmException(resp)

    def find_sub_for_event(
        self, event_type: str, subs: List[Dict]
    ) -> Union[Dict, None]:
        for found in parse("$[?(@.eventType == '" + event_type + "')]").find(subs):
            return found.value

    async def create_subscription(
        self,
        event_type: str,
        project_id: str,
        collection: str,
        cxoneflow_url: str,
        shared_secret: str,
    ) -> None:
        payload = {
            "publisherId": "tfs",
            "eventType": event_type,
            "resourceVersion": "1.0",
            "consumerId": "webHooks",
            "consumerActionId": "httpRequest",
            "publisherInputs": {"projectId": project_id},
            "consumerInputs": {
                "url": self.make_cx_endpoint_url(cxoneflow_url),
                "basicAuthPassword": shared_secret,
            },
        }

        resp = await self._scm_api_call(
            api_path=f"{self._encode(collection)}/_apis/hooks/subscriptions",
            json_body=payload,
            query_args=self._api_ver_url_params(),
            method="POST",
        )

        if not resp.ok:
            raise ScmException(resp)

    async def delete_subscription(
        self,
        collection: str,
        sub_id: str,
    ):

        resp = await self._scm_api_call(
            api_path=f"{self._encode(collection)}/_apis/hooks/subscriptions/{sub_id}",
            query_args=self._api_ver_url_params(),
            method="DELETE",
        )
        if not resp.ok:
            raise ScmException(resp)

    __update_map = {
        "git.pullrequest.updated": update_hook_pr_update_from_sub_json,
        "git.pullrequest.created": update_hook_pr_create_from_sub_json,
        "git.push": update_hook_push_from_sub_json,
    }

    async def get_repo_ref_list(
        self, collection_name: str, project_name: str, repo_name: str, query_args: Dict
    ) -> requests.Response:
        return await self._scm_api_call(
            api_path=self._encode(collection_name)
            + f"/{self._encode(project_name)}/_apis/git/repositories/"
            + f"{self._encode(repo_name)}/refs",
            query_args=query_args,
        )

    async def get_repo_list(
        self, collection_name: str, project_name: str
    ) -> requests.Response:
        return await self._scm_api_call(
            api_path=f"{self._encode(collection_name)}/{self._encode(project_name)}/_apis/git/repositories"
        )


class ADOBasicAuthService(ADOService):
    def __init__(
        self,
        auth: HTTPTokenBasicAuth,
        *args,
        **kwargs,
    ):
        ADOService.__init__(self, *args, **kwargs)
        self.__auth = auth

    async def _get_auth(self, force_reauth=False) -> AuthBase:
        return self.__auth


class ADOSPAuthService(ADOService):

    def __init__(
        self,
        sp_tenant_id: str,
        sp_client_id: str,
        sp_client_secret: str,
        *args,
        **kwargs,
    ):
        ADOService.__init__(self, *args, **kwargs)

        self.__lock = Lock()
        self.__cached_token = None
        self.__token_exp = None

        self.__token_auth_url = (
            f"https://login.microsoftonline.com/{sp_tenant_id}/oauth2/v2.0/token"
        )

        self.__auth_payload = {
            "client_id": sp_client_id,
            "scope": "https://app.vssps.visualstudio.com/.default",
            "client_secret": sp_client_secret,
            "grant_type": "client_credentials",
        }

    async def _get_auth(self, force_reauth=False) -> AuthBase:
        async with self.__lock:

            if force_reauth:
                self.__cached_token = self.__token_exp = None

            if self.__cached_token is not None:
                if (
                    self.__token_exp is not None
                    and datetime.now(UTC) < self.__token_exp
                ):
                    return HTTPBearerAuth(self.__cached_token)
                else:
                    self.__cached_token = self.__token_exp = None

            auth_resp = await to_thread(
                requests.post,
                url=self.__token_auth_url,
                headers=self.required_headers,
                data=self.__auth_payload,
                proxies=self.proxies,
                verify=self.ssl_verify,
            )

            if not auth_resp.ok:
                raise ScmException(auth_resp)
            else:
                self.__cached_token = auth_resp.json().get("access_token", None)
                self.__token_exp = (
                    datetime.now(UTC)
                    + timedelta(seconds=auth_resp.json().get("expires_in", 0))
                    if self.__cached_token is not None
                    else None
                )

            if self.__cached_token is None:
                raise ServicePrincipalAuthException(self.__token_auth_url)

            return HTTPBearerAuth(self.__cached_token)
