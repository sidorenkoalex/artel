"""Канарейка пропускает полный набор только на приёмке своего клона.

Группа: долгоживущий
Красен до реализации: клон ещё не включает признак пропуска, а автогейт всегда зовёт полный набор.
"""

import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, budget, canary, catalog, config,
                          fixation, fsm, gates, lease, store, workspace)
from tests.sandbox import RealGitSandbox, capture


class CanaryCloneSkipTest(RealGitSandbox):
    """Команда работает с учебным git-клоном и подменённым процессом ведения."""

    def setUp(self):
        super().setUp()
        seed = random.randrange(1 << 32)
        print(f"зерно: {seed}")
        self.seed = seed
        entry = self.root / "orchestrator" / "canary_drive.py"
        entry.parent.mkdir(parents=True)
        entry.write_text("# учебный вход\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "учебный вход")
        self.target = self.git("rev-parse", "HEAD").strip()
        self.home = self.root / "fixture-home"
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir(parents=True)
        self.template = pool / "fixture.md"
        self.template.write_text("# Учебная задача\n", encoding="utf-8")
        self.real_popen = subprocess.Popen

    def _run(self, steps, *, error=False):
        before = {name: value for name, value in vars(config).items()
                  if isinstance(value, bool) and name.isupper()}
        inside = []

        def fake_popen(argv, *args, **kwargs):
            if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
                return self.real_popen(argv, *args, **kwargs)
            inside.append({name: value for name, value in vars(config).items()
                           if isinstance(value, bool) and name.isupper()})
            if error:
                raise RuntimeError("учебный сбой процесса")
            result_path = Path(argv[argv.index("--result") + 1])
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(json.dumps({
                "task_id": "01FIXTURE", "head": self.target,
                "outcome": "killed", "escalated": False,
                "metrics": {"steps": 3, "cost_usd": 0.0,
                            "review_iterations": 0, "escalations": [],
                            "dev_retries": 0, "outcome": "killed",
                            "kill_note": "штатно", "test_author_visited": False,
                            "ceiling_exhausted": False,
                            "ceiling_raise": None},
                "steps": steps,
            }, ensure_ascii=False), encoding="utf-8")
            kwargs["stdout"].write("учебный процесс завершён\n")

            class FinishedProcess:
                def wait(self, timeout=None):
                    return 0

            return FinishedProcess()

        with mock.patch.object(Path, "home", return_value=self.home), \
                mock.patch.object(catalog, "cmd_init"), \
                mock.patch.object(subprocess, "Popen", fake_popen):
            if error:
                try:
                    capture(lambda: canary.cmd_canary(
                        k=1, sha=self.target, templates=[self.template.stem]))
                except RuntimeError as exc:
                    self.assertIn("учебный сбой", str(exc))
                else:
                    self.fail("учебное исключение потеряно")
                row = None
            else:
                capture(lambda: canary.cmd_canary(
                    k=1, sha=self.target, templates=[self.template.stem]))
                row = store.db().execute(
                    "SELECT * FROM canary_runs ORDER BY id DESC LIMIT 1").fetchone()
        after = {name: value for name, value in vars(config).items()
                 if isinstance(value, bool) and name.isupper()}
        self.assertTrue(inside, f"зерно: {self.seed}; процесс не вызван")
        return before, inside[0], after, row

    def test_ac1_clone_flag_restored_on_both_exits(self):
        """Учебный клон видит включённый признак, а оба выхода возвращают исходное значение.

        Ловит мутацию: клон не включает признак или забывает восстановить
        его после исключения — в снимках конфигурации различается значение.
        """
        for error in (False, True):
            with self.subTest(error=error):
                before, inside, after, _ = self._run([], error=error)
                changed = [name for name, value in before.items()
                           if value is False and inside.get(name) is True]
                self.assertTrue(changed, f"зерно: {self.seed}; {before} -> {inside}")
                self.assertEqual(before, after, f"зерно: {self.seed}; {after}")

    def test_ac4_skip_is_not_refusal_and_other_refusal_keeps_verdict(self):
        """Учебный результат с пропуском и с настоящим отказом сохраняет прежний вердикт.

        Ловит мутацию: запись о пропуске ошибочно становится причиной
        отказа либо настоящий отказ теряется из строки БД или красит вердикт.
        """
        skip = "полный набор пропущен: канарейка проверяет конвейер, код целевого sha проверяет CI main"
        steps = [
            {"ts": "2026-10-07T00:00:00Z", "actor": "fsm",
             "action": "state -> acceptance", "detail": ""},
            {"ts": "2026-10-07T00:00:01Z", "actor": "fsm",
             "action": "полный набор пропущен", "detail": skip},
            {"ts": "2026-10-07T00:00:02Z", "actor": "autogate",
             "action": "state -> merge_gate", "detail": ""},
        ]
        _, _, _, passed = self._run(steps)
        self.assertIsNone(passed["autogate_refusal"], f"зерно: {self.seed}; {dict(passed)}")
        self.assertEqual(passed["verdict"], "green", f"зерно: {self.seed}")
        reason = "иной отказ учебного автогейта"
        steps[1] = {"ts": "2026-10-07T00:00:01Z", "actor": "fsm",
                    "action": "автогейт acceptance не пройден", "detail": reason}
        steps[2]["actor"] = "canary"
        _, _, _, refused = self._run(steps)
        self.assertEqual(refused["autogate_refusal"], reason,
                         f"зерно: {self.seed}; {dict(refused)}")
        self.assertEqual(refused["verdict"], "green", f"зерно: {self.seed}")


class AutogateSkipTest(RealGitSandbox):
    """Автогейт проходит реальный переход с учебными ветками и подменённым набором."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        rng = random.Random(self.seed)
        self.task_id = f"T{rng.randrange(1 << 72):018X}"
        self.branch = f"task/{self.task_id.lower()}"
        docs_branch = f"artifact/{self.task_id.lower()}"
        code_rel = "tests/test_fixture_plank.py"
        self.git("checkout", "-q", "-b", self.branch)
        code_text = ('"""Учебная планка."""\nimport unittest\n'
                     'class Plank(unittest.TestCase):\n'
                     '    def test_ac1_fixture(self):\n'
                     '        self.assertEqual(2 + 2, 4)\n')
        code_path = self.root / code_rel
        code_path.parent.mkdir(parents=True, exist_ok=True)
        code_path.write_text(code_text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "учебная планка")
        self.git("checkout", "-q", "-b", docs_branch)
        self.git("symbolic-ref", f"refs/artifacts/{self.task_id}",
                 f"refs/heads/{docs_branch}")
        tdir = config.TASKS / self.task_id
        acc = tdir / "acceptance_tests"
        acc.mkdir(parents=True, exist_ok=True)
        (tdir / "REVIEW.md").write_text(
            "---\n" + f"task: {self.task_id}\n" +
            "type: review\nauthor_role: reviewer\nstatus: approved\n"
            "iteration: 1\nschema_version: 2\n---\n\n# REVIEW\n",
            encoding="utf-8")
        digest = hashlib.sha256(code_text.encode("utf-8")).hexdigest()
        (acc / "long_lived.sha256.txt").write_text(
            f"{digest}  {code_rel}\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "учебные документы")
        lock_sha = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", self.branch)
        conn = store.db()
        store.insert_task(conn, self.task_id, "Проверка автогейта", "review",
                          self.branch, config.DEFAULT_TARGET, 10.0)
        store.update_task(conn, self.task_id, tests_locked_sha=lock_sha)
        patches = [
            mock.patch.object(fsm, "guard_refuses", return_value=False),
            mock.patch.object(fixation, "read", return_value=("", True)),
            mock.patch.object(fixation, "approve_sha_hint", return_value=""),
            mock.patch.object(store, "record_fixation", return_value=None),
            mock.patch.object(gates, "policy", return_value=gates.AUTO),
            mock.patch.object(workspace, "on_task_branch", return_value=True),
            mock.patch.object(workspace, "path", return_value=self.root),
            mock.patch.object(budget, "budget_block", return_value=None),
            mock.patch.object(lease, "run_locked",
                              side_effect=lambda conn, task, sid, fn,
                                                 **kwargs: fn("test-session")),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def _flag_name(self):
        # Имя признака не задано критерием: берём булеву перемену клона.
        entry = self.root / "orchestrator" / "canary_drive.py"
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# учебный вход\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "учебный вход")
        home = self.root / "fixture-home"
        pool = home / config.CANARY_POOL_DIRNAME
        pool.mkdir(parents=True)
        (pool / "fixture.md").write_text("# Учебная задача\n", encoding="utf-8")
        before = {name: value for name, value in vars(config).items()
                  if isinstance(value, bool) and name.isupper()}
        seen = []
        real_popen = subprocess.Popen

        def fake_popen(argv, *args, **kwargs):
            if list(argv[:3]) != [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
                return real_popen(argv, *args, **kwargs)
            seen.append({name: value for name, value in vars(config).items()
                         if isinstance(value, bool) and name.isupper()})
            raise RuntimeError("учебная остановка до ведения")

        with mock.patch.object(Path, "home", return_value=home), \
                mock.patch.object(catalog, "cmd_init"), \
                mock.patch.object(subprocess, "Popen", fake_popen):
            with self.assertRaisesRegex(RuntimeError, "учебная остановка"):
                capture(lambda: canary.cmd_canary(k=1,
                    sha=self.git("rev-parse", "HEAD").strip(),
                    templates=["fixture"]))
        names = [name for name, value in before.items()
                 if value is False and seen and seen[0].get(name) is True]
        self.assertTrue(names, f"зерно: {self.seed}; признак не включён")
        return names

    def test_ac2_enabled_flag_skips_suite_and_journals_reason(self):
        """Включённый признак ведёт учебную задачу через автогейт без вызова набора.

        Ловит мутацию: автогейт всё же вызывает full_suite, забывает строку
        пропуска или останавливает переход вместо продолжения приёмки.
        """
        names = self._flag_name()
        with mock.patch.multiple(config, **{name: True for name in names}), \
                mock.patch.object(acceptance, "full_suite") as suite:
            out = capture(fsm.cmd_advance, self.task_id)
        suite.assert_not_called()
        self.assertEqual(store.get_task(store.db(), self.task_id)["state"],
                         "merge_gate", f"зерно: {self.seed}; {out}")
        detail = "\n".join(row["detail"] or "" for row in
                           store.task_steps(store.db(), self.task_id))
        self.assertIn("полный набор пропущен: канарейка проверяет конвейер, код целевого sha проверяет CI main",
                      detail, f"зерно: {self.seed}; {detail}")

    def test_ac3_disabled_flag_runs_suite_on_ordinary_path(self):
        """Обычная задача с выключенным признаком вызывает набор и сохраняет ручной approve.

        Ловит мутацию: условие пропуска применяется и вне клона — полный
        набор не вызывается, а approve наследует канареечный обход.
        """
        names = self._flag_name()
        green = acceptance.FullSuiteRun(
            True, acceptance.FULL_SUITE_GREEN, "зелёный", None, "зелёный прогон")
        with mock.patch.multiple(config, **{name: False for name in names}), \
                mock.patch.object(acceptance, "full_suite", return_value=green) as suite:
            out = capture(fsm.cmd_advance, self.task_id)
        suite.assert_called_once()
        self.assertEqual(store.get_task(store.db(), self.task_id)["state"],
                         "merge_gate", f"зерно: {self.seed}; {out}")
        store.update_task(store.db(), self.task_id, state="acceptance")
        red = acceptance.FullSuiteRun(
            False, acceptance.FULL_SUITE_RED, "красный", None, "учебный отказ")
        with mock.patch.multiple(config, **{name: False for name in names}), \
                mock.patch.object(acceptance, "full_suite", return_value=red) as suite:
            approve_out = capture(fsm.cmd_approve, self.task_id)
        suite.assert_called_once()
        self.assertEqual(store.get_task(store.db(), self.task_id)["state"],
                         "acceptance", f"зерно: {self.seed}; {approve_out}")
