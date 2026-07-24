from cxoneflow_audit.core import Remover
from typing import Any
from asyncio import gather
from .ado_service import ADOService

class AdoRemover(Remover):
    def __init__(self, scm_api_service: ADOService, *args, **kwargs):
        Remover.__init__(self, scm_api_service=scm_api_service, *args, **kwargs)

    async def _process_lu(self, lu: Any) -> bool:
        sub_ids = [
            s["id"]
            for s in self.scm_service.get_subs_for_project(
                await self.scm_service.list_lu_webhook_subscriptions(
                    lu["collection"],
                ),
                lu["id"],
                self.scm_service.make_cx_endpoint_url(self.cxoneflow_url),
                ADOService.ADO_EVENT_TYPES,
            )
        ]

        if len(sub_ids) > 0:
            AdoRemover.log().info(f"Removing webhook subscriptions for {self.scm_service.get_lu_repr(lu)}")
            await gather(
                *[
                    self.scm_service.delete_subscription(lu["collection"], sub_id)
                    for sub_id in sub_ids
                ]
            )
        else:
            AdoRemover.log().info(f"No webhook subscriptions to remove for {self.scm_service.get_lu_repr(lu)}")
            

        return True
