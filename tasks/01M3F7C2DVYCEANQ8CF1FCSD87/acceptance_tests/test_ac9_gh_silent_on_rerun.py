"""AC-9: `gh` не отвечает на запуск повтора или на ожидание.

Красен до реализации: команды `ci-rerun` в пульте нет вовсе — `resolve_command`
не находит обработчика ни в таблице команд `orchestrator/artel.py`, ни по
очевидным адресам, и `run_ci_rerun` валит тест этим сообщением.

Молчание `gh` в фикстуре начинается ИМЕННО с повтора и держится дальше
(`gh_down_after_rerun`): предусловия команда успела прочитать, а запуск/
ожидание и любой последующий опрос статуса — уже нет. Это тот же
best-effort, что несёт `ci.trigger_rerun` (сбой не бросает исключение) —
команда обязана довести его до именованного отказа и записи журнала, а не
до трейсбека.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import REASON, CiRerunSandbox, names_gh_silence  # noqa: E402


class GhSilentOnRerunTest(CiRerunSandbox):
    """Два обстоятельства молчания `gh` — два ОТДЕЛЬНЫХ теста, не подслучая
    одного: повтор с тем же основанием второй раз по той же задаче
    отказывает сам (требование 10), и второй подслучай внутри одного метода
    проверял бы не молчание `gh`, а повторное основание."""

    def _assert_named_refusal_with_gh_silence(self, label: str) -> None:
        """Общая часть обоих обстоятельств: отказ именованный, запись
        журнала называет «`gh` не ответил», состояние не тронуто."""
        before = self.last_step_id()

        text = self.run_ci_rerun(REASON)
        records = self.journal_since(before)

        self.assertTrue(
            text.strip(),
            f"{label}: отказ обязан быть именованным — команда промолчала")
        self.assertTrue(
            any(names_gh_silence(record) for record in records),
            f"{label}: запись журнала обязана называть исход «gh не "
            f"ответил»; записи: {records}")
        self.assertEqual(
            self.state(), "verifying",
            "команда не меняет состояние задачи (требование 9)")
        self.assertEqual(
            self.state_transitions_since(before), [],
            "перехода FSM команда не делает")

    def test_ac9_gh_silent_on_rerun_start_refuses_without_traceback(self):
        """`gh` не ответил на ЗАПУСК повтора — отказ и запись журнала.

        `gh run rerun` отвечает ненулевым кодом, дальше `gh` молчит на всё.
        Команда обязана завершиться именованным отказом — не исключением и
        не трейсбеком: любое исключение, кроме `SystemExit` именованного
        отказа, `run_ci_rerun` наружу пропускает, и тест падает именно на нём.

        Ловит мутацию: исход `gh не ответил` не различается вовсе (текст
        `ci.trigger_rerun` журналируется как успешный повтор) — Оператор
        прочитал бы «повтор запущен» там, где не запущено ничего, и ждал бы
        зелёного CI, которого никто не перезапускал.
        """
        self.enter_verifying_red()
        self.rerun_rc = 1
        self.rerun_stderr = "gh: could not connect to api.github.com"
        self.gh_down_after_rerun = True

        self._assert_named_refusal_with_gh_silence("запуск повтора")

    def test_ac9_gh_silent_on_wait_refuses_without_traceback(self):
        """`gh` не ответил на ОЖИДАНИЕ повтора — отказ и запись журнала.

        `gh run rerun` прошёл, а `gh run watch` ответил ненулевым кодом, и
        дальше `gh` молчит на всё (в том числе на любой повторный опрос
        статуса). Исход ожидания неизвестен — значит не зелёный (инвариант
        19), и журнал обязан называть именно молчание `gh`, а не успех.

        Ловит мутацию: исход определяется только по коду запуска повтора
        (`gh run rerun`), а сбой ожидания не различается — запись журнала
        сообщала бы Оператору состоявшийся зелёный повтор при неизвестном
        исходе.
        """
        self.enter_verifying_red()
        self.watch_rc = 1
        self.watch_stderr = "gh: could not connect to api.github.com"
        self.gh_down_after_rerun = True

        self._assert_named_refusal_with_gh_silence("ожидание повтора")


if __name__ == "__main__":
    unittest.main()
