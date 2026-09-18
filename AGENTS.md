# Agent instructions

## Python interpreter

Always use the project virtual environment at `.venv`, never the bare `python`
on the `PATH`: the system interpreter has older, incompatible versions of some
dependencies installed globally (for instance `pystages` 1.3 instead of the
required 1.5).

- Run commands with `.venv/bin/python` (or `poetry run <command>`).
- Console entry points are available as `.venv/bin/laserstudio`,
  `.venv/bin/chipscan`, etc.
- The application itself is started as a module: `.venv/bin/python -m laserstudio --config config.yaml`.

## Checks

`pytest` and `mypy` come from the `test` / `lint` extras and are not always
installed in `.venv`; install the extra before relying on them.

- Tests: `.venv/bin/python -m pytest` (integration tests are excluded by
  default; they need a running Laser Studio on port 4444 and are run with
  `-m integration`).
- Types: `.venv/bin/python -m mypy laserstudio`.
