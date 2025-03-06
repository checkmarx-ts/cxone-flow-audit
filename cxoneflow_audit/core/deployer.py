from .common import Operation

class Deployer(Operation):
  def __init__(self, shared_secret : str, replace : bool, *args):
    super().__init__(*args)
    self.__shared_secret = shared_secret
    self.__replace = replace

  @property
  def shared_secret(self) -> str:
    return self.__shared_secret

  @property
  def replace(self) -> bool:
    return self.__replace
