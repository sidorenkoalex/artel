"""Юнит-тесты генерации содержимого RETRO (orchestrator/retro.py, SPEC T043).

Сквозной путь (запись файла, git add/commit, некритичность провала) уже
покрыт приёмочными тестами `tasks/T043/acceptance_tests/` и
`tests/test_fsm_retro.py` — здесь только чистые функции генератора,
без git и без FSM-песочницы.
"""
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import cleanup, config, retro, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

SENTENCE_SPEC_TEXT = """---
task: T900
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: задача для теста

## Контекст

Первая часть, вторая часть,
третья часть на новой строке — тут точка.
Второе предложение не должно попасть в Суть.

## Требования

1. Требование.

## Критерии приёмки

AC-1. Критерий.

## Не входит

- Ничего.
"""

TOKEN_DOT_SPEC_TEXT = """---
task: T900
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: задача для теста

## Контекст

`docs/codebase-map.md` устарел после 27.08, регенерация нужна в тот же
день. Второе предложение не должно попасть в Суть.

## Требования

1. Требование.

## Критерии приёмки

AC-1. Критерий.

## Не входит

- Ничего.
"""

SPEC_TEXT = """---
task: T900
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: задача для теста

## Контекст

Первая строка контекста.
Вторая строка контекста — не должна попасть в дайджест.

## Требования

1. Требование.

## Критерии приёмки

AC-1. Критерий.

## Не входит

- Ничего.
"""

ACCEPTANCE_FIXTURE = ('''"""Фикстура."""
# @AC-2: manual — причина.
import unittest


class T(unittest.TestCase):
    def test_@ac1_one(self):
        pass
''').replace("@ac", "ac").replace("@AC", "AC")


