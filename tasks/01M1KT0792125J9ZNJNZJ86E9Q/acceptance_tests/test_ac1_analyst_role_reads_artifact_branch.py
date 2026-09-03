"""AC-1 (tasks/01M1KT0792125J9ZNJNZJ86E9Q/SPEC.md): «Для задачи, заведённой
`cmd_new --tz` после A7 (артефактная ветка, кодовой ветки с `tasks/<id>/`
нет), `run` в состоянии `spec_writing` подключает роль analyst (TZ.md
найден в артефактной ветке), а не отвечает «SPEC пишет Оператор»».

Красен до реализации: `orchestrator/runner.py::step_role` (SPEC,
«Материалы», строки ~84-89) определяет наличие TZ.md через `t["branch"]`
(кодовая ветка задачи) — `gitcmd.on_foreign_branch(branch)` и диск
`config.TASKS` — и НИКОГДА не смотрит в артефактную ветку пульта
(`orchestrator/artifact_source.py::resolve`), где `cmd_new --tz` реально
коммитит TZ.md после A7. Тесты ниже кладут TZ.md ТОЛЬКО в артефактную
ветку и оставляют кодовую ветку задачи неотличимой от «ещё не заведена»
(реальный момент жизни задачи до первого шага роли, `gitcmd.branch_exists`
подтверждает предпосылку явно) — сегодняшний код его не находит.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import gitcmd, runner, store  # noqa: E402
from tests.sandbox import FakeProc  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

TZ_TEXT = "Хотим кнопку экспорта отчёта в CSV на странице задач.\n"


class _Ac1Sandbox(RealPultGitTest):
    """`RealPultGitTest.setUp` уже заводит `self.TASK` (`cmd_new` без
    `--tz`, target — self/артель) в состоянии `spec_writing`, с реальной
    артефактной веткой пульта (SPEC.md-заглушка уже там) — сюда остаётся
    только доложить TZ.md, которого `cmd_new` без `--tz` не создаёт."""

    def seed_tz(self) -> None:
        self._seed_artifact_branch(
            f"tasks/{self.TASK}/TZ.md", TZ_TEXT, f"{self.TASK}: TZ.md")

    def row(self):
        return store.get_task(store.db(), self.TASK)


class StepRoleReadsTzFromArtifactBranchTest(_Ac1Sandbox):

    def test_ac1_step_role_is_analyst_when_tz_only_on_artifact_branch(self):
        """TZ.md лежит только в артефактной ветке пульта (`artifact/<id>`,
        куда его реально кладёт `cmd_new --tz` после A7); кодовой ветки
        задачи (`t["branch"]`) в git ещё нет вовсе — типичный момент
        жизни только что заведённой задачи. `runner.step_role` обязан
        найти TZ.md через артефактную ветку и вернуть роль `"analyst"`,
        а не молчать «TZ.md не заведён».

        Ловит мутацию: если проверка наличия TZ.md останется только по
        `t["branch"]`/`gitcmd.on_foreign_branch`/диску `config.TASKS`
        (без обращения к артефактной ветке пульта), `has_tz` останется
        `False`, и метод вернёт `None` вместо `"analyst"`.
        """
        self.seed_tz()
        t = self.row()
        self.assertFalse(
            gitcmd.branch_exists(t["branch"]),
            "предпосылка сценария: кодовой ветки задачи ещё нет")

        self.assertEqual(runner.step_role(t), "analyst")


class RunStartsAnalystWithArtifactBranchTzTest(_Ac1Sandbox):

    def test_ac1_run_does_not_refuse_with_spec_writes_operator_message(self):
        """`run` полным путём (`runner.cmd_run`, публичный вход команды,
        не внутренняя функция) на задаче с TZ.md только в артефактной
        ветке не отказывает текстом «SPEC пишет Оператор» и реально
        запускает шаг analyst (агент подменён `FakeProc` — реальный
        процесс/сеть не используются).

        Ловит мутацию: тот же дефект `step_role`, но обнаруженный через
        публичную команду `run`, а не через внутреннюю функцию напрямую —
        ловит и регрессию, если кто-то продублирует старую проверку TZ.md
        отдельно внутри `_cmd_run`, обойдя исправленный `step_role`.
        """
        self.seed_tz()

        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            try:
                self.capture(runner.cmd_run, self.TASK)
            except SystemExit as exc:
                self.fail(f"run отказал: {exc}")

        popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
