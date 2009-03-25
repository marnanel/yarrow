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

def mailto(address, linking=0):
	"""Returns an HTML snippet containing a mailto link for
the given address. Correctly handles the GROGGS-specific special
cases of spqr1@cam and spqr@foo. (We assume that all RGTP servers
other than GROGGS use only the full network domain.)"""

	# _Just_ in case we have any addresses with &s in...
	address = cgi.escape(address)

	if not linking:
		return address # that was easy...

	atpos = address.find('@')

	if atpos==-1:
		# no @-sign!
		return address # only sensible answer, really

	domain = address[atpos+1:]
	suffix = ''

	if domain=='cam':
		# Generic Cambridge address
		suffix = '.ac.uk'
	elif domain.find('.')==-1:
		# Cambridge department or college or similar
		suffix = '.cam.ac.uk'

	# mild spam-trap:
	address = address.replace('@','&#64;').replace('.','&#46;')

	return '<a href="mailto:%s%s">%s</a>' % (address, suffix,
						 address)

################################################################

# FIXME: General fn to print "try again?" as a link to the current page. (use environ.)

################################################################
	
def linkify(y, text):
	"""Adds hyperlinks to |text|. Automatically calls cgi.escape()
	on the text for you."""

	temp = cgi.escape(text)
	temp = re.sub(r'\b([A-Za-z]\d{7})\b',
		      y.html_for_matched_itemid,
		      temp)
	temp = re.sub('(http:([A-Za-z0-9_+~#/?=%.,-]|&amp;)*)(?!<)',
		      r'<a href="\1">\1</a>',
		      temp)
	temp = re.sub('(ftp:([A-Za-z0-9_+~#/?=%.,-]|&amp;)*)(?!<)',
		      r'<a href="\1">\1</a>',
		      temp)
	temp = re.sub('(gopher:([A-Za-z0-9_+~#/?=%.,-]|&amp;)*)(?!<)',
		      r'<a href="\1">\1</a>',
		      temp)
	temp = re.sub('([A-Za-z0-9._+-]*@[A-Za-z0-9._+]+)',
		      r'<a href="mailto:\1">\1</a>',
		      temp)
	# I was considering allowing www.anything to be an http link,
	# but that starts interfering with the text when it's already
	# in a link. Odd that links can't nest, isn't it?

	return temp

################################################################

def html_print(message, grogname, author, time, y):
	"""Prints one of the sections of an item which contains
	one reply and the banner across the top."""

	# First: the banner across the top...

	if grogname:
		print """<table class="reply" width="100%%">
<tr><th rowspan="2">%s</th><td class="uid">%s</td></tr>
<tr><td>%s</td></tr></table>""" % (
		# We don't linkify the grogname, because it's often
		# just an email address.
		cgi.escape(grogname),
		mailto(author, y.uidlink),
		time,
		)

	# Get rid of useless whitespace...
	while len(message)!=0 and message[0]=='': message = message[1:]
	while len(message)!=0 and message[-1]=='': message = message[:-1]

	# And now for some real content.

	print '<p>'
	for line in message:
		print linkify(y, line)
		if y.reformat:
			if line=='':
				print '</p><p>'
		else:
			# We're not reformatting, so just
			# break at the ends of lines.
			print '<br>'
	print '</p>'
	
################################################################

def http_status_from_exception(e):
	"""Returns a properly-formatted Status: line for return
	in the CGI headers. The line will contain a HTTP status
	code as defined in RFC2616 section 10. It will no longer
	contain the actual text "Status: ", though."""
	n = '404'
	ec = e.__class__

	if ec is rgtp.RGTPTimeoutException:
		# 503: Service Unavailable
		# Note that this isn't 504 (Gateway Timeout)
		# since this is returned when the RGTP server
		# times US out, not when we time THEM out.
		n = '503'
	elif ec is rgtp.RGTPUpstreamException:
		# 502: Bad Gateway
		n = '502'
	elif ec is rgtp.RGTPServerException:
		# 500: Internal Server Error; our bad
		n = '500'
	elif ec is rgtp.RGTPAuthException:
		# You'd think this would be 403: Forbidden...
		# but actually it makes more sense for it
		# to be 200: OK, because people need to see the
		# "visitor" button, and the error code can make
		# intermediate agents hide the http body.
		# (In particular, it means you can't set any browse
		# page as a Freshmeat demo site.)
		n = '200'
	else:
		# no idea about this one.
		# Make it something generic.
		n = '500'

	return '%s %s' % (n, str(e))

################################################################

class read_handler:

	def head(self, y):

		try:
			# fixme: This stat is wasteful. We can pick all this
			# up from a[0].
			self.status = y.connection.stat(y.item)
			y.title = self.status['subject']
			self.item = y.connection.item(y.item)
		except rgtp.RGTPException, r:
			print http_status_from_exception(r)
			y.title = str(r)
			self.status = None
			self.item = None

	def body(self, y):

		def possibly_link(y, rh, title, key, anchor):
			"""If we have a continuation in direction 'key',
			prints a link to it."""
			target = rh.status[key]
			if target:
				try:
					name = y.connection.stat(target)['subject']
					print '<p><i>(%s <a href="%s/%s">%s</a>)</i></p>' % (
						title,
						y.url_prefix(),
						target + anchor,
						name)

				except rgtp.RGTPException:
					print '<p><i>(%s item %s, which is no longer available.)</i></p>' % (title, target)

		print '<h1>%s</h1>' % (linkify(y, y.title))

		if you_should_be_logged_in(y):
			return

		if self.item:
			possibly_link(y, self,
				      'Continued from', 'from', '#end')
			for i in self.item[1:]:
				print '<hr class="invisible"><a name="%x"></a>'%(
					i['sequence'])
				html_print(i['message'], i['grogname'],
					   i['author'],
					   time.strftime("%a %d %b %Y %I:%M:%S%P",
							 time.localtime(i['timestamp'])),
					   y)
				print '<a name="after-%x"></a>' % (
					i['sequence'])

			possibly_link(y, self, 'Continued in', 'to', '')

			print '<a name="end"></a>'

			if y.connection.access_level > 1 and self.status['to']==None:
				print '<hr>'
				y.show_posting_box(self.status['replied'],
						   None)

			print '<hr><i>(Return to <a href="%s/browse">the %s index</a>)</i>' % (
				y.url_prefix(), y.server)

		if y.user and not y.user.last_sequences.has_key(y.server):
			y.user.last_sequences[y.server] = {} # Stop errors below...

		if y.user and \
			self.status and \
			(not y.user.last_sequences[y.server].has_key(y.item) or \
				y.user.last_sequences[y.server][y.item] != self.status['replied']):
			# When they last read this entry, there was a
			# different number of replies. Update their record
			# with the new number they've seen.
			y.user.last_sequences[y.server][y.item] = self.status['replied']
			y.user.save()

################################################################

