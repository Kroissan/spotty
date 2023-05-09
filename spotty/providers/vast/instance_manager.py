import io
import json
import logging
import subprocess
import sys

from spotty.commands.writers.abstract_output_writrer import AbstractOutputWriter
from spotty.deployment.abstract_ssh_instance_manager import AbstractSshInstanceManager
from spotty.providers.vast.config.instance_config import InstanceConfig
from spotty.providers.vast.helpers.vast import create__instance, search__offers, server_url_default, display_table, \
    displayable_fields, parse_env

from argparse import Namespace


class InstanceManager(AbstractSshInstanceManager):
    instance_config: InstanceConfig

    def _get_instance_config(self, instance_config: dict) -> InstanceConfig:
        """Validates the instance config and returns an InstanceConfig object."""
        return InstanceConfig(instance_config, self.project_config)

    def is_running(self):
        """Assuming the remote instance is running."""
        return True

    def clean(self, output: AbstractOutputWriter):
        pass

    def start(self, output: AbstractOutputWriter, dry_run=False):
        machine_id = self._find_instance(output)


        args = Namespace(**{
            "id": machine_id,
            "image": self.instance_config.container_config.image,
            "env": ' '.join([f'-e {key}={value}' for key, value in self.instance_config.container_config.env.items()]) + ' ' +
                   ' '.join([f"-p {i['containerPort']}:{i['containerPort']}" for i in self.instance_config.container_config.ports]),
            "price": self.instance_config.max_price,
            "disk": self.instance_config.root_volume_size,
            "label": self.instance_config.name,
            "extra": None,
            "onstart": None,
            "args": None,
            "image_login": self.instance_config.image_login,
            "python_utf8": False,
            "lang_utf8": False,
            "use_jupyter_lab": False,
            "jupyter_dir": None,
            "create_from": None,
            "force": None
        })
        print(machine_id)
        exit()

    def sync(self, output: AbstractOutputWriter, dry_run=False):

        output.write('Syncing files with the instance...')
        exit()
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

    def _find_instance(self, output: AbstractOutputWriter) -> int:
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

        output_catch = io.StringIO()
        sys.stdout = output_catch
        search__offers(args)
        sys.stdout = sys.__stdout__

        # get the output as a string
        output_str = output_catch.getvalue()
        selected_machine = next(iter(json.loads(output_str)), None)

        if selected_machine and selected_machine['dph_total'] <= self.instance_config.max_price:
            output.write("\n\nselected machine:")
            display_table([selected_machine], displayable_fields)
            return selected_machine['id']
        else:
            raise ValueError('No instances found with these parameters.')

    @property
    def ssh_host(self) -> str:
        return self.instance_config.host

    @property
    def ssh_key_path(self) -> str:
        return self.instance_config.key_path

    @property
    def ssh_port(self) -> int:
        return self.instance_config.port
