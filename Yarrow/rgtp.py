"RGTP client library."

# Copyright (c) 2002-9 Thomas Thurman
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

import socket
import string
import md5
import binascii
import wrapping
import common

################################################################
#
# This module implements an RGTP client.
#
# It contains four parts:
#
# base:
#  a simple client which knows how to connect, and how to send
#  and receive data, but not much else.  This class defers
#  dealing with the actual data to...
#
# callbacks:
#  several classes to which the "base" class delegates dealing
#  with the actual data from various commands.
#  (Singleton instances of callbacks tend to be named "towel",
#  for some reason.)
#
# fancy:
#  a full-featured RGTP client constructed from "base" and
#  a few dozen callbacks.
#
# interpreted_index:
#  a class which can read an index in the form in which it
#  crosses the wire, and return useful subsets of the data
#  therein.
#
# FIXME: callbacks should be called "interpreters" or "drivers"
#  or "controllers" or something.
#
# FIXME: although callbacks are well-designed for reading
#  the data from the server, they are ill-equipped for sending
#  anything back.  This is necessary in several places, so
#  various approaches have evolved: some callbacks keep a copy
#  of "base" and write to it, some rely on "fancy" passing them
#  in multiple times.  Also:
#
# TODO: If callbacks were able to write to the server as
#  well as read from it, most or all of the methods in "fancy"
#  would be possible using only one line of code and a callback
#  class.  It might be possible just to have the callbacks
#  and be done with it.  One possible way this could be done is
#  to use continuations: the "callback" would yield an object of
#  class sending(<MESSAGE>), class receiving(<EXPECTED CODE>),
#  which would cause the obvious results, or of any other class,
#  which would be returned from the send() function.  This would
#  make everything much simpler and clearer.
#  It would also mean that almost everything in this module would
#  need to be recoded.
#
###########################################################

class RGTPException (Exception):
	"Houston, we have a problem."

	def __init__(self, name=''):
		self.name = name

	def __str__(self):
		return self.name

# And all the subclasses:

# FIXME: How about including HTTP equivalents as a field?

class RGTPTimeoutException(RGTPException):
	"Problem due to timeouts somewhere along the line."
	pass

class RGTPUpstreamException(RGTPException):
	"Problem with the RGTP server, as judged by us."
	pass

class RGTPServerException(RGTPException):
	"Problem with us, possibly as judged by the RGTP server."
	pass

class RGTPAuthException(RGTPException):
	"Authentication problems."
	pass

class AlreadyEditedError (RGTPException):
	"""Thrown after an attempt to modify an item
	which had been modified by someone else."""
	pass

class FullItemError (RGTPException):
	"Thrown after an attempt to add to a full item."
	pass

class UnacceptableContentError (RGTPException):
	"""Thrown if the server isn't happy with the text
we send. There are two public member fields: |problem| is
one of ['text','subject','grogname'], and |text| is the text
the server sent to complain."""

	def __init__(self, code, text):
		if code==423:
			self.problem = 'text'
		elif code==424:
			self.problem = 'subject'
		elif code==425:
			self.problem = 'grogname'
		else:
			raise 'unknown unacceptable content code: ' + code
			
		self.code = code
		self.text = text

###########################################################

class response:
	"One message from the server."

	def __init__(self, text, code=None):
		"Creates a response from a line of text received from the server."

		if code==None:
			try:
				self.numeric = int(text[0:3])
				self.textual = text[4:]
			except:
				self.numeric = -999
				self.textual = '(Weird bug finding:) ' +text
		else:
			self.numeric = code
			self.textual = text
		self.maybe_panic()

	def maybe_panic(self):
		if self.numeric==481:
			raise RGTPTimeoutException("Timeout: "+self.textual)
		elif self.numeric in (
			484,  # general rgtp server panic
			-999, # the panic code that yarrow assigns when
			#       the response is so malformed we can't get a
			#       code out of it
			):
			raise RGTPUpstreamException("Server internal error: "+self.textual)
		elif self.numeric in (
			500, # General mess-up
			510, # Unknown command
			511, # Wrong parameters
			512, # Line length problems
			582, # Dot-doubling problems
			):
			raise RGTPServerException("Broken client: "+self.textual)
		elif self.numeric in (530, 531):
			raise RGTPAuthException("Permission denied. (Try logging in with a privileged account?): "+self.textual)

	def code(self):
		return self.numeric

	def text(self):
		return self.textual

	def __str__(self):
		return str(self.numeric) + " " + self.textual

