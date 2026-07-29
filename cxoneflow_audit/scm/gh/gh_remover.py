from typing import Any
from cxoneflow_audit.core import Remover
from cxoneflow_audit.util import NotFoundException
from .gh_service import GHService


class GithubRemover(Remover):

    def __init__(self, scm_api_service: GHService, *args, **kwargs):
        Remover.__init__(self, scm_api_service=scm_api_service, *args, **kwargs)

    async def _process_lu(self, lu: Any) -> bool:
        org_name = lu["login"]

        noAction = True

        appRemoved = False if self.scm_service.check_for_app else True

        if self.scm_service.check_for_app:
            try:
                app = await self.scm_service.get_org_installed_app(org_name)
            except NotFoundException:
                self.log().warning(
                    "PAT permissions don't allow app configuration enumeration for organization %s.",
                    org_name,
                )
                app = None

            if app is not None:
                install_id = app["id"]
                if await self.scm_service.remove_app(install_id):
                    self.log().info(
                        "Github app with installation id %d removed from organization %s",
                        install_id,
                        org_name,
                    )
                    noAction = False
                    appRemoved = True
                else:
                    self.log().warning(
                        "Could not remove Github app with installation id %d from organization %s",
                        install_id,
                        org_name,
                    )

        hookRemoved = True
        try:
            async for hook in await self.scm_service.organization_hooks_iterator(
                org_name
            ):
                if self._eval_correct_webhook_url(hook["config"]["url"]):
                    if await self.scm_service.delete_webhook(org_name, hook["id"]):
                        self.log().info(
                            "Webhook configuration removed from organization %s",
                            org_name,
                        )
                        noAction = False
                    else:
                        self.log().warning(
                            "Could not remove webhook configuration from organization %s",
                            org_name,
                        )
                        hookRemoved = False
        except NotFoundException:
            self.log().warning(
                "PAT permissions don't allow webhook configuration enumeration for organization %s.",
                org_name,
            )

        if noAction:
            self.log().warning("No actions performed for organization %s", org_name)

        return appRemoved and hookRemoved
