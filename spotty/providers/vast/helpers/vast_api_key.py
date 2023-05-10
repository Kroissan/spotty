import os

from spotty.providers.vast.helpers.vast_cli import api_key_file

vast_api_key = ""
if os.path.exists(api_key_file):
    with open(api_key_file, "r") as reader:
        vast_api_key = reader.read().strip()
