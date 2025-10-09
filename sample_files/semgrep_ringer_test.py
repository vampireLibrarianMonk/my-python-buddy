# Wildcard import (info)
from math import *

# Print debugging (info)
print("Debugging mode enabled")

import subprocess

import yaml


def load_yaml_bad(stream):
    # Unsafe yaml load (warning)
    data = yaml.load(stream)
    return data


def file_handle_issue():
    # Missing with statement (warning)
    f = open("tmp.txt", "w")
    f.write("oops")
    f.close()


def run_eval(user_input):
    # Eval injection (error)
    eval(user_input)


def run_shell(cmd):
    # Shell=True command (error)
    subprocess.run(cmd, shell=True)
