from typing import List
from cxoneflow_audit.scm.common import SCMTool
from cxoneflow_audit.scm.gh.gh_auditor import GithubAuditor
from cxoneflow_audit.scm.gh.gh_deployer import GithubDeployer
from cxoneflow_audit.scm.gh.gh_remover import GithubRemover
from cxoneflow_audit.scm.gh.gh_kicker import GithubKicker
from cxoneflow_audit.scm.gh.gh_service import GHService
from cxoneflow_audit.scm import HTTPBearerAuth


class GithubTool(SCMTool):

    def __init__(self, **kwargs):
        super().__init__(
            audit=self.gh_audit,
            deploy=self.gh_deploy,
            remove=self.gh_remove,
            kickoff=self.gh_kickoff,
            **kwargs,
        )

    async def gh_audit(self, args: List[str], help: bool = False):
        """Usage: cxoneflow-audit gh audit [--no-config] [--outfile CSVFILE]
                          [--match-regex M_REGEX | --skip-regex S_REGEX]
                          [--app-slug SLUG]
                          [--app-key KEYFILE]
                          (--pat PAT | --pat-env) (--scm-api-url URL)
                          (--cx-url CX_URL)

        Deployment Options

        --cx-url CX_URL             The base URL for the CxOneFlow endpoint
                                    (e.g. https://cxoneflow.corp.com)

        Output Options

        --outfile CSVFILE          The path to a file where the audit CSV will be
                                   written. [default: ./cxoneflow.csv]

        --no-config                Only include projects that are not configured.

        Filtering Options

        --match-regex M_REGEX      Regular expression matching organization names that
                                   should be configured to send events to CxOneFlow.

        --skip-regex S_REGEX       Regular expression matching organization names that
                                   should not be configured to send events to CxOneFlow.

        SCM Options

        --pat PAT                  An SCM PAT with appropriate privileges.

        --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

        --scm-api-url URL          The URL to the SCM's API endpoint
                                   (e.g. https://api.github.com, https://github.corp.com/api/v3/)

        Github App Options

        --app-slug SLUG             The Github app slug for the CxOneFlow app.

        --app-key KEYFILE           The path to the app private key file.
        """
        args = self._get_opts(self.gh_audit.__doc__, ["gh", "audit"] + args, help)

        return await GithubAuditor(
            outfile=args["--outfile"],
            only_not_cfg=args["--no-config"],
            targets=None,
            concurrency=self.concurrency,
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=GHService(
                api_base_url=args["--scm-api-url"],
                app_slug=args["--app-slug"],
                app_key_file=args["--app-key"],
                auth=HTTPBearerAuth(SCMTool.resolve_from_env(args["--pat"], "CX_PAT")),
                proxy=self.proxy,
                ssl_verify=not self.ssl_ignore,
            ),
            cxoneflow_url=args["--cx-url"],
        ).execute()

    async def gh_deploy(self, args: List[str], help: bool = False):
        """Usage: cxoneflow-audit gh deploy
                          [--app-slug SLUG]
                          [--match-regex M_REGEX | --skip-regex S_REGEX]
                          (--shared-secret SECRET | --shared-secret-env) [--replace]
                          (--pat PAT | --pat-env) (--scm-api-url URL)
                          (--cx-url CX_URL)

        Deployment Options

        --cx-url CX_URL             The base URL for the CxOneFlow endpoint
                                    (e.g. https://cxoneflow.corp.com)

        --shared-secret SECRET     The shared secret configured in the service hook

        --shared-secret-env        Obtain the shared secret from the environment variable 'CX_SECRET'

        --replace                  If an existing webhook configuration is found, replace it.

        Filtering Options

        --match-regex M_REGEX      Regular expression matching organization names that
                                   should be configured to send events to CxOneFlow.

        --skip-regex S_REGEX       Regular expression matching organization names that
                                   should not be configured to send events to CxOneFlow.
        SCM Options

        --pat PAT                  An SCM PAT with appropriate privileges.

        --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

        --scm-api-url URL          The URL to the SCM's API endpoint
                                   (e.g. https://api.github.com, https://github.corp.com/api/v3/)

        Github App Options

        --app-slug SLUG            Skip webhook deployment if a Github app with this slug is installed
                                   in the organization.
        """
        args = self._get_opts(self.gh_deploy.__doc__, ["gh", "deploy"] + args, help)

        return await GithubDeployer(
            concurrency=self.concurrency,
            targets=None,
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=GHService(
                api_base_url=args["--scm-api-url"],
                app_slug=args["--app-slug"],
                auth=HTTPBearerAuth(SCMTool.resolve_from_env(args["--pat"], "CX_PAT")),
                proxy=self.proxy,
                ssl_verify=not self.ssl_ignore,
            ),
            cxoneflow_url=args["--cx-url"],
            shared_secret=SCMTool.resolve_from_env(
                args["--shared-secret"], "CX_SECRET"
            ),
            replace=args["--replace"],
        ).execute()

    async def gh_remove(self, args: List[str], help: bool = False):
        """Usage: cxoneflow-audit gh remove
                          [(--app-slug SLUG) (--app-key KEYFILE)]
                          [--match-regex M_REGEX | --skip-regex S_REGEX]
                          (--pat PAT | --pat-env) (--scm-api-url URL)
                          (--cx-url CX_URL)

        Removal Options

        --cx-url CX_URL             The base URL for the CxOneFlow endpoint
                                    (e.g. https://cxoneflow.corp.com)

        Filtering Options

        --match-regex M_REGEX      Regular expression matching organization names that
                                   should have configurations removed.

        --skip-regex S_REGEX       Regular expression matching organization names that
                                   should not have configurations removed.
        SCM Options

        --pat PAT                  An SCM PAT with appropriate privileges.

        --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

        --scm-api-url URL          The URL to the SCM's API endpoint
                                   (e.g. https://api.github.com, https://github.corp.com/api/v3/)

        Github App Options

        --app-slug SLUG            Remove the Github app with this slug from the organization.

        --app-key KEYFILE          The path to the Github app private key file.
        """
        args = self._get_opts(self.gh_remove.__doc__, ["gh", "remove"] + args, help)

        return await GithubRemover(
            concurrency=self.concurrency,
            targets=None,
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=GHService(
                api_base_url=args["--scm-api-url"],
                app_slug=args["--app-slug"],
                app_key_file=args["--app-key"],
                auth=HTTPBearerAuth(SCMTool.resolve_from_env(args["--pat"], "CX_PAT")),
                proxy=self.proxy,
                ssl_verify=not self.ssl_ignore,
            ),
            cxoneflow_url=args["--cx-url"],
        ).execute()

    async def gh_kickoff(self, args: List[str], help: bool = False):
        """Usage: cxoneflow-audit gh kickoff [--match-regex M_REGEX | --skip-regex S_REGEX]
                          (--pat PAT | --pat-env) (--scm-api-url URL) [--audit-file AUDIT_FILE]
                          (--ssh-key-path SSHKEY) [--ssh-key-pass SSHPASS | --ssh-key-env]
                          [--app-slug SLUG] (--cx-url CX_URL)

        Deployment Options

        --cx-url CX_URL             The base URL for the CxOneFlow endpoint
                                    (e.g. https://cxoneflow.corp.com)

        --audit-file AUDIT_FILE     A path to a file where audit data about the
                                    started scans is written. Data is appended
                                    to the file if it exists. [Default: kickoff_audit.csv]

        --ssh-key-path SSHKEY       The path to a file containing a PEM encoded
                                    SSH private key for authenticating with the
                                    CxOneFlow kickoff API

        --ssh-key-pass SSHPASS      The password to the SSH private key if it is
                                    password protected.

        --ssh-key-env               Indicates that the SSH key password should be
                                    obtained from the environment variable CX_SSHPASS.

        Filtering Options

        --match-regex M_REGEX      Regular expression matching organization names that
                                   should have repositories iterated for the first scan.

        --skip-regex S_REGEX       Regular expression matching organization names that
                                   should not have repositories iterated for the first scan.

        SCM Options

        --pat PAT                  An SCM PAT with appropriate privileges.

        --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

        --scm-api-url URL          The URL to the SCM's API endpoint
                                   (e.g. https://api.github.com, https://github.corp.com/api/v3/)

        Github App Options

        --app-slug SLUG            The slug for the Github app that is used for cloning repositories
                                   when CxOneFlow handles events generated by the app.
        """
        args = self._get_opts(self.gh_kickoff.__doc__, ["gh", "kickoff"] + args, help)

        return await GithubKicker(
            concurrency=self.concurrency,
            targets=None,
            audit_file_path=args["--audit-file"],
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=GHService(
                api_base_url=args["--scm-api-url"],
                app_slug=args["--app-slug"],
                auth=HTTPBearerAuth(SCMTool.resolve_from_env(args["--pat"], "CX_PAT")),
                proxy=self.proxy,
                ssl_verify=not self.ssl_ignore,
            ),
            ssh_private_key_path=args["--ssh-key-path"],
            ssh_private_key_password=SCMTool.resolve_from_env(
                args["--ssh-key-pass"], "CX_SSHPASS"
            ),
            cxoneflow_url=args["--cx-url"],
        ).execute()

    async def __call__(self, args: List[str], help: bool = False):
        """Usage: cxoneflow-audit gh <command> [<args>...]

        <command> can be one of:
        audit       Execute an audit for CxOneFlow webhook or Github app deployment.

        deploy      Deploy CxOneFlow webhooks on the projects in the specified organizations.

        remove      Remove CxOneFlow webhooks on the projects in the specified organizations.

        kickoff     Iterate through repositories in the specified orginizations
                    and perform an initial scan on the default branch.

        Use "cxoneflow-audit help gh <command>" for further help.
        """
        tool = [] if help else ["gh"]
        return await self._dispatch(
            self.__call__.__doc__, "<command>", "<args>", tool + args, help
        )
