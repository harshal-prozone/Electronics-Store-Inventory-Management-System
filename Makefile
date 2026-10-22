.PHONY: install run test

install:
	python3 -m venv .venv
	. .venv/bin/activate && python -m pip install -r requirements.txt

run:
	. .venv/bin/activate && flask --app app run --debug

test:
	. .venv/bin/activate && pytest -q
