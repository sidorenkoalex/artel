"""AC-2: файл задачи держит сценарии AC-1/3/10/12/15/16 Б-1б и мутации M14/M18/M20.

Группа: разовый
Красен до реализации: файла tests/test_canary_parallel_protection.py ещё нет — сбор вложенного pytest не находит ни одного теста.

Свойство «файл содержит тест сценария со свойствами требований 2–3»
проверяется исполнением: каждая мутация требования 5 SPEC накладывается на
копию рабочей копии кода (не на саму рабочую копию), файл задачи гоняется
в копии — хотя бы один его тест обязан покраснеть красным утверждением (не
зависанием до таймаута pytest и не прерыванием). Контроль — та же копия без
мутации: все тесты файла зелёные, иначе краснота под мутацией ничего не
доказывает.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runs import run_under_mutations, run_unmutated_copy  # noqa: E402

CANARY = "orchestrator/canary.py"
ARTEL = "orchestrator/artel.py"


class MutationsReddenNewFileTest(unittest.TestCase):

    def test_ac2_control_unmutated_copy_is_green(self):
        """Копия кода без мутаций: каждый тест файла задачи зелёный.

        Сценарий: копия рабочей копии во временном каталоге, каждый тест
        файла — отдельным процессом pytest; все коды возврата 0.
        Ловит мутацию: тест файла зависит от окружения рабочей копии (`.git`,
        настоящий реестр пульта) и в копии красен — тогда краснота под
        мутациями ниже была бы краснотой окружения, и этот контроль краснеет.
        """
        run_unmutated_copy()

    def test_ac2_ac1_sequential_literal_catches_zavershen(self):
        """Мутация литерала последовательной ветки краснит файл задачи.

        Сценарий: в последовательной ветке `cmd_canary` (вхождение с отступом
        8 пробелов) «прогон {run_stamp} завершён» → «завершен».
        Ловит мутацию: тест AC-1 Б-1б сверяет вывод подстрокой («прогон»),
        а не дословно с литералом SEQUENTIAL_LITERAL — мутация выживает, и
        этот тест краснеет.
        """
        run_under_mutations([(
            CANARY,
            '\n        print(f"[canary] прогон {run_stamp} завершён")',
            '\n        print(f"[canary] прогон {run_stamp} завершен")')],
            "AC-1 (завершён → завершен)")

    def test_ac2_ac3_parallel_detach_catches_dropped_parallel(self):
        """Отвязанный процесс без `--parallel` краснит файл задачи.

        Сценарий: в `artel._cmd_canary` фильтр argv отвязанного процесса
        выбрасывает и `--detach`, и `--parallel`.
        Ловит мутацию: тест AC-3 Б-1б проверяет только отсутствие `--detach`
        и не считает вхождения `--parallel` в argv — мутация выживает, и этот
        тест краснеет.
        """
        run_under_mutations([(
            ARTEL,
            '_detach_canary([arg for arg in rest if arg != "--detach"])',
            '_detach_canary([arg for arg in rest if arg not in '
            '("--detach", "--parallel")])')],
            "AC-3 (--parallel выброшен из argv отвязанного)")

    def test_ac2_ac10_ac12_baseline_catches_set_baseline_in_finish(self):
        """Запись `canary_baseline` в `_finish_child` краснит файл задачи.

        Сценарий: перед `if _has_run_row(run_stamp, child.title):` в
        `_finish_child` вставлена `store.set_canary_baseline(...)`.
        Ловит мутацию: тесты AC-10/AC-12 Б-1б не заводят базовую строку до
        прогона или не сравнивают таблицу `canary_baseline` после — мутация
        выживает, и этот тест краснеет.
        """
        run_under_mutations([(
            CANARY,
            "\n    if _has_run_row(run_stamp, child.title):",
            "\n    store.set_canary_baseline(store.db(), child.title, 0, 0.0, 0, "
            "plan.name)\n    if _has_run_row(run_stamp, child.title):")],
            "AC-10/AC-12 (set_canary_baseline в _finish_child)")

    def test_ac2_ac15_parent_death_catches_upper_set(self):
        """Набор дочернего в верхнем регистре краснит файл задачи.

        Сценарий: в `_child_argv` `"--set", plan.name` → `plan.name.upper()`.
        Ловит мутацию: подменённый дочерний теста AC-15 Б-1б берёт `--set` не
        из настоящего argv после run-task, а из константы — запись дочернего
        несёт прежний набор, `live_run_note(default_set_only=True)` не `None`,
        мутация выживает, и этот тест краснеет.
        """
        run_under_mutations([(
            CANARY,
            '"--set", plan.name, "--summary"',
            '"--set", plan.name.upper(), "--summary"')],
            "AC-15 (--set plan.name.upper())")

    def test_ac2_ac16_drop_catches_disabled_mark_check(self):
        """Снятая сверка метки в `cmd_canary_run_task` краснит файл задачи.

        Сценарий: `if not _mark_owned_by_parent(mark):` → `if False:`.
        Ловит мутацию: тест AC-16 Б-1б не проверяет, что у `gamma` не было
        ведения (`_run_one_task`) и ровно одна строка — красная строка
        родителя, — мутация выживает, и этот тест краснеет.
        """
        run_under_mutations([(
            CANARY,
            "if not _mark_owned_by_parent(mark):",
            "if False:")],
            "AC-16 (сверка метки снята)")

    def test_ac2_ac16_drop_catches_missing_parent_red_row(self):
        """Удалённая красная строка родителя краснит файл задачи.

        Сценарий: в `_finish_child` удалён вызов
        `_report_child_failure(run_stamp, child.title, plan, reason)` перед
        `return False`.
        Ловит мутацию: тест AC-16 Б-1б не требует у `gamma` ровно одной
        строки с полями `_report_child_failure` — мутация выживает, и этот
        тест краснеет.
        """
        run_under_mutations([(
            CANARY,
            "\n    _report_child_failure(run_stamp, child.title, plan, reason)\n"
            "    return False",
            "\n    return False")],
            "AC-16 (_report_child_failure удалён)")

    def test_ac2_m14_nonzero_exit_with_row_catches_ignored_code(self):
        """M14: код выхода дочернего со строкой прогона перестал учитываться.

        Сценарий: в `_finish_child`
        `return code == 0 and reason is None and not child.killed` →
        `return reason is None and not child.killed`.
        Ловит мутацию: тест M14 не требует `SystemExit` «прогон … красный»
        при `alfa`, вышедшем с кодом 3 после своей строки, — мутация
        выживает, и этот тест краснеет.
        """
        run_under_mutations([(
            CANARY,
            "return code == 0 and reason is None and not child.killed",
            "return reason is None and not child.killed")],
            "M14 (код выхода не учтён)")

    def test_ac2_m18_sigint_catches_missing_handler(self):
        """M18: SIGINT выпал из сигналов параллельного прогона.

        Сценарий: `_PARALLEL_SIGNALS` без `signal.SIGINT`.
        Ловит мутацию: тест M18 шлёт SIGINT, не дождавшись обработчика
        родителя, или пропускает `KeyboardInterrupt` из теста — мутация
        выживает либо прерывает вложенный pytest вместо красного
        утверждения, и этот тест краснеет.
        """
        run_under_mutations([(
            CANARY,
            "_PARALLEL_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)",
            "_PARALLEL_SIGNALS = (signal.SIGTERM, signal.SIGHUP)")],
            "M18 (без SIGINT)")

    def test_ac2_m20_grandchild_catches_kill_instead_of_killpg(self):
        """M20: сигнал уходит процессу дочернего, а не его группе.

        Сценарий: в `_signal_group` `os.killpg(child.proc.pid, signum)` →
        `os.kill(child.proc.pid, signum)`; файл задачи краснеет примерно
        через `PARALLEL_STOP_GRACE_SEC`, не зависая до таймаута pytest.
        Ловит мутацию: внук теста M20 запущен в своей сессии или дочерний
        выходит по SIGTERM сам, не дожидаясь внука, — мутация выживает, и
        этот тест краснеет.
        """
        run_under_mutations([(
            CANARY,
            "os.killpg(child.proc.pid, signum)",
            "os.kill(child.proc.pid, signum)")],
            "M20 (os.kill вместо os.killpg)")


if __name__ == "__main__":
    unittest.main()
