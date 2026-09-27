"""AC-1 — 01M3H1Z489CKJ8FHSRS4TYTPX2: подзадача деления с непустой
строкой «Зоны:» получает предварительные зоны в колонке `tasks.zones` и
запись о них в своём журнале; ссылка на родителя разбору не мешает.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. После создания подзадачи с непустой строкой «Зоны:» в её `tz_body`
колонка `tasks.zones` содержит предварительные зоны, а в журнале
подзадачи есть запись предварительных зон; строка «Родительская задача:
…» в её `TZ.md` не мешает разбору.

Запись журнала ищется по фиксированному действию `catalog.
PRELIMINARY_ZONES_ACTION` — существующая общая механика записи
предварительных зон (её же зовёт `cmd_new`), а не новое действие: SPEC
требование 1 предписывает подзадаче ту же механику, и Оператор читает
журнал по тому же действию.

`TZ.md` подзадачи читается ИЗ АРТЕФАКТНОЙ ВЕТКИ
(`artifact_branch.read_tree`), а не с диска: на прогоне гейта в рабочей
копии лежит один `acceptance_tests/`.

Красен до реализации: сегодняшний `catalog.spawn_subtask` зон не
записывает вовсе (единственный вызыватель `_record_preliminary_zones` —
`cmd_new`), поэтому колонка `tasks.zones` подзадачи остаётся `NULL` и
записи «предварительные зоны из ТЗ» в её журнале нет — падают оба
ассерта.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import artifact_branch, catalog  # noqa: E402


class SubtaskRecordsPreliminaryZonesTest(_sandbox.SubtaskZoneSandbox):

    def test_ac1_zones_column_and_journal_carry_the_declared_zones(self):
        """Подзадача заведена с телом, чья строка «Зоны:» называет два
        пути: колонка `tasks.zones` несёт ровно их, а в журнале ЭТОЙ
        подзадачи есть запись предварительных зон, называющая те же пути.

        Ловит мутацию: разработчик записал зоны не в строку подзадачи, а
        оставил их родителю (или записал колонку, не журналируя) —
        подзадача осталась бы невидимой прогнозу очереди зон, ради
        которого задача и заведена, а Оператор не узнал бы из журнала,
        откуда взялось значение колонки.
        """
        declared = {_sandbox.SHARED_ZONE, _sandbox.OTHER_ZONE}

        _out, sub_id = self.spawn(
            _sandbox.tz_body(f"{_sandbox.SHARED_ZONE}, {_sandbox.OTHER_ZONE}"))

        self.assertEqual(
            declared, _sandbox.zone_set(self.zones_of(sub_id)),
            f"колонка tasks.zones подзадачи {sub_id} не несёт зон её ТЗ: "
            f"{self.zones_of(sub_id)!r}")
        details = self.journal_details(sub_id, catalog.PRELIMINARY_ZONES_ACTION)
        self.assertTrue(
            details,
            f"в журнале подзадачи {sub_id} нет записи с действием "
            f"«{catalog.PRELIMINARY_ZONES_ACTION}»: "
            f"{self.journal_actions(sub_id)}")
        for zone in sorted(declared):
            self.assertIn(
                zone, " | ".join(details),
                f"запись предварительных зон не называет зону {zone}: "
                f"{details}")

    def test_ac1_parent_link_line_does_not_break_the_zones_parsing(self):
        """Собранный `TZ.md` подзадачи действительно начинается ссылкой
        «Родительская задача: …», стоящей ровно перед строкой «Зоны:», —
        и при этом в колонке зон только заявленные зоны: путь, названный
        в НАЗВАНИИ родителя (и потому попавший в ту же ссылку), зоной
        подзадачи не становится.

        Ловит мутацию: на разбор подан текст, в котором строка «Зоны:»
        уже не начинает строку (ссылка приклеена к телу без перевода
        строки) — заякоренный на начало строки разбор `_tz_zone_items`
        не найдёт ничего, и колонка останется `NULL`; либо зоны собраны
        по ВСЕМУ тексту `TZ.md` вместо раздела «Зоны:» — тогда в колонку
        затечёт путь из названия родителя.
        """
        _out, sub_id = self.spawn(_sandbox.tz_body(_sandbox.SHARED_ZONE))

        tree = artifact_branch.read_tree(sub_id)
        tz = tree[f"tasks/{sub_id}/TZ.md"]
        link_line = (f"Родительская задача: {_sandbox.PARENT_ID} — "
                     f"{_sandbox.PARENT_TITLE}")
        lines = tz.splitlines()
        self.assertIn(link_line, lines, f"TZ.md подзадачи не несёт ссылки "
                                        f"на родителя:\n{tz}")
        self.assertTrue(
            lines[lines.index(link_line) + 1].startswith("Зоны:"),
            f"сценарий критерия не воспроизведён: строка «Зоны:» не идёт "
            f"сразу за ссылкой на родителя:\n{tz}")

        self.assertEqual(
            {_sandbox.SHARED_ZONE}, _sandbox.zone_set(self.zones_of(sub_id)),
            f"колонка зон подзадачи {sub_id} разошлась с её строкой "
            f"«Зоны:» (путь {_sandbox.PATH_IN_PARENT_TITLE} назван только "
            f"в ссылке на родителя): {self.zones_of(sub_id)!r}")


if __name__ == "__main__":
    unittest.main()
