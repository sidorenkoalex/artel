"""Приёмочный тест AC-4 задачи 01M290Q1VK21V0X2VKC7WS6K1K: `--drop`
использует тот же цикл fetch/правка/push с повторами non-fast-forward и
удержанием заметки при отказе сети (`_hold_pending`), что и остальные
виды `note`; удержанная операция `drop` успешно допушивается `--flush`.

Красен до реализации: `orchestrator.notes.cmd_note` ещё не понимает флаг
`--drop` — вызов падает до попытки push, поведение удержания проверить
нечем.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import doctor, notes  # noqa: E402
from _sandbox import (NoteSandbox, PushSpy, SECTION_HEADINGS,  # noqa: E402
                      _inject_foreign_commit, section_rows)


class DropNetworkFailureHoldsTest(NoteSandbox):

    def test_ac4_network_failure_holds_drop_and_doctor_warns(self):
        """`origin` недоступен — `--drop` не роняет процесс необработанным
        исключением: запрос остаётся удержанным (`notes.pending_notes()` —
        одна запись), origin не продвигается (строка «КЛЮЧСНЯТЬ» всё ещё
        на месте), `doctor.check_pending_notes()` предупреждает.

        Ловит мутацию: сетевой отказ push у `--drop` молча теряет запрос
        (`pending_notes()` остаётся пустым) вместо удержания — тест
        красен на `assertEqual(len(pending), 1)`.
        """
        head_before = self.origin_head()
        self.break_origin_remote()

        try:
            notes.cmd_note(["--drop", "КЛЮЧСНЯТЬ"])
        except SystemExit:
            pass

        self.assertEqual(self.origin_head(), head_before)
        self.assertIn("КЛЮЧСНЯТЬ", self.origin_backlog())
        pending = notes.pending_notes()
        self.assertEqual(len(pending), 1, pending)

        check = doctor.check_pending_notes()
        self.assertEqual(check.status, "warn", check)


class DropNonFastForwardExhaustionHoldsTest(NoteSandbox):

    def test_ac4_exhausted_retries_hold_drop_and_doctor_warns(self):
        """Исчерпание повторов non-fast-forward (постоянный посторонний
        коммит перед каждой попыткой push) для `--drop` — тот же исход,
        что и сетевой отказ: запрос удерживается, `doctor` предупреждает.

        Ловит мутацию: после исчерпания повторов `--drop` отбрасывает
        несохранённый запрос (`pending_notes()` пуст).
        """
        spy = PushSpy(on_before_push=lambda n: _inject_foreign_commit(
            self.origin, f"EXTERNAL-{n}.md"))

        with mock.patch("subprocess.run", new=spy):
            try:
                notes.cmd_note(["--drop", "КЛЮЧСНЯТЬ"])
            except SystemExit:
                pass

        pending = notes.pending_notes()
        self.assertEqual(len(pending), 1, pending)
        check = doctor.check_pending_notes()
        self.assertEqual(check.status, "warn", check)


class DropFlushTest(NoteSandbox):

    def test_ac4_flush_pushes_held_drop_and_doctor_stops_warning(self):
        """`note --flush` с восстановленным `origin` допушивает ранее
        удержанный `--drop`: строка «КЛЮЧСНЯТЬ» исчезает из origin,
        `pending_notes()` пустеет, `doctor.check_pending_notes()`
        возвращается к «ok».

        Ловит мутацию: `--flush` допушивает только `insert`/`append`,
        игнорируя удержанные заметки вида `drop` — строка «КЛЮЧСНЯТЬ»
        осталась бы в origin после `--flush`.
        """
        self.break_origin_remote()
        try:
            notes.cmd_note(["--drop", "КЛЮЧСНЯТЬ"])
        except SystemExit:
            pass
        self.assertEqual(len(notes.pending_notes()), 1,
                         "предусловие: должна остаться ровно одна удержанная заметка")
        self.restore_origin_remote()

        notes.cmd_note(["--flush"])

        text = self.origin_backlog()
        self.assertNotIn("КЛЮЧСНЯТЬ", text)
        self.assertEqual(notes.pending_notes(), [])
        self.assertEqual(doctor.check_pending_notes().status, "ok")
        # Соседние строки раздела не задеты допушенным снятием.
        rows = section_rows(text, SECTION_HEADINGS["копилка"])
        self.assertTrue(any("КЛЮЧСОСТОЯНИЕ" in row for row in rows))


if __name__ == "__main__":
    unittest.main()
