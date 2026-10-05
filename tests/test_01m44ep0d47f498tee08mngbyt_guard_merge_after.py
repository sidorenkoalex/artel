"""Проверка формы поля `merge_after` SPEC структурной проверкой guard (AC-1).

Группа: долгоживущий
Красен до реализации: guard сегодня поле merge_after не знает вовсе — самоссылка, повтор и элемент не в формате id проходят без единой ошибки по полю; тесты «корректный список» и «поля нет» зелёные с рождения.

Предмет — `guard.check` по файлу SPEC (то же ядро, которое исполняет
`python3 scripts/guard.py <файл>` для каждого переданного пути). Ошибка
«по полю» — строка вывода guard, в которой названо поле `merge_after`:
посторонние нарушения фикстуры (если появятся) на исход не влияют. Id
задач порождаются заново на каждый запуск (`idgen.new_task_id`), версия
схемы и префиксная форма элементов — от зерна; зерно печатается и входит в
текст каждого провала.
"""
import random
import re
import tempfile
import unittest
from pathlib import Path

from orchestrator import idgen
from scripts import guard

FIELD = "merge_after"

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: {version}
zones: orchestrator/catalog.py
budget_usd: 30
{field_line}---

# SPEC: фикстура поля зависимостей мержа

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстура.

## Не входит

Ничего.
"""

REPEAT_WORDS = re.compile(r"повтор|дубл|дважды", re.IGNORECASE)


class GuardMergeAfterFieldTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def element(self, task_id: str) -> str:
        """Полный id либо его префикс (длина — от зерна)."""
        if self.rng.random() < 0.5:
            return task_id
        return task_id[:self.rng.randint(8, len(task_id) - 1)]

    def field_errors(self, field_value, *, task: str, version: int = 5) -> list[str]:
        field_line = "" if field_value is None else f"{FIELD}: {field_value}\n"
        path = self.tdir / f"SPEC-{self.rng.randrange(1 << 30)}.md"
        path.write_text(SPEC_TEXT.format(task=task, version=version,
                                         field_line=field_line),
                        encoding="utf-8")
        return [e for e in guard.check(path) if FIELD in e]

    def test_ac1_self_reference_names_field_and_element(self):
        """SPEC, чей `merge_after` называет id из поля `task:`, получает ошибку guard.

        Сценарий: id задачи свежий; `merge_after` несёт ровно его (версия
        схемы — любая из 1-5, от зерна: проверка формы действует для SPEC
        любой версии). Хотя бы одна строка ошибки называет и поле, и сам
        элемент.

        Ловит мутацию: сверка с полем `task:` пропущена (проверяются только
        формат и повторы) — guard молчит о самоссылке, ни одной строки с
        `merge_after` в выводе нет.
        """
        task = idgen.new_task_id()
        version = self.rng.randint(1, guard.SUPPORTED_SCHEMA_VERSION)

        errors = self.field_errors(task, task=task, version=version)

        self.assertTrue([e for e in errors if task in e], self.note(
            f"нет ошибки, называющей {FIELD} и {task} (schema_version "
            f"{version}): {errors}"))

    def test_ac1_repeated_element_is_a_repeat_error(self):
        """Повтор одного и того же элемента — ошибка guard о повторе.

        Сценарий: другой (чужой) id или его префикс стоит в `merge_after`
        дважды подряд через запятую; вторым входом — образец критерия
        `01M446X1, 01M446X1`. Строка ошибки называет поле, сам элемент и
        говорит о повторе.

        Ловит мутацию: элементы собираются во множество до проверки — повтор
        схлопывается молча, ошибки о нём нет.
        """
        task = idgen.new_task_id()
        cases = [self.element(idgen.new_task_id()), "01M446X1"]
        for repeated in cases:
            with self.subTest(element=repeated):
                errors = self.field_errors(f"{repeated}, {repeated}", task=task)

                self.assertTrue(
                    [e for e in errors if repeated in e and REPEAT_WORDS.search(e)],
                    self.note(f"нет ошибки о повторе {repeated}: {errors}"))

    def test_ac1_element_not_in_task_id_format_is_a_form_error(self):
        """Элемент не в формате id задачи пульта — ошибка формы по полю.

        Сценарий: `merge_after: foo bar` (образец критерия) и тот же
        элемент рядом с корректным id в начале или в конце списка (от
        зерна). Каждый вход даёт хотя бы одну ошибку по полю.

        Ловит мутацию: проверка формата элемента снята (остаются только
        самоссылка и повтор) — `foo bar` проходит без ошибки.
        """
        task = idgen.new_task_id()
        valid = self.element(idgen.new_task_id())
        mixed = (f"foo bar, {valid}" if self.rng.random() < 0.5
                 else f"{valid}, foo bar")
        for value in ("foo bar", mixed):
            with self.subTest(value=value):
                errors = self.field_errors(value, task=task)

                self.assertTrue(errors, self.note(
                    f"{FIELD}: {value} прошёл guard без ошибки формы"))

    def test_ac1_valid_list_and_missing_field_pass(self):
        """Корректный список из двух разных id и SPEC без поля проходят без ошибок по полю.

        Сценарий: два свежих чужих id (каждый полностью или префиксом, от
        зерна) через запятую; отдельно — SPEC каждой версии 1-5 без поля
        `merge_after`. Ни одна строка ошибки guard не называет поле;
        `guard.SUPPORTED_SCHEMA_VERSION` остаётся 5.

        Ловит мутацию: поле объявлено обязательным (ошибка «нет
        merge_after» у SPEC без поля) либо разделитель «запятая с пробелом»
        не распознаётся и корректный список читается одним негодным
        элементом — тогда в выводе появляется строка с `merge_after`.
        """
        self.assertEqual(guard.SUPPORTED_SCHEMA_VERSION, 5)
        task = idgen.new_task_id()
        first, second = idgen.new_task_id(), idgen.new_task_id()
        while second == first:
            second = idgen.new_task_id()
        value = f"{self.element(first)}, {self.element(second)}"
        if value.split(", ")[0] == value.split(", ")[1]:
            value = f"{first}, {second}"

        self.assertEqual(self.field_errors(value, task=task), [],
                         self.note(f"корректный список {value!r}"))
        for version in range(1, guard.SUPPORTED_SCHEMA_VERSION + 1):
            with self.subTest(schema_version=version):
                self.assertEqual(
                    self.field_errors(None, task=task, version=version), [],
                    self.note(f"SPEC без поля, schema_version {version}"))


if __name__ == "__main__":
    unittest.main()
