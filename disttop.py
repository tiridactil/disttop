#!/usr/bin/python3
"""Simple script to run top on multiple machines at once.

This script runs top through ssh on all specified machines.
On every refresh it runs 'ssh -x top -bn 1' for every host.
Uses ssh connexion multiplexing to avoid too many connections.

Hosts that cannot be contacted are listed at the bottom

Future Work:
- Support for -i -H etc.
"""

import argparse
import multiprocessing
import re
import string
import subprocess
import sys

from itertools import chain
from pathlib import Path

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
		self.error = error.strip()
		self.host = host

def prepssh(host):
	"""Setup connection multiplexing to 'host'"""
	# build base command
	cmd = ["ssh", host, "-NfM", "-S", "~/.disttop/ssh_%h_%p_%r"]

	# Run command, pipe both outputs
	subprocess.Popen(cmd).communicate()

def cleanssh(host):
	"""Teardown connection multiplexing to 'host'"""
	# build base command
	cmd = ["ssh", host, "-qS", "~/.disttop/ssh_%h_%p_%r", "-O", "exit"]

	# Run command, pipe both outputs
	subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).communicate()

def calltop(host):
	"""ssh onto 'host' and retrieve currently running processes.
	Returns the output of top as a single string.
	Raises SSH_Error on any error of the command.
	"""
	# build base command
	cmd = ["ssh", host, "-xT", "-S", "~/.disttop/ssh_%h_%p_%r", "-oBatchMode=True", "top", "-bsn", "1"]

	# Run command, pipe both outputs
	with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
		out, err = proc.communicate()

		# Did it succeed
		if proc.returncode != 0:
			# Don't try to figure out why, just throw the error
			raise SSH_Error(err.decode("utf-8") if err else "Unkown Error", host)

		# return the text
		return out.decode("utf-8") if out else ""

################################################################################
#               Top Handling
################################################################################

class Process:
	"""Class representing a single running process .

	Attributes:
		attributes are the same as 'top' plus the added host line
	"""
	def __init__(self, host, data):
		self.host = host
		fields = data.split()
		if(len(fields) < 12) :
			print('ERROR: invalid top line for host {} : "{}"({})'.format(host, data, fields), file=sys.stderr)
			sys.exit(1)
		self.pid, self.user, self.pr, self.nice, self.virt, self.res, self.shr, self.s, self.cpu, self.mem, self.time, *self.cmd = fields
		self.cmd  = " ".join(self.cmd)


def getprocs(host):
	"""Get processes running on host as a list of 'Process'
	Forwards any exception from calltop
	"""
	# calltop first, obviously
	try:
		out = calltop(host)
	except SSH_Error as s:
		return {'broken': "{}: '{}'".format(host, s.error) }

	# each line represents a process
	procs = []
	for line in out.splitlines():
		# get rid of leading whitespace
		sl = line.lstrip()
		if not sl :
			continue

		# it so happens that actual process lines start with a number, the PID
		# ignore those that don't
		if not sl[0].isnumeric():
			continue

		# convert to process and append
		procs.append( Process(host, sl) )

	# return the list of Process
	return {'procs': procs}


################################################################################
#               Printing
################################################################################
def nstr(stdscr, y, x, text, n):
	"""wrapper around printing in curses.
	calls print if no curses window is passed
	y, x, text, n are interpreted as window.addnstr in curses"""
	if stdscr:
		stdscr.addnstr(y, x, text, n)
	else:
		print(text)

def print_procs(stdscr, procs, broken_procs):
	"""print the list of process to the screen, with some nice formatting"""
	# pre-create the list of fields and which side to pad when printing
	fields  = [('host','<'), ('pid','>'), ('user','<'), ('pr','>'), ('nice','>'), ('virt','>'), ('res','>'), ('shr','>'), ('s','>'), ('cpu','>'), ('mem','>'), ('time','>'), ('cmd','<')]

	# to look nice, I want everything to align
	# I do this by calculing the max width for each column
	# the max might be off screen and I don't care
	# don't forget the header in size calculation
	fields = [(f, s, max( [ len(f) ] + [len( getattr(p,f) ) for p in procs] )) for f,s in fields]

	# get the max coordinates, if there is no screen instance just fake it
	y, x = stdscr.getmaxyx() if stdscr else (1000, 1000)
	x -= 1 # I use x as the parameter to addnstr and maxX is to large

	# print the header
	text = " | ".join( "{val:{s}{w}}".format(val = f, s = s, w = w) for f, s, w in fields )
	nstr(stdscr, 0, 0, text, x)
	nstr(stdscr, 1, 0, "-" * x, x)

	# actually print the processes
	for pi, p in enumerate(procs[:y - 3]):
		text = "   ".join( "{val:{s}{w}}".format(val = getattr(p,f), s = s, w = w) for f, s, w in fields )
		nstr(stdscr, pi + 2, 0, text, x)

	# print broken_procs
	nstr(stdscr, y - 1, 0, "Broken Hosts: {}".format(", ".join(broken_procs)), x)

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

################################################################################
#               Main Loop
################################################################################
# running top through subprocess ssh is not a gread idea, in part because it is slow
# to avoid slowing down per host, use a pool to do the ssh commands
pool = multiprocessing.Pool(len(options.hosts))

# main loop using curses
from curses import wrapper
def main(stdscr):
	# print every second even if users don't touch anything
	stdscr.timeout(1000)
	while True:
		# even in the pool this is pretty slow, start it right away	but don't wait for the result
		results = pool.imap_unordered(getprocs, options.hosts, chunksize = 1)

		# while we are waiting for ssh check if the users wants to stop
		if stdscr.getch() != -1:
			# if the users pressed ANY key, just assuming it's time to stop
			return

		# pool.imap* returns an iterator, not a list. Wait for all results
		results = [r for r in results]

		# filter the good results from the bad
		good    = [r['procs' ] for r in results if 'procs'  in r]
		brokens = [r['broken'] for r in results if 'broken' in r]

		# pool.imap* return a list so this is a 2d list, flatten it
		procs   = [j for sub in good for j in sub]

		# sort the process by cpu time so the active ones are on top
		# since this is a fancy future list from pool.imap*,
		# it will wait for ssh results implicitly
		procs.sort(key=lambda p: float(p.cpu), reverse=True)

		# everything is ready to print
		# clean the screen
		stdscr.clear()

		# do the fancy printing
		print_procs(stdscr, procs, brokens)

		# push it to the screen
		stdscr.refresh()

# create the directory for the socket multiplexing if needed
Path("~/.disttop").mkdir(parents=True, exist_ok=True)

# prep the ssh multiplexing
pool.map(prepssh, options.hosts, chunksize = 1)

# run the main loop
wrapper(main)

# teardown the ssh multiplexing
pool.map(cleanssh, options.hosts, chunksize = 1)