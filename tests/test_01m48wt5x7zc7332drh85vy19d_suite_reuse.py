"""Повторное использование полного прогона по содержимому дерева.

Группа: долгоживущий
Красен до реализации: full_suite каждый раз зовёт run_full_suite, запись не содержит полного итога и в config нет FULL_SUITE_REUSE_MAX_AGE_SEC.
"""

import json
import os
import random
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, artel, config, fsm, store, workspace
from tests.sandbox import (LightTransitionSandbox, RealGitSandbox,
                           network_guarded_real_run)


RED = ("========== short test summary info ==========\n"
       "FAILED tests/test_x.py::test_x - AssertionError: x\n"
       "========== 1 failed, 2 passed in 0.10s ==========\n")
GREEN = "========== 3 passed in 0.10s ==========\n"
NODE = "tests/test_x.py::test_x"


class SuiteReuseTest(RealGitSandbox):
    """Временный git-репозиторий и подмена публичного запуска pytest."""

    def test_ac5_tracked_change_invalidates_result(self):
        """После красного прогона меняется один отслеживаемый файл; следующий запуск видит новое дерево.

        Ловит мутацию: ключ берётся из HEAD и игнорирует незакоммиченную правку — второй запуск не зовёт run_full_suite.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        with mock.patch.object(acceptance, "run_full_suite", side_effect=[(False, RED), (True, GREEN)]) as run:
            acceptance.full_suite(self.root, "TREE")
            (self.root / "marker.txt").write_text(f"{rng.getrandbits(128)}\n", encoding="utf-8")
            result = acceptance.full_suite(self.root, "TREE")
        self.assertEqual(run.call_count, 2, f"зерно {seed}: правка дерева не вызвала прогон")
        self.assertTrue(result.green)

    def test_ac4_same_uncommitted_tree_in_scratch_reuses_green_result(self):
        """Два worktree с одинаковой наложенной правкой дают один зелёный итог и ссылку на него.

        Ловит мутацию: ключ берётся из HEAD вместо содержимого scratch — второй worktree снова запускает pytest.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        scratch = self.root.parent / f"scratch-{seed}"
        self.git("worktree", "add", "-q", "--detach", str(scratch), config.MAIN_BRANCH)
        self.addCleanup(lambda: self.git("worktree", "remove", "--force", str(scratch)))
        applied = f"{seed} приложение\n"
        for root in (self.root, scratch):
            (root / "marker.txt").write_text(applied, encoding="utf-8")
        with mock.patch.object(acceptance, "run_full_suite", return_value=(True, GREEN)) as run:
            first = acceptance.full_suite(self.root, "GREEN")
            second = acceptance.full_suite(scratch, "GREEN")
        self.assertEqual(run.call_count, 1, f"зерно {seed}: совпадающие деревья прогнаны дважды")
        self.assertTrue(first.green and second.green)
        self.assertIn("использован повторно", second.detail)

    def test_ac6_command_change_invalidates_result(self):
        """На одном дереве два профиля запуска различаются командой pytest.

        Ловит мутацию: отпечаток команды не входит в ключ — второй профиль берёт чужой красный итог.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        first = ["python3", "-m", "pytest", f"--maxfail={rng.randrange(1, 5)}"]
        second = [*first, "-q"]
        with mock.patch.object(acceptance, "run_full_suite", side_effect=[(False, RED), (True, GREEN)]) as run:
            acceptance.full_suite(self.root, "ENV", command=first)
            result = acceptance.full_suite(self.root, "ENV", command=second)
        self.assertEqual(run.call_count, 2, f"зерно {seed}: команды {first}, {second}")
        self.assertTrue(result.green)

    def test_ac7_age_boundary(self):
        """Повтор в пределах срока берёт сохранённый итог, после срока запускает pytest снова.

        Ловит мутацию: проверка возраста пропущена либо сравнение на границе перевёрнуто — число запусков отличается.
        """
        with mock.patch.object(acceptance, "run_full_suite", side_effect=[(False, RED), (True, GREEN)]) as run:
            with mock.patch.object(time, "time", return_value=1_000_000):
                first = acceptance.full_suite(self.root, "AGE")
            with mock.patch.object(time, "time", return_value=1_000_000 + config.FULL_SUITE_REUSE_MAX_AGE_SEC):
                same = acceptance.full_suite(self.root, "AGE")
            self.assertEqual(run.call_count, 1)
            self.assertEqual(same.digest, first.digest)
            with mock.patch.object(time, "time", return_value=1_000_001 + config.FULL_SUITE_REUSE_MAX_AGE_SEC):
                fresh = acceptance.full_suite(self.root, "AGE")
        self.assertEqual(run.call_count, 2)
        self.assertTrue(fresh.green)

    def test_ac8_incomplete_runs_are_not_reused(self):
        """Таймаут, незапущенный прогон, отсутствие набора и вывод без сводки не становятся итогами.

        Ловит мутацию: один из незавершённых исходов сохраняется — на повторе run_full_suite не вызывается.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        outcomes = [
            (False, f"полный набор tests/ не уложился в {config.FULL_SUITE_TIMEOUT_SEC} с"),
            (False, "прогон не начат: машина занята"),
            (False, acceptance.FULL_SUITE_NO_TESTS_NOTE),
            (False, "ImportError: xdist\n"),
        ]
        random.Random(seed).shuffle(outcomes)
        for index, incomplete in enumerate(outcomes):
            with self.subTest(index=index, seed=seed):
                (self.root / "marker.txt").write_text(f"case {seed} {index}\n", encoding="utf-8")
                self.git("add", "marker.txt")
                self.git("commit", "-q", "-m", f"case-{index}")
                with mock.patch.object(acceptance, "run_full_suite", side_effect=[incomplete, (True, GREEN)]) as run:
                    acceptance.full_suite(self.root, f"INCOMPLETE-{index}")
                    acceptance.full_suite(self.root, f"INCOMPLETE-{index}")
                self.assertEqual(run.call_count, 2, f"зерно {seed}, исход {incomplete}")

    def test_ac9_non_repository_falls_back_to_run(self):
        """Каталог без git не даёт достоверный ключ, но исход обоих прогонов определяется pytest.

        Ловит мутацию: ошибка git принимается за постоянный пустой ключ — второй вызов берёт первый исход.
        """
        with tempfile.TemporaryDirectory() as other_dir:
            other = Path(other_dir)
            with mock.patch.object(acceptance, "run_full_suite", side_effect=[(False, RED), (True, GREEN)]) as run:
                first = acceptance.full_suite(other, "NOGIT")
                second = acceptance.full_suite(other, "NOGIT")
        self.assertEqual(run.call_count, 2)
        self.assertFalse(first.green)
        self.assertTrue(second.green)

    def test_ac10_untracked_file_prevents_save(self):
        """Посторонний неотслеживаемый файл не входит в дерево git и запрещает сохранение итога.

        Ловит мутацию: проверка untracked пропущена — второй вызов берёт первый красный результат.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        (self.root / f"untracked_{seed}.txt").write_text("не в индексе\n", encoding="utf-8")
        with mock.patch.object(acceptance, "run_full_suite", side_effect=[(False, RED), (True, GREEN)]) as run:
            acceptance.full_suite(self.root, "UNTRACKED")
            result = acceptance.full_suite(self.root, "UNTRACKED")
        self.assertEqual(run.call_count, 2, f"зерно {seed}: посторонний файл не заблокировал reuse")
        self.assertTrue(result.green)

    def test_ac12_suite_run_record_is_not_gate_result(self):
        """Запись suite-run для совпадающего коммита не заменяет прогон гейта.

        Ловит мутацию: читатель гейта не различает источник записи — гейт берёт результат suite-run без запуска.
        """
        sha = self.git("rev-parse", "HEAD").strip()
        acceptance.save_failures(sha, [NODE], "suite-run")
        with mock.patch.object(acceptance, "run_full_suite", return_value=(True, GREEN)) as run:
            result = acceptance.full_suite(self.root, "SOURCE")
        run.assert_called_once()
        self.assertTrue(result.green)

    def test_ac13_record_has_complete_result(self):
        """Красный и зелёный прогоны сохраняют ключ, время, исход, сводку, упавшие тесты и лог.

        Ловит мутацию: из записи выпало одно из полей — её нельзя безопасно повторить или объяснить Оператору.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        cases = [(False, RED, "1 failed, 2 passed", r"red|красн"),
                 (True, GREEN, "3 passed", r"green|зел")]
        random.Random(seed).shuffle(cases)
        for index, (green, output, summary, outcome) in enumerate(cases):
            with self.subTest(index=index, seed=seed):
                (self.root / "marker.txt").write_text(f"{seed}:{index}\n", encoding="utf-8")
                self.git("add", "marker.txt")
                self.git("commit", "-q", "-m", f"case-{index}")
                before = time.time()
                with mock.patch.object(acceptance, "run_full_suite", return_value=(green, output)):
                    run = acceptance.full_suite(self.root, f"RECORD-{index}")
                records = [json.loads(p.read_text(encoding="utf-8"))
                           for p in acceptance.suite_results_dir().glob("*.json")]
                matching = [r for r in records if str(run.log_path) in str(r)
                            and summary in str(r)]
                self.assertTrue(matching, f"зерно {seed}: {records}")
                record = matching[0]
                self.assertRegex(str(record), r"[0-9a-f]{40}")
                times = []
                for value in record.values():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        times.append(float(value))
                    elif isinstance(value, str):
                        try:
                            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                            times.append(parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp())
                        except ValueError:
                            pass
                self.assertTrue(any(before <= value <= time.time() for value in times),
                                f"зерно {seed}: {record}")
                self.assertIn(str(run.log_path), str(record))
                self.assertRegex(str(record).lower(), outcome)
                if not green:
                    self.assertIn(NODE, str(record))


