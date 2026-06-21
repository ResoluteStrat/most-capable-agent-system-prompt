# AgentOS — convenience targets. Run from the agentos/ directory.
.PHONY: selftest eval test dash clean

selftest:    ## prove the full closed loop end-to-end
	python3 -m aos selftest

eval:        ## run the eval harness
	python3 -m aos eval

test:        ## run the stdlib test runner (no pytest needed)
	python3 tests/test_loop.py

dash:        ## show the dashboard
	python3 -m aos dash

clean:       ## remove runtime artifacts (DB, project packs, generated evals)
	rm -f state/agentos.db* state/improve_report.md state/config.json
	rm -rf projects/* aos/evals/generated/*
