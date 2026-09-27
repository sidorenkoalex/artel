"""AC-11 — 01M3GKJ84XM5QPC6TK5EE307Q9: карта кодовой базы вместе с
аддитивным документом сливается одним коммитом; одиночная карта ведёт
себя как сегодня.

Источник — SPEC.md, «Критерии приёмки»:

AC-11. Набор конфликтных файлов «`docs/codebase-map.md` + аддитивный
документ» сливается автоматически: карта разрешена перегенерацией,
документ — аддитивным слиянием, merge завершён одним коммитом подтяжки, в
журнале обе записи (карта и аддитивный конфликт). Набор из одного
`docs/codebase-map.md` ведёт себя как сегодня.

Настоящего `scripts/codebase_map.py` в песочнице нет — база слияния
несёт его заглушку (`_sandbox._MAP_REGENERATOR`), пишущую
`docs/codebase-map.md`: предмет критерия — связка «карта и документ
одним коммитом подтяжки», не содержимое карты, а способ её разрешения
(`checkout --theirs` + запуск `python3 scripts/codebase_map.py` в слитом
дереве) остаётся ровно тем, что делает `pull._auto_resolve_map_conflict`
сегодня.

Красен до реализации: сегодняшнее условие авторазрешения — буквально
`files == [MAP_REL]`, поэтому набор «карта + документ» уходит в
`merge --abort` и `escalated`; первый метод падает на состоянии задачи.
Второй метод (одиночная карта) зелёный с рождения — он и должен таким
остаться: это фиксация сегодняшнего поведения, которое расширение
обязано сохранить.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import pull  # noqa: E402

ADDITIVE_MERGE_PHRASE = "аддитивный конфликт слит"


class MapWithAdditiveDocTest(_sandbox.AdditivePullSandbox):

    def map_journal_entries(self) -> list:
        """Записи журнала, называющие карту и способ её разрешения —
        сегодняшняя запись `pull._auto_resolve_map_conflict`."""
        return [text for text in self.journal_texts()
                if pull.MAP_REL in text and "регенерац" in text.lower()]

    def test_ac11_map_and_additive_doc_merge_in_one_pull_commit(self):
        """Конфликт по `docs/codebase-map.md` и по аддитивному
        документу разрешается целиком: задача остаётся в `in_dev`,
        документ несёт обе добавки, вершина ветки — один коммит
        подтяжки, в журнале и запись о карте, и запись об аддитивном
        конфликте.

        Ловит мутацию: карта и документы разрешаются двумя независимыми
        проходами, каждый со своим `git commit` — по первому родителю
        ветки легло бы два коммита вместо одного, и `assertEqual(1, …)`
        это поймает.
        """
        self.seed_base({pull.MAP_REL: _sandbox.BASE_LINES,
                        _sandbox.DOC_A: _sandbox.BASE_LINES},
                       with_map_regenerator=True)
        self.seed_branch_side({
            rel: list(_sandbox.BASE_LINES) + [_sandbox.BRANCH_LINE]
            for rel in (pull.MAP_REL, _sandbox.DOC_A)})
        self.seed_main_side({
            rel: list(_sandbox.BASE_LINES) + [_sandbox.MAIN_LINE]
            for rel in (pull.MAP_REL, _sandbox.DOC_A)})

        outcome = self.evaluate()

        self.assertIsInstance(
            outcome, pull.Pulled,
            f"набор «карта + аддитивный документ» обязан слиться, "
            f"получено: {outcome!r}")
        self.assertEqual("in_dev", self.state())
        self.assert_all_lines_present(_sandbox.DOC_A)
        self.assertEqual(self.pull_commit_message(), self.head_subject())
        self.assertEqual(1, self.commits_added_to_branch(),
                         "карта и документ обязаны быть завершены ОДНИМ "
                         "коммитом подтяжки")
        self.assertTrue(
            self.map_journal_entries(),
            f"нет записи журнала о разрешении карты регенерацией: "
            f"{self.journal_texts()}")
        self.assertTrue(
            [t for t in self.journal_texts() if ADDITIVE_MERGE_PHRASE in t],
            f"нет записи «{ADDITIVE_MERGE_PHRASE}»: {self.journal_texts()}")

    def test_ac11_map_alone_keeps_todays_behaviour(self):
        """Единственный конфликтный файл — карта: подтяжка завершается
        как сегодня (один коммит подтяжки, запись о регенерации) и НЕ
        пишет записи об аддитивном слиянии.

        Ловит мутацию: карта пропущена через новый аддитивный путь
        (она ведь `docs/**` и обе стороны только дописали строки) —
        вместо перегенерации в ней осталось бы union-склеенное
        содержимое двух карт, а в журнале появилась бы чужая запись
        вместо сегодняшней.
        """
        self.seed_additive_conflict(pull.MAP_REL, with_map_regenerator=True)

        outcome = self.evaluate()

        self.assertIsInstance(outcome, pull.Pulled,
                              f"одиночная карта разрешается как сегодня, "
                              f"получено: {outcome!r}")
        self.assertEqual("in_dev", self.state())
        self.assertEqual(self.pull_commit_message(), self.head_subject())
        self.assertTrue(
            self.map_journal_entries(),
            f"сегодняшняя запись о регенерации карты пропала: "
            f"{self.journal_texts()}")
        self.assertEqual(
            [], [t for t in self.journal_texts()
                 if ADDITIVE_MERGE_PHRASE in t],
            "одиночная карта не аддитивное слияние — лишней записи быть "
            "не должно")


if __name__ == "__main__":
    unittest.main()
