import requests, time, jwt
from typing import Dict, AsyncGenerator, Callable, Coroutine, Any, Union
from asyncio import Lock
from dataclasses import dataclass
from cxoneflow_audit.scm import SCMAPIService
from cxoneflow_audit.__version__ import PROGNAME
from cxoneflow_audit.util import ScmException, NotFoundException
from cxoneflow_audit.scm import HTTPBearerAuth


@dataclass(frozen=False)
class HookData:
    _orgName: str
    _orgId: int
    _orgUrl: str
    hasOrgWebhook: bool = False
    orgWebhookActive: bool = None
    orgWebhookCreatedAt: str = None
    orgWebhookUpdatedAt: str = None
    orgWebhookConfigUrl: str = None
    orgWebhookPushEvents: bool = None
    orgWebhookPREvents: bool = None
    orgWebhookJsonContentType: bool = None
    hasGithubApp: bool = False
    githubAppPendingApproval: bool = None
    githubAppPendingRequestDate: str = None
    githubAppPendingRequester: str = None
    githhubAppCreatedAt: str = None
    githubAppUpdatedAt: str = None
    githubAppId: str = None
    githubInstallId: str = None
    githubAppSlug: str = None
    githubAppInstallUrl: str = None
    githubAppAllRepos: bool = None
    githubAppCorrectPermissions: bool = None
    githubAppCorrectEvents: bool = None
    githubAppSuspended: bool = None
    githubAppSuspendedBy: str = None
    githubAppSuspendedAt: str = None
    githubAppCorrectWebhookUrl: bool = None


@dataclass(frozen=True)
class PendingInstallData:
    requestDate: str
    requester: str
    org: str


