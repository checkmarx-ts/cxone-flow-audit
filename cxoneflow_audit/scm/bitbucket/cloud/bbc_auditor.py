from typing import Dict, Any, List
import csv
from asyncio import Lock
from cxoneflow_audit.core.common import ConfigState
from cxoneflow_audit.core import Auditor
from .bbc_service import HookData, HookScope
from .consts import repo_required_events, ws_required_events


class BitBucketCloudAuditor(Auditor):

    def __init__(self, *args, **kwargs):
        Auditor.__init__(self, *args, **kwargs)
        self.__lock = Lock()
        self.__data = []

    async def __process_hook_scope(
        self,
        lu_repr: str,
        configScope: HookScope,
        hook_def: Dict,
        req_events: List[str],
        final_state: ConfigState,
    ) -> bool:
        ws_config = HookData(
            lu=lu_repr,
            configScope=configScope,
            configState=ConfigState.NOT_CONFIGURED,
            hookUrl=hook_def.get("url", ""),
        )

        configured = False
        endpoint = False

        if not ws_config.hookUrl.startswith(self.cxoneflow_url):
            return False

        if not hook_def.get("url", "").startswith(
            self.cxoneflow_url.rstrip("/") + "/bbc"
        ):
            ws_config.configState = ConfigState.MISCONFIG
            ws_config.issues.append("CxOneFlow endpoint should be /bbc")
        else:
            endpoint = True

        ws_config.active = hook_def.get("active", False)
        if not ws_config.active:
            ws_config.configState = ConfigState.MISCONFIG
            ws_config.issues.append("CxOneFlow webhook is configured but not active")

        ssl_verify = not hook_def.get("skip_cert_verification")
        if not ssl_verify:
            ws_config.configState = ConfigState.MISCONFIG
            ws_config.issues.append(
                "CxOneFlow SSL certificate validation is turned off"
            )

        ws_config.secretSet = hook_def.get("secret_set")
        if not ws_config.secretSet:
            ws_config.configState = ConfigState.MISCONFIG
            ws_config.issues.append("Webhook secret is not set")

        missing_events = [ev for ev in req_events if ev not in hook_def.get("events")]

        if len(missing_events) > 0:
            ws_config.configState = ConfigState.MISCONFIG
            ws_config.missingEvents = missing_events
            ws_config.issues.append(
                "Not all required events are being sent by the webhook"
            )

        if ws_config.configState == ConfigState.NOT_CONFIGURED:
            if (
                ws_config.active
                and endpoint
                and ssl_verify
                and ws_config.secretSet
                and len(ws_config.missingEvents) == 0
            ):
                ws_config.configState = final_state
                configured = True
            else:
                ws_config.configState = ConfigState.PARTIAL_CONFIG

        async with self.__lock:
            self.__data.append(ws_config)

        return configured

    async def _process_lu(self, lu: Any) -> bool:
        self.log().debug(f"Processing: {self.scm_service.get_lu_repr(lu)}")

        lu_workspace_hook_configured = False

        # Start at workspace scope
        async for ws in self.scm_service.call_paginated_api(
            api_path=f"/workspaces/{self.scm_service.get_lu_name(lu)}/hooks"
        ):

            if await self.__process_hook_scope(
                self.scm_service.get_lu_repr(lu),
                HookScope.WORKSPACE,
                ws,
                ws_required_events,
                ConfigState.CONFIGURED,
            ):
                lu_workspace_hook_configured = True

        # If no configured webhooks found in workspace, note it.
        if not lu_workspace_hook_configured:
            async with self.__lock:
                self.__data.append(
                    HookData(
                        lu=self.scm_service.get_lu_repr(lu),
                        configScope=HookScope.WORKSPACE,
                        configState=ConfigState.NOT_CONFIGURED,
                    )
                )

        # Now iterate the repositories in the workspace and look at their hooks.
        async for repo in self.scm_service.call_paginated_api(
            api_path=f"/repositories/{self.scm_service.get_lu_name(lu)}"
        ):
            repo_slug = repo.get("slug")
            repo_repr = f"{repo_slug}:{self.scm_service.get_lu_repr(lu)}"
            if repo_slug is not None:
                async for repo_hook in self.scm_service.call_paginated_api(
                    api_path=f"/repositories/{self.scm_service.get_lu_name(lu)}/{repo_slug}/hooks"
                ):
                    await self.__process_hook_scope(
                        repo_repr,
                        HookScope.REPO,
                        repo_hook,
                        repo_required_events,
                        (
                            ConfigState.CONFIGURED
                            if not lu_workspace_hook_configured
                            else ConfigState.MISCONFIG
                        ),
                    )

        return len(self.__data) > 0

    async def execute(self) -> int:

        result = await super().execute()

        with open(self.outfile, "wt", encoding="UTF-8") as csv_dest:
            writer = csv.writer(csv_dest, lineterminator="\n", quoting=csv.QUOTE_ALL)
            # pylint: disable=E1101
            sorted_fields = sorted(list(HookData.__dataclass_fields__.keys()))
            writer.writerow(sorted_fields)
            for row in self.__data:
                if not (
                    self.skip_configured and row.configState == ConfigState.CONFIGURED
                ):
                    writer.writerow([row.__dict__[x] for x in sorted_fields])

        return result
