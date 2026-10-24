"""Адресный прогон тестов full_suite_lock с фиксированным зерном песочницы.

python3 seeded_timing.py <зерно> <узел pytest>... — из рабочего каталога.
"""
import random
import sys

import pytest

seed = int(sys.argv[1])
real = random.randrange


def fixed(*args, **kwargs):
    if args == (1 << 30,):
        return seed
    return real(*args, **kwargs)


random.randrange = fixed
args = ["-p", "no:cacheprovider", "-p", "no:xdist", "-p", "timeout",
        "-o", "timeout=300", "--durations=0", "--durations-min=0",
        *sys.argv[2:]]
sys.argv = ["pytest", *args]
sys.exit(pytest.main(args))
