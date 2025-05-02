import json, os

def get_config():
    config_data = {}
    script_dir = os.path.dirname(__file__)
    
    # Load config.json
    config_path = os.path.join(script_dir, 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as config_file:
            config_data.update(json.load(config_file))
    
    return config_data