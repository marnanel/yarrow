#!/usr/bin/python

import socket
import string
import md5
import binascii

class RGTPException (Exception):
	def __init__(self, name):
		self.name = name

	def __str__(self):
		return self.name

def inverted_bitstring(x):
	result = ""
	for i in range(len(x)):
		result = result + chr(255-ord(x[i]))
	return result

class stomach:
	done = 0
	stuff = []
	def __call__(self,a,b):
		self.eat(a,b)

	def eat(self,a,b):
		if a==-1:
			self.stuff.append(b)
		elif a==0:
			self.done = 1
		else:
			raise RGTPException("Wasn't expecting " + str(a) + " " + b)

class regu_handler(stomach):
	def __call__(self,a,b):
		if a==100:
			pass # probably best to ignore this
		elif a==482:
			raise RGTPException("Permission denied to create account: " + b)
		elif a==250:
			pass # good, that's what we want
		elif a==280:
			self.stuff.append(b)
		elif b=='' or b[0]==' ':
			self.eat(a,b[1:])

class base:
	"Basic RGTP handling."

	state=0
	outgoing=0
	incoming=0
	callback=0
	logging=0
	log=''

	def get_line(self):
		temp=""
		while len(temp)==0:
			temp = self.receive()
		numeric = int(temp[0:3])
		textual = temp[4:]

		if numeric==481:
			raise RGTPException("Timeout.")
		elif numeric==484:
			raise RGTPException("Server internal error: "+textual)
		elif numeric==500 or numeric==510 or numeric==511 or numeric==512 or numeric==582:
			raise RGTPException("Broken client.")
		elif numeric==484:
			raise RGTPException("Server internal error.")
		elif numeric==530 or numeric==531:
			raise RGTPException("Permission denied. (Try logging in with a privileged account?)")
		else:
			self.callback(numeric, textual)
		if numeric==250: # Magic value for continuations
			while temp!='.':
				temp = self.receive()
				if temp!='.':
					self.callback(-1, temp)
			self.callback(0, "")

	def __init__(self, host, port, callback):
		self.state = 0
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect((host, port))
		self.incoming = sock.makefile("r")
		self.outgoing = sock.makefile("w")
		self.callback = callback
		self.get_line()

	def receive(self):
		temp = string.rstrip(self.incoming.readline())
		if self.logging: self.log = self.log + "\n<" +temp
		return temp

	def send(self, message, callback):
		self.callback = callback
		self.outgoing.write(message + "\r\n")
		self.outgoing.flush()
		if self.logging: self.log = self.log + "\n>"+message
		self.get_line()

class fancy:
	"Encapsulated RGTP."

	base = 0
	access_level = 0

	def __init__(self, host, port, logging):
		class funky:
			access_level = 0
			def __call__(self,a,b):
				self.access_level = a-230
		froody = funky()
		self.base = base(host, port, froody)
		self.access_level = froody.access_level
		self.logging = logging
		self.log = ''

	def login(self, email, sharedsecret):
		class authorise:
			clientnonce = "8a0eb22b27cc2dd5373f8cd9657fe8ea"
			hash = md5.new()

			def __init__(self, base, email, sharedsecret):
				self.base = base
				self.email = email[0:16]
				# todo: pad with nuls if it's <16 bytes
				self.sharedsecret = sharedsecret
				self.done = 0

			def __call__(self,a,b):
				if a==333:
					self.hash.update(binascii.unhexlify(self.clientnonce))
					self.hash.update(binascii.unhexlify(b))
					self.hash.update(self.email)
					self.hash.update(inverted_bitstring(binascii.unhexlify(self.sharedsecret)))
					self.base.send("AUTH "+self.hash.hexdigest()+" "+self.clientnonce, self)
				elif a==133:
					pass # ummm...
				elif a==483:
					raise RGTPException("Authentication failed ("+b+")")
				elif a==130:
					pass # ignore this
				elif a>=230 and a<=233:
					self.base.access_level = a-230
					self.done = 1
				elif a==482 or a==483 or a==432 or a==433:
					raise RGTPException("Failed to log you in - " + b)
				else:
					raise RGTPException("Wasn't expecting " + str(a) + " " + b)

		towel = authorise(self.base, email, sharedsecret)
		self.base.send("USER "+email, towel)
		while not towel.done:
			self.base.get_line()

	def request_account(self, email):
		towel = regu_handler()
		self.base.send("REGU", towel)
		while not towel.done:
			self.base.get_line()
		if email!="":
			self.base.send("USER "+email, towel)
			print "Sending repeat"
			while not towel.done:
				self.base.get_line()
		return towel.stuff

	def motd(self):
		class funky:
			done = 0
			stuff = ''
			def __call__(self,a,b):
				if a==-1:
					self.stuff += b + "\n"
				elif a==0:
					self.done = 1

		froody = funky()
		self.base.send("MOTD", froody)
		while not froody.done:
			self.base.get_line()
		return string.split(froody.stuff, '\n')

	def index(self):
		class funky:
			result = []
			done = 0
			def __call__(self,a,b):
				if a==-1:
					self.result.append((string.strip(b[0:8]), string.strip(b[9:17]),
						string.strip(b[18:26]), string.strip(b[27:102]),
						b[103], string.strip(b[105:])))
				elif a==0:
					self.done = 1

		froody = funky()
		self.base.send("INDX", froody)
		while (not froody.done):
			self.base.get_line()
		return funky.result

	def logout(self):
		class funky: # generalise me!
			def __call__(self,a,b):
				if a!=280:
					raise "Not what I wanted"
		if self.access_level!=0:
			self.base.send("QUIT", funky())
			self.access_level = 0

	def __del__(self):
		self.logout()

	def item(self, id):
		class funky:
			result = []
			done = 0
			firstline = 0
			buffer = ''
			subject = ''

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

					if temp[0][0:5]=='Subject: ':
						self.subject = temp[0][10:]
						temp = temp[1:]

					if name=='':
						atpos = string.find(date, ' at ')
						if atpos!=-1:
							name = date[:atpos]
							date = date[atpos+4:]

					self.result.append((name, date, temp))

					self.buffer=''

			def __call__(self,a,b):
				if a==-1:
					if self.firstline:
						self.firstline = 0
						# should parse it, but...
						self.result.append(b)
						self.result.append(b)
					elif b!='' and b[0]=='^':
						self.put_buffer()
					else:
						self.buffer=self.buffer+b+"\n"
				elif a==0:
					self.done = 1
					self.put_buffer()
				elif a==410:
					raise "No such item"
				elif a==250:
					self.firstline = 1

		froody = funky()
		self.base.send("ITEM "+id, froody)
		while (not froody.done):
			self.base.get_line()
		return funky.result

