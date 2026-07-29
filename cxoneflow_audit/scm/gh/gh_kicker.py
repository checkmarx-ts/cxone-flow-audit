from typing import Any
from cxoneflow_audit.core import Kicker
from cxoneflow_audit.util import NotFoundException
from cxoneflow_kickoff_api import GithubKickoffMsg
from .gh_service import GHService


class GithubKicker(Kicker):
    def __init__(self, scm_api_service: GHService, *args, **kwargs):
        Kicker.__init__(self, scm_api_service=scm_api_service, *args, **kwargs)

    @property
    def scm_key(self) -> str:
        return "gh"

    async def _process_lu(self, lu: Any) -> bool:
        org_name = lu["login"]

        app_id = None
        install_id = None
        if self.scm_service.check_for_app:
            try:
                installed_app = await self.scm_service.get_org_installed_app(org_name)
                if installed_app is not None:
                    app_id = installed_app["app_id"]
                    install_id = installed_app["id"]
            except NotFoundException:
                self.log().warning(
                    "App information for organization %s not found. Scans will be attempted but may fail without the app install id.",
                    org_name,
                )

        async for repo in self.scm_service.repo_iterator(org_name):
            await self._exec_kickoff(
                repo["clone_url"],
                GithubKickoffMsg(
                    clone_urls=[repo["clone_url"], f"ssh://{repo['ssh_url']}"],
                    branch_name=repo["default_branch"],
                    sha=await self.scm_service.get_latest_repo_commit(
                        org_name, repo["name"], repo["default_branch"]
                    ),
                    repo_organization_name=org_name,
                    repo_name=repo["name"],
                    install_id=install_id,
                    app_id=app_id,
                ),
            )

        return True