class RetroGenerationTest(TmpRootTest):
    """Песочница: sandbox.TmpRootTest полным набором путей (SPEC T061, AC-3)."""

    TASK = "T900"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Задача для теста",
                          "merge_gate", "task/t900-x", config.DEFAULT_TARGET,
                          50.0)

    def write_spec(self, text=SPEC_TEXT) -> None:
        tdir = config.TASKS / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(text, encoding="utf-8")

    def write_acceptance_tests(self) -> None:
        adir = config.TASKS / self.TASK / "acceptance_tests"
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "test_fixture.py").write_text(ACCEPTANCE_FIXTURE,
                                              encoding="utf-8")

    def add_step(self, actor, action, detail="") -> None:
        store.journal(self.conn, self.TASK, actor, action, detail)

    def test_build_done_has_merge_sha_address_and_first_context_line_only(self):
        self.write_spec()
        store.update_task(self.conn, self.TASK, spent_usd=1.5,
                          review_iters=1, accept_rejects=0)
        self.add_step("developer", "agent run finished",
                      "rc=0, попытка 1/1, стоимость $1.5000, токенов 42")

        text = retro.build_done(self.conn, self.TASK, "deadbeef" * 5)

        self.assertIn("deadbeef" * 5 + f":tasks/{self.TASK}/", text)
        self.assertIn("Первая строка контекста.", text)
        self.assertNotIn("Вторая строка контекста", text)
        self.assertIn("developer", text)
        self.assertLessEqual(len(text.splitlines()), 30)

    def test_build_done_gist_takes_full_first_sentence_not_line_or_comma(self):
        """SPEC T063, требование 1 — предложение, перенесённое через
        несколько строк и содержащее запятые до точки, должно попасть в
        Суть целиком, обрезка идёт по точке."""
        self.write_spec(SENTENCE_SPEC_TEXT)

        text = retro.build_done(self.conn, self.TASK, "deadbeef" * 5)

        self.assertIn("Первая часть, вторая часть, "
                      "третья часть на новой строке — тут точка.", text)
        self.assertNotIn("Второе предложение", text)

    def test_build_done_gist_does_not_cut_at_dot_inside_path_or_date(self):
        """REVIEW T063 итерации 1, blocker: мотивирующий пример SPEC
        (путь `docs/codebase-map.md` и дата `27.08` до реальной точки
        конца предложения) проходит через build_done без обрезки внутри
        токена."""
        self.write_spec(TOKEN_DOT_SPEC_TEXT)

        text = retro.build_done(self.conn, self.TASK, "deadbeef" * 5)

        self.assertIn(
            "`docs/codebase-map.md` устарел после 27.08, регенерация "
            "нужна в тот же день.", text)
        self.assertNotIn("Второе предложение", text)

    def test_build_killed_gist_from_journaled_tz_takes_full_first_sentence(self):
        """SPEC T063, требование 2 — то же правило обрезки по точке для
        ТЗ, сохранённого в журнал `kill` (SPEC T048)."""
        self.add_step("operator", "state -> killed", "kill switch")
        self.add_step("operator", cleanup.KILL_TZ_JOURNAL_ACTION,
                      "Первая часть ТЗ, вторая часть ТЗ,\n"
                      "третья часть ТЗ на новой строке — тут точка ТЗ.\n"
                      "Второе предложение ТЗ не должно попасть в Суть.\n")

        text = retro.build_killed(self.conn, self.TASK)

        self.assertIn("Первая часть ТЗ, вторая часть ТЗ, "
                      "третья часть ТЗ на новой строке — тут точка ТЗ.", text)
        self.assertNotIn("Второе предложение ТЗ", text)

    def test_build_done_is_deterministic(self):
        self.write_spec()
        self.write_acceptance_tests()
        store.update_task(self.conn, self.TASK, spent_usd=2.0)
        self.add_step("developer", "agent run finished",
                      "rc=0, попытка 1/1, стоимость $2.0000, токенов 10")
        self.add_step("fsm", "state -> escalated", "причина A")

        first = retro.build_done(self.conn, self.TASK, "cafe" * 10)
        second = retro.build_done(self.conn, self.TASK, "cafe" * 10)

        self.assertEqual(first, second)

    def test_build_done_aggregates_cost_per_actor_across_events(self):
        self.add_step("developer", "agent run finished",
                      "rc=1, попытка 1/2, стоимость $1.0000, токенов 10")
        self.add_step("developer", "agent run finished",
                      "rc=0, попытка 2/2, стоимость $0.5000, токенов 5")

        text = retro.build_done(self.conn, self.TASK, "aaaa" * 10)

        self.assertIn("developer: $1.50, 15 токенов", text)

    def test_build_done_escalations_show_count_and_last_verbatim(self):
        self.add_step("fsm", "state -> escalated", "первая причина")
        self.add_step("operator", "state -> in_dev", "продолжаем")
        self.add_step("fsm", "state -> escalated", "последняя причина")

        text = retro.build_done(self.conn, self.TASK, "bbbb" * 10)

        self.assertIn("последняя причина", text)
        self.assertNotIn("первая причина", text)
        self.assertIn("2", text)

    def test_build_done_without_escalations_says_none(self):
        text = retro.build_done(self.conn, self.TASK, "cccc" * 10)

        self.assertIn("Эскалации: нет", text)

    def test_build_done_truncates_multiline_escalation_to_first_line(self):
        """Самый частый путь эскалации в системе — исчерпание попыток
        агента (`orchestrator/runner.py`): `detail` тянет хвост лога
        (`config.LOG_TAIL_LINES` строк, склеенных через `\\n`) одной
        f-строкой. Требование 4 разрешает превышать 30 строк только для
        killed — для done лимит обязан держаться независимо от того,
        сколько строк в тексте причины последней эскалации."""
        log_tail = "\n".join(f"строка лога {i}" for i in range(15))
        self.add_step("fsm", "state -> escalated",
                      f"исчерпаны попытки агента\n{log_tail}")

        text = retro.build_done(self.conn, self.TASK, "dddd" * 10)

        self.assertIn("исчерпаны попытки агента", text)
        self.assertNotIn("строка лога", text)
        self.assertLessEqual(len(text.splitlines()), 30)

    def test_build_killed_quotes_multiline_escalation_verbatim(self):
        """killed — исключение по объёму цитаты (требование 4/7) явно
        разрешено: полный многострочный `detail` должен попасть в файл
        дословно, не только первая строка."""
        log_tail = "\n".join(f"строка лога {i}" for i in range(5))
        self.add_step("operator", "state -> killed", "kill switch")
        self.add_step("fsm", "state -> escalated",
                      f"исчерпаны попытки агента\n{log_tail}")

        text = retro.build_killed(self.conn, self.TASK)

        self.assertIn("исчерпаны попытки агента", text)
        self.assertIn("строка лога 4", text)

    def test_build_killed_has_no_artifacts_and_no_address_form(self):
        self.add_step("operator", "state -> killed", "kill switch")

        text = retro.build_killed(self.conn, self.TASK)

        self.assertIn(retro.NO_ARTIFACTS_NOTE, text)
        self.assertIn("kill switch", text)
        self.assertNotRegex(text, r"[0-9a-f]{40}:tasks/")

    def test_build_killed_survives_missing_task_dir(self):
        """`tasks/<id>/` уже убран `cleanup` — генератор не падает
        (SPEC, требование 6: БД остаётся источником истины)."""
        self.add_step("operator", "state -> killed", "kill switch")
        self.assertFalse((config.TASKS / self.TASK).exists())

        text = retro.build_killed(self.conn, self.TASK)

        self.assertIn(self.TASK, text)
        self.assertIn("0 тест(ов)", text)

    def test_build_killed_without_kill_step_has_fallback_reason(self):
        text = retro.build_killed(self.conn, self.TASK)

        self.assertIn("причина не найдена в журнале", text)

    def test_build_done_shows_the_upper_estimate_separately_from_the_total(self):
        """SPEC 01M1NWCM3TDY0YABEKE8DYQA1C, требование 7 — юнит-угол на
        `build_done`, дополняющий приёмочный
        `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/
        test_ac7_retro_shows_estimate_separately.py`."""
        store.update_task(self.conn, self.TASK, spent_usd=3.0,
                          spent_estimate_usd=7.0)

        text = retro.build_done(self.conn, self.TASK, "cafe" * 10)

        self.assertIn("Стоимость итого: $3.00", text)
        self.assertIn("$7.00", text)

    def test_build_killed_without_an_estimate_says_nothing_about_it(self):
        self.add_step("operator", "state -> killed", "kill switch")
        store.update_task(self.conn, self.TASK, spent_usd=1.0,
                          spent_estimate_usd=0.0)

        text = retro.build_killed(self.conn, self.TASK)

        self.assertNotIn("оцен", text.lower())


