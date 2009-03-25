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

import config
import cgi
import rgtp
import wrapping
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

if os.environ.has_key('SCRIPT_NAME'):
	prefix = os.environ['SCRIPT_NAME'] + '/'
else:
	prefix = '/'

# FIXME: General fn to print "try again?" as a link to the current page. (use environ.)

def html_for_itemid(matchobj):
	itemid = matchobj.groups()[0]
	# FIXME: We should cache these somewhere. (Wrapper for "stat"?)
	# FIXME: This should be a subfunction of linkify.
	# FIXME: Would be nice to mark them with a * or something for unread ones.
	try:
		return '<a href="'+prefix+rgtp_connection.server+'/'+itemid+'" title="'+rgtp_connection.connection.stat(itemid)['subject']+'">'+itemid+'</a>'
	except rgtp.RGTPException, r:
		# Problem fetching the title. Hmm.
		return '<span title="'+str(r)+'">'+itemid+'</span>'

def linkify(text):
	"Adds hyperlinks to |text|. If you use this with cgi.escape(), call that first."
	temp = text
	temp = re.sub(r'\b([A-Za-z]\d{7})\b', html_for_itemid, temp)
	temp = re.sub('(http:([A-Za-z0-9_+~#/?=%.-]|&amp;)*)(?!<)', r'<a href="\1">\1</a>', temp)
	temp = re.sub('(ftp:([A-Za-z0-9_+~#/?=%.-]|&amp;)*)(?!<)', r'<a href="\1">\1</a>', temp)
	temp = re.sub('(gopher:([A-Za-z0-9_+~#/?=%.-]|&amp;)*)(?!<)', r'<a href="\1">\1</a>', temp)
	temp = re.sub('([A-Za-z0-9._+-]*@[A-Za-z0-9._+]+)', r'<a href="mailto:\1">\1</a>', temp)
	# I was considering allowing www.anything to be an http link, but that starts
	# interfering with the text when it's already in a link. Odd that links can't
	# nest, isn't it?
	return temp

def html_print(message, grogname, author, time, reformat):
	"Prints one of the sections of an item which contains one reply and the banner across the top."
	# First: the banner across the top...

	if grogname!=None:
		print '<table class="reply" width="100%"><tr><th rowspan="2">'
		# We don't linkify the grogname, because it's often just an email address.
		print cgi.escape(grogname)
		print '</th><td>'
		print cgi.escape(author)
		print '</td></tr><tr><td>'
		print time
		print '</td></tr></table>'

	# And now for some real content.

	for line in message:
		print linkify(cgi.escape(line))
		if reformat:
			if line=='':
				print '<br><br>'
			elif len(line)<40:
				# just a guess, but...
				print '<br>'
		else:
			# We're not reformatting, so just break at the ends of lines.
			print '<br>'

################################################################

class read_handler:

	def head(self, y):

		try:
			# fixme: This stat is wasteful. We can pick all this up from a[0].
			self.status = y.connection.stat(y.item)
			y.title = self.status['subject']
			self.item = y.connection.item(y.item)
		except rgtp.RGTPException, r:
			y.title = str(r)
			self.status = None
			self.item = None

	def body(self, y):

		if you_should_be_logged_in(y):
			return

		def possibly_link(y, rh, title, key, anchor):
			"If we have a continuation in direction 'key', prints a link to it."
			target = rh.status[key]
			if target:
				try:
					name = y.connection.stat(target)['subject']
					print '<p><i>(%s <a href="%s/%s">%s</a>)</i></p>' % (
						title,
						prefix + y.server,
						target + anchor,
						name)

				except rgtp.RGTPException:
					print """
<p><i>(%s item %s, which is no longer available.)</i></p>""" % (title, target)

		print '<h1>' + linkify(cgi.escape(y.title)) + '</h1>'
		if self.item:
			possibly_link(y, self, 'Continued from', 'from', '#end')
			for i in self.item[1:]:
				print '<a name="%x"></a>' %(i['sequence'])
				html_print(i['message'], i['grogname'],
					i['author'],
					time.strftime("%a %d %b %Y %I:%M:%S %p",
						time.localtime(i['timestamp'])),
					y.reformat)
				print '<a name="after-%x"></a>' %(i['sequence'])

			possibly_link(y, self, 'Continued in', 'to', '')

			print '<a name="end"></a>'

			if y.connection.access_level > 1 and self.status['to']==None:
				print '<hr>'
				y.show_posting_box(self.status['replied'], 0)

		print '<hr><i>(Return to <a href="%s/browse">the %s index</a>)</i>' % (
			prefix + y.server, y.server)

		if y.user and not y.user.last_sequences.has_key(y.server):
			y.user.last_sequences[y.server] = {} # Stop errors below...

		if y.user and \
			self.status and \
			(not y.user.last_sequences[y.server].has_key(y.item) or \
				y.user.last_sequences[y.server][y.item] != self.status['replied']):
			# When they last read this entry, there was a different number of
			# replies. Update their record with the new number they've seen.
			y.user.last_sequences[y.server][y.item] = self.status['replied']
			y.user.save()