class motd_handler:
	def head(self, y):
		y.title = y.server + ' message of the day'

	def body(self, y):
		print '<h1>'+y.server+' message of the day</h1>'
		if y.form.has_key('data') and y.is_post_request() and y.connection.access_level > 2:
			self.set_it(y)
		else:
			self.get_it(y)

	def set_it(self, y):
		y.connection.send_data('yarrow', # discarded
				       string.split(y.form['data'].value, '\r\n'))
		y.connection.set_motd()
		print '<p>Okay, the message of the day is now changed.</p>'

	def get_it(self, y):
		# FIXME: a thought. yarrow could have its own motd method,
		# which updated the sequence number for when the user last
		# saw the motd as a side-effect, and did the [1:]
		# automatically.
		# (maybe also have a param "return None if the sequence
		# is <= N")

		motd = y.connection.motd()[1:]
		
		html_print(motd, None, None, None, y)

		# Editors get extra stuff:
		if y.connection.access_level > 2:
			print """
<hr>
<p>If you'd like to modify the message of the day,
please enter the new text into the box below.</p>
<form action="%s/motd" method="post">
<textarea style="width: 99%%" cols="50"
class="textbox" rows="10" name="data">""" % (
				y.url_prefix())
			for line in motd:
				print line
			print '</textarea>'
			print '<input type="submit" value=" Modify "></form>'


################################################################

def you_should_be_logged_in(y):
	"""Prints appropriate warnings if y requires you to be logged in
	and you're not. Returns whether we recommend they should be
	prevented from continuing."""

	result = 0

	if y.user:
		# They're logged into yarrow.

		who_they_are = y.user.state(y.server, 'userid', '')

		if not who_they_are:
			# ... but we have no details for them on this
			# server.

			if y.connection.access_level==0:
				print """<p>Sorry, this server doesn't
permit guest users. You'll have to <a href="%s/newbie">apply for
an account</a> if you want to use it.</p>""" % (
	y.url_prefix())

			if y.user.username!='Visitor':
				print """
<p><b>Already have a %s ID?</b>
<a href="%s/config">Set it up</a> in order to post.<br>
<b>Don't have a %s ID?</b>
<a href="%s/newbie">Apply for one!</a></p>""" % (
			    y.server,
			    y.url_prefix(),
			    y.server,
			    y.url_prefix(),
			    )

			if y.connection.access_level==0:
				# Can't go any further, then.
				result = 1
	else:
		# They're not logged in to yarrow.
		# Can we give them satisfaction anyway?
		if y.connection.access_level==0:
			# No. But at least we can point them
			# in the right direction.
			print """
<p>You're trying to view a page from %s, which
doesn't permit anonymous browsing.<br>Would you like
to try connecting as a guest?</p>

<form action="%s/browse" method="post"><p align="center">
<input type="hidden" name="visiting" value="1">
<input type="submit" value=" Yes, I'm just visiting. ">
</p></form>

<p>You'll need cookies enabled to continue from here.</p>
""" % (y.server, y.url_prefix())
			result = 1

		# Otherwise they have guest access anyway,
		# which is just about as good.

	if not y.is_real_user():
		print"""<p><b>Already have a yarrow account?</b>
<a href="%s/login">Log in</a> in order to save settings.<br>
<b>Don't have a yarrow account?</b>
<a href="%s/newbie">Set one up</a>-- it's easy!</p>""" % (
	 y.url_prefix('sys'),
	 y.url_prefix('sys'),
	 )	 

	return result

################################################################

class browse_handler:
	def head(self, y):
		try:
			y.collater = cache.index(y.server, y.connection)
			y.title = y.server + ' index'
		except rgtp.RGTPException, r:
			print http_status_from_exception(r)
			y.title = str(r)			

	def body(self, y):

		def we_should_show_motd(y, sequences):
			"Whether we should show the MOTD this time."
			whether = y.user.state(y.server, 'motd', 0)

			if whether=='always':
				return 1
			elif whether=='never':
				return 0
			else:
				# So we only show it if it's changed.

				if y.user.last_sequences[y.server].get('motd')==sequences.get('motd'):
					return 0
				elif not sequences.has_key('motd'):
					# Weird, but possible
					return 0
				else:
					y.user.last_sequences[y.server]['motd']=sequences['motd']
					y.user.save()
					return 1
		
		print '<h1>%s</h1>' % (y.server)

		if you_should_be_logged_in(y):
			return

		if not y.collater:
			print '<p>%s</p><p>(Try' % (
				y.title)
			print '<a href="%s/config">reconfiguring</a>?)</p>' % (
				y.url_prefix())
			return

		index = y.collater.items()
		sequences = y.collater.sequences()

		if y.user and not y.user.last_sequences.has_key(y.server):
			# Stop errors below...
			y.user.last_sequences[y.server] = {}

		if we_should_show_motd(y, sequences):
			html_print(y.connection.motd()[1:],
				   None,
				   '',
				   '',
				   y)

		# and now we can display them. sort them by date.

		# FIXME: would be nice to add some way of following
		# continuation chains through here.
		
		def compare_dates(left, right, I = index):
			return cmp(I[left]['date'], I[right]['date'])

		keys = index.keys()
		keys.sort(compare_dates)
		keys.reverse()

		sliceStart = 0
		sliceSize = 20
		if y.form.has_key('unsliced'):
			sliceSize = len(keys)

		if y.form.has_key('slice'):
			try:
				sliceSize = int(y.form['slice'].value)
			except:
				pass
				
		if y.form.has_key('skip'):
			try:
				sliceStart = int(y.form['skip'].value)
			except:
				pass
		
		keys = keys[sliceStart:sliceSize+sliceStart]

		# Work out family relationships for the JavaScript snippet.
		js_family = []
		scanned = {}

		for n in keys:
			if not n in scanned.keys():

				# Find the oldest ancestor.
				cursor = n
				while index[cursor].has_key('parent'):
					cursor = index[cursor]['parent']

				# OK, now find all its kids (that are on screen)

				family = [cursor]
				while index[cursor].has_key('child'):
					cursor = index[cursor]['child']
					family.append(cursor)
					scanned[cursor] = 1

				family = [x for x in family if x in keys]

				if len(family)!=1:
					js_family.append("'%s'" % (string.join(family,' ')))
		del scanned
		
		print """
<script><!--
var m = [""" + string.join(js_family,",\n") + """];
function b(i, c) { document.getElementById(i).setAttribute('class',c); }
function g(f, i, c) { for (var k in f) { if (f[k]!=i) b(f[k], c); } }
function s(i, c) { for (var j in m) { if (m[j].indexOf(i)!=-1) g(m[j].split(' '), i, c); } }
function r(i) { s(i.getAttribute('id'), 'related'); }
function u(i) { s(i.getAttribute('id'), ''); }
//-->
</script>
<table width="100%" class="browse">
<tr><th>On</th><th>#</th>
<th>Most recently by</th><th>About</th></tr>"""

		for k in keys:
			line = index[k]

			if y.is_real_user():
				if y.user.last_sequences[y.server].get(k)>=sequences.get(k):
					highlight = 0
				else:
					highlight = 1
			else:
				# No user information, so don't bother highlighting.
				highlight = 0

			if highlight and y.user.last_sequences[y.server].has_key(k):
				anchor = '#after-%x' % (
					y.user.last_sequences[y.server][k])
			else:
				anchor = ''

			if line['live']:
				most_recently_from = mailto(line['from'], y.uidlink)
			else:
				# Don't show "most recently by" on
				# posts that have been continued.
				most_recently_from = '-- continued above'

			print """
<tr>
<td>%s</td><td><i>%s</i></td><td class="uid">%s</td>
<td class="subject">%s<a id="%s"
onmouseover="r(this)" onmouseout="u(this)"
href="%s/%s%s">%s%s%s%s%s</a></td>
</tr>"""                      % (
                                common.neat_date(line['date']),
				str(line['count']), # always an int?
				most_recently_from,
				('', '&deg;')[highlight],
				k, y.url_prefix(), k, anchor,
				('<i>', '')[line['live']],
				('', '<b>')[highlight],
				line['subject'],
				('', '</b>')[highlight],
				('</i>', '')[line['live']],
				)

		print '<tr><td colspan="4" align="center">'

		if sliceStart+sliceSize < len(index):
			print '<a href="%s/browse?skip=%d">&lt;&lt; Earliest</a> |' % (
				y.url_prefix(),
				len(index)-sliceSize)
			
			print '<a href="%s/browse?skip=%d">&lt; Previous</a> |' % (
				y.url_prefix(),
				sliceStart+sliceSize)
		
		print 'Items %d-%d of %d' % (sliceStart+1,
					      sliceStart+len(keys),
					      len(index))

		if y.form.has_key('unsliced'):
			 print '| <a href="%s/browse">Most recent</a>' % (y.url_prefix())
		else:
			 print '| <a href="%s/browse?unsliced=1">All</a>' % (y.url_prefix())

		if sliceStart - sliceSize >= 0:
			if sliceStart==sliceSize:
				print '| <a href="%s/browse">Next &gt;</a>' % (
					y.url_prefix())
			else:
				print '| <a href="%s/browse?skip=%d">Next &gt;</a>' % (
					y.url_prefix(),
					sliceStart-sliceSize)
	
			print '| <a href="%s/browse">Newest &gt;&gt;</a>' % (
				y.url_prefix())
		
		print """
</td></tr>
<tr><td colspan="4" align="center">
( <a href="%s/post">Post a new message</a> )</td></tr>
</table>""" % (y.url_prefix())

