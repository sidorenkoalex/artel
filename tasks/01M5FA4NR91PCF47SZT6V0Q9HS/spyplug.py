import functools
import os
from pathlib import Path

import orchestrator

REAL = Path(orchestrator.__file__).resolve().parents[1]
OUT = os.environ["SPY_OUT"]
_current = {"id": None}


def _hit(kind, real):
    with open(OUT, "a", encoding="utf-8") as out:
        out.write(f"{_current['id']}\t{kind}\t{'REAL' if real else 'tmp'}\n")


def _root_real():
    from orchestrator import config as cfg
    try:
        return Path(cfg.ROOT).resolve() == REAL
    except OSError:
        return True


def pytest_configure(config):
    from orchestrator import canary, doctor, fsm_merge_gate
    from orchestrator.doctor import cli
    orig_dir = canary._live_dir

    @functools.wraps(orig_dir)
    def spy_dir():
        path = orig_dir()
        try:
            under = Path(path).resolve().is_relative_to(REAL)
        except OSError:
            under = True
        _hit("live_dir", under)
        return path
    canary._live_dir = spy_dir

    orig_all = cli.all_checks

    @functools.wraps(orig_all)
    def spy_all(conn):
        _hit("all_checks", _root_real())
        return orig_all(conn)
    cli.all_checks = spy_all
    doctor.all_checks = spy_all

    orig_refuse = fsm_merge_gate._refuse_during_canary

    @functools.wraps(orig_refuse)
    def spy_refuse(*a, **kw):
        _hit("refuse_during_canary", _root_real())
        return orig_refuse(*a, **kw)
    fsm_merge_gate._refuse_during_canary = spy_refuse


def pytest_runtest_logstart(nodeid, location):
    _current["id"] = nodeid
