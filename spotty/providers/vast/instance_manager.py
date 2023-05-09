import io
import json
import logging
import os
import shlex
import subprocess
import sys
import time

import requests

from spotty.commands.writers.abstract_output_writrer import AbstractOutputWriter
from spotty.config.project_config import ProjectConfig
from spotty.deployment.abstract_ssh_instance_manager import AbstractSshInstanceManager
from spotty.deployment.utils.commands import get_ssh_command
from spotty.providers.remote.helpers.rsync import check_rsync_installed, get_upload_command
from spotty.providers.vast.config.instance_config import InstanceConfig
from spotty.providers.vast.helpers.catch_stdout import catch_stdout
from spotty.providers.vast.helpers.vast import create__instance, search__offers, server_url_default, display_table, \
    displayable_fields, parse_env, api_key_guard, api_key_file, show__instances, stop__instance, destroy__instance, \
    show__user, apiurl

from argparse import Namespace

from spotty.providers.vast.helpers.vast_api_key import vast_api_key
from spotty.providers.vast.resource_managers.ssh_key_manager import SshKeyManager
from spotty.utils import render_table

default_args = {
    "raw": True,
    "api_key": vast_api_key,
    'url': server_url_default,
}


class InstanceManager(AbstractSshInstanceManager):
    instance_config: InstanceConfig
    ssh_key_manager: SshKeyManager
    running_instance: None

    def __init__(self, project_config: ProjectConfig, instance_config: dict):
        super().__init__(project_config, instance_config)
        self.ssh_key_manager = SshKeyManager()
        self.running_instance = None

    def _get_instance_config(self, instance_config: dict) -> InstanceConfig:
        """Validates the instance config and returns an InstanceConfig object."""
        return InstanceConfig(instance_config, self.project_config)

    def is_running(self):
        """Assuming the remote instance is running."""
        instance = self._get_running_instances()
        if instance and instance.get('actual_status') == "exited":
            raise ValueError("Instance outbid")
        return instance.get("actual_status") == "running"

    def clean(self, output: AbstractOutputWriter):
        pass

    def delete(self, output: AbstractOutputWriter):
        pass

    def exec(self, command: str, tty: bool = True) -> int:
        """Executes a command on the host OS."""
        super().exec(command='')

    def start(self, output: AbstractOutputWriter, dry_run=False):
        # make sure the Dockerfile exists
        self._check_dockerfile_exists()

        if not dry_run:
            # check if the instance is already running
            if self.is_running():
                print('Instance is already running. Are you sure you want to restart it?')
                res = input('Type "y" to confirm: ')
                if res != 'y':
                    raise ValueError('The operation was cancelled.')

                # terminating the instance to make EBS volumes available (the stack will be deleted later)
                output.write('Terminating the instance... ', newline=False)
                self.stop(False, output)
                output.write('DONE')

        machine = self._find_instance(output)

        args = Namespace(**{
            "id": machine['id'],
            "image": self.instance_config.container_config.image,
            "env": ' '.join(
                [f'-e {key}={value}' for key, value in self.instance_config.container_config.env.items()]) + ' ' +
                 ' '.join([f"-p {i['containerPort']}:{i['containerPort']}" for i in
                             self.instance_config.container_config.ports]),
            "price": machine['dph_base'] * 1.2,
            "disk": self.instance_config.root_volume_size,
            "label": self.instance_config.name,
            "extra": None,
            "onstart": None,
            "onstart_cmd": None,
            "args": None,
            "login": self.instance_config.image_login,
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
            for i in range(10):
                time.sleep(15)

                instance = self._get_running_instances(force_update=True)
                status = (instance.get('status_msg') or "").lower()

                if "success" in status and instance.get('ports'):
                    output.write("Instance created successfully.")
                    break
                elif "error" in status:
                    output.write(f"error message: {status}")
                    self.stop(False, output)
                    raise ValueError("Instance creation failed.")

            self._match_rsa_key(output)

    def stop(self, only_shutdown: bool, output: AbstractOutputWriter):
        instance_id = self._get_running_instances().get('id')
        if instance_id:
            args = Namespace(**default_args, id=instance_id)
            if only_shutdown:
                output.write('Shutting down the instance...')
                stop__instance(args)
            else:
                destroy__instance(args)
        else:
            output.write('Instance is not running.')

    def sync(self, output: AbstractOutputWriter, dry_run=False):

        output.write('Syncing files with the instance...')

        # check rsync is installed
        check_rsync_installed()

        # sync the project with the instance
        rsync_cmd = get_upload_command(
            local_dir=self.project_config.project_dir,
            remote_dir=self.instance_config.host_project_dir,
            ssh_user=self.ssh_user,
            ssh_host=self.ssh_host,
            ssh_key_path=self.ssh_key_path,
            ssh_port=self.ssh_port,
            filters=self.project_config.sync_filters,
            use_sudo=(not self.instance_config.container_config.run_as_host_user),
            dry_run=dry_run,
        )

        # execute the command locally
        logging.debug('rsync command: ' + rsync_cmd)

        exit_code = subprocess.call(rsync_cmd, shell=True)
        if exit_code != 0:
            raise ValueError('Failed to upload files to the instance.')

    def download(self, download_filters: list, output: AbstractOutputWriter, dry_run=False):

        output.write('Downloading files from the instance...')
        exit()
        # check rsync is installed
        check_rsync_installed()

        # sync the project with the instance
        rsync_cmd = get_download_command(
            local_dir=self.project_config.project_dir,
            remote_dir=self.instance_config.host_project_dir,
            ssh_user=self.ssh_user,
            ssh_host=self.ssh_host,
            ssh_key_path=self.ssh_key_path,
            ssh_port=self.ssh_port,
            filters=download_filters,
            use_sudo=(not self.instance_config.container_config.run_as_host_user),
            dry_run=dry_run,
        )

        # execute the command locally
        logging.debug('rsync command: ' + rsync_cmd)
        exit_code = subprocess.call(rsync_cmd, shell=True)
        if exit_code != 0:
            raise ValueError('Failed to download files from the instance.')

    def _find_instance(self, output: AbstractOutputWriter) -> dict:
        output.write(f"Finding instance related to query:\n{self.instance_config.query}"
                     f"sorted by: {self.instance_config.sort}\n"
                     f"bid price: {self.instance_config.max_price}")
        query = self.instance_config.query.replace("\r\n", "\n").replace("\n", " ")
        query += f" disk_space>={self.instance_config.root_volume_size}"
        query += f" direct_port_count>={len(self.instance_config.container_config.ports)}"
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

        if selected_machine and selected_machine['dph_total'] <= self.instance_config.max_price:
            output.write("\n\nselected machine:")
            display_table([selected_machine], displayable_fields)
            return selected_machine
        else:
            raise ValueError('No instances found with these parameters.')

    def _match_rsa_key(self, output: AbstractOutputWriter):
        user = json.loads(catch_stdout(lambda: show__user(Namespace(**default_args))))
        if user["ssh_key"] != self.ssh_key_manager.get_public_key_value():
            print('Vast ai account already have a different RSA key registered.')
            res = input('Type "y" to update it automatically: ')
            if res != 'y':
                raise ValueError(f'Put your private rsa key in {self.ssh_key_manager.private_key_file}')
            output.write("Updating RSA key...")

            url = apiurl(Namespace(**default_args), f"/users/{user['id']}/")
            requests.put(url, json={
                "ssh_key": self.ssh_key_manager.get_public_key_value()
            })

    def _get_running_instances(self, force_update=False) -> dict:
        if force_update or not self.running_instance:
            args = Namespace(**{
                "raw": True,
                "api_key": vast_api_key,
                'url': server_url_default,
            })

            self.running_instance = next(iter(json.loads(catch_stdout(lambda: show__instances(args)))), {})

        return self.running_instance or {}

    def get_status_text(self):
        instance = self._get_running_instances()
        table = [
            ('CPU', instance.get('cpu_name') + f" ({int(instance.get('cpu_cores_effective'))}C/{instance.get('cpu_cores')}T)"),
            ('GPU', f"{instance.get('num_gpus')}x {instance.get('gpu_name')} {int(instance.get('gpu_ram')/1024)}GB ({instance.get('total_flops')} TFLOPS) "),
            ('Network Up/Down', f"{int(instance.get('inet_up')/1024)}/{int(instance.get('inet_down')/1024)} MB/s"),
            ('Network Cost', f"${instance.get('inet_up_cost')}/{instance.get('inet_down_cost')} $/GB"),
            ('hourly price', f"${instance.get('dph_total')}/h"),
            ('public ip', instance.get('public_ipaddr')),

        ]

        port_tables = [('Docker', 'Exposed')]
        for port, host in instance.get('ports', {}).items():
            if "22" not in port:
                port_tables.append((port, host[0]['HostPort']))

        return render_table(table) + "\nPort mapping:\n" + render_table(port_tables)

    @property
    def ssh_host(self) -> str:
        return self._get_running_instances().get('public_ipaddr')

    @property
    def ssh_key_path(self):
        return self.ssh_key_manager.private_key_file

    @property
    def ssh_port(self) -> int:
        instance = self._get_running_instances()

        for port, host in instance.get('ports', {}).items():
            if '22' in port:
                return int(host[0]['HostPort'])

        raise ValueError('No ssh port found.')

    @property
    def ssh_env_vars(self) -> dict:
        """Environmental variables that will be set when ssh to the instance."""
        return {}
    @property
    def use_tmux(self) -> bool:
        """As we can't connect to host on vast.ai, we can't install tmux"""
        return False