################################################################

class wombat_handler:
	def head(self, y):
		y.title = 'The wombat'

	def body(self, y):
		print """<h1>The wombat</h1>
<p>Mary had a little lamb.<br>They met in unarmed combat,<br>
and (for the sake of rhyming verse)<br>it turned into a wombat.</p>"""

################################################################

class post_handler:
	"Handles both creating new items and replying to existing ones."

	def head(self, y):
		y.title = 'Post to %s' % (y.server)

	def body(self, y):
		if y.form.has_key('data'):
			self.submit(y)
		else:
			self.form(y)

	def submit(self, y):
		if y.form.has_key('from'):
			name = y.form['from'].value
		else:
			name = '' # just use a blank

		if y.form.has_key('subject'):
			subject = y.form['subject'].value
		else:
			subject = None

		if y.item!='':
			item = y.item
		else:
			item = None

		if (not subject) and (not item):
			print '<h1>You must give a subject</h1>'
			print '<p>You cannot post an item without a subject.'
			print 'Please try again.</p>'
			y.show_posting_box(None,
					   '',
					   y.form['data'].value)
			return

		try:
			if y.form.has_key('sequence'):
				# They've requested some sanity checks:
				# the item hasn't been continued, and
				# its reply number matches a certain sequence number.
				currently = y.connection.stat(y.item)
				if currently['to'] or \
				   (int(y.form['sequence'].value,16) !=
				    currently['replied']):
					# Then it's been edited.
					raise rgtp.AlreadyEditedError()

			y.connection.send_data(name,
					       string.split(y.form['data'].value,
							    '\r\n'))
			details = y.connection.post(item, subject)

			# Success! Work out the URL of the new posting.
			print '<h1>Added gossip</h1>'
			print 'Your gossip was added. You can view it'
			print '<a href="%s/%s#%x">here</a>.' % (
				y.url_prefix(),
				details['itemid'],
				details['sequence'])

			if y.readmyown:
				# We've read our own comments; update the
				# "most recent sequence" number of this item
				# to show so.

				y.user.last_sequences[y.server][details['itemid']]=details['sequence']
				y.user.save()

		except rgtp.AlreadyEditedError:
			# Nope, someone's been there before us.
			# We should tell them what they said.
			# (IE has a nasty habit of eating the
			# contents of forms if you go back to them.)
			print """
<h1>Collision</h1>
<p>Sorry, someone posted a reply in the time between when you read the item
and when you submitted your reply. I suggest you go and read
<a href="%s/%s">what's changed</a> before you reply again.</p>
<p>For reference, you said:<blockquote>""" % \
	(y.url_prefix(), item)
			for line in string.split(y.form['data'].value,'\r\n'):
				print line + '<br>'
			print '</blockquote></p>'

		except rgtp.FullItemError:
			print '<h1>That item\'s full</h1>'
			print '<p>You need to start a new item. Edit your text'
			print 'if needs be, and think of an appropriate new subject'
			print 'line.</p>'
			y.show_posting_box(None, '', y.form['data'].value)

		except rgtp.UnacceptableContentError, uce:
			print """
<h1>%s</h1>
<p>The server isn't happy with %s. It says:</p><blockquote>%s</blockquote>
<p>Please fix the problem and try again.</p>""" % (
				uce.text,
				{
				'text': 'the text of your posting',
				'subject': 'the subject of your posting',
				'grogname': 'your grogname',
				} [uce.problem],
				uce.text);

			y.show_posting_box(None,
					   subject,
					   y.form['data'].value)

	def form(self, y):
		print '<h1>Post a new item</h1>'
		y.show_posting_box()

################################################################

class editlog_handler:
	def head(self, y):
		y.title = y.server + ' edit log'

	def body(self, y):
		if you_should_be_logged_in(y):
			return

		print """
<h1>Edit log</h1>
<p>Only editors have the power to change the entries that
other users have made on an RGTP server. When they do edit
something, it shows up here so that everyone can know that
a change has been made. Editors usually also add a note to
the item itself, to explain.</p>
<table width="100%">
<tr>
<th>Item</th>
<th>Date</th>
<th>Action</th>
<th>Editor</th>
<th>Reason</th>
</tr>"""

		edits = y.connection.edit_log()
		edits.reverse()

		for thing in edits:
			print '<tr>'
			if thing.has_key('item'):
				print '<td>'
				if thing['action']=='withdrawn':
					print thing['item']
				else:
					print linkify(y, thing['item'])
				print '</td>'
			else:
				print '<td><a href="%s/browse">' % (
					y.url_prefix())
				print '<i>index</i></a></td>'
			print '<td>'+thing['date']+'</td>'
			print '<td>'+thing['action']+'</td>'
			print '<td>'+thing['editor']+'</td>'
			print '<td>'+linkify(y, thing['reason'])+'</td>'
			print '</tr>'
		print '</table>'

################################################################

