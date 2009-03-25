#!/usr/bin/python
#
#  yarrow - (yet another retro reverse-ordered website?)
#  v0.30
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

import cgi
import rgtp
import wrapping
import time
import os
import string
import Cookie
import sys
import re

if os.environ.has_key('SCRIPT_NAME'):
	prefix = os.environ['SCRIPT_NAME'] + '/'
else:
	prefix = '/'

# Prefix for linking to stuff that never changes. At present this is:
#   - the CSS
#   - reverse-gossip.gif
#   - favicon.ico
static_prefix = '/'

def linkify(text, item_prefix = None):
	"Adds hyperlinks to |text|. If you use this with cgi.escape(), call that first. |item_prefix| is what to add to GROGGS itemids; leave this as None if you don't want to linkify them."
	temp = text
	if item_prefix:
		temp = re.sub(r'\b([A-Za-z]\d{7})\b', r'<a href="'+item_prefix+r'/\1">\1</a>', temp)
	temp = re.sub('(http:[A-Za-z0-9_+~#/?=%.-]*)(?!<)', r'<a href="\1">\1</a>', temp)
	temp = re.sub('(ftp:[A-Za-z0-9_+~#/?=%.-]*)(?!<)', r'<a href="\1">\1</a>', temp)
	temp = re.sub('(gopher:[A-Za-z0-9_+~#/?=%.-]*)(?!<)', r'<a href="\1">\1</a>', temp)
	temp = re.sub('([A-Za-z0-9._+-]*@[A-Za-z0-9._+]+)', r'<a href="mailto:\1">\1</a>', temp)
	# I was considering allowing www.anything to be an http link, but that starts
	# interfering with the text when it's already in a link. Odd that links can't
	# nest, isn't it?
	return temp

def html_print(message, grogname, author, time, reformat, item_prefix=''):
	"Prints one of the sections of an item which contains one reply and the banner across the top."
	# First: the banner across the top...

	print '<table class="reply" width="100%"><tr><th rowspan="2">'
	# We don't linkify the grogname, because it's often just an email address.
	print cgi.escape(grogname)
	print '</th><td>'
	print cgi.escape(author)
	print '</td></tr><tr><td>'
	print cgi.escape(time)
	print '</td></tr></table>'

	# And now for some real content.

	for line in message:
		print linkify(cgi.escape(line), item_prefix)
		if reformat:
			if line=='':
				print '<br><br>'
			elif len(line)<40:
				# just a guess, but...
				print '<br>'
		else:
			# We're not reformatting, so just break at the ends of lines.
			print '<br>'

def all_known_servers():
	"Returns a list of all known servers. At present, each one is a 4-tuple: name, host, port, description."
	result = []
	list = open("servers.dat")
	while 1:
		stuff = list.readline()
		if not stuff:
                	break
		result.append(string.split(stuff, None, 3))
	list.close()
	return result

