#!/usr/bin/python3

import argparse
import subprocess


target = "localhost"

cmd = ["ssh", target, "-x", "top", "-bn", "1"]
with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
	try:
		out, _ = proc.communicate()

		print("Process returned code : {}".format(proc.returncode))
		print( out.decode("utf-8") if out else "No output")
	except subprocess.TimeoutExpired:
		print("Command timeout")