class config_handler:
	def head(self, y):
		y.title = 'How to access %s' % (y.server)

	def body(self, y):
		if not y.user:
			print '<p>Sorry, you can\'t set the options for'
			print 'individual servers unless you'
			print '<a href="%s/login">log in to' % (
				y.url_prefix('sys'))
			print 'yarrow</a>.</p>'
			return

		if y.form.has_key("yes"):
			self.submit(y)
		else:
			self.form(y)

	def form(self, y):
		def meta_field(y, field):
			result = y.user.state(y.server, field, '')
			if result==None:
				return ''
			else:
				return result

		print '<h1>How to access '+y.server+'</h1>'

		print '<h2>Logging in</h2>'
		print '<form action="'+y.url_prefix()+'/config" method="post">'
		print '<p>Firstly, please give a user-ID and shared-secret to use'
		print 'on this server. This is'
		print 'not the same thing as the username and password you used'
		print 'to log into yarrow; you should have received an email'
		print 'from the '+y.server+' editors telling you what your'
		print 'shared-secret is.</p>'
		print '<table>'
		print '<tr><td>User-ID:</td>'
		print '<td><INPUT TYPE="text" NAME="userid" value="%s"></td></tr>' % (meta_field(y, 'userid'))
		print '<tr><td>Shared-secret:</td>'
		print '<td><INPUT TYPE="text" NAME="secret" value="%s"></td></tr>' % (meta_field(y, 'secret'))
		print '</table>'
		print '<p>If you\'ve never received email from the editors,'
		print 'and you\'d like to be able to post to this server,'
		print 'you probably need to <a href="'+y.url_prefix()+'/newbie">register'
		print 'on it</a>. But if this server allows guest access, and'
		print 'all you want to do is read, you may simply leave the'
		print 'boxes above blank, and yarrow will log you in as a guest.</p>'
		print '</table>'

		print '<h2>Grogname</h2>'
		print '<p>Your grogname is a short piece of text which identifies you. It\'s'
		print 'similar to a nameline on <a href="http://mono.org">Monochrome</a> or'
		print 'a title on <a href="http://ewtoo.org">talkers</a>. You always have'
		print 'the chance to set a grogname wherever you can use one, but here you'
		print 'get the chance to set a default one.</p>'
		print '<p>If you list more than one (on separate lines), yarrow will'
		print 'pick a random one for you each time.</p>'
		print '<textarea cols="75" rows="5" name="grogname">'

		grognames = y.user.state(y.server, 'grogname', '')
		if grognames:
			for name in grognames:
				print '%s' % (name)
		else:
			print 'The Wombat'
		print '</textarea>'

		print '<h2>Reformatting</h2>'
		print '<p>If you like, yarrow can attempt to reformat the text received'
		print 'from the server so that it fills the width of your screen.'
		print 'Otherwise, the text will be displayed just as the server'
		print 'sends it.</p>'

		if meta_field(y, 'reformat')==1:
			reformatting_checked = ' checked'
		else:
			reformatting_checked = ''

		print '<p><input type="checkbox" name="reformat"%s> Reformat text.</p>' % (
			reformatting_checked)

		always_checked = updated_checked = never_checked = ''
		motd_status = meta_field(y, 'motd')
		if motd_status=='always':
			always_checked = ' checked'
		elif motd_status=='never':
			never_checked = ' checked'
		else:
			updated_checked = ' checked'

		print """<h2>Message of the Day</h2>
<p>Should yarrow show the message of the day on the index page?
(You can always see it by clicking the "status" link in the sidebar, too.)</p>

<p><input type="radio" name="motd" value="always"%s>Always show the MOTD.<br>
<input type="radio" name="motd" value="updated"%s>Only show the MOTD when
it's been updated.<br>
<input type="radio" name="motd" value="never"%s>Never show
the MOTD.</p>""" % (
	always_checked,
	updated_checked,
	never_checked,
	)
                print '<h2>Logging</h2>'
		if meta_field(y, 'log')==1:
			logging_checked = ' checked'
		else:
			logging_checked = ''

		print """<p>Show what messages were passed between us and the RGTP server
to generate each page. Unless you're hugely interested in
<a href="http://www.groggs.group.cam.ac.uk/groggs/protocol.txt">RGTP
nargery</a>, you probably don't want this turned on.</p>

<p><input type="checkbox" name="log"%s> Show RGTP logs.</p>
""" % (
	logging_checked)


		checked = ''
	        if meta_field(y, 'uidlink')!=0:
			checked = ' checked'

		print '<h2>Linking userids</h2>'
		print '<p>Yarrow can turn userids into hyperlinks; this is mostly useful,'
		print 'but with some kinds of browser it just gets annoying.</p>'
		print '<p><input type="checkbox" name="uidlink"%s>' % (checked)
		print 'Linkify userids.</p>'
		
		checked = ''
	        if meta_field(y, 'readmyown')!=0:
			checked = ' checked'

		print '<h2>Marking your own gossip as unread</h2>'
		print '<p>When you post to this server, do you want your own contributions'
		print 'to be marked as read as soon as you post them? If you leave this'
		print 'turned off, they will stay unread until you actually read them,'
		print 'just like contributions from anyone else.</p>'
		print '<p><input type="checkbox" name="readmyown"%s>' % (checked)
		print 'Mark that I\'ve read anything I post.</p>'
		
                print '<input type="submit" value=" OK ">'
		print '<input type="hidden" name="yes" value="y">'
		print '</form>'

	def submit(self, y):
		def put_meta_field(y, field, value):
			y.user.set_state(y.server, field, value)

		if y.form.has_key('userid'):
			userid = y.form['userid'].value
		else:
			userid = None

		# Remove spaces. (Maybe an RE would have been prettier.)
		if y.form.has_key('secret'):
			secret = string.join(string.split(y.form['secret'].value),'')
		else:
			secret = ''

		# Check for its not being a hex number.
		if not re.search('^[0-9A-Fa-f]*$', secret):
			print '<h1>Invalid secret</h1>'
			print '<p>Sorry, the shared-secret you gave wasn\'t valid.'
			print 'Secrets may contain only the digits 0 to 9,'
			print 'the letters A to F, and spaces. Case doesn\'t matter.'
			print 'If you copied the secret from an email, double-check'
			print 'that it was copied correctly.'
			print '<a href="%s/config">Try again?</a></p>' % (y.url_prefix())
			return

		if len(secret)%2==1:
			print '<h1>Invalid secret</h1>'
			print '<p>Sorry, the shared-secret you gave wasn\'t valid.'
			print 'Secrets must contain an even number of letters or numbers;'
			print 'yours had %d, which is very odd.' % (len(secret))
			print '<a href="%s/config">Try again?</a></p>' % (y.url_prefix())
			return

		# Right. Before we can treat this as valid, we must attempt to log in
		# using it, and see what happens. (Since this is separate from the
		# main RGTP session, we don't log it.) [FIXME: If we did, would it
		# work anyway? Should it? Find out.]

		if userid:
			test_connection = rgtp.fancy(y.server_details['host'],
				y.server_details['port'], 0)
			try:
				# We need at least a 1.
				test_connection.raise_access_level(1, userid, secret)

				put_meta_field(y, 'userid', userid)
				put_meta_field(y, 'secret', secret)

				print '<h1>Success!</h1>'
				print '<p>Thank you. You now have'
				print ['no','read-only','normal read and append','full editor'][test_connection.access_level]
				print 'access to %s.</p>' % (y.server)
				test_connection.logout()
			except rgtp.RGTPException:
				print '<h1>Authentication failure</h1>'
				print '<p>That doesn\'t appear to be a registered shared-secret'
				print 'on %s. <a href="%s/config">Try again?</a></p>' % (y.server, y.url_prefix())
				return
		else:
			put_meta_field(y, 'userid', userid)
			put_meta_field(y, 'secret', secret)
		
		grognames = []
		# [] is also what they get if they've specified no grognames.

		if y.form.has_key('grogname'):
			original = string.split(y.form['grogname'].value,
						'\r\n')

			# Now weed out the bad ones: too long, say, or blank.
			for name in original:
				if len(name)>75:
					print '<p>'+name
					print ' is too long to be a grogname. Ignored.</p>'
				elif name!='':
					grognames.append(name)

		put_meta_field(y, 'grogname', grognames)

		if y.form.has_key('reformat') and y.form['reformat'].value=='on':
			put_meta_field(y, 'reformat', 1)
		else:
			put_meta_field(y, 'reformat', 0)

		if y.form.has_key('motd') and y.form['motd'].value in ('always','never'):
			put_meta_field(y, 'motd', y.form['motd'].value)
		else:
			put_meta_field(y, 'motd', 'updated')

		if y.form.has_key('log') and y.form['log'].value=='on':
			put_meta_field(y, 'log', 1)
		else:
			put_meta_field(y, 'log', 0)

		if y.form.has_key('uidlink') and y.form['uidlink'].value=='on':
			put_meta_field(y, 'uidlink', 1)
		else:
			put_meta_field(y, 'uidlink', 0)

		if y.form.has_key('readmyown') and y.form['readmyown'].value=='on':
			put_meta_field(y, 'readmyown', 1)
		else:
			put_meta_field(y, 'readmyown', 0)

		y.user.save()

		print """
<p>You probably want to go and <a href="%s/browse">read
some gossip</a> now.</p>""" % (y.url_prefix())

