"""AC-2 — 01M3H1Z489CKJ8FHSRS4TYTPX2: подзадача без строки «Зоны:» (и с
пустой строкой «Зоны:») оставляет колонку `tasks.zones` равной NULL.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. Создание подзадачи без строки «Зоны:» или с пустой строкой
оставляет её колонку `tasks.zones` равной NULL.

`NULL` — не то же, что пустая строка: признак «зона не заявлена вовсе»
читают `checkpoint._zone_paths` и гейт зон, и подмена его пустой строкой
превращает «зон нет» в «зоны заявлены пустыми».

Зелёный с рождения: сегодня `spawn_subtask` колонку зон не пишет ни при
каком теле подраздела, поэтому для ЭТИХ двух тел ожидаемое поведение уже
наблюдается — тест сохранения существующего поведения. Он краснеет
тогда, когда правка AC-1 запишет зоны безусловно (пустой строкой вместо
отказа от записи), и различие «NULL против пустой строки» потеряется.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402


class SubtaskWithoutZonesKeepsColumnNullTest(_sandbox.SubtaskZoneSandbox):

    def test_ac2_body_without_a_zones_line_leaves_the_column_null(self):
        """Подраздел деления без строки «Зоны:» вовсе: колонка
        `tasks.zones` заведённой подзадачи — ровно `NULL`.

        Ловит мутацию: запись предварительных зон сделана безусловно
        (`store.update_task(conn, task_id, zones=", ".join(items))` без
        проверки пустого перечня) — колонка получила бы пустую строку, и
        фильтр WIP-чекпоинта посчитал бы посторонним любой путь такой
        подзадачи.
        """
        _out, sub_id = self.spawn(_sandbox.TZ_BODY_WITHOUT_ZONES_LINE,
                                  title="Часть без зон")

        self.assertIsNone(
            self.zones_of(sub_id),
            f"колонка tasks.zones подзадачи {sub_id} без строки «Зоны:» "
            f"обязана остаться NULL, получено: "
            f"{self.zones_of(sub_id)!r}")

    def test_ac2_empty_zones_line_leaves_the_column_null(self):
        """Подраздел деления со строкой «Зоны:» без единого пути: та же
        колонка — `NULL`, а не пустая строка и не строка из запятых.

        Ловит мутацию: разбор зон подан в запись без проверки на пустоту
        (или проверяется текст раздела, а не перечень его элементов) —
        пустая строка «Зоны:» дала бы колонку `''`, неотличимую от
        заявленных зон для читателей колонки.
        """
        _out, sub_id = self.spawn(_sandbox.TZ_BODY_EMPTY_ZONES_LINE,
                                  title="Часть с пустой строкой зон")

        self.assertIsNone(
            self.zones_of(sub_id),
            f"колонка tasks.zones подзадачи {sub_id} с пустой строкой "
            f"«Зоны:» обязана остаться NULL, получено: "
            f"{self.zones_of(sub_id)!r}")


if __name__ == "__main__":
    unittest.main()