class ApproveReuseTest(LightTransitionSandbox):
    """Публичный approve на задаче в acceptance после сохранённого прогона."""

    def setUp(self):
        super().setUp()
        self.set_state("acceptance")
        self.wt_path.mkdir(exist_ok=True)
        for args in (("init", "-q", "-b", config.MAIN_BRANCH),
                     ("config", "user.email", "suite@example.invalid"),
                     ("config", "user.name", "suite test"),
                     ("add", "-A")):
            result = network_guarded_real_run(["git", "-C", str(self.wt_path), *args],
                                              capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        (self.wt_path / "marker.txt").write_text("fixture\n", encoding="utf-8")
        for args in (("add", "marker.txt"), ("commit", "-q", "-m", "fixture")):
            result = network_guarded_real_run(["git", "-C", str(self.wt_path), *args],
                                              capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

        def real_worktree_git(repo, *args):
            if Path(repo) != self.wt_path:
                return None
            return network_guarded_real_run(["git", "-C", str(repo), *args],
                                            capture_output=True, text=True)

        self.in_repo_handlers.insert(0, real_worktree_git)
        for target, name, value in (
            (fsm, "confirm_fixation", True),
            (workspace, "on_task_branch", True),
            (workspace, "path", self.wt_path),
        ):
            patcher = mock.patch.object(target, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_ac1_approve_reuses_autogate_failure(self):
        """После красного прогона на дереве approve отказывает с тем же тестом и сводкой без нового запуска.

        Ловит мутацию: approve игнорирует сохранённый итог — run_full_suite вызывается второй раз.
        """
        with mock.patch.object(acceptance, "run_full_suite", return_value=(False, RED)) as run:
            acceptance.full_suite(self.wt_path, self.TASK)
            output = self.capture(lambda: fsm.cmd_approve(self.TASK))
        self.assertEqual(run.call_count, 1, output)
        self.assertEqual(self.state(), "acceptance")
        self.assertIn(NODE, output)
        self.assertIn("1 failed, 2 passed", output)

    def test_ac2_approve_refusal_names_original_result(self):
        """Повторный отказ approve называет время первого прогона, дерево и его лог в выводе и журнале.

        Ловит мутацию: повтор берёт исход, но теряет происхождение — в журнале остаётся только новый отказ без исходного лога.
        """
        with mock.patch.object(acceptance, "run_full_suite", return_value=(False, RED)) as run:
            original = acceptance.full_suite(self.wt_path, self.TASK)
            output = self.capture(lambda: fsm.cmd_approve(self.TASK))
        tree = network_guarded_real_run(
            ["git", "-C", str(self.wt_path), "rev-parse", "HEAD^{tree}"],
            capture_output=True, text=True).stdout.strip()
        journal = "\n".join(str(row["detail"] or "") for row in
                            store.task_steps(store.db(), self.TASK))
        self.assertEqual(run.call_count, 1, output)
        for surface in (output, journal):
            self.assertRegex(surface, r"итог прогона .+ дерево .+ лог .+ — использован повторно")
            self.assertIn(tree, surface)
            self.assertIn(str(original.log_path), surface)

    def test_ac3_accept_red_uses_same_failure_and_records_reason(self):
        """Оператор принимает сохранённую красноту; журнал сохраняет основание и тот же упавший тест.

        Ловит мутацию: accept-red проводит приёмку, но повторно запускает pytest либо теряет основание и сводку в журнале.
        """
        reason = "осознанно принимаю красноту базы"
        with mock.patch.object(acceptance, "run_full_suite", return_value=(False, RED)) as run:
            acceptance.full_suite(self.wt_path, self.TASK)
            self.capture(lambda: fsm.cmd_approve(self.TASK, accept_red=reason))
        journal = "\n".join(str(row["detail"] or "") for row in
                            store.task_steps(store.db(), self.TASK))
        self.assertEqual(run.call_count, 1, journal)
        self.assertEqual(self.state(), "merge_gate")
        self.assertIn(reason, journal)
        self.assertIn(NODE, journal)
        self.assertIn("1 failed, 2 passed", journal)

    def test_ac11_fresh_flag_replaces_saved_result(self):
        """Флаг approve принуждает новый прогон и сохраняет его зелёный исход для следующего гейта.

        Ловит мутацию: флаг разбирается, но игнорируется — approve снова видит старую красноту или новый итог не заменяет старый.
        """
        with mock.patch.object(acceptance, "run_full_suite",
                               side_effect=[(False, RED), (True, GREEN),
                                            (False, RED)]) as run:
            acceptance.full_suite(self.wt_path, self.TASK)
            with mock.patch.object(sys, "argv", ["artel.py", "approve", self.TASK,
                                                  "--fresh-suite"]), \
                 mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}):
                output = self.capture(artel.main)
            self.assertEqual(run.call_count, 2, output)
            self.assertEqual(self.state(), "merge_gate", output)
            next_gate = acceptance.full_suite(self.wt_path, self.TASK)
        self.assertTrue(next_gate.green)
        self.assertEqual(run.call_count, 2, next_gate.detail)
