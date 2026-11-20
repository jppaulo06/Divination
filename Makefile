PYTHON ?= python3

.PHONY: ci-setup check lint monitoring eval-recorder-tests runner-tests eval eval-conversations eval-conversations-if-changed eval-record-baseline eval-compare

ci-setup:
	$(PYTHON) scripts/ci.py setup

check lint monitoring eval-recorder-tests runner-tests eval eval-conversations eval-compare:
	$(PYTHON) scripts/ci.py $@

eval-conversations-if-changed:
	$(PYTHON) scripts/ci.py scheduled-conversations

eval-record-baseline:
	$(PYTHON) scripts/ci.py record-baseline
