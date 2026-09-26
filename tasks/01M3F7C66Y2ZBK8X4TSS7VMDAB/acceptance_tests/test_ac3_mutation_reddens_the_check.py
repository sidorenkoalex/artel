"""AC-3: проверка закрытости краснеет на мутации «соединение не закрыто и
объект жив» — ровно то состояние, в котором тест оставляет `del conn`.

Мутация ставится не текстом теста, а окружением: `close()` затравочного
соединения становится пустышкой, а сам объект соединения удерживается
сильной ссылкой. Это воспроизводит `del conn` в ссылочном цикле
(SPEC, «Контекст») детерминированно: соединение остаётся открытым И живым
на любой платформе и при любом моменте циклической сборки мусора, поэтому
краснеют оба разрешённых критерием приёма — и `sqlite3.ProgrammingError`
на обращении, и смерть слабой ссылки. Служебные файлы WAL в проверке не
участвуют вовсе, поэтому исход не зависит от того, удаляет ли их SQLite.

Красен до реализации: сегодня в теле теста проверки закрытости нет, и под
этой мутацией `test_command_writes_nothing` остаётся зелёным (на macOS
списки файлов «до» и «после» совпадают) — падения, которое планка
требует, не происходит.
"""
import contextlib
import unittest
from unittest import mock

from orchestrator import store

import _target


def _no_close(self):
    """Подмена `_AutoClosingConnection.close`: соединение не закрывается.

    Возврат к `del conn` отличается от явного закрытия ровно этим —
    вызванного `close()` не происходит ни в теле теста, ни в `__del__`
    до неопределённого момента сборки мусора.
    """
    return None


class Ac3MutationSensitivityTest(unittest.TestCase):
    """AC-3: краснота проверки закрытости на возврате к `del conn`."""

    @contextlib.contextmanager
    def _close_neutralised(self):
        """Мутация: `close()` — пустышка, объекты соединений удерживаются.

        Отдаёт список удержанных соединений, чтобы прогон, не позвавший
        `store.db()` ни разу, был виден как явная ошибка мутации, а не как
        тихо зелёный тест.
        """
        kept: list = []
        real_db = store.db

        def fake_db(*args, **kwargs):
            conn = real_db(*args, **kwargs)
            kept.append(conn)  # сильная ссылка: объект соединения жив
            return conn

        try:
            with mock.patch.object(store, "db", fake_db), \
                 mock.patch.object(store._AutoClosingConnection, "close",
                                   _no_close):
                yield kept
        finally:
            for conn in kept:  # уборка: настоящий close() уже вернулся
                with contextlib.suppress(Exception):
                    conn.close()

    def _failure_line(self, result: unittest.TestResult) -> int:
        """Строка `tests/test_models.py` ВНУТРИ тела теста, на которой
        случилось падение мутированного прогона."""
        reports = _target.problem_reports(result)
        self.assertTrue(
            reports,
            f"{_target.TARGET_NAME}: под мутацией «соединение не закрыто и "
            f"живо» тест остался зелёным — прямой проверки закрытости в нём "
            f"нет (AC-2/AC-3), возврат к `del conn` он не поймает")
        start, end = _target.method_line_range()
        text = reports[0]
        inside = _target.lines_inside_method(text)
        self.assertTrue(
            inside,
            f"{_target.TARGET_NAME}: падение под мутацией пришло не на строки "
            f"тела теста ({start}-{end}) — планка ждала падения проверки "
            f"закрытости, а получила вот что:\n{text}")
        return inside[-1]

    def test_ac3_unclosed_and_alive_connection_reddens_the_test(self):
        """Тест зелёный без мутации и падает с мутацией — причём падает
        РАНЬШЕ снимка списка файлов, то есть именно на проверке закрытости,
        а не на разнице списков файлов «до»/«после».

        Ловит мутацию: проверка закрытости написана так, что зелена и при
        живом открытом соединении — например утверждение о другом объекте,
        о результате `close()` или о смерти слабой ссылки, которую тест
        сам же и уронил до проверки. Такая проверка проходит и после
        возврата к `del conn`, то есть планки мутации из требования 2 в
        тесте фактически нет.
        """
        snapshot = _target.first_snapshot_line()
        self.assertIsNotNone(
            snapshot,
            f"{_target.TARGET_NAME}: в теле нет ни одного вызова "
            f"`iterdir()` — отделить падение проверки закрытости от падения "
            f"сверки списка файлов нечем (AC-3)")

        clean = _target.run_target()
        self.assertTrue(
            clean.wasSuccessful(),
            f"{_target.TARGET_NAME}: тест красный БЕЗ всякой мутации — "
            f"проверка закрытости обязана быть выполнимой на исправленном "
            f"коде:\n{clean.failures}{clean.errors}")

        with self._close_neutralised() as kept:
            mutated = _target.run_target()
        self.assertTrue(
            kept,
            f"{_target.TARGET_NAME}: под мутацией не было ни одного вызова "
            f"`store.db()` — затравочное соединение заводится в обход "
            f"`store.db()`, и мутация «возврат к `del conn`» к тесту не "
            f"применима; проверка AC-3 в таком виде ничего не значит")
        self.assertFalse(
            mutated.wasSuccessful(),
            f"{_target.TARGET_NAME}: мутация «соединение не закрыто и живо» "
            f"тест не уронила — значит возврат к `del conn` он тоже не "
            f"поймает (AC-3)")

        line = self._failure_line(mutated)
        self.assertLess(
            line, _target.absolute(snapshot),
            f"{_target.TARGET_NAME}: под мутацией тест упал на строке {line} "
            f"— это не раньше первого `iterdir()` (строка "
            f"{_target.absolute(snapshot)}), то есть краснеет сверка файлов, "
            f"а не прямая проверка закрытости; на macOS такая краснота не "
            f"воспроизводится (AC-3 требует одинакового поведения на обеих "
            f"платформах)")
