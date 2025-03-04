from asyncio import Semaphore
from cxoneflow_audit.util import NameMatcher
from typing import Dict, List, AsyncGenerator, Any
import logging, asyncio
from enum import Enum
from dataclasses import dataclass

class ConfigState(Enum):
  def __str__(self):
    return str(self.value)

  CONFIGURED = "Configured"
  PARTIAL_CONFIG = "Partially Configured"
  NOT_CONFIGURED = "Not Configured"
  UNKNOWN = "Unknown"

class Operation:

  @classmethod
  def log(clazz) -> logging.Logger:
      return logging.getLogger(clazz.__name__)

  def __init__(self, targets : List[str], concurrency : Semaphore, match : NameMatcher, pat : str, cx_url : str,
               shared_secret : str, scm_url : str, proxy : Dict, ignore_ssl_errors : bool):
    self.__concurrency = concurrency
    self.__targets = targets
    self.__match = match
    self.__pat = pat
    self.__cx_url = cx_url
    self.__scm_url = scm_url
    self.__shared_secret = shared_secret
    self.__proxies = proxy
    self.__ignore_ssl_errors = ignore_ssl_errors

  @property
  def proxies(self) -> Dict:
    return self.__proxies

  @property
  def ignore_ssl_errors(self) -> bool:
    return self.__ignore_ssl_errors

  @property
  def scm_pat(self) -> str:
    return self.__pat
  
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
  def shared_secret(self) -> str:
    return self.__shared_secret
  
  @property
  def _scm_name(self) -> str:
    raise NotImplementedError("_scm_name")
  
  def _get_lu_name(self, lu : Any) -> str:
    raise NotImplementedError("_get_match_part_of_lu")

  def _get_lu_repr(self, lu : Any) -> str:
    raise NotImplementedError("_get_lu_repr")

  async def _lu_iterator(self) -> AsyncGenerator[Dict, None]:
    raise NotImplementedError("_lu_iterator")

  async def _exec_on_target(self, target_name : str):
    raise NotImplementedError("_exec_on_target")

  async def __thread(self, lu : Any) -> bool:
    async with self.__concurrency:
      if self.__match.should_keep(self._get_lu_name(lu)):
        return await self._process_lu(lu)
      else:
        self.log().debug(f"LU skipped due to no match: {self._get_lu_repr(lu)}")

  async def _process_lu(self, lu : Any) -> bool:
    raise NotImplementedError("_process_lu")

  async def execute(self) -> int:
    lus = []

    self.log().debug(f"Retrieving LUs for SCM {self._scm_name}")

    async for lu_data in self._lu_iterator():
      lus.append(lu_data)

    self.log().debug(f"{len(lus)} LUs found for SCM {self._scm_name}")

    task_result, _ = await asyncio.wait([asyncio.get_running_loop()
                                         .create_task(self.__thread(t)) for t in lus]) 
    ret = 0
    for res in task_result:
      if isinstance(res, BaseException):
        self.log().exception(res)
        ret = max(ret, 2)
      elif not res:
        ret = 100

    return ret
