import shlex
from spotty.deployment.container.abstract_container_commands import AbstractContainerCommands
from spotty.deployment.utils.cli import shlex_join


class VastCommands(AbstractContainerCommands):
    def exec(self, command: str, interactive: bool = False, tty: bool = False, user: str = None,
             container_name: str = None, working_dir: str = None) -> str:
        return command
