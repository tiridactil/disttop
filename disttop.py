#!/usr/bin/python3

import argparse
import subprocess


target = "localhost"

class SSH_Error(Exception):
    """Exception raised for ssh errors .

    Attributes:
        error -- the stderr output of ssh
        host  -- the host that triggered the error
    """

    def __init__(self, error, host):
        self.error = error
        self.host = host

def calltop(host):
	cmd = ["ssh", host, "-x", "top", "-bn", "1"]
	with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
		out, err = proc.communicate()

		if proc.returncode != 0:
			raise SSH_Error(err.decode("utf-8") if err else "Unkown Error", host)

		return out.decode("utf-8") if out else ""

try:
	out = calltop(target)
	print(out)
except SSH_Error as e:
	print("Host {} encountered an error".format(e.host))
	print(e.error)