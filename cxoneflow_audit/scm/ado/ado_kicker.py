
from cxoneflow_audit.scm.ado.ado_base import AdoBase
from cxoneflow_audit.core import Kicker
from typing import AsyncGenerator, Dict, Any, Union, Tuple
from cxoneflow_kickoff_api import AdoKickoffMsg
from asyncio import to_thread
import requests, urllib.parse
from jsonpath_ng import parse


class AdoKicker(Kicker, AdoBase):

  __repo_remote_url = parse("$.remoteUrl")
  __repo_ssh_url = parse("$.sshUrl")
  __repo_default_branch = parse("$.defaultBranch")
  __repo_name = parse("$.name")
  
  __ref_sha = parse("$.value[*].objectId")

  def __init__(self, *args, **kwargs):
    Kicker.__init__(self, *args, **kwargs)
    AdoBase.__init__(self)

  @property
  def _scm_name(self) -> str:
    return "ADO"

  def _get_lu_name(self, lu : Any) -> str:
    return self._render_lu_name(lu)

  def _get_lu_repr(self, lu : Any) -> str:
    return self._render_lu_repr(lu)

  async def _lu_iterator(self) -> AsyncGenerator[Dict, None]:
    async for x in self._lu_iterator_delegate(self.scm_base_url, self.targets, self.scm_pat, self.proxies, self.ignore_ssl_errors):
      yield x

  @property
  def scm_key(self) -> str:
    return "adoe"
  
  async def __kickoff_msg_factory(self, collection_name : str, project_name : str, lu_repr : str, repo : Dict) -> Tuple[Union[None, AdoKickoffMsg], Union[str, None]]:
      repo_name = None
      if len(AdoKicker.__repo_name.find(repo)) > 0:
        repo_name = AdoKicker.__repo_name.find(repo).pop().value
      else:
        self.log().warning(f"Skipping a repository with no name in LU {lu_repr}")
        return None, None

      clone_urls = []
      remote_url = None
      if len(AdoKicker.__repo_remote_url.find(repo)) > 0:
        remote_url = AdoKicker.__repo_remote_url.find(repo).pop().value
        clone_urls.append(remote_url)

      if len(AdoKicker.__repo_ssh_url.find(repo)) > 0:
        clone_urls.append(AdoKicker.__repo_ssh_url.find(repo).pop().value)

      if len(clone_urls) == 0:
        self.log().warning(f"Repository {repo_name} had no clone URLs in LU {lu_repr}")
        return None, remote_url

      default_branch = None
      if len(AdoKicker.__repo_default_branch.find(repo)) > 0:
        default_branch = AdoKicker.__repo_default_branch.find(repo).pop().value.replace("refs/heads/", "")
      else:
        self.log().warning(f"Repository {repo_name} has no default branch in LU {lu_repr}")
        return None, remote_url

      ref_params = {
        "filter" : "heads",
        "filterContains" : default_branch
      }

      ref_params.update(self._api_ver_url_params())
      ref_url = self._org_url(self.scm_base_url, collection_name) + f"/{urllib.parse.quote(project_name)}/_apis/git/repositories/" + \
        f"{urllib.parse.quote(repo_name)}/refs"
      ref_list = await to_thread(requests.request, "GET", ref_url, params=ref_params, headers=self._required_headers(self.scm_pat), 
                                 proxies=self.proxies, verify=not self.ignore_ssl_errors)

      if not ref_list.ok:
        self.log().warning(f"{ref_list.status_code} returned when attempting to retrieve the ref list for repo {repo_name} in LU {lu_repr}")
        return None, remote_url

      ref_list_json = ref_list.json()

      if int(ref_list_json['count']) == 0:
        self.log().warning(f"Repo {repo_name} had no commits in LU {lu_repr}")
        return None, remote_url

      default_branch_sha = None
      if len(AdoKicker.__ref_sha.find(ref_list_json)) > 0:
        default_branch_sha = AdoKicker.__ref_sha.find(ref_list_json).pop().value
      else:
        self.log().warning(f"Repository {repo_name} default branch {default_branch} had no head commit SHA in LU {lu_repr}")
        return None, remote_url

      return AdoKickoffMsg(
        clone_urls = clone_urls, 
        branch_name=default_branch, 
        collection_name=collection_name,
        project_name=project_name,
        repo_name=repo_name,
        sha=default_branch_sha
      ), remote_url

  async def _process_lu(self, lu : Any) -> bool:
    project_name = lu['name']
  
    repo_url = self._org_url(self.scm_base_url, lu['collection']) + f"/{urllib.parse.quote(project_name)}/_apis/git/repositories"

    repo_list = await to_thread(requests.request, "GET", repo_url, params=self._api_ver_url_params(), 
                                headers=self._required_headers(self.scm_pat), 
                                proxies=self.proxies, verify=not self.ignore_ssl_errors)

    if not repo_list.ok:
      self.log().error(f"{repo_list.status_code} returned attempting to obtain a list of repositories for LU {self._render_lu_repr(lu)}")
      return False

    repo_list_json = repo_list.json()
    repo_count = repo_list_json['count']
    self.log().info(f"{repo_count} repositories found for LU {self._render_lu_repr(lu)}")

    async def repo_iter():
      for repo in repo_list_json['value']:
        yield repo

    async for repo in repo_iter():
      try:
        msg, clone_url = await self.__kickoff_msg_factory(lu['collection'], project_name, self._render_lu_repr(lu), repo)
        if msg is None:
          continue
        else:
          await self._exec_kickoff(clone_url, msg)
      except BaseException as ex:
        self.log().exception(f"Exception trying to scan repo [{repo}]", ex)


    return True
