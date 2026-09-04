"""AC-4 (tasks/01M1NBWRTAHSX9FQGTQWENY80A/SPEC.md): «Компоненты
ANSWER-n.md учитываются в общем размере тела пакета, передаваемом в
context_package.discipline, и делятся на пронумерованные части по общему
правилу вместе с остальными компонентами — не получают исключения из
потолка части.»

`test_ac4_a_large_answer_alone_pushes_the_package_into_numbered_parts` —
КРАСЕН до реализации: `review.review_package` сегодня вообще не читает
ANSWER-n.md (см. докстринг test_ac1) — крупный ANSWER-файл сегодня никак
не мог бы раздуть тело пакета сверх `config.CONTEXT_PART_MAX_BYTES` и
вызвать деление на части: остальные компоненты фикстуры (SPEC/PLAN/
diff/stat из `AnswerInReviewPackageSandbox`) сами по себе далеко меньше
потолка части.

`test_ac4_without_the_large_answer_the_same_task_does_not_split` —
ЗЕЛЁНЫЙ с рождения (контрольная пара к первому, без ANSWER вовсе —
поведение не зависит от реализации этой задачи).

Потолок — `config.CONTEXT_PART_MAX_BYTES`, не литерал: тест берёт значение
динамически (см. skill test-authoring, «Предпосылки о значениях
конфигурации»), переживёт правку Оператором этого потолка.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402
from _sandbox import AnswerInReviewPackageSandbox  # noqa: E402

ANSWER_HEADER = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: большой батч AC-4

## Ответы

"""


class Ac4AnswerCountsTowardPartSplitTest(AnswerInReviewPackageSandbox):

    def big_answer_text(self) -> str:
        """ANSWER-компонент сам по себе крупнее потолка части
        (`CONTEXT_PART_MAX_BYTES`), но заведомо меньше потолка файла
        (`CONTEXT_FILE_MAX_BYTES`) — иначе он был бы целиком пропущен как
        «превышен лимит файла» (`context_package.FILE_CAP_REASON`), и тест
        проверял бы не то деление, что нужно AC-4.

        Наполнитель — ASCII («z»), не кириллица: кириллический символ в
        UTF-8 занимает 2 байта при подсчёте `filler_len` символами —
        итоговый размер компонента вышел бы вдвое больше расчётного и
        пробил бы потолок ФАЙЛА вместо потолка ЧАСТИ (обнаружено при
        валидации теста стабом реализации — компонент пропускался как
        «превышен лимит файла», а не делился)."""
        header = ANSWER_HEADER.format(task=self.TASK)
        filler_len = config.CONTEXT_PART_MAX_BYTES - len(header.encode("utf-8")) + 4096
        self.assertLess(
            filler_len + len(header.encode("utf-8")),
            config.CONTEXT_FILE_MAX_BYTES,
            "предпосылка теста нарушена: ANSWER крупнее потолка файла "
            "целиком — сам компонент был бы пропущен, а не разделён")
        return header + ("z" * filler_len) + "\nМАРКЕР-КОНЦА-AC4-b58e\n"

    def test_ac4_a_large_answer_alone_pushes_the_package_into_numbered_parts(self):
        """Единственный ANSWER-компонент крупнее потолка части (остальные
        компоненты пакета — маленькие) — пакет обязан разделиться на
        пронумерованные части, а не остаться одним куском текста.

        Ловит мутацию: реализация добавляет ANSWER-компонент К ТЕКСТУ
        пакета уже ПОСЛЕ вызова `context_package.discipline` (например,
        конкатенацией строкой в конце), минуя пересчёт размера тела —
        тогда деление на части не сработает, части не появятся, а
        добавленный ANSWER-текст останется недоделённым довеском.
        """
        self.add_answer(1, self.big_answer_text())

        self.run_agent("review")

        package = self.package_text()
        self.assertIn("--- ЧАСТЬ 1/", package,
                      "крупный ANSWER-компонент не привёл к делению пакета "
                      "на пронумерованные части — не учтён в общем размере "
                      "тела (AC-4)")
        self.assertIn("МАРКЕР-КОНЦА-AC4-b58e", package,
                      "содержимое крупного ANSWER-компонента потеряно при "
                      "делении на части")
        detail = self.journal_details("ревью-пакет собран")[0]
        self.assertIn("поделён на", detail,
                      "число частей не попало в журнал пакета")

    def test_ac4_without_the_large_answer_the_same_task_does_not_split(self):
        """Контрольная пара к предыдущему тесту: ТА ЖЕ задача (тот же
        SPEC/PLAN/diff/stat фикстуры), но БЕЗ крупного ANSWER-файла — не
        делится на части вовсе. Доказывает, что деление в предыдущем
        тесте вызвано именно объёмом ANSWER-компонента, а не посторонней
        причиной (например, случайно раздутым SPEC/PLAN фикстуры).

        Ловит мутацию: реализация форсирует деление пакета на части
        безусловно (например, задев общий путь `discipline` регрессией)
        — тогда деление появилось бы и здесь, без крупного ANSWER, и тест
        покраснел бы на `assertNotIn`.
        """
        self.run_agent("review")

        self.assertNotIn("--- ЧАСТЬ 1/", self.package_text(),
                         "пакет без крупного ANSWER неожиданно поделён на "
                         "части — деление не связано с объёмом ANSWER")


if __name__ == "__main__":
    import unittest
    unittest.main()