################################################################

class motd_handler:
	def head(self, y):
		y.title = y.server + ' message of the day'

	def body(self, y):
		print '<h1>'+y.server+' message of the day</h1>'
		print '<p>'
		# FIXME: a thought. yarrow could have its own motd method,
		# which updated the sequence number for when the user last
		# saw the motd as a side-effect, and did the [1:] automatically.
		# (maybe also have a param "return None if the sequence is <= N")
		html_print(y.connection.motd()[1:], None, None, None, y.reformat)
		print '</p>'

################################################################

def you_should_be_logged_in(y):
	"Prints appropriate warnings if y requires you to be logged in and you're not. Returns whether we recommend they should be prevented from continuing."
	if y.user:
		# They're logged into yarrow.

		who_they_are = y.user.state(y.server, 'userid', '')

		if not who_they_are:
			# But we don't know who they are on this server, so we'll need
			# to explain that to them.
			print '<p><b>Note:</b> You\'re logged into yarrow, but since you'
			print 'haven\'t yet told us any details for this server ('+y.server+'),'
			if y.connection.access_level==0:
				print 'and %s doesn\'t accept guest users,' % (y.server)
				print 'we can\'t get any gossip from it until you do.'
			else:
				print 'we\'ve logged you in as a guest.'
			print 'If you already have an account on '+y.server+','
			print 'go to the <a href="'+prefix+y.server+'/config">settings page</a>'
			print 'and tell us the name and shared secret; or, if you don\'t have'
			print 'an account on '+y.server+' already, you could'
			print '<a href="'+prefix+y.server+'/newbie">apply for one</a>.</p>'

			if y.connection.access_level==0:
				# Helpful hint:
				print '<p>(Some RGTP servers allow users to log in as "guest",'
				print 'with no password, to read without registering; you might'
				print 'give that a try.)</p>'
				return 1

			return 0
	else:
		# They're not logged in to yarrow. Can we give them satisfaction anyway?
		if y.connection.access_level==0:
			print """
<h1>Log in</h1>
<p>You'll have to log in to yarrow, because the page you're trying to view
comes from the %s server, which doesn't permit random anonymous
browsing.</p>""" % (y.server)
			login_form()
			return 1

		# They have guest access anyway, which is just about as good.
		return 0

################################################################

