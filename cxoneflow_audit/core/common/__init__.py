from asyncio import Semaphore
from cxoneflow_audit.util import NameMatcher
from typing import Dict, List, AsyncGenerator, Any
import logging, asyncio
from enum import Enum
from asyncio import to_thread
import requests
import requests.auth
from cxoneflow_audit.util import ScmException
from cxoneflow_audit.__version__ import PROGNAME

class ConfigState(Enum):
  def __str__(self):
    return str(self.value)

  CONFIGURED = "Configured"
  PARTIAL_CONFIG = "Partially Configured"
  NOT_CONFIGURED = "Not Configured"
  UNKNOWN = "Unknown"
  MISCONFIG = "Misconfigured"

class Operation:

  @classmethod
  def log(clazz) -> logging.Logger:
      return logging.getLogger(clazz.__name__)

  def __init__(self, targets : List[str], concurrency : Semaphore, match : NameMatcher, cx_url : str,
               scm_url : str, proxy : Dict, ignore_ssl_errors : bool):
    self.__concurrency = concurrency
    self.__targets = targets
    self.__match = match
    self.__cx_url = cx_url
    self.__scm_url = scm_url.rstrip("/") + "/"
    self.__proxies = proxy
    self.__ignore_ssl_errors = ignore_ssl_errors

    self.__required_headers = {"User-Agent" : PROGNAME}


  async def __internal_api_call(self, url : str, query_args : Dict[str, str] = None, method : str = "GET", json_body : Dict = None,
                      headers : Dict = {}, auth : requests.auth.AuthBase = None) -> requests.Response:
    resp = await to_thread(requests.request, method, url, params=query_args,
                     headers=headers, proxies=self.proxies,
                     verify=not self.ignore_ssl_errors, json=json_body, auth=auth)
    
    if not resp.ok:
      raise ScmException(f"{url} response: {resp.status_code}")

    return resp

  async def _scm_api_call(self, api_path : str, headers : Dict = {}, **kwargs) -> requests.Response:
    url = self.scm_base_url + api_path.lstrip("/")
    headers.update(self.__required_headers)
    return await self.__internal_api_call(url, headers=headers, **kwargs)


  @property
  def proxies(self) -> Dict:
    return self.__proxies

  @property
  def ignore_ssl_errors(self) -> bool:
    return self.__ignore_ssl_errors

  @property
  def scm_base_url(self) -> str:
    return self.__scm_url

  @property
  def cxone_flow_url(self) -> str:
    return self.__cx_url

  @property
  def targets(self) -> List[str]:
    return self.__targets
  
  @property
  def _scm_name(self) -> str:
    raise NotImplementedError("_scm_name")
  
  def _get_lu_name(self, lu : Any) -> str:
    raise NotImplementedError("_get_lu_name")

  def _get_lu_repr(self, lu : Any) -> str:
    raise NotImplementedError("_get_lu_repr")

  async def _lu_iterator(self) -> AsyncGenerator[Dict, None]:
    raise NotImplementedError("_lu_iterator")

  async def __thread(self, lu : Any) -> bool:
    async with self.__concurrency:
      if self.__match.matches(self._get_lu_name(lu)):
        return await self._process_lu(lu)
      else:
        self.log().info(f"LU skipped due to match rules: {self._get_lu_repr(lu)}")
        return True

  async def _process_lu(self, lu : Any) -> bool:
    raise NotImplementedError("_process_lu")

  async def execute(self) -> int:
    lus = []

    self.log().info(f"Retrieving LUs for SCM {self._scm_name}")

    async for lu_data in self._lu_iterator():
      lus.append(lu_data)

    self.log().debug(f"{len(lus)} LUs found for SCM {self._scm_name}")

    task_result = []

    if len(lus) > 0:
      task_result = await asyncio.gather(*[asyncio.get_running_loop()
                                         .create_task(self.__thread(t)) for t in lus], return_exceptions=True) 
    result_code = 0
    for res in task_result:
      if isinstance(res, BaseException):
        self.log().exception(res)
        result_code = max(result_code, 2)
      elif not res:
        result_code = 100

    return result_code
