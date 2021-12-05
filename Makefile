NAME := mapmaker
BASE := $(shell pwd)
DIST := file://$(BASE)/dist

BRANCH := $(shell git rev-parse --abbrev-ref HEAD)

.PHONY: build samples

# Dependencies:
# sdist and  wheel require the "build" package to be installed.
# install with `pip install build`
#
# check requires `twine` to be installed

build:
	# build sdist and wheel
	python -m build

sdist:
	python -m build --sdist

wheel:
	python -m build --wheel

check: build
	# check the distribution
	twine check dist/*

pypi: check-master clean check
	# upload to PyPi, relies an ~/.pypirc for authentication
	twine upload dist/*

check-master:
	# make sure we are on the "master" branch
	if [ "$(BRANCH)" != "master" ] ; then echo "not on master" && exit 1 ; fi

clean:
	rm dist/* || true

dev-install:
	pip install --editable .

samples:
	./mapmaker.py --zoom 10 --gallery 63.0695,-151.0074 30km ./samples
