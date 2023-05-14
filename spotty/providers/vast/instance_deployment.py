import json
import subprocess
import time
from argparse import Namespace

from spotty.commands.writers.abstract_output_writrer import AbstractOutputWriter
from spotty.deployment.abstract_cloud_instance.abstract_data_transfer import AbstractDataTransfer
from spotty.deployment.abstract_cloud_instance.abstract_instance_deployment import AbstractInstanceDeployment
from spotty.deployment.container.abstract_container_commands import AbstractContainerCommands
from spotty.providers.vast.config.instance_config import InstanceConfig

from spotty.providers.vast.helpers.catch_stdout import catch_stdout
from spotty.providers.vast.helpers.vast_api_key import vast_api_key
from spotty.providers.vast.helpers.vast_cli import server_url_default, show__instances, create__instance, \
    search__offers, displayable_fields, display_table, stop__instance, destroy__instance
from spotty.providers.vast.resource_managers.ssh_key_manager import SshKeyManager

default_args = {
    "raw": True,
    "api_key": vast_api_key,
    'url': server_url_default,
}


class InstanceDeployment(AbstractInstanceDeployment):
    instance_config: InstanceConfig

    def __init__(self, instance_config: InstanceConfig):
        super().__init__(instance_config)
        self._instance = None

    def get_instance(self, force_update=False) -> dict:
        if force_update or not self._instance:
            args = Namespace(**{
                "raw": True,
                "api_key": vast_api_key,
                'url': server_url_default,
            })

            self._instance = next(filter(lambda x: x.get('label') == self.instance_config.name,
                                         json.loads(catch_stdout(lambda: show__instances(args)))), {})
        return self._instance

    @property
    def ssh_key_manager(self) -> SshKeyManager:
        return SshKeyManager()

    def deploy(self, container_commands: AbstractContainerCommands, output: AbstractOutputWriter,
               bucket_name: str = None, data_transfer: AbstractDataTransfer = None, dry_run: bool = False):
        machine = self._find_instance(output)

        if 'docker login' not in self.instance_config.image_login:
            login = subprocess.check_output(self.instance_config.image_login, shell=True).decode().split('\n')[0]
        else:
            login = self.instance_config.image_login

        if login:
            login = login.split('docker login ')[-1]

        args = Namespace(**{
            "id": machine['id'],
            "image": self.instance_config.container_config.image,
            "env": ' '.join(
                [f'-e {key}={value}' for key, value in self.instance_config.container_config.env.items()]) + ' ' +
                   ' '.join([f"-p {i['containerPort']}:{i['containerPort']}" for i in
                             self.instance_config.container_config.ports]),
            "price": machine['dph_base'] * self.instance_config.bid_ratio,
            "disk": self.instance_config.root_volume_size,
            "label": self.instance_config.name,
            "extra": None,
            "onstart": None,
            "onstart_cmd": None,
            "args": None,
            "login": login,
            "python_utf8": False,
            "lang_utf8": False,
            "jupyter": False,
            "ssh": True,
            "direct": True,
            "use_jupyter_lab": False,
            "jupyter_dir": None,
            "jupyter_lab": None,
            "create_from": None,
            "force": None,
        }, **default_args)

        output_str = catch_stdout(lambda: create__instance(args))

        if json.loads(output_str)['success']:
            for i in range(20):
                time.sleep(30)

                instance = self.get_instance(force_update=True)
                status = (instance.get('status_msg') or "").lower()

                if "success" in status and instance.get('ports'):
                    output.write("Instance created successfully.")
                    break
                elif "error" in status:
                    output.write(f"error message: {status}")
                    raise ValueError("Instance creation failed.")

                elif i == 19:
                    output.write(f"Instance creation timeout. Current instance status: {status}")
                    output.write("check manually at https://cloud.vast.ai/instances/")
                    raise ValueError("Instance creation failed.")

            self.ssh_key_manager.match_rsa_key(default_args)

    def _find_instance(self, output: AbstractOutputWriter) -> dict:
        output.write(f"Finding instance related to query:\n{self.instance_config.query}"
                     f"sorted by: {self.instance_config.sort}\n")
        query = self.instance_config.query.replace("\r\n", "\n").replace("\n", " ")
        query += f" disk_space>={self.instance_config.root_volume_size}"
        query += f" direct_port_count>{len(self.instance_config.container_config.ports)}"  # strict > to have at least one port for direct ssh
        query += " rentable=True"

        args = Namespace(**{
            'query': query,
            'type': self.instance_config.type,
            'order': self.instance_config.sort,
            'storage': self.instance_config.root_volume_size,
            'no_default': False,
            'disable_bundling': False,
            'api_key': '',
            'url': server_url_default,
            'raw': True
        })

        output_str = catch_stdout(lambda: search__offers(args))
        selected_machine = next(iter(json.loads(output_str)), None)

        if selected_machine:
            output.write("\n\nselected machine:")
            display_table([selected_machine], displayable_fields)
            return selected_machine
        else:
            raise ValueError('No instances found with these parameters.')

    def delete(self, output: AbstractOutputWriter):
        instance_id = self.get_instance().get('id')
        if instance_id:
            args = Namespace(**default_args, id=instance_id)
            output.write('Deleting the instance...')
            destroy__instance(args)

    def stop(self, output: AbstractOutputWriter):
        instance_id = self.get_instance().get('id')
        if instance_id:
            args = Namespace(**default_args, id=instance_id)
            output.write('Shutting down the instance...')
            stop__instance(args)

    @property
    def ssh_port(self) -> int:
        instance = self.get_instance()

        for port, host in instance.get('ports', {}).items():
            if '22' in port:
                return int(host[0]['HostPort'])

        raise ValueError('No ssh port found.')