class browse_handler:
	def head(self, y):
		y.title = y.server + ' index'

	def body(self, y):
		if you_should_be_logged_in(y):
			return

		# optionally (FIXME: honour switch)
		print '<p>'
		html_print(y.connection.motd()[1:], None, '', '', 1)
		print '</p>'

		print '<table width="100%">'
		print '<tr><th class="index">On</th><th class="index">#</th><th class="index">Most recently by</th>'
		print '<th class="index">About</th></tr>'

		collater = cache.index(y.server, y.connection)
		index = collater.items()
		sequences = collater.sequences()

		# and now we can display them. sort them by date.

		# FIXME: would be nice to add some way of following continuation chains
		# through here.
		
		def compare_dates(left, right, I = index):
			return cmp(I[left]['date'], I[right]['date'])

		keys = index.keys()
		keys.sort(compare_dates)
		keys.reverse()

		if y.user and not y.user.last_sequences.has_key(y.server):
			y.user.last_sequences[y.server] = {} # Stop errors below...

		for k in keys:
			line = index[k]

			if y.user:
				if y.user.last_sequences[y.server].has_key(k) \
				   and y.user.last_sequences[y.server][k]>=sequences[k]:
					highlight = 0
				else:
					highlight = 1
			else:
				# No user information, so don't bother highlighting.
				highlight = 0

			print '<tr>'
			print '<td>'+common.neat_date(line['date'])+'</td>'
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

			if highlight and y.user.last_sequences[y.server].has_key(k):
				anchor = '#after-%x' %(y.user.last_sequences[y.server][k])
			else:
				anchor = ''

			print '<a class="exempt" href="'+prefix+y.server+'/'+k+anchor+'">'
			if not line['live']: print '<i>'
			if highlight: print '<b>'
			print line['subject']

			if highlight: print '</b>'
			if not line['live']: print '</i>'
			print '</a></td></tr>'
		print '<tr><td colspan="4" align="center">('
		print '<a href="'+prefix+y.server+'/post">'
		print 'Post a new message</a> )</td></tr>'
		print '</table>'

################################################################

class wombat_handler:
	def head(self, y):
		y.title = 'The wombat'

	def body(self, y):
		print '<h1>The wombat</h1>'
		print '<p>Mary had a little lamb.<br>'
		print 'They met in unarmed combat,<br>'
		print 'and (for the sake of rhyming verse)<br>'
		print 'it turned into a wombat.</p>'

################################################################

class post_handler:
	"Handles both creating new items and replying to existing ones."

	def head(self, y):
		y.title = 'Post a new item to %s' % (y.server)

	def body(self, y):
		if y.form.has_key('data'):
			self.submit(y)
		else:
			self.form(y)

	def submit(self, y):
		submission_status = [0]

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

		if y.form.has_key('sequence'):
			# They've requested some sanity checks:
			# the item hasn't been continued, and its reply number
			# matches a certain sequence number.
			currently = y.connection.stat(y.item)
			if currently['to'] or \
			   (int(y.form['sequence'].value,16) != currently['replied']):
				submission_status[0] = -1

		if submission_status[0]==0: # Still OK to send stuff?
			y.connection.send_data(name, string.split(y.form['data'].value, '\r\n'))
			submission_status = y.connection.post(item, subject)

		if submission_status[0]==-1:
			# Nope, someone's been there before us.
			# We should tell them what they said. IE has a nasty habit of
			# eating the contents of forms if you go back to them.
			print """
<h1>Collision</h1>
<p>Sorry, someone posted a reply in the time between when you read the item
and when you submitted your reply. I suggest you go and read
<a href="%s/%s">what's changed</a> before you reply again.</p>
<p>For reference, you said:<blockquote>""" % \
	(prefix+y.server, item)
			for line in string.split(y.form['data'].value,'\r\n'):
				print line + '<br>'
			print '</blockquote></p>'

		elif submission_status[0]==1:
			print '<h1>That item\'s full</h1>'
			print '<p>You need to start a new item. Edit your text'
			print 'if needs be, and think of an appropriate new subject'
			print 'line.</p>'
			y.show_posting_box(None, 1, y.form['data'].value)

		else:
			# Success! Work out the URL of the new posting.
			print '<h1>Added comment</h1>'
			print 'Your comment was added. You can view it'
			print '<a href="%s%s/%s#%x">here</a>.' % (
				prefix, y.server,
				submission_status[1],
				submission_status[2])

	def form(self, y):
		print '<h1>Post a new item</h1>'
		y.show_posting_box()

################################################################

