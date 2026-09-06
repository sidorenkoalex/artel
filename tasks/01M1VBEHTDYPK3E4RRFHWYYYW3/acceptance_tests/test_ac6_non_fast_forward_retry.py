"""Приёмочный тест AC-6 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3: push,
отклонённый как non-fast-forward, повторяется с новым fetch — до 3 раз.

Красен до реализации: `orchestrator.notes` ещё не существует — импорт
падает `ModuleNotFoundError`.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import (NoteSandbox, PushSpy, SECTION_HEADINGS,  # noqa: E402
                      _inject_foreign_commit, row_cells, section_rows)


class NonFastForwardRetryTest(NoteSandbox):

    def test_ac6_single_conflict_retries_once_with_fresh_fetch_and_succeeds(self):
        """Один посторонний коммит, ушедший в origin МЕЖДУ fetch и первым
        push команды `note`, отклоняет первую попытку non-fast-forward;
        `note` перечитывает origin заново и успешно проводит СВОЮ строку
        вторым push — оба коммита (посторонний и от `note`) остаются в
        origin, посторонний не затёрт.

        Ловит мутацию: реализация не перечитывает origin перед повтором
        (шлёт тот же локальный коммит второй раз) — второй push отклоняется
        тем же non-fast-forward, попытка команды завершится либо
        удержанием коммита (найдётся в `notes.pending_notes()`, а не в
        origin), либо `push_calls` окажется больше 2 — оба исхода красят
        тест ниже.
        """
        spy = PushSpy(on_before_push=lambda n: (
            _inject_foreign_commit(self.origin, "EXTERNAL-once.md")
            if n == 1 else None))

        with mock.patch("subprocess.run", new=spy):
            notes.cmd_note(["копилка", "--text",
                            "9 | 09.09 | своя строка | orchestrator/mine.py"])

        self.assertEqual(spy.push_calls, 2,
                         "ожидалась ровно одна повторная попытка push")
        text = self.origin_backlog()
        rows = section_rows(text, SECTION_HEADINGS["копилка"])
        self.assertEqual(row_cells(rows[2]),
                         ["9", "09.09", "своя строка", "orchestrator/mine.py"])
        outside_diff = self.origin_run(
            "log", "--all", "--format=%s").stdout
        self.assertIn("внешний коммит EXTERNAL-once.md", outside_diff,
                      "посторонний коммит должен остаться в истории origin")

    def test_ac6_persistent_conflict_stops_after_three_push_attempts(self):
        """Постоянный конфликт (посторонний коммит перед КАЖДОЙ попыткой)
        не даёт команде повторять push бесконечно — ровно 3 попытки push
        за вызов, не больше.

        Ловит мутацию: отсутствие потолка повторов (цикл до первого
        успеха) — `push_calls` вырос бы далеко за 3 на постоянном
        конфликте.
        """
        spy = PushSpy(on_before_push=lambda n: _inject_foreign_commit(
            self.origin, f"EXTERNAL-{n}.md"))

        with mock.patch("subprocess.run", new=spy):
            try:
                notes.cmd_note(["копилка", "--text",
                                "9 | 09.09 | не пройдёт | orchestrator/never.py"])
            except SystemExit:
                pass

        self.assertEqual(spy.push_calls, 3)


if __name__ == "__main__":
    unittest.main()
