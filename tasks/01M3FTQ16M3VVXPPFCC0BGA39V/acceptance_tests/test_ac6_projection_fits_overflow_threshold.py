"""AC-6 — 01M3FTQ16M3VVXPPFCC0BGA39V: проекция карты реального дерева
умещается в порог переполнения, сам порог и условие алерта не тронуты.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. Размер проекции карты реального дерева (`project_for_brief` от
содержимого `docs/codebase-map.md`, в байтах UTF-8) не превышает
`config.CONTEXT_FILE_MAX_BYTES`; значение этой константы и условие
алерта переполнения не изменены.

Зелёный с рождения: оба свойства критерия — сохранение (проекция сегодня
63 958 байт при потолке 131 072, порог и условие алерта в
`orchestrator/brief.py` ветка ещё не трогала). Тест — планка против
двух правдоподобных способов «починить» переполнение после +34 модулей
карты: поднять потолок и ослабить условие алерта; SPEC «Не входит»
запрещает и то, и то.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import brief, config  # noqa: E402
from scripts import codebase_map  # noqa: E402

CONFIG_REL = "orchestrator/config.py"
BRIEF_REL = "orchestrator/brief.py"
ALERT_FUNCTION = "_handle_map_size_alert"
_CONST_RE = re.compile(r"^CONTEXT_FILE_MAX_BYTES\s*=\s*([0-9_]+)", re.M)


class ProjectionSizeTest(unittest.TestCase):

    def test_ac6_projection_of_real_map_fits_the_overflow_threshold(self):
        """Проекция карты реального дерева (файл `docs/codebase-map.md`
        рабочей копии, прогнанный через `project_for_brief`) в байтах
        UTF-8 не превышает `config.CONTEXT_FILE_MAX_BYTES`.

        Ловит мутацию: правило проекции для секций подпакетов оставляет
        им все четыре поля (например, `project_for_brief` возвращает
        такие секции как есть) — 34 новых секции с блоками
        «Импортируется» раздувают проекцию, и при исчерпании запаса
        порога `assertLessEqual` покраснеет, вместо того чтобы алерт
        переполнения молча выкинул карту из брифа разработчика.
        """
        self.assertTrue(
            _util.MAP_PATH.is_file(),
            f"{_util.MAP_REL} обязан лежать в рабочей копии — карта "
            f"коммитится в ветку (AC-6)")
        map_text = _util.MAP_PATH.read_text(encoding="utf-8")
        size = len(codebase_map.project_for_brief(map_text).encode("utf-8"))
        self.assertLessEqual(
            size, config.CONTEXT_FILE_MAX_BYTES,
            f"проекция {_util.MAP_REL} — {size} байт при потолке "
            f"config.CONTEXT_FILE_MAX_BYTES = {config.CONTEXT_FILE_MAX_BYTES} "
            f"(AC-6): уточняй правило проекции, не порог")

    def test_ac6_threshold_constant_is_unchanged(self):
        """Значение `config.CONTEXT_FILE_MAX_BYTES` в ветке задачи
        совпадает со значением на точке расхождения с базой интеграции.

        Ловит мутацию: переполнение проекции «починено» подъёмом потолка
        в `orchestrator/config.py` вместо уточнения правила проекции —
        сверка с базой покраснеет (сравнение с литералом такую правку
        тоже поймало бы, но сверка с базой не требует править планку,
        когда потолок законно двинет Оператор отдельным решением).
        """
        base_text = _util.show_at_base(CONFIG_REL)
        self.assertIsNotNone(
            base_text, f"{CONFIG_REL} не читается на точке расхождения (AC-6)")
        match = _CONST_RE.search(base_text)
        self.assertIsNotNone(
            match, f"в {CONFIG_REL} базы нет присваивания "
                   f"CONTEXT_FILE_MAX_BYTES (AC-6)")
        base_value = int(match.group(1).replace("_", ""))
        self.assertEqual(
            base_value, config.CONTEXT_FILE_MAX_BYTES,
            f"порог переполнения обязан остаться прежним: на базе "
            f"{base_value}, в ветке {config.CONTEXT_FILE_MAX_BYTES} (AC-6)")

    def test_ac6_overflow_alert_condition_is_unchanged(self):
        """Условие алерта переполнения (`if` внутри
        `brief._handle_map_size_alert`) в ветке задачи текстуально
        совпадает с условием на точке расхождения, и сам алерт на месте
        (`brief.MAP_OVERSIZED_ALERT_SOURCE` объявлен).

        Ловит мутацию: сравнение в алерте ослаблено (`>` заменено на
        заведомо недостижимое условие, потолок в нём подменён другой
        константой) либо функция алерта переписана/переименована —
        сравнение текста условия с базой покраснеет.
        """
        base_text = _util.show_at_base(BRIEF_REL)
        self.assertIsNotNone(
            base_text, f"{BRIEF_REL} не читается на точке расхождения (AC-6)")
        head_text = (_util.REPO_ROOT / BRIEF_REL).read_text(encoding="utf-8")

        base_cond = _util.first_if_test_source(base_text, ALERT_FUNCTION)
        head_cond = _util.first_if_test_source(head_text, ALERT_FUNCTION)
        self.assertIsNotNone(
            base_cond,
            f"в {BRIEF_REL} базы не нашлось условие алерта в "
            f"{ALERT_FUNCTION} (AC-6)")
        self.assertIsNotNone(
            head_cond,
            f"в {BRIEF_REL} ветки нет функции {ALERT_FUNCTION} с условием "
            f"алерта переполнения — алерт не трогается этой задачей (AC-6)")
        self.assertEqual(
            base_cond, head_cond,
            f"условие алерта переполнения обязано остаться прежним (AC-6)")
        self.assertTrue(brief.MAP_OVERSIZED_ALERT_SOURCE,
                        "источник алерта переполнения обязан остаться "
                        "объявленным (AC-6)")


if __name__ == "__main__":
    unittest.main()
