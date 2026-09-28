"""AC-6, AC-7 — джоб CI `protected-paths`: вердикт нарушения на новых
путях и разбор нового перечня из текста `orchestrator/config.py`.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. `ci_protected_paths.is_violation` с перечнем требования 1 считает
нарушением каждый из пяти новых путей (включая `tests/sub/conftest.py`) и
не считает нарушением `tests/test_conftest_role_guard.py` и
`docs/pyproject.md`.

AC-7. `ci_protected_paths.protected_paths_from_source`, прочитав текст
`orchestrator/config.py` с новым перечнем, возвращает все 17 записей
(маска среди них) и причину-пустую-строку.

«Перечень требования 1» AC-6 берётся как `config.PROTECTED_PATHS` —
крутилку Оператора планка не дублирует литералом. Текст модуля AC-7
читается по `config.__file__`, а не по собранному от корня пути: адрес
модуля даёт сам Python, и подмена `config.ROOT` песочницей соседних
тестов на него не влияет. Это код репозитория, не артефакт задачи, —
чтение с диска здесь законно.

Красен до реализации: ни маски, ни четырёх литералов в перечне нет — `is_violation` не считает нарушением `conftest.py`, а в разобранном перечне AC-7 нет записи `**/conftest.py`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _protected  # noqa: E402
from orchestrator import config  # noqa: E402
from scripts import ci_protected_paths  # noqa: E402


class CiJobViolationTest(unittest.TestCase):

    def test_ac6_new_paths_are_violations_and_lookalikes_are_not(self):
        """`is_violation` с перечнем требования 1 красит PR на каждом из
        новых путей (включая вложенный `tests/sub/conftest.py`) и не
        красит на `tests/test_conftest_role_guard.py` и
        `docs/pyproject.md`.

        Ловит мутацию: `is_violation` оставили на голом
        `path.startswith(prefix)` (её сегодняшняя формула), позвав общего
        помощника только в гейтах пульта. Наблюдаемое расхождение: джоб
        `protected-paths` возвращает 0 на PR, который правит
        `tests/sub/conftest.py`, — рубеж CI на новых путях молча выключен,
        притом что гейты пульта такой дифф отклоняют.
        """
        protected = list(config.PROTECTED_PATHS)
        for path in _protected.PROTECTED_NEW_PATHS:
            with self.subTest(path=path, verdict="нарушение"):
                self.assertTrue(
                    ci_protected_paths.is_violation(path, protected),
                    f"джоб CI не считает правку {path} нарушением")
        for path in _protected.CI_NON_VIOLATION_PATHS:
            with self.subTest(path=path, verdict="не нарушение"):
                self.assertFalse(
                    ci_protected_paths.is_violation(path, protected),
                    f"джоб CI ложно считает правку {path} нарушением")


class ProtectedPathsFromSourceTest(unittest.TestCase):

    def test_ac7_new_list_is_parsed_from_the_config_source(self):
        """Разбор текста `orchestrator/config.py` модульным `ast` отдаёт
        весь новый перечень (запись-маска среди записей) и пустую причину.

        Число записей сверяется с `config.PROTECTED_PATHS`, а не с
        литералом 17: «17» — состояние перечня на день задачи, а
        пополняет его и Оператор мимо задачи. Равенство разобранного
        списка живому кортежу — та же проверка, только переживающая
        крутилку.

        Ловит мутацию: перечень записан не литеральным кортежем, а
        вычислением (`PROTECTED_PATHS = _LEGACY + _TEST_SETTINGS`, или
        маска собрана f-строкой) — `ast.literal_eval` отказывает, функция
        возвращает `(None, причина)`, и джоб CI становится красным кодом
        возврата 2 на КАЖДОМ PR, ничего не проверив.
        """
        source = Path(config.__file__).read_text(encoding="utf-8")

        paths, reason = ci_protected_paths.protected_paths_from_source(source)

        self.assertEqual(reason, "")
        self.assertEqual(paths, list(config.PROTECTED_PATHS))
        self.assertIn(_protected.MASK_ENTRY, paths)


if __name__ == "__main__":
    unittest.main()
