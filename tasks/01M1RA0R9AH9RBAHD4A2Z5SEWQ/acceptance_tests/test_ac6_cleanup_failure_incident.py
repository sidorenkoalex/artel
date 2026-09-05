"""AC-6 (tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/SPEC.md): очистка worktree сама
не удалась (git не ответил на одном из своих шагов) — «would be
overwritten by merge» всё же произошёл: задача уходит в `escalated`,
журнал называет конкретный незакоммиченный файл, заводится alert
`kind=incident`, а текст отказа/эскалации НЕ несёт формулировку «конфликт
подтяжки» (это инцидент очистки, не спор версий содержимого, требование
4 — разные причины отказа для Оператора).

Красен до реализации: текущий код на ЛЮБОЙ отказ `git merge` безусловно
пишет detail `f"конфликт подтяжки {source_branch} в ветку {branch}: ..."`
(`orchestrator/fsm.py::_pull_main_or_escalate`) и не заводит alert вовсе —
без различения причины отказа (очистка/git против содержательного спора)
тест на отсутствие фразы «конфликт подтяжки» и на alert `kind=incident`
падает уже сегодня.
"""
import subprocess
import unittest
from unittest import mock

from _sandbox import PullCleanupSandbox  # noqa: E402
from orchestrator import acceptance, alerts, gitcmd, store  # noqa: E402


class CleanupFailureIncidentTest(PullCleanupSandbox):

    def _side_effect(self):
        """`checkout -- docs/codebase-map.md` (попытка очистки по AC-1)
        сама отказывает («git не ответил» — требование 4, дословный
        пример из SPEC) — `git merge` после этого продолжает получать
        реальный текст git «would be overwritten by merge», называющий
        карту: очистка была ПОПЫТАНА и провалилась, а не просто
        пропущена."""
        calls = []

        def side_effect(repo, *args):
            calls.append((repo, args))
            if repo != self.wt_path:
                resp = self._fixation_response(repo, *args)
                if resp is not None:
                    return resp
                raise AssertionError(f"неожиданный вызов вне worktree "
                                     f"задачи: repo={repo} args={args}")
            if args[:1] == ("checkout",) and self.MAP_REL in args:
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, "",
                    "fatal: unable to write new index file (тест: сбой git)")
            if args[:1] == ("merge",) and "--abort" in args:
                return self._ok(repo, *args)
            if args[:1] == ("merge",):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, "",
                    "error: Your local changes to the following files "
                    f"would be overwritten by merge:\n\t{self.MAP_REL}\n"
                    "Please commit your changes or stash them before you "
                    "merge.\nAborting\n")
            if args[:2] == ("diff", "--name-only"):
                # Не содержательный merge-конфликт — merge вообще не
                # стартовал (отказ ДО начала слияния), unmerged-файлов нет.
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

    def test_ac6_cleanup_failure_escalates_as_incident_not_pull_conflict(self):
        """Провал самой очистки (checkout карты не удался, merge продолжает
        получать «would be overwritten») эскалирует задачу с указанием
        конкретного файла и заводит alert `kind=incident`, но НЕ несёт
        формулировку «конфликт подтяжки».

        Ловит мутацию: код классифицирует любой отказ merge одинаково
        («конфликт подтяжки», без alert) — тест на `assertNotIn` и на
        наличие incident-алерта падает, потому что текущая реализация
        именно так и поступает.
        """
        calls, side_effect = self._side_effect()
        with mock.patch.object(gitcmd, "commits_behind", return_value=4), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.advance_from_in_dev()

        self.assertEqual(
            self.state(), "escalated",
            "неудавшаяся очистка обязана эскалировать задачу")
        combined = out + " ".join(self.journal_details())
        self.assertIn(
            self.MAP_REL, combined,
            f"журнал обязан называть конкретный незакоммиченный файл: "
            f"{combined!r}")
        self.assertNotIn(
            "конфликт подтяжки", combined.lower(),
            "это инцидент очистки, не спор версий — текст не должен "
            "использовать формулировку конфликта подтяжки")
        conn = store.db()
        incidents = [a for a in alerts.open_alerts(conn, "incident")
                    if a["target"] == self.TASK]
        self.assertTrue(
            incidents,
            "обязан завестись alert kind=incident по этой задаче")
        acc_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
