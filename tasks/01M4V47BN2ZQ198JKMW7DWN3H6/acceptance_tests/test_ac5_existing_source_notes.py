"""Записки, уже записанные в ссылку документов этой задачи.

Группа: разовый
Зелёный с рождения: существующие записки уже есть в источнике; тест удерживает их от удаления при подготовке проверяющих ролей.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import artifact_text  # noqa: E402


class SourceNotesTest(unittest.TestCase):
    def test_ac5_existing_notes_remain_in_source(self):
        """После выкладки этой задачи ссылка всё ещё содержит прежние записки.

        Ловит мутацию: фильтр удаляет скрытую записку из ссылки документов —
        чтение NOTE-analyst.md или NOTE-spec_auditor.md возвращает None.
        """
        for name in ("NOTE-analyst.md", "NOTE-spec_auditor.md"):
            with self.subTest(name=name):
                self.assertIsNotNone(artifact_text(name), name)


if __name__ == "__main__":
    unittest.main()