###########################################################

class callback:
	"""A class which knows how to deal with one aspect of RGTP."""
	# FIXME: "callback" is a crappy name.

	def __init__(self):
		# By default, returns the callback itself, so that it can be inspected.
		self.answer = self

	def __call__(self, message):
		"""Deals with an incoming RGTP message.
|message| is of type "response"."""
		pass

	def done(self):
		"""Returns 1 iff 'base' can throw this callback away now.
This will not be checked until __call__() has been called at least once."""
		return 1

	def result(self):
		"""Returns whatever the callback was supposed to find out."""
		return self.answer

###########################################################

class expect(callback):
	"""Callback that expects a message with a certain RGTP code number;
the callback finishes quietly if the first message has that number, and
throws an exception if it does not."""
	# FIXME: The expectation is always necessarily 2xx, and people
	# have to subclass this class if they want to throw custom exceptions
	# for unexpected results.  Perhaps we should allow a mapping between
	# error codes and exception classes to be passed in as an extra
	# parameter to __init__.
	def __init__(self, expectation):
		callback.__init__(self)
		self.desideratum = expectation

	def __call__(self, message):
		if message.code() != self.desideratum:
			# FIXME: This should be one of our own exception classes,
			# not a string
			raise "Expected %s, but got %s." % (
				str(self.desideratum),
				message,
				)

###########################################################

class multiline(callback):
	"""The ancestor of complex callbacks which deal with
RGTP transactions extending over multiple lines.  Not usable
in itself."""
	def __init__(self):
		callback.__init__(self)
		self.finished = 0

	def complete(self):
		self.finished = 1

	def done(self):
		return self.finished

###########################################################

class stomach(multiline):
	"""The ancestor of all callbacks which expect some
multi-line data and need it stored somewhere.  Perfectly
usable in itself."""
	def __init__(self):
		multiline.__init__(self)
		self.answer = []

	def __call__(self,message):
		self.eat(message)

	def eat(self,message):
		if message.code()==250:
			pass # data coming up-- good
		elif message.code()==-1:
			self.swallow(message.text())
		elif message.code()==0:
			self.complete()
		else:
			raise RGTPException("Wasn't expecting " + str(message))

	def swallow(self, data):
		self.answer.append(data)

###########################################################

class base:
	"Basic RGTP handling."

	def __init__(self, host, port, cback, logging=1, encoding='iso-8859-1'):
		self.logging=logging
		self.log=''
		self.state = 0
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect((host, port))
		self.incoming = sock.makefile("r")
		self.outgoing = sock.makefile("w")
		self.encoding = encoding
		self._get_line(cback)

	def _get_line(self, cback):
		looping = 1

		while looping:
			temp = ''

			# Read from the client until we get a response.
			while len(temp)==0:
				temp = self.receive()
				message = response(temp)
				cback(message)

			if message.code()==250: # Magic value for continuations
				while temp!='.':
					temp = self.receive()
					if temp!='.':
						cback(response(temp, -1))
				cback(response('', 0))

			# okay. Ask whether we should go round again.
			looping = not cback.done()

	def receive(self):
		temp = string.rstrip(self.incoming.readline())
		# FIXME: Removing this line makes it work.  Why?  It should be vital!
		#temp = temp.decode(self.encoding).encode('utf-8')
		if self.logging: self.log = self.log + "\n<" +temp
		return temp

	def raw_send(self, message):
		"Simply sends one line to the server."
		self.outgoing.write(message + "\r\n")
		self.outgoing.flush()
		if self.logging:
			self.log = self.log + "\n>"+message

	def send(self, message, cback):
		"Sends one line to the server, and waits for a response."
		self.raw_send(message.decode('utf-8').encode(self.encoding))
		self._get_line(cback)
		return cback.result()

###########################################################

