#!/usr/bin/python

import rgtp

a=rgtp.fancy("rgtp.thurman.org.uk", 1499, 0)
print a.index()
print a.interpreted_index()
print a.stat('F0000002')
print a.item('F0000002')
a.logout()

