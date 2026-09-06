"""Красен до реализации: AC-3/AC-4/AC-5/AC-6 падают — `runner.
run_agent_once` пока безусловно журналирует «agent run finished» и
возвращает исход "ok" при rc=0, не проверяя, оставила ли роль на диске
рабочего каталога свой обязательный артефакт (SPEC 01M1RQ12JVHE3PQYDFV1XPSTQ3,
требование 3; реализация в `orchestrator/runner.py` явно отложена до
мержа стека ч.3, см. SPEC «Контекст»/«Не входит») — в этих четырёх тестах
рабочий каталог роли (`role_workdir_task_dir`) намеренно остаётся без
нужного файла, а текущий код всё равно доводит шаг до "ok" без ретрая и
эскалации. AC-7 (регрессия штатного пути) уже зелёный — сегодняшний код
и так не трогает случай, когда артефакт на месте, никакой новой проверки
там нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import RoleCwdSandbox  # noqa: E402
from orchestrator import config  # noqa: E402


def _all_ok_attempts():
    """AGENT_ATTEMPTS одинаковых успешных попыток (rc=0) — артефакт
    отсутствует на КАЖДОЙ из них: если бы шаг когда-то и написал файл,
    вопрос «отсутствует ли артефакт» больше не стоял бы (регрессия
    покрыта отдельно, `Ac7ArtifactPresentStepStaysUnaffectedTest`)."""
    return [(0, [f"готово (попытка {n})\n"])
           for n in range(1, config.AGENT_ATTEMPTS + 1)]


class Ac3ReviewerMissingReviewMdFailsTheStepTest(RoleCwdSandbox):

    def test_ac3_missing_review_md_fails_the_step_not_finishes_it(self):
        """Ревьювер отчитывается rc=0 на каждой из AGENT_ATTEMPTS попыток,
        но `REVIEW.md` ни разу не появляется в рабочем каталоге роли —
        шаг обязан довести дело до эскалации задачи тем же путём, что и
        настоящий провал агента (`tests/test_agent_failure.py::
        CmdRunFailureTest.test_escalates_after_retries_exhausted`), а не
        тихо признать rc=0 успехом.

        Ловит мутацию: проверка присутствия `REVIEW.md` смотрит не в
        рабочий каталог роли, а туда же, откуда бриф читает SPEC.md
        (`config.TASKS`, эмуляция артефактной ветки) — там тоже пусто,
        но по другой причине, и в реальной системе эти два адреса не
        совпадают: тест должен красне(ва)ть именно по причине отсутствия
        файла в `workspace.path`, не по побочному совпадению путей.
        """
        self.set_state("review")

        self.run_agent(*_all_ok_attempts())

        self.assertEqual(self.popen.call_count, config.AGENT_ATTEMPTS,
                         "rc=0 без артефакта не должен останавливать "
                         "ретраи после первой же попытки")
        self.assertEqual(self.task_row()["state"], "escalated")
        details = self.journal_details()
        self.assertTrue(
            any("шаг завершён без артефакта REVIEW.md" in d for d in details),
            details)
        self.assertEqual(
            self.journal_details("agent run finished"), [],
            "провал без артефакта не должен журналироваться как штатное "
            "завершение шага")


class Ac4AnalystMissingSpecAndQuestionsFailsTheStepTest(RoleCwdSandbox):

    def setUp(self):
        super().setUp()
        self.write_tz()

    def test_ac4_missing_spec_and_questions_fails_the_step(self):
        """Аналитик отчитывается rc=0 на каждой попытке, но ни `SPEC.md`,
        ни `QUESTIONS.md` ни разу не появляются в рабочем каталоге роли —
        тот же класс отказа, что и AC-3/AC-5/AC-6, для роли, у которой
        обязательный выход — один ИЗ ДВУХ файлов (SPEC.md — ТЗ понятно,
        QUESTIONS.md — эскалация к Оператору).

        Ловит мутацию: проверка требует ОБА файла одновременно (`and`
        вместо `or`) — на штатном пути аналитик пишет ровно один из них,
        и такая мутация ложно проваливала бы КАЖДЫЙ штатный шаг analyst,
        а не только тот, где нет ни одного; здесь же нет ни одного из
        двух, так что оба варианта проверки (and/or) сходятся на одном и
        том же результате «отсутствует» — тест целится в сам факт отказа,
        не в форму условия.
        """
        self.set_state("spec_writing")

        self.run_agent(*_all_ok_attempts())

        self.assertEqual(self.popen.call_count, config.AGENT_ATTEMPTS)
        self.assertEqual(self.task_row()["state"], "escalated")
        details = self.journal_details()
        self.assertTrue(
            any("шаг завершён без артефакта SPEC.md/QUESTIONS.md" in d
               for d in details),
            details)
        self.assertEqual(self.journal_details("agent run finished"), [])


class Ac5DeveloperMissingPlanFailsTheStepTest(RoleCwdSandbox):

    def test_ac5_missing_plan_md_fails_the_step(self):
        """Разработчик отчитывается rc=0 на каждой попытке, но `PLAN.md`
        ни разу не появляется в рабочем каталоге роли — тот же класс
        отказа, что и у ревьювера (AC-3), для роли developer.

        Ловит мутацию: проверка смотрит на диск ПОСЛЕ автокоммита шага
        (`checkpoint.commit_step_artifacts`), а не до него — в продовом
        коде автокоммит переносит `tasks/<id>/` в артефактную ветку и
        стирает его с диска рабочего каталога (`shutil.rmtree`), поэтому
        проверка «после» видела бы пустой каталог всегда, даже когда
        PLAN.md реально был, и штатный путь (AC-7) ложно проваливался бы.
        """
        self.set_state("in_dev")

        self.run_agent(*_all_ok_attempts())

        self.assertEqual(self.popen.call_count, config.AGENT_ATTEMPTS)
        self.assertEqual(self.task_row()["state"], "escalated")
        details = self.journal_details()
        self.assertTrue(
            any("шаг завершён без артефакта PLAN.md" in d for d in details),
            details)
        self.assertEqual(self.journal_details("agent run finished"), [])


class Ac6TestAuthorMissingAcceptanceTestsFailsTheStepTest(RoleCwdSandbox):

    def test_ac6_missing_acceptance_tests_dir_fails_the_step(self):
        """Автор приёмочных тестов отчитывается rc=0 на каждой попытке,
        но каталог `acceptance_tests/` ни разу не появляется в рабочем
        каталоге роли — тот же класс отказа (AC-3/AC-4/AC-5), критерий —
        по каталогу, не по конкретному имени файла внутри него.

        Ловит мутацию: проверка ищет конкретный файл (например,
        `acceptance_tests/test_ac1.py`) вместо факта существования и
        непустоты самого каталога — критерий сформулирован по каталогу
        целиком, конкретное имя файла тестов не оговорено ни SPEC, ни
        планкой.
        """
        self.set_state("tests_writing")

        self.run_agent(*_all_ok_attempts())

        self.assertEqual(self.popen.call_count, config.AGENT_ATTEMPTS)
        self.assertEqual(self.task_row()["state"], "escalated")
        details = self.journal_details()
        self.assertTrue(
            any("шаг завершён без артефакта acceptance_tests/" in d
               for d in details),
            details)
        self.assertEqual(self.journal_details("agent run finished"), [])


ROLE_ARTIFACTS = (
    ("analyst", "spec_writing", ("SPEC.md",)),
    ("test_author", "tests_writing", ("acceptance_tests/test_marker.py",)),
    ("developer", "in_dev", ("PLAN.md",)),
    ("reviewer", "review", ("REVIEW.md",)),
)


class Ac7ArtifactPresentStepStaysUnaffectedTest(RoleCwdSandbox):
    """Регрессия (критерий приёмки 7): артефакт на месте — исход и журнал
    прежние, ни один из четырёх сценариев AC-3..AC-6 не пойман по ошибке."""

    def setUp(self):
        super().setUp()
        self.write_tz()

    def test_ac7_present_artifact_keeps_the_step_ok(self):
        """Для каждой из четырёх ролей — один успешный (rc=0) прогон, где
        нужный артефакт уже лежит в рабочем каталоге роли ДО прогона
        (`seed_role_artifact`, имитация «роль уже написала») — шаг
        обязан довести дело до "agent run finished" с первой попытки,
        без ретрая и без эскалации, тем же результатом, что и до
        появления проверки присутствия артефакта.

        Ловит мутацию: проверка присутствия смотрит не в `workspace.
        path(task_id)/tasks/<id>/`, а в другой каталог (например, в
        `config.TASKS/<id>/`, эмуляцию артефактной ветки, где ничего из
        сидированного здесь нет) — тогда штатный путь ложно ловился бы
        как «артефакта нет», ретраил бы и в итоге эскалировал задачу
        вместо одного тихого "agent run finished".
        """
        for role, state, artifacts in ROLE_ARTIFACTS:
            with self.subTest(role=role):
                # Счётчик — ДО прогона этой роли: `self.TASK` общий на все
                # четыре подтеста, журнал копится, «ровно одна новая запись
                # agent run finished» проверяется приростом, не абсолютным
                # числом (иначе третья/четвёртая роль в цикле ложно ловила
                # бы уже накопленные записи предыдущих ролей).
                finished_before = len(self.journal_details("agent run finished"))
                self.set_state(state)
                for rel in artifacts:
                    self.seed_role_artifact(rel)

                self.run_agent((0, ["готово\n"]))

                self.assertEqual(self.popen.call_count, 1,
                                 f"{role}: штатный путь не должен ретраить")
                self.assertEqual(self.task_row()["state"], state,
                                 f"{role}: штатный путь не должен эскалировать")
                self.assertEqual(
                    len(self.journal_details("agent run finished")),
                    finished_before + 1,
                    f"{role}: штатное завершение не журналировано ровно раз")
                self.assertFalse(
                    any("шаг завершён без артефакта" in d
                       for d in self.journal_details()),
                    f"{role}: штатный путь с артефактом на месте не должен "
                    f"получать пометку его отсутствия")


if __name__ == "__main__":
    unittest.main()
