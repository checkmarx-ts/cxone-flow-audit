from cxoneflow_audit.core import Deployer
from cxoneflow_audit.core.common import ConfigState
from typing import Any, Dict, AsyncGenerator
from asyncio import gather
from .ado_service import ADOService


class AdoDeployer(Deployer):

    def __init__(self, scm_api_service: ADOService, *args, **kwargs):
        Deployer.__init__(self, scm_api_service=scm_api_service, *args, **kwargs)

    async def _process_lu(self, lu: Any) -> bool:
        subs = self.scm_service.get_subs_for_project(
            await self.scm_service.list_lu_webhook_subscriptions(
                lu["collection"],
            ),
            lu["id"],
            self.scm_service.make_cx_endpoint_url(self.cxoneflow_url),
            ADOService.ADO_EVENT_TYPES,
        )

        hook_data = self.scm_service.hook_data_from_lu_factory(lu)

        for event in ADOService.ADO_EVENT_TYPES:
            sub = self.scm_service.find_sub_for_event(event, subs)
            if sub:
                self.scm_service.update_hook_by_event_type(event, hook_data, sub)

        if (
            await self.scm_service.evaluate_subscription_state(hook_data)
            == ConfigState.CONFIGURED
            and not self.replace
        ):
            self.log().warning(
                f"{self.scm_service.get_lu_repr(lu)} is already configured, no changes made."
            )
            return True

        self.log().info(f"Configuring {self.scm_service.get_lu_repr(lu)}")

        sub_ids = [s["id"] for s in subs]
        if len(sub_ids) > 0:
            await gather(
                *[
                    self.scm_service.delete_subscription(lu["collection"], sub_id)
                    for sub_id in sub_ids
                ]
            )

        await gather(
            *[
                self.scm_service.create_subscription(
                    event,
                    lu["id"],
                    lu["collection"],
                    self.cxoneflow_url,
                    self.shared_secret,
                )
                for event in ADOService.ADO_EVENT_TYPES
            ]
        )

        return True
