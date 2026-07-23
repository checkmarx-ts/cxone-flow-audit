from asyncio import Semaphore
from cxoneflow_audit.util import NameMatcher
from typing import Dict, List, AsyncGenerator, Any
import logging, asyncio
from enum import Enum
from cxoneflow_audit.scm import SCMAPIService


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

    def __init__(
        self,
        targets: List[str],
        concurrency: Semaphore,
        match: NameMatcher,
        scm_api_service: SCMAPIService,
        cxoneflow_url: str,
    ):
        self.__concurrency = concurrency
        self.__targets = targets
        self.__match = match
        self.__scm_service = scm_api_service
        self.__cx_url = cxoneflow_url

    @property
    def scm_service(self) -> SCMAPIService:
        return self.__scm_service

    @property
    def cxoneflow_url(self) -> str:
        return self.__cx_url

    @property
    def targets(self) -> List[str]:
        return self.__targets

    async def __thread(self, lu: Any) -> bool:
        async with self.__concurrency:
            if self.__match.matches(self.__scm_service.get_lu_name(lu)):
                return await self._process_lu(lu)
            else:
                self.log().info(
                    f"LU skipped due to match rules: {self.__scm_service.get_lu_repr(lu)}"
                )
                return True

    async def execute(self) -> int:
        lus = []

        self.log().info(f"Retrieving LUs for SCM {self.__scm_service.scm_name}")

        async for lu_data in self.__scm_service.lu_iterator():
            lus.append(lu_data)

        self.log().debug(f"{len(lus)} LUs found for SCM {self.__scm_service.scm_name}")

        task_result = []

        if len(lus) > 0:
            task_result = await asyncio.gather(
                *[
                    asyncio.get_running_loop().create_task(self.__thread(t))
                    for t in lus
                ],
                return_exceptions=True,
            )
        result_code = 0
        for res in task_result:
            if isinstance(res, BaseException):
                self.log().exception(res)
                result_code = max(result_code, 2)
            elif not res:
                result_code = 100

        return result_code

    async def _process_lu(self, lu: Any) -> bool:
        raise NotImplementedError("_process_lu")

    def _eval_correct_webhook_url(self, url: str) -> bool:
        return url.startswith(self.cxoneflow_url)
