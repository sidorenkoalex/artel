"""Живой прогон пульта защищает временную копию базы."""

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
