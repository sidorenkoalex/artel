"""Юнит-тесты флага `--model` в команде шага и `model=` в журнале «agent
run started» (SPEC 01M2DTT96FS25SHXP0HDTWARQH, требования 3-5).

Постоянная копия части покрытия приёмочной планки задачи (`tasks/
01M2DTT96FS25SHXP0HDTWARQH/acceptance_tests/test_ac3_ac4_command_flag.py`,
`test_ac5_ac6_journal_model_field.py`) — та планка уходит при следующей
чистке каталога задачи, этот файл остаётся регрессией `tests/`. Тот же
приём песочницы, что `tests/test_step_cost.py::CmdRunCostTest`: реального
`claude` CLI нет, `subprocess.Popen` подменён `FakeProc`.
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


def _roles_yaml_text(role: str, model: str | None) -> str:
    """Реальный `roles.yaml` репозитория, с `model:` вставленной под
    заголовком роли (или без вставки — `model=None`); `skills:`/
    `token_slot:` реальных ролей не трогаются."""
    lines = _REAL_ROLES_TEXT.splitlines(keepends=True)
    anchor = f"  {role}:\n"
    for i, line in enumerate(lines):
        if line == anchor:
            # Реальный roles.yaml с 13.09 (коммит Оператора d4e80604) уже
            # несёт `model:` у ролей — существующую строку снять, иначе
            # сценарий «поле не задано» неотличим от боевого (правка
            # Оператора 19.09, amend-tests).
            j = i + 1
            while j < len(lines) and lines[j].startswith("    "):
                if lines[j].lstrip().startswith("model:"):
                    del lines[j]
                    break
                j += 1
            if model is not None:
                lines[i] = line + f"    model: {model}\n"
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

    def set_model(self, model: str | None) -> None:
        path = self.root / "roles-under-test.yaml"
        path.write_text(_roles_yaml_text("developer", model), encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_agent(self) -> mock.Mock:
        proc = FakeProc([result_event(usd=0.1)])
        with mock.patch.object(runner, "spawn_agent", return_value=proc) as popen:
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
        self.set_model("claude-opus-5")

        argv = self.run_agent().call_args.args[0]

        self.assertEqual(argv.count("--model"), 1, argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-opus-5")
        known_flags = ("--permission-mode", "--output-format",
                      "--allowedTools", "--setting-sources",
                      "--strict-mcp-config")
        positions = [argv.index(f) for f in known_flags]
        self.assertEqual(positions, sorted(positions), argv)

    def test_command_has_no_model_flag_and_warns_once_when_unset(self):
        """Ловит мутацию: `--model` подставляется безусловно, либо
        предупреждение не пишется/пишется больше одного раза, либо
        отсутствие поля останавливает/проваливает шаг."""
        self.set_model(None)

        argv = self.run_agent().call_args.args[0]

        self.assertNotIn("--model", argv)
        rows = self.all_step_rows()
        warnings = [r for r in rows
                   if "модель роли не задана — дефолт CLI" in r["detail"]]
        self.assertEqual(len(warnings), 1, rows)
        self.assertFalse(
            any(r["action"] in ("agent run FAILED", "agent run SKIPPED",
                                "agent run TIMEOUT") for r in rows), rows)

    def test_run_started_journal_carries_the_model(self):
        """Ловит мутацию: запись «agent run started» не несёт `model=`
        вовсе, либо несёт значение, отличное от `roles.yaml`."""
        self.set_model("claude-opus-5")

        self.run_agent()

        details = self.journal_details("agent run started")
        self.assertEqual(len(details), 1)
        self.assertIn("model=claude-opus-5", details[0])

    def test_run_started_journal_uses_the_default_marker_when_unset(self):
        """Ловит мутацию: поле не задано, но запись несёт `model=None`/
        пустую строку вместо литерала «дефолт CLI»."""
        self.set_model(None)

        self.run_agent()

        details = self.journal_details("agent run started")
        self.assertEqual(len(details), 1)
        self.assertIn("model=дефолт CLI", details[0])


if __name__ == "__main__":
    unittest.main()
