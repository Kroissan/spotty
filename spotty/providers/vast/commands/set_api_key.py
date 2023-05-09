from argparse import ArgumentParser, Namespace
from spotty.providers.vast.helpers.vast import set__api_key, api_key_file_base, api_key_guard
from spotty.commands.abstract_command import AbstractCommand
from spotty.commands.writers.abstract_output_writrer import AbstractOutputWriter


class SetApiKey(AbstractCommand):

    name = 'set-api-key'
    description = "This will save your api key in a hidden file in your home directory. It authenticates your other vast commands to your account, so don't share it."

    def configure(self, parser: ArgumentParser):
        super().configure(parser)
        parser.add_argument("new_api_key", help="Api key to set as currently logged in user")

    def run(self, args: Namespace, output: AbstractOutputWriter):
        set__api_key(args)
