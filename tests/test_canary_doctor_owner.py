"""Живой прогон пульта защищает временную копию базы."""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

from orchestrator import config, doctor, liveness


def test_live_pult_suite_base_is_not_a_hung_canary_run():
    """Ловит мутацию: сторож принимает живую базу обычного suite-run за мёртвую канарейку."""
    with tempfile.TemporaryDirectory() as root:
        with mock.patch.object(tempfile, "tempdir", root):
            base = Path(tempfile.mkdtemp(prefix="artel-suite-base-"))
            (base / liveness.SUITE_OWNER_MARKER).write_text(str(os.getpid()),
                                                            encoding="utf-8")
            with mock.patch.object(doctor, "_running_processes", return_value=[
                    (70001, config.HUNG_TEST_RUN_AGE_SEC + 1,
                     "python -m pytest")]), \
                 mock.patch.object(doctor, "_process_cwd", return_value=str(base)):
                assert doctor._find_hung_test_runs(object()) == []


def test_unrelated_live_suite_run_does_not_protect_orphan_base():
    """Ловит мутацию: pid чужого suite-run защищает базу без собственного живого маркера."""
    with tempfile.TemporaryDirectory() as root:
        temp_root = Path(root)
        logs = temp_root / "logs"
        run_path = logs / "suite-run" / "other-task" / "run.json"
        run_path.parent.mkdir(parents=True)
        run_path.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        with mock.patch.object(tempfile, "tempdir", root), \
             mock.patch.object(config, "LOGS", logs):
            orphan = Path(tempfile.mkdtemp(prefix="artel-suite-base-"))
            live = Path(tempfile.mkdtemp(prefix="artel-suite-base-"))
            (live / liveness.SUITE_OWNER_MARKER).write_text(
                str(os.getpid()), encoding="utf-8")
            assert doctor._orphan_temp_dirs() == [orphan]
            doctor._fix_orphan_temp_dirs()
            assert not orphan.exists()
            assert live.exists()


def test_live_origin_marker_protects_before_remote_link():
    """Ловит мутацию: doctor удаляет origin с живым маркером до записи remote URL."""
    with tempfile.TemporaryDirectory() as root:
        with mock.patch.object(tempfile, "tempdir", root):
            origin = Path(tempfile.mkdtemp(prefix="artel-canary-origin-"))
            (origin / liveness.CANARY_OWNER_MARKER).write_text(
                str(os.getpid()), encoding="utf-8")
            assert origin not in doctor._orphan_temp_dirs()
            doctor._fix_orphan_temp_dirs()
            assert origin.exists()
