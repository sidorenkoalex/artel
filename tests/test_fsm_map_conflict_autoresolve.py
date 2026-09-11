"""Юнит-тесты авторазрешения конфликта подтяжки, где единственный
конфликтующий файл — `docs/codebase-map.md` (SPEC T067) —
`orchestrator/fsm.py::_conflicting_files`/`_auto_resolve_map_conflict`,
подключённые внутрь `_pull_main_or_escalate`.

Полный прогон РЕАЛЬНОГО git и РЕАЛЬНОГО `scripts/codebase_map.py` —
приёмочные тесты `tasks/T067/acceptance_tests/` (`_sandbox.py`); здесь —
ветвление решения через мок трёх точек (`gitcmd.commits_behind`,
`gitcmd.in_repo`, `subprocess.run` регенератора), тем же приёмом лёгкой
FSM-песочницы без реального git, что и `tests/test_branch_freshness_
gate.py` (T051).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import acceptance, agent_log, fsm, gitcmd, store  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402


class MapConflictAutoResolveTest(LightTransitionSandbox):

    MAP_REL = "docs/codebase-map.md"

    # ------------------------------------------------------------ утилиты

    def journal_rows(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in self.journal_rows()]

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(("git", "-C", str(repo), *args), 0, "", "")

    def _conflict_response(self, repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            ("git", "-C", str(repo), *args), 1, "",
            "CONFLICT (content): Merge conflict in docs/codebase-map.md")

    def make_in_repo_side_effect(self, conflict_files: list[str]):
        """Заглушка `gitcmd.in_repo`, записывающая все вызовы, отвечающая
        конфликтом на `merge` и списком `conflict_files` на `diff
        --name-only --diff-filter=U`."""
        calls: list = []

        def side_effect(repo, *args):
            calls.append(args)
            if args[:1] == ("merge",) and "--abort" in args:
                return self._ok(repo, *args)
            if args[:1] == ("merge",):
                return self._conflict_response(repo, *args)
            if args[:2] == ("diff", "--name-only"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0,
                    "\n".join(conflict_files) + ("\n" if conflict_files else ""),
                    "")
            if args[:1] in (("checkout",), ("add",), ("commit",), ("reset",)):
                # `reset` — часть новой очистки worktree перед merge (SPEC
                # 01M1RA0R9AH9RBAHD4A2Z5SEWQ, требования 1-2, `checkpoint.
                # commit_pull_checkpoint` исключает `tasks/<id>/` из
                # WIP-коммита этим вызовом): нечего коммитить в этом
                # сценарии («diff --cached» ниже отвечает «чисто»), поэтому
                # безобидный no-op, как и остальные три вызова здесь.
                return self._ok(repo, *args)
            # `fsm._dirty_refuses`/`store.record_fixation` (A7: self/артель
            # фиксируется тем же кодом, что и любой target, — эти вызовы
            # существовали и до A7, просто не были достижимы этой лёгкой
            # песочницей раньше, пока она падала на `cmd_new`) сверяют/
            # коммитят артефактный репо `config.PROJECTS/<target>/`
            # (`fixation.read`/`fix`) ПЕРЕД/НА каждом из трёх гейтов
            # (SPEC/REVIEW/PLAN) — «чисто, нечего коммитить» здесь, тест
            # не о фиксации.
            if args == ("rev-parse", "HEAD"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "f" * 40 + "\n", "")
            if args[:2] == ("status", "--porcelain"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args[:1] == ("init",):
                return self._ok(repo, *args)
            if args[:2] == ("diff", "--cached"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")  # нечего коммитить
            raise AssertionError(f"неожиданный gitcmd.in_repo вызов: {args}")

        return calls, side_effect

    # ------------------------------------------- авторазрешение — успех

    def test_map_only_conflict_autoresolves_without_escalation(self):
        """Ловит мутацию (SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS, REVIEW.md
        итерация 1, R1-F2): возврат материализации планки к временному
        каталогу (регрессия №14) или к `cwd=config.ROOT` — `plank_root`/
        `cwd`, сверяемые ниже с `self.wt_path`, перестали бы совпадать,
        и `assertEqual` по ним это поймает.
        """
        self.write_acceptance_plank()
        calls, side_effect = self.make_in_repo_side_effect([self.MAP_REL])
        with mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run",
                               return_value=subprocess.CompletedProcess(
                                   ["python3", "scripts/codebase_map.py"],
                                   0, "", "")) as regen, \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run, \
             mock.patch.object(agent_log, "environment_fingerprint",
                               return_value="env-fp-stub"):
            # ADR-0015: приёмка теперь прогоняется прямо в `in_dev` (эта
            # же функция, до перехода в `verifying`) — журнал зелёного
            # прогона несёт fingerprint окружения (`agent_log.
            # environment_fingerprint`), который иначе позвал бы РЕАЛЬНЫЕ
            # `git --version`/`claude --version` через тот же глобальный
            # `subprocess.run`, замоканный строкой выше только под ответ
            # регенератора карты — без этой заглушки `regen` ловил бы
            # чужие вызовы и `assert_called_once()` ниже падал бы.
            out = self.advance_from_in_dev()

        self.assertEqual(self.state(), "verifying",
                         "конфликт только по карте не имеет права "
                         "эскалировать — переход обязан состояться")
        self.assertNotIn("эскалац", out.lower())
        regen.assert_called_once()
        self.assertEqual(regen.call_args.kwargs.get("cwd"), self.wt_path,
                         "регенерация обязана идти на СЛИТОМ дереве "
                         "worktree задачи, не главной копии пульта")
        # ADR-0015: с этой задачи `in_dev` зовёт `acceptance.run` дважды —
        # раз внутри `pull.evaluate` (рубеж «прогон планки после
        # подтяжки», SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS, этот тест изначально
        # про НЕГО) и второй раз своим отдельным рубежом
        # `_acceptance_run_refuses` (SPEC T023, требование 6, переехавшим
        # из `review()`) — оба легитимны и стояли в системе ДО этой задачи
        # (просто на двух разных вызовах `advance`, не в одном); первый
        # вызов в списке — от `pull.evaluate`, его и проверяет этот тест.
        self.assertEqual(acc_run.call_count, 2)
        plank_root = acc_run.call_args_list[0][0][0]
        self.assertEqual(
            plank_root, self.wt_path / "tasks" / self.TASK,
            "SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS AC-1: планка обязана "
            "материализоваться в рабочий каталог кода задачи, не во "
            "временный каталог")
        self.assertEqual(
            acc_run.call_args_list[0].kwargs.get("cwd"), self.wt_path,
            "SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS AC-2: cwd прогона обязан "
            "быть равен рабочему каталогу кода задачи")

        commit_calls = [c for c in calls if c[:1] == ("commit",)]
        self.assertEqual(len(commit_calls), 1,
                         "merge обязан быть завершён явным commit")
        abort_calls = [c for c in calls if c[:1] == ("merge",) and "--abort" in c]
        self.assertEqual(abort_calls, [], "успешное авторазрешение не "
                         "откатывает merge")

    def test_map_only_conflict_journal_records_orchestrator_and_method(self):
        calls, side_effect = self.make_in_repo_side_effect([self.MAP_REL])
        with mock.patch.object(gitcmd, "commits_behind", return_value=1), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run",
                               return_value=subprocess.CompletedProcess(
                                   ["python3", "scripts/codebase_map.py"],
                                   0, "", "")), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            self.advance_from_in_dev()

        rows = self.journal_rows()
        matching = [r for r in rows
                   if (r["actor"] or "") == "orchestrator"
                   and self.MAP_REL in (r["detail"] or "")]
        self.assertTrue(matching, f"нет записи actor=orchestrator, "
                        f"называющей {self.MAP_REL}: "
                        f"{[(r['actor'], r['action'], r['detail']) for r in rows]}")
        text = " ".join(f"{r['action'] or ''} {r['detail'] or ''}"
                        for r in matching).lower()
        self.assertTrue(any(k in text for k in ("регенерац", "regen")),
                        f"запись обязана называть способ разрешения: {text!r}")

    # --------------------------------------- авторазрешение — провал регенерации

    def test_map_only_conflict_regen_failure_aborts_and_escalates(self):
        calls, side_effect = self.make_in_repo_side_effect([self.MAP_REL])
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run",
                               return_value=subprocess.CompletedProcess(
                                   ["python3", "scripts/codebase_map.py"],
                                   1, "", "boom")), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.advance_from_in_dev()

        self.assertEqual(self.state(), "escalated",
                         "провал регенерации при авторазрешении обязан "
                         "эскалировать, а не оставлять полусмерженное "
                         "состояние")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())
        abort_calls = [c for c in calls if c[:1] == ("merge",) and "--abort" in c]
        self.assertEqual(len(abort_calls), 1,
                         "провал авторазрешения обязан откатывать merge")
        commit_calls = [c for c in calls if c[:1] == ("commit",)]
        self.assertEqual(commit_calls, [],
                         "merge не завершается commit'ом при провале "
                         "регенерации")
        acc_run.assert_not_called()

    # ----------------------------------- конфликт карты + другого файла

    def test_map_plus_other_file_conflict_still_escalates(self):
        calls, side_effect = self.make_in_repo_side_effect(
            [self.MAP_REL, "shared.txt"])
        with mock.patch.object(gitcmd, "commits_behind", return_value=4), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run") as regen, \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.advance_from_in_dev()

        self.assertEqual(self.state(), "escalated",
                         "конфликт по нескольким файлам, включая карту, "
                         "обязан эскалировать")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())
        regen.assert_not_called()
        abort_calls = [c for c in calls if c[:1] == ("merge",) and "--abort" in c]
        self.assertEqual(len(abort_calls), 1)
        acc_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