class GHService(SCMAPIService):

    def __init__(
        self,
        auth: HTTPBearerAuth,
        app_slug: str,
        app_key_file: str = None,
        *args,
        **kwargs,
    ):
        SCMAPIService.__init__(self, *args, **kwargs)
        self.__scm_token_auth = auth
        self.__app_slug = app_slug
        self.__app_id = None
        self.__app_api_lock = Lock()
        self.__general_lock = Lock()
        self.__app_webhook = None
        self.__pending_install_orgs = None

        if app_key_file is not None:
            with open(app_key_file, "rt", encoding="UTF-8") as k:
                self.__private_key = k.read()
        else:
            self.__private_key = None

    @property
    def scm_name(self) -> str:
        return "Github"

    def get_lu_name(self, lu: Any) -> str:
        return lu["login"]

    def get_lu_repr(self, lu: Any) -> str:
        return f"{lu['login']}:{lu['id']}:{lu['url']}"

    @property
    def read_app_config(self) -> bool:
        return not self.__private_key is None

    @property
    def check_for_app(self) -> bool:
        return not self.__app_slug is None

    async def __app_api_call(
        self,
        api_path: str,
        *args,
        **kwargs,
    ) -> requests.Response:
        async with self.__app_api_lock:
            if self.__app_id is None and self.__app_slug is not None:
                res = await self._scm_api_call(
                    api_path=f"/apps/{self.__app_slug}",
                    auth=self.__scm_token_auth,
                )
                if not res.ok:
                    return None
                else:
                    app_data = res.json()
                    self.__app_id = app_data["id"]

        payload = {
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "iss": str(self.__app_id),
            "alg": "RS256",
        }

        headers = {
            "Authorization": f"Bearer {jwt.encode(payload, self.__private_key, algorithm='RS256')}",
        }

        if "headers" in kwargs.keys():
            kwargs["headers"].update(headers)
        else:
            kwargs["headers"] = headers

        return await self._scm_api_call(api_path, *args, **kwargs)

    # pylint: disable=W0102
    async def __api_generator(
        self,
        coro: Coroutine,
        api_path: str,
        query_args: Dict[str, str] = {},
        per_page: int = 100,
        page_param: str = "page",
        page_by_count: bool = True,
        initial_page_count_val: Any = 1,
        next_page_calc: Callable[[Any, Dict], Any] = None,
        iterate_element: str = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[Dict, None]:
        opt_dict = {"per_page": str(per_page)}
        opt_dict.update(query_args)

        while True:
            if page_by_count:
                if page_param in opt_dict.keys():
                    opt_dict[page_param] += 1
                else:
                    opt_dict[page_param] = initial_page_count_val

            try:
                res = await coro(
                    api_path=api_path, query_args=opt_dict, *args, **kwargs
                )
            except ScmException as scm_ex:
                if scm_ex.response.status_code != 404:
                    raise
                else:
                    raise NotFoundException(api_path)

            element = (
                res.json() if iterate_element is None else res.json()[iterate_element]
            )

            if len(element) == 0:
                break

            for data in element:
                if not page_by_count:
                    opt_dict[page_param] = next_page_calc(
                        (
                            opt_dict[page_param]
                            if page_param in opt_dict.keys()
                            else initial_page_count_val
                        ),
                        data,
                    )
                yield data

    async def organization_hooks_iterator(
        self, org_name: str
    ) -> AsyncGenerator[Dict, None]:
        return self.__api_generator(
            self._scm_api_call, f"/orgs/{org_name}/hooks", auth=self.__scm_token_auth
        )

    async def lu_iterator(self) -> AsyncGenerator[Dict, None]:
        async for x in self.__api_generator(
            self._scm_api_call,
            "/organizations",
            page_by_count=False,
            page_param="since",
            next_page_calc=lambda _, data: str(data["id"]),
            auth=self.__scm_token_auth,
        ):
            yield x

    async def get_app_pending_install(
        self, org: str
    ) -> Union[PendingInstallData, None]:
        if not self.read_app_config:
            return None

        async with self.__general_lock:
            if self.__pending_install_orgs is None:
                self.__pending_install_orgs = {}

                async for req in self.__api_generator(
                    self.__app_api_call, "/app/installation-requests"
                ):
                    self.__pending_install_orgs[req["account"]["login"]] = (
                        PendingInstallData(
                            requestDate=req["created_at"],
                            requester=req["requester"]["login"],
                            org=req["account"]["login"],
                        )
                    )
        return self.__pending_install_orgs.get(org)

    async def get_app_webhook_endpoint(self) -> Union[str, None]:
        if not self.read_app_config:
            return None

        async with self.__general_lock:
            if self.__app_webhook is None:
                res = await self.__app_api_call("/app/hook/config")
                if not res.ok:
                    return None
                else:
                    self.__app_webhook = res.json()["url"]

        return self.__app_webhook

    async def get_org_installed_app(self, org_name: str) -> Union[Dict, None]:
        async for app in self.__api_generator(
            self._scm_api_call,
            f"/orgs/{org_name}/installations",
            iterate_element="installations",
            auth=self.__scm_token_auth,
        ):
            if (
                self.__app_slug is not None
                and app["app_slug"] == self.__app_slug.lower()
            ):
                return app

    def __make_hook_payload(self, cxoneflow_url: str, shared_secret: str) -> Dict:
        return {
            "name": "web",
            "config": {
                "url": cxoneflow_url.rstrip("/") + "/gh",
                "secret": shared_secret,
                "content_type": "json",
            },
            "events": ["pull_request", "pull_request_review", "push"],
            "active": True,
        }

    async def create_webhook(
        self, org_name: str, shared_secret: str, cxoneflow_url: str
    ) -> bool:
        return (
            await self._scm_api_call(
                f"/orgs/{org_name}/hooks",
                method="POST",
                json_body=self.__make_hook_payload(cxoneflow_url, shared_secret),
                auth=self.__scm_token_auth,
            )
        ).ok

    async def delete_webhook(self, org_name: str, hook_id: int) -> bool:
        return (
            await self._scm_api_call(
                f"/orgs/{org_name}/hooks/{hook_id}",
                method="DELETE",
                auth=self.__scm_token_auth,
            )
        ).ok

    async def replace_webhook(
        self, org_name: str, shared_secret: str, hook_id: int, cxoneflow_url: str
    ) -> bool:
        return (
            await self._scm_api_call(
                f"/orgs/{org_name}/hooks/{hook_id}",
                method="PATCH",
                json_body=self.__make_hook_payload(cxoneflow_url, shared_secret),
                auth=self.__scm_token_auth,
            )
        ).ok

    async def remove_app(self, install_id: int) -> bool:
        return (
            await self.__app_api_call(
                f"/app/installations/{install_id}", method="DELETE"
            )
        ).ok

    async def repo_iterator(self, org_name: str) -> AsyncGenerator[Dict, None]:
        async for repo in self.__api_generator(
            self._scm_api_call, f"/orgs/{org_name}/repos", auth=self.__scm_token_auth
        ):
            yield repo

    async def get_latest_repo_commit(
        self, org_name: str, repo_name: str, branch_name: str
    ) -> Union[str, None]:

        data = await self._scm_api_call(
            f"/repos/{org_name}/{repo_name}/commits",
            {"sha": branch_name, "per_page": "1"},
            auth=self.__scm_token_auth,
        )

        if data.ok:
            return data.json().pop()["sha"]
        else:
            return None
