"""Юнит-тесты сверки путей ТЗ с зонами в `orchestrator/catalog.py`
(SPEC 01M2XJKQNFTWHYAY4KBBQ1NVY7, требования 2-4): `_tz_sections`,
`_tz_path_check`, `_tz_path_refusal` и отказ `cmd_new` ДО заведения.

Приёмочная планка задачи закрывает сквозные сценарии AC-2..AC-7; здесь
— разбор разделов ТЗ в формате сегодняшних ТЗ Оператора (образец —
`tasks/01M2XFSE8G3MBRHHQR38H53J1M/TZ.md`): многословная метка «Только
чтение (не менять):» как граница раздела «Зоны:», перенос строки зон,
две причины отказа одним текстом, отсутствие расхода id/строки/ветки.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import InitializedTmpRootTest, resilient_tmp_cleanup  # noqa: E402

EXISTING = ("orchestrator/catalog.py", "orchestrator/fsm.py",
            "orchestrator/zone_lock.py", "scripts/guard.py",
            "templates/SPEC.md", "tests/test_foo.py")


def seed(root: Path) -> None:
    for rel in EXISTING:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# фикстура\n", encoding="utf-8")


TZ_REAL_FORMAT = """Источник: копилка.

Требуется:
1. Починить orchestrator/fsm.py и scripts/guard.py.
2. Учесть orchestrator/zone_lock.py.

Зоны: orchestrator/catalog.py, scripts/guard.py,
tests/.
Только чтение (не менять): orchestrator/zone_lock.py (`_covered_by` —
переиспользовать), templates/SPEC.md (формат не меняется).

Не входит: изменение orchestrator/fsm.py.

Рамка: $45.
"""


class TzSectionsTest(unittest.TestCase):

    def test_multiword_label_ends_the_zones_section_without_blank_line(self):
        """«Только чтение (не менять):» сразу за перенесённой строкой
        «Зоны:» (без пустой строки) закрывает раздел зон: тело зон —
        два физических ряда, без текста «Только чтение».

        Ловит мутацию: граница раздела — однословный `_TZ_LABEL_LINE`
        (не `_TZ_ANY_LABEL_LINE`) — раздел «Зоны:» поглотил бы «Только
        чтение…», и защищённый `templates/SPEC.md` оттуда считался бы
        зоной."""
        body, spans = catalog._tz_sections(TZ_REAL_FORMAT, (catalog._TZ_ZONES_LABEL,))

        self.assertIn("tests/.", body)
        self.assertNotIn("Только чтение", body)
        self.assertEqual(len(spans), 1)

    def test_declaring_sections_are_collected_with_the_parenthesised_label(self):
        """Тела «Только чтение (не менять):» и «Не входит:» собираются
        вместе; их диапазоны не пересекаются с телом «Зоны:».

        Ловит мутацию: метка «Только чтение» ищется без хвоста
        `[^:\\n]*` — раздел со скобками не распознан, путь из него
        остался бы неклассифицированным."""
        body, spans = catalog._tz_sections(TZ_REAL_FORMAT,
                                           catalog._TZ_DECLARING_LABELS)

        self.assertIn("orchestrator/zone_lock.py", body)
        self.assertIn("templates/SPEC.md", body)
        self.assertIn("orchestrator/fsm.py", body)
        self.assertEqual(len(spans), 2)


class TzPathCheckTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name)
        seed(self.root)
        patcher = mock.patch.object(config, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_real_format_tz_is_fully_classified(self):
        """ТЗ в формате Оператора: `orchestrator/fsm.py` — в «Не входит»,
        `orchestrator/zone_lock.py`/`templates/SPEC.md` — в «Только
        чтение», `scripts/guard.py` — в «Зоны:», защищённых зон нет.

        Ловит мутацию: классифицирующие разделы вычитаются из
        проверяемого текста не все (или защищённость сверяется по всему
        ТЗ, а не по «Зоны:») — `_tz_path_check` вернул бы непустой
        список."""
        self.assertEqual(catalog._tz_path_check(TZ_REAL_FORMAT), ([], []))

    def test_unclassified_and_protected_are_reported_together(self):
        """Путь в «Требуется» вне зон и защищённый путь в «Зоны:» — обе
        причины в одном тексте `_tz_path_refusal`, каждая со своим
        адресом.

        Ловит мутацию: отказ возвращает первую найденную причину —
        Оператор чинил бы ТЗ в два захода."""
        tz = ("Требуется:\n1. Починить orchestrator/fsm.py.\n\n"
              "Зоны: orchestrator/catalog.py, templates/SPEC.md.\n")

        text = catalog._tz_path_refusal("TZ.md", tz)

        self.assertIn("orchestrator/fsm.py", text)
        self.assertIn(guard.UNCLASSIFIED_PATH_HINT, text)
        self.assertIn("templates/SPEC.md", text)
        self.assertIn(guard.PROTECTED_ZONE_REFUSAL, text)

    def test_clean_tz_gives_no_refusal(self):
        """ТЗ без нарушений — `None`.

        Ловит мутацию: `_tz_path_refusal` возвращает пустую строку вместо
        `None` — `cmd_new` (`if refusal is not None`) отказал бы пустым
        текстом каждому ТЗ."""
        self.assertIsNone(catalog._tz_path_refusal(
            "TZ.md", "Требуется:\n1. Ничего.\n\nЗоны: tests/.\n"))


class CmdNewRefusesBeforeSideEffectsTest(InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        seed(self.root)
        self.tz_file = self.root / "TZ.md"

    def test_refusal_happens_before_id_row_and_branch(self):
        """Отказавший `new --tz` не зовёт ни `idgen.new_task_id`, ни
        `_new_task_row`: id не расходуется, строки и ветки нет; текст
        отказа — `SystemExit` с именем файла и подсказкой.

        Ловит мутацию: сверка перенесена ниже по `cmd_new` (например, к
        подсказке калибровки) — `_new_task_row` уже отработал бы."""
        self.tz_file.write_text(
            "Требуется:\n1. Починить orchestrator/fsm.py.\n\n"
            "Зоны: orchestrator/catalog.py.\n", encoding="utf-8")

        with mock.patch.object(catalog, "_new_task_row") as row, \
                mock.patch.object(catalog.idgen, "new_task_id") as new_id, \
                self.assertRaises(SystemExit) as ctx:
            catalog.cmd_new("Фикстура", str(self.tz_file))

        row.assert_not_called()
        new_id.assert_not_called()
        self.assertIn("orchestrator/fsm.py", str(ctx.exception.code))
        self.assertIn(guard.UNCLASSIFIED_PATH_HINT, str(ctx.exception.code))

    def test_classified_tz_reaches_task_creation(self):
        """ТЗ, где тот же путь назван в «Не входит:», доходит до
        `_new_task_row`.

        Ловит мутацию: разбор «Не входит:» не подключён — честное ТЗ
        отказало бы до заведения."""
        self.tz_file.write_text(
            "Требуется:\n1. Учесть orchestrator/fsm.py.\n\n"
            "Зоны: orchestrator/catalog.py.\n\n"
            "Не входит: правка orchestrator/fsm.py.\n", encoding="utf-8")

        with mock.patch.object(catalog, "_new_task_row") as row, \
                mock.patch.object(catalog, "_warn_pin_divergence"):
            self.capture(catalog.cmd_new, "Фикстура", str(self.tz_file))

        row.assert_called_once()


if __name__ == "__main__":
    unittest.main()
