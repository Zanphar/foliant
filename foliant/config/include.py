from pathlib import Path

from yaml import safe_load, add_constructor

from foliant.config.base import BaseParser


class Parser(BaseParser):
    def _resolve_include_tag(self, _, node) -> str:
        '''Replace value after ``!include`` with the content of the referenced file.'''

        parts = node.value.split('#')

        if len(parts) == 1:
            path = Path(parts[0]).expanduser()

            with open(self.project_path/path) as include_file:
                return safe_load(include_file)

        elif len(parts) == 2:
            path, section = Path(parts[0]).expanduser(), parts[1]

            with open(self.project_path/path) as include_file:
                return safe_load(include_file)[section]

        else:
            raise ValueError('Invalid include syntax')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        add_constructor('!include', self._resolve_include_tag)
