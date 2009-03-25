"General distutils script for yarrow 1.2.0. Rather experimental at present."
  
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

import sys
import os
import os.path
import pwd

try:
    from distutils.core import setup
except ImportError:
    print """
You don't seem to have distutils installed!
Have a look at http://rgtp.thurman.org.uk/yarrow/docs/
for some suggestions as to how to get hold of it.
"""
    sys.exit()

def press_enter():
    "Prints a prompt and waits for the user to press return."
    sys.stdout.write('Please press Enter to continue: ')
    sys.stdout.flush()
    sys.stdin.readline()

# Okay, in the absence of any consensus as to where Linux systems should
# keep CGI, we'll have to guess. The earlier an entry is, the more we
# prefer it.
#
# Trouble is that when you build an archive, such as an RPM, this sticks
# to whatever it was on the build host. Need to think of a way to work
# around this.

cgi_bin_directory = None

for potential in [
    '/usr/lib/cgi-bin',       # Debian
    '/home/httpd/cgi-bin',    # Red Hat (?)
    '/var/www/cgi-bin',       # Seen this around the place
    '/usr/local/lib/cgi-bin', # I suppose it's _possible_
    '~/public_html/cgi-bin',  # Scraping the bottom of the barrel here
    ]:
    if os.path.isdir(potential):
        # Woohoo! We've found a valid directory
        cgi_bin_directory = potential
        break

if cgi_bin_directory:
    print 'setup: CGI script will be installed in %s' % (cgi_bin_directory)
    print
else:
    cgi_bin_directory = '/tmp'

    print 'setup: **** WARNING ****'
    print 'setup: no valid CGI directory was found!'
    print 'setup: CGI script will be installed in /tmp instead. Please move it.'
    print 'setup: Contact the maintainer if you know where it _should_ go.'

    press_enter()

# We also need to make a /var/lib/yarrow directory. Unfortunately we do this
# even when we're not installing, like when we're creating an archive.
# (Distutils should have a way of checking, but hey...)

backing_store = '/var/lib/yarrow'

if not os.path.isdir(backing_store):
    print 'setup: creating yarrow\'s backing store directory.'
    os.makedirs(backing_store, 0700)

    # Now we have the less-than-fun task of guessing which user
    # is the one the webserver runs as.

    uid = 0 # It'll be root if we can't think of anything else.

    # Check through a list of likely names.

    for name in ['www-data',
                 'wwwrun',
                 'daemon',
                 'httpd',
                 # um, any others?
                 ]:
        try:
            uid = pwd.getpwnam(name)[2]
            # yay, we survived that, so it's a real one
            break
        except KeyError:
            pass # evidently not that one, then

    print 'setup: Giving access to %s only.' % (pwd.getpwuid(uid)[0])
    os.chown(backing_store, uid, 0)
    print 'setup: If your webserver runs scripts as a different'
    print 'setup: user, please chown the directory %s.' % (backing_store)
    press_enter()

setup(
    name         = 'yarrow',
    description  = 'CGI-based RGTP bulletin board client',
    version      = '1.2.0',
    author       = 'Thomas Thurman',
    author_email = 'marnanel@marnanel.org',
    url          = 'http://rgtp.thurman.org.uk/yarrow/',
    licence      = 'GPL',
    platforms    = ['posix'],
    keywords     = 'rgtp cgi bulletin conferencing conference discussion board',
    packages     = ['Yarrow'],
    data_files   = [('/etc', ['yarrow.conf']),
                    (cgi_bin_directory, ['yarrow.cgi'])],
    long_description = """Yarrow is a CGI front end to the RGTP bulletin
board transfer protocol. It lets users browse RGTP information using
an ordinary web browser.""",
    )

print 'setup: done.'
