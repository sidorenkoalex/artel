"""Приёмочный тест AC-3 — 01M283NC4JJXK7QS68Y9ET8TBK.

Источник — tasks/01M283NC4JJXK7QS68Y9ET8TBK/SPEC.md, «Критерии приёмки»:

AC-3. При этом коммите пишется запись журнала с `actor=orchestrator`,
действием «код закоммичен пультом за роль» и `detail`, несущим список
закоммиченных файлов и число изменённых строк.

Число строк контролируется тестом буквально (тот же приём, что уже несёт
`tasks/01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests/
test_ac3_discard_journal_names_paths_and_line_count.py` для соседнего
класса чекпоинтов): правка добавляет РОВНО 4 строки в единственный новый
файл — `detail` обязан называть и путь (`orchestrator/new_module.py`), и
это число (4), иначе «список файлов и число строк» не проверены, а
изображены.

Красен до реализации: до этой задачи действие «код закоммичен пультом за
роль» в журнале не существует ни при каком сценарии (см. AC-1/AC-2) —
`code_commit_journal_entries()` возвращает пустой список, и первый же
`assertEqual(len(entries), 1, ...)` красит тест.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DeveloperWipCommitSandbox  # noqa: E402


class JournalEntryListsFilesAndLineCountTest(DeveloperWipCommitSandbox):

    def test_ac3_journal_entry_names_actor_action_file_and_line_count(self):
        """Шаг `developer` завершается `rc=0` с новым файлом из ровно 4
        строк вне `tasks/<id>/` — запись журнала о код-коммите пульта
        несёт `actor=orchestrator`, действие «код закоммичен пультом за
        роль», а `detail` называет и путь файла, и число 4.

        Ловит мутацию: коммит происходит (AC-1/AC-2 зелёные), но
        журналирование забыто/использует другой `actor`/действие, либо
        `detail` несёт только сообщение коммита без списка файлов и
        числа строк — тогда либо `entries` пуст, либо `assertIn`/
        `re.search` ниже не находят требуемого.
        """
        self.enter_in_dev()
        self.write_code_file(
            "orchestrator/new_module.py",
            "строка 1\nстрока 2\nстрока 3\nстрока 4\n")

        self.run_faked()

        entries = self.code_commit_journal_entries()
        self.assertEqual(
            len(entries), 1,
            "AC-3: запись журнала о код-коммите пульта обязана появиться "
            "ровно один раз")
        entry = entries[0]
        self.assertEqual(entry["actor"], "orchestrator")
        self.assertEqual(entry["action"], "код закоммичен пультом за роль")
        self.assertIn(
            "orchestrator/new_module.py", entry["detail"],
            f"AC-3: detail обязан называть закоммиченный путь — "
            f"фактически: {entry['detail']!r}")
        self.assertTrue(
            re.search(r"\b4\b", entry["detail"]),
            f"AC-3: detail обязан называть число изменённых строк (4) — "
            f"фактически: {entry['detail']!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
