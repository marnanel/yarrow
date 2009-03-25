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

class AlreadyExistsException(Exception):
	"Thrown when you attempt to create a user that already exists."
	pass

def hash_of(password):
	temp = md5.new()
	temp.update(password)
	return temp.hexdigest()

class user:
	"Represents one user of the system."
	def __init__(self, username):
		self.username = username
		self.metadata = {}
		self.last_sequences = {}
		self.version = 1

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

	def password_matches(self, another):
		"Returns true if the password that's set matches |password|."
		return hash_of(another) == self.password

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

	def set_password(self, new_password):
		self.password = hash_of(new_password)

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

	def password_matches(self, another):
		return 0 # nah!

	def save(self, must_not_exist=0):
		# no, go away
		pass

	def set_password(self, new_password):
		pass # quite literally!

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

def from_session_key(key):
	sessions = shelve.open(sessions_file)
	username = sessions.get(key)
	sessions.close()

	if username:
		return from_name(username)
	else:
		return None

def create(username, password):
	"""Creates a new user with username |username| and password |password|.
It must not already exist. Writes it out to persistant storage and
returns the newly-created user."""

	result = user(username)
	result.set_password(password)
	result.save(1)

	return result
