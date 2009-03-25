#!/usr/bin/python

import string

def wrap(text, linelength = 80):
	costs = []
	words_on_line = []
	for i in range(len(text), 0, -1):
		candidate = text[i-1:]
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
	temp = text
	result = []

	while temp!=[]:
		cut = words_on_line[n]
		result.append(string.join(temp[:cut]))
		temp = temp[cut:]
		n -= cut
	return result
