"""AC-5 (tasks/T051/SPEC.md): `doctor` выдаёт предупреждение для каждой
активной (нетерминальной) задачи, чья ветка отстала от main больше чем на
N коммитов (N — константа конфигурации, дефолт порядка 10).
"""
import subprocess
import unittest
from unittest import mock

from _sandbox import RealGitFreshnessTest  # noqa: E402
from orchestrator import config, doctor, runner, store  # noqa: E402

# Значительно больше любого разумного "порядка 10" дефолта (SPEC, требование
# 8) — устойчиво к тому, каким именно developer выберет N в этих рамках.
LAG_COMMITS = 25

REAL_RUN = subprocess.run


def _claude_only_run(args, **kwargs):
    """Фейк только для `claude ...`; git и остальное — в настоящий
    `subprocess.run`. `doctor.subprocess` и `gitcmd.subprocess` — один
    модуль, безусловная глушилка душила и git-вызовы сверки свежести
    (образец — `tests/test_doctor.py::claude_only_run`; правка Оператора
    по эскалации T051, вопрос 2)."""
    if args and args[0] == "claude":
        return subprocess.CompletedProcess(list(args), 1, "", "")
    return REAL_RUN(args, **kwargs)


class DoctorWarnsLaggingActiveBranchTest(RealGitFreshnessTest):

    def setUp(self):
        super().setUp()
        self.initial_sha = self.main_head()
        # Ветка T001 (активная, из базовой песочницы) — на исходном коммите,
        # main дальше уходит вперёд без неё.
        self.git("branch", self.branch, self.initial_sha)
        for i in range(LAG_COMMITS):
            self.git("commit", "--allow-empty", "-q", "-m", f"main #{i}")

    def all_checks(self) -> list:
        """`doctor.all_checks` с подавленными внешними вызовами (CLI, живой
        смоук, keychain) — по образцу `tests/test_doctor.py` `healthy_mocks`,
        этому тесту важна только сверка свежести, не остальные проверки."""
        with mock.patch.object(runner.keychain, "token",
                              lambda slot: "tok-test"), \
                mock.patch.object(
                    doctor.subprocess, "run",
                    side_effect=_claude_only_run), \
                mock.patch.object(doctor.subprocess, "Popen",
                                  side_effect=FileNotFoundError):
            return doctor.all_checks(store.db())

    def test_ac5_active_task_far_behind_main_gets_a_warning(self):
        checks = self.all_checks()

        self.assertTrue(
            any(c.status == "warn" and self.TASK in c.detail for c in checks),
            f"активная задача {self.TASK}, отставшая от main на "
            f"{LAG_COMMITS} коммитов, обязана получить предупреждение "
            f"doctor; получено: {[(c.name, c.status, c.detail) for c in checks]}")

    def test_ac5_terminal_task_far_behind_main_is_not_warned(self):
        terminal_branch = "task/t002-zavershena"
        self.git("branch", terminal_branch, self.initial_sha)
        store.insert_task(store.db(), "T002", "Уже завершена задача", "done",
                          terminal_branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        checks = self.all_checks()

        self.assertFalse(
            any(c.status == "warn" and "T002" in c.detail for c in checks),
            "терминальная (done/killed) задача не должна получать "
            "предупреждение о свежести ветки, даже сильно отстав от main")


if __name__ == "__main__":
    unittest.main()