class editlog_handler:
	def head(self, y):
		y.title = y.server + ' edit log'

	def body(self, y):
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

		for thing in edits:
			print '<tr>'
			if thing.has_key('item'):
				print '<td>'
				if thing['action']=='withdrawn':
					print thing['item']
				else:
					print linkify(thing['item'])
				print '</td>'
			else:
				print '<td><a href="'+prefix+y.server+'/browse">'
				print '<i>index</i></a></td>'
			print '<td>'+thing['date']+'</td>'
			print '<td>'+thing['action']+'</td>'
			print '<td>'+thing['editor']+'</td>'
			print '<td>'+linkify(thing['reason'])+'</td>'
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
			print '<a href="'+prefix+'sys/login">log in to'
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
		print '<form action="'+prefix+y.server+'/config" method="post">'
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
		print 'you probably need to <a href="'+prefix+y.server+'/newbie">register'
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
		print '<p><b>Not honoured in this version</b></p>'
		print '<p>If you like, yarrow can attempt to reformat the text received'
		print 'from the server so that it fills the width of your screen.'
		print 'Otherwise, the text will be displayed just as the server'
		print 'sends it.</p>'
		# FIXME doesn't pick up state
		print '<p><input type="checkbox" name="reformat"> Reformat text.</p>'

		print '<h2>Message of the Day</h2>'
		print '<p><b>Not honoured in this version</b></p>'
		print '<p>Should yarrow show the message of the day on the index page?'
		print '(You can always see it by clicking the "status" link in the'
		print 'sidebar, too.)</p>'
		print '<p><input type="radio" name="motd" value="always">Always show the MOTD.'
		print '<br><input type="radio" name="motd" value="updated">Only show the MOTD when it\'s been updated.'
		print '<br><input type="radio" name="motd" value="always">Never show the MOTD.</p>'

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
			print '<a href="%s/config">Try again?</a></p>' % (prefix+y.server)
			return

		if len(secret)%2==1:
			print '<h1>Invalid secret</h1>'
			print '<p>Sorry, the shared-secret you gave wasn\'t valid.'
			print 'Secrets must contain an even number of letters or numbers;'
			print 'yours had %d, which is very odd.' % (len(secret))
			print '<a href="%s/config">Try again?</a></p>' % (prefix+y.server)
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
				print 'on %s. <a href="%s/config">Try again?</a></p>' % (y.server, prefix+y.server)
				return
		else:
			put_meta_field(y, 'userid', userid)
			put_meta_field(y, 'secret', secret)
		
		# reformat only happens if it's true; we must set it to true
		# only if it exists and is true, and false otherwise.
		put_meta_field(y, 'reformat', str(y.form.has_key('reformat') and y.form['reformat'].value==1))

		grognames = []
		# [] is also what they get if they've specified no grognames.

		if y.form.has_key('grogname'):
			# FIXME: Will it always be \r\n? Do we have rfc-type
			# proof of this?
			original = string.split(y.form['grogname'].value, '\r\n')

			# Now weed out the bad ones: too long, say, or blank.
			for name in original:
				if len(name)>75:
					print '<p>'+name
					print ' is too long to be a grogname. Ignored.</p>'
				elif name!='':
					grognames.append(name)

		put_meta_field(y, 'grogname', grognames)

		# next: handle the motd switch correctly (both for display and
		# processing. (Use the existing "radio" fn?))

		y.user.save()

		print """
<p>You probably want to go and <a href="%s/browse">read
some gossip</a> now.</p>""" % (prefix+y.server)

################################################################

class unknown_command_handler:
	def __init__(self, command_name):
		self.command_name = command_name

	def head(self, y):
		y.title = "Unknown command - " + self.command_name

	def body(self, y):
		print '<h1>Unknown command</h1>'
		print '<p>I don\'t know how to '+self.command_name+'.'
		print '(Here\'s <a href="'+prefix+y.server+'">what I do know</a>.)</p>'

################################################################

