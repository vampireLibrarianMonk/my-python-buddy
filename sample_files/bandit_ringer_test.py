# MEDIUM severity: exec usage --> B102
def run_code(code):
    exec(code)


# Medium severity: request_without_timeout --> B113
# HIGH severity: request verify=False --> B501
import requests


def insecure_request():
    return requests.get("https://example.com", verify=False)


# HIGH severity: chmod world‑writable --> B103
import os


def write_world_writable(path):
    os.chmod(path, 0o777)


# LOW severity: blacklist --> B404
# HIGH severity:  subprocess with shell=True and dynamic input --> B602
import subprocess


def do_shell(cmd):
    subprocess.Popen(cmd, shell=True)