class FirstSentenceTest(unittest.TestCase):
    """`_first_sentence` — обрезка по точке, не по строке/запятой
    (SPEC T063, требования 1, 2)."""

    def test_cuts_at_first_dot_across_lines_and_commas(self):
        text = "Часть один, часть два,\nчасть три на новой строке.\nХвост."

        self.assertEqual(retro._first_sentence(text),
                         "Часть один, часть два, часть три на новой строке.")

    def test_no_dot_returns_whole_collapsed_text(self):
        text = "Без точки\nна двух строках"

        self.assertEqual(retro._first_sentence(text),
                         "Без точки на двух строках")

    def test_empty_text_returns_empty_string(self):
        self.assertEqual(retro._first_sentence(""), "")

    def test_does_not_cut_at_dot_inside_file_path_or_date(self):
        """REVIEW T063 итерации 1, blocker: точка внутри пути/расширения
        файла или даты (без пробела после неё) — не граница предложения,
        поиск должен продолжаться до реальной точки-конца-предложения."""
        text = ("Правка тронула `orchestrator/artel.py` 27.08, но задача "
                "решена в тот же день. Второе предложение лишнее.")

        self.assertEqual(
            retro._first_sentence(text),
            "Правка тронула `orchestrator/artel.py` 27.08, но задача "
            "решена в тот же день.")

    def test_does_not_cut_at_dot_inside_abbreviation(self):
        text = ("Опишем кратко, т.е. по сути, всё сделано верно. "
                "Второе предложение лишнее.")

        self.assertEqual(
            retro._first_sentence(text),
            "Опишем кратко, т.е. по сути, всё сделано верно.")

    def test_cuts_at_trailing_dot_with_no_following_text(self):
        self.assertEqual(retro._first_sentence("Всё предложение целиком."),
                         "Всё предложение целиком.")


class CostBlockTest(unittest.TestCase):
    """`retro._cost_block` — строка оценки только при ненулевой
    `spent_estimate_usd`, отдельно от «Стоимость итого» (SPEC
    01M1NWCM3TDY0YABEKE8DYQA1C, требование 7)."""

    def test_default_estimate_omits_the_estimate_line(self):
        lines = retro._cost_block([], 3.0)

        self.assertEqual(lines[0], "Стоимость итого: $3.00")
        self.assertFalse(any("оцен" in line.lower() for line in lines))

    def test_nonzero_estimate_adds_a_distinct_line(self):
        lines = retro._cost_block([], 3.0, 7.0)

        self.assertIn("Стоимость итого: $3.00", lines)
        self.assertTrue(any("$7.00" in line for line in lines))
        self.assertNotIn("Стоимость итого: $7.00", lines)


class ParseTotalCostTest(unittest.TestCase):
    """`retro.parse_total_cost` (SPEC T049, требование 4) — извлечение
    «Стоимость итого: $X.XX» из уже сгенерированного RETRO для пересева
    программного расхода холодного старта (`budget.reseed_program_spend`)."""

    def test_finds_total_cost_on_its_own_line(self):
        text = "# RETRO: T900\n\nСтоимость итого: $12.50\n  developer: $12.50\n"

        self.assertEqual(retro.parse_total_cost(text), 12.5)

    def test_finds_integer_cost_without_fraction(self):
        text = "Стоимость итого: $7\n"

        self.assertEqual(retro.parse_total_cost(text), 7.0)

    def test_missing_line_returns_none(self):
        text = "# RETRO: T900\n\nИтог: done, sha aaaa\n"

        self.assertIsNone(retro.parse_total_cost(text))

    def test_only_matches_at_line_start_not_per_actor_line(self):
        """Требование 4: строка ИТОГО, не построчная разбивка по актёру —
        `COST_RE` («стоимость $X») уже покрывает построчный разбор, здесь
        нужна ИМЕННО заглавная сумма RETRO, привязанная к началу строки."""
        text = "  developer: стоимость $3.00, 10 токенов\n"

        self.assertIsNone(retro.parse_total_cost(text))

    def test_empty_text_returns_none(self):
        self.assertIsNone(retro.parse_total_cost(""))


if __name__ == "__main__":
    unittest.main()
