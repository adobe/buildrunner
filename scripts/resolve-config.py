import os, json, base64, sys
from subprocess import Popen, PIPE, STDOUT

def run_command (cmd, input_data = ''):
    return Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=PIPE).communicate(input=input_data)

try:
    CONFIG_FILE = sys.argv[1]
    config_contents = open(CONFIG_FILE).read()
    config = json.loads(config_contents)

    if config.get('credsStore', ''):
        creds_cmd = 'docker-credential-{}'.format(config['credsStore'])

        results = run_command(['which', creds_cmd], '')
        if results[0]:
            for key in config.get('auths', {}).keys():
                creds = json.loads(run_command([creds_cmd, 'get'], key)[0].strip())
                config['auths'][key] = {"auth": base64.b64encode('{}:{}'.format(creds.get('Username', ''), creds.get('Secret', '')))}

        del config['credsStore']

    print(json.dumps(config))
except:
    print("{}")
