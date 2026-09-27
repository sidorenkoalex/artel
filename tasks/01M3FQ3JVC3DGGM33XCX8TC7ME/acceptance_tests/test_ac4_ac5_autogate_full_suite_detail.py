"""AC-4, AC-5 задачи 01M3FQ3JVC3DGGM33XCX8TC7ME — файл лога полного
набора и различимость трёх исходов `acceptance.run_full_suite` в detail
записи автогейта о непройденном полном наборе.

Красен до реализации: автогейт пишет одну и ту же фразу «автогейт:
полный набор tests/ красный» на все три исхода, файла лога полного
набора не создаёт и путь к нему в detail не называет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import (FAILED_NODEIDS, HEAD_MARKER, SUMMARY_LINE,  # noqa: E402
                       log_file_number, red_output)
from _sandbox import FullSuiteSandbox  # noqa: E402
from orchestrator import config  # noqa: E402


class FullSuiteLogFileTest(FullSuiteSandbox):

    def test_ac4_log_file_carries_whole_output_and_is_named_in_detail(self):
        """Красный прогон полного набора на автогейте оставляет в каталоге
        логов ролей файл с ПОЛНЫМ выводом прогона (включая заголовок
        сессии, который в выжимку не попадает), а detail записи журнала
        называет путь к этому файлу.

        Ловит мутацию: в файл пишется та же урезанная выжимка (срез
        `[-2000:]`, который `run_full_suite` отдаёт вызывающему), а не
        полный вывод — начало вывода прогона в файле не найдётся, и
        раскопать причину красноты по логу снова будет нечем.
        """
        before = set(self.log_files())
        self.set_red_run(red_output())

        self.autogate()

        created = [p for p in self.log_files() if p not in before]
        self.assertEqual(len(created), 1,
                         f"ожидался ровно один новый файл лога в "
                         f"{config.LOGS}, появились {created}")
        log_path = created[0]
        text = log_path.read_text(encoding="utf-8")
        self.assertIn(HEAD_MARKER, text,
                      f"{log_path.name} не несёт начала вывода прогона — в "
                      f"файл ушла выжимка, не полный вывод")
        self.assertIn(SUMMARY_LINE, text)

        detail = self.autogate_refusal_detail()
        self.assertTrue(
            log_path.name in detail or str(log_path) in detail,
            f"detail записи автогейта не называет путь к файлу лога "
            f"{log_path}: {detail!r}")

    def test_ac4_second_run_takes_the_next_number_and_keeps_the_first(self):
        """Второй прогон полного набора той же задачи пишет файл со
        следующим номером: первый файл остаётся на диске со своим
        содержимым, новый несёт вывод второго прогона.

        Ловит мутацию: имя файла лога собрано из одного `task_id` без
        нумерации (`<id>-fullsuite.log`) либо номер считается от нуля
        заново — второй прогон перезатирает первый, и сравнить два
        прогона между собой уже нечем.
        """
        before = set(self.log_files())
        first_summary = "1 failed, 305 passed in 70.01s"
        self.set_red_run(red_output(summary_line=first_summary))
        self.autogate()
        first = [p for p in self.log_files() if p not in before]
        self.assertEqual(len(first), 1, f"первый прогон: {first}")
        first_path = first[0]

        second_summary = "7 failed, 299 passed in 72.42s"
        self.set_red_run(red_output(summary_line=second_summary))
        self.autogate()

        second = [p for p in self.log_files()
                  if p not in before and p != first_path]
        self.assertEqual(len(second), 1,
                         f"второй прогон не завёл отдельный файл лога, в "
                         f"{config.LOGS} лежит {self.log_files()}")
        second_path = second[0]
        self.assertIn(first_summary, first_path.read_text(encoding="utf-8"),
                      f"{first_path.name} перезатёрт вторым прогоном")
        self.assertIn(second_summary, second_path.read_text(encoding="utf-8"))

        first_n = log_file_number(first_path.name)
        second_n = log_file_number(second_path.name)
        self.assertIsNotNone(first_n, f"в имени {first_path.name} нет номера")
        self.assertIsNotNone(second_n, f"в имени {second_path.name} нет номера")
        self.assertEqual(second_n, first_n + 1,
                         f"нумерация файлов лога не последовательна: "
                         f"{first_path.name} -> {second_path.name}")


class ThreeOutcomesDistinguishableTest(FullSuiteSandbox):

    def red_detail(self) -> str:
        self.set_red_run(red_output())
        self.autogate()
        return self.autogate_refusal_detail()

    def timeout_detail(self) -> str:
        self.set_timeout_run(red_output())
        self.autogate()
        return self.autogate_refusal_detail()

    def missing_tests_detail(self) -> str:
        self.set_green_run()
        self.drop_tests_dir()
        self.autogate()
        return self.autogate_refusal_detail()

    def test_ac5_red_run_detail_names_failed_tests_and_summary_line(self):
        """Исход «красный прогон»: detail записи «автогейт acceptance не
        пройден» несёт имена упавших тестов и итоговую строку pytest, а не
        только признак красноты.

        Ловит мутацию: разбор вывода заведён, но его результат в detail не
        подставлен — запись остаётся прежней константной фразой, и имена
        упавших тестов из журнала опять не прочитать.
        """
        detail = self.red_detail()

        self.assertIn(SUMMARY_LINE, detail)
        for nodeid in FAILED_NODEIDS:
            self.assertIn(nodeid, detail,
                          f"detail не назвал упавший тест {nodeid}: {detail!r}")

    def test_ac5_timeout_detail_names_the_full_suite_timeout(self):
        """Исход «таймаут»: detail называет потолок
        `config.FULL_SUITE_TIMEOUT_SEC` (значение читается от config, не
        литералом) — по записи видно, что прогон не упал, а не уложился.

        Ловит мутацию: таймаут обработан той же ветвью, что красный
        прогон (`green` ложно во всех трёх случаях, причина одна) — в
        detail не окажется ни потолка, ни слова о превышении.
        """
        detail = self.timeout_detail()

        self.assertIn(str(config.FULL_SUITE_TIMEOUT_SEC), detail,
                      f"detail таймаута не называет потолок "
                      f"config.FULL_SUITE_TIMEOUT_SEC="
                      f"{config.FULL_SUITE_TIMEOUT_SEC}: {detail!r}")

    def test_ac5_missing_tests_dir_detail_names_the_absent_suite(self):
        """Исход «tests/ нет в worktree»: detail говорит именно об
        отсутствии каталога полного набора в рабочей копии, а не о
        красноте прогона.

        Ловит мутацию: отсутствие `tests/` по-прежнему схлопнуто в
        «полный набор tests/ красный» — Оператор ищет упавшие тесты там,
        где не запускалось ни одного.
        """
        detail = self.missing_tests_detail()

        self.assertIn("tests/", detail)
        self.assertIn("worktree", detail,
                      f"detail не называет отсутствие tests/ в worktree: "
                      f"{detail!r}")

    def test_ac5_three_outcomes_do_not_share_one_detail(self):
        """Три исхода `acceptance.run_full_suite` дают три РАЗНЫХ detail:
        различимость — свойство записей друг относительно друга, не
        только наличие слов в каждой по отдельности.

        Ловит мутацию: две ветви из трёх собирают detail одним и тем же
        выражением (например, таймаут и отсутствие tests/ обе падают в
        «набор не проверен») — тексты совпадут дословно.
        """
        red = self.red_detail()
        timeout = self.timeout_detail()
        missing = self.missing_tests_detail()

        self.assertNotEqual(red, timeout, "красный прогон и таймаут неразличимы")
        self.assertNotEqual(red, missing,
                            "красный прогон и отсутствие tests/ неразличимы")
        self.assertNotEqual(timeout, missing,
                            "таймаут и отсутствие tests/ неразличимы")


if __name__ == "__main__":
    unittest.main()
