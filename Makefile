.PHONY: build
build:
	pip install -U pip
	pip install -U wheel setuptools
	pip install -U foc ouch
	pip install -r requirements.txt
