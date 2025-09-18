import time
from typing import Dict, AsyncGenerator, Coroutine, Callable, Any, Union
from dataclasses import dataclass
from asyncio import to_thread, Lock
import requests
import jwt
from cxoneflow_audit.util import ScmException
from cxoneflow_audit.__version__ import PROGNAME


@dataclass(frozen=False)
class HookData:
  _orgName : str
  _orgId : int
  _orgUrl : str
  hasOrgWebhook : bool = False
  orgWebhookActive : bool = False
  orgWebhookCreatedAt : str = None
  orgWebhookUpdatedAt : str = None
  orgWebhookConfigUrl : str = None
  orgWebhookPushEvents : bool = False
  orgWebhookPREvents : bool = False
  hasGithubApp : bool = None
  pendingGithubAppApproval : bool = None
  pendingRequestDate : str = None
  pendingRequester : str = None
  githhubAppCreatedAt : str = None
  githubAppUpdatedAt : str = None
  githubAppId : str = None
  githubInstallId : str = None
  githubAppSlug : str = None
  githubAppInstallUrl : str = None
  githubAppAllRepos : bool = None
  githubAppCorrectPermissions : bool = None
  githubAppCorrectEvents : bool = None
  githubAppSuspended : bool = None
  githubAppSuspendedBy : str = None
  githubAppSuspendedAt : str = None
  githubAppCorrectWebhookUrl : bool = None

@dataclass(frozen=True)
class PendingInstallData:
  requestDate : str
  requester : str
  org : str


class GithubBase:
  def __init__(self, cxone_flow_url : str, scm_url : str, pat : str, proxy : Dict, ignore_ssl_errors : bool,
               app_slug : str, app_key_file : str):
    self.__scm_url = scm_url.rstrip("/") + "/"
    self.__proxies = proxy
    self.__ignore_ssl_errors = ignore_ssl_errors
    self.__scm_pat = pat
    self.__webhook_url = cxone_flow_url.rstrip("/") + "/gh"
    self.__app_slug = app_slug
    self.__app_id = None
    self.__app_api_lock = Lock()
    self.__general_lock = Lock()
    self.__app_webhook = None
    self.__pending_install_orgs = None

    with open(app_key_file, "rt", encoding="UTF-8") as k:
      self.__private_key = k.read()


  @property
  def webhook_url(self) -> str:
    return self.__webhook_url

  def __required_pat_headers(self) -> Dict:
    return {
      "Authorization" : f"Bearer {self.__scm_pat}",
      "User-Agent" : PROGNAME
      }

  async def __app_api_call(self, api_path : str, query_args : Dict[str, str] = None) -> requests.Response:
    async with self.__app_api_lock:
      if self.__app_id is None and self.__app_slug is not None:
        res = await self.__api_call(f"/apps/{self.__app_slug}")
        if not res.ok:
          return None
        else:
          app_data = res.json()
          self.__app_id = app_data['id']

    payload = {
        'iat' : int(time.time()),
        "exp" : int(time.time()) + 600,
        'iss' : self.__app_id,
        'alg' : "RS256"
    }

    headers = {
      "Authorization" : f"Bearer {jwt.encode(payload, self.__private_key, algorithm='RS256')}",
      "User-Agent" : PROGNAME
      }

    url = self.__scm_url + api_path.lstrip("/")

    return await to_thread(requests.request, "GET", url, params=query_args,
                     headers=headers, proxies=self.__proxies,
                     verify=not self.__ignore_ssl_errors)

  async def __api_call(self, api_path : str, query_args : Dict[str, str] = None) -> requests.Response:

    url = self.__scm_url + api_path.lstrip("/")

    return await to_thread(requests.request, "GET", url, params=query_args,
                     headers=self.__required_pat_headers(), proxies=self.__proxies,
                     verify=not self.__ignore_ssl_errors)


  # pylint: disable=W0102
  async def __api_generator(self, coro : Coroutine, api_path : str, query_args : Dict[str, str] = {},
                            per_page : int = 100, page_param : str = "page", page_by_count : bool = True,
                            initial_page_count_val : Any = 0,
                            next_page_calc : Callable[[Any, Dict], Any] = None,
                            iterate_element : str = None) -> AsyncGenerator[Dict, None]:
    opt_dict = {"per_page" : per_page}
    opt_dict.update(query_args)

    while True:
      res = await coro(api_path, opt_dict)
      if page_by_count:
        if page_param in opt_dict.keys():
          opt_dict[page_param] += 1
        else:
          opt_dict[page_param] = initial_page_count_val


      if not res.ok and res.status_code != 404:
        raise ScmException(f"Status {res.status_code} attempting api call {api_path}.")
      elif res.status_code == 404:
        break
      else:
        element = res.json() if iterate_element is None else res.json()[iterate_element]

        if len(element) == 0:
          break

        for data in element:
          if not page_by_count:
            opt_dict[page_param] = next_page_calc(opt_dict[page_param] if page_param in opt_dict.keys() else initial_page_count_val, data)
          yield data



  async def _organization_hooks_iterator(self, org_name : str) -> AsyncGenerator[Dict, None]:
    return self.__api_generator(self.__api_call, f"/orgs/{org_name}/hooks")

  async def _organization_iterator(self) -> AsyncGenerator[Dict, None]:
    return self.__api_generator(self.__api_call, "/organizations", 
                                page_by_count = False, page_param="since",
                                next_page_calc=lambda _, data : data['id'])

  async def _get_app_pending_install(self, org : str) -> Union[PendingInstallData, None]:
    async with self.__general_lock:
      if self.__pending_install_orgs is None:
        self.__pending_install_orgs = {}

        async for req in self.__api_generator(self.__app_api_call, "/app/installation-requests"):
          self.__pending_install_orgs[req['account']['login']]=PendingInstallData(requestDate=req['created_at'],
                                                                requester=req['requester']['login'],
                                                                org=req['account']['login'])
    return self.__pending_install_orgs.get(org)

  async def _get_app_webhook_endpoint(self) -> Union[str, None]:

    async with self.__general_lock:
      if self.__app_webhook is None:
        res = await self.__app_api_call("/app/hook/config")
        if not res.ok:
          return None
        else:
          self.__app_webhook = res.json()['url']

    return self.__app_webhook

  async def _get_org_installed_app(self, org_name : str) -> Union[Dict, None]:
    async for app in self.__api_generator(self.__api_call, f"/orgs/{org_name}/installations", iterate_element="installations"):
      if self.__app_slug is not None and app['app_slug'] == self.__app_slug.lower():
        return app
