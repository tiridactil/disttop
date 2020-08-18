#!/usr/bin/python3

import argparse
import subprocess
import sys

################################################################################
#               SSH Handling
################################################################################

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


################################################################################
#               Argument Parsing
################################################################################
parser = argparse.ArgumentParser(description='Distributed wrapper for top')
parser.add_argument('hosts', metavar='hosts', type=str, nargs='*', help='the list of hosts on which to run top')

try:
	options =  parser.parse_args()
except:
	print('ERROR: invalid arguments', file=sys.stderr)
	parser.print_help(sys.stderr)
	sys.exit(1)

for host in options.hosts:
	try:
		print("Calling top for {}".format(host))
		out = calltop(host)
		# print(out)
	except SSH_Error as e:
		print("Host {} encountered an error".format(e.host))
		print(e.error)