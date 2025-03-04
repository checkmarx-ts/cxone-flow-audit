import logging, logging.config

def bootstrap(log_level : str, use_console : bool = True, dest_file : str = None):

  selected_handlers = []
  handlers_dict = {}

  if use_console:
    selected_handlers.append("console")
    handlers_dict["console"] = {
              "class": "logging.StreamHandler",
              "formatter": "default",
              "stream": "ext://sys.stdout"
          }

  if dest_file is not None:
    selected_handlers.append("file")
    handlers_dict["file"] = {
              "class": "logging.handlers.RotatingFileHandler",
              "formatter": "default",
              "filename": dest_file,
              "backupCount" : 10,
              "maxBytes" : 1024000000
          }


  log_cfg = {
      "version": 1,
      "formatters": {
          "default": {
              "format": "[%(asctime)s][%(process)d][%(name)s][%(levelname)s] %(message)s",
              "datefmt": "%Y-%m-%dT%H:%M:%S%z"
          }
      },
      "loggers": {
          "root": {
              "handlers": selected_handlers,
              "level": log_level
          }
      }
  }

  log_cfg['handlers'] = handlers_dict

  logging.config.dictConfig(log_cfg)