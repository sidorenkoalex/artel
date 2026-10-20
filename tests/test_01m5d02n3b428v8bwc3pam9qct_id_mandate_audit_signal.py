"""Строка мандата на ослабление теста по идентификатору в ANSWER — сигнал аудита SPEC «б) мандат в ANSWER» (AC-10).

Группа: долгоживущий
Красен до реализации: `_MANDATE_MARKERS` аудита SPEC несёт только маркеры зон и прежний маркер тестов — строка «Ослабление теста по идентификатору разрешено: …» сигнала «б)» не даёт.

Свойство проверяется без песочницы: `spec_audit.signals` — чистая функция
текстов SPEC, полей заголовка, ТЗ и ANSWER. SPEC без признаков прочих
сигналов, бюджет ниже порога, ТЗ без ADR.

Провалидировано временным стабом реализации (удалён, не закоммичен): новый
маркер в `_MANDATE_MARKERS` аудита — метод зелёный.

Идентификаторы, отступ строки и её место среди ANSWER — из `random`; зерно
печатается и входит в текст каждого провала.
"""
import random
import unittest

from orchestrator.advance_gates import spec_audit

NEW = "Ослабление теста по идентификатору разрешено:"
SIGNAL = "б) мандат в ANSWER"
LETTERS = "abcdefghijkmnpqrstuvwxyz"

SPEC = """---
task: 01FIXTURE
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: lib/
budget_usd: 1
---

# SPEC: фикстура аудита

## Контекст
Фикстура.

## Требования
1. Правка фикстуры.

## Критерии приёмки
AC-1. Критерий фикстуры.

## Не входит
"""


class IdMandateAuditSignalTest(unittest.TestCase):

    def test_ac10_new_marker_line_in_answer_is_signal_b(self):
        """ANSWER со строкой нового маркера даёт сигнал «б) мандат в ANSWER», называющий эту строку; без неё сигнала нет.

        Несколько случайных входов: набор из одного–трёх текстов ANSWER,
        в одном (на случайном месте) — строка нового маркера с
        идентификатором Vitest (пробелы, « > ») и случайным отступом;
        прочие тексты — абзацы без маркеров. `signals` возвращает строку
        «б) мандат в ANSWER: …», несущую строку маркера (без отступа). Те
        же тексты без строки маркера — сигнала «б)» нет.

        Ловит мутацию: новый маркер не добавлен в `_MANDATE_MARKERS`
        аудита — сигнала «б)» нет, аудит идёт кратким разбором при
        мандате на ослабление; строка распознаётся без `strip` — с
        отступом сигнала нет.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)

        def word(size=6):
            return "".join(rng.choice(LETTERS) for _ in range(size))

        for _ in range(5):
            line = (f"{NEW} c{word()}:src/{word(4)}/{word()}.test.ts::"
                    f"{word()} {word(4)} > {word()} {word(5)}")
            pad = rng.choice(("", "  ", "\t", "    "))
            plain = [f"Ответ Оператора {word()}.\n\nПояснение {word()}.\n"
                     for _ in range(rng.randint(1, 3))]
            at = rng.randrange(len(plain))
            with_line = list(plain)
            with_line[at] = plain[at] + f"\n{pad}{line}\n"
            found = spec_audit.signals(SPEC, {"zones": "lib/"}, "", with_line)
            hits = [s for s in found if s.startswith(SIGNAL)]
            self.assertTrue(hits, f"зерно: {seed}; нет сигнала «{SIGNAL}»: "
                                  f"{found}")
            self.assertIn(line, hits[0], f"зерно: {seed}; {hits}")
            found = spec_audit.signals(SPEC, {"zones": "lib/"}, "", plain)
            self.assertFalse([s for s in found if s.startswith(SIGNAL)],
                             f"зерно: {seed}; сигнал без маркера: {found}")


if __name__ == "__main__":
    unittest.main()
