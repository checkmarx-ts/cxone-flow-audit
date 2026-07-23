from typing import Dict, Any, AsyncGenerator
import requests
import requests.auth
from asyncio import to_thread
from cxoneflow_audit.__version__ import PROGNAME
from cxoneflow_audit.util import ScmException


class HTTPBearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        requests.auth.AuthBase.__init__(self)
        self.__token = token

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.__token}"
        return r


class SCMAPIService:
    def __init__(
        self,
        api_base_url: str,
        *args,
        proxy: str = None,
        ssl_verify: bool = True,
        **kwargs,
    ):
        self.__scm_url = api_base_url.rstrip("/") + "/"
        self.__proxies = proxy
        self.__ssl_verify = ssl_verify
        self.__required_headers = {"User-Agent": PROGNAME}

    @property
    def proxies(self) -> Dict:
        return self.__proxies

    @property
    def ssl_verify(self) -> bool:
        return self.__ssl_verify

    async def _scm_api_call(
        self,
        api_path: str,
        headers: Dict = {},
        query_args: Dict[str, str] = None,
        method: str = "GET",
        json_body: Dict = None,
        **kwargs,
    ) -> requests.Response:
        url = self.__scm_url + api_path.lstrip("/")

        headers.update(self.__required_headers)

        resp = await to_thread(
            requests.request,
            method,
            url,
            params=query_args,
            headers=headers,
            proxies=self.__proxies,
            verify=self.__ssl_verify,
            json=json_body,
            **kwargs,
        )

        if not resp.ok:
            raise ScmException(resp)

        return resp

    def get_lu_name(self, lu: Any) -> str:
        raise NotImplementedError("_get_lu_name")

    def get_lu_repr(self, lu: Any) -> str:
        raise NotImplementedError("_get_lu_repr")

    async def lu_iterator(self) -> AsyncGenerator[Dict, None]:
        raise NotImplementedError("_lu_iterator")

    @property
    def scm_name(self) -> str:
        raise NotImplementedError("_scm_name")
