from docopt import docopt, DocoptExit
from cxoneflow_audit.__version__ import PROGNAME
from typing import List, Dict
from cxoneflow_audit.util import NameMatcher
import asyncio, os

class SCMTool:

  class UnknownTool(Exception):...

  def __init__(self, *, concurrency : asyncio.Semaphore, proxy : Dict, ssl_ignore : bool, **kwargs):
    self.__command_map = kwargs
    self.__sem = concurrency
    self.__proxy = proxy
    self.__ssl_ignore = ssl_ignore


  @staticmethod
  def resolve_from_env(value, env_key):
    if value is not None:
      return value
    elif env_key in os.environ.keys():
      return os.environ[env_key]
    else:
      return None

  @property
  def concurrency(self) -> asyncio.Semaphore:
    return self.__sem
  
  @property
  def proxy(self) -> Dict:
    return self.__proxy
  
  @property
  def ssl_ignore(self) -> bool:
    return self.__ssl_ignore

  @staticmethod
  def _matcher_factory(skip_regex : str, match_regex : str) -> NameMatcher:
    if skip_regex is not None:
      return NameMatcher.create_as_skip(skip_regex)
    elif match_regex is not None:
      return NameMatcher.create_as_match(match_regex)
    else:
      return NameMatcher.create_as_match(".*")


  def _get_opts(self, docstring : str, args : List[str], help : bool = True):
    try:
      return docopt(docstring, args, version=PROGNAME)
    except DocoptExit as ex:
      if help:
        print(docstring)
        exit(0)
      else:
        print(ex)
        exit(1)

  async def _dispatch(self, docstring : str, cmd_key : str, args_key : str, args : List[str], help : bool = True):
    try:
      args = docopt(docstring, args, version=PROGNAME, options_first = True)

      if args[cmd_key] not in self.__command_map.keys():
          raise SCMTool.UnknownTool(args[cmd_key])
      
      return await self.__command_map[args[cmd_key]](args[args_key], help)
    except DocoptExit as ex:
      if help:
        print(docstring)
        exit(0)
      else:
        print(ex)
        exit(1)

  async def __call__(self, args : List[str], help : bool = True):
    raise NotImplementedError("__call__")
