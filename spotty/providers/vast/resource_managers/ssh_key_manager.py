import json
import os
import subprocess
from argparse import Namespace

import requests

from spotty.configuration import get_spotty_keys_dir
from shutil import which
from spotty.providers.instance_manager_factory import PROVIDER_VAST
from spotty.providers.vast.helpers.catch_stdout import catch_stdout
from spotty.providers.vast.helpers.vast_cli import show__user, apiurl


class SshKeyManager(object):

    def __init__(self):
        self._key_name = 'ssh-key'
        self._keys_dir = get_spotty_keys_dir(PROVIDER_VAST)

    @property
    def private_key_file(self):
        return os.path.join(self._keys_dir, self._key_name)

    @property
    def public_key_file(self):
        return os.path.join(self._keys_dir, self._key_name + '.pub')

    def get_public_key_value(self):
        # generate a key if it doesn't exist
        if not os.path.isfile(self.private_key_file) or not os.path.isfile(self.public_key_file):
            self._generate_ssh_key()

        # read the public key value
        with open(self.public_key_file, 'r') as f:
            public_key_value = f.read()

        return public_key_value

    def _generate_ssh_key(self):
        # delete the private key file if it already exists
        if os.path.isfile(self.private_key_file):
            os.unlink(self.private_key_file)

        # create a provider subdirectory
        if not os.path.isdir(self._keys_dir):
            os.makedirs(self._keys_dir, mode=0o755, exist_ok=True)

        # check that the "ssh-keygen" tool is installed
        ssh_keygen_cmd = 'ssh-keygen'
        if which(ssh_keygen_cmd) is None:
            raise ValueError('"ssh-keygen" command not found.')

        generate_key_cmd = [ssh_keygen_cmd, '-t', 'rsa', '-N', '', '-f', self.private_key_file, '-q']

        # generate a key pair
        res = subprocess.run(generate_key_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode:
            raise subprocess.CalledProcessError(res.returncode, generate_key_cmd)

    def match_rsa_key(self, args):
        user = json.loads(catch_stdout(lambda: show__user(Namespace(**args))))
        if user["ssh_key"] != self.get_public_key_value():
            print('Vast ai account already have a different RSA key registered.')
            print('local:\n', self.get_public_key_value())
            print('remote:\n', user["ssh_key"])
            res = input('Type "y" to update it automatically: ')
            if res != 'y':
                raise ValueError(f'Put your private rsa key in {self.private_key_file}')
            print("Updating RSA key...")

            url = apiurl(Namespace(**args), f"/users/{user['id']}/")
            requests.put(url, json={
                "ssh_key": self.get_public_key_value()
            })

