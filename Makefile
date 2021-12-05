NAME := mapmaker
BASE := $(shell pwd)
DIST := file://$(BASE)/dist

.PHONY: samples

build:
	python setup.py sdist

dev-install:
	# Use shell to make env vars visible to pip
	pip install --user --upgrade --pre --force-reinstall --no-deps --no-index --find-links "$(DIST)" $(NAME)

samples:
	./mapmaker.py --zoom 10 --gallery 63.0695,-151.0074 30km ./samples
