"Common functions for RGTP clients."

#  common.py - routines shared by many parts of yarrow
#
# Copyright (c) 2002 Thomas Thurman
# thomas@thurman.org.uk
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have be able to view the GNU General Public License at 
# http://www.gnu.org/copyleft/gpl.html ; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

###########################################################

import random
import fcntl
import time
import config

def random_hex_string(length = 32):
	"Generates a string of random hex digits. Useful for nonces."

	result = ''

	# The easiest way to generate a hex digit is using the built-in
	# hex() function, which returns strings of the form "0x7"-- so
	# we take the third character.
	
	for n in range(0, length):
		result = result + hex(int(random.random()*16))[2]

	return result

################################################################

class mutex:
	"Provides simple semaphore-like mutual exclusion."
	file = None

	def __init__(self, filename):
		"Creates a lock based on |filename|."
		self.filename = config.backing_store_path(filename)

	def get(self):
		"""If nobody else is doing a get() on this filename,
		then this function gives us the lock and continues.
		Otherwise it blocks until the process with the current
		lock has drop()ped it."""
		
		self.file = open(self.filename, 'w')
		fcntl.flock(self.file.fileno(), fcntl.LOCK_EX)

	def drop(self):
		"""Relinquishes the lock so that other processes can
		have a go."""
		fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
		self.file.close()

################################################################

# We take the time once. Usually this would be better inside
# the next function, but since yarrow is designed to be run
# only briefly, we assume that the time won't change significantly
# during the run.
current_time = time.localtime(time.time())

def neat_date(seconds):
	"""Returns a string representation of |seconds|, which
	is the number of seconds since the epoch. The string will
	contain less information the further the date is in the past."""
	
	wanted = time.localtime(seconds)
	result = ""

	if wanted[0:3]!=current_time[0:3]:
		# if it's not today
		result = time.strftime("%e&nbsp;%b", wanted)

	if wanted[0]*12+wanted[1] > current_time[0]*12+current_time[1]-12:
		# only print the time if it's less than a year ago
		result = time.strftime("%l:%M%P&nbsp;",wanted) + result
	else:
		# otherwise tell them the year
		result = result + '&nbsp;' +str(wanted[0])
	return result
