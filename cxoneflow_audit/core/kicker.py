from .common import Operation
from cxoneflow_audit.__version__ import PROGNAME
from cxoneflow_kickoff_api import KickoffClient, KickoffMsg


class Kicker(Operation):
  def __init__(self, ssh_private_key_path : str, ssh_private_key_password : str, *args, **kwargs):
    super().__init__(*args, **kwargs)

    with open(ssh_private_key_path, "rt") as key:
      key_bytes = key.read()

    self.__ko_client = KickoffClient(key_bytes, ssh_private_key_password, self.cxone_flow_url, PROGNAME, self.proxies, not self.ignore_ssl_errors)
  
  @property
  def kickoff_client(self) -> KickoffClient:
    return self.__ko_client
  
  @property
  def scm_key(self) -> str:
    raise NotImplementedError("scm_key")

  async def _exec_kickoff(self, msg : KickoffMsg) -> None:
    response = await self.__ko_client.kickoff_scan(msg)
    pass

