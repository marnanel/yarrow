dummy:
	@echo "Commands for installing yarrow:"
	@echo " make install - installs yarrow.  **This is probably what you want.**"
	@echo
	@echo "Commands for creating archives:"
	@echo " make tar     - creates gzipped and bzip2d tarfiles"
	@#echo " make rpm     - creates an .RPM file"
	@#echo " make deb     - creates a .deb file if you're lucky"
	@#echo "                   (not officially supported)"
	@echo "(Output of these always ends up in the dist/ directory.)"

clean:
	rm -rf dist

# mainly for the maintainer's use
dist: clean tar #rpm
	cp dist/* /home/ftp/pub/thurman/rgtp
	cp dist/* ../web/download/archives

tar: targz tarbz2

targz: README
	python setup.py -q sdist

# Ack, no way of doing this gracefully.
# (Look into ways to avoid having the version number
# written explicitly here.)
tarbz2: targz
	mkdir dist/tarbz2
	cd dist/tarbz2; tar xzf ../yarrow-1.2.0.tar.gz
	cd dist/tarbz2; tar cjf yarrow-1.2.0.tar.bz2 yarrow-1.2.0
	mv dist/tarbz2/*.bz2 dist
	rm -rf dist/tarbz2

# Not supported until we can check it works properly.
rpm: README
	python setup.py -q bdist_rpm --group "Web/Applications"
	rpm -qip dist/yarrow-1.2.0-1.noarch.rpm

# not an official working option.
# .deb files, when we support them, will be generated using a quite
# different process.
deb: rpm
	# This is the "you'll be very lucky if it works"(tm) approach to
	# package management
	cd dist; fakeroot alien --to-deb yarrow-1.2.0-1.noarch.rpm

install:
	python setup.py -q install

README: ../web/docs/index.php
	lynx -dump http://rgtp.thurman.org.uk/yarrow/docs/index.php > README