from spotty.commands.writers.abstract_output_writrer import AbstractOutputWriter
from spotty.config.project_config import ProjectConfig
from spotty.deployment.container.vast.vast_commands import VastCommands
from spotty.providers.remote.instance_manager import InstanceManager as RemoteInstanceManager
from spotty.providers.vast.config.instance_config import InstanceConfig
from spotty.providers.vast.instance_deployment import InstanceDeployment, default_args
from spotty.utils import render_table


class InstanceManager(RemoteInstanceManager):
    instance_config: InstanceConfig
    instance_deployment: InstanceDeployment

    def __init__(self, project_config: ProjectConfig, instance_config: dict):
        super().__init__(project_config, instance_config)
        self.instance_deployment = InstanceDeployment(self._get_instance_config(instance_config))

    def _get_instance_config(self, instance_config: dict) -> InstanceConfig:
        """Validates the instance config and returns an InstanceConfig object."""
        return InstanceConfig(instance_config, self.project_config)

    def is_running(self):
        """Assuming the remote instance is running."""
        instance = self.instance_deployment.get_instance()
        if instance and instance.get('actual_status') == "exited":
            raise ValueError("Instance outbid")
        return instance.get("actual_status") == "running"

    def clean(self, output: AbstractOutputWriter):
        pass

    def delete(self, output: AbstractOutputWriter):
        pass

    def exec(self, command: str, tty: bool = True) -> int:
        """Executes a command on the host OS."""
        self.instance_deployment.ssh_key_manager.match_rsa_key(default_args)
        if command == "$SHELL":
            raise ValueError("Cannot run shell on Host on Vast.ai")
        super().exec(command, tty)

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

            try:
                self.instance_deployment.deploy(self.container_commands, output, dry_run=dry_run)
            except Exception as e:
                output.write("an error occurred while deploying the instance: " + str(e))
                res = input('Type "y" to shut it down: ')
                if res == 'y':
                    self.stop(False, output)
                    raise e

            self.sync(output)
            self.exec("echo 'HOME=/workspace && cd' >> /root/.bashrc")

    def stop(self, only_shutdown: bool, output: AbstractOutputWriter):
        if only_shutdown:
            self.instance_deployment.stop(output)
        else:
            self.instance_deployment.delete(output)

    def get_status_text(self):
        self.is_running()
        instance = self.instance_deployment.get_instance()
        table = [
            ('CPU',
             instance.get('cpu_name') + f" ({int(instance.get('cpu_cores_effective'))}T available)"),
            ('GPU',
             f"{instance.get('num_gpus')}x {instance.get('gpu_name')} {'{:.1f}'.format(int(instance.get('gpu_ram') or 0) / 1024)}GB ({'{:.1f}'.format(instance.get('total_flops', 0))} TFLOPS) "),
            ('Network Up/Down',
             f"{int(instance.get('inet_up', 0))}/{(int(instance.get('inet_down') or 0))} MB/s  |  {int((instance.get('inet_up_billed') or 0) / 1024)}/{int((instance.get('inet_down_billed') or 0) / 1024)} billed"),
            ('Network Cost', f"{instance.get('inet_up_cost')}/{instance.get('inet_down_cost')} $/GB"),
            ('hourly price', "{:.2f}".format(instance.get('dph_total')) + " $/H"),
            ('public ip', instance.get('public_ipaddr')),

        ]

        port_tables = [('Docker', 'Exposed')]
        for port, host in instance.get('ports', {}).items():
            if "22" not in port:
                port_tables.append((port, host[0]['HostPort']))

        return render_table(table) + "\nPort mapping:\n" + render_table(port_tables)

    @property
    def ssh_host(self) -> str:
        return self.instance_deployment.get_instance().get('public_ipaddr')

    @property
    def ssh_key_path(self):
        return self.instance_deployment.ssh_key_manager.private_key_file

    @property
    def ssh_port(self) -> int:
        return self.instance_deployment.ssh_port

    @property
    def ssh_env_vars(self) -> dict:
        """Environmental variables that will be set when ssh to the instance."""
        return {}

    @property
    def use_tmux(self) -> bool:
        """As we can't connect to host on vast.ai, we can't install tmux"""
        return False

    @property
    def container_commands(self) -> VastCommands:
        """A collection of commands to manage a container from the host OS."""
        return VastCommands(self.instance_config)
