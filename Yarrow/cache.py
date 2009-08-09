"Caching for RGTP indexes."

# FIXME for this: we should check that the data in the cache is consistent.
# At present it never times out.

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

import shelve
import rgtp
import common
import config

indexes_file = config.backing_store_path('indexes')

def index(name, rgtp_server):
	"""Returns an index for the RGTP server |name| (where
	|rgtp_server| is an object representing that server).
	If possible, uses and updates the cache on backing store."""
	
	mutex = common.mutex('indexes.lock')

	mutex.get()
	indexes = shelve.open(indexes_file)

	current = None

	if indexes.has_key(name):
		# AND the datestamp is recent
		try:
			current = indexes[name]

			if current.version<2:
				# too old
				# FIXME: we should get the version to check against
				# from the rgtp module, not hard-code it.
				current = None
			else:
				current.eat(rgtp_server.index(current.sequences()['all']+1))
		except:
			# didn't work; just reload
			current = None

	if not current:
		current = rgtp.interpreted_index()
		current.eat(rgtp_server.index())

	indexes[name] = current
	indexes.close()
	mutex.drop()

	return current
