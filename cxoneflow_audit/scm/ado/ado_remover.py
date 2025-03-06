from cxoneflow_audit.core import Remover

class AdoRemover(Remover):
  @property
  def _scm_name(self) -> str:
    return "ADO"
