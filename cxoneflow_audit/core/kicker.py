from .common import Operation
from cxoneflow_audit.__version__ import PROGNAME
from cxoneflow_kickoff_api import KickoffClient, KickoffMsg, KickoffClientException, KickoffStatusCodes, KickoffResponseMsg
from typing import Union
import asyncio, os


class Kicker(Operation):
  def __init__(self, ssh_private_key_path : str, ssh_private_key_password : str, audit_file_path : str, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__lock = asyncio.Lock()
    self.__file_lock = asyncio.Lock()
    self.__audit_file_path = audit_file_path

    if not os.path.exists(audit_file_path):
      with open(audit_file_path, "wt") as f:
        f.write("\"Repository\",\"Status\",\"Scan Id\"\n")

    with open(ssh_private_key_path, "rt") as key:
      key_bytes = key.read()

    self.__ko_client = KickoffClient(key_bytes, ssh_private_key_password, 
                                     self.cxone_flow_url.rstrip("/") + f"/{self.scm_key}/kickoff", 
                                     PROGNAME, self.proxies, not self.ignore_ssl_errors)
  
  @property
  def kickoff_client(self) -> KickoffClient:
    return self.__ko_client
  
  @property
  def scm_key(self) -> str:
    raise NotImplementedError("scm_key")
  
  async def __write_audit(self, repo_repr : str, result : str, scanid : str) -> None:
    async with self.__file_lock:
      with open(self.__audit_file_path, "at") as f:
        f.write(f"\"{repo_repr}\",\"{result}\",\"{scanid}\"\n")
  
  def __callback(self, status : KickoffStatusCodes, msg : KickoffResponseMsg, delay : int) -> bool:
    if status == KickoffStatusCodes.TOO_MANY_SCANS:
      self.log().info(f"Server has {len(msg.running_scans)} running scans, asked to back off.  Delaying {delay} seconds before trying to start scan.")
      for scan in msg.running_scans:
        self.log().info(f"Running: {scan.project_name}@{scan.scan_branch} (Scan Id: {scan.scan_id})")
    else:
      self.log().info(f"Server status: {status}")

    return True

  async def _exec_kickoff(self, repo_repr : str, msg : KickoffMsg) -> Union[KickoffStatusCodes, None]:
    # Throttle scan submissions to avoid the chance of overloading the system with scans.
    async with self.__lock:
      try:
        status, response = await self.__ko_client.kickoff_scan(msg, self.__callback)
        if status == KickoffStatusCodes.SCAN_STARTED:
          self.log().info(f"Scan started: ScanId [{response.started_scan.scan_id}] Project [{response.started_scan.project_name}] for repository [{repo_repr}]")
          await asyncio.sleep(2)
          await self.__write_audit(repo_repr, status, response.started_scan.scan_id)
          return status
        else:
          self.log().warning(f"Server responded with status [{status}] for scan attempt with repository [{repo_repr}]")
          await self.__write_audit(repo_repr, status, "N/A")

      except KickoffClientException as ex:
        await self.__write_audit(repo_repr, ex, "N/A")
        self.log().exception(ex)

