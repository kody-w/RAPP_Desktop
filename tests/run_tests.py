#!/usr/bin/env python3
"""
RAPP Desktop Test Runner

Usage:
    python tests/run_tests.py              # Run all tests
    python tests/run_tests.py --unit       # Run only unit tests
    python tests/run_tests.py --coverage   # Run with coverage
    python tests/run_tests.py --verbose    # Verbose output
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_tests(args):
    """Run the test suite."""
    cmd = ["python", "-m", "pytest"]

    # Add test path
    test_path = PROJECT_ROOT / "tests"
    cmd.append(str(test_path))

    # Options
    if args.verbose:
        cmd.append("-v")

    if args.coverage:
        cmd.extend([
            "--cov=rapp_os",
            "--cov-report=term-missing",
            "--cov-report=html:coverage_report"
        ])

    if args.unit:
        cmd.extend(["-m", "not integration and not slow"])

    if args.integration:
        cmd.extend(["-m", "integration"])

    if args.pattern:
        cmd.extend(["-k", args.pattern])

    if args.failfast:
        cmd.append("-x")

    # Print command
    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)

    # Run tests
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="RAPP Desktop Test Runner")

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Run with coverage report"
    )
    parser.add_argument(
        "--unit", "-u",
        action="store_true",
        help="Run only unit tests"
    )
    parser.add_argument(
        "--integration", "-i",
        action="store_true",
        help="Run only integration tests"
    )
    parser.add_argument(
        "--pattern", "-k",
        help="Run tests matching pattern"
    )
    parser.add_argument(
        "--failfast", "-x",
        action="store_true",
        help="Stop on first failure"
    )

    args = parser.parse_args()

    # Check dependencies
    try:
        import pytest
    except ImportError:
        print("Installing test dependencies...")
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r",
            str(PROJECT_ROOT / "tests" / "requirements.txt")
        ])

    # Run tests
    exit_code = run_tests(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
