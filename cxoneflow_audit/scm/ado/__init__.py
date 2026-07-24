from typing import List, Dict
from docopt import docopt
from cxoneflow_audit.scm.ado.ado_auditor import AdoAuditor
from cxoneflow_audit.scm.ado.ado_deployer import AdoDeployer
from cxoneflow_audit.scm.ado.ado_remover import AdoRemover
from cxoneflow_audit.scm.ado.ado_kicker import AdoKicker
from cxoneflow_audit.scm.ado.ado_service import (
    ADOBasicAuthService,
    ADOSPAuthService,
    ADOService,
)
from cxoneflow_audit.scm.common import SCMTool
from cxoneflow_audit.scm import HTTPTokenBasicAuth, HTTPBearerAuth


class AdoTool(SCMTool):

    def __init__(self, **kwargs):
        super().__init__(
            audit=self.ado_audit,
            deploy=self.ado_deploy,
            remove=self.ado_remove,
            kickoff=self.ado_kickoff,
            **kwargs,
        )

    def __service_factory(self, args: Dict[str, str]) -> ADOService:
        pat = args["--pat"] is not None or args["--pat-env"]
        sp = (
            args["--sp-tenant-id"] is not None
            or args["--sp-client-id"] is not None
            or args["--sp-client-secret"] is not None
            or args["--sp-client-secret-env"]
        )

        if pat and sp:
            AdoTool.log().error("Use either Service Principal or PAT, not both.")
            raise Exception("Bad ADO credential configuration.")
        elif not (pat or sp):
            AdoTool.log().error("No SCM credentials provided.")
            raise Exception("Bad ADO credential configuration.")
        elif pat:
            return ADOBasicAuthService(
                auth=HTTPTokenBasicAuth(
                    SCMTool.resolve_from_env(args.get("--pat"), "CX_PAT")
                ),
                proxy=self.proxy,
                ssl_verify=not self.ssl_ignore,
                api_base_url=args["--scm-url"],
                targets=args["TARGETS"],
            )
        elif sp:
            return ADOSPAuthService(
                args["--sp-tenant-id"],
                args["--sp-client-id"],
                SCMTool.resolve_from_env(
                    args.get("--sp-client-secret"), "CX_SP_SECRET"
                ),
                proxy=self.proxy,
                ssl_verify=not self.ssl_ignore,
                api_base_url=args["--scm-url"],
                targets=args["TARGETS"],
            )

    async def ado_audit(self, ado_args: List[str], help: bool = False):
        """Usage: cxoneflow-audit adoe audit [--no-config] [--outfile CSVFILE]
                          [--match-regex M_REGEX | --skip-regex S_REGEX]
                          (
                            (--pat PAT | --pat-env) |
                            (--sp-tenant-id TID)
                            (--sp-client-id CID)
                            (--sp-client-secret SECRET | --sp-client-secret-env)
                          )
                          (--scm-url URL)
                          (--cx-url CX_URL) TARGETS...

        TARGETS...                  One or more collection names where containing projects
                                    where service hook configurations will be audited.

        Deployment Options

        --cx-url CX_URL             The base URL for the CxOneFlow endpoint
                                    (e.g. https://cxoneflow.corp.com)


        Output Options

        --outfile CSVFILE          The path to a file where the audit CSV will be
                                   written. [default: ./cxoneflow.csv]

        --no-config                Only include projects that are not configured
                                   or are partially configured.

        Filtering Options

        --match-regex M_REGEX      Regular expression that matches ADO projects that
                                   should be configured to send events to CxOneFlow.

        --skip-regex S_REGEX       Regular expression that matches ADO projects that
                                   should not be configured to send events to CxOneFlow.

        SCM Options (General)

        --scm-url URL              The URL to the SCM instance (e.g. https://dev.azure.com)

        SCM Options (PAT)

        --pat PAT                  An SCM PAT with appropriate privileges.

        --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

        SCM Options (Service Principal)

        --sp-tenant-id TID          The Entra tenant ID where the Service Principal
                                    was created.

        --sp-client-id CID          The Service Principal client id.

        --sp-client-secret SECRET   The Service Principal client secret.

        --sp-client-secret-env      Obtain the value of the Service Principal client
                                    secret from the environment variable 'CX_SP_SECRET'
        """
        args = self._get_opts(
            self.ado_audit.__doc__, ["adoe", "audit"] + ado_args, help
        )

        return await AdoAuditor(
            outfile=args["--outfile"],
            only_not_cfg=args["--no-config"],
            concurrency=self.concurrency,
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=self.__service_factory(args),
            cxoneflow_url=args["--cx-url"],
        ).execute()

    async def ado_deploy(self, ado_args: List[str], help: bool = False):
        """Usage: cxoneflow-audit adoe deploy [--match-regex M_REGEX | --skip-regex S_REGEX]
                          (--shared-secret SECRET | --shared-secret-env) [--replace]
                          (
                            (--pat PAT | --pat-env) |
                            (--sp-tenant-id TID)
                            (--sp-client-id CID)
                            (--sp-client-secret SECRET | --sp-client-secret-env)
                          )
                          (--scm-url URL)
                          (--cx-url CX_URL) TARGETS...

        TARGETS...                  One or more collection names where service hook
                                    configurations will be created on each project.

        Deployment Options

        --cx-url CX_URL             The base URL for the CxOneFlow endpoint
                                    (e.g. https://cxoneflow.corp.com)

        --shared-secret SECRET     The shared secret configured in the service hook

        --shared-secret-env        Obtain the shared secret from the environment variable 'CX_SECRET'

        --replace                  If an existing webhook subscription is found, replace it.

        Filtering Options

        --match-regex M_REGEX      Regular expression that matches ADO projects that
                                   should be configured to send events to CxOneFlow.

        --skip-regex S_REGEX       Regular expression that matches ADO projects that
                                   should not be configured to send events to CxOneFlow.

        SCM Options (General)

        --scm-url URL              The URL to the SCM instance (e.g. https://dev.azure.com)

        SCM Options (PAT)

        --pat PAT                  An SCM PAT with appropriate privileges.

        --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

        SCM Options (Service Principal)

        --sp-tenant-id TID          The Entra tenant ID where the Service Principal
                                    was created.

        --sp-client-id CID          The Service Principal client id.

        --sp-client-secret SECRET   The Service Principal client secret.

        --sp-client-secret-env      Obtain the value of the Service Principal client
                                    secret from the environment variable 'CX_SP_SECRET'
        """
        args = self._get_opts(
            self.ado_deploy.__doc__, ["adoe", "deploy"] + ado_args, help
        )

        return await AdoDeployer(
            shared_secret=SCMTool.resolve_from_env(
                args["--shared-secret"], "CX_SECRET"
            ),
            replace=args["--replace"],
            concurrency=self.concurrency,
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=self.__service_factory(args),
            cxoneflow_url=args["--cx-url"],
        ).execute()

    async def ado_remove(self, ado_args: List[str], help: bool = False):
        """Usage: cxoneflow-audit adoe remove [--match-regex M_REGEX | --skip-regex S_REGEX]
                          (
                            (--pat PAT | --pat-env) |
                            (--sp-tenant-id TID)
                            (--sp-client-id CID)
                            (--sp-client-secret SECRET | --sp-client-secret-env)
                          )
                          (--scm-url URL)
                          (--cx-url CX_URL) TARGETS...

        TARGETS...                  One or more collection names where service hook
                                    configurations will be removed from each project.

        Deployment Options

        --cx-url CX_URL             The base URL for the CxOneFlow endpoint
                                    (e.g. https://cxoneflow.corp.com)

        Filtering Options

        --match-regex M_REGEX      Regular expression that matches ADO projects that
                                   should be configured to send events to CxOneFlow.

        --skip-regex S_REGEX       Regular expression that matches ADO projects that
                                   should not be configured to send events to CxOneFlow.
        SCM Options (General)

        --scm-url URL              The URL to the SCM instance (e.g. https://dev.azure.com)

        SCM Options (PAT)

        --pat PAT                  An SCM PAT with appropriate privileges.

        --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

        SCM Options (Service Principal)

        --sp-tenant-id TID          The Entra tenant ID where the Service Principal
                                    was created.

        --sp-client-id CID          The Service Principal client id.

        --sp-client-secret SECRET   The Service Principal client secret.

        --sp-client-secret-env      Obtain the value of the Service Principal client
                                    secret from the environment variable 'CX_SP_SECRET'
        """
        args = self._get_opts(
            self.ado_remove.__doc__, ["adoe", "remove"] + ado_args, help
        )

        return await AdoRemover(
            concurrency=self.concurrency,
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=self.__service_factory(args),
            cxoneflow_url=args["--cx-url"],
        ).execute()

    async def ado_kickoff(self, ado_args: List[str], help: bool = False):
        """Usage: cxoneflow-audit adoe kickoff [--match-regex M_REGEX | --skip-regex S_REGEX]
                          (
                            (--pat PAT | --pat-env) |
                            (--sp-tenant-id TID)
                            (--sp-client-id CID)
                            (--sp-client-secret SECRET | --sp-client-secret-env)
                          )
                          (--scm-url URL) [--audit-file AUDIT_FILE]
                          (--ssh-key-path SSHKEY) [--ssh-key-pass SSHPASS | --ssh-key-env]
                          (--cx-url CX_URL) TARGETS...

        TARGETS...                  One or more collection names containing projects
                                    for which all repositories will be scanned.

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

        --match-regex M_REGEX      Regular expression that matches ADO projects that
                                   should be configured to send events to CxOneFlow.

        --skip-regex S_REGEX       Regular expression that matches ADO projects that
                                   should not be configured to send events to CxOneFlow.

        SCM Options (General)

        --scm-url URL              The URL to the SCM instance (e.g. https://dev.azure.com)

        SCM Options (PAT)

        --pat PAT                  An SCM PAT with appropriate privileges.

        --pat-env                  Obtain the PAT from the environment variable 'CX_PAT'

        SCM Options (Service Principal)

        --sp-tenant-id TID          The Entra tenant ID where the Service Principal
                                    was created.

        --sp-client-id CID          The Service Principal client id.

        --sp-client-secret SECRET   The Service Principal client secret.

        --sp-client-secret-env      Obtain the value of the Service Principal client
                                    secret from the environment variable 'CX_SP_SECRET'
        """
        args = self._get_opts(
            self.ado_kickoff.__doc__, ["adoe", "kickoff"] + ado_args, help
        )

        return await AdoKicker(
            concurrency=self.concurrency,
            audit_file_path=args["--audit-file"],
            match=self._matcher_factory(args["--skip-regex"], args["--match-regex"]),
            scm_api_service=self.__service_factory(args),
            ssh_private_key_path=args["--ssh-key-path"],
            ssh_private_key_password=SCMTool.resolve_from_env(
                args["--ssh-key-pass"], "CX_SSHPASS"
            ),
            cxoneflow_url=args["--cx-url"],
        ).execute()

    async def __call__(self, ado_args: List[str], help: bool = False):
        """Usage: cxoneflow-audit adoe <command> [<args>...]

        <command> can be one of:
        audit       Execute an audit for CxOneFlow webhook deployment.

        deploy      Deploy CxOneFlow webhooks on the projects in the specified collections.

        remove      Remove CxOneFlow webhooks on the projects in the specified collections.

        kickoff     Iterate through project repositories in the specified collection
                    and perform an initial scan on the default branch.

        Use "cxoneflow-audit help adoe <command>" for further help.
        """
        tool = [] if help else ["adoe"]
        return await self._dispatch(
            self.__call__.__doc__, "<command>", "<args>", tool + ado_args, help
        )
