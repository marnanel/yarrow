/*
 * Word-wrapping algorithm extracted from Buttress. Expects input
 * words in a linked list, and expects a function which will tell
 * it the width of any given word.
 */

typedef struct word_Tag *word;
struct word_Tag {
    word *next, *alt;
    int type;
    int aux;
    int breaks;			       /* can a line break after it? */
    wchar_t *text;
    filepos fpos;
};

typedef struct tagWrappedLine wrappedline;
struct tagWrappedLine {
    wrappedline *next;
    word *begin, *end;		       /* first & last words of line */
    int nspaces;		       /* number of whitespaces in line */
    int shortfall;		       /* how much shorter than max width */
};

wrappedline *wrap_para(word *text, int width, int subsequentwidth,
		       int (*widthfn)(word *)) {
    wrappedline *head = NULL, **ptr = &head;
    int nwords, wordsize;
    struct wrapword {
	word *begin, *end;
	int width;
	int spacewidth;
	int cost;
	int nwords;
    } *wrapwords;
    int i, j, n;

    /*
     * Break the line up into wrappable components.
     */
    nwords = wordsize = 0;
    wrapwords = NULL;
    while (text) {
	if (nwords >= wordsize) {
	    wordsize = nwords + 64;
	    wrapwords = srealloc(wrapwords, wordsize * sizeof(*wrapwords));
	}
	wrapwords[nwords].width = 0;
	wrapwords[nwords].begin = text;
	while (text) {
	    wrapwords[nwords].width += widthfn(text);
	    wrapwords[nwords].end = text->next;
	    if (text->next && (text->next->type == word_WhiteSpace ||
			       text->next->type == word_EmphSpace ||
			       text->breaks))
		break;
	    text = text->next;
	}
	if (text && text->next && (text->next->type == word_WhiteSpace ||
			   text->next->type == word_EmphSpace)) {
	    wrapwords[nwords].spacewidth = widthfn(text->next);
	    text = text->next;
	} else {
	    wrapwords[nwords].spacewidth = 0;
	}
	nwords++;
	if (text)
	    text = text->next;
    }

    /*
     * Perform the dynamic wrapping algorithm: work backwards from
     * nwords-1, determining the optimal wrapping for each terminal
     * subsequence of the paragraph.
     */
    for (i = nwords; i-- ;) {
	int best = -1;
	int bestcost = 0;
	int cost;
	int linelen = 0, spacewidth = 0;
	int seenspace;
	int thiswidth = (i == 0 ? width : subsequentwidth);

	j = 0;
	seenspace = 0;
	while (i+j < nwords) {
	    /*
	     * See what happens if we put j+1 words on this line.
	     */
	    if (spacewidth)
		seenspace = 1;
	    linelen += spacewidth + wrapwords[i+j].width;
	    spacewidth = wrapwords[i+j].spacewidth;
	    j++;
	    if (linelen > thiswidth) {
		/*
		 * If we're over the width limit, abandon ship,
		 * _unless_ there is no best-effort yet (which will
		 * only happen if the first word is too long all by
		 * itself).
		 */
		if (best > 0)
		    break;
	    }
	    if (i+j == nwords) {
		/*
		 * Special case: if we're at the very end of the
		 * paragraph, we don't score penalty points for the
		 * white space left on the line.
		 */
		cost = 0;
	    } else {
		cost = (thiswidth-linelen) * (thiswidth-linelen);
		cost += wrapwords[i+j].cost;
	    }
	    /*
	     * We compare bestcost >= cost, not bestcost > cost,
	     * because in cases where the costs are identical we
	     * want to try to look like the greedy algorithm,
	     * because readers are likely to have spent a lot of
	     * time looking at greedy-wrapped paragraphs and
	     * there's no point violating the Principle of Least
	     * Surprise if it doesn't actually gain anything.
	     */
	    if (best < 0 || bestcost >= cost) {
		bestcost = cost;
		best = j;
	    }
	}
	/*
	 * Now we know the optimal answer for this terminal
	 * subsequence, so put it in wrapwords.
	 */
	wrapwords[i].cost = bestcost;
	wrapwords[i].nwords = best;
    }

    /*
     * We've wrapped the paragraph. Now build the output
     * `wrappedline' list.
     */
    i = 0;
    while (i < nwords) {
	wrappedline *w = mknew(wrappedline);
	*ptr = w;
	ptr = &w->next;
	w->next = NULL;

	n = wrapwords[i].nwords;
	w->begin = wrapwords[i].begin;
	w->end = wrapwords[i+n-1].end;

	/*
	 * Count along the words to find nspaces and shortfall.
	 */
	w->nspaces = 0;
	w->shortfall = width;
	for (j = 0; j < n; j++) {
	    w->shortfall -= wrapwords[i+j].width;
	    if (j < n-1 && wrapwords[i+j].spacewidth) {
		w->nspaces++;
		w->shortfall -= wrapwords[i+j].spacewidth;
	    }
	}
	i += n;
    }

    sfree(wrapwords);

    return head;
}

void wrap_free(wrappedline *w) {
    while (w) {
	wrappedline *t = w->next;
	sfree(w);
	w = t;
    }
}
