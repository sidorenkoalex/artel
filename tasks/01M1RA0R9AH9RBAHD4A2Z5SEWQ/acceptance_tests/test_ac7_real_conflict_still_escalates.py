"""AC-7 (tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/SPEC.md): настоящий конфликт
содержимого при `git merge` (конфликтующий файл за пределами случая
«только карта», SPEC T067) по-прежнему уводит задачу в `escalated` с
текстом «конфликт подтяжки» — поведение байт-в-байт как сейчас, не
ослаблено этой задачей.

Зелёный с рождения: этот сценарий (реальный merge-конфликт по обычному
файлу) уже обрабатывается существующим кодом `_pull_main_or_escalate`
байт-в-байт так же, как требует критерий, — предмет теста ПРЕЖНЕЕ
поведение, которое требования 1-2 этой задачи не имеют права тронуть;
фейковый git ниже к тому же принимает (безобидным no-op'ом) вызовы
`checkout`/`add`/`reset`/`diff --cached`, которых требования 1-2 добавят
ДО merge, поэтому тест остаётся зелёным и после их появления.
"""
import subprocess
import unittest
from unittest import mock

from _sandbox import PullCleanupSandbox  # noqa: E402
from orchestrator import acceptance, gitcmd  # noqa: E402


class RealConflictBeyondMapStillEscalatesTest(PullCleanupSandbox):

    def _side_effect(self, conflict_file="shared.txt"):
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
                # AC-1: карта чистая — отбрасывание безобидный no-op.
                return self._ok(repo, *args)
            if args[:1] == ("merge",) and "--abort" in args:
                return self._ok(repo, *args)
            if args[:1] == ("merge",):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, "",
                    f"CONFLICT (content): Merge conflict in {conflict_file}")
            if args[:2] == ("diff", "--name-only"):
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, f"{conflict_file}\n", "")
            if args[:2] == ("diff", "--cached"):
                # AC-2: прочего WIP нет — нечего коммитить.
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

    def test_ac7_real_content_conflict_beyond_map_still_escalates_as_pull_conflict(self):
        """Конфликт по обычному (не карта) файлу — задача эскалирует с
        формулировкой «конфликт подтяжки», merge откатывается `git merge
        --abort`, приёмочные тесты не запускаются.

        Ловит мутацию: очистка/чекпоинт требований 1-2 этой задачи по
        ошибке проглатывают НАСТОЯЩИЙ merge-конфликт (например,
        расширенное условие авторазрешения ошибочно принимает
        `conflict_file` как «единственный конфликт — карта») — тест
        поймает и уход из `escalated`, и пропажу формулировки «конфликт
        подтяжки», и лишний вызов `acceptance.run`.
        """
        calls, side_effect = self._side_effect()
        with mock.patch.object(gitcmd, "commits_behind", return_value=5), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.advance_from_in_dev()

        self.assertEqual(self.state(), "escalated",
                         "настоящий конфликт содержимого обязан эскалировать")
        combined = (out + " ".join(self.journal_details())).lower()
        self.assertIn(
            "конфликт подтяжки", combined,
            "настоящий конфликт содержимого обязан нести прежнюю "
            "формулировку «конфликт подтяжки»")
        abort_calls = [args for repo, args in calls
                      if repo == self.wt_path and args[:1] == ("merge",)
                      and "--abort" in args]
        self.assertEqual(len(abort_calls), 1,
                         "конфликт обязан откатываться git merge --abort")
        acc_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