class fancy:
	"Encapsulated RGTP."

	base = 0
	access_level = 0

	def __init__(self,
		     host='rgtp-serv.groggs.group.cam.ac.uk',
		     port=1431,
		     logging=0):

		class first_connect(callback):
			access_level = 0
			def __call__(self, message):
				self.access_level = message.code()-230

		towel = first_connect()
		self.base = base(host, port, towel, logging)
		self.access_level = towel.access_level

	def login(self, email, sharedsecret = None):

		class authorise(multiline):

			def __init__(self, base, email, sharedsecret):
				multiline.__init__(self)
				self.clientnonce = common.random_hex_string()
				self.hash = md5.new()
				self.base = base
				self.email = email[0:16]
				while len(self.email)<16:
					# pad with nuls if it's <16 bytes
					self.email += '\0'
				self.sharedsecret = sharedsecret

			def __call__(self, message):
				if message.code()==333:
					def inverted_bitstring(x):
						result = ""
						for i in range(len(x)):
							result = result + chr(255-ord(x[i]))
						return result
					self.hash.update(binascii.unhexlify(self.clientnonce))
					self.hash.update(binascii.unhexlify(message.text()))
					self.hash.update(self.email)
					self.hash.update(inverted_bitstring(binascii.unhexlify(self.sharedsecret)))
					self.base.send("AUTH "+self.hash.hexdigest()+" "+self.clientnonce, self)
				elif message.code()==133:
					pass # ummm...
				elif message.code() in [482, 483]:
					raise RGTPException("Authentication failed ("+message.text()+")")
				elif message.code()==130:
					pass # ignore this
				elif message.code()>=230 and message.code()<=233:
					self.answer = message.code()-230
					self.complete()
				elif message.code()==482 or message.code()==483 or message.code()==432 or message.code()==433:
					raise RGTPException("Failed to log you in - " + message.text())
				else:
					raise RGTPException("Wasn't expecting " + str(message))

		# FIXME: Should callbacks have access to the base object?
		# This one does; regu, in a very similar circumstance,
		# does not, and we have to call the second part for it.
		self.access_level = self.base.send(
			"USER "+email,
			authorise(self.base, email, sharedsecret))

	def request_account(self, email):
		class regu_handler(stomach):
			def __init__(self):
				stomach.__init__(self)

			def __call__(self, message):
				if message.code()==100:
					pass # probably best to ignore this
				elif message.code()==482 or message.code()==280:
					successful = message.code()==280
					self.answer = (successful, message.text())
				elif message.code()==250:
					pass # good, that's what we want
				elif message.text()=='' or message.text()[0]==' ':
					self.eat(response(message.text()[1:], message.code()))

		towel = regu_handler()
		self.base.send("REGU", towel)
		if email!=None:
			try:
				self.base.send("USER "+email, towel)
			except RGTPServerException, rse:
				return (0, str(rse))
		return towel.answer

	def motd(self):
		return self.base.send("MOTD", stomach())

	def index(self, since=None, since_is_date=0):
		class index_reader(multiline):
			def __init__(self):
				multiline.__init__(self)
				self.answer = []

			def __call__(self, message):
				if message.code()==-1:
					b = message.text()
					self.answer.append((string.strip(b[0:8]), string.strip(b[9:17]),
						string.strip(b[18:26]), string.strip(b[27:102]),
						b[103], string.strip(b[105:])))
				elif message.code()==0:
					self.complete()

		if since:
			if since_is_date:
				request = 'INDX %08x' % (since)
			else:
				request = 'INDX #%08x' % (since)
		else:
			request = 'INDX'

		return self.base.send(request, index_reader())

	def logout(self):
		if self.access_level != 0:
			self.base.send("QUIT", expect(280))
			self.access_level = 0

	def __del__(self):
		self.logout()

	def item(self, id):
		class item_reader(multiline):
			def __init__(self):
				multiline.__init__(self)
				self.answer = []
				self.firstline = 0
				self.buffer = ''
				self.subject = ''

			def put_buffer(self):
				if self.buffer!='':
					lines = string.split(self.buffer, '\n')
					grogname = ''
					author = ''
					date = ''

					# Firstly, there'll be "item" or "reply" lines.
					# (Perhaps we should complain if there aren't.)
					if lines[0][0:5]=='Item ':
						date = lines[0][19:]
						lines = lines[1:]
					elif lines[0][0:11]=='Reply from ':
						date = lines[0][11:]
 						lines = lines[1:]

					atpos = string.rfind(date, ' at ')
					if atpos != -1:
						author = date[:atpos]
						date = date[atpos+4:]

					# "From" introduces an explicit grogname.
					if lines[0][0:5]=='From ':
						grogname = lines[0][5:]
						lines = lines[1:]

					# If the server tells us a subject, ignore it;
					# we'll have other ways of finding that out.
					if lines[0][0:9]=='Subject: ':
						lines = lines[1:]

					# Right. If we don't know the grogname by now,
					# it might have been short enough to go into the
					# author field.
					if grogname=='':
						openbracket = string.rfind(author, '(')
						if openbracket!=-1 and author[-1]==')':
							# Ah, so it was.
							grogname = author[:openbracket-1]
							author = author[openbracket+1:-1]
						else:
							# Well, just give them the address again.
							grogname = author

					self.answer.append({'grogname': grogname,
						'date': date,
						'author': author,
						'message': lines,
						'sequence': self.sequence,
						'timestamp': self.timestamp})
					self.buffer=''

			def __call__(self, message):
				if message.code()==-1:
					text = message.text()
					if self.firstline:
						self.firstline = 0
						# should parse it, but...
						self.answer.append(text)

					elif text!='' and text[0]=='^' and text[1]!='^':
						self.put_buffer()
						if len(text)==18:
							self.sequence = int(text[1:9], 16)
							self.timestamp = int(text[10:18], 16)
					else:
						if text!='' and text[0] in ['^', '.']:
							text = text[1:]
						self.buffer=self.buffer+text+"\n"
				elif message.code()==0:
					self.put_buffer()
					self.complete()
				elif message.code()==410:
					raise "No such item"
				elif message.code()==250:
					self.firstline = 1

		return self.base.send("ITEM "+id, item_reader())

	def item_plain(self, id):
		"Returns the item with itemid |id|, without any interpretation."
		return self.base.send("ITEM "+id, stomach())

        def raise_access_level(self, target=None, user=None, password=None, tryGuest=0):
		# Set target==None to get as high as we can with current
		# credentials.
                if target==None or target > self.access_level:
			# If they want more than they already have...
                        if user!=None and user!='':
				# They have a username. Fine: use it.
                                self.login(user, password)
		                if target!=None and target > self.access_level:
					raise RGTPException(user + " doesn't have a high enough access level.")
                        else:
				# No username. Hmm, maybe we can try the "guest" trick.
                                if tryGuest and (target==None or target==1) and self.access_level==0:
                                        self.login("guest", 0)
                                else:
					if target!=None:
	                                        raise RGTPException("You need to log in for that.")

		# So, did it work?
                if target > self.access_level:
			raise RGTPException("Sorry: try logging in with a more privileged account.");

	def backdoor(self):
		"""Allows access to the test server's backdoor
		(gives editor powers for experimentation)"""
		for i in range(0, 3):
			self.base.send('DBUG', expect(200))
		self.login('yarrow@example.com', 0)

	def stat(self, id):
		class status_reader(callback):
			def __call__(self, message):
				if message.code()==211:
					self.answer = message.text()
				elif message.code()==410:
					raise RGTPException("Not available: "+message.text())
				else:
					raise RGTPException("Wasn't expecting " + str(message))

		def maybe_blank(thing):
			if thing=='        ':
				return None
			else:
				return thing

		def maybe_hex(thing):
			if thing==None:
				return None
			else:
				return int(thing, 16)

		r = self.base.send("STAT "+id, status_reader())

		return {'from': maybe_blank(r[0:8]),
			'to': maybe_blank(r[9:17]),
			'edited': maybe_hex(maybe_blank(r[18:26])),
			'replied': maybe_hex(maybe_blank(r[27:35])),
			'subject': r[36:] }

	def send_data(self, grogname, message, raw=False):
		class dumper(multiline):

			def __init__(self, name, data, base, raw):
                                multiline.__init__(self)
				self.name = name
				self.data = data
				self.base = base
				self.raw = raw

			def __call__(self, message):
				def dot_doubled(line):
					if line!='' and line[0]=='.':
						# Dot-doubling: if it already
						# begins with a dot, it needs
						# another.
						return '.' + line
					else:
						return line

				if message.code()==150:
					# The server says "go ahead".
					# So here goes!
					self.base.raw_send(
						dot_doubled(self.name))
					if raw:
						for line in self.data:
							self.base.raw_send(dot_doubled(line))
					else:
						for paragraph in self.data:
							for line in wrapping.wrap(paragraph):
								self.base.raw_send(dot_doubled(line))
					# All done!
					self.base.raw_send('.')
				elif message.code() in [423, 424, 425]:
					# server's not happy with
					# something we said
					raise UnacceptableContentError(
						message.code(),
						message.text())
				elif message.code()==350:
					self.complete()
				else:
					raise("Wasn't expecting " + str(message))

		self.base.send('DATA', dumper(grogname, message, self.base, raw))

	def post(self, item, subject):
		"""
If item is None, this is a NEWI.
If item is not None and subject is None, this is a REPL.
If item is not None and subject is not None, this is a CONT.

On success, returns a dictionary with keys "itemid" and "sequence".

Failure cases:
 Throws AlreadyEditedError if this item has been edited.
   (You should check for the item having been edited already
    yourself, as well; there are cases this function won't
    pick up (such as editing which doesn't cause continuation).
 Throws FullItemError if this item is full (so you must CONT).
 Throws UnacceptableContentError if the content is unacceptable
    (it could be a bad subject or grogname, or something to
    do with the text).
"""

		class item_generator(multiline):
			"Callback for post()."

			def __init__(self, itemid):
                                multiline.__init__(self)
				self.itemid = itemid
				self.sequence = None

			def __call__(self, message):
				if message.code()==120:
					# A new itemid for us.
					self.itemid = message.text()

				elif message.code()==122:
					# continuation information
					# (it'll go to 422, below)

					# Because we're so stateless
					# around here, we can throw
					# this information away. If anyone
					# wants to use this library for more
					# general purposes, I'll add code to
					# capture it.

					pass

				elif message.code()==220:
					# Success code, and sequence number.
					self.sequence = int(
						message.text()[:8],16)
					
					# woohoo! all done
					self.complete()
					
				elif message.code()==421:
					# it's overflowing!
					raise FullItemError()

				elif message.code()==422:
					# it's overflowed!
					raise AlreadyEditedError()

				elif message.code() in [423, 424, 425]:
					# server's not happy with
					# something we said
					raise UnacceptableContentError(
						message.code(),
						message.text())

				else:
					raise("Wasn't expecting " +
					      str(message))

		towel = item_generator(item)
		if item==None:
			self.base.send('NEWI '+subject, towel)
		else:
			try:
				self.base.send('REPL '+item, towel)
			except FullItemError, fie:
				if subject!=None:
					# ah, we don't need to return an error:
					# we were given a subject in case
					# this happened. Use it.
					towel = item_generator(item)
					self.base.send('CONT '+subject, towel)
				else:
					# So we don't know what to do about
					# full items. Let's hope the
					# caller does.
					raise fie

		# Looks like it all worked.
		return {"itemid": towel.itemid,
			"sequence": towel.sequence}

	def edit_log(self):
		class edit_log_reader(multiline):
			def __init__(self):
				multiline.__init__(self)
				self.state = 0
				self.answer = []

			def __call__(self, message):
				if message.code()==-1:
					if self.state==0:
						b = string.split(message.text())
						self.change = {}

						if b[0]=="Item":
							self.change['item'] = b[1]
							b=b[2:]
						elif b[0]=="Index":
							b=b[1:]
						else:
							raise RGTPException('Unexpected stuff in edit log')

						self.change['action'] = b[0]
						self.change['editor'] = b[2]
						self.change['date'] = string.join(b[4:9])
