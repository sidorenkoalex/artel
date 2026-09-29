"""Юнит-тесты исключения долгоживущих файлов перечня лока из diff пакета
ревью и из меры гейта ёмкости (SPEC 01M3NSZ4YWZW9SD5Y6H62ATGRV,
требования 5-6; ADR-0020): `review.snapshot_exclude` — точные пути
перечня лока, а не префикс задачи; исключение действует в полном и в
инкрементальном diff и в мере гейта; текст файла приходит ревьюверу
отдельным компонентом в границах запуска до стат-списка; непрочитанный
перечень оставляет файл в diff.

Планка задачи целиком разовая и после мержа не исполняется — эти тесты
держат требования 5-6 вместо неё (R1-F1 REVIEW.md итерации 1). diff —
настоящий `git diff` песочницы `_LockedSandbox`
(`tests/test_amend_long_lived.py`).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, brief, config, gitcmd, review, store  # noqa: E402
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from orchestrator.advance_gates import capacity  # noqa: E402
from tests.test_amend_long_lived import _LockedSandbox, edited_source  # noqa: E402

RUN_ID = "0123456789abcdef0123456789abcdef"
UNIQUE = "# МЕТКА-ТЕКСТА-ДОЛГОЖИВУЩЕГО-ФАЙЛА"
STAT_HEADER = "### Изменённые файлы (git diff --stat"
DIFF_HEADER = "### Diff (git diff "


def boundary_markers() -> tuple[str, str]:
    lines = brief.wrap_boundary(RUN_ID, "x").split("\n")
    return lines[0], lines[-1]


class ReviewPackageExcludeTest(_LockedSandbox):

    def own_source(self) -> str:
        return edited_source(tail=f"{UNIQUE}\n")

    def setUp(self):
        super().setUp()
        self.stray = f"tests/test_{self.TASK.lower()}_gamma.py"
        self.wt_commit({"feature.py": "print('код фичи')\n",
                        self.stray: edited_source(tail="# вне перечня\n")})

    def package(self, **kwargs) -> str:
        with mock.patch.object(brief, "new_run_id", lambda: RUN_ID):
            return review.review_package(store.db(), self.TASK, "песочница",
                                         self.branch, **kwargs)["text"]

    def body_after(self, text: str, header: str) -> str:
        opening, closing = boundary_markers()
        start = text.index(header)
        body_start = text.index(opening, start)
        return text[body_start:text.index(closing, body_start)]

    def assert_excluded(self, text: str) -> None:
        stat = self.body_after(text, STAT_HEADER)
        diff = self.body_after(text, DIFF_HEADER)
        self.assertNotIn(self.own, stat)
        self.assertNotIn(self.own, diff)
        self.assertNotIn(UNIQUE, diff)
        self.assertIn(self.stray, stat)
        self.assertIn(self.stray, diff)
        self.assertIn("feature.py", diff)

    def test_exclude_is_literal_manifest_paths(self):
        """`snapshot_exclude` — прежние три элемента плюс
        `:(exclude,literal)<путь>` на каждый путь перечня лока; файл с
        префиксом задачи вне перечня не исключается.

        Ловит мутацию: исключение выводится по префиксу задачи или глобом
        без `literal` — под него попадает файл вне перечня.
        """
        self.assertEqual(review.snapshot_exclude(self.TASK),
                         (".", f":!tasks/{self.TASK}/", ":!docs/codebase-map.md",
                          f":(exclude,literal){self.own}"))

    def test_full_diff_excludes_manifest_file(self):
        """Итерация 1 (полный diff): пути файла перечня нет ни в
        стат-списке, ни в diff; файл вне перечня и код фичи на месте.

        Ловит мутацию: `snapshot_exclude` не добавляет пути перечня лока —
        долгоживущий файл снова в diff ревьювера.
        """
        self.assert_excluded(self.package())

    def test_incremental_diff_excludes_manifest_file(self):
        """Итерация 2 с базой вердикта до коммита файла перечня: пути нет
        ни в стат-списке, ни в инкрементальном diff.

        Ловит мутацию: инкремент отбирает исключения фильтром
        `startswith(":!")` — длинная форма `:(exclude,literal)…` выпадает,
        и файл возвращается в инкрементальный diff.
        """
        self.assert_excluded(self.package(iteration=2, prev_sha=self.base_sha))

    def test_component_before_stat_inside_boundaries(self):
        """Текст файла перечня с головы кодовой ветки — отдельный компонент:
        заголовок с путём, тело внутри граничных маркеров запуска, всё до
        стат-списка.

        Ловит мутацию: компонента нет (или он после diff, или без обёртки
        `brief.wrap_boundary`) — ревьювер не видит текста теста либо видит
        его без границ недоверенных данных.
        """
        text = self.package()
        opening, closing = boundary_markers()
        stat_at = text.index(STAT_HEADER)
        at = text.find(UNIQUE)
        self.assertNotEqual(at, -1, "текста файла перечня нет в пакете")
        self.assertLess(at, stat_at)
        open_at = text.rfind(opening, 0, at)
        self.assertNotEqual(open_at, -1)
        self.assertEqual(text.count(closing, open_at, at), 0)
        self.assertLess(text.find(closing, at), stat_at)
        header_at = text.rfind("\n### ", 0, open_at)
        self.assertIn(self.own, text[header_at:open_at])

    def test_unreadable_manifest_keeps_file_in_diff(self):
        """Перечень в дереве лока испорчен: пакет собирается, файл перечня
        остаётся в стат-списке и diff, `snapshot_exclude` — прежний кортеж.

        Ловит мутацию: сбой чтения перечня роняет сборку пакета или
        исключает файлы по префиксу задачи — файл пропадает из поля зрения.
        """
        artifact_branch.commit_files(
            self.TASK, {acceptance_gates.long_lived_manifest_rel(self.TASK):
                        "мусор\n"}, "испорченный перечень")
        self.set_row(tests_locked_sha=gitcmd.branch_head_sha(self.docs_branch))

        text = self.package()

        self.assertIn(self.own, self.body_after(text, STAT_HEADER))
        self.assertIn(self.own, self.body_after(text, DIFF_HEADER))
        self.assertEqual(review.snapshot_exclude(self.TASK),
                         (".", f":!tasks/{self.TASK}/", ":!docs/codebase-map.md"))


class CapacityGateExcludeTest(_LockedSandbox):

    CEILING = 4000
    FILLER = "".join(f"# строка наполнителя {i:04d} {'x' * 40}\n"
                     for i in range(150))

    def own_source(self) -> str:
        return edited_source(tail=self.FILLER)

    def gate_refuses(self) -> bool:
        with mock.patch.object(config, "REVIEW_SNAPSHOT_DIFF_MAX_BYTES",
                               self.CEILING):
            return capacity._capacity_gate_refuses(store.db(), self.TASK,
                                                   self.row(), "in_dev")

    def test_gate_does_not_measure_manifest_file(self):
        """diff ветки — только файл перечня крупнее потолка: гейт ёмкости не
        отказывает; тот же текст файлом с префиксом задачи вне перечня —
        отказывает.

        Ловит мутацию: пути перечня лока не входят в общий узел
        `snapshot_exclude` — гейт мерит байты, которых ревьювер в diff не
        получает, и отказывает.
        """
        text = self.own_source()
        self.assertGreater(len(text.encode("utf-8")), self.CEILING)
        self.assertFalse(self.gate_refuses())
        self.wt_commit({f"tests/test_{self.TASK.lower()}_gamma.py": text})
        self.assertTrue(self.gate_refuses())


if __name__ == "__main__":
    unittest.main()
