from typing import Dict
import requests
import requests.auth
from asyncio import to_thread


class HTTPBearerAuth(requests.auth.AuthBase):
  def __init__(self, token):
      requests.auth.AuthBase.__init__(self)
      self.__token = token

  def __call__(self, r):
      r.headers["Authorization"] = f"Bearer {self.__token}"
      return r


class APIAccessor:
  def __init__(self, api_base_url : str, proxies : Dict, ssl_verify : bool, auth : requests.auth.AuthBase):
    self.__scm_url = api_base_url.rstrip("/") + "/"
    self.__proxies = proxies
    self.__ignore_ssl_errors = ssl_verify
    self.auth = auth


  async def _api_call(self, api_path : str, query_args : Dict[str, str] = None, method : str = "GET", json_body : Dict = None,
                      headers : Dict = {}, auth : requests.auth.AuthBase = None) -> requests.Response:
    url = self.__scm_url + api_path.lstrip("/")

    return await to_thread(requests.request, method, url, params=query_args,
                     headers=headers, proxies=self.__proxies,
                     verify=not self.__ignore_ssl_errors, json=json_body, auth=auth)