################################################################

class unknown_command_handler:
	def __init__(self, command_name):
		self.command_name = command_name

	def head(self, y):
		y.title = "Unknown command - " + self.command_name
		# This is quite legitimately 404-- since pages are
		# named after commands, you've specified a page which
		# doesn't exist.
		y.fly.set_header('Status','404 Unknown command')

	def body(self, y):
		print '<h1>Unknown command</h1>'
		print '<p>I don\'t know how to %s.' % (self.command_name)
		print '(Here\'s <a href="%s">what I do know</a>.)</p>' % (
			y.url_prefix())

################################################################

class unknown_server_handler:
	def __init__(self, server_name):
		self.server_name = server_name

	def head(self, y):
		y.title = "Unknown server - " + self.server_name
		y.fly.set_header('Status','404 Unknown server')

	def body(self, y):
		print '<h1>Unknown server</h1>'
		print '<p>I don\'t know a server named '+self.server_name+'.'
		print '(Here\'s <a href="%s">the servers I do know</a>.)</p>' % (
			y.url_prefix(None))

################################################################

class login_failure_handler:
	def head(self, y):
		y.title = "Login failed!"

	def body(self, y):
		print '<h1>Password failure</h1>'
		print '<p>That\'s not your password!</p>'

################################################################

class login_handler:
	def head(self, y):
		y.title = "Log in to yarrow"

	def body(self, y):
		if y.logging_in_status=='accepted':
			# Since all they asked for was to log in,
			# we needn't take them straight to any
			# particular page.
			print """
<h1>Logged in</h1>
<p>You're now logged in. You probably want to go and look for
<a href="%s">some gossip</a> to read.</p>""" % (
				y.url_prefix(None))

			# FIXME: Add warning about "permanent" logins if
			# you're using a public terminal?

		# Can't be "failed". That would have been picked up already.
		else:
			print """
<h1>Log in to yarrow</h1>
<p>Enter your yarrow username and password here. You're logging into yarrow
as a whole here, rather than into any particular RGTP server; this means
that you can access your RGTP shared-secrets from any computer connected
to the Internet. If you don't have a yarrow account, you may
<a href="%s/newbie">get a new account</a> here.</p>

<form action="%s" method="post"><table>
<tr><td>Username:</td> <td><INPUT TYPE="text" NAME="user"></td></tr>
<tr><td>Password:</td> <td><INPUT TYPE="password" NAME="password">
 <a href="%s/resetpass">(Forget?)</a> </td></tr>
<tr><td>Remember my login on this computer.</td>
 <td><INPUT TYPE="checkbox" CHECKED NAME="remember"><br>
(You probably want to leave this turned on,
unless you're using a public workstation.) </td></tr>
<tr><td colspan="2" align="right"><input type="submit" value=" OK "></td></tr>
</table></form>

<p>You will need cookies enabled from here on in.</p>
""" % (
	y.url_prefix('sys'),
	maybe_environ('REQUEST_URI'),
	y.url_prefix('sys'),
	)

################################################################

class logout_handler:
	def head(self, y):
		y.title = "Log out of yarrow"
		y.clear_session()
		y.user = None

	def body(self, y):
		print """
<h1>Logged out</h1>
<p>You're now logged out.</p>"""

################################################################

class newbie_handler:
	def head(self, y):
		y.title = "Get a new yarrow account"

		# This has to be done before we send the body of the HTML,
		# because it can cause us to set cookies.

		if y.form.has_key('user'):
			try:
				user.create(y.form['user'].value)
				self.result='ok'
			except user.AlreadyExistsException, aee:
				self.result='clash'
		else:
			self.result='genesis'

	def body(self, y):
		if self.result=='ok':
			print '<h1>Created.</h1>'
			print '<p>Check your inbox for email from yarrow. When you'
			print 'get it, you can go and'
			print '<a href="'+y.url_prefix()+'/newpass">change'
			print 'your password</a>.</p>'
		elif self.result=='clash':
			print '<h1>Name clash.</h1>'
			print '<p>Sorry, but a user named '+y.form['user'].value
			print 'already exists.'
			print '<a href="%s/newbie">Try again</a>?</p>' % (
				y.url_prefix('sys'))
		else:
			print '<h1>Get a new yarrow account</h1>'
			print '<p>This lets you create a new account on yarrow. Once you\'ve'
			print 'set this up, you can go on to set up accounts on individual'
			print 'RGTP servers.</p>'
			print '<form action="%s/newbie" method="post"><table>' % (
				y.url_prefix('sys'))
			print '<tr><td>Your email address (which is also your username):</td>'
			print '<td><INPUT TYPE="text" NAME="user"></td></tr>'
			print '<tr><td colspan="2" align="right">'
			print '<input type="submit" value=" OK "></td></tr>'
			print '</table></form>'
			print '<p>yarrow will send you email telling you your'
			print 'initial password.</p>'

################################################################

