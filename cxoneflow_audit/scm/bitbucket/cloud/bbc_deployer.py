from typing import Any
from cxoneflow_audit.core import Deployer
from .consts import ws_required_events


class BitBucketCloudDeployer(Deployer):
    def __init__(self, *args, **kwargs):
        Deployer.__init__(self, *args, **kwargs)

    async def _process_lu(self, lu: Any) -> bool:
        self.log().debug(f"Processing: {self.scm_service.get_lu_repr(lu)}")

        add_config = True

        endpoint_url = self.cxoneflow_url.rstrip("/") + "/bbc"

        async for hook in self.scm_service.call_paginated_api(
            api_path=f"/workspaces/{self.scm_service.get_lu_name(lu)}/hooks"
        ):
            url_match = hook.get("url", "").startswith(endpoint_url)

            if url_match and not self.replace:
                self.log().info(
                    f"Webhook configuration for {self.scm_service.get_lu_repr(lu)} was not modified."
                )
                add_config = False
                break
            elif url_match and self.replace:
                await self.scm_service._scm_api_call(
                    api_path=f"/workspaces/{self.scm_service.get_lu_name(lu)}/hooks/{hook.get('uuid')}",
                    method="DELETE",
                    auth=self.scm_service.auth,
                )

        if add_config:
            hook_def = {
                "description": "CxOneFlow",
                "url": endpoint_url,
                "active": True,
                "secret": self.shared_secret,
                "events": ws_required_events,
            }

            await self.scm_service._scm_api_call(
                api_path=f"/workspaces/{self.scm_service.get_lu_name(lu)}/hooks",
                method="POST",
                json_body=hook_def,
                auth=self.scm_service.auth,
            )

            self.log().info(
                f"Webhook configuration for {self.scm_service.get_lu_repr(lu)} was installed."
            )
