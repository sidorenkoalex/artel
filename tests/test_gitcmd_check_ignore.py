"""Юнит-тесты `gitcmd.check_ignore`/`gitcmd.diff_names` (SPEC
01M1KVG3KSCY47HWXWF5HM0E76, требования 1 и 3): критерий «игнорируется»
обязан быть настоящим разбором `.gitignore` пульта (`git check-ignore`),
не самодельным списком расширений — единственный способ поймать
директорное правило (`dropme/`), которое списком суффиксов не выразить.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, gitcmd  # noqa: E402
from tests.sandbox import (GitignoreCommittedRealGitSandbox,  # noqa: E402
                           RealGitSandbox)


class CheckIgnoreTest(GitignoreCommittedRealGitSandbox):

    def test_empty_paths_is_empty_without_a_git_call(self):
        """Ловит мутацию: удаление короткого пути `if not paths: return
        set()` — пустой список ушёл бы в `subprocess.run` с пустым stdin;
        реальный `git check-ignore` без единого пути на входе не гарантирует
        пустое множество тем же кодом (может отличаться по returncode/
        поведению), тест перестал бы быть детерминированным независимо от
        git на машине.
        """
        self.assertEqual(gitcmd.check_ignore([]), set())

    def test_extension_rule_matches(self):
        """Ловит мутацию: `check_ignore` перестаёт распознавать суффиксные
        правила `.gitignore` (например, порча парсинга полей `-z`-вывода
        `git check-ignore -v -z`) — `*.pyc` не попал бы в результат, тест
        упал бы на `assertEqual`.
        """
        ignored = gitcmd.check_ignore(["tasks/X/acceptance_tests/"
                                       "__pycache__/test_ac.cpython-311.pyc"])
        self.assertEqual(
            ignored,
            {"tasks/X/acceptance_tests/__pycache__/test_ac.cpython-311.pyc"})

    def test_directory_rule_not_expressible_as_an_extension_list_matches(self):
        """`dropme/` — директорное правило; список суффиксов в коде такой
        путь никогда не поймает (единственный способ — настоящий парсинг
        .gitignore, ровно то, что здесь проверяется).

        Ловит мутацию: замена настоящего `git check-ignore` на самодельный
        список расширений (регрессия SPEC, требование 1) — `dropme/
        notes.txt` не матчится ни одним суффиксом и результат окажется
        пустым множеством вместо ожидаемого пути.
        """
        ignored = gitcmd.check_ignore(["tasks/X/dropme/notes.txt"])
        self.assertEqual(ignored, {"tasks/X/dropme/notes.txt"})

    def test_path_need_not_exist_on_disk(self):
        """`checkpoint`/`fsm_advance` зовут `check_ignore` над путями
        внешнего target, которых на диске `config.ROOT` нет вовсе —
        директорное правило обязано матчиться по строке пути, не по
        факту существования каталога/файла.

        Ловит мутацию: реализация, которая перед вызовом git проверяет
        `Path(p).exists()` и пропускает несуществующие пути без запроса
        к git — путь `dropme/nested/deep.txt` (каталог `tasks/` физически
        отсутствует, `self.assertFalse` выше это фиксирует) вернулся бы
        не игнорируемым, хотя правило `dropme/` его покрывает.
        """
        self.assertFalse((self.root / "tasks").exists())
        ignored = gitcmd.check_ignore(["tasks/X/dropme/nested/deep.txt"])
        self.assertEqual(ignored, {"tasks/X/dropme/nested/deep.txt"})

    def test_non_ignored_path_is_not_in_the_result(self):
        """Ловит мутацию: `check_ignore` по ошибке считает игнорируемым
        любой путь под `tasks/` (например, из-за слишком широкого правила
        сборки stdin/парсинга) — `PLAN.md`, который `.gitignore` не
        затрагивает, попал бы в результат вместо пустого множества.
        """
        ignored = gitcmd.check_ignore(["tasks/X/PLAN.md"])
        self.assertEqual(ignored, set())

    def test_mixed_batch_returns_only_the_ignored_subset(self):
        """Ловит мутацию: смещение индексов при разборе `-z`-полей batch-
        ответа `git check-ignore --stdin` (`fields[i + 3]`/шаг `i += 4`) —
        на смешанном списке из игнорируемых и обычных путей сдвиг на одно
        поле возвращает не тот путь или теряет часть результата, тогда как
        для одиночного вызова (см. предыдущие тесты) сдвиг может остаться
        незамеченным.
        """
        paths = ["tasks/X/PLAN.md",
                 "tasks/X/acceptance_tests/__pycache__/x.pyc",
                 "tasks/X/dropme/notes.txt",
                 "tasks/X/SPEC.md"]
        ignored = gitcmd.check_ignore(paths)
        self.assertEqual(
            ignored,
            {"tasks/X/acceptance_tests/__pycache__/x.pyc",
             "tasks/X/dropme/notes.txt"})

    def test_unresponsive_git_is_none(self):
        """Ловит мутацию: удаление `try/except OSError: return None` вокруг
        `subprocess.run` — недоступный git (бинарь не найден) уронил бы
        исключение наружу вместо fail-closed `None`, на котором вызывающий
        код (`checkpoint`/`fsm_advance`) обязан деградировать без коммита
        вслепую (SPEC, требование 6).
        """
        with mock.patch.object(gitcmd.subprocess, "run",
                               side_effect=OSError("git не найден")):
            self.assertIsNone(gitcmd.check_ignore(["tasks/X/PLAN.md"]))


class DiffNamesTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        (self.root / "a.txt").write_text("1\n", encoding="utf-8")
        (self.root / "b.txt").write_text("1\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "before")
        self.before = gitcmd.head_sha()
        (self.root / "a.txt").write_text("2\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "after")
        self.after = gitcmd.head_sha()

    def test_lists_changed_paths(self):
        """Ловит мутацию: `diff_names` возвращает булево (как `diff_paths`)
        вместо списка путей — лок `fsm_advance.in_dev` не смог бы вычесть
        из результата игнорируемые пути (SPEC, требование 3), тест упал бы
        на несовпадении с `["a.txt"]`.
        """
        self.assertEqual(gitcmd.diff_names(self.before, self.after),
                         ["a.txt"])

    def test_no_changes_is_an_empty_list(self):
        """Ловит мутацию: `res.stdout.splitlines()` без фильтра пустых строк
        (`if p`) — на отсутствии изменений между `self.before` и им же
        самим вернулся бы список с одной пустой строкой вместо `[]`.
        """
        self.assertEqual(gitcmd.diff_names(self.before, self.before), [])

    def test_unreachable_sha_is_none(self):
        """Ловит мутацию: удаление проверки `res.returncode != 0` — git
        на несуществующем sha вернул бы ненулевой код и пустой/ошибочный
        stdout, который без проверки кода превратился бы в `[]` вместо
        fail-closed `None`.
        """
        self.assertIsNone(gitcmd.diff_names("d" * 40, self.after))

    def test_pathspec_narrows_the_comparison(self):
        """Ловит мутацию: потеря `*paths` при сборке команды `git diff
        --name-only a b -- *paths` — сравнение перестало бы сужаться
        pathspec'ом, и `b.txt` (не менявшийся) не был бы отфильтрован из
        общего диффа, результат перестал бы быть пустым списком.
        """
        self.assertEqual(gitcmd.diff_names(self.before, self.after, "b.txt"), [])


if __name__ == "__main__":
    unittest.main()
