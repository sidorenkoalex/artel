"""Приёмочные тесты T063 — «Суть» RETRO берёт полное первое предложение,
а не первую строку/запятую (SPEC.md AC-1, AC-2, AC-3).

Песочница — тот же приём, что `tests/test_retro.py`: `config.ROOT/DB/TASKS`
подменены на временный каталог, БД создаётся с нуля, `orchestrator.retro`
вызывается напрямую (без FSM и без git) — здесь важны только чистые
функции извлечения «Сути», не сквозной путь merge_gate/kill.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import cleanup, config, retro, store  # noqa: E402

TASK = "T900"

# Предложение переносится через несколько строк ДО точки и содержит запятые
# до неё — ровно случай бага из SPEC (T042: обрезка по запятой/строке, а не
# по границе предложения). Второе предложение обязано остаться отброшенным.
SPEC_TEXT = """---
task: T900
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: задача для теста T063

## Контекст

Первая часть предложения, вторая часть предложения,
третья часть предложения на новой строке — тут стоит точка.
Второе предложение контекста не должно попасть в Суть.

## Требования

1. Требование.

## Критерии приёмки

AC-1. Критерий.

## Не входит

- Ничего.
"""

# Тот же приём для killed-фолбэка (AC-3): фолбэк обязан остаться прежним
# поведением build_killed — целой первой строкой «как есть», БЕЗ обрезки по
# предложению (это единственное отличие от done-пути AC-1). Одна строка с
# двумя предложениями — маркер того, что фолбэк не режет по точке.
FALLBACK_SPEC_TEXT = """---
task: T900
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: задача для теста T063 (фолбэк)

## Контекст

Первое предложение фолбэка. Второе предложение фолбэка тоже на той же строке.
Вторая строка контекста — не должна попасть в дайджест.

## Требования

1. Требование.

## Критерии приёмки

AC-1. Критерий.

## Не входит

- Ничего.
"""

TZ_TEXT = """Первая часть ТЗ, вторая часть ТЗ,
третья часть ТЗ на новой строке — и тут точка ТЗ.
Второе предложение ТЗ не должно попасть в Суть.
"""


class RetroGistSentenceTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "Задача для теста",
                          "merge_gate", "task/t900-x", config.DEFAULT_TARGET,
                          50.0)

    def write_spec(self, text) -> None:
        tdir = config.TASKS / TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(text, encoding="utf-8")

    def journal_tz(self, tz_text) -> None:
        store.journal(self.conn, TASK, "operator",
                      cleanup.KILL_TZ_JOURNAL_ACTION, tz_text)

    def test_ac1_done_gist_takes_full_first_sentence_across_lines_and_commas(self):
        self.write_spec(SPEC_TEXT)

        text = retro.build_done(self.conn, TASK, "deadbeef" * 5)

        self.assertIn(
            "вторая часть предложения", text,
            "предложение обрезано по первой запятой/строке, а не по точке "
            "(требование 1)")
        self.assertIn(
            "третья часть предложения на новой строке", text,
            "первое предложение, перенесённое через несколько строк, "
            "должно попасть в Суть целиком (требование 1)")
        self.assertNotIn(
            "Второе предложение контекста", text,
            "в Суть попало содержимое ПОСЛЕ точки — обрезка должна быть "
            "по границе первого предложения (требование 1)")

    def test_ac2_killed_gist_from_journaled_tz_takes_full_first_sentence(self):
        self.journal_tz(TZ_TEXT)

        text = retro.build_killed(self.conn, TASK)

        self.assertIn(
            "вторая часть ТЗ", text,
            "первое предложение ТЗ обрезано по первой запятой/строке "
            "(требование 2)")
        self.assertIn(
            "третья часть ТЗ на новой строке", text,
            "первое предложение ТЗ, перенесённое через несколько строк, "
            "должно попасть в Суть целиком (требование 2)")
        self.assertNotIn(
            "Второе предложение ТЗ", text,
            "в Суть попало содержимое ПОСЛЕ точки ТЗ — обрезка должна быть "
            "по границе первого предложения (требование 2)")

    def test_ac3_killed_gist_without_journaled_tz_uses_unchanged_fallback(self):
        self.write_spec(FALLBACK_SPEC_TEXT)

        text = retro.build_killed(self.conn, TASK)

        self.assertIn(
            "Первое предложение фолбэка.", text,
            "фолбэк без ТЗ в журнале обязан по-прежнему брать текст из "
            "«Контекста» SPEC (требование 3)")
        self.assertIn(
            "Второе предложение фолбэка тоже на той же строке", text,
            "фолбэк без ТЗ в журнале не должен резать по границе "
            "предложения — это прежнее (неизменённое) поведение "
            "build_killed, а не новая логика AC-1/AC-2 (требование 3)")
        self.assertNotIn(
            "Вторая строка контекста", text,
            "фолбэк по-прежнему берёт только первую непустую строку "
            "«Контекста», не весь раздел (прежнее поведение build_killed)")


if __name__ == "__main__":
    unittest.main()
