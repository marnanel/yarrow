"Configuration mechanisms for Yarrow."

#  yarrow - (yet another retro reverse-ordered website?)
#  v0.40
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

import ConfigParser
import string
import os.path

# The line below beginning "baseconf" is modified by the installation script
# to point at your base config file for yarrow. If you need to put that
# somewhere else, modify this line yourself.
baseconf = '/service/website/rgtp.thurman.org.uk/conf/yarrow.conf'

settings = ConfigParser.ConfigParser()
settings.read(baseconf)

backing_store_dir = settings.get('general', 'backing-store')

def backing_store_path(filename):
	"""Returns the path to a file named |filename| that we can
	guarantee stays where it is between runs."""
	return os.path.join(backing_store_dir, filename)

def value(section, option):
	"""Returns a value from the system configuration file."""
	try:
		return settings.get(section, option)
	except:
		return None

def server_details(name):
	"""Returns a dictionary of configuration information for the server
	named |name|; |name| can either be a nickname (i.e. a paragraph name
	in yarrow.conf) or its hostname (as given in yarrow.conf)."""

	section = name+'-server'

	if not settings.has_section(section):
		# hmm, it doesn't exist.
		# Peter Colledge asked for this extended matching:

		found = 0
		for server in settings.sections():
			if server.endswith('-server') and settings.get(server, 'address')==name:
				section = server
				found = 1
		if not found:
			raise Exception(name + ' is not a known server')

	address = string.split(value(section, 'address'), ':')
	if len(address)>1:
		port = int(address[1])
	else:
		# Use IANA's default RGTP port
		port = 1431

	longdesc = value(section, 'longdesc')
	if longdesc == None:
		longdesc = ''

	return {
		'host': address[0],
		'port': port,
		'description': value(section, 'description'),
		'backdoor': value(section, 'backdoor'),
		'longdesc': longdesc,
		}

def all_known_servers():
	"Returns a dictionary mapping name to details for all known RGTP servers."
	result = {}

	for candidate in settings.sections():
		if candidate[-7:]=='-server':
			name = candidate[:-7]
			result[name] = server_details(name)

	return result
