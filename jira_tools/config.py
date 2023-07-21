import json


def load_config(config_file):
    with open(config_file) as config_file:
        return json.loads(config_file.read())


def get_config_and_options():
    """Returns the configuration and cli options."""
    # FIXME merge config and options retrieval
    pass
