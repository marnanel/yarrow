"""The web-fly.

This is a simple object which stands in for a stream, such as stdout.
It can later produce everything written to that stream, and carry out
tasks on the data which are useful to a CGI script, such as compression.

According to <http://www.mnot.net/cgi_buffer/>, the cgi_buffer library
does much the same as this module. I should investigate it, maybe.
"""

import md5
import gzip
import cStringIO

def compressBuf(buf):
	"""Compress to a memory buffer. Code thanks to Alan Kennedy:
	see <http://www.xhaus.com/alan/python/httpcomp.html>."""
	zbuf = cStringIO.StringIO()
	zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 9)
        zfile.write(buf)
	zfile.close()
	return zbuf.getvalue()

class webfly:
	def __init__(self):
		self.buffer = ''
		self.digest = md5.new()
		self.headers = {
			'Content-Type': 'text/html',
			'Cache-Control': 'no-cache, must-revalidate'}
		self.other_header_strings = ''
		self.only_headers = 0

	def write(self, whatever):
		self.buffer = self.buffer + whatever
		self.digest.update(whatever)

	def send_only_headers(self):
		self.only_headers = 1

	def content(self):
		if self.only_headers:
			return ''
		else:
			return self.buffer

	def etag(self):
		return 'm-'+self.digest.hexdigest()[0:7]

	def set_header(self, field, value):
		self.headers[field] = value

	def set_cookies(self, dough):
		temp = str(dough)
		if temp!='':
			self.other_header_strings += temp + '\r\n'

	def compress(self):
		if not self.headers.has_key('Content-Encoding') and not self.only_headers:
			self.headers['Content-Encoding'] = 'gzip'
			self.buffer = compressBuf(self.buffer)

	def cgi_headers(self):
		result = ''
		
		if self.only_headers:
			result = 'Content-Length: 0\r\n'
		else:
			result = 'Content-Length: %d\r\nETag: "%s"\r\n' % (
				len(self.buffer),
				self.etag())

		for anything in self.headers.keys():
			result += '%s: %s\r\n' % (
				anything,
				self.headers[anything])

		return self.other_header_strings + result