class change_password_handler:
	def head(self, y):
		y.title = "Change your yarrow password"
		if y.form.has_key('user') \
		  and y.form.has_key('oldpass') \
		  and y.form.has_key('newpass1') \
		  and y.form.has_key('newpass2'):
			self.submit(y)
			# FIXME: Not really worth doing this in a separate proc
		else:
			self.result = 'showform'

	def body(self, y):
		"Prints the body text for this page. Because all the hard\
work has already been done, this just prints text according to the value of\
self.result."
		if self.result=='badpass':
			print '<h1>Verification problem</h1>'
			print '<p>Either I couldn\'t find a user with the name you gave,'
			print 'or the old password you gave was wrong (and I\'m'
			print 'certainly not going to tell you which one it was).'
			print '<a href="'+y.url_prefix()+'/newpass">Try again?</a></p>'
		elif self.result=='nomatch':
			print '<h1>The new passwords didn\'t match</h1>'
			print '<p>Silly person.'
			print '<a href="'+y.url_prefix()+'/newpass">Try again?</a></p>'
		elif self.result=='ok':
			print '<h1>Password changed</h1>'
			print '<p>I\'ve changed the password, and you\'re now'
			print 'logged in to yarrow.'
			print 'You probably want to go and look for'
			print '<a href="'+y.url_prefix()+'/server">some gossip</a>'
			print 'to read now.</p>'
		elif self.result=='showform':
			print '<h1>Change your yarrow password</h1>'

			if y.form.has_key('user') or y.form.has_key('oldpass') or y.form.has_key('newpass1') or y.form.has_key('newpass2'):
				print '<p><b>Please fill in all the boxes!</b></p>'

			print '<p>This lets you change your password on yarrow. If you'
			print 'don\'t have an account on yarrow yet, you probably want'
			print 'to go and <a href="'+y.url_prefix()+'/newbie">create'
			print 'an account</a> instead.</p>'

			print '<p>This is not where you change your shared-secret on'
			print 'any RGTP server. For that, contact the Editors of the'
			print 'relevant server.</p>'

			print '<form action="'+y.url_prefix('sys')+'/newpass" method="post"><table>'
			print '<tr><td>Your email address:</td>'
			print '<td><INPUT TYPE="text" NAME="user"></td></tr>'
			print '<tr><td>Your old password</td>'
			print '<td><INPUT TYPE="password" NAME="oldpass">'
			print '<a href="'+y.url_prefix()+'/resetpass">(Forget?)</a>'
			print '</td></tr>'
			print '<tr><td>Your new password:</td>'
			print '<td><INPUT TYPE="password" NAME="newpass1"></td></tr>'
			print '<tr><td>Your new password again, to verify:</td>'
			print '<td><INPUT TYPE="password" NAME="newpass2"></td></tr>'
			print '<tr><td colspan="2" align="right">'
			print '<input type="submit" value=" OK "></td></tr>'
			print '</table></form>'
		else:
			raise rgtp.RGTPException('Weird status: '+self.result)

	def submit(self, y):
		candidate = user.from_name(y.form['user'].value)
		if candidate==None or \
		  not candidate.password_matches(y.form['oldpass'].value):
			self.result = 'badpass'
		elif y.form['newpass1'].value!=y.form['newpass2'].value:
			self.result = 'nomatch'
		else:
			candidate.set_password(y.form['newpass2'].value)
			candidate.save()

			y.accept_user(candidate, 1)

			self.result = 'ok'

################################################################

class reset_password_handler:
	def head(self, y):
		y.title = 'Reset your password'

	def body(self, y):
		if y.form.has_key('user'):
			self.submit(y)
		else:
			self.form(y)

	def submit(self, y):
		candidate = user.from_name(y.form['user'].value)
		if candidate==None:
			# Bother-- this lets them do checks on who has an account
			# (though they'll run the risk of sending a lot of email
			# if they try). Think about solutions to this problem.
			print '<h1>Verification problem</h1>'
			print '<p>I couldn\'t find a user with the name you gave.'
			print '<a href="'+y.url_prefix()+'/resetpass">Try again?</a></p>'
		else:
			candidate.invent_new_password()
			candidate.save()

			print '<h1>New password sent</h1>'
			print '<p>Check your inbox, then go and'
			print '<a href="'+y.url_prefix()+'/newpass">change it</a>'
			print 'to something sensible.</p>'

	def form(self, y):
		print '<h1>Reset your yarrow password</h1>'

		print '<p>If you\'ve forgotten your password, you can use this'
		print 'form to have it reset to a random string and emailed'
		print 'to you.</p>'

		print '<p>This is not where you change your shared-secret on'
		print 'any RGTP server. For that, contact the Editors of the'
		print 'relevant server.</p>'

		print '<form action="'+y.url_prefix('sys')+'/resetpass" method="post"><table>'
		print '<tr><td>Your email address:</td>'
		print '<td><INPUT TYPE="text" NAME="user"></td></tr>'
		print '<tr><td colspan="2" align="right">'
		print '<input type="submit" value=" OK "></td></tr>'
		print '</table></form>'
			
################################################################

class server_chooser_handler:
	def head(self, y):
		y.title = 'Choose an RGTP server'

	def body(self, y):
		print '<h1>First off, choose yourself a server.</h1>'

		print '<table width="100%">'
		print '<tr><th>Name</th>'
		print '<th>Description</th>'
		print '<th>Your settings</th></tr>'

		servers = config.all_known_servers()
		server_names = servers.keys()
		server_names.sort()

		for server in server_names:
			print '<tr><td><a href="%s">%s</a></td><td>%s</td><td>' % (
				y.url_prefix(server),
				server,
				servers[server]['description'])

			if y.user:
				userid = y.user.state(server, 'userid', '')
				if userid!='':
					print userid
				else:
					print '<i>unknown</i>'
				print '[<a href="%s/config">change</a>]' % (
					y.url_prefix(server))
			else:
				print '<i>not logged in</i>'

			print '</td></tr>'

		print '</table>'
	
		print '<h1>Interested in adding to these?</h1>'
		print '<p>You can'
		print '<a href="http://freshmeat.net/projects/spurge">download</a>'
		print 'and run your own RGTP server.'
		print 'If you know of any servers not listed above,'
		print 'please <a href="mailto:spurge@thurman.org.uk">'
		print 'let us know</a>.</p>'

################################################################

class server_frontend_handler:
	def __init__(self, list):
		self.verbs = list

	def head(self, y):
		if not y.server:
			# Probably we're redirecting...
			return
		
		y.title = '%s - %s' % (y.server,
				       y.server_details.get('description'))

	def body(self, y):
		if not y.server:
			# Probably we're redirecting...
			return

		print '<h1>%s</h1>' % (y.server)

		if y.server=='sys':
			# not a real server! Bail.
			print "<p>This isn't a real server; it's just used as"
			print "a placeholder. Best place to go would be"
			print '<a href=".">back to the main page</a>.'
			return

		if y.server_details.has_key('longdesc'):
			print y.server_details['longdesc']

		print '<p>%s lives on the host <code>%s</code>, port <code>%s</code>.</p>' % (
			y.server.title(),
			y.server_details['host'],
			y.server_details['port'])

		print '<ul>'
		print '<li><a href="%s/browse"><b>Read %s now!</b></a></li>' % (
			y.url_prefix(),
			y.server.title())
		print '<li><a href=".">Look for some other servers.</a></li>'
		print '</ul>'
			

################################################################

class regu_handler:
	"Lets you create an account on an RGTP server."
	def head(self, y):
		y.title = 'Request a %s account' % (y.server)

	def body(self, y):
		print '<h1>New %s account</h1>' % (y.server)

		if y.form.has_key('newbie'):
			# We have a name. Try to create an account with that name.
			result = y.connection.request_account(y.form['newbie'].value)

			if result[0]:
				print '<h2>Success!</h2>'
			else:
				print '<h2>Account creation failed</h2>'
			print '<p><i>' + result[1] + '</i></p>'
			if result[0]:
				print '<p>Check your email for a message\
from the %s server.</p>' % (y.server)

			print """
<p>If you'd like to contact a human to discuss this, the Editors' email
addresses are usually listed in <a href="%s/motd">the server's
message of the day</a>.</p>""" % (y.url_prefix())
		else:
			# They haven't given us a username. So we give them a form
			# to fill in. Firstly, get the warning text, by doing an
			# account request and then bailing before we give them a
			# name.
			warning = y.connection.request_account(None)
			print '<p><b>Please read this before'
			print 'continuing:</b></p><p>'
			for line in warning:
				print cgi.escape(line) + '<br>'
			print """
</p>
<form action="%s/newbie" method="post">
<input type="text" name="newbie">
<input type="submit" value=" Apply "></form>
""" % (y.url_prefix())

