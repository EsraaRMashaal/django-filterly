"""
run_tests.py — django-filterly test runner
==========================================

HOW TO RUN
----------

  Option 1 — double-click or run directly:
      python run_tests.py

  Option 2 — with the virtual environment active:
      .venv\Scripts\activate          # Windows CMD
      source .venv/bin/activate       # macOS / Linux
      python run_tests.py

  Option 3 — pass extra pytest flags via CLI:
      python run_tests.py -k TestParser
      python run_tests.py -x
      python run_tests.py --tb=short

WHAT IT DOES
------------
  Runs the full test suite under tests/ with:
    -v          verbose (one line per test)
    --tb=short  short traceback on failures
    --cov       coverage report for django_filterly/
    --cov-report=term-missing  shows which lines are not covered
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# Base pytest command; extra args forwarded from the command line
CMD = [
    sys.executable, "-m", "pytest",
    "tests/",
    "-v",
    "--tb=short",
    f"--cov={ROOT / 'django_filterly'}",
    "--cov-report=term-missing",
    *sys.argv[1:],          # forward any extra flags the caller passed
]


def main() -> None:
    print("=" * 70)
    print("django-filterly — running test suite")
    print("=" * 70)
    print(f"Command: {' '.join(CMD)}\n")

    result = subprocess.run(CMD, cwd=ROOT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
