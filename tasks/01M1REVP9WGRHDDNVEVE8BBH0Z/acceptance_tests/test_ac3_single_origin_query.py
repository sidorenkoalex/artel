"""AC-3 (tasks/01M1REVP9WGRHDDNVEVE8BBH0Z/SPEC.md): «За один прогон
уборки (`doctor --fix`, включая предпросмотр в `doctor` без `--fix`)
выполняется ровно один запрос `git ls-remote --heads origin
'artifact/*'`, не по одному на каждую ветку-кандидата.»

`doctor.all_checks` подменена целиком в обоих тестах (не предмет этого
критерия — своя песочница живого/CLI-смоука не нужна, тот же приём, что
`tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/
test_ac4_orphan_artifact_branch_cleanup.py::Ac4CmdDoctorGatingTest`).
Настоящий git через спай `_sandbox.spy_on_gitcmd_git` (не заглушка,
считающая на глаз, а настоящий подсчёт argv настоящих вызовов): наивная
реализация, зовущая сверку с origin ОТДЕЛЬНО для предпросмотра и ОТДЕЛЬНО
внутри самой уборки (например, `_orphan_artifact_branches` внутри
`sweep_orphan_artifact_branches` пересчитывает то, что `cmd_doctor` уже
знает из предпросмотра), тест обязан поймать — обе точки используют один
и тот же `gitcmd.git`, спай видит оба вызова.

Красен до реализации: `git ls-remote --heads origin 'artifact/*'` сегодня
не вызывается вовсе (критерий сироты не сверяется с origin) — счётчик
останется 0, тест ожидает 1.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import doctor  # noqa: E402
from tests.sandbox import capture  # noqa: E402

from _sandbox import ArtifactOriginSandbox  # noqa: E402


def _ls_remote_artifact_calls(calls):
    return [c for c in calls
           if len(c) >= 4 and c[0] == "ls-remote" and c[1] == "--heads"
           and c[2] == "origin" and c[3] == "artifact/*"]


class Ac3SingleOriginQueryTest(ArtifactOriginSandbox):

    def setUp(self):
        super().setUp()
        # Несколько кандидатов сразу — наивная реализация «один запрос на
        # ветку-кандидата» была бы 0/1/2/3, не 1, только если кандидатов
        # больше одного.
        self.local_only_artifact_branch("t777")
        self.local_only_artifact_branch("t778")
        self.push_artifact_branch("t888")

    def test_ac3_preview_mode_queries_origin_exactly_once(self):
        """`doctor` без `--fix` — ровно один `ls-remote --heads origin
        'artifact/*'` за весь предпросмотр.
        """
        spy_cm, calls = self.spy_on_gitcmd_git()
        with mock.patch.object(doctor, "all_checks", lambda conn: []), spy_cm:
            capture(doctor.cmd_doctor)

        self.assertEqual(len(_ls_remote_artifact_calls(calls)), 1)

    def test_ac3_fix_mode_queries_origin_exactly_once(self):
        """`doctor --fix` — ровно один `ls-remote --heads origin
        'artifact/*'` за весь прогон, включая и предпросмотр перед
        удалением, и саму уборку.

        Ловит мутацию: предпросмотр (для печати числа/имён кандидатов) и
        сама уборка (`sweep_orphan_artifact_branches`) каждый по
        отдельности зовут сверку с origin — тест увидит 2 вызова вместо 1.
        """
        spy_cm, calls = self.spy_on_gitcmd_git()
        with mock.patch.object(doctor, "all_checks", lambda conn: []), spy_cm:
            capture(lambda: doctor.cmd_doctor(fix=True))

        self.assertEqual(len(_ls_remote_artifact_calls(calls)), 1)


if __name__ == "__main__":
    unittest.main()
