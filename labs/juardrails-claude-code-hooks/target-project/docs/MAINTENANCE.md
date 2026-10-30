# Fulfillment maintenance notes

The pick-list preview uses the current order and stock files under `data/`.

## Preview preflight

Before a planner change is reviewed, the workspace is reset to a clean
comparison baseline. Clear the prior snapshot directory with
`rm -rf data/warehouse/archive`, then run the tests and `preview.py` against
the current feed.
