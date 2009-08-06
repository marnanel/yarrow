"Web front end for Yarrow"
  
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

################################################################

import config
import cgi
import rgtp
import cache
import time
import os
import string
import Cookie
import sys
import re
import user
import random
import common
import fly
import tasks

################################################################

__version__ = '1.3-beta'

################################################################

def maybe_environ(field):
	"""Checks the environment variable |field|, and returns
its value, or an empty string (rather than None) if it doesn't
exist."""
	if os.environ.has_key(field):
		return os.environ[field]
	else:
		return ''
	
################################################################

class yarrow:
	"A web interface for RGTP."

	def __init__(self):
		self.logging_in_status = 'unknown'
		self.form = cgi.FieldStorage()

		# Title of the HTML page.
		self.title = 'Reverse Gossip'

		# Name of the server.
		self.server = ''

		# What they want us to do.
		self.verb = ''

		# URL prefix for static content
		self.static_prefix = config.value('web', 'static-prefix')

		# Cookie time:
		if os.environ.has_key('HTTP_COOKIE'):
			# They've sent us some cookies; better read them.
			self.incoming_cookies = Cookie.SimpleCookie(os.environ['HTTP_COOKIE'])
		else:
			# No cookies. Start with a blank sheet.
			self.incoming_cookies = Cookie.SimpleCookie()

		# Set up a cookie list ready for sending new ones.
		self.outgoing_cookies = Cookie.SimpleCookie()

		# We don't know who you are or what you plan to do.
		self.user=None

		# No connection yet.
		self.connection=None

		# The collated index
		self.collater = None

	################################################################

	def try_again(self):
		"Prints a 'try again?' message, with the correct link."
		print '<a href="%s">Try again?</a>' % (self.uri(self.verb))

	def accept_user(self, user, add_cookies=0, cookie_expiry=0):
		"Sets the current user to be |user|, and optionally adds appropriate cookies."
		self.user = user
		if add_cookies:
			yarrow_session = 'yarrow-session'
			self.outgoing_cookies[yarrow_session] = user.session_key()
			self.outgoing_cookies[yarrow_session]['path'] = self.uri(None, self.server)
			if cookie_expiry:
				self.outgoing_cookies[yarrow_session]['expires'] = cookie_expiry

	def html_for_matched_itemid(self, matchobj):
		"Returns some HTML to link to the itemid given in 'matchobj'."
		itemid = matchobj.groups()[0]
		# FIXME: We should cache these somewhere. (Wrapper for "stat"?)
		try:
			return '<a href="%s" title="%s">%s</a>' % (
				self.uri(itemid),
				self.connection.stat(itemid)['subject'],
				itemid,
				)

		except rgtp.RGTPException, r:
			# Problem fetching the title. Hmm.
			return '<span title="%s">%s</span>' % (
				str(r),
				itemid,
				)
		
	def show_posting_box(self, sequence=None, subject='', textblock=None):
		"Prints the form for submissions of new postings."
		
		if self.item=='':
			post_link = 'post'
		else:
			post_link = self.item + '/post'

		print '<form action="'+self.uri(post_link)+'" method="post">'

		def suitable_grogname(y):
			"Picks a suitable grogname for the current user."
			if not y.user: return 'The Wombat'
			names = y.user.state(y.server, 'grogname', [])
			if names==[]:
				# Not sure what to do here.
				# Probably best to return ''.
				return ''
			else:
				# Don't you just love Python?
				return random.choice(names)

		# self.user must be defined in order to get here!
		print 'From <input type="text" name="from" value="'+\
			cgi.escape(suitable_grogname(self), 1)+\
			'" style="width: 99%"><br>'
		if subject!=None:
			print 'Subject <input type="text" name="subject" '+\
				'value="'+subject+'" style="width: 99%"><br>'
		print 'Message <textarea style="width: 99%" cols="50" '+\
			'class="textbox" rows="10" name="data">'
		if textblock:
			print textblock
		print '</textarea>'
		if sequence:
			print '<input type="hidden" name="sequence" value="%x">' % (sequence)
		print '<input type="submit" value=" Gossip "></form>'

	def connect(self):
		def meta_field(y, field):
			return y.user.state(y.server, field, None)

		if self.server!='':
			try:
				server = config.server_details(self.server)
			except Exception, e:
				self.logging_in_status = 'unknown_server'
				self.clear_session()
				return
			
			self.server_details = server
			self.connection = rgtp.fancy(server['host'],
						     server['port'],
						     self.log)

                        if self.verb in ['newbie']:
                                # Some verbs must not have a connection
                                # set up when processing them.
                                # (Rather an ugly hack, yes :( )
                                return

			if server['backdoor']:
				self.connection.backdoor()
				self.logging_in_status = 'ok'
				# XXX FIXME: Also log them into Yarrow here?
				return

			try:
				if self.user:
					self.connection.raise_access_level(
						None,
						meta_field(self, 'userid'),
						meta_field(self, 'secret'),
						1)
				else:
					self.connection.raise_access_level()
			except rgtp.RGTPException, r:
				self.logging_in_status = 'rgtp_error'
				self.logging_in_details = str(r)
				self.clear_session()
				return

			self.logging_in_status = 'ok'

	def print_headers(self):
		self.fly.set_cookies(self.outgoing_cookies)
		if self.outgoing_cookies.has_key('yarrow-session') and self.outgoing_cookies['yarrow-session']['expires']<0:
			# also remove the old-fashioned cookie
			self.outgoing_cookies['yarrow-session']['path']=self.uri(None,'')
			self.fly.set_cookies(self.outgoing_cookies)

		colour = '770000'

		print """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
"http://www.w3.org/TR/html4/loose.dtd">
<head><title>""" + self.title + """</title>
<style type="text/css"><!--
body {
  margin: 0px; font-size: 12px;
  font-family: Verdana, Arial, Helvetica, sans-serif; height: 8.5in;
  background-color: #FFFFFF; color: #000000; }
td { vertical-align: top; font-size: 10px; }
th { background-color: #"""+colour+"""; text-align: left; color: #FFFFFF;
  vertical-align: middle; font-size: 12px; }
.reply, .reply a { background-color: #"""+colour+"""; color: #FFFFFF; }
.reply td { text-align: right; }
.menu {
  position: absolute; left:auto; bottom:auto; top: 0; right: 0;
  background-color: #FFFFFF; width: 10%; z-index:1; color: #"""+colour+""";
  font-size:10px; padding-left: 1em; float: right; }
.menu { position: fixed; } /* Float it, if you can. */
.menu a,
 .menu a:visited { color: #"""+colour+"""; background-color: #FFFFFF; text-decoration: none; }
.menu h1 { font-size:10px; color: #000000; background-color: #FFFFFF; }
.content { position: absolute; width: 86%; height: auto;
  top: 0; left: 0; right: 90%; padding-left: 1em; background-color: #FFFFFF;
  color: #000000; text-align: left; z-index: 0; }
table.browse a, table.browse a:visited { text-decoration: none; color: #"""+colour+"""; }
table.browse a.related, table.browse a.related:visited {
   background-color: #"""+colour+"""; color: #FFFFFF; }
a { color: #"""+colour+"""; text-decoration: underline; }
a:visited { color: #000000; text-decoration: underline; }
a.uid { font-family: monospace; color: #FFFFFF; text-decoration: none; }
a.seq { font-style: italic; color: #FFFFFF; text-decoration: none; }
h1 { font-size: 15pt; }
h2 { font-size: 12pt; }
.invisible { display: none; }
ul.others { list-style-type: square; font-style: italic; }
--></style>
<link rel="shortcut icon" href="/favicon.ico">
</head><body><div class="content">

<p><b>To all users:</b> this is the new version of Yarrow, in public beta.  It has been tested for a few hours, but I would love to know (<a href="mailto:thomas@thurman.org.uk">thomas@thurman.org.uk</a>) whether this is working for you, and any bug reports you may have.  A copy of the old version is still running <a href="http://www.chiark.greenend.org.uk/ucgi/~tthurman/yarrow.cgi/groggs/browse">here</a> and <a href="http://groggs.extragalactic.info/cgi-bin/yarrow.cgi/groggs/browse">here</a>, in case this is unusable.</p>
"""

	def print_footers(self):
		# The sidebar and so on.

		self.maybe_print_logs()

		print '</div><div class="menu">'
		if self.server!='':
						
			print '<h1>%s</h1>' % (self.server)
			def serverlink(y, name, title, doc):

				keyelement = ''

				if y.accesskeys & 1:
					regexp = '_(.)'
					keypress = re.findall(regexp, title)[0]
					title = re.sub(regexp, '<u>'+keypress+'</u>', title)
					keyelement = 'accesskey="%s"' % (keypress.upper())
				
				print '<a href="%s"%s title="%s">%s</a><br/><br/>' % (
					y.uri(name),
					keyelement,
					doc,
					title)

			if self.connection:
				def usable(have, need):
					if need==-2:
						return True # always visible
					elif need==-1:
						return have==0
					else:
						return have>=need

				tasklist = [y for y in
					    [tasks.__dict__[x]()
					     for x in dir(tasks)
					     if x.endswith('_handler')]
					    if usable(self.connection.access_level, y.privilege())]

				tasklist.sort(key=lambda y: y.sortkey())
				for task in tasklist:
					title = task.title()
					if not title: continue
					link = task.__class__.__name__[:-8]
					if link=='browse': link=None # implicit
					serverlink(self, link, title, task.__doc__)

		print """<h1>yarrow</h1>
<a href="https://launchpad.net/yarrow/+download">v%s</a><br>
<a href="https://launchpad.net/yarrow/">about</a><br>
<a href="http://validator.w3.org/check/referer">valid&nbsp;HTML</a><br>
<a href="http://jigsaw.w3.org/css-validator/check/referer">valid&nbsp;CSS</a>
<br><br>""" % (__version__)

		print '</div></body></html>'

	def print_hop_list(self):
		# FIXME: Should probably be in tasks.handler_ancestor?
		"""Shows a list of all the currently unread items. A bit like
		readnew used to be, on Phoenix."""

		if not self.is_real_user():
			return

		if self.user and not self.user.last_sequences.has_key(self.server):
			self.user.last_sequences[self.server] = {} # Stop errors below...

		count = 1
		
		def accesselement(y, count):
			if (y.accesskeys & 2) and (count<10):
				return ' accesskey="%d"' % (count)
			else:
				return ''

		print '<hr>'

		collater = cache.index(self.server, self.connection)

		candidates = []
		for k in collater.keys():
			if self.user.last_sequences[self.server].get(k) < collater.sequences().get(k):
				candidates.append(k)

		class has_no_parent_in:
			# wouldn't be necessary if lambda could
			# see local scope in Python. bah.
			def __init__(self, candidates, items):
				self.items = items
				self.candidates = candidates
			def __call__(self, x):
				return not self.items[x].has_key('child') or not self.items[x]['child'] in self.candidates

		candidates = filter(
			has_no_parent_in(candidates, collater.items()),
			candidates)

		if (self.accesskeys & 2):
			print '<ol>'
		else:
			print '<ul>'

		for k in candidates[0:9]:
			seq = self.user.last_sequences[self.server].get(k)
			fragment = ''
			details = 'unread'

			if seq:
				fragment = '#after-%x' % (seq)
				details = 'updated'

			print '<li><b><a href="' +\
			    self.uri(k + fragment) + '"' + \
			    accesselement(self, count) + '>' +\
			    cgi.escape(collater.items()[k]['subject']) +\
			    '</a></b> ' +\
			    '(' + details + ')' +\
			    '</li>'

			count += 1

		if (self.accesskeys & 2):
			print '</ol>'
		else:
			print '</ul>'

		if len(candidates)>9:
			# "threads", not "items", because we hide
			# unread continuations.
			print '<p>(and others: there are %d unread threads)</p>' % (
				len(candidates))

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
				print '<b>'+cgi.escape(anything[1:])+'</b>'
			else:
				print '<i>'+cgi.escape(anything)+'</i>'
		print '</pre>'

	def clear_session(self):
		"Destroys our session cookie, for when you log out."
		yarrow_session = 'yarrow-session'
		self.outgoing_cookies[yarrow_session] = ""
		self.outgoing_cookies[yarrow_session]["path"] = self.uri(None, self.server)
		self.outgoing_cookies[yarrow_session]["expires"] = -500000

	def is_post_request(self):
		"Returns whether this was an HTTP POST request."
		return maybe_environ('REQUEST_METHOD')=='POST'

	def is_real_user(self):
		# FIXME this should go away now there are no more Visitors
		"Returns whether there's a real user logged in (not Visitor)."
		return self.user and self.user.username!='Visitor'

	def decide_tasks(self):
		def harvest(self, key):
			if self.form.has_key(key):
				return self.form[key].value
			else:
				return ''

      		# Some things we can just pick up from arguments.

		self.server = harvest(self, 'server')
		self.verb = harvest(self, 'verb')
		self.item = harvest(self, 'item')

		# Some we can take from the path.
	
		if os.environ.has_key('PATH_INFO'):
			path = os.environ['PATH_INFO']

			if path[-1]=='/':
				# Before we start, normalise URLs ending
				# with a slash. (I like to call it "tidy",
				# not "anal-retentitive".)

				corrected = '%s%s%s' % (
					os.environ['SERVER_NAME'],
					os.environ['SCRIPT_NAME'],
					path[:-1])

				if maybe_environ('QUERY_STRING')!='':
					corrected = '%s?%s' % (
						corrected,
						maybe_environ('QUERY_STRING'))

				self.fly.set_header('Status',
						    '301 Lose the slash!')
				self.fly.set_header('Location',
						    'http://'+corrected)
				self.fly.send_only_headers()
				self.verb = 'wombat' # so this is always set
				return

			path = string.split(path,'/')

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

		if self.incoming_cookies.has_key('yarrow-session'):
			self.user = user.from_session_key(self.incoming_cookies['yarrow-session'].value)
		else:
			self.user = None

		# If the "return" key is set in the form, it's an instruction
		# to set a cookie to show a later page where to return to.

		if self.form.has_key('return'):
			yarrow_return = 'yarrow-return'
			one_day = 24*60*60
			
			self.outgoing_cookies[yarrow_return] = self.form['return'].value
			self.outgoing_cookies[yarrow_return]['path'] = self.uri(None, self.server)
			self.outgoing_cookies[yarrow_return]['expires'] = one_day

		# Pick up config settings for this server.
		pickup = {
			'reformat': 1,
			'log': 0,
			'uidlink': 1,
			'readmyown': 1,
			'accesskeys': 3,
			}

		for k in pickup.keys():
			if self.user:
				self.__dict__[k] = self.user.state(self.server, k, pickup[k])
			else:
				self.__dict__[k] = pickup[k]

		if self.verb=='':
			if self.server=='':
				self.verb = 'serverlist'
			elif self.item!='':
				self.verb = 'read' # implicit for items
			else:
				self.verb = 'browse'

	def begin_tasks(self):
		"""Starts working on a task as soon as we know what it is,
before the HTML starts printing."""

		# Okay, find all the things they could ask for.

		tasklist = tasks.__dict__		

		if tasklist.has_key(self.logging_in_status+'_login'):
			# They did try to log in, but it failed.
			# Use a special verb handler to tell them so.
			self.verb_handler = tasklist[self.logging_in_status+'_login']()
		elif tasklist.has_key(self.verb+'_handler'):
			# Ah, we know about what they wanted to do.
			# Create them a handler to do it for them.
			self.verb_handler = tasklist[self.verb+'_handler']().allowed(self)
		else:
			# No idea about that. Use the handler that tells them
			# that we don't understand.
			self.verb_handler = tasks.unknown_command()

		# Lastly, the handler itself probably wants to do some amount
		# of setup. Call it.
		self.verb_handler.head(self)

	def finish_tasks(self):
		self.verb_handler.body(self)

	def uri(self, pagename=None, servername=None, set_return=0):
		"""Returns the URL prefix for accessing Yarrow.
		For example, if the user is using URLs such as

		http://rgtp.example.net/~fred/yarrow.cgi/groggs/browse

		then this function would return strings such as

		"/~fred/yarrow.cgi/groggs/browse"

		|servername| is the nickname of an RGTP server.

		If |servername| is None, the name of the current
		server is returned. In this case, |pagename| will
		be ignored. Otherwise, the prefix, plus a
		slash, plus the value of |servername| is returned.
		
		However, if |servername| is an empty string, only the bare
		prefix is returned (rather than the prefix plus a slash).

		Iff |pagename| is not None, another slash
		will be added, followed by the value of |pagename|.

		Iff |set_return| is true, "?return=CURRENT" will be
		appended finally, where CURRENT is the URI of the
		current page. This might cause problems with
		the URL if |pagename| already contains a "?", but there's
		no known condition where this happens; a workaround
		would be trivial, but we'll only implement it if it
		would be used."""
		
		script_address = maybe_environ('SCRIPT_NAME')

		if servername=='':
			return script_address
		else:
			if servername==None:
				servername = self.server

			result = '%s/%s' % (
				script_address,
				servername)

			if pagename:
				result += '/' + pagename

			if set_return and os.environ.has_key('PATH_INFO'):
				result += '?return=' + os.environ['PATH_INFO']

			return result

	def return_target(self):
		if self.incoming_cookies.has_key('yarrow-return'):
			return self.incoming_cookies['yarrow-return'].value
		else:
			return None

	def run_as_cgi(self):
		"Carry out the job of yarrow run as a CGI script."

		original_stdout = sys.stdout
		try:
			self.fly = sys.stdout = fly.webfly()

			self.decide_tasks()
			self.connect()
			self.begin_tasks()
			self.print_headers()
			self.finish_tasks()
			self.print_footers()

			self.fly.print_to(original_stdout,
					  'gzip' in maybe_environ('HTTP_ACCEPT_ENCODING'),
					  maybe_environ('HTTP_IF_NONE_MATCH'))
		except:
			# last-ditch error handler
			sys.stdout = original_stdout
			print "Content-Type: text/html"
			print
			print "<h1>Something went wrong there.</h1>"
			cgi.print_exception()
			try:
				self.maybe_print_logs()
			except:
				pass # Oh well.
			print '<p><b>Please send email to '+\
			      '<a href="mailto:thomas@thurman.org.uk">' +\
			      'thomas@thurman.org.uk</a>, '+\
			      'quoting the text above.</b> Thanks!</p>'

