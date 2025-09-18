from typing import Dict, AsyncGenerator, Any, List
from asyncio import Lock
import csv
from cxoneflow_audit.core.common import ConfigState
from cxoneflow_audit.scm.gh.gh_base import GithubBase, HookData
from cxoneflow_audit.core import Auditor
from cxoneflow_audit.util import ScmException

class GithubAuditor(Auditor, GithubBase):

  def __init__(self, app_slug : str, app_key_file : str, *args, **kwargs):
    Auditor.__init__(self, *args, **kwargs)
    GithubBase.__init__(self, self.cxone_flow_url, self.scm_base_url,
                        self.scm_pat, self.proxies, self.ignore_ssl_errors,
                        app_slug, app_key_file)
    self.__data = {}
    self.__lock = Lock()


  @property
  def _scm_name(self) -> str:
    return "GitHub"

  def _get_lu_name(self, lu : Any) -> str:
    return lu['login']

  def _get_lu_repr(self, lu : Any) -> str:
    return f"{lu['login']}:{lu['id']}:{lu['url']}"

  async def _lu_iterator(self) -> AsyncGenerator[Dict, None]:
    async for x in await self._organization_iterator():
      yield x

  @staticmethod
  def __eval_correct_permissions(perms : Dict[str, str]) -> bool:
    return "contents" in perms.keys() and perms["contents"] == "read" \
      and "pull_requests" in perms.keys() and perms["pull_requests"] == "write"


  @staticmethod
  def __eval_correct_events(events : List[str]) -> bool:
    return "pull_request" in events and "push" in events and "pull_request_review" in events

  def __eval_correct_webhook_url(self, url : str) -> bool:
    return url.startswith(self.webhook_url)

  async def _process_lu(self, lu : Any) -> bool:
    self.log().debug(f"Processing: {self._get_lu_repr(lu)}")

    hook_cfg = HookData(_orgName=lu['login'], _orgId=lu['id'], _orgUrl=lu['url'])
    current_state = ConfigState.NOT_CONFIGURED

    try:
      async for hook in await self._organization_hooks_iterator(lu['login']):
        if not hook['config']['url'].startswith(self.webhook_url):
          continue
        else:
          current_state = ConfigState.CONFIGURED

        hook_cfg.hasOrgWebhook = True
        hook_cfg.orgWebhookActive = hook['active']
        hook_cfg.orgWebhookCreatedAt = hook['created_at']
        hook_cfg.orgWebhookUpdatedAt = hook['updated_at']
        hook_cfg.orgWebhookConfigUrl = hook['url']
        hook_cfg.orgWebhookPushEvents = 'push' in hook['events']
        hook_cfg.orgWebhookPREvents = 'pull_request' in hook['events']
        if not hook_cfg.orgWebhookPushEvents or not hook_cfg.orgWebhookPREvents:
          current_state = ConfigState.PARTIAL_CONFIG

      # State should be NOT_CONFIGURED when an app is found. If app and webhooks
      # are found, state is MISCONFIG
      app = await self._get_org_installed_app(lu['login'])

      if app is not None:
        if current_state != ConfigState.NOT_CONFIGURED:
          current_state = ConfigState.MISCONFIG

        hook_cfg.githubAppCorrectWebhookUrl = self.__eval_correct_webhook_url(await self._get_app_webhook_endpoint())

        hook_cfg.githubAppSuspendedAt = app['suspended_at']
        hook_cfg.githubAppSuspendedBy = app['suspended_by']
        hook_cfg.githubAppSuspended = hook_cfg.githubAppSuspendedAt is not None and hook_cfg.githubAppSuspendedBy is not None
        if hook_cfg.githubAppSuspended:
          current_state = ConfigState.MISCONFIG
        elif current_state == ConfigState.NOT_CONFIGURED:
          current_state = ConfigState.CONFIGURED

        hook_cfg.hasGithubApp = True
        hook_cfg.pendingGithubAppApproval = False
        hook_cfg.githhubAppCreatedAt = app['created_at']
        hook_cfg.githubAppUpdatedAt = app['updated_at']
        hook_cfg.githubAppId = str(app['app_id'])
        hook_cfg.githubInstallId = str(app['id'])
        hook_cfg.githubAppSlug = app['app_slug']
        hook_cfg.githubAppInstallUrl = app['html_url']
        hook_cfg.githubAppAllRepos = app['repository_selection'] == "all"
        if not hook_cfg.githubAppAllRepos and current_state != ConfigState.MISCONFIG:
          current_state = ConfigState.PARTIAL_CONFIG

        hook_cfg.githubAppCorrectPermissions = GithubAuditor.__eval_correct_permissions(app['permissions'])
        if not hook_cfg.githubAppCorrectPermissions and current_state != ConfigState.MISCONFIG:
          current_state = ConfigState.PARTIAL_CONFIG

        hook_cfg.githubAppCorrectEvents = GithubAuditor.__eval_correct_events(app['events'])
        if not hook_cfg.githubAppCorrectEvents and current_state != ConfigState.MISCONFIG:
          current_state = ConfigState.PARTIAL_CONFIG
      else:
        pending_data = await self._get_app_pending_install(lu['login'])
        hook_cfg.pendingGithubAppApproval = pending_data is not None

        if hook_cfg.pendingGithubAppApproval and current_state == ConfigState.NOT_CONFIGURED:
          current_state = ConfigState.PARTIAL_CONFIG
        elif not hook_cfg.pendingGithubAppApproval and current_state == ConfigState.NOT_CONFIGURED:
          current_state = ConfigState.UNKNOWN

        if hook_cfg.pendingGithubAppApproval:
          hook_cfg.hasGithubApp = False
          hook_cfg.pendingRequestDate = pending_data.requestDate
          hook_cfg.pendingRequester = pending_data.requester

      if not hook_cfg.pendingGithubAppApproval and not hook_cfg.hasGithubApp and not hook_cfg.hasOrgWebhook:
        self.log().warning("The configuration for organization %s can't be determined. This may be due to PAT permissions.", lu['login'])

      async with self.__lock:
        if current_state in self.__data.keys():
          self.__data[current_state].append(hook_cfg)
        else:
          self.__data[current_state] = [hook_cfg]

    except ScmException as ex:
      current_state = ConfigState.UNKNOWN
      self.log().error(ex)


  async def execute(self) -> int:

    result = await super().execute()

    with open(self.outfile, "wt", encoding="UTF-8") as csv_dest:
      writer = csv.writer(csv_dest, lineterminator="\n", quoting=csv.QUOTE_ALL)
      # pylint: disable=E1101
      sorted_fields = sorted(list(HookData.__dataclass_fields__.keys()))
      headers = ["state"] + sorted_fields
      writer.writerow(headers)
      for state in self.__data.keys():
        if not (self.skip_configured and state == ConfigState.CONFIGURED):
          for row in self.__data[state]:
            writer.writerow([state] + [row.__dict__[x] for x in sorted_fields])

    return result
