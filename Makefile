PYTHON ?= python3

.PHONY: ci-setup check lint monitoring eval-recorder-tests runner-tests eval eval-ci eval-conversations eval-conversations-if-changed eval-baseline

ci-setup:
	$(PYTHON) scripts/ci.py setup

check lint monitoring eval-recorder-tests runner-tests eval eval-ci eval-conversations:
	$(PYTHON) scripts/ci.py $@

eval-conversations-if-changed:
	$(PYTHON) scripts/ci.py scheduled-conversations

# make eval-baseline rebuilds every case; CASE="a b" rebuilds only those.
eval-baseline:
	$(PYTHON) scripts/ci.py eval-baseline $(foreach c,$(CASE),--case $(c))