################################################################

class udbm_handler:
	def head(self, y):
		y.title = 'Modify user settings on '+y.server

	def body(self, y):
		print '<h1>%s user database manager</h1>' % (
			y.server)
		
		if y.connection.access_level < 3:
			# Errrr nope. You need to be an editor to do this.
			print 'You need to be an editor to use the database manager.'
			return
		
		command = ''
		if y.form.has_key('command'):
			command = y.form['command'].value

		response = y.connection.udbm(command)
		print """
<form action="%s/users" method="post">
<input type="text" name="command">
<input type="submit" value=" OK "></form>
<pre>%s</pre>""" % (
			y.url_prefix(),
			cgi.escape(string.join(response,'\n')))

                if response == []:
			# GROGGS's udbm often returns a success code
			# but no text on success.
			print '<i>(Looks like that was successful.)</i>'

################################################################

class catchup_handler:
	def head(self, y):
		y.title = 'Catch up with %s' % (y.server)

	def body(self, y):
		print '<h1>Catch up with %s</h1>' % (y.server)

		if y.form.has_key('yes') and y.is_post_request():
			# Note that this catches us up to *now*, rather than
			# wherever we were when the user read the index last.
			# The difference is a few seconds, usually, but might
			# be significant occasionally. I'm not sure what we
			# should do about it, though.

			y.user.last_sequences[y.server] = \
				cache.index(y.server, y.connection).sequences()
			y.user.save()

			print '<p>OK, done. Now, you probably want to'
		else:
			print '<p>From here, you can mark all gossip on %s as "read".</p>' % (y.server)
			print '<form action="%s/catchup" method="post">' % (y.url_prefix())
			print '<input type="hidden" name="yes" value="y">'
			print '<input type="submit" value=" I mean it! "></form>'
			print '<p>Or you could just'

		print 'go back to <a href="%s/browse">the %s index</a>.</p>' % (
			y.url_prefix(), y.server)

################################################################

