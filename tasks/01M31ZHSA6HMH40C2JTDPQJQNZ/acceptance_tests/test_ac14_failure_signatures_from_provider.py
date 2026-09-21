"""AC-14 — 01M31ZHSA6HMH40C2JTDPQJQNZ: классификация провалившейся
попытки берёт сигнатуры у провайдера роли шага, а классы и их
последствия остаются общими.

Источник — SPEC.md, «Критерии приёмки»:

AC-14. Классификация попытки берёт сигнатуры у провайдера роли шага:
набор классов и их последствия остаются в
`orchestrator/failure_classification.py`, провайдер-заглушка с другими
сигнатурами меняет класс того же текста, а `ClaudeProvider` на текстах
инцидентов даёт те же классы, что до задачи (включая извлечение
требуемой версии CLI из текста класса `model_unsupported`).

Класс попытки читается там, где его читает пульт, — возвратом
`runner.run_agent_once` (третий элемент кортежа): прямой вызов
классификатора зафиксировал бы его сегодняшнюю сигнатуру, которой
требование 9 как раз и не обещает.

Красен до реализации: сигнатуры — литералы модуля
`orchestrator/failure_classification.py` (CLASS_1A_SIGNATURES и соседи),
провайдер роли на классификацию не влияет: под заглушкой с другим
форматом текст инцидента получает ТОТ ЖЕ класс, и `assertNotEqual`
краснеет. Остальные три теста файла зелены и сегодня — это тесты
сохранения существующего поведения: классы шести текстов инцидентов,
извлечение требуемой версии CLI и общий набор классов с его
последствиями переезд сигнатур к провайдеру менять не вправе.
"""
import io
import sys
import unittest
from contextlib import redirect_stdout, suppress
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _provider  # noqa: E402
import _run  # noqa: E402
from orchestrator import failure_classification, runner  # noqa: E402
from tests.sandbox import FakeProc  # noqa: E402

#: Тексты инцидентов и их классы — те же, что классификатор даёт сегодня
#: (`tests/test_failure_classification.py`), литералами: сверка функции с
#: ней же ничего бы не проверила.
INCIDENTS = (
    ("API Error: 403 Request not allowed", "1a"),
    ("сеть: Connection refused, повтор позже", "1b"),
    ("API Error: Connection lost mid-response. The response above may be "
     "incomplete.", "stream_broken"),
    ("API Error: usage limit reached, try later", "session_limit"),
    ("API Error: 529 Overloaded, please retry later", "system_candidate"),
    ("API Error: 400 {\"type\":\"error\",\"error\":{\"message\":\"This "
     "Claude Code version does not support this model; version 2.1.251 or "
     "newer is required\"}}", "model_unsupported"),
)

#: Требуемая версия CLI из текста класса «модель не поддерживается».
REQUIRED_CLI_VERSION = "2.1.251"

#: Текст одного инцидента, на котором сверяются два провайдера.
AUTH_FAILURE, AUTH_CLASS = INCIDENTS[0]


class FailureSignaturesTest(_run.StepRunSandbox):

    def attempt_class(self, text: str):
        """Класс провалившейся попытки — возвратом `run_agent_once`."""
        proc = FakeProc([f"{text}\n"], 1)
        with mock.patch.object(runner, "spawn_agent", return_value=proc):
            with redirect_stdout(io.StringIO()):
                _, _, failure_class = runner.run_agent_once(
                    self.conn, self.TASK, self.ROLE, "промпт шага", 1)
        return failure_class

    def test_ac14_claude_signatures_still_give_the_same_classes(self):
        """Шесть текстов инцидентов получают у провайдера `claude` те же
        классы, что до задачи, и все они — из общего набора классов.

        Ловит мутацию: при переезде сигнатур к провайдеру теряется
        порядок проверки — специфичные списки перестают перехватывать
        текст раньше общего якоря «API Error:», и детерминированный
        отказ «модель не поддерживается» снова лечится тремя попытками
        с минутным бэкоффом.
        """
        for text, expected in INCIDENTS:
            with self.subTest(expected=expected):
                self.assertEqual(self.attempt_class(text), expected)
                self.assertIn(expected, failure_classification.CLASS_LABELS)

    def test_ac14_required_cli_version_is_still_extracted(self):
        """Отказ шага по классу «модель не поддерживается CLI»
        по-прежнему называет требуемую версию CLI из текста попытки.

        Ловит мутацию: извлечение версии переехало к провайдеру, а точка
        отказа осталась звать общий модуль (или наоборот) — Оператор
        получает отказ без числа, до которого надо поднять CLI или
        запись модели в каталоге.
        """
        text = INCIDENTS[-1][0]

        with suppress(SystemExit):
            self.run_stream([f"{text}\n"], rc=1)

        detail = self.details(runner.MODEL_UNSUPPORTED_REFUSAL_ACTION)[-1]
        self.assertIn(REQUIRED_CLI_VERSION, detail)

    def test_ac14_stub_provider_changes_the_class_of_the_same_text(self):
        """Один и тот же текст инцидента получает у провайдера `claude`
        и у провайдера-заглушки с другими сигнатурами разные классы.

        Ловит мутацию: сигнатуры остались литералами общего модуля —
        второй провайдер, чей CLI пишет об отказе авторизации своими
        словами, получит «класс не распознан», останется без бэкоффа
        связки транзиентных и молча сожжёт все попытки шага.

        Сверяется ровно то, что называет критерий: класс ИЗМЕНИЛСЯ.
        Обратную сторону («заглушка читает свой формат») проверяет
        AC-8 на разборе строки потока — там формат приходит аргументом
        при любом раскладе, а сигнатуры провал может объявлять и
        таблицей, к тексту которой заглушке не подобраться.
        """
        self.assertEqual(self.attempt_class(AUTH_FAILURE), AUTH_CLASS)

        _provider.register(self, _provider.stub_format_provider_class()(),
                           self.ROLE)

        self.assertNotEqual(self.attempt_class(AUTH_FAILURE), AUTH_CLASS,
                            "класс текста не зависит от провайдера роли")

    def test_ac14_classes_and_their_consequences_stay_common(self):
        """Набор классов, их подписи и связка транзиентных системных
        остаются в `orchestrator/failure_classification.py`.

        Ловит мутацию: вместе с сигнатурами к провайдеру уезжает и набор
        классов — последствия (бэкофф связки, алерты «обрыв потока» и
        «session limit», обрыв повторов у `model_unsupported`) начинают
        зависеть от провайдера, хотя требование 9 держит их общими.
        """
        labels = failure_classification.CLASS_LABELS

        for _, expected in INCIDENTS:
            self.assertIn(expected, labels)
        self.assertEqual(failure_classification.TRANSIENT_SYSTEM_CLASSES,
                         ("1a", "1b", "system_candidate"))
        self.assertNotIn(failure_classification.MODEL_UNSUPPORTED_CLASS,
                         failure_classification.TRANSIENT_SYSTEM_CLASSES)


if __name__ == "__main__":
    unittest.main()
