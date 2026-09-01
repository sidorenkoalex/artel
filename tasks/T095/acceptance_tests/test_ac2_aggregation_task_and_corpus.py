"""AC-2 (tasks/T095/SPEC.md): метрика «трение» агрегируется на уровень
задачи (по шагам этой задачи) и на уровень корпуса (по всем задачам).

Ни формула агрегации, ни разметка блока (AC-3) SPEC не фиксирует
(требование 1 отдаёт «точный состав сигналов и пороги» разработчику) —
поэтому тесты здесь не сравнивают HTML с заранее вычисленным числом
(формула агрегации неизвестна заранее), а проверяют РЕАКЦИЮ отображения
на изменение исходных данных: если множество чисел в блоке трения не
меняется независимо от того, что происходит в логах шагов, агрегации
попросту нет (или она — заглушка), а если меняется — она построена по
факту прочитанных логов. Тот же приём даёт естественную проверку
уровня задачи отдельно от уровня корпуса: правка лога ОДНОЙ задачи не
обязана трогать то, что показано у ДРУГОЙ (изоляция по задаче), а
появление НОВОЙ задачи с ненулевым трением обязано отразиться хоть
где-то в блоке (это и есть «по всем задачам» — корпус).

Данные попадают в отчёт через файлы `.artel/logs/<id>-<role>-N.log`,
доступные на диске к моменту генерации (вариант 4а SPEC требования 4) —
самое прямое прочтение материалов SPEC («по логу шага»/«по файлам
логов, доступным на машине») и самая простая из двух опций требования
4, которую разработчик волен выбрать в PLAN (AC-7). Если разработчик
вместо этого выбирает вариант 4б (журнал по завершении шага), эти тесты
по-прежнему обязаны проходить: значение трения шага определяется тем же
логом того же шага в обоих вариантах (различается лишь МОМЕНТ разбора и
место хранения результата), так что `cmd_report()`, не находя готовой
журнальной записи для шага-фикстуры без реального прогона, обязан(а)
разобрать доступный файл лога напрямую — это не выход за AC-4
(источник по-прежнему «файлы логов и/или state.db», оба локальны).

Красен до реализации: `orchestrator.report`/`orchestrator.agent_log` не
несут метрику трения (`FrictionSandboxTest.setUp`, `_sandbox.py`) —
кроме `TaskLevelIsolationTest`: изоляция между задачами тривиально
верна и без единой строчки метрики трения (нечему смешиваться, если
метрики ещё нет вовсе), поэтому этот тест зелёный с рождения и обязан
остаться зелёным после реализации — как инвариант, а не как временное
совпадение.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (FrictionSandboxTest, bash_call, edit_call,  # noqa: E402
                      friction_section, numeric_tokens, read_call, scope)


class TaskLevelReactsToOwnStepsTest(FrictionSandboxTest):
    """Отображение по задаче обязано зависеть от логов ЭТОЙ задачи."""

    def test_ac2_task_friction_changes_when_its_own_log_gets_noisier(self):
        self.mk_task("T001", "Задача-фикстура для проверки шагов")
        self.write_log("T001", "developer", 1, [
            read_call("t1", "a.py"),
            read_call("t2", "b.py"),
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ])
        html_clean = self.run_report_html()
        tokens_clean = numeric_tokens(friction_section(html_clean))

        # тот же файл лога того же шага, тот же прогон — теперь с повтором
        self.write_log("T001", "developer", 1, [
            read_call("t1", "a.py"),
            read_call("t2", "a.py"),
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ])
        html_noisy = self.run_report_html()
        tokens_noisy = numeric_tokens(friction_section(html_noisy))

        self.assertNotEqual(
            tokens_clean, tokens_noisy,
            "блок трения не изменился, хотя лог единственного шага "
            "задачи стал заметно более шумным (повтор чтения файла) — "
            "похоже, отображение не считается по факту лога")


class TaskLevelIsolationTest(FrictionSandboxTest):
    """Трение одной задачи не обязано определяться логами другой."""

    def test_ac2_one_tasks_log_does_not_change_another_tasks_shown_value(self):
        self.mk_task("T001", "Чистая задача-фикстура")
        self.mk_task("T002", "Вторая задача-фикстура")
        clean_lines = [
            read_call("t1", "a.py"),
            read_call("t2", "b.py"),
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ]
        self.write_log("T001", "developer", 1, clean_lines)
        self.write_log("T002", "developer", 1, clean_lines)

        html_before = self.run_report_html()
        window_t001_before = scope(html_before, "T001")
        self.assertIsNotNone(window_t001_before, "T001 не найдена в отчёте")
        tokens_t001_before = numeric_tokens(window_t001_before)

        # шумим ТОЛЬКО T002; T001 не трогаем вовсе
        self.write_log("T002", "developer", 1, [
            read_call("t1", "z.py"),
            read_call("t2", "z.py"),
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ])
        html_after = self.run_report_html()
        window_t001_after = scope(html_after, "T001")
        self.assertIsNotNone(window_t001_after, "T001 не найдена в отчёте")
        tokens_t001_after = numeric_tokens(window_t001_after)

        self.assertEqual(
            tokens_t001_before, tokens_t001_after,
            "числа рядом с T001 изменились от правки лога ДРУГОЙ задачи "
            "(T002) — трение T001 обязано считаться по шагам T001, не "
            "смешиваться с чужими")


class CorpusLevelReactsToAllTasksTest(FrictionSandboxTest):
    """Блок трения обязан отражать данные ВСЕХ задач корпуса, не только
    первой когда-либо созданной."""

    def test_ac2_block_changes_when_a_new_noisy_task_appears_in_corpus(self):
        self.mk_task("T001", "Единственная задача — чистый шаг")
        self.write_log("T001", "developer", 1, [
            read_call("t1", "a.py"),
            read_call("t2", "b.py"),
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ])
        html_one_task = self.run_report_html()
        tokens_one_task = numeric_tokens(friction_section(html_one_task))

        self.mk_task("T002", "Новая задача — шумный шаг")
        self.write_log("T002", "developer", 1, [
            read_call("t1", "z.py"),
            read_call("t2", "z.py"),
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ])
        html_two_tasks = self.run_report_html()
        tokens_two_tasks = numeric_tokens(friction_section(html_two_tasks))

        self.assertNotEqual(
            tokens_one_task, tokens_two_tasks,
            "блок трения не изменился при появлении в корпусе новой "
            "задачи с шумным шагом — агрегация «на уровень корпуса (по "
            "всем задачам)» не подтверждается")


if __name__ == "__main__":
    unittest.main()
