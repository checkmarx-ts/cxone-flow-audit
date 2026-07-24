import csv
from typing import Dict, AsyncGenerator, Any, Awaitable
from asyncio import gather, Lock
from cxoneflow_audit.core import Auditor
from cxoneflow_audit.core.common import ConfigState
from .ado_service import HookData, ADOService


class AdoAuditor(Auditor):

    def __init__(self, scm_api_service: ADOService, *args, **kwargs):
        Auditor.__init__(self, scm_api_service=scm_api_service, *args, **kwargs)

    async def _evaluate_subscription_state(self, project_id: str) -> ConfigState:
        if project_id not in self.__data.keys():
            return ConfigState.NOT_CONFIGURED

        return await self.scm_service.evaluate_subscription_state(
            self.__data[project_id]
        )

    async def __record_pr_create(self, project_id: str, sub_json: Dict) -> None:
        async with self.__lock:
            self.scm_service.update_hook_pr_create_from_sub_json(
                self.__data[project_id], sub_json
            )

    async def __record_pr_update(self, project_id: str, sub_json: Dict) -> None:
        async with self.__lock:
            self.scm_service.update_hook_pr_update_from_sub_json(
                self.__data[project_id], sub_json
            )

    async def __record_push(self, project_id: str, sub_json: Dict) -> None:
        async with self.__lock:
            self.scm_service.update_hook_push_from_sub_json(
                self.__data[project_id], sub_json
            )

    async def __validate_event_set(
        self, project_id: str, event_name: str, record_lambda: Awaitable, sub_json: Dict
    ) -> None:
        for sub in self.scm_service.get_subs_for_project(
            sub_json,
            project_id,
            self.scm_service.make_cx_endpoint_url(self.cxoneflow_url),
            [event_name],
        ):
            await record_lambda(project_id, sub)

    async def _process_lu(self, lu_data: Any) -> bool:
        self.log().debug(f"Processing: {self.scm_service.get_lu_repr(lu_data)}")

        async with self.__lock:
            if lu_data["id"] not in self.__data.keys():
                self.__data[lu_data["id"]] = self.scm_service.hook_data_from_lu_factory(
                    lu_data
                )

        subs = await self.scm_service.list_lu_webhook_subscriptions(
            lu_data["collection"]
        )

        await gather(
            self.__validate_event_set(
                lu_data["id"], "git.pullrequest.created", self.__record_pr_create, subs
            ),
            self.__validate_event_set(
                lu_data["id"], "git.pullrequest.updated", self.__record_pr_update, subs
            ),
            self.__validate_event_set(
                lu_data["id"], "git.push", self.__record_push, subs
            ),
        )

        return True

    async def execute(self) -> int:
        self.__data = {}
        self.__lock = Lock()

        result = await super().execute()

        with open(self.outfile, "wt") as csv_dest:
            writer = csv.writer(csv_dest, lineterminator="\n", quoting=csv.QUOTE_ALL)
            # pylint: disable=E1101
            sorted_fields = sorted(list(HookData.__dataclass_fields__.keys()))
            headers = ["state"] + sorted_fields
            writer.writerow(headers)
            for pid in self.__data.keys():
                state = await self._evaluate_subscription_state(pid)
                if not (self.skip_configured and state == ConfigState.CONFIGURED):
                    writer.writerow(
                        [state] + [self.__data[pid].__dict__[x] for x in sorted_fields]
                    )

        return result
