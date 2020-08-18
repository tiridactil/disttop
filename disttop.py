#!/usr/bin/python3

import argparse
import multiprocessing
import re
import string
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
#               Top Handling
################################################################################

class Process:
	def __init__(self, host, data):
		self.host = host
		fields = data.split()
		if(len(fields) < 12) :
			print('ERROR: invalid top line for host {} : "{}"({})'.format(host, data, fields), file=sys.stderr)
			sys.exit(1)
		self.pid  = fields[0]
		self.user = fields[1]
		self.pr   = fields[2]
		self.nice = fields[3]
		self.virt = fields[4]
		self.res  = fields[5]
		self.shr  = fields[6]
		self.s    = fields[7]
		self.cpu  = fields[8]
		self.mem  = fields[9]
		self.time = fields[10]
		self.cmd  = " ".join(fields[11:])


def getprocs(host):
	procs = []
	out = calltop(host)
	for line in out.splitlines():
		sl = line.lstrip()
		if not sl :
			continue
		if sl[0].isnumeric():
			procs.append( Process(host, sl) )
	return procs


################################################################################
#               Printing
################################################################################

def nstr(stdscr, y, x, text, n):
	if stdscr:
		stdscr.addnstr(y, x, text, n)
	else:
		print(text)

def print_procs(stdscr, procs):
	fields  = ['host', 'pid', 'user', 'pr', 'nice', 'virt', 'res', 'shr', 's', 'cpu', 'mem', 'time', 'cmd']
	formats = ['{val:<{width}}', '{val:>{width}}', '{val:<{width}}', '{val:>{width}}', '{val:>{width}}', '{val:>{width}}', '{val:>{width}}', '{val:>{width}}', '{val:>{width}}', '{val:>{width}}', '{val:>{width}}', '{val:>{width}}', '{val:<{width}}']
	widths = [0] * len(fields);
	i = 0
	for i, f in enumerate(fields):
		widths[i] = len( f )
		for p in procs:
			widths[i] = max( widths[i], len( getattr(p,f) ) )

	y = 1000;
	x = 1000;
	if stdscr:
		y, x = stdscr.getmaxyx()
	text = " | ".join( formats[fi].format(val = f, width = widths[fi]) for fi, f in enumerate(fields) )
	nstr(stdscr, 0, 0, text, x - 1)
	nstr(stdscr, 1, 0, "-" * x, x - 1)
	for pi, p in enumerate(procs[:y - 2]):
		text = "   ".join( formats[fi].format(val = getattr(p,f), width = widths[fi]) for fi, f in enumerate(fields) )
		nstr(stdscr, pi + 2, 0, text, x - 1)

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

pool = multiprocessing.Pool(len(options.hosts))

from curses import wrapper
def main(stdscr):
	stdscr.nodelay(True)
	i = 0
	while True:
		stdscr.clear()
		stdscr.move(0, 0)

		results = pool.map(getprocs, options.hosts, chunksize = 1)
		procs = [p for plist in results for p in plist]
		procs.sort(key=lambda p: float(p.cpu), reverse=True)

		print_procs(stdscr, procs)

		stdscr.refresh()
		if stdscr.getch() >= 0:
			return

wrapper(main)