def login_form(submit_to = None):

	if submit_to == None:
		submit_to = os.environ['REQUEST_URI']

	print """
<p>Enter your yarrow username and password here. You're logging into yarrow
as a whole here, rather than into any particular RGTP server; this means
that you can access your RGTP shared-secrets from any computer connected
to the Internet. If you don't have a yarrow account, you may
<a href="%ssys/newbie">get a new account</a> here.</p>

<form action="%s" method="post"><table>
<tr><td>Username:</td> <td><INPUT TYPE="text" NAME="user"></td></tr>
<tr><td>Password:</td> <td><INPUT TYPE="password" NAME="password">
 <a href="%ssys/resetpass">(Forget?)</a> </td></tr>
<tr><td>Remember my login on this computer</td>
 <td><INPUT TYPE="checkbox" CHECKED NAME="remember"></td></tr>
<tr><td colspan="2" align="right"><input type="submit" value=" OK "></td></tr>
</table></form>""" % (prefix, submit_to, prefix)

################################################################

#FIXME: This is called only from one place, so probably should be moved.
def handle_potential_logging_in(y):
	"""Many pages give the user the chance to log in (by calling login_form())
if the user isn't currently logged in; such login forms submit to the current
page, so that on success we can go back there. Such pages need to call this
function from their 'head()' to handle it if the user is logging in. Returns
'accepted' if the user was logged in successfully, 'failed' if they weren't,
and 'not' if the user wasn't attempting to log in."""

	if y.form.has_key('password') and y.form.has_key('user'):
		# OK, so they're logging in.
		possible = user.from_name(y.form['user'].value)
		if possible and possible.password_matches(y.form['password'].value):

			if y.form.has_key('remember') and y.form['remember']:
				expiry = 60*60*24*365*10 # Ten years or so
			else:
				expiry = 0 # As soon as you close the browser

			y.accept_user(possible, 1, expiry)
			return 'accepted'
		else:
			return 'failed'
	else:
		return 'not'

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
			# Since all they asked for was to log in, we needn't take them
			# straight to any particular page.
			print '<h1>Logged in</h1>'
			print '<p>You\'re now logged in. You probably want to go and look for'
			print '<a href="'+prefix+y.server+'/server">some gossip</a>'
			print 'to read now.</p>'

			# FIXME: Add warning about "permanent" logins if you're using
			# a public terminal?

		# Can't be "failed". That would have been picked up already.
		else:
			print '<h1>Log in to yarrow</h1>'
			login_form()

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
			print '<a href="'+prefix+y.server+'/newpass">change'
			print 'your password</a>.</p>'
		elif self.result=='clash':
			print '<h1>Name clash.</h1>'
			print '<p>Sorry, but a user named '+y.form['user'].value
			print 'already exists.'
			print '<a href="'+prefix+'sys/newbie">Try again</a>?</p>'
		else:
			print '<h1>Get a new yarrow account</h1>'
			print '<p>This lets you create a new account on yarrow. Once you\'ve'
			print 'set this up, you can go on to set up accounts on individual'
			print 'RGTP servers.</p>'
			print '<form action="'+prefix+'sys/newbie" method="post"><table>'
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
			print '<a href="'+prefix+y.server+'/newpass">Try again?</a></p>'
		elif self.result=='nomatch':
			print '<h1>The new passwords didn\'t match</h1>'
			print '<p>Silly person.'
			print '<a href="'+prefix+y.server+'/newpass">Try again?</a></p>'
		elif self.result=='ok':
			print '<h1>Password changed</h1>'
			print '<p>I\'ve changed the password, and you\'re now'
			print 'logged in to yarrow.'
			print 'You probably want to go and look for'
			print '<a href="'+prefix+y.server+'/server">some gossip</a>'
			print 'to read now.</p>'
		elif self.result=='showform':
			print '<h1>Change your yarrow password</h1>'

			if y.form.has_key('user') or y.form.has_key('oldpass') or y.form.has_key('newpass1') or y.form.has_key('newpass2'):
				print '<p><b>Please fill in all the boxes!</b></p>'

			print '<p>This lets you change your password on yarrow. If you'
			print 'don\'t have an account on yarrow yet, you probably want'
			print 'to go and <a href="'+prefix+y.server+'/newbie">create'
			print 'an account</a> instead.</p>'

			print '<p>This is not where you change your shared-secret on'
			print 'any RGTP server. For that, contact the Editors of the'
			print 'relevant server.</p>'

			print '<form action="'+prefix+'sys/newpass" method="post"><table>'
			print '<tr><td>Your email address:</td>'
			print '<td><INPUT TYPE="text" NAME="user"></td></tr>'
			print '<tr><td>Your old password</td>'
			print '<td><INPUT TYPE="password" NAME="oldpass">'
			print '<a href="'+prefix+y.server+'/resetpass">(Forget?)</a>'
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
			print '<a href="'+prefix+y.server+'/resetpass">Try again?</a></p>'
		else:
			candidate.invent_new_password()
			candidate.save()

			print '<h1>New password sent</h1>'
			print '<p>Check your inbox, then go and'
			print '<a href="'+prefix+y.server+'/newpass">change it</a>'
			print 'to something sensible.</p>'

	def form(self, y):
		print '<h1>Reset your yarrow password</h1>'

		print '<p>If you\'ve forgotten your password, you can use this'
		print 'form to have it reset to a random string and emailed'
		print 'to you.</p>'

		print '<p>This is not where you change your shared-secret on'
		print 'any RGTP server. For that, contact the Editors of the'
		print 'relevant server.</p>'

		print '<form action="'+prefix+'sys/resetpass" method="post"><table>'
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
		print '<p>This is still being built. Don\'t expect anything to work.</p>'
		print '<h1>First off, choose yourself a server.</h1>'

		print '<table width="100%">'
		print '<tr><th class="index">Name</th>'
		print '<th class="index">Description</th>'
		print '<th class="index">Your settings</th></tr>'

		servers = config.all_known_servers()
		server_names = servers.keys()
		server_names.sort()

		for server in server_names:
			print '<tr><td><a href="%s/browse">%s</a></td><td>%s</td><td>' % (
				prefix+server, server, servers[server]['description'])

			if y.user:
				userid = y.user.state(server, 'userid', '')
				if userid!='':
					print userid
				else:
					print '<i>unknown</i>'
				print '[<a href="'+prefix+server+'/config">change</a>]'
			else:
				print '<i>not logged in</i>'
			print '</td>'
			print '</tr>'
	
		print '</table>'
	
		print '<h1>Interested in adding to these?</h1>'
		print '<p>You can'
		print '<a href="http://rgtp.thurman.org.uk/spurge/">download</a>'
		print 'and run your own RGTP server.'
		print 'If you know of any servers not listed above,'
		print 'please <a href="mailto:spurge@thurman.org.uk">'
		print 'let us know</a>.</p>'

