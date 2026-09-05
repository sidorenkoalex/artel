"""AC-1, AC-4 (tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/SPEC.md):
`orchestrator/fsm.py::_pull_main_or_escalate` перед вызовом `git merge`
приводит worktree задачи в чистое состояние, если единственная
незакоммиченная правка — `docs/codebase-map.md`: отбрасывает её
(`git checkout -- docs/codebase-map.md`), и подтяжка main проходит без
эскалации из-за «would be overwritten by merge».

Красен до реализации: `_pull_main_or_escalate` ещё не делает checkout
незакоммиченной `docs/codebase-map.md` перед merge — фейковый git ниже
намеренно отвечает реальным текстом отказа git «would be overwritten by
merge» на КАЖДЫЙ `merge`, пока не увидит явный `checkout --
docs/codebase-map.md`; без этой правки задача уходит в `escalated`
вместо `review`, оба теста падают.
"""
import subprocess
import unittest
from unittest import mock

from _sandbox import PullCleanupSandbox  # noqa: E402
from orchestrator import acceptance, gitcmd  # noqa: E402


class MapOnlyDirtyDiscardedTest(PullCleanupSandbox):

    def _side_effect(self):
        """Фейковый git: `merge` отвечает реальным текстом git «would be
        overwritten by merge», называющим `docs/codebase-map.md`, пока не
        случится `checkout -- docs/codebase-map.md` — тем самым имитирует
        ИМЕННО тот отказ, из-за которого заведена эта задача (SPEC
        «Контекст»), а не содержательный конфликт слияния."""
        calls = []
        discarded = {"map": False}

        def side_effect(repo, *args):
            calls.append((repo, args))
            if repo != self.wt_path:
                resp = self._fixation_response(repo, *args)
                if resp is not None:
                    return resp
                raise AssertionError(f"неожиданный вызов вне worktree "
                                     f"задачи: repo={repo} args={args}")
            if args[:1] == ("checkout",) and self.MAP_REL in args:
                discarded["map"] = True
                return self._ok(repo, *args)
            if args[:1] == ("merge",) and "--abort" in args:
                return self._ok(repo, *args)
            if args[:1] == ("merge",):
                if discarded["map"]:
                    return self._ok(repo, *args)
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, "",
                    "error: Your local changes to the following files "
                    f"would be overwritten by merge:\n\t{self.MAP_REL}\n"
                    "Please commit your changes or stash them before you "
                    "merge.\nAborting\n")
            if args[:2] == ("diff", "--name-only"):
                # Не настоящий конфликт содержимого — после отбрасывания
                # карты merge проходит начисто, `_conflicting_files` не
                # находит незавершённого merge вовсе.
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args[:2] == ("diff", "--cached"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args == ("rev-parse", "HEAD"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "f" * 40 + "\n", "")
            if args[:2] == ("status", "--porcelain"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, "", "")
            if args[:1] == ("init",):
                return self._ok(repo, *args)
            if args[:1] in (("add",), ("reset",)):
                return self._ok(repo, *args)
            raise AssertionError(f"неожиданный gitcmd.in_repo вызов: {args}")

        return calls, side_effect

    def test_ac1_map_only_dirty_worktree_discarded_via_checkout_before_merge(self):
        """Единственная незакоммиченная правка worktree — `docs/codebase-
        map.md`: перед `git merge` она обязана быть отброшена явным
        `checkout -- docs/codebase-map.md`, а не оставлена как есть.

        Ловит мутацию: реализация вызывает `git merge` напрямую, без
        предварительного `checkout` карты, — фейковый git в этом файле
        всегда отвечает «would be overwritten by merge», пока такого
        `checkout`-вызова не было, поэтому в `calls` не появится ни
        одного `checkout`-вызова, называющего `docs/codebase-map.md` ДО
        успешного `merge`.
        """
        calls, side_effect = self._side_effect()
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            self.advance_from_in_dev()

        wt_calls = [args for repo, args in calls if repo == self.wt_path]
        checkout_calls = [c for c in wt_calls
                          if c[:1] == ("checkout",) and self.MAP_REL in c]
        self.assertTrue(
            checkout_calls,
            f"нет ни одного checkout-вызова, отбрасывающего {self.MAP_REL}: "
            f"{wt_calls}")
        merge_calls = [c for c in wt_calls
                      if c[:1] == ("merge",) and "--abort" not in c]
        self.assertEqual(len(merge_calls), 1,
                         "подтяжка обязана вызвать ровно один успешный merge")
        checkout_idx = wt_calls.index(checkout_calls[0])
        merge_idx = wt_calls.index(merge_calls[0])
        self.assertLess(checkout_idx, merge_idx,
                        "отбрасывание карты обязано случиться ДО git merge, "
                        "иначе merge получит отказ «would be overwritten»")

    def test_ac4_map_only_dirty_worktree_pulls_main_without_escalation(self):
        """Worktree с незакоммиченной изменённой `docs/codebase-map.md` (и
        больше ничем) успешно подтягивает main: задача переходит в
        `review`, эскалации нет, приёмочные тесты подтянутого дерева
        прогнаны.

        Ловит мутацию: без отбрасывания карты `git merge` отказывает
        «would be overwritten by merge»; `_conflicting_files` не находит
        `[MAP_REL]` (это не содержательный конфликт, а отказ ДО начала
        merge) — старый код обязан откатить merge и эскалировать; итоговое
        состояние осталось бы `escalated`, не `review`.
        """
        calls, side_effect = self._side_effect()
        with mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            out = self.advance_from_in_dev()

        self.assertEqual(
            self.state(), "review",
            "подтяжка main обязана состояться без эскалации задачи")
        combined = (out + " ".join(self.journal_details())).lower()
        self.assertNotIn("эскалац", combined)
        # Правка Оператора 06.09 (amend-tests): после hotfix регрессии №14
        # (ADR-0013) контракт — `acceptance.run(tdir, code_root=<worktree>)`;
        # проверяем и каталог планки, и код ветки, как
        # tests/test_branch_freshness_gate.py.
        acc_run.assert_called_once()
        self.assertEqual(acc_run.call_args.args[0], self.wt_path / "tasks" / self.TASK)
        self.assertEqual(acc_run.call_args.kwargs.get("code_root"), self.wt_path)


if __name__ == "__main__":
    unittest.main()
