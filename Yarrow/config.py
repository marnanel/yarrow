#!/usr/bin/python
#
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

settings = ConfigParser.ConfigParser()
settings.read('/etc/yarrow.conf')

def value(section, option):
	return settings.get(section, option)

# FIXME: Peter Colledge asks that this also matches on
#    hostname -- if port==rgtp
#    hostname:port
def server_details(name):
	section = name+'-server'

	if not settings.has_section(section):
		raise Exception(self.server + ' is not a known server')

	address = string.split(value(section, 'address'), ':')
	if len(address)>1:
		port = int(address[1])
	else:
		port = 1431
	return {
		'host': address[0],
		'port': port,
		'description': value(section, 'description')}

def all_known_servers():
	result = {}

	for candidate in settings.sections():
		if candidate[-7:]=='-server':
			name = candidate[:-7]
			result[name] = server_details(name)

	return result
