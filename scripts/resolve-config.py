"""
Copyright 2023 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
import json
import base64
import sys
from subprocess import Popen, PIPE


def run_command(cmd, input_data=""):
    """
    :param cmd:
    :param input_data:
    """
    return Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=PIPE).communicate(
        input=bytes(input_data, "utf-8")
    )


try:
    CONFIG_FILE = sys.argv[1]
    config_contents = open(CONFIG_FILE).read()
    config = json.loads(config_contents)

    if config.get("credsStore", ""):
        creds_cmd = f"docker-credential-{config['credsStore']}"

        results = run_command(["which", creds_cmd], "")
        if results[0]:
            for key in config.get("auths", {}).keys():
                creds = json.loads(run_command([creds_cmd, "get"], key)[0].strip())
                config["auths"][key] = {
                    "auth": str(
                        base64.b64encode(
                            bytes(
                                f"{creds.get('Username', '')}:{creds.get('Secret', '')}",
                                "utf-8",
                            )
                        ),
                        "utf-8",
                    )
                }

        del config["credsStore"]

    print(json.dumps(config))
except Exception:
    print("{}")
