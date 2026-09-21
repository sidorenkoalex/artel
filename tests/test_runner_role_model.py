"""Юнит-тесты флага `--model` в команде шага и `model=` в журнале «agent
run started» (SPEC 01M2DTT96FS25SHXP0HDTWARQH, требования 3-5; SPEC
01M3009Y9AGGY6ZCFA7H1HJ1TD, требования 5, 9).

Постоянная копия части покрытия приёмочной планки задачи (`tasks/
01M2DTT96FS25SHXP0HDTWARQH/acceptance_tests/test_ac3_ac4_command_flag.py`,
`test_ac5_ac6_journal_model_field.py`) — та планка уходит при следующей
чистке каталога задачи, этот файл остаётся регрессией `tests/`. Тот же
приём песочницы, что `tests/test_step_cost.py::CmdRunCostTest`: реального
`claude` CLI нет, `subprocess.Popen` подменён `FakeProc`.

Модель шага с 20.09 — результат разрешения цепочки «роль -> ярус ->
модель» (`orchestrator/models.py`), поэтому карта исполнителей под тестом
задаёт РОЛИ ЯРУС, а модель яруса — локальный слой песочницы. Прежний
сценарий «поле `model:` не задано — дефолт CLI и предупреждение» заменён
сценарием «ярус не задан — отказ до старта агента»: требование 5 сняло
молчаливый дефолт.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, gitcmd, runner, store  # noqa: E402
from tests.sandbox import (DeveloperBriefTmpRootTest as TmpRootTest,  # noqa: E402
                           FakeProc, capture_new_task_id, event, fake_git,
                           sync_spec_from_worktree)

REPO_ROOT = Path(__file__).resolve().parent.parent
_REAL_ROLES_TEXT = (REPO_ROOT / "roles.yaml").read_text(encoding="utf-8")


def result_event(usd=0.1, **fields) -> str:
    return event(type="result", subtype="success", is_error=False,
                result="готово", total_cost_usd=usd, **fields)


def _roles_yaml_text(role: str, tier: str | None) -> str:
    """Реальный `roles.yaml` репозитория, с `model_tier:` вставленным под
    заголовком роли (или без вставки — `tier=None`, сценарий «ярус не
    задан»); `skills:`/`token_slot:` реальных ролей не трогаются.

    Строки `model:`/`model_tier:` этой роли снимаются перед вставкой:
    боевой `roles.yaml` несёт `model:` до применения приложения к PLAN
    задачи 01M3009Y9AGGY6ZCFA7H1HJ1TD, и без снятия сценарий «поле не
    задано» был бы неотличим от боевого (правка Оператора 19.09,
    amend-tests).
    """
    lines = _REAL_ROLES_TEXT.splitlines(keepends=True)
    anchor = f"  {role}:\n"
    for i, line in enumerate(lines):
        if line == anchor:
            j = i + 1
            while j < len(lines) and lines[j].startswith("    "):
                if lines[j].lstrip().startswith(("model:", "model_tier:")):
                    del lines[j]
                    continue
                j += 1
            if tier is not None:
                lines[i] = line + f"    model_tier: {tier}\n"
            break
    else:
        raise AssertionError(f"роль {role!r} не найдена в roles.yaml")
    return "".join(lines)


class ModelFlagJournalTest(TmpRootTest):
    """Один прогон `runner.cmd_run` (роль developer) с управляемым
    `roles.yaml`: argv команды и журнал шага."""

    def setUp(self):
        super().setUp()
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Модель роли")
        sync_spec_from_worktree(self.TASK)
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()
        tdir = config.WORKTREES / self.TASK / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "PLAN.md").write_text("маркер\n", encoding="utf-8")

        patcher = mock.patch.object(runner.time, "sleep", lambda _: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def set_tier(self, tier: str | None) -> None:
        path = self.root / "roles-under-test.yaml"
        path.write_text(_roles_yaml_text("developer", tier), encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_tier_model(self, tier: str, model: str) -> None:
        """Модель яруса в локальном слое песочницы: модель шага задаёт
        он, а не карта исполнителей."""
        config.MODELS_LOCAL.write_text(f"tiers:\n  {tier}: {model}\n",
                                       encoding="utf-8")

    def run_agent(self, expect_exit: bool = False) -> mock.Mock:
        """Один прогон шага. `expect_exit` — сценарий отказа до старта
        агента (`sys.exit`, как его увидел бы `auto`): исключение
        перехватывается, чтобы тест смотрел журнал, а не падал сам."""
        proc = FakeProc([result_event(usd=0.1)])
        with mock.patch.object(runner, "spawn_agent", return_value=proc) as popen:
            if expect_exit:
                with self.assertRaises(SystemExit):
                    self.capture(runner.cmd_run, self.TASK)
            else:
                self.capture(runner.cmd_run, self.TASK)
        return popen

    def journal_details(self, action: str) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action)).fetchall()]

    def all_step_rows(self) -> list:
        return store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()

    def test_command_carries_the_model_flag_once_in_prior_flag_order(self):
        """Ловит мутацию: `--model` добавляется дважды, значение — не то
        роли, либо вставка сдвигает порядок существующих флагов."""
        self.set_tier("strong")
        self.set_tier_model("strong", "claude-opus-5")

        argv = self.run_agent().call_args.args[0]

        self.assertEqual(argv.count("--model"), 1, argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-opus-5")
        known_flags = ("--permission-mode", "--output-format",
                      "--allowedTools", "--setting-sources",
                      "--strict-mcp-config")
        positions = [argv.index(f) for f in known_flags]
        self.assertEqual(positions, sorted(positions), argv)

    def test_model_comes_from_the_tier_of_the_local_layer_not_the_roles_map(self):
        """Ловит мутацию: модель читается из `roles.yaml` (как до 20.09)
        — смена модели яруса в локальном слое пульта не меняла бы ничего,
        и оба файла задавали бы модель одновременно."""
        self.set_tier("strong")
        self.set_tier_model("strong", "claude-sonnet-5")

        argv = self.run_agent().call_args.args[0]

        self.assertEqual(argv[argv.index("--model") + 1], "claude-sonnet-5")

    def test_role_without_a_tier_refuses_before_the_agent_starts(self):
        """Ловит мутацию: роль без `model_tier` идёт на дефолт CLI —
        прежнее молчаливое поведение, снятое требованием 5: агент
        стартовал бы без явной модели."""
        self.set_tier(None)

        spawn = self.run_agent(expect_exit=True)

        spawn.assert_not_called()
        actions = [r["action"] for r in self.all_step_rows()]
        self.assertIn(runner.MODEL_UNRESOLVED_REFUSAL_ACTION, actions)
        self.assertNotIn("agent run started", actions)

    def test_run_started_journal_carries_the_model(self):
        """Ловит мутацию: запись «agent run started» не несёт `model=`
        вовсе, либо несёт значение, отличное от разрешённой моделью
        яруса."""
        self.set_tier("strong")
        self.set_tier_model("strong", "claude-opus-5")

        self.run_agent()

        details = self.journal_details("agent run started")
        self.assertEqual(len(details), 1)
        self.assertIn("model=claude-opus-5", details[0])


if __name__ == "__main__":
    unittest.main()
