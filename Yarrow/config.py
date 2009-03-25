#!/usr/bin/python
#
#  yarrow - (yet another retro reverse-ordered website?)
#  v0.40
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

# This should mostly end up in a file such as /etc/yarrow.conf.

# The version of yarrow this is.
version = 'yarrow 0.40'

# Prefix for linking to HTTP stuff that never changes. At present this is:
#   - the CSS
#   - reverse-gossip.gif
#   - favicon.ico
# Must end with a slash.
http_static_prefix = '/'

# Source address for yarrow mail (sent when they set up a new account
# or change their password.)

# You can use yarrow@thurman.org.uk if you like,
# but you probably want to pick something else.

mail_source_address = 'yarrow@thurman.org.uk'

