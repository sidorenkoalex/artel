"""Приёмочный тест AC-7 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3: сетевой отказ
push (или исчерпание повторов non-fast-forward) — коммит удерживается
(`.artel/notes-pending/` либо ветка `notes-pending`), не теряется;
`doctor` выдаёт предупреждение о удержанных заметках.

Хранилище удержанных коммитов SPEC оставляет на выбор реализации
(«.artel/notes-pending/ либо локальная ветка notes-pending») — тест
поэтому не заглядывает внутрь конкретного представления, а спрашивает
модуль о своём же наблюдаемом состоянии через `notes.pending_notes()`
(список удержанных заметок) — единственная точка, которую обязана
реализовать команда `note` независимо от выбранного хранилища.

Красен до реализации: `orchestrator.notes` ещё не существует — импорт
падает `ModuleNotFoundError`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import doctor, notes  # noqa: E402
from _sandbox import NoteSandbox, PushSpy, _inject_foreign_commit  # noqa: E402


class NetworkFailureHoldsTest(NoteSandbox):

    def test_ac7_network_failure_holds_commit_and_doctor_warns(self):
        """`origin` недоступен (эквивалент сетевого отказа) — команда не
        падает необработанным исключением, коммит остаётся удержанным
        (`notes.pending_notes()` — одна запись), origin не получает ни
        новой строки, ни новой головы, и `doctor.check_pending_notes()`
        предупреждает об этом.

        Ловит мутацию: сетевой отказ push молча теряет коммит (`pending_
        notes()` остаётся пустым) — тест красен на `assertEqual(len(...), 1)`.
        """
        head_before = self.origin_head()
        self.break_origin_remote()

        try:
            notes.cmd_note(["копилка", "--text",
                            "9 | 09.09 | потеряется? | orchestrator/net.py"])
        except SystemExit:
            pass

        self.assertEqual(self.origin_head(), head_before)
        pending = notes.pending_notes()
        self.assertEqual(len(pending), 1, pending)

        check = doctor.check_pending_notes()
        self.assertEqual(check.status, "warn", check)


class NonFastForwardExhaustionHoldsTest(NoteSandbox):

    def test_ac7_exhausted_retries_hold_commit_and_doctor_warns(self):
        """Исчерпание повторов non-fast-forward (постоянный посторонний
        коммит перед каждой попыткой push, AC-6) — тот же исход, что и
        сетевой отказ: коммит удерживается, `doctor` предупреждает.

        Ловит мутацию: после исчерпания повторов реализация просто
        отбрасывает несохранённую правку (`pending_notes()` пуст).
        """
        spy = PushSpy(on_before_push=lambda n: _inject_foreign_commit(
            self.origin, f"EXTERNAL-{n}.md"))

        with mock.patch("subprocess.run", new=spy):
            try:
                notes.cmd_note(["копилка", "--text",
                                "9 | 09.09 | не пройдёт | orchestrator/never.py"])
            except SystemExit:
                pass

        pending = notes.pending_notes()
        self.assertEqual(len(pending), 1, pending)
        check = doctor.check_pending_notes()
        self.assertEqual(check.status, "warn", check)


if __name__ == "__main__":
    unittest.main()
