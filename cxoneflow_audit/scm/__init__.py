import cxoneflow_audit.scm.ado as ado
from dataclasses import dataclass
from cxoneflow_audit.core import Auditor, Deployer, Remover

@dataclass(frozen=True)
class ActionClasses:
  Auditor : Auditor
  Deployer : Deployer
  Remover : Remover

scm_map = {
  "ado" : ActionClasses(Auditor=ado.AdoAuditor, Deployer=ado.AdoDeployer, Remover=ado.AdoRemover)
}