class yarrow:
	"A CGI interface for RGTP."

	form = cgi.FieldStorage()
	current_time = time.localtime(time.time())
	title = 'Reverse Gossip'
	server = ''
	verb = ''
	user = ''
	password = ''
	if os.environ.has_key('HTTP_COOKIE'):
		# They've sent us some cookies; better read them.
		incoming_cookies = Cookie.SimpleCookie(os.environ['HTTP_COOKIE'])
	else:
		# No cookies. Start with a blank sheet.
		incoming_cookies = Cookie.SimpleCookie()
	outgoing_cookies = Cookie.SimpleCookie()

	def neat_date(self, seconds):
		wanted = time.localtime(seconds)
		result = ""

		if wanted[0:3]!=self.current_time[0:3]:
			# if it's not today
			result = time.strftime("%d&nbsp;%b", wanted)

		if wanted[0]*12+wanted[1] > self.current_time[0]*12+self.current_time[1]-12:
			# only print the time if it's less than a year ago
			result = time.strftime("%I:%M&nbsp;%p&nbsp;",wanted) + result
		else:
			# otherwise tell them the year
			result = result + '&nbsp;' +str(wanted[0])
		return result

	def choose_a_server(self):
		print '<p>This is still being built. Don\'t expect anything to work.</p>'
		print '<h1>First off, choose yourself a server.</h1>'

		print '<table width="100%">'
		print '<tr><th class="index">Name</th>'
		print '<th class="index">Description</th>'
		print '<th class="index">Address</th></tr>'

		for stuff in all_known_servers():
			# URLs don't list port numbers where it's default
			if stuff[2]=='1431':
				listed_port = ''
			else:
				listed_port = ':'+stuff[2]

			print '<tr>'
			print '<td><a href="'+prefix+stuff[0]+'">'+stuff[0]+'</a></td>'
			print '<td>'+stuff[3]+'</td>'
			print '<td><i>rgtp://'+stuff[1]+listed_port+'</i></td>'
			print '</tr>'
	
		print '</table>'
	
		print '<h1>Interested in adding to these?</h1>'
		print '<p>You can <a href="/">download</a> and run your'
		print 'own RGTP server.'
		print 'If you know of any servers not listed above,'
		print 'please <a href="mailto:spurge@thurman.org.uk">'
		print 'let us know</a>.</p>'

	def login(self):
		print '<h1>' + self.server + ' login</h1>'
		print '<UL>'

		print '<LI><a href="'+prefix+self.server+'/motd/">Tell me more</a> about '+self.server+'.</LI>'
		print '<LI>I have an account on ' + self.server + ' already: <FORM ACTION="'+prefix+self.server+'/browse/" METHOD="POST"><table border align="center"><tr><td>My email address is</td><td><INPUT TYPE="text" NAME="user"></td></tr><tr><td>and my shared secret is</td><td><INPUT TYPE="password" NAME="password"></td></tr><tr><td>Remember my login<br>(does nothing atm)</td><td><INPUT TYPE="checkbox" CHECKED NAME="remember"></td></tr><tr><td colspan="2" align="right"><INPUT TYPE="submit" VALUE=" OK "></td></tr></table></FORM></LI>'
		print '<LI><A HREF="'+prefix+self.server+'/browse/">I\'d just like to browse</A>. (But that depends whether the server allows guest access.)</LI>'
		print '<LI><A HREF="'+prefix+self.server+'/newbie/">I\'d like to create a new account</A>.</LI>'
		print '</UL>'

	def logout(self):
		print '<h1>' + self.server + ' logout</h1>'
		print 'You are now logged out.'
	
	def browse(self):
		self.connection.raise_access_level(1, self.user, self.password)
		print '<table width="100%">'
		print '<tr><th class="index">On</th><th class="index">#</th><th class="index">Most recently by</th>'
		print '<th class="index">About</th></tr>'

		index = self.connection.interpreted_index()

		# and now we can display them. sort them by date.
		
		def compare_dates(left, right, I = index):
			return cmp(I[left]['date'], I[right]['date'])

		keys = index.keys()
		keys.sort(compare_dates)
		keys.reverse()

		for k in keys:
			line = index[k]
			print '<tr>'
			print '<td>'+self.neat_date(line['date'])+'</td>'
			print '<td><i>' + str(line['count']) + '</i></td>'
			print '<td>'
			if line['live']:
				print line['from']
			else:
				# Don't show "most recently by" on
				# posts that have been continued.
				print '<i>-- continued above</i>'
			print '</td>'
			print '<td class="subject">'
			if self.usenc:
				nc = '?nc=' + str(line['count'])
			else:
				nc = ''
			print '<a href="'+prefix+self.server+'/'+k+'/'+nc+'">'
			if not line['live']: print '<i>'
			print line['subject']
			if not line['live']: print '</i>'
			print '</a></td></tr>'
		print '<tr><td colspan="3" align="center">('
		print '<a href="'+prefix+self.server+'/post/">'
		print 'Post a new message</a> )</td></tr>'
		print '</table>'
	
	def serverlink(self, name, title):
		print '<a href="'+prefix+self.server+'/'+name+'/">'+title+'</a><br>'
	
	def motd(self):
		html_print(self.connection.motd()[1:], self.server+' message of the day', '', '', self.reformat, prefix+self.server)

	def show_posting_box(self, sequence=None, show_subject=1, textblock=None):
		if self.item=='':
			item_link = ''
		else:
			item_link = '/' + self.item

		print '<form action="'+prefix+self.server+item_link+'/post" method="post">'
		print 'From <input type="text" name="from" value="'+self.grogname+'" style="width: 99%"><br>'
		if show_subject:
			print 'Subject <input type="text" name="subject" value="" style="width: 99%"><br>'
		print 'Message <textarea style="width: 99%" cols="50" class="textbox" rows="10" name="data">'
		if textblock:
			print textblock
		print '</textarea>'
		if sequence:
			print '<input type="hidden" name="sequence" value="'+sequence+'">'
		print '<input type="submit" value=" Gossip "></form>'

	def post(self):
		self.connection.raise_access_level(2, self.user, self.password)
		if self.form.has_key('data'):

			submission_status = 0

			if self.form.has_key('from'):
				name = self.form['from'].value
			else:
				name = '' # just use a blank

			if self.form.has_key('subject'):
				subject = self.form['subject'].value
			else:
				subject = None

			if self.item!='':
				item = self.item
			else:
				item = None

			if self.form.has_key('sequence'):
				# They've requested some sanity checks:
				# the item hasn't been continued, and its reply number
				# matches a certain sequence number.
				currently = self.connection.stat(self.item)
				if currently['to'] or (self.form['sequence'].value != currently['replied']):
					submission_status = -1

			if submission_status==0: # Still OK to send stuff?
				self.connection.send_data(name, string.split(self.form['data'].value, '\r\n'))
				submission_status = self.connection.post(item, subject)

			if submission_status==-1:
				print '<h1>Collision</h1>'
				print '<p>Sorry, someone posted a reply in the time between'
				print 'when you read the item and when you submitted your'
				print 'reply. I suggest you go and read'
				print '<a href="'+prefix+self.server+'/'+item+'">what\'s'
				print 'changed</a> before you reply again.</p>'
				# Tell them what they said. IE has a nasty habit of
				# eating the contents of forms if you go back to them.
				print '<p>For reference, you said:<blockquote>'
				for line in string.split(self.form['data'].value,'\r\n'):
					print line + '<br>'
				print '</blockquote></p>'
			elif submission_status==1:
				print '<h1>That item\'s full</h1>'
				print '<p>You need to start a new item. Edit your text'
				print 'if needs be, and think of an appropriate new subject'
				print 'line.</p>'
 				self.show_posting_box(None, 1, self.form['data'].value)
			else:
				print '<h1>Added comment</h1>'
				print 'Your comment was added. You can view it'
				print '<a href="'+prefix+self.server+'/'+submission_status+'/">'
				print 'here</a>.'
		else:
			print '<h1>Post a new item</h1>'
			self.show_posting_box()

	def profile(self):
		def radio(object, name, value):
			"Prints HTML code for a radio button."
			if object.__dict__.has_key(name):
				currently = object.__dict__[name]
			else:
				currently = '0'

			if currently==value:
				checked = ' checked'
			else:
				checked = ''
			print '<input type="radio" name="'+name+'" value="'+str(value)+'"'+checked+'>'

		print '<h1>Your settings</h1>'

		print '<form action="'+prefix+self.server+'/browse/" method="post">'
		if self.grogname!='':
			example_name = self.grogname
		else:
			example_name = 'The Wombat'

		print '<h2>Grogname</h2>'
		print '<input type="text" name="grogname" value="'+example_name+'"'
		print 'style="width: 99%"><br>'
		print '<p>Your grogname is a short piece of text which identifies you. It\'s'
		print 'similar to a nameline on <a href="http://mono.org">Monochrome</a> or'
		print 'a title on <a href="http://ewtoo.org">talkers</a>. You always have'
		print 'the chance to set a grogname wherever you can use one, but here you'
		print 'get the chance to set a default one.</p>'

		print '<h2>Using <i>?nc</i></h2>'
		radio(self, 'usenc', 1)
		print 'Add <i>?nc=X</i> to'
		print 'the ends of URLs for items, where <i>X</i> is the number of'
		print 'comments-- so if your browser colours links according to whether'
		print 'you\'ve followed them, it will appear that you haven\'t visited'
		print 'items which have received new comments. (Adding the <i>?nc</i>'
		print 'to an item\'s URL makes no difference to the way the item is'
		print 'displayed.)<br>'
		radio(self, 'usenc', 0)
		print 'Don\'t add <i>?nc</i>'
		print 'to items-- always keep one URL for each item.<br>'

		print '<h2>Reformatting</h2>'
		radio(self, 'reformat', 1)
		print 'Attempt to format lines to be as wide as your screen.<br>'
		radio(self, 'reformat', 0)
		print 'Leave lines being'
		print '80 characters wide as they\'re received from the server, just as'
		print 'most clients display them.<br>'

		print '<h2>Logging</h2>'
		radio(self, 'log', 1)
		print 'Show what messages were passed between us and the RGTP server'
		print 'to generate each page. Note that this can make the index'
		print 'take impractically long to load.<br>'
		radio(self, 'log', 0)
		print 'Don\'t. (Unless you\'re hugely interested in'
		print '<a href="http://www.groggs.group.cam.ac.uk/protocol.txt">RGTP'
		print 'nargery</a>, this one is probably what you want.)<br>'

		print '<input type="submit" value=" OK ">'
		print '</form>'
	
	def newbie(self):
		print '<h1>New ' + self.server + ' account</h1>'

		if self.form.has_key('newbie'):
			# We have a name. Try to create an account with that name.
			result = self.connection.request_account(self.form['newbie'].value)

			if result[0]:
				print '<h2>Success!</h2>'
			else:
				print '<h2>Account creation failed</h2>'
			print '<p><i>' + result[1] + '</i></p>'
			if result[0]:
				print '<p>Check your email for a message from the'
				print self.server + ' server.</p>'
			print '<p>If you\'d like to contact a human to'
			print 'discuss this, the Editors\' email addresses are usually'
			print 'listed in <a href="'+prefix+self.server+'/motd/">the'
			print 'server\'s message of the day</a>.</p>'
		else:
			# they haven't given us a username. So we give them a form
			# to fill in. Firstly, get the warning text, by doing an
			# account request and then bailing before we give them a
			# name.
			warning = self.connection.request_account(None)
			print '<table align="center"><tr><td><img src="/exclamation" width="36" height="35" alt="/!\\"></td><td>'
			print '<b>Please read this before continuing:</b><br><br>'
			for line in warning:
				print cgi.escape(line) + '<br>'
			print '</td></tr><tr><td colspan="2" align="right">'
			print '<FORM ACTION="'+prefix+self.server+'/newbie/" METHOD="POST"><INPUT TYPE="text" NAME="newbie"> <INPUT TYPE="submit" VALUE=" Apply "></FORM>'
			print '</td></tr></table>'
	
	def connect(self):
		if self.server!='':
			for name in all_known_servers():
				if name[0]==self.server:
					return rgtp.fancy(name[1], int(name[2]), self.log)
			raise rgtp.RGTPException(self.server + ' is not a known server')

	def print_headers(self):
		print self.outgoing_cookies
		print
		print '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">'
		
		print '<HEAD><TITLE>' + self.title + '</TITLE>'
	
		print '<style type="text/css"><!--'
		print '@import "' + static_prefix + 'yarrow.css";'
		print '--></style>'
		print '<link rel="SHORTCUT ICON" href="' + static_prefix + 'favicon.ico">'
		print '</head>'
	
		print '<body>'

		print '<div class="status">'
		print '<img src="' + static_prefix + 'reverse-gossip.gif" height="64" width="294" alt="Reverse Gossip" align="right">'

		if self.server!='':
			print '<a href="'+prefix+'"><b>this is:</b></a> ' + self.server + '<br>'

			print '<a href="'+prefix+self.server+'/login/"><b>you are:</b></a>'
			if self.user=='':
				print '<i>guest</i><br>'
			else:
				print self.user + '<br>'

		print '<a href="'+prefix+self.server+'/profile/"><b>grogname:</b></a>'
		if self.grogname!='':
			print self.grogname+'<br>'
		else:
			print '<i>not set</i><br>'

		print '<a href="http://rgtp.thurman.org.uk/yarrow/"><b>client:</b></a>'
		print 'yarrow 0.30'

		print '</div>'

		print '<div class="menu">'
		if self.server!='':
			self.serverlink('browse','index')
			self.serverlink('post','post')
			self.serverlink('motd','status')
			print '<br>'
			self.serverlink('profile','settings')
			print '<br>'
			if self.user=='':
				self.serverlink('login','log&nbsp;in')
			else:
				self.serverlink('logout','log&nbsp;out')
		print '<br>'
		print '<a href="'+prefix+'yarrow-faq/browse/">help</a><br><br>'
		print '<a href="http://validator.w3.org/check/referer">valid&nbsp;HTML</a><br>'
		print '<a href="http://jigsaw.w3.org/css-validator/check/referer">valid&nbsp;CSS</a><br>'
		print '</div>'
		print '<div class="content">'
	
	def maybe_print_logs(self):
		if not self.connection or not self.connection.base.logging:
			return
		print '<h1>Log</h1><pre>'
		for anything in string.split(self.connection.base.log,'\n'):
			if not anything or anything=='':
				pass
			elif anything[0]=='<':
				print cgi.escape(anything[1:])
			elif anything[0]=='>':
				print '<b>' + cgi.escape(anything[1:]) + '</b>'
			else:
				print '<i>'+cgi.escape(anything)+'</i>'
		print '</pre>'

	def harvest(self, key):
		if self.form.has_key(key):
			return form[key].value
		else:
			return ''

	def cookiename(self, key):
		return self.server + "-" + key

	def clear_cookie(self, key):
		name = self.cookiename(key)
		self.outgoing_cookies[name] = ""
		self.outgoing_cookies[name]["path"] = prefix + self.server
		self.outgoing_cookies[name]["expires"] = -500000

	def harvest_with_cookies(self, key):

		# A note on the way we handle cookies in Yarrow:
		#
		# For any setting X we might want to pick up from a cookie,
		# if there's an HTTP field (get or put) named X, we use
		# its value and (as a side effect) set X as a cookie.
		# Otherwise, if there's a cookie named X, we use its value.
		#
		# Given all this, the only other place we need to set cookies
		# is in "logout", where we clear them.

		name = self.cookiename(key)

		if self.form.has_key(key):
			# There's an HTTP field with that name,
			# so use it.
			value = self.form[key].value

			# Also, tell the client about it so we can
			# use the value again later.
			self.outgoing_cookies[name] = value
			self.outgoing_cookies[name]['path'] = prefix + self.server
			self.outgoing_cookies[name]['expires'] = 500000
			self.outgoing_cookies[name]['version'] = 1
			return value
		else:
			# Maybe it's in the cookies we received?
			if self.incoming_cookies.has_key(name):
				# Ah, see-- the client had the answer.
				return self.incoming_cookies[name].value
			else:
				# No idea. Send them back an empty string.
				return ''

	def decide_tasks(self):
		# Some things we can just pick up from arguments.

		self.server = self.harvest('server')
		self.verb = self.harvest('verb')
		self.item = self.harvest('item')

		# Some we can take from the path.
	
		if os.environ.has_key('PATH_INFO'):
			path = string.split(os.environ['PATH_INFO'],'/')

			for thing in path:
				if thing=='':
					continue
				elif self.server=='':
					self.server=thing
				elif self.item=='' and len(thing)==8:
					self.item=thing
				elif self.verb=='':
					self.verb=thing
				else:
					raise rgtp.RGTPException("what's " + thing + " good for?")

		# Hmm, defaults...
	
		def safeint(x, default):
			"Turn a string into an integer, or return a default value if we can't."
			if x=='' or x==None:
				return default
			else:
				return int(x)

		if self.verb=='':
			if self.item=='':
				self.verb = 'login'
			else:
				self.verb = 'read'

		# Now, pick up the persistent things:
		self.user = self.harvest_with_cookies('user')
		self.password = string.join(string.split(self.harvest_with_cookies('password')),'')
		self.grogname = self.harvest_with_cookies('grogname')
		self.usenc = safeint(self.harvest_with_cookies('usenc'), 0)
		self.reformat = safeint(self.harvest_with_cookies('reformat'), 1)
		self.log = safeint(self.harvest_with_cookies('log'), 0)

	def begin_tasks(self):
		"Start working on a task as soon as we know what it is, before the HTML starts printing."
		if self.verb=='read':
			self.connection.raise_access_level(None, self.user, self.password)
			try:
				self.this_status = self.connection.stat(self.item)
				self.title = self.this_status['subject']
				self.this_item = self.connection.item(self.item)
			except rgtp.RGTPException, r:
				self.title = str(r)
				self.this_status = None
				self.this_item = None
		elif self.verb=='motd':
			self.title = self.server + ' message of the day'
		elif self.verb=='wombat':
			self.title = 'The wombat'
		elif self.verb=='wombat':
			self.title = 'Your profile'
		elif self.verb=='logout':
			self.clear_cookie("user")
			self.clear_cookie("password")
		elif self.verb=='post':
			self.title = 'Post a new item to ' + self.server
		elif self.verb=='browse':
			self.title = self.server + ' index'
	
	def finish_tasks(self):
		if self.server=='':
			self.choose_a_server()
		elif self.verb=='login':
			self.login()
		elif self.verb=='logout':
			self.logout()
		elif self.verb=='browse':
			self.browse()
		elif self.verb=='wombat':
			print '<h1>The wombat</h1>'
			print '<p>Mary had a little lamb.<br>'
			print 'They met in unarmed combat,<br>'
			print 'and (for the sake of rhyming verse)<br>'
			print 'it turned into a wombat.</p>'
		elif self.verb=='read':
			def possibly_link(self, title, key, anchor):
				"If we have a continuation in direction 'key', prints a link to it."
				target = self.this_status[key]
				if target:
					try:
						name = self.connection.stat(target)['subject']
						print '<p><i>(' + title
						print '<a href="' + prefix + self.server + '/' + target + anchor + '">' + name + '</a>)</i></p>'
					except rgtp.RGTPException:
						print '<p><i>('+title+' item '+target+', which is no longer available.)</i></p>'
			print '<h1>' + linkify(cgi.escape(self.title), prefix+self.server) + '</h1>'
			if self.this_item:
				possibly_link(self, 'Continued from', 'from', '#end')
				for i in self.this_item[2:]:
					html_print(i[3], i[0], i[1], i[2], self.reformat, prefix+self.server)
				possibly_link(self, 'Continued in', 'to', '')

				if self.connection.access_level > 1 and self.this_status['to']==None:
					print '<hr>'
					self.show_posting_box(self.this_status['replied'], 0)

			print '<hr><i>(Return to <a href="' + prefix + self.server + '/browse/">the ' + self.server + ' index</a>)</i>'
		elif self.verb=='motd':
			self.motd()
		elif self.verb=='newbie':
			self.newbie()
		elif self.verb=='post':
			self.post()
		elif self.verb=='profile':
			self.profile()
		else:
			print "Seems we haven't implemented "+self.verb+"."
	
	
print "Content-Type: text/html"

y = yarrow()
y.decide_tasks()

try:
	y.connection = y.connect()
	y.begin_tasks()
	y.print_headers()
	y.finish_tasks()
except:
	print
	print "<h1>Something went wrong there.</h1>"
	cgi.print_exception()
	try:
		y.maybe_print_logs()
	except:
		pass # Oh well.
	sys.exit(255)

y.maybe_print_logs()

print '<a name="end"></a></div></BODY></HTML>'

