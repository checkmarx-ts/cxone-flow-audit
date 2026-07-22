from typing import List
from cxoneflow_audit.scm.common import SCMTool
from .bbc_auditor import BitBucketCloudAuditor
from .bbc_deployer import BitBucketCloudDeployer
from .bbc_remover import BitBucketCloudRemover
from .bbc_kicker import BitBucketCloudKicker
from .bbc_service import BBCWorkspaceService
from requests.auth import HTTPBasicAuth


class BitBucketCloudTool(SCMTool):

    def __init__(self, **kwargs):
        super().__init__(
            audit=self.bbc_audit,
            deploy=self.bbc_deploy,
            remove=self.bbc_remove,
            kickoff=self.bbc_kickoff,
            **kwargs,
        )

    async def bbc_audit(self, args: List[str], help: bool = False):
        """Usage: cxoneflow-audit bbc audit [--no-config] [--outfile CSVFILE]
                          [--match-regex M_REGEX | --skip-regex S_REGEX]
                          (--api-token TOKEN | --api-token-env)
                          (--api-token-email EMAIL)
                          (--cx-url CX_URL)

        Deployment Options

        --cx-url CX_URL             The base URL for the CxOneFlow endpoint
                                    (e.g. https://cxoneflow.corp.com)

        Output Options

        --outfile CSVFILE          The path to a file where the audit CSV will be
                                   written. [default: ./cxoneflow.csv]

        --no-config                Only include workspaces or repositories that are not
                                   configured.

        Filtering Options

        --match-regex M_REGEX      Regular expression matching workspace slugs that should
                                   be configured to send events to CxOneFlow.

        --skip-regex S_REGEX       Regular expression matching workspace slugs that should
                                   not be configured to send events to CxOneFlow.

        SCM Options

        --api-token TOKEN          An API token with appropriate privileges.

        --api-token-env            Obtain the API token from the environment variable 'CX_APITOKEN'

        --api-token-email EMAIL    The Atlassian email address for the account for the API token

        """
        args = self._get_opts(self.bbc_audit.__doc__, ["bbc", "audit"] + args, help)

        return await BitBucketCloudAuditor(
            outfile=args["--outfile"],
            only_not_cfg=args["--no-config"],
            targets=None,
            concurrency=self.concurrency,
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=BBCWorkspaceService(
                HTTPBasicAuth(
                    args["--api-token-email"],
                    SCMTool.resolve_from_env(args["--api-token"], "CX_APITOKEN"),
                ),
                proxy=self.proxy,
                ssl_verify=not self.ssl_ignore,
            ),
            cxoneflow_url=args["--cx-url"],
        ).execute()

    async def bbc_deploy(self, args: List[str], help: bool = False):
        """Usage: cxoneflow-audit bbc deploy
                          [--match-regex M_REGEX | --skip-regex S_REGEX]
                          (--shared-secret SECRET | --shared-secret-env) [--replace]
                          (--api-token TOKEN | --api-token-env)
                          (--api-token-email EMAIL)
                          (--cx-url CX_URL)

        Deployment Options

        --cx-url CX_URL             The base URL for the CxOneFlow endpoint
                                    (e.g. https://cxoneflow.corp.com)

        --shared-secret SECRET     The shared secret configured in the service hook

        --shared-secret-env        Obtain the shared secret from the environment variable 'CX_SECRET'

        --replace                  If an existing webhook configuration is found, replace it.

        Filtering Options

        --match-regex M_REGEX      Regular expression matching workspace slugs that should
                                   be configured to send events to CxOneFlow.

        --skip-regex S_REGEX       Regular expression matching workspace slugs that should
                                   not be configured to send events to CxOneFlow.
        SCM Options

        --api-token TOKEN          An API token with appropriate privileges.

        --api-token-env            Obtain the API token from the environment variable 'CX_APITOKEN'

        --api-token-email EMAIL    The Atlassian email address for the account for the API token

        """
        args = self._get_opts(self.bbc_deploy.__doc__, ["bbc", "deploy"] + args, help)

        return await BitBucketCloudDeployer(
            concurrency=self.concurrency,
            targets=None,
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=BBCWorkspaceService(
                HTTPBasicAuth(
                    args["--api-token-email"],
                    SCMTool.resolve_from_env(args["--api-token"], "CX_APITOKEN"),
                ),
                proxy=self.proxy,
                ssl_verify=not self.ssl_ignore,
            ),
            cxoneflow_url=args["--cx-url"],
            shared_secret=SCMTool.resolve_from_env(
                args["--shared-secret"], "CX_SECRET"
            ),
            replace=args["--replace"],
        ).execute()

    async def bbc_remove(self, args: List[str], help: bool = False):
        """Usage: cxoneflow-audit bbc remove
                          [--match-regex M_REGEX | --skip-regex S_REGEX]
                          (--api-token TOKEN | --api-token-env)
                          (--api-token-email EMAIL)
                          (--cx-url CX_URL)

        Removal Options

        --cx-url CX_URL             The base URL for the CxOneFlow endpoint
                                    (e.g. https://cxoneflow.corp.com)

        Filtering Options

        --match-regex M_REGEX      Regular expression matching workspace slugs that should
                                    be configured to send events to CxOneFlow.

        --skip-regex S_REGEX       Regular expression matching workspace slugs that should
                                    not be configured to send events to CxOneFlow.
        SCM Options

        --api-token TOKEN          An API token with appropriate privileges.

        --api-token-env            Obtain the API token from the environment variable 'CX_APITOKEN'

        --api-token-email EMAIL    The Atlassian email address for the account for the API token

        """
        args = self._get_opts(self.bbc_remove.__doc__, ["bbc", "remove"] + args, help)

        return await BitBucketCloudRemover(
            concurrency=self.concurrency,
            targets=None,
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=BBCWorkspaceService(
                HTTPBasicAuth(
                    args["--api-token-email"],
                    SCMTool.resolve_from_env(args["--api-token"], "CX_APITOKEN"),
                ),
                proxy=self.proxy,
                ssl_verify=not self.ssl_ignore,
            ),
            cxoneflow_url=args["--cx-url"],
        ).execute()

    async def bbc_kickoff(self, args: List[str], help: bool = False):
        """Usage: cxoneflow-audit bbc kickoff [--match-regex M_REGEX | --skip-regex S_REGEX]
                          [--audit-file AUDIT_FILE]
                          (--api-token TOKEN | --api-token-env)
                          (--api-token-email EMAIL)
                          (--ssh-key-path SSHKEY) [--ssh-key-pass SSHPASS | --ssh-key-env]
                          (--cx-url CX_URL)

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

        --match-regex M_REGEX      Regular expression matching workspace names that
                                   should have repositories iterated for the first scan.

        --skip-regex S_REGEX       Regular expression matching workspace names that
                                   should not have repositories iterated for the first scan.

        SCM Options

        --api-token TOKEN          An API token with appropriate privileges.

        --api-token-env            Obtain the API token from the environment variable 'CX_APITOKEN'

        --api-token-email EMAIL    The Atlassian email address for the account for the API token

        """
        args = self._get_opts(self.bbc_kickoff.__doc__, ["bbc", "kickoff"] + args, help)

        return await BitBucketCloudKicker(
            concurrency=self.concurrency,
            targets=None,
            audit_file_path=args["--audit-file"],
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=BBCWorkspaceService(
                HTTPBasicAuth(
                    args["--api-token-email"],
                    SCMTool.resolve_from_env(args["--api-token"], "CX_APITOKEN"),
                ),
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
        """Usage: cxoneflow-audit bbc <command> [<args>...]

        <command> can be one of:
        audit       Execute an audit for CxOneFlow webhook deployment.

        deploy      Deploy CxOneFlow webhooks for the specified workspaces.

        remove      Remove CxOneFlow webhooks from the specified workspaces.

        kickoff     Iterate through repositories in the specified workspaces
                    and perform an initial scan on the production branch.

        Use "cxoneflow-audit help bbc <command>" for further help.
        """
        tool = [] if help else ["bbc"]
        return await self._dispatch(
            self.__call__.__doc__, "<command>", "<args>", tool + args, help
        )
