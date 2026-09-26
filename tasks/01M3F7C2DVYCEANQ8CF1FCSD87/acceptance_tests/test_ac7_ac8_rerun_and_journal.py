"""AC-7/AC-8: штатный повтор и запись журнала об его исходе.

Красен до реализации: команды `ci-rerun` в пульте нет вовсе — `resolve_command`
не находит обработчика ни в таблице команд `orchestrator/artel.py`, ни по
очевидным адресам, и `run_ci_rerun` валит тест этим сообщением.

Повтор в обоих тестах исполняет НАСТОЯЩАЯ `ci.trigger_rerun` (шпион песочницы
делегирует ей, требование 7): и поиск прогона по sha, и `gh run rerun
--failed`, и `gh run watch` уходят в подменённый `gh`, сети нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (BRANCH_GREEN, REASON, RUN_ID, CiRerunSandbox,  # noqa: E402
                      names_green_outcome, names_red_outcome)


class RerunAndJournalTest(CiRerunSandbox):

    def test_ac7_happy_path_calls_trigger_rerun_once_and_journals_outcome(self):
        """Штатный путь: один вызов `ci.trigger_rerun` + запись журнала.

        Задача в `verifying`, CI ветки завершённо-красный, голова совпадает с
        sha красного статуса, имена упавших заданий ветки не пересекаются с
        не-зелёными заданиями вершины главной ветки. Повтор обязан
        запуститься ровно один раз и ровно для ветки задачи, а журнал —
        понести основание Оператора, id прогона и исход ожидания.

        Ловит мутацию: повтор заводится своим кодом (`gh run rerun` прямо из
        команды) вместо `ci.trigger_rerun` — `trigger_calls` останется
        пустым; либо повтор зовётся в цикле «до зелёного» — вызовов станет
        больше одного; либо в журнал уходит только основание, без id прогона
        и исхода, и Оператор не может отличить состоявшийся повтор от
        несостоявшегося.
        """
        self.enter_verifying_red()
        self.branch_check_runs_after_rerun = BRANCH_GREEN
        before = self.last_step_id()

        text = self.run_ci_rerun(REASON)
        records = self.journal_since(before)

        self.assertEqual(
            self.trigger_calls, [self.branch],
            f"повтор обязан исполняться ровно одним вызовом ci.trigger_rerun "
            f"с веткой задачи; сказано: {text!r}")
        self.assertTrue(
            any(RUN_ID in " ".join(argv) for argv in self.rerun_calls),
            f"настоящая ci.trigger_rerun обязана дойти до `gh run rerun "
            f"{RUN_ID} --failed`; argv gh: {self.gh_calls_since_command()}")
        self.assertTrue(
            any(REASON in record and RUN_ID in record for record in records),
            f"запись журнала обязана нести основание Оператора и id прогона; "
            f"записи: {records}")
        self.assertTrue(
            any(names_green_outcome(record) for record in records),
            f"запись журнала обязана называть исход ожидания (здесь — "
            f"зелёный); записи: {records}")
        self.assertEqual(
            self.state(), "verifying",
            "сама команда состояния задачи не меняет (требование 9)")
        self.assertEqual(
            self.state_transitions_since(before), [],
            "команда не двигает автомат — перехода FSM в журнале нет")

    def test_ac8_red_again_keeps_verifying_and_names_outcome(self):
        """Повтор снова красный: исход назван, задача осталась в `verifying`.

        Фикстура: повтор запускается и завершается, но CI головы ветки
        остаётся завершённо-красным (то же задание упало снова), а `gh run
        watch --exit-status` отдаёт ненулевой код с заключением прогона.
        Оператор обязан прочитать в журнале именно этот исход; роль при этом
        не запускается (`runner.cmd_run`/`spawn_agent` в песочнице падают
        `AssertionError` на любом вызове), переход FSM не происходит.

        Ловит мутацию: исход ожидания журналируется одинаково для любого
        повтора («повтор запущен») — снова красный прогон читался бы в
        журнале как зелёный, и Оператор считал бы флейк погашенным.
        """
        self.enter_verifying_red()
        self.watch_rc = 1
        # Текст `gh` намеренно НЕ содержит слова об исходе, по которому
        # `names_red_outcome` узнаёт «снова красный»: иначе реализация,
        # журналирующая вывод `gh` без собственного вердикта об исходе,
        # прошла бы тест на чужом слове.
        self.watch_stderr = f"прогон {RUN_ID} завершился с ошибкой"
        before = self.last_step_id()

        text = self.run_ci_rerun(REASON)
        records = self.journal_since(before)

        self.assertEqual(
            self.trigger_calls, [self.branch],
            f"штатные предусловия выполнены — повтор обязан состояться; "
            f"сказано: {text!r}")
        self.assertTrue(
            any(names_red_outcome(record) for record in records),
            f"запись журнала обязана называть исход «снова красный»; "
            f"записи: {records}")
        self.assertFalse(
            any(names_green_outcome(record) for record in records),
            f"снова красный повтор не имеет права быть записан зелёным "
            f"исходом; записи: {records}")
        self.assertEqual(
            self.state(), "verifying",
            "после снова красного повтора задача остаётся в verifying")
        self.assertEqual(
            self.state_transitions_since(before), [],
            "перехода FSM команда не делает (требование 9)")


if __name__ == "__main__":
    unittest.main()