class yarrow:
	"A web interface for RGTP."

	def __init__(self):
		self.logging_in_status = 'unknown'
		self.form = cgi.FieldStorage()

		# Title of the HTML page.
		self.title = 'Reverse Gossip'

		# Name of the server.
		# FIXME: replace with server_details[n] --
		# or make that a dictionary?
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

	def accept_user(self, user, add_cookies=0, cookie_expiry=0):
		"Sets the current user to be |user|, and optionally adds appropriate cookies."
		self.user = user
		if add_cookies:
			self.outgoing_cookies['yarrow-session'] = user.session_key()
			self.outgoing_cookies['yarrow-session']['path'] = self.url_prefix('')
			if cookie_expiry:
				self.outgoing_cookies['yarrow-session']['expires'] = cookie_expiry

	def html_for_matched_itemid(self, matchobj):
		"Returns some HTML to link to the itemid given in 'matchobj'."
		itemid = matchobj.groups()[0]
		# FIXME: We should cache these somewhere. (Wrapper for "stat"?)
		try:
			return '<a href="%s/%s" title="%s">%s</a>' % (
				self.url_prefix(),
				itemid,
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
			item_link = ''
		else:
			item_link = '/' + self.item

		print '<form action="'+self.url_prefix()+item_link+'/post" method="post">'

		def suitable_grogname(y):
			"Picks a suitable grogname for the current user."
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

		if self.server!='' and self.server!='sys':
			try:
				server = config.server_details(self.server)
			except Exception, e:
				self.logging_in_status = 'unknown-server'
				return
			
			self.server_details = server
			self.connection = rgtp.fancy(server['host'],
						     server['port'],
						     self.log)
			if self.verb in ['newbie', 'config']:
				# Some verbs must not have a connection
				# set up when processing them.
				# (Rather an ugly hack, yes :( )
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
				self.logging_in_status = 'rgtp-error'
				self.logging_in_details = str(r)
				return

			self.logging_in_status = 'ok'

	def hop_target(self):
		"""Returns the itemid of the hop target, or None if there's
		no good place to go."""

		if not self.collater:
			# FIXME: Possibly this should be done automatically
			# when they make the connection.
			try:
				self.collater = cache.index(self.server,
							 self.connection)
			except rgtp.RGTPException, r:
				return None
			
		if self.item:
			return 'item'
		else:
			return None

	def print_headers(self, fly):
		fly.set_cookies(self.outgoing_cookies)

		print """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
"http://www.w3.org/TR/html4/loose.dtd">
<head><title>""" + self.title + """</title>
<style type="text/css"><!--
body {
  margin: 0px; font-size: 12px;
  font-family: Verdana, Arial, Helvetica, sans-serif; height: 8.5in;
  background-color: #FFFFFF; color: #000000; }
td {
  vertical-align: top; font-size: 10px; }
th {
  background-color: #770000; text-align: left; color: #FFFFFF;
  vertical-align: middle; font-size: 12px; }
.reply {
  background-color: #770000; color: #FFFFFF; }
.reply td {
  text-align: right; }
.menu {
  position: absolute; left:auto; bottom:auto; top: 0; right: 0;
  background-color: #FFFFFF; width: 10%; z-index:1; color: #FF0000;
  font-size:10px; padding-left: 1em; float: right; }
.menu {
  position: fixed; } /* Float it, if you can. */
.menu a, .menu a:visited {
  color: #770000; background-color: #FFFFFF; text-decoration: none; }
.menu h1 {
  font-size:10px; color: #000000; background-color: #FFFFFF; }
.content { position: absolute; width: 86%; height: auto;
  top: 0; left: 0; right: 90%; padding-left: 1em; background-color: #FFFFFF;
  color: #000000; text-align: left; z-index: 0; }
a { color: #770000; text-decoration: underline; }
a:visited { color: #000000; text-decoration: underline; }
table.browse a, table.browse a:visited { text-decoration: none; color: #770000; }
td.uid { font-style: italic; }
td.uid a, td.uid a:visited { font-style: normal; font-family: monospace; }
table.reply td.uid a { text-decoration: none; color: #FFFFFF; }
table.browse a.related, table.browse a.visited { color: #FFFFFF; background-color: #770000; }
h1 { font-size: 15pt; }
h2 { font-size: 12pt; }
.invisible { display: none; }
span.hop { font-size: 15px; border:groove; color: #777777; font-weight:bold;}
--></style>
<link rel="shortcut icon" href="/favicon.ico">
</head><body><div class="content">"""

	def print_footers(self):
		# The sidebar and so on.

		self.maybe_print_logs()

		print '</div><div class="menu">'
		if self.server!='' and self.server!='sys':
			print '<h1>%s</h1>' % (self.server)
			def serverlink(y, name, title):
				print '<a href="%s/%s">%s</a><br>' % (
					y.url_prefix(),
					name,
					title)
			serverlink(self,'browse','browse')
			serverlink(self,'post','post')
			serverlink(self,'catchup','catch&nbsp;up')
			print '<br>'
			serverlink(self,'config','config')
			serverlink(self,'newbie','register')
			if self.connection.access_level > 2:
				serverlink(self,'users','accounts')
			print '<br>'
			serverlink(self,'motd','status')
			serverlink(self,'editlog', 'show&nbsp;edits');

		print '<h1>general</h1>'
		if self.is_real_user():
			print '<a href="%s/logout">log&nbsp;out</a><br>' % (
				self.url_prefix('sys'))

			print '<br>'

			servers = self.user.metadata.keys()
			servers.sort()
			for server in servers:
				print '<a href="%s/browse">&gt;&nbsp;%s</a><br>' % (
					self.url_prefix(server), server)
		else:
			print '<a href="%s/login">log&nbsp;in</a><br>' % (
				self.url_prefix('sys'))

		print """<h1>yarrow</h1>
<a href="http://rgtp.thurman.org.uk/yarrow/">about</a><br>
<a href="http://validator.w3.org/check/referer">valid&nbsp;HTML</a><br>
<a href="http://jigsaw.w3.org/css-validator/check/referer">valid&nbsp;CSS</a>
<br><br>"""

                # are we doing this?
		# hop_to = self.hop_target()
                # if hop_to:
		# 	print """<span class="hop" title="Hop to: %s">
		# <a href="%s/%s">hop</a></span>""" % (hop_to, self.url_prefix(), hop_to)
		# else:
		#	print """<span class="hop"
		# title="Nowhere's better than anywhere else!">hop</span>"""

		print '</div></body></html>'
	
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
		self.outgoing_cookies['yarrow-session'] = ""
		self.outgoing_cookies['yarrow-session']["path"] = self.url_prefix('')
		self.outgoing_cookies['yarrow-session']["expires"] = -500000

	def is_post_request(self):
		"Returns whether this was an HTTP POST request."
		return maybe_environ('REQUEST_METHOD')=='POST'

	def is_real_user(self):
		"Returns whether there's a real user logged in (not Visitor)."
		return self.user and self.user.username!='Visitor'

	def decide_tasks(self):
		def harvest(self, key):
			if self.form.has_key(key):
				return self.form[key].value
			else:
				return ''

		def handle_potential_logging_in(y):
			"""Many pages give the user the chance to log in
			(by calling login_form()) if the user isn't currently
			logged in; such login forms submit to the current
			page, so that on success we can go back there. Such
			pages need to call this function from their 'head()'
			to handle it if the user is logging in. Returns
			'accepted' if the user was logged in successfully,
			'failed' if they weren't,
			and 'not' if the user wasn't attempting to log in."""

			# FIXME: When the dust of adding "visitors" has
			# settled, find whether this is really as common
			# as it used to be.

			visiting = y.form.has_key('visiting') and y.is_post_request()

			username = password = None

			if visiting:
				username = 'Visitor'
			elif y.form.has_key('user'):
				# hmm, confusing name
				username = y.form['user'].value

			if y.form.has_key('password'):
				password = y.form['password'].value

			if visiting or password:
				# OK, so they're logging in.
				possible = user.from_name(username)

				if possible and (visiting or possible.password_matches(password)):
					if (not visiting) and y.form.has_key('remember') and y.form['remember'].value:
						# Ten years or so
						expiry = 60*60*24*365*10
					else:
						# As soon as you
						# close the browser
						expiry = 0

					y.accept_user(possible, 1, expiry)
					return 'accepted'
				else:
					return 'failed'
			else:
				return 'not'

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

		if self.user:
			self.reformat = self.user.state(self.server,
							'reformat', 0)
			self.log = self.user.state(self.server, 'log', 0)
			self.uidlink = self.user.state(self.server, 'uidlink', 1)
			self.readmyown = self.user.state(self.server, 'readmyown', 1)
		else:
			self.reformat = 0
			self.log = 0
			self.uidlink = 1
			self.readmyown = 0 # but you can't post anyway

		if self.item!='' and self.verb=='':
			self.verb = 'read' # implicit for items

		if self.server=='':
			self.server='sys'
			if self.verb=='':
				# The default verb is different if they
				# haven't specified a server too (because then
				# they're coming in on the main page).
				self.verb = 'server'

		# Many pages can print the login form, and that form submits
		# back to the same page (so that if it works, you can go
		# straight to what you were asking for). It makes sense to
		# handle the logging in globally.
		self.logging_in_status = handle_potential_logging_in(self)

	tasks = {
		'read': read_handler,
		'motd': motd_handler,
		'browse': browse_handler,
		'users': udbm_handler,
		'wombat': wombat_handler,
		'post': post_handler,
		'editlog': editlog_handler,
		'config': config_handler,
		'newbie': regu_handler,
		'catchup': catchup_handler,
	}

	sys_tasks = {
		'login': login_handler,
		'logout': logout_handler,	
		'newbie': newbie_handler,
		'newpass': change_password_handler,
		'server': server_chooser_handler,
		'resetpass': reset_password_handler,
	}

	def begin_tasks(self):
		"""Starts working on a task as soon as we know what it is,
before the HTML starts printing."""

		# Okay, find all the things they could ask for.

		if self.server=='sys':
			# "sys" is magic, not a real server;
			# get the list for "sys".
			tasklist = self.sys_tasks
		else:
			tasklist = self.tasks

		if self.verb=='':
			# They didn't say what they wanted to do,
			# so give them a general overview.
			self.verb_handler = server_frontend_handler(tasklist)
		elif tasklist.has_key(self.verb):
			# Ah, we know about what they wanted to do.
			# Create them a handler to do it for them.
			self.verb_handler = tasklist[self.verb]()
		else:
			# No idea about that. Use the handler that tells them
			# that we don't understand.
			self.verb_handler = unknown_command_handler(self.verb)

		if self.logging_in_status=='failed':
			# They did try to log in, but it failed.
			# Use a special verb handler to tell them so.
			self.verb_handler = login_failure_handler()
		elif self.logging_in_status=='unknown-server':
			# Similarly.
			self.verb_handler = unknown_server_handler(self.server)

		# Lastly, the handler itself probably wants to do some amount
		# of setup. Call it.
		self.verb_handler.head(self)

	def finish_tasks(self):
		self.verb_handler.body(self)

	def url_prefix(self, servername=0):
		"""Returns the URL prefix for accessing this server.
		If |servername|==0 (or omitted), only the bare prefix
		is returned. If it's None, the prefix plus a slash plus
		the name of the current server is returned; otherwise
		the prefix plus a slash plus the value of |servername|
		is returned."""
		script_address = maybe_environ('SCRIPT_NAME')

		if servername==None:
			return script_address
		else:
			if servername==0:
				servername = self.server
			return '%s/%s' % (
				script_address,
				servername,
				)

	def run_as_cgi(self):
		"Carry out the job of yarrow run as a CGI script."

		original_stdout = sys.stdout
		try:
			self.fly = webfly = sys.stdout = fly.webfly()

			self.decide_tasks()
			self.connect()
			self.begin_tasks()
			self.print_headers(webfly)
			self.finish_tasks()
			self.print_footers()

			# Okay. Should we send them all this?
			if maybe_environ('HTTP_IF_NONE_MATCH')==webfly.etag():
				original_stdout.write('Status: 304 Hi again :)')
			else:

				if maybe_environ('HTTP_ACCEPT_ENCODING').find('gzip')!=-1:
					webfly.compress()
				original_stdout.write(webfly.cgi_headers()+'\r\n')
				original_stdout.write(webfly.content())
		except:
			sys.stdout = original_stdout
			print "Content-Type: text/html"
			print
			print "<h1>Something went wrong there.</h1>"
			cgi.print_exception()
			try:
				self.maybe_print_logs()
			except:
				pass # Oh well.

