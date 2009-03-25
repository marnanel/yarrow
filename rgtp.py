#!/usr/bin/python
#
#  rgtp.py - RGTP client library
#  v0.02
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

import socket
import string
import md5
import binascii

###########################################################

class RGTPException (Exception):
	"Houston, we have a problem."

	def __init__(self, name):
		self.name = name

	def __str__(self):
		return self.name

###########################################################

class response:
	"One message from the server."

	def __init__(self, text, code=None):
		"Creates a response from a line of text received from the server."

		if code==None:
			self.numeric = int(text[0:3])
			self.textual = text[4:]
		else:
			self.numeric = code
			self.textual = text
		self.maybe_panic()

	def maybe_panic(self):
		if self.numeric==481:
			raise RGTPException("Timeout.")
		elif self.numeric==484:
			raise RGTPException("Server internal error: "+self.textual)
		elif self.numeric==500 or self.numeric==510 or self.numeric==511 or self.numeric==512 or self.numeric==582:
			raise RGTPException("Broken client.")
		elif self.numeric==484:
			raise RGTPException("Server internal error.")
		elif self.numeric==530 or self.numeric==531:
			raise RGTPException("Permission denied. (Try logging in with a privileged account?)")

	def code(self):
		return self.numeric

	def text(self):
		return self.textual

	def __str__(self):
		return str(self.numeric) + " " + self.textual

###########################################################

class callback:
	def __call__(self, message):
		pass

	def done(self):
		return 1

###########################################################

class expect(callback):
	def __init__(self, expectation):
		self.desideratum = expectation

	def __call__(self, message):
		if message.code() != self.desideratum:
			raise "Expected " + str(self.desideratum) + " but got " + message

###########################################################

class multiline(callback):

	def __init__(self):
		self.finished = 0

	def complete(self):
		self.finished = 1

	def done(self):
		return self.finished

###########################################################

class stomach(multiline):
	def __init__(self):
		self.stuff = []

	def __call__(self,message):
		self.eat(message)

	def eat(self,message):
		if message.code()==250:
			pass # data coming up-- good
		elif message.code()==-1:
			self.stuff.append(message.text())
		elif message.code()==0:
			self.complete()
		else:
			raise RGTPException("Wasn't expecting " + str(message))

###########################################################

class base:
	"Basic RGTP handling."

	def __init__(self):
		self.state=0
		self.outgoing=0
		self.incoming=0
		self.cback=0
		self.logging=0
		self.log=''

	def __init__(self, host, port, cback, logging):
		self.logging=logging
		self.log=''
		self.state = 0
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect((host, port))
		self.incoming = sock.makefile("r")
		self.outgoing = sock.makefile("w")
		self.cback = cback
		self.get_line()

	def get_line(self):
		looping = 1

		while looping:
			temp = ''

			# Read from the client until we get a response.
			while len(temp)==0:
				temp = self.receive()
				message = response(temp)
				self.cback(message)

			if message.code()==250: # Magic value for continuations
				while temp!='.':
					temp = self.receive()
					if temp!='.':
						self.cback(response(temp, -1))
				self.cback(response('', 0))

			# okay. Ask whether we should go round again.
			looping = not self.cback.done()

	def receive(self):
		temp = string.rstrip(self.incoming.readline())
		if self.logging: print "\n<" + temp#self.log = self.log + "\n<" +temp
		return temp

	def send(self, message, cback):
		self.cback = cback
		self.outgoing.write(message + "\r\n")
		self.outgoing.flush()
		if self.logging: print "\n>"+message # self.log = self.log + "\n>"+message
		self.get_line()

###########################################################

