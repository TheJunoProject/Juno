"""Allow `python -m server ...` as an alternative to the `juno` script."""

from server.cli import main

raise SystemExit(main())
