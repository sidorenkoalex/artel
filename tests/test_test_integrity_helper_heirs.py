"""Наследники класса с изменённой цепочкой помощников вне диффа и сбой
чтения модуля стороны в гейте неослабления (SPEC
01M4G8N9KBTVNNT7YGZ59Q5WBF, требование 2; ревью итерации 1, R1-F1/R1-F2).

Помощник базового класса не теряет своего утверждения, но класс файла
диффа перестаёт отдавать его наследнику — пустым переопределением или
сменой базового класса. Вызывающий в файле вне диффа теряет утверждения
так же, как при удалении утверждения в самом помощнике, и находка гейта
мержа должна быть у него та же. Песочница — настоящий git
(`tests.sandbox.ConnRealGitSandbox`), вход — `merge_gate_escalates`.
"""
import unittest
from unittest import mock

from orchestrator import config, gitcmd, store
from orchestrator.advance_gates import test_integrity
from scripts import guard
from tests.sandbox import ConnRealGitSandbox

TASK = "T001"
BRANCH = "task/t001-nasledniki"
ARTIFACT = "artifact/t001"
STATE = "review"
ESCALATED_ACTION = "state -> escalated"

TOP = ("import unittest\n\n\n"
       "class Top(unittest.TestCase):\n"
       "    def check(self, value):\n"
       "        self.assertEqual(value, 1)\n")
MID = ("from tests.top import Top\n\n\n"
       "class Mid(Top):\n"
       "    pass\n")
CALLER = ("from tests.mid import Mid\n\n\n"
          "class CallerTest(Mid):\n"
          "    def test_m(self):\n"
          "        self.check(1)\n")


