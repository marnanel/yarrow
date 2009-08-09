"Optional metadata"

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

################################################################

import common
import shelve
import config

class metadata:
    def __init__(self):
        self.tags = {}
        self.slugs = {}
        self.seen = {}

    def consider(self, collater, connection):
        k = collater.keys()
        k.sort()
        for itemid in k:
            if self.seen.has_key(itemid):
                continue

            item = connection.item_plain(itemid)
            while item[0]!='': item=item[1:]
            item = item[1:]
            for line in item:
                if not line or not line.startswith('&'):
                    break

                if line.startswith('&TAGS='):
                    for tag in [t.strip().replace(' ','-') for t in line[6:].split(',')]:
                        if not self.tags.has_key(tag):
                            self.tags[tag] = []
                        self.tags[tag].append(itemid)
                elif line.startswith('&SLUG='):
                    self.slugs[line[6:]] = itemid

            self.seen[itemid] = 1

metadata_file = config.backing_store_path('metadata')

def get(name, collater, connection):
	mutex = common.mutex('metadata.lock')
	mutex.get()

	meta = shelve.open(metadata_file)

        if meta.has_key(name):
            current = meta[name]
        else:
            current = metadata()

        current.consider(collater, connection)

        meta[name] = current
        meta.close()
        mutex.drop()

        return current

