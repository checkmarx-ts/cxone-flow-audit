from .common import Operation

class Remover(Operation):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
