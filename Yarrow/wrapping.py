#!/usr/bin/python
#
#  wrapping.py - library to implement word-wrap
#  $Header: /var/cvs/yarrow/Yarrow/wrapping.py,v 1.2 2003/01/26 03:39:28 marnanel Exp $
#
#     I'm indebted to Simon Tatham for pointing
#     me at the algorithm used in this code.
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

import string

def wrap(text, linelength = 79):
	"Word-wraps |text|, a string. Returns a list of strings, one per line, no line longer than |linelength|."
	costs = []
	words_on_line = []
	words = []

	# Split |text| into |words|. Really long words are broken into pieces
	# (solving a bug found by GS104; see S0241523).
	for word in string.split(text):
		while len(word)>=linelength:
			words.append(word[0:linelength])
			word = word[linelength:]
		words.append(word)

	for i in range(len(words), 0, -1):
		candidate = words[i-1:]
		width = len(candidate)-1
		for word in candidate:
			width += len(word)

		if width<=linelength:
			# It fits in the last line, so we can have it for free.
			costs.append(0)
			words_on_line.append(len(candidate))
		else:
			# How much stuff can we put onto the first line?

			minimum_cost = -1

			firstlength = 0
			for j in range(0,len(candidate)-1):
				word = candidate[j]
				if firstlength==0:
					firstlength = len(word)
				else:
					firstlength += len(word)+1 # remember the space
				if firstlength > linelength:
					break
				score = (linelength-firstlength)**2 + costs[len(candidate)-(j+2)]

				if minimum_cost == -1 or score < minimum_cost:
					minimum_cost = score
					minimum_wol = j+1

			costs.append(minimum_cost)
			words_on_line.append(minimum_wol)

	n = -1
	temp = words
	result = []

	while temp!=[]:
		cut = words_on_line[n]
		result.append(string.join(temp[:cut]))
		temp = temp[cut:]
		n -= cut

	if result==[]:
		return [''] # an empty line
	else:
		return result
