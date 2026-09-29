"""AC-11..AC-13 — перечень долгоживущих файлов
`tasks/<id>/acceptance_tests/long_lived.sha256.txt` в ветке документов:
записан на выходе из `tests_writing` раньше `tests_locked_sha` (есть в
дереве коммита лока), формат Р2 (`<64 hex>  <путь>\\n`, строки по пути,
без комментариев), суммы — SHA-256 файлов на голове кодовой ветки; без
долгоживущих файлов — пустой, и выход проходит; правка перечня после
лока ловится нынешней сверкой лока на `in_dev -> verifying`.

Дерево коммита лока читается `gitcmd.show(<tests_locked_sha>, …)` —
ровно то содержимое, которое сверяет лок.

Группа: разовый
Красен до реализации: перечня ещё никто не пишет — в дереве коммита лока файла `long_lived.sha256.txt` нет.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

LINE = re.compile(r"^([0-9a-f]{64})  (\S.*)$")


class ManifestTest(_sandbox.LongLivedSandbox):

    def test_ac11_manifest_in_lock_tree_lists_every_long_lived_file(self):
        """Кодовая ветка несёт два долгоживущих файла задачи (имена заведены
        в обратном порядке пути). После выхода из `tests_writing` перечень
        есть в дереве коммита лока; каждая строка — формат Р2; строки
        отсортированы по пути; пути — ровно два файла задачи; сумма каждой
        строки равна SHA-256 байтов файла на голове кодовой ветки;
        последняя строка завершена переводом строки.

        Ловит мутацию: перечень пишется ПОСЛЕ записи `tests_locked_sha`
        (лок снят с коммита без перечня) либо сумма берётся от текста
        рабочего каталога с другим концом строки — в дереве лока перечня
        нет или сумма не совпадает с `git show <ветка>:<путь>`.
        """
        first = self.ll_path("zeta")
        second = self.ll_path("alpha")
        self.lock_with({first: _sandbox.long_lived_source(tag="zeta"),
                        second: _sandbox.long_lived_source(tag="alpha")})
        text = self.manifest_at_lock()
        self.assertIsNotNone(text, "перечня нет в дереве коммита лока")
        self.assertTrue(text.endswith("\n"), f"нет перевода строки: {text!r}")
        lines = text.splitlines()
        parsed = []
        for line in lines:
            match = LINE.match(line)
            self.assertIsNotNone(match, f"строка не по формату Р2: {line!r}")
            parsed.append((match.group(2), match.group(1)))
        paths = [p for p, _ in parsed]
        self.assertEqual(paths, sorted(paths), "строки не отсортированы по пути")
        self.assertEqual(sorted(paths), sorted([first, second]))
        for path, digest in parsed:
            self.assertEqual(digest, self.head_sha256(path),
                             f"сумма {path} не равна SHA-256 файла на голове")

    def test_ac12_empty_manifest_without_long_lived_files(self):
        """Кодовая ветка без долгоживущих файлов: выход из `tests_writing`
        проходит, перечень в дереве коммита лока есть и пуст.

        Ловит мутацию: пустой перечень не пишется вовсе («нечего писать»)
        либо отсутствие долгоживущих файлов считается отказом — перечня
        нет в дереве лока или задача осталась в `tests_writing`.
        """
        self.lock_with({})
        self.assertEqual(self.manifest_at_lock(), "",
                         "перечень задачи без долгоживущих файлов не пуст "
                         "или не записан")

    def test_ac13_manifest_edit_after_lock_is_caught_by_lock_check(self):
        """Перечень записан и залочен; затем в перечень коммитом в ветку
        документов дописана строка файла базы `tests/test_existing.py` с
        ВЕРНОЙ суммой — каждая строка перечня по-прежнему совпадает с
        головой кодовой ветки, так что отказ может дать только сверка
        лока. `in_dev -> verifying` отклонён записью нынешней сверки лока
        («лок приёмочных тестов»).

        Ловит мутацию: перечень пишется в ветку документов вне каталога
        `acceptance_tests/` (или в файл, отброшенный `.gitignore`) — лок
        его не покрывает, правка проходит незамеченной.
        """
        rel = self.ll_path("alpha")
        self.lock_with({rel: _sandbox.long_lived_source()})
        text = self.manifest_at_lock()
        self.assertTrue(text, "перечня нет в дереве коммита лока")
        existing = "tests/test_existing.py"
        forged = text + f"{self.head_sha256(existing)}  {existing}\n"
        self.artifact_commit(
            {f"acceptance_tests/{_sandbox.MANIFEST_NAME}": forged},
            "правка перечня после лока")
        out, entries = self.advance_in_dev()
        text = "\n".join(entries + [out])
        self.assertEqual(self.state(), "in_dev",
                         f"правка перечня после лока не отклонила переход: {text}")
        self.assertIn("лок приёмочных тестов", text)


if __name__ == "__main__":
    unittest.main()
