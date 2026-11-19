import importlib.util
from pathlib import Path
from zipimport import zipimporter, ZipImportError
import logging


def load_plugins_from_directory(directory):
    plugin_paths = set(Path(directory).rglob("*.pyroplug"))
    for plugin_path in plugin_paths:
        try:
            logging.error(f"Loading plugin {plugin_path}")
            zimport = zipimporter(plugin_path.as_posix())
            spec = zimport.find_spec("plugin")
            if spec:
                module = importlib.util.module_from_spec(spec)
                if spec.loader:
                    spec.loader.exec_module(module)
                    module.init_plugin()
        except ZipImportError as ex:
            logging.error(f"Couldn't load plugin {plugin_path}:{ex}")