class fancy:
	"Encapsulated RGTP."

	base = 0
	access_level = 0

	def __init__(self, host, port, logging):
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
				clientnonce = "8a0eb22b27cc2dd5373f8cd9657fe8ea"
				hash = md5.new()
				self.base = base
				self.email = email[0:16]
				# todo: pad with nuls if it's <16 bytes
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
				elif message.code()==483:
					raise RGTPException("Authentication failed ("+message.text()+")")
				elif message.code()==130:
					pass # ignore this
				elif message.code()>=230 and message.code()<=233:
					self.access_level = message.code()-230
					self.complete()
				elif message.code()==482 or message.code()==483 or message.code()==432 or message.code()==433:
					raise RGTPException("Failed to log you in - " + message.text())
				else:
					raise RGTPException("Wasn't expecting " + str(message))

		towel = authorise(self.base, email, sharedsecret)
		self.base.send("USER "+email, towel)
		self.access_level = towel.access_level

	def request_account(self, email):
		class regu_handler(stomach):

			def __call__(self, message):
				if message.code()==100:
					pass # probably best to ignore this
				elif message.code()==482:
					raise RGTPException("Permission denied to create account: " + message.text())
				elif message.code()==250:
					pass # good, that's what we want
				elif message.code()==280:
					self.stuff.append(message.text())
				elif message.text()=='' or message.text()[0]==' ':
					self.eat(response(message.text()[1:], message.code()))

		towel = regu_handler()
		self.base.send("REGU", towel)
		if email!='':
			self.base.send("USER "+email, towel)
		return towel.stuff

	def motd(self):
		towel = stomach()
		self.base.send("MOTD", towel)
		return towel.stuff

	def index(self):
		class index_reader(multiline):
			def __init__(self):
				self.result = []

			def __call__(self, message):
				if message.code()==-1:
					b = message.text()
					self.result.append((string.strip(b[0:8]), string.strip(b[9:17]),
						string.strip(b[18:26]), string.strip(b[27:102]),
						b[103], string.strip(b[105:])))
				elif message.code()==0:
					self.complete()

		towel = index_reader()
		self.base.send("INDX", towel)
		return towel.result

	def interpreted_index(self):
		index = {}
		for line in self.index():

			if line[4]=='I' or line[4]=='R' or line[4]=='C' or line[4]=='F':
				if not index.has_key(line[2]):
					index[line[2]] = {'date': 0, 'count': 0, 'subject': 'Unknown', 'live': 1 }

				if line[4]=='I' or line[4]=='C':
					index[line[2]]['subject'] = line[5]

				if index[line[2]]['date'] < int(line[1],16):
					index[line[2]]['date'] = int(line[1],16)
					index[line[2]]['from'] = line[3]

				if line[4]=='F':
					index[line[2]]['live'] = 0

				index[line[2]]['count'] = index[line[2]]['count'] + 1;

		return index


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
				self.result = []
				self.firstline = 0
				self.buffer = ''
				self.subject = ''

			def put_buffer(self):
				if self.buffer!='':
					temp = string.split(self.buffer, '\n')
					name = ''
					date = ''

					if temp[0][0:5]=='Item ':
						date = temp[0][19:]
						temp = temp[1:]
					elif temp[0][0:11]=='Reply from ':
						date = temp[0][11:]
 						temp = temp[1:]

					if temp[0][0:5]=='From ':
						name = temp[0][5:]
						temp = temp[1:]

					if temp[0][0:9]=='Subject: ':
						temp = temp[1:]

					if name=='':
						atpos = string.find(date, ' at ')
						if atpos!=-1:
							name = date[:atpos]
							date = date[atpos+4:]

					self.result.append((name, date, temp))

					self.buffer=''

			def __call__(self, message):
				if message.code()==-1:
					if self.firstline:
						self.firstline = 0
						# should parse it, but...
						self.result.append(message.text())
						self.result.append(message.text())
					elif message.text()!='' and message.text()[0]=='^':
						self.put_buffer()
					else:
						self.buffer=self.buffer+message.text()+"\n"
				elif message.code()==0:
					self.put_buffer()
					self.complete()
				elif message.code()==410:
					raise "No such item"
				elif message.code()==250:
					self.firstline = 1

		towel = item_reader()
		self.base.send("ITEM "+id, towel)
		return towel.result


        def raise_access_level(self, target, user=None, password=None):
                if target > self.access_level:
			# If they want more than they already have...
                        if user!=None:
				# They have a username. Fine: use it.
                                self.login(user, password)
		                if target > self.access_level:
					raise RGTPException(user + " doesn't have a high enough access level.")
                        else:
				# No username. Hmm, maybe we can try the "guest" trick.
                                if target==1 and self.access_level==0:
                                        self.login("guest", 0)
                                else:
                                        raise rgtp.RGTPException("You need to log in for that.")

		# So, did it work?
                if target > self.access_level:
			raise RGTPException("Sorry: try logging in with a more privileged account.");

	def stat(self, id):
		class status_reader(callback):
			access_level = 0
			def __call__(self, message):
				if message.code()==211:
					self.result = message.text()
				else:
					raise("Wasn't expecting " + str(message))

		def maybe_blank(thing):
			if thing=='        ':
				return None
			else:
				return thing

		towel = status_reader()
		self.base.send("STAT "+id, towel)
		r = towel.result
		return {'from': maybe_blank(r[0:8]), 'to': maybe_blank(r[9:17]), 'edited': maybe_blank(r[18:26]), 'replied': maybe_blank(r[27:35]), 'subject': r[36:] }

