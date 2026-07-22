from typing import Any
from cxoneflow_audit.core import Remover
from .consts import ws_required_events


class BitBucketCloudRemover(Remover):
    def __init__(self, *args, **kwargs):
        Remover.__init__(self, *args, **kwargs)

    async def _process_lu(self, lu: Any) -> bool:
        self.log().debug(f"Processing: {self.scm_service.get_lu_repr(lu)}")

        endpoint_url = self.cxoneflow_url.rstrip("/") + "/bbc"

        async for hook in self.scm_service.call_paginated_api(
            api_path=f"/workspaces/{self.scm_service.get_lu_name(lu)}/hooks"
        ):
            url_match = hook.get("url", "").startswith(endpoint_url)

            if url_match:
                self.log().info(
                    f"Webhook configuration for {self.scm_service.get_lu_repr(lu)} was removed."
                )

                await self.scm_service._scm_api_call(
                    api_path=f"/workspaces/{self.scm_service.get_lu_name(lu)}/hooks/{hook.get('uuid')}",
                    method="DELETE",
                    auth=self.scm_service.auth,
                )
