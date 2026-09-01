"""AC-8 (tasks/T092/SPEC.md): сгенерированный HTML-файл содержит число
журнальных записей актора `operator` по дням за последние 14 дней.

Фикстура ставит записи на три дня: 1 день назад и 12 дней назад (внутри
окна 14 дней — обязаны попасть в отчёт со своим числом), и 20 дней
назад (вне окна — обязана быть исключена целиком, иначе это не «за
последние 14 дней», а весь журнал). На день «1 день назад» добавлены
ещё и записи актора `autogate` — они не должны подмешиваться в счётчик
именно `operator` за этот день.

Тест не завязан на точную разметку/формат числа — ищет посчитанное
значение рядом (`_sandbox.scope`) с датой соответствующего дня в
документе. Даты вычисляются тем же смещением от текущего момента,
которым фикстура проставляет `steps.ts` (`store.now()` формат
`%Y-%m-%d %H:%M:%SZ`), чтобы дата в тесте гарантированно совпадала
с датой, записанной в БД, независимо от способа, которым отчёт сам
считает границу окна.

Красен до реализации: `orchestrator/report.py` не существует.
"""
import time
import unittest

from _sandbox import ReportSandboxTest, scope  # noqa: E402


def date_str(days_ago: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() - days_ago * 86400))


class OperatorJournalPerDayTest(ReportSandboxTest):

    NEAR_DAYS_AGO = 1
    NEAR_OPERATOR_COUNT = 13
    NEAR_NOISE_COUNT = 5  # actor=autogate тем же днём — не должен войти

    WITHIN_DAYS_AGO = 12
    WITHIN_OPERATOR_COUNT = 6

    OUTSIDE_DAYS_AGO = 20
    OUTSIDE_OPERATOR_COUNT = 8

    def setUp(self):
        super().setUp()
        self.mk_task("T001", "Задача-фикстура для журнала", "in_dev")

        for _ in range(self.NEAR_OPERATOR_COUNT):
            self.mk_step("T001", "operator", "approve",
                        days_ago=self.NEAR_DAYS_AGO)
        for _ in range(self.NEAR_NOISE_COUNT):
            self.mk_step("T001", "autogate", "state -> merge_gate",
                        days_ago=self.NEAR_DAYS_AGO)

        for _ in range(self.WITHIN_OPERATOR_COUNT):
            self.mk_step("T001", "operator", "approve",
                        days_ago=self.WITHIN_DAYS_AGO)

        for _ in range(self.OUTSIDE_OPERATOR_COUNT):
            self.mk_step("T001", "operator", "approve",
                        days_ago=self.OUTSIDE_DAYS_AGO)

        _, new_files, _, _ = self.run_report()
        self.path = new_files[0]
        self.html = self.path.read_text(encoding="utf-8")

    def test_ac8_day_within_window_is_shown(self):
        near = date_str(self.NEAR_DAYS_AGO)
        self.assertIn(near, self.html,
                     f"день {near} (внутри 14 дней) не показан в отчёте")

    def test_ac8_day_outside_window_is_excluded(self):
        outside = date_str(self.OUTSIDE_DAYS_AGO)
        self.assertNotIn(
            outside, self.html,
            f"день {outside} (20 дней назад, вне окна 14 дней) "
            "присутствует в отчёте")

    def test_ac8_count_near_the_near_day_matches_operator_only(self):
        near = date_str(self.NEAR_DAYS_AGO)
        window = scope(self.html, near)
        self.assertIsNotNone(window, f"дата {near} не найдена в отчёте")
        self.assertIn(
            str(self.NEAR_OPERATOR_COUNT), window,
            f"рядом с {near} нет числа записей operator "
            f"({self.NEAR_OPERATOR_COUNT})")

    def test_ac8_count_near_the_within_day_is_shown(self):
        within = date_str(self.WITHIN_DAYS_AGO)
        window = scope(self.html, within)
        self.assertIsNotNone(window, f"дата {within} не найдена в отчёте")
        self.assertIn(
            str(self.WITHIN_OPERATOR_COUNT), window,
            f"рядом с {within} нет числа записей operator "
            f"({self.WITHIN_OPERATOR_COUNT})")


if __name__ == "__main__":
    unittest.main()