class HeirSandbox(ConnRealGitSandbox):

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, TASK, "Наследники", STATE, BRANCH,
                          config.DEFAULT_TARGET, 10.0)
        self.conn.commit()

    def write(self, path: str, text: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit_diff(self, base: dict, head: dict) -> None:
        for path, text in base.items():
            self.write(path, text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        self.checkout(BRANCH, create=True)
        for path, text in head.items():
            self.write(path, text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "голова")
        self.checkout(config.MAIN_BRANCH)

    def escalation(self) -> str:
        found = [row["detail"] or "" for row in self.conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (TASK,)) if row["action"] == ESCALATED_ACTION]
        self.assertEqual(1, len(found), "ожидалась одна эскалация")
        return found[0]

    def merge_gate(self) -> bool:
        return test_integrity.merge_gate_escalates(self.conn, TASK, STATE,
                                                   BRANCH, ARTIFACT)


class HeirOutsideDiffTest(HeirSandbox):

    def base_files(self) -> dict:
        return {"tests/top.py": TOP, "tests/mid.py": MID,
                "tests/test_caller.py": CALLER}

    def test_empty_override_in_diff_reaches_caller_outside_diff(self):
        """Пустое переопределение помощника в классе файла диффа — находка у вызывающего вне диффа.

        Ловит мутацию: кандидаты вне диффа ищутся только по помощникам,
        потерявшим своё утверждение (`guard.weakened_helpers`), без
        классов с изменённым набором методов — `git grep` не запускается,
        `CallerTest::test_m` теряет утверждение молча, эскалации нет.
        """
        self.commit_diff(self.base_files(), {
            "tests/mid.py": MID.replace(
                "    pass\n", "    def check(self, value):\n        pass\n")})
        self.assertTrue(self.merge_gate())
        detail = self.escalation()
        self.assertIn("tests/test_caller.py", detail)
        self.assertIn("CallerTest::test_m", detail)

    def test_base_class_change_in_diff_reaches_caller_outside_diff(self):
        """Смена базового класса в файле диффа — находка у вызывающего вне диффа.

        Ловит мутацию: изменённым классом считается только класс с иным
        набором методов, смена базовых классов не учитывается — наследник
        вне диффа не становится кандидатом, эскалации нет.
        """
        # Импорты модуля те же: меняется только база класса.
        mid = "import unittest\n" + MID
        files = self.base_files()
        files["tests/mid.py"] = mid
        self.commit_diff(files, {"tests/mid.py": mid.replace(
            "class Mid(Top)", "class Mid(unittest.TestCase)")})
        self.assertTrue(self.merge_gate())
        self.assertIn("CallerTest::test_m", self.escalation())

    def test_heir_of_heir_outside_diff_is_reached(self):
        """Наследник наследника изменённого класса, оба вне диффа, — находка.

        Ловит мутацию: поиск наследников не продолжается по классам
        найденных файлов вне диффа — вызывающий через промежуточный
        модуль вне диффа (`tests/mid.py`) не найден, эскалации нет.
        """
        root = ("import unittest\n\n\n"
                "class Root(unittest.TestCase):\n"
                "    def check(self, value):\n"
                "        self.assertEqual(value, 1)\n\n\n")
        files = self.base_files()
        files["tests/top.py"] = root + "class Top(Root):\n    pass\n"
        self.commit_diff(files, {"tests/top.py": (
            root + "class Top(unittest.TestCase):\n    pass\n")})
        self.assertTrue(self.merge_gate())
        self.assertIn("CallerTest::test_m", self.escalation())

class ChangedClassesTest(unittest.TestCase):

    def test_only_classes_with_asserting_chain_are_listed(self):
        """В изменённые классы входят только классы, чья цепочка несёт метод с утверждением.

        Ловит мутацию: фильтр по утверждениям цепочки снят — класс без
        утверждающих методов (`Plain`) тоже возвращается и каждый дифф с
        новым тестом зовёт поиск вызывающих в git.
        """
        base = ("class Plain:\n    def test_a(self):\n        pass\n\n\n"
                "class Asserting:\n    def check(self):\n        assert 1\n")
        head = base.replace("pass\n", "pass\n\n    def test_b(self):\n"
                            "        pass\n").replace(
            "assert 1\n", "assert 1\n\n    def extra(self):\n        pass\n")
        self.assertEqual({"Asserting"}, guard.changed_classes(base, head))

    def test_import_change_lists_all_asserting_classes(self):
        """Смена импортов модуля делает изменёнными все его классы с утверждающей цепочкой.

        Ловит мутацию: смена импортов не учитывается — база, разрешаемая
        через другой импорт с тем же именем, наследника не затрагивает.
        """
        base = ("from tests.a import Top\n\n\n"
                "class Mid(Top):\n    def check(self):\n        assert 1\n")
        head = base.replace("tests.a", "tests.b")
        self.assertEqual({"Mid"}, guard.changed_classes(base, head))

    def test_subclass_names_by_last_component(self):
        """Наследник находится и по голому имени базы, и по атрибуту модуля.

        Ловит мутацию: имя базы сравнивается целиком — `mid.Mid` не
        совпадает с `Mid`, наследник через `from tests import mid` пропущен.
        """
        source = ("class A(Mid):\n    pass\n\n\n"
                  "class B(mid.Mid):\n    pass\n\n\n"
                  "class C(Other):\n    pass\n")
        self.assertEqual({"A", "B"}, guard.subclass_names(source, {"Mid"}))


class SideModuleReadFailureTest(unittest.TestCase):

    def _modules(self, listed):
        with mock.patch.object(gitcmd, "show",
                               return_value=(None, "git не ответил")), \
             mock.patch.object(gitcmd, "ls_tree_files",
                               return_value=listed):
            base_modules, _head, _read, failures = \
                test_integrity._side_modules("base", "head", None, set(),
                                             ({}, {}))
            base_modules.module("tests/top.py")
        return failures

    def test_unread_existing_module_is_a_failure(self):
        """Модуль, который в дереве есть, но не прочитан, — сбой чтения, не «модуля нет».

        Ловит мутацию: `None` от `gitcmd.show` читается как отсутствие
        модуля — сбой на стороне base прячет помощников только в базе,
        список сбоев пуст.
        """
        self.assertEqual(1, len(self._modules(["tests/top.py"])))
        self.assertEqual(1, len(self._modules(None)))

    def test_absent_module_is_not_a_failure(self):
        """Модуля нет в дереве стороны — не сбой.

        Ловит мутацию: любой `None` от `gitcmd.show` считается сбоем —
        ссылка на несуществующий модуль `tests/` роняет гейт в «git не
        ответил».
        """
        self.assertEqual([], self._modules([]))


if __name__ == "__main__":
    unittest.main()
