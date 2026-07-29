from typing import Any, List, Dict
from cxoneflow_audit.core import Kicker
from cxoneflow_kickoff_api import BitbucketCloudKickoffMsg


class BitBucketCloudKicker(Kicker):

    def __init__(self, *args, **kwargs):
        Kicker.__init__(self, *args, **kwargs)

    @property
    def scm_key(self) -> str:
        return "bbc"

    def __make_clone_urls_from_links(self, links: List[Dict]) -> List[str]:
        ret = []
        for link in links:
            scheme = link.get("name")
            href = link.get("href")

            if href.startswith(scheme):
                ret.append(href)
            else:
                ret.append(f"{scheme}://{href}")

        return ret

    async def __get_latest_commit_sha(
        self, workspace: str, repo_slug: str, branch: str
    ) -> str:
        async for commit in self.scm_service.call_paginated_api(
            api_path=f"/repositories/{workspace}/{repo_slug}/commits",
            query_args={"include": branch, "pagelen": "1"},
        ):
            return commit.get("hash")

    async def _process_lu(self, lu: Any) -> bool:
        async for repo in self.scm_service.call_paginated_api(
            api_path=f"/repositories/{self.scm_service.get_lu_name(lu)}"
        ):
            clone_url_links = repo.get("links", {}).get("clone", {})
            mainbranch = repo.get("mainbranch", {}).get("name")

            for clone_link_entry in clone_url_links:
                if clone_link_entry.get("name", "") == "https":
                    await self._exec_kickoff(
                        clone_link_entry.get("href"),
                        BitbucketCloudKickoffMsg(
                            self.__make_clone_urls_from_links(clone_url_links),
                            mainbranch,
                            await self.__get_latest_commit_sha(
                                self.scm_service.get_lu_name(lu),
                                repo.get("slug"),
                                mainbranch,
                            ),
                            repo.get("slug"),
                            repo.get("project", {}).get("key"),
                            repo.get("project", {}).get("name"),
                            self.scm_service.get_lu_name(lu),
                        ),
                    )
            pass
        return True
