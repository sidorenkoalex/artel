"""AC-6: набор сигнатур провалов провайдера `codex` — кортеж с именами
классов из общего набора пульта, неопознанный текст уходит в повтор с
бэкоффом, и наборы двух провайдеров не заимствуют друг у друга тексты.

Непустоты набора планка НЕ требует намеренно: тексты сигнатур эта задача
не выдумывает (SPEC требование 3, «Не входит» — они наполняются по живым
случаям в задаче 6), поэтому проверяются свойства набора и поведение по
умолчанию, а не его состав.

Красен до реализации: `CodexProvider.failure_signatures` ещё не реализован — базовый интерфейс поднимает `NotImplementedError` при первом обращении классификатора.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _stream import PROVIDER, provider  # noqa: E402
from orchestrator import (config, failure_classification,  # noqa: E402
                          providers, runner, store)
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

#: Текст провала, не совпадающий ни с одной сигнатурой ни одного
#: провайдера: ни якоря своего CLI, ни чужих слов.
UNMATCHED_FAILURE_TEXT = "codex: шаг оборвался без объяснимых слов\n"


def signature_texts(entries) -> list:
    """Все тексты-сигнатуры набора одним списком."""
    return [sig for entry in entries for sig in entry.signatures]


class SignatureSetTest(unittest.TestCase):
    """Форма набора и его имена классов."""

    def test_ac6_signatures_are_a_tuple_of_classes_of_the_common_set(self):
        """`failure_signatures()` — кортеж, и каждое имя класса в нём есть
        в общем наборе классов пульта.

        Ловит мутацию: провайдер объявляет собственное имя класса (скажем,
        `codex_limit`) — последствия класса (минутный бэкофф, алерты,
        обрыв повторов) адресата не находят, и `classify_attempt_failure`
        тихо отдаёт `None` на тексте, который сам же и опознал.
        """
        table = provider().failure_signatures()

        self.assertIsInstance(table, tuple)
        for entry in table:
            with self.subTest(entry.failure_class):
                self.assertIn(entry.failure_class,
                              failure_classification.CLASS_LABELS)

    def test_ac6_neither_provider_borrows_the_signatures_of_the_other(self):
        """Ни одна сигнатура Claude не классифицирует текст у `codex`, и
        ни одна сигнатура `codex` — у Claude.

        Ловит мутацию: `failure_signatures` провайдера `codex` возвращает
        готовый набор Claude (самый короткий способ «завести механизм») —
        провал Codex классифицируется по чужим словам, а класс
        детерминированного отказа Claude обрывает повторы шага на тексте,
        которого его CLI никогда не произносит.
        """
        codex = providers.get(PROVIDER)
        claude = providers.get(providers.DEFAULT_PROVIDER)

        self.assertIsNot(codex.failure_signatures(),
                         claude.failure_signatures())
        for text in signature_texts(claude.failure_signatures()):
            with self.subTest(claude=text):
                self.assertIsNone(
                    failure_classification.classify_attempt_failure(text, codex),
                    "сигнатура Claude опознаётся набором codex")
        for text in signature_texts(codex.failure_signatures()):
            with self.subTest(codex=text):
                self.assertIsNone(
                    failure_classification.classify_attempt_failure(text, claude),
                    "сигнатура codex опознаётся набором Claude")


class UnmatchedFailureTest(TaskSeededTmpRootTest):
    """Текст провала мимо всех сигнатур: неизвестный класс — повтор с
    бэкоффом, не детерминированный отказ шага."""

    ROLE = "developer"

    def test_ac6_an_unmatched_failure_text_is_unknown_and_retried(self):
        """Провал с неопознанным текстом остаётся неклассифицированным, и
        цикл попыток шага доигрывает все `config.AGENT_ATTEMPTS` попытки
        с паузами между ними — а не обрывается после первой.

        Число попыток и наличие паузы берутся от `config`, не литералом:
        и потолок попыток, и бэкофф — крутилки Оператора.

        Ловит мутацию: в набор `codex` добавлена «на всякий случай»
        сигнатура-ловушка широкого текста под детерминированный класс
        (`model_unsupported`) либо под `session_limit` — `_run_attempts`
        обрывает цикл на первой попытке, и транзиентный провал Codex
        становится безвозвратным отказом шага без единого повтора.
        """
        failure_class = failure_classification.classify_attempt_failure(
            UNMATCHED_FAILURE_TEXT, providers.get(PROVIDER))
        self.assertIsNone(failure_class,
                          "текст не совпадает ни с одной сигнатурой")

        attempts, pauses = [], []

        def once(conn, task_id, role, prompt, attempt):
            attempts.append(attempt)
            return "failed", UNMATCHED_FAILURE_TEXT, failure_class

        conn = store.db()
        task = store.get_task(conn, self.TASK)
        with mock.patch.object(runner, "run_agent_once", once), \
                mock.patch.object(runner.time, "sleep", pauses.append):
            _, _, resulting_class = runner._run_attempts(
                conn, self.TASK, task, self.ROLE, "промпт шага")

        self.assertEqual(attempts, list(range(1, config.AGENT_ATTEMPTS + 1)))
        self.assertEqual(len(pauses), config.AGENT_ATTEMPTS - 1)
        self.assertTrue(all(pause > 0 for pause in pauses), pauses)
        self.assertIsNone(resulting_class, "класс так и остался неизвестным")


if __name__ == "__main__":
    unittest.main()