################################################################

class verb_listing_handler:
	def __init__(self, list):
		self.verbs = list

	def head(self, y):
		y.title = 'Intermediate page'

	def body(self, y):
		print '<h1>Places you can go from here</h1>'
		if y.server=='sys':
			print '<p>These are all the verbs you can use'
			print 'globally, rather than only on one server.</p>'
		else:
			print '<p>These verbs apply only to '+y.server+'.</p>'
		print '<ul>'
		for verb in self.verbs.keys():
			print '<li><a href="'+prefix+y.server+'/'+verb+'">'
			print verb+'</a></li>'
		print '</ul>'
			

################################################################

class destroy_account_handler:
	def head(self, y):
		y.title = 'Destroy your account'

	def body(self, y):
		print '<h1>Destroy your yarrow account</h1>'
		print '<p>From here, you can destroy your whole yarrow account.</p>'
		print '<p><form action="'+prefix+'sys/login" method="post"><table>'
		print '<tr><td>Username:</td>'
		print '<td><INPUT TYPE="text" NAME="user"></td></tr>'
		print '<tr><td>Password:</td>'
		print '<td><INPUT TYPE="password" NAME="password">'
		print '<a href="'+prefix+y.server+'/resetpass">(Forget?)</a>'
		print '</td></tr>'
		print '<tr><td colspan="2" align="right">'
		print '<input type="submit" value=" OK "></td></tr>'
		print '</table></form></p>'

		# FIXME handle it!	

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
addresses are usually listed in <a href="%s/motd/">the server's
message of the day</a>.</p>""" % (prefix+y.server)
		else:
			# they haven't given us a username. So we give them a form
			# to fill in. Firstly, get the warning text, by doing an
			# account request and then bailing before we give them a
			# name.
			warning = y.connection.request_account(None)
			print '<table align="center"><tr><td>\
<img src="/exclamation" width="36" height="35" alt="/!\\"></td><td>'
			print '<b>Please read this before continuing:</b><br><br>'
			for line in warning:
				print cgi.escape(line) + '<br>'
			print '</td></tr><tr><td colspan="2" align="right">'
			print '<form action="'+prefix+y.server+'/newbie" method="post">'
			print '<INPUT TYPE="text" NAME="newbie">'
			print '<INPUT TYPE="submit" VALUE=" Apply "></FORM>'
			print '</td></tr></table>'


################################################################

class catchup_handler:
	def head(self, y):
		y.title = 'Catch up with %s' % (y.server)

	def body(self, y):
		print '<h1>Catch up with %s</h1>' % (y.server)

		if y.form.has_key('yes'):
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
			print '<form action="%s/catchup" method="post">' % (prefix+y.server)
			print '<input type="hidden" name="yes" value="y">'
			print '<input type="submit" value=" I mean it! "></form>'
			print '<p>Or you could just'

		print 'go back to <a href="%s/browse">the %s index</a>.</p>' % (
			prefix+y.server, y.server)

################################################################

class yarrow:
	"A CGI interface for RGTP."

	form = cgi.FieldStorage()

	# Title of the HTML page.
	title = 'Reverse Gossip'

	server = '' # FIXME: replace with server_details[n] -- or make that a dictionary?
	verb = ''

	static_prefix = config.value('web', 'static-prefix')

	################################################################
	# Cookie time:

	if os.environ.has_key('HTTP_COOKIE'):
		# They've sent us some cookies; better read them.
		incoming_cookies = Cookie.SimpleCookie(os.environ['HTTP_COOKIE'])
	else:
		# No cookies. Start with a blank sheet.
		incoming_cookies = Cookie.SimpleCookie()

	# Set up a cookie list ready for sending new ones.
	outgoing_cookies = Cookie.SimpleCookie()

	################################################################

	def accept_user(self, user, add_cookies=0, cookie_expiry=0):
		"Sets the current user to be |user|, and optionally adds appropriate cookies."
		self.user = user
		if add_cookies:
			self.outgoing_cookies['yarrow-session'] = user.session_key()
			self.outgoing_cookies['yarrow-session']['path'] = prefix
			if cookie_expiry:
				self.outgoing_cookies['yarrow-session']['expires'] = cookie_expiry

	def serverlink(self, name, title):
		print '<a href="'+prefix+self.server+'/'+name+'">'+title+'</a><br>'
	
	def show_posting_box(self, sequence=None, show_subject=1, textblock=None):
		if self.item=='':
			item_link = ''
		else:
			item_link = '/' + self.item

		print '<form action="'+prefix+self.server+item_link+'/post" method="post">'

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
		if show_subject:
			print 'Subject <input type="text" name="subject" '+\
				'value="" style="width: 99%"><br>'
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
			server = config.server_details(self.server)
			self.server_details = server
			connection = rgtp.fancy(server['host'],
				server['port'], self.log)
			if self.verb!='newbie': # ugh, ugly hack
				if self.user:
					connection.raise_access_level(None,
						meta_field(self, 'userid'),
						meta_field(self, 'secret'))
				else:
					connection.raise_access_level()
			return connection

	def print_headers(self):
		print self.outgoing_cookies
		print
		print """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
