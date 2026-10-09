.PHONY: test demo
test:
	PYTHONPATH=src:tests python3 -m unittest discover -s tests -v
demo:
	PYTHONPATH=src python3 -m offer_scout.cli run --simulate
