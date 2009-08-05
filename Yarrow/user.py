"Handles management of users-- passwords, options and so on."

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
import md5
import common
import config

users_file = config.backing_store_path('users')
sessions_file = config.backing_store_path('sessions')

class user:
	"Represents one user of the system."
	def __init__(self, username):
		self.username = username
		self.metadata = {}
		self.last_sequences = {}
		self.version = 1
		# We no longer use the password field, so set it to '*'
		# so that new accounts won't be usable by older copies
		# of Yarrow.
		self.password = '*'

	def __str__(self):
		return self.username

	def set_state(self, server, field, value):
		if not self.metadata.has_key(server):
			self.metadata[server] = {}

		self.metadata[server][field] = value

	def clear_state(self, server, field):
		if not self.metadata.has_key(server):
			self.metadata[server] = {}

		if self.metadata[server].has_key(field):
			del self.metadata[server][field]

	def state(self, server, field, default):
		if self.metadata.has_key(server) and \
		  self.metadata[server].has_key(field):
			return self.metadata[server][field]
		else:
			return default

	def session_key(self):
		"Returns a session key that can later be passed to from_session_key() to retrieve this user."
		key = common.random_hex_string()
		mutex = common.mutex('sessions.lock')
		mutex.get()
		sessions = shelve.open(sessions_file)
		sessions[key] = self.username
		sessions.close()
		mutex.drop()
		return key

	def save(self, must_not_exist=0):
		mutex = common.mutex('users.lock')
		mutex.get()
		store = shelve.open(users_file)

		if must_not_exist and store.has_key(self.username):
			store.close()
			raise AlreadyExistsException()

		store[self.username] = self
		store.close()
		mutex.drop()

# XXX This should go away
class visitor(user):
	"Represents a casual user of the system whose name we don't know."
	def __init__(self):
		self.username = 'Visitor'
		self.metadata = {}
		self.last_sequences = {}

	def set_state(self, server, field, value):
		# nope. we're read-only
		pass

	def state(self, server, field, default):
		return default

	def save(self, must_not_exist=0):
		# no, go away
		pass

	def invent_new_password(self):
		pass
	
def from_name(username):
	"Returns a user with the given username. If none exists, returns None."
	if username=='Visitor':
		return visitor()
	else:
		users = shelve.open(users_file)
		result = users.get(username)
		users.close()
		return result

def from_userid_and_secret(userid, secret, server):
	"""Returns a user with the given userid and secret on the given server.
	If none exists, returns None."""
	if userid=='Visitor':
		return visitor()

	# This is enormously inefficient.
	# It's written this way to keep the existing structure.
	# We need to rethink the way we store user information.
	# At least it only happens when users log in.

	result = None
	users = shelve.open(users_file)
	for k in users.keys():
		u = users[k]
		if u.metadata.has_key(server) and u.metadata[server]['secret'].lower()==secret.lower():
			result = u
			break
	users.close()
	return result

def from_session_key(key):
	sessions = shelve.open(sessions_file)
	username = sessions.get(key)
	sessions.close()

	if username:
		return from_name(username)
	else:
		return None

def create(userid, secret, server):
	"""Creates a new user with a random username and no password, and
writes it out to backing storage."""

	result = user(common.random_hex_string())
	result.set_state(server, 'userid', userid)
	result.set_state(server, 'secret', secret)
	result.save(1)

	return result
