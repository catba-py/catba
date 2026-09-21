#!/usr/bin/env python3
"""Project-local CatBa launcher.

This file is part of the CatBa project template. It is intentionally tiny:
it forwards execution to the installed ``catba`` package and never contains
CLI logic of its own.

Because this file is named ``catba.py``, Python would otherwise resolve
``import catba`` to this file rather than the installed package. The script's
own directory is removed from ``sys.path`` before importing so the installed
package wins.

Intended flow:

    ./catba.py <command>
        |
        v
    CatBa package / runtime
        |
        v
    run project
"""

import os
import sys

# Drop the script's own directory so it does not shadow the installed
# ``catba`` package (this file is named catba.py).
_here = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p) != _here]

from catba.cli import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
