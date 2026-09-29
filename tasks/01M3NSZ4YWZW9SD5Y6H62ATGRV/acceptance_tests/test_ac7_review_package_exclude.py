"""AC-7: долгоживущий файл перечня лока исключён из стат-списка и diff
пакета ревью (полный и инкрементальный diff) и из меры гейта ёмкости,
а ревьюверу приходит отдельным компонентом до стат-списка; файл с
префиксом задачи вне перечня и сбой чтения перечня оставляют файл в
diff.

diff — настоящий `git diff` песочницы: предмет — действие pathspec
исключения на git, а не форма кортежа.

Группа: разовый
Красен до реализации: `review.snapshot_exclude` исключает только `tasks/<id>/` и карту — долгоживущий файл перечня виден в стат-списке и diff, гейт ёмкости мерит его байты, отдельного компонента нет.

Почему разовый: сценарий строит ветку документов через `artifact_branch`
и адресует `tasks/<id>/` — признаки, запрещённые долгоживущему файлу;
долгоживущие тесты — требование 9 SPEC.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (AmendSandbox, MANIFEST_NAME,  # noqa: E402
                      boundary_markers, fixed_run_id, long_lived_source)
from orchestrator import config, review, store  # noqa: E402
from orchestrator.advance_gates import capacity  # noqa: E402

UNIQUE = "# МЕТКА-ТЕКСТА-ДОЛГОЖИВУЩЕГО-ФАЙЛА"
STAT_HEADER = "### Изменённые файлы (git diff --stat"
DIFF_HEADER = "### Diff (git diff "


class ReviewPackageExcludeTest(AmendSandbox):

    def own_source(self) -> str:
        # Перечень лока несёт файл с уникальной строкой — её и ищем.
        return long_lived_source(tail=f"{UNIQUE}\n")

    def setUp(self):
        super().setUp()
        self.stray = f"tests/test_{self.TASK.lower()}_gamma.py"
        self.wt_commit({"feature.py": "print('код фичи')\n",
                        self.stray: long_lived_source(tail="# вне перечня\n")})

    def package(self, **kwargs) -> str:
        with fixed_run_id():
            return review.review_package(store.db(), self.TASK, "песочница",
                                         self.branch, **kwargs)["text"]

    def body_after(self, text: str, header: str) -> str:
        """Тело компонента между граничными маркерами после заголовка."""
        opening, closing = boundary_markers()
        start = text.index(header)
        body_start = text.index(opening, start)
        return text[body_start:text.index(closing, body_start)]

    def assert_excluded(self, text: str, label: str) -> None:
        stat = self.body_after(text, STAT_HEADER)
        diff = self.body_after(text, DIFF_HEADER)
        self.assertNotIn(self.own, stat, f"{label}: файл перечня в стат-списке")
        self.assertNotIn(self.own, diff, f"{label}: файл перечня в diff")
        self.assertNotIn(UNIQUE, diff, f"{label}: текст файла перечня в diff")
        self.assertIn(self.stray, stat, f"{label}: файл вне перечня пропал из стат-списка")
        self.assertIn(self.stray, diff, f"{label}: файл вне перечня пропал из diff")
        self.assertIn("feature.py", diff, f"{label}: код фичи пропал из diff")

    def test_ac7_full_diff_excludes_manifest_file(self):
        """Итерация 1 (полный diff от базы ветки): пути файла перечня нет
        ни в стат-списке, ни в diff; файл с префиксом задачи вне перечня и
        код фичи — на месте.

        Ловит мутацию: исключение выводится по префиксу задачи, а не из
        перечня лока — файл вне перечня тоже пропадает из diff.
        """
        self.assert_excluded(self.package(), "итерация 1")

    def test_ac7_incremental_diff_excludes_manifest_file(self):
        """Итерация 2 с базой вердикта до коммита файла перечня (файл тронут
        собственным коммитом ветки после базы): пути нет ни в стат-списке,
        ни в инкрементальном diff.

        Ловит мутацию: исключение записано длинной формой магии
        `:(exclude,literal)…`, а инкремент отбирает исключения фильтром
        `startswith(":!")` — файл возвращается в инкрементальный diff.
        """
        self.assert_excluded(self.package(iteration=2, prev_sha=self.base_sha),
                             "итерация 2")

    def test_ac7_component_before_stat_inside_boundaries(self):
        """Текст файла перечня (с головы кодовой ветки) — в пакете отдельным
        компонентом: заголовок с путём, тело внутри граничных маркеров
        запуска, всё — до стат-списка.

        Ловит мутацию: компонент добавлен после diff (или без обёртки
        `brief.wrap_boundary`) — ревьювер получает текст теста без границ
        недоверенных данных либо уже после diff.
        """
        text = self.package()
        opening, closing = boundary_markers()
        stat_at = text.index(STAT_HEADER)
        at = text.find(UNIQUE)
        self.assertNotEqual(at, -1, "текста файла перечня нет в пакете")
        self.assertLess(at, stat_at, "компонент обязан идти до стат-списка")
        open_at = text.rfind(opening, 0, at)
        close_at = text.find(closing, at)
        self.assertNotEqual(open_at, -1, "тело компонента вне граничных маркеров")
        self.assertLess(close_at, stat_at)
        self.assertEqual(text.count(closing, open_at, at), 0,
                         "между открывающим маркером и текстом закрыт другой компонент")
        header_at = text.rfind("\n### ", 0, open_at)
        self.assertIn(self.own, text[header_at:open_at],
                      "заголовок компонента обязан назвать путь файла")
        self.assertIn(self.own_text.strip(), text[open_at:close_at])

    def test_ac7_unreadable_manifest_keeps_file_in_diff(self):
        """Перечень в дереве лока испорчен (строка не по формату Р2) — пакет
        собирается, файл перечня остаётся в стат-списке и diff.

        Ловит мутацию: при сбое чтения перечня исключение выводится по
        префиксу задачи (или сборка пакета падает) — файл пропадает из
        поля зрения ревьювера.
        """
        self.artifact_commit({f"acceptance_tests/{MANIFEST_NAME}": "мусор\n"},
                             "испорченный перечень")
        self.set_row(tests_locked_sha=self.heads()[1])

        text = self.package()

        self.assertIn(self.own, self.body_after(text, STAT_HEADER))
        self.assertIn(self.own, self.body_after(text, DIFF_HEADER))


class CapacityGateExcludeTest(AmendSandbox):

    CEILING = 4000
    FILLER = "".join(f"# строка наполнителя {i:04d} {'x' * 40}\n" for i in range(150))

    def own_source(self) -> str:
        return long_lived_source(tail=self.FILLER)

    def gate_refuses(self) -> bool:
        with mock.patch.object(config, "REVIEW_SNAPSHOT_DIFF_MAX_BYTES",
                               self.CEILING):
            return capacity._capacity_gate_refuses(store.db(), self.TASK,
                                                   self.row(), "in_dev")

    def test_ac7_capacity_gate_does_not_measure_manifest_file(self):
        """diff ветки — только файл перечня крупнее потолка: гейт ёмкости
        не отказывает; контроль — такой же файл с префиксом задачи вне
        перечня: гейт отказывает.

        Ловит мутацию: исключение добавлено только в сборку пакета, а мера
        гейта считает по своему pathspec — гейт отказывает по байтам
        файла, которые ревьювер в diff не получает.
        """
        self.assertGreater(len(self.own_text.encode("utf-8")), self.CEILING)
        self.assertFalse(self.gate_refuses(),
                         "байты файла перечня не имеют права входить в меру")
        self.wt_commit({f"tests/test_{self.TASK.lower()}_gamma.py":
                        self.own_text})
        self.assertTrue(self.gate_refuses(),
                        "файл вне перечня обязан мериться гейтом")


if __name__ == "__main__":
    unittest.main()
