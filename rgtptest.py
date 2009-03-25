#!/usr/bin/python

import rgtp

a=rgtp.fancy("rgtp.thurman.org.uk", 1431)
#a.login("marnanel@nimyad.org", "0e59d965a3114a7039bd6b499a793661")
print a.motd()
a.logout()