"http://www.w3.org/TR/html4/loose.dtd">
<head><title>%s</title>
<style type="text/css"><!--
@import "%snew-yarrow.css";
--></style>
<link rel="shortcut icon" href="%sfavicon.ico">
</head><body><div class="content">""" % (
		self.title,
		self.static_prefix,
		self.static_prefix)

	def print_footers(self):
		# The sidebar.

		print '</div><div class="menu">'
		if self.server!='' and self.server!='sys':
			print '<h1>%s</h1>' % (self.server)
			self.serverlink('browse','browse')
			self.serverlink('post','post')
			self.serverlink('catchup','catch&nbsp;up')
			print '<br>'
			self.serverlink('config','config')
			print '<br>'
			self.serverlink('motd','status')
			self.serverlink('editlog', 'show&nbsp;edits');
			# FIXME: regu link?

		print '<h1>general</h1>'
		if self.user==None:
			print '<a href="%ssys/login">log&nbsp;in</a><br>' % (prefix)
		else:
			print '<a href="%ssys/logout">log&nbsp;out</a><br>' % (prefix)

			print '<br>'

			servers = self.user.metadata.keys()
			servers.sort()
			for server in servers:
				print '<a href="%s%s/browse">&gt;&nbsp;%s</a><br>' % (prefix, server, server)
		print '<h1>yarrow</h1>'
		print '<a href="http://rgtp.thurman.org.uk/yarrow/">about</a><br>'
		print '<a href="http://validator.w3.org/check/referer">valid&nbsp;HTML</a><br>'
		print '<a href="http://jigsaw.w3.org/css-validator/check/referer">valid&nbsp;CSS</a><br>'
		print '</div>'

		print '</BODY></HTML>'

	
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

	def harvest(self, key):
		if self.form.has_key(key):
			return self.form[key].value
		else:
			return ''

	def clear_session(self):
		"Destroys our session cookie, for when you log out."
		self.outgoing_cookies['yarrow-session'] = ""
		self.outgoing_cookies['yarrow-session']["path"] = prefix
		self.outgoing_cookies['yarrow-session']["expires"] = -500000

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
					# This causes Apache to 500. :( FIXME
					raise rgtp.RGTPException("what's " + thing + " good for?")

		if self.incoming_cookies.has_key('yarrow-session'):
			self.user = user.from_session_key(self.incoming_cookies['yarrow-session'].value)
		else:
			self.user = None

		# legacy (remove later)
		self.usenc = 0
		self.reformat = 0
		self.log = 0

		if self.item!='' and self.verb=='':
			self.verb = 'read' # implicit for items

		if self.server=='':
			self.server='sys'
			if self.verb=='':
				# The default verb is different if they
				# haven't specified a server too (because then
				# they're coming in on the main page).
				self.verb = 'server'

		# FIXME: there is _no_ support for logging anywhere any more! make some!

		# Many pages can print the login form, and that form submits
		# back to the same page (so that if it works, you can go
		# straight to what you were asking for). It makes sense to
		# handle the logging in globally.
		self.logging_in_status = handle_potential_logging_in(self)

	tasks = {
		'read': read_handler,
		'motd': motd_handler,
		'browse': browse_handler,
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
		'destroy': destroy_account_handler,
		'resetpass': reset_password_handler,
	}

	def begin_tasks(self):
		"""Starts working on a task as soon as we know what it is,
