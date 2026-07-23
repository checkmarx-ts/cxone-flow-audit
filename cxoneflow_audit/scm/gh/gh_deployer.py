from typing import Any, AsyncGenerator, Dict
from cxoneflow_audit.core import Deployer
from cxoneflow_audit.util import NotFoundException
from .gh_service import GHService


class GithubDeployer(Deployer):

    def __init__(self, scm_api_service: GHService, *args, **kwargs):
        Deployer.__init__(self, scm_api_service=scm_api_service, *args, **kwargs)

    async def _process_lu(self, lu: Any) -> bool:
        org_name = lu["login"]

        if self.scm_service.check_for_app:

            try:
                if await self.scm_service.get_org_installed_app(org_name) is not None:
                    self.log().warning(
                        "The Github app is installed in organization %s, skipping webhook deployment.",
                        org_name,
                    )
                    return False
            except NotFoundException:
                self.log().warning(
                    "PAT permissions don't allow app configuration enumeration for organization %s.",
                    org_name,
                )

        existing_def = None
        try:
            async for hook in await self.scm_service.organization_hooks_iterator(
                org_name
            ):
                if self._eval_correct_webhook_url(hook["config"]["url"]):
                    existing_def = hook
                    break
        except NotFoundException:
            self.log().warning(
                "PAT permissions don't allow webhook configuration enumeration for organization %s.",
                org_name,
            )
            return False

        if existing_def is not None and not self.replace:
            self.log().warning(
                "Existing webhook configuration found in organization %s, no changes made.",
                org_name,
            )
            return False
        elif existing_def is not None and self.replace:
            if not await self.scm_service.replace_webhook(
                org_name, self.shared_secret, existing_def["id"], self.cxoneflow_url
            ):
                self.log().error(
                    "Unable to replace webhook definition %d for organization %s.",
                    existing_def["id"],
                    org_name,
                )
                return False
            else:
                self.log().info(
                    "Webhooks definiton %d replaced in organization %s.",
                    existing_def["id"],
                    org_name,
                )
                return True
        elif existing_def is None:
            if not await self.scm_service.create_webhook(
                org_name, self.shared_secret, self.cxoneflow_url
            ):
                self.log().error(
                    "Unable to deploy webhook for organization %s.", org_name
                )
                return False
            else:
                self.log().info("Webhooks deployed in organization %s.", org_name)
                return True
