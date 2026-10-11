"""Приёмочные тесты T043 — RETRO на переходе `merge_gate` -> `done`
(SPEC.md, AC-1, AC-4, AC-6).

Песочница — `retro_sandbox.RetroSandboxTest` (см. докстрока модуля):
`FsmTest` (БД/артефакты во временном каталоге, git подменён) плюс второй
синтетический `config.ROOT` для `docs/retro/`.

AC-1 проверяет НАБОР ФАКТОВ из требования 5, не конкретную вёрстку строк:
разработчик волен выбрать формулировки, тест закрепляет данные (id,
название из БД, sha мержа в форме требования 8, обоих акторов шагов,
итоговую стоимость, счётчики ревью/приёмки, дословную первую строку
«Контекста» и отсутствие второй, число тестов/manual/skip). Проверка
чисел — `field_lines` (значение и одно из ключевых слов на одной строке,
с границей числа): формулировку не диктует, но и не позволяет тесту
пройти на случайном совпадении цифры в другом контексте (sha, токены).

AC-4 — независимость от общего состояния стенда: два полностью отдельных
прогона песочницы (второй `setUp()` перепатчивает `config.DB/TASKS/ROOT`
на новые временные каталоги поверх первых, тем же приёмом, что
`KillKeepsMainIntactTest.fresh_repo` в tests/test_invariants.py) с
одинаковыми входными данными обязаны дать байт-в-байт одинаковый файл;
`store.now` зафиксирован (см. retro_sandbox), иначе разница во времени
двух реальных прогонов сама по себе нарушила бы «тот же файл байт в
байт», не будучи дефектом реализации.
"""
# AC-6: manual — критерий уже покрыт `.github/workflows/ci.yml` (джоб
# `python`, `unittest discover -s tests -v` на каждый пуш в чистом
# раннере); повтор прогона всего набора подпроцессом внутри
# acceptance_tests ловил бы экологические условия машины разработчика, а
# не дефект этой задачи (прецедент tasks/T042 AC-5, tasks/T036 AC-4).

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from retro_sandbox import (CONTEXT_LINE, MERGE_SHA,  # noqa: E402
                           RetroSandboxTest)


def field_lines(text: str, value, keywords) -> list[str]:
    """Строки текста, где встречается `value` как отдельное число (не
    подстрока другого числа) вместе хотя бы с одним из `keywords`."""
    pat = re.compile(rf"(?<!\d){re.escape(str(value))}(?!\d)")
    return [line for line in text.splitlines()
           if pat.search(line) and any(k.lower() in line.lower()
                                       for k in keywords)]


class Ac1DoneRetroTest(RetroSandboxTest):
    """AC-1: merge_gate -> done оставляет docs/retro/<id>.md <=30 строк с
    полями требования 5, коммит которого уходит тем же push, что и merge."""

    def setUp(self):
        super().setUp()
        self.write_context_spec()
        self.set_state("merge_gate", review_iters=2, accept_rejects=1,
                       spent_usd=3.5)
        self.add_finished_step("developer", 1.0, 100)
        self.add_finished_step("reviewer", 2.5, 200)
        self.add_escalation("нужна помощь Оператора: неясен объём")
        self.write_acceptance_tests_fixture()

    def test_ac1_retro_file_has_required_fields_within_30_lines(self):
        self.approve()

        self.assertEqual(self.state(), "done")
        subcommands = self.git_subcommands()
        self.assertIn("merge", subcommands)
        self.assertIn("push", subcommands)
        self.assertLess(subcommands.index("merge"), subcommands.index("push"),
                        "коммит RETRO должен уйти тем же push, что и merge")

        text = self.retro_text()
        lines = text.splitlines()
        self.assertLessEqual(
            len(lines), 30,
            "RETRO задачи, дошедшей до done, не должен превышать 30 строк "
            "(требование 4)")

        title = self.task_row()["title"]
        self.assertIn(self.TASK, text, "нет id задачи")
        self.assertIn(title, text, "нет названия задачи (tasks.title)")

        self.assertIn(
            f"{MERGE_SHA}:tasks/{self.TASK}/", text,
            "адрес артефактов не в форме <merge-sha>:tasks/<id>/ "
            "(требование 8)")

        self.assertIn(CONTEXT_LINE, text,
                      "нет дословной первой строки раздела «Контекст»")
        self.assertNotIn(
            "Вторая строка контекста", text,
            "извлечение первой строки «Контекста» должно быть точечным, "
            "не пересказом/копией всего раздела (требование 5)")

        self.assertIn("developer", text, "нет актора developer в разбивке по шагам")
        self.assertIn("reviewer", text, "нет актора reviewer в разбивке по шагам")

        self.assertTrue(
            field_lines(text, "3.5", ("стоимост", "$", "итог"))
            or field_lines(text, "3.50", ("стоимост", "$", "итог")),
            "нет итоговой стоимости (3.5 = 1.0 + 2.5, tasks.spent_usd)")

        self.assertTrue(
            field_lines(text, 2, ("ревью", "итерац")),
            "нет числа итераций ревью (review_iters=2)")
        self.assertTrue(
            field_lines(text, 1, ("отказ",)),
            "нет числа отказов приёмки (accept_rejects=1)")

        self.assertIn(
            "нужна помощь Оператора: неясен объём", text,
            "нет дословной причины эскалации (state -> escalated, требование 5)")

        self.assertTrue(
            field_lines(text, 2, ("тест",)),
            "нет числа приёмочных тестов (2 test_ac* в фикстуре)")
        self.assertTrue(
            field_lines(text, 1, ("manual",))
            or field_lines(text, 1, ("ручн",)),
            "нет числа пометок manual (1 в фикстуре)")
        self.assertTrue(
            field_lines(text, 1, ("skip",))
            or field_lines(text, 1, ("пропущ",)),
            "нет числа пометок skip (1 в фикстуре)")


class Ac4DeterministicGenerationTest(RetroSandboxTest):
    """AC-4: повторный прогон по тем же входным данным даёт тот же файл
    байт в байт."""

    def _populate(self) -> None:
        self.write_context_spec()
        self.set_state("merge_gate", review_iters=1, accept_rejects=0,
                       spent_usd=1.25)
        self.add_finished_step("developer", 1.25, 500)
        self.add_escalation("вопрос про объём (детерминизм)")
        self.write_acceptance_tests_fixture()

    def test_ac4_two_independent_runs_produce_identical_bytes(self):
        self._populate()
        self.approve()
        first = self.retro_text().encode("utf-8")

        # Второй, полностью независимый прогон: новые временные
        # config.DB/TASKS/LOGS/ROOT поверх первых (setUp() второй раз,
        # тот же приём, что fresh_repo() в KillKeepsMainIntactTest).
        self.setUp()
        self._populate()
        self.approve()
        second = self.retro_text().encode("utf-8")

        self.assertEqual(
            first, second,
            "повторная генерация по тем же входным данным (журнал steps, "
            "фронтматтеры) не дала байт-в-байт идентичный файл")


if __name__ == "__main__":
    import unittest
    unittest.main()