#						self.change['sequence'] = b[9][2:10]
						if len(b)>9:
							self.change['sequence'] = b[9]
						else:
							# Very old versions of IWJ's rgtp didn't
							# supply this.
							self.change['sequence'] = ''
					elif self.state==1:
						self.change['reason'] = message.text()
						self.answer.append(self.change)

					self.state = (self.state+1)%3

				elif message.code()==0:
					self.complete()

		return self.base.send("ELOG", edit_log_reader())

	def diff(self, itemid):
		"""
Returns the changes made by an editor to an item.
|itemid| may be None, in which case the index is diffed."""
		class diff_reader(multiline):
			# FIXME: this should be a subclass of stomach
			def __init__(self):
				multiline.__init__(self)
				self.state = 0
				self.answer = []

			def __call__(self, message):
				code = message.code()
				if code==-1:
					self.answer.append(message.text())
				elif code==0 or code==410:
					self.complete()

		if itemid:
			diff = 'DIFF '+itemid
		else:
			diff = 'DIFF'

		return self.base.send(diff, diff_reader())

	def literal(self, strings):
		"Sends a series of literal commands to the server. Ignores the results."
		# FIXME this is not used any more

		dummy = callback()

		for thing in strings:
                        if thing!='':
				self.base.send(thing, dummy)

	def udbm(self, command=''):
		command = ('UDBM '+command).strip()
		return self.base.send(command, stomach())

	def set_motd(self):
		"Sets the MOTD to the data you most recently sent."
		# FIXME: should maybe return the new sequence number.
		# not much use for it at present, though.
		self.base.send('MOTS', expect(220))

	def edit(self, itemid, content, digest, reason):
		"Edits an item."

		class edlk_callback(expect):
			def __init__(self):
				expect.__init__(self, 200)

			def __call__(self, message):
				if message.code()==411:
					raise RGTPException('Another editor is editing.  Please try again later.')
				else:
					expect.__call__(self, message)

		class edit_callback(stomach):
			def __init__(self):
				stomach.__init__(self)
				self.hash = md5.new()

			def swallow(self, data):
				self.hash.update(data)

			def complete(self):
				if self.hash.hexdigest()!=digest:
					raise RGTPException('The item was changed while you were editing it.')
				stomach.complete(self)

		class edcf_callback(expect):
			def __init__(self):
				expect.__init__(self, 220)

			def __call__(self, message):
				if message.code()==410:
					raise RGTPException('The item has vanished!')
				elif message.code() in [423, 424, 425]:
					# server's not happy with
					# something we said
					raise UnacceptableContentError(
						message.code(),
						message.text())
				else:
					expect.__call__(self, message)

		content = content.split('\n')
		while content and content[-1] == '': content = content[:-1]

		self.base.send('EDLK', edlk_callback())
		self.base.send('EDIT '+itemid, edit_callback())
		if content:
			self.send_data('', content, True)
		self.base.send('EDCF '+reason, edcf_callback())
		self.base.send('EDUL', expect(200))

