import re

class NameMatcher:

  @staticmethod
  def create_as_skip(regex : str):
    inst = NameMatcher()
    inst.__regex = re.compile(regex)
    inst.__invert = True
    return inst


  @staticmethod
  def create_as_match(regex : str):
    inst = NameMatcher()
    inst.__regex = re.compile(regex)
    inst.__invert = False
    return inst


  def matches(self, test_value : str) -> bool:
    result = self.__regex.search(test_value)

    return not bool(result) if self.__invert else bool(result)


class ScmException(Exception):
  pass