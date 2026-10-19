CC ?= gcc
PYTHON ?= python3

.PHONY: all c-core test test-c test-python clean install-dev

all: c-core
	mkdir -p sdk/litrun/lib
	cp core/lib/liblitrun_core.so sdk/litrun/lib/

c-core:
	$(MAKE) -C core all

test-c:
	$(MAKE) -C core test

test-python:
	PYTHONPATH=sdk:. $(PYTHON) tests/run_tests.py

test: test-c test-python

install-dev: all
	$(PYTHON) -m pip install -e ".[all]"

clean:
	$(MAKE) -C core clean
	rm -rf sdk/litrun/lib
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
