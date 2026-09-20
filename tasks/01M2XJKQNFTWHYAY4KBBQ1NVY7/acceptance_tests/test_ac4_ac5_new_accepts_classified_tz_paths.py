"""AC-4, AC-5: `new --tz` проходит, когда путь ТЗ классифицирован.

Зелёный с рождения: сегодня `catalog.cmd_new` не сверяет пути ТЗ с зонами вовсе и заводит задачу при любом тексте — эти сценарии проверяют не появление отказа, а его ОТСУТСТВИЕ там, где классификация состоялась, и покраснеют ровно на ложном срабатывании новой сверки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from _new_sandbox import NewWithTzSandbox  # noqa: E402
from orchestrator import config  # noqa: E402


class NewAcceptsClassifiedTzPathTest(NewWithTzSandbox):

    def test_ac4_path_named_in_the_not_included_section_passes(self):
        """Тот же путь, что в AC-2 приводит к отказу, назван в разделе
        «Не входит:» — `new --tz` проходит и заводит задачу.

        Ловит мутацию: классифицирующим считается только раздел «Зоны:»
        (разбор «Не входит:» не написан или его метка не распознана) —
        `new` отказал бы, и строка задачи не появилась бы.
        """
        text = self.run_new(_util.tz_text(
            requires=f"Починить разбор ответа в {_util.UNCLASSIFIED_PATH}.",
            zones=_util.ZONE_PATH,
            not_included=f"{_util.UNCLASSIFIED_PATH} — эта задача его не трогает."))

        _util.assert_no_unclassified_refusal(self, text)
        self.assert_task_created(text)

    def test_ac4_path_named_in_the_read_only_section_passes(self):
        """Тот же путь назван в разделе «Только чтение (не менять):» —
        `new --tz` проходит.

        Ловит мутацию: перечень классифицирующих разделов неполон —
        частый случай — забыт именно «Только чтение…:», у которого
        между меткой и двоеточием стоит хвост «(не менять)»; отказ
        сработал бы на честно классифицированном пути.
        """
        text = self.run_new(_util.tz_text(
            requires=f"Учесть поведение {_util.UNCLASSIFIED_PATH}.",
            zones=_util.ZONE_PATH,
            read_only=f"{_util.UNCLASSIFIED_PATH} (только сверяемся)."))

        _util.assert_no_unclassified_refusal(self, text)
        self.assert_task_created(text)

    def test_ac5_path_under_a_directory_zone_passes(self):
        """Путь ТЗ лежит ПОД каталогом, названным в «Зоны:»: пара
        `tests/test_foo.py` при «Зоны: tests/» из формулировки критерия
        и пара вне `config.COMMON_ZONES` (каталог
        `orchestrator/advance_gates/`), на которой вложенность не может
        быть подменена общими зонами.

        Ловит мутацию: покрытие считается буквальным совпадением строк
        (без `zone_lock._covered_by`) — файл под каталогом-зоной
        остался бы неклассифицированным, и `new` отказал бы.
        """
        cases = ((_util.SPEC_DIR_ZONE, _util.SPEC_DIR_ZONE_FILE),
                 (_util.NESTED_DIR_ZONE, _util.NESTED_DIR_FILE))
        for zone, path in cases:
            with self.subTest(zone=zone):
                before = self.task_count()
                text = self.run_new(
                    _util.tz_text(requires=f"Поправить {path}.", zones=zone),
                    title=f"Фикстура планки {zone}")
                _util.assert_no_unclassified_refusal(self, text)
                self.assertEqual(self.task_count(), before + 1,
                                 f"задача не заведена при зоне {zone}:\n{text}")

    def test_ac5_path_from_common_zones_passes_without_being_in_zones(self):
        """Путь входит в `config.COMMON_ZONES` и в «Зоны:» ТЗ не назван —
        `new --tz` всё равно проходит (общие зоны трогают все задачи).

        Значение берётся из `config.COMMON_ZONES` динамически: правка
        списка Оператором не должна ронять планку.

        Ловит мутацию: `_is_common_zone` не подключён к классификации
        (сверка идёт только с разделом «Зоны:») — общая зона стала бы
        поводом для отказа у каждой второй задачи.
        """
        self.assertIn(_util.COMMON_ZONE_FILE, config.COMMON_ZONES)

        text = self.run_new(_util.tz_text(
            requires=f"Читать константу из {_util.COMMON_ZONE_FILE}.",
            zones=_util.ZONE_PATH))

        _util.assert_no_unclassified_refusal(self, text)
        self.assert_task_created(text)


if __name__ == "__main__":
    unittest.main()
