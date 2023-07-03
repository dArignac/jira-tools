import json


def load_config(config_file):
    with open(config_file) as config_file:
        return json.loads(config_file.read())
