PYTHON ?= python3

.PHONY: ci-setup check lint monitoring runner-tests eval eval-conversations eval-conversations-if-changed

ci-setup:
	$(PYTHON) scripts/ci.py setup

check lint monitoring runner-tests eval eval-conversations:
	$(PYTHON) scripts/ci.py $@

eval-conversations-if-changed:
	$(PYTHON) scripts/ci.py scheduled-conversations
