"""Юнит-тесты компонентов проекта в `orchestrator/project_profile.py` (SPEC
01M58FNWBV25FF26E7AZ9Q9912, требования 6-8) — свойства, не покрытые
долгоживущим файлом задачи: `depends_on` вида `contract` выбор не расширяет,
пустой набор путей, негодная строка идентификатора и `#` без номера в имени.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import project_profile, targets  # noqa: E402

ENTRY = {"components": {
    "api": {"paths": ["^api/"]},
    "web": {"paths": "^web/",
            "depends_on": {"api": {"via": "contract",
                                   "paths": ["^api/schema/"]}}},
}}


class SelectComponentsTest(unittest.TestCase):

    def select(self, paths) -> tuple:
        with mock.patch.object(targets, "target", return_value=ENTRY):
            return project_profile.select_components("proj", paths)

    def test_contract_dependency_does_not_widen_selection(self):
        """Путь под `paths` поставщика `depends_on` вида `contract` задевает
        только поставщика, не потребителя.

        Ловит мутацию: `_touches` берёт `paths` любого `depends_on` без
        сверки `via` — путь `api/schema/x.json` выберет и `web`.
        """
        self.assertEqual(self.select(["api/schema/x.json"]), ("api",))

    def test_empty_paths_select_all_components(self):
        """Пустой набор путей у записи с несколькими компонентами — все
        компоненты в порядке записи, не пустой выбор.

        Ловит мутацию: убрана ветка «ничего не задето — все» после цикла —
        пустой набор даёт `()`.
        """
        self.assertEqual(self.select([]), ("api", "web"))
        self.assertEqual(self.select(iter(())), ("api", "web"))


class TestIdTest(unittest.TestCase):

    def test_malformed_text_raises_value_error(self):
        """Строка без компонента, пути или полного имени — `ValueError`.

        Ловит мутацию: `parse_test_id` не проверяет разделители — строка
        без `::` разбирается в кортеж с пустым именем вместо отказа.
        """
        for text in ("api/tests/test_x.py", "api:tests/test_x.py",
                     ":tests/test_x.py::t", "api:::t", "api:p::"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    project_profile.parse_test_id(text)

    def test_hash_without_number_stays_in_name(self):
        """`#` без десятичного номера за ним — часть полного имени,
        номер `None`; `test_id` отвергает компонент с `:`.

        Ловит мутацию: номер отрезается по любому `#` — `t#a` даёт
        `ValueError` `int('a')` или имя `t`; `test_id` склеивает компонент
        с `:`, который потом не разобрать.
        """
        self.assertEqual(project_profile.parse_test_id("a:p.py::t[x#y]"),
                         ("a", "p.py", "t[x#y]", None))
        self.assertEqual(project_profile.parse_test_id("a:p.py::t#²"),
                         ("a", "p.py", "t#²", None))
        with self.assertRaises(ValueError):
            project_profile.test_id("a:b", "p.py", "t")


if __name__ == "__main__":
    unittest.main()
