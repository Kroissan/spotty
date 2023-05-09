import os
from typing import List
from spotty.config.abstract_instance_config import AbstractInstanceConfig
from spotty.config.abstract_instance_volume import AbstractInstanceVolume
from spotty.config.project_config import ProjectConfig
from spotty.config.host_path_volume import HostPathVolume
from spotty.providers.vast.config.validation import validate_instance_parameters


class InstanceConfig(AbstractInstanceConfig):

    def __init__(self, instance_config: dict, project_config: ProjectConfig):
        super().__init__(instance_config, project_config)

    def _validate_instance_params(self, params: dict):
        # validate the config and fill missing parameters with the default values
        return validate_instance_parameters(params)

    def _get_instance_volumes(self) -> List[AbstractInstanceVolume]:
        volumes = []
        for volume_config in self._params['volumes']:
            volume_type = volume_config['type']
            if volume_type == HostPathVolume.TYPE_NAME:
                volumes.append(HostPathVolume(volume_config))
            else:
                raise ValueError('Volume type "%s" is not supported.' % volume_type)

        return volumes

    @property
    def user(self):
        return 'ubuntu'

    @property
    def query(self) -> str:
        return self._params['query']

    @property
    def type(self) -> str:
        return self._params['type']

    @property
    def sort(self) -> int:
        return self._params['sort']

    @property
    def max_price(self) -> float:
        return self._params['maxPrice']

    @property
    def root_volume_size(self) -> int:
        return self._params['rootVolumeSize']

    @property
    def ports(self) -> List[str]:
        return list(set(self._params['ports']))

    @property
    def image_login(self) -> str:
        return self._params['imageLogin']

    @property
    def key_path(self) -> str:
        key_path = os.path.expanduser(self._params['keyPath'])
        if not os.path.isabs(key_path):
            key_path = os.path.join(self.project_config.project_dir, key_path)

        key_path = os.path.normpath(key_path)

        return key_path
