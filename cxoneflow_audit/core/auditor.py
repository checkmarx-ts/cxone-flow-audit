from .common import Operation

class Auditor(Operation):

  def __init__(self, outfile : str, only_not_cfg : bool, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__outfile = outfile
    self.__only_not_cfg = only_not_cfg

  @property
  def outfile(self) -> str:
    return self.__outfile
  
  @property
  def skip_configured(self) -> bool:
    return self.__only_not_cfg
