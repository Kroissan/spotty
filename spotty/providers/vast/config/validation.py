from schema import Optional, And, Regex, Or, Use
from spotty.config.validation import validate_config, get_instance_parameters_schema
from spotty.providers.vast.helpers.vast_cli import parse_query


def validate_instance_parameters(params: dict):
    from spotty.config.host_path_volume import HostPathVolume

    instance_parameters = {
        Optional('query', default=''): And(str, lambda x: parse_query(x.replace('\r\n', '\n').replace('\n', ' '))),
        Optional('type', default='on-demand'): And(str, lambda x: x in ['bid', 'on-demand']),
        Optional('sort', default='on-demand'): str,
        Optional('bidRatio', default=0): And(Or(float, int, str), Use(str),
                                             Regex(r'^\d+(\.\d{1,6})?$', error='Incorrect value for "maxPrice".'),
                                             Use(float),
                                             And(lambda x: x > 0, error='"bidRatio" should be greater than 0 or '
                                                                        'should  not be specified.'),
                                             ),
        Optional('rootVolumeSize', default=16): And(Or(int, str), Use(str),
                                                    Regex(r'^\d+$', error='Incorrect value for "rootVolumeSize".'),
                                                    Use(int),
                                                    And(lambda x: x > 0,
                                                        error='"rootVolumeSize" should be greater than 0 or should '
                                                              'not be specified.'),
                                                    ),
        Optional('ports', default=[]): [And(str, Regex(r'^port-[0-9]+$'))],
        Optional('imageLogin', default=None): str,
    }

    schema = get_instance_parameters_schema(instance_parameters, HostPathVolume.TYPE_NAME)

    return validate_config(schema, params)