before the HTML starts printing."""

		# Okay, find all the things they could ask for.

		if self.server=='sys':
			# "sys" is magic, not a real server; get the list for "sys".
			tasklist = self.sys_tasks
		else:
			tasklist = self.tasks

		if self.verb=='':
			# They didn't say what they wanted to do,
			# so give them a list.
			self.verb_handler = verb_listing_handler(tasklist)
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

		# Lastly, the handler itself probably wants to do some amount
		# of setup. Call it.
		self.verb_handler.head(self)

	def finish_tasks(self):
		self.verb_handler.body(self)

# The global RGTP connection.
rgtp_connection = yarrow()

def run_cgi():
	"Carry out the job of yarrow run as a CGI script."

	print "Content-Type: text/html"

	rgtp_connection.decide_tasks()

	try:
		rgtp_connection.connection = rgtp_connection.connect()
		rgtp_connection.begin_tasks()
		rgtp_connection.print_headers()
		rgtp_connection.finish_tasks()
		rgtp_connection.print_footers()
	except:
		print
		print "<h1>Something went wrong there.</h1>"
		cgi.print_exception()
		try:
			rgtp_connection.maybe_print_logs()
		except:
			pass # Oh well.
		sys.exit(255)

	rgtp_connection.maybe_print_logs()