################################################################

# need to add fields for:
# datestamp of last eat()
class interpreted_index:
	"""If you pass index lines into the eat() method in
the form in which they pass across the wire, this class will
interpret them, and offers many useful accessors for the data
therein."""

	def __init__(self):
		self.index = {}
		self.last_sequences = { 'all': -1 }
		self.version = 1
		self.c_line = None

	def eat(self, lines):
		for line in lines:

			sequence = int(line[0], 16)
			if sequence>self.last_sequences['all']:
				self.last_sequences['all'] = sequence

			if line[4] in ['I','R','C','F']:
				if not self.index.has_key(line[2]):
					self.index[line[2]] = {'date': 0,
							       'count': 0,
							       'subject': 'Unknown',
							       'live': 1 }
					self.last_sequences[line[2]] = -1

				if line[4]!='F' and sequence > self.last_sequences[line[2]]:
					self.last_sequences[line[2]] = sequence

				if line[4] in ['I','C']:
					self.index[line[2]]['subject'] = line[5]

				if self.index[line[2]]['date'] < int(line[1],16):
					self.index[line[2]]['date'] = int(line[1],16)
					self.index[line[2]]['from'] = line[3]

				if line[4]!='F' and sequence > self.last_sequences[line[2]]:
					self.last_sequences[line[2]] = sequence

				if line[4]=='C':
				    self.c_line = line

				if self.index[line[2]]['date'] < int(line[1],16):
					self.index[line[2]]['date'] = int(line[1],16)
					self.index[line[2]]['from'] = line[3]

				if line[4]=='F':
					self.index[line[2]]['live'] = 0
					self.index[line[2]]['parent'] = self.c_line[2]
					self.index[self.c_line[2]]['child'] = line[2]

				self.index[line[2]]['count'] = self.index[line[2]]['count'] + 1

			elif line[4]=='M':
				self.last_sequences['motd'] = sequence

	def items(self):
		# throw if version!=1?
		return self.index

	def sequences(self):
		return self.last_sequences

	def keys(self):
		def compare_dates(left, right, I = self.index):
			return cmp(I[left]['date'], I[right]['date'])

		temp = self.index.keys()
		temp.sort(compare_dates)
		temp.reverse()

		return temp
