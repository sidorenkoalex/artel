"""Приёмочные тесты SPEC 01M1SCQ6WZHMQVK1AHP9F392JZ (регрессия №15):
опорное время рубежа `orchestrator/fsm_advance.py::_review_rework_gate_refuses`
обязано определяться моментом вердикта `changes_requested` ревьювера
(автокоммит его шага, либо запись журнала `agent run finished`), а не
последним коммитом, тронувшим `tasks/<id>/REVIEW.md` по любой причине —
включая правку леджера замечаний developer'ом (T100), которая сегодня
ошибочно сдвигает опорное время вперёд (инцидент 05.09,
01M1REVEZ1HESMJ7AFD5A9MEJ8).

Красен до реализации: большинство тестов файла — сегодня
`_review_rework_gate_refuses` берёт опорное время буквально как время
ПОСЛЕДНЕГО коммита `REVIEW.md` (`_commit_iso_date(branch,
f"tasks/{task_id}/REVIEW.md")`) без разбора подписи коммита, и вовсе не
смотрит в журнал `steps` — ни для опорного времени (fallback требования
1), ни для критерия «был ли шаг developer» (требование 2, второе условие
OR). Падать им положено именно по отсутствию кода этой задачи, не по
опечатке фикстуры — проверено стабом-заглушкой корректной реализации
(валидация test_author, стаб не закоммичен).

Зелёный с рождения: два теста — `DeveloperNeverRanRefusesTest.test_ac7_*`
и `DeveloperStepAfterBaselinePassesTest.test_ac3_code_commit_after_baseline_passes`
— намеренно устроены так, что в них ровно ОДИН коммит трогает REVIEW.md
— сегодняшняя (наивная, «последний коммит») и будущая (правильная,
«автокоммит шага reviewer») логика вычисления опорного времени в этом
частном случае совпадают, так что базовый инвариант «код после вердикта
— пропускать, код до вердикта — отказывать» уже верен и до этой задачи;
они охраняют этот инвариант от регрессии новым кодом, а не документируют
дыру.

Все тесты гоняют НАСТОЯЩИЙ git (`tests.sandbox.TmpRootTest`, `gitcmd.git`/
`gitcmd.show` НЕ подменены) — так поведение проверяется по фактической
git-истории с управляемой датой коммиттера (`GIT_COMMITTER_DATE`), а не
по угаданным аргументам конкретного вызова `git log`, которые эта задача
ещё не написала.
"""
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import auto, config, fsm_advance, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK_ID = "T001"
ARTIFACT_BRANCH = f"artifact/{TASK_ID.lower()}"
CODE_BRANCH = f"task/{TASK_ID.lower()}-x"

REVIEWER_AUTOCOMMIT_MESSAGE = (
    f"{TASK_ID}: артефакты шага reviewer (автокоммит оркестратора)")
DEVELOPER_AUTOCOMMIT_MESSAGE = (
    f"{TASK_ID}: артефакты шага developer (автокоммит оркестратора)")

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 1
---

# REVIEW: тест регрессии №15

## Замечания

{footer}
"""

_GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "artel tests", "GIT_AUTHOR_EMAIL": "artel@example.invalid",
    "GIT_COMMITTER_NAME": "artel tests", "GIT_COMMITTER_EMAIL": "artel@example.invalid",
}


def _at(year: int, month: int, day: int, hour: int = 10) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)


def _store_ts(when: datetime) -> str:
    """Формат `orchestrator.store.now()` (`%Y-%m-%d %H:%M:%SZ`) — так
    строка ложится в столбец `steps.ts` в точности так же, как её пишет
    настоящий `store.journal`, только со значением, которое выбирает тест,
    а не текущим временем."""
    return when.strftime("%Y-%m-%d %H:%M:%SZ")


# Все даты фикстуры заданы явно (не текущим временем) и строго по
# возрастанию — общий инициализирующий коммит репозитория тоже датирован
# явно (`_INIT_AT`, до всех остальных): `git log` для линейной истории
# может переставить местами родителя и потомка, если у потомка дата
# коммиттера РАНЬШЕ, чем у родителя (не строго топологический порядок по
# умолчанию) — без явной ранней даты у инициализирующего коммита он получил
# бы реальное время прогона теста, которое в этой песочнице позже (2026,
# см. currentDate), чем даты фикстуры ниже, и ломало бы порядок.
_INIT_AT = _at(2020, 1, 1)
T_REVIEWER = _at(2026, 8, 1)       # T1 — вердикт ревьювера, changes_requested
T_CODE_BEFORE = _at(2026, 7, 31)   # до T1 — переделка НЕ отработана
T_CODE_AFTER = _at(2026, 8, 2)     # между T1 и T3 — штатный шаг developer
T_LEDGER_EDIT = _at(2026, 8, 3)    # T3 — правка леджера developer'ом (T100)


class ReviewReworkGateGitTest(TmpRootTest):
    """Общая песочница: настоящий git-репозиторий в `config.ROOT`
    (`TmpRootTest`), две ветки — артефактная (`REVIEW.md`) и кодовая
    (коммиты developer) — обе строятся вручную с управляемой датой
    коммиттера, `_review_rework_gate_refuses` зовётся напрямую."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = TASK_ID
        self.t = {"branch": CODE_BRANCH}
        self._known_branches = set()
        self._git("init", "-q", "-b", config.MAIN_BRANCH)
        self._git("config", "user.email", "artel@example.invalid")
        self._git("config", "user.name", "artel tests")
        (config.ROOT / "README.md").write_text("init\n", encoding="utf-8")
        self._git("add", "README.md")
        self._commit_at("init", _INIT_AT)

    # ------------------------------------------------------------ утилиты

    def _git(self, *args: str):
        result = subprocess.run(["git", *args], cwd=config.ROOT,
                                capture_output=True, text=True)
        assert result.returncode == 0, (args, result.stdout, result.stderr)
        return result

    def _commit_at(self, message: str, when: datetime):
        env = {**os.environ, **_GIT_IDENTITY,
              "GIT_AUTHOR_DATE": when.isoformat(),
              "GIT_COMMITTER_DATE": when.isoformat()}
        result = subprocess.run(["git", "commit", "-q", "-m", message],
                                cwd=config.ROOT, capture_output=True,
                                text=True, env=env)
        assert result.returncode == 0, (message, result.stdout, result.stderr)

    def _checkout(self, branch: str, base: str = config.MAIN_BRANCH):
        if branch in self._known_branches:
            self._git("checkout", "-q", branch)
        else:
            self._git("checkout", "-q", "-b", branch, base)
            self._known_branches.add(branch)

    def commit_review(self, status: str, iteration: int, when: datetime,
                      message: str, footer: str = "",
                      branch: str = ARTIFACT_BRANCH) -> None:
        self._checkout(branch)
        task_dir = config.ROOT / "tasks" / self.task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "REVIEW.md").write_text(
            REVIEW_MD.format(task=self.task_id, status=status,
                             iteration=iteration, footer=footer),
            encoding="utf-8")
        self._git("add", f"tasks/{self.task_id}/REVIEW.md")
        self._commit_at(message, when)

    def commit_code(self, when: datetime, message: str = "код фикса",
                    branch: str = CODE_BRANCH) -> None:
        self._checkout(branch)
        (config.ROOT / "a.py").write_text(f"# {when.isoformat()}\n",
                                          encoding="utf-8")
        self._git("add", "a.py")
        self._commit_at(message, when)

    def journal_row(self, actor: str, action: str, detail: str,
                    when: datetime | None = None) -> None:
        store.journal(self.conn, self.task_id, actor, action, detail)
        if when is not None:
            row_id = self.conn.execute(
                "SELECT last_insert_rowid()").fetchone()[0]
            self.conn.execute("UPDATE steps SET ts=? WHERE id=?",
                              (_store_ts(when), row_id))
            self.conn.commit()

    def enter_in_dev(self, detail: str = "замечания ревью, итерация 1") -> None:
        """Запись `state -> in_dev`, которую в реальном цикле оставляет
        `orchestrator/fsm_advance.py::review` на КАЖДОМ возврате из ревью
        с замечаниями — без неё `auto._role_step_since_state_entry`
        (общая функция требования 2/AC-4) сама деградирует к «такой
        записи нет вовсе» и безусловно засчитывает шаг developer состоявшимся
        (докстринг функции), что замаскировало бы ЛЮБОЙ git-сигнал этого
        файла нулём различающей силы — тесты, которым важен именно
        git-сигнал (или его отсутствие), обязаны сперва создать реалистичное
        журнальное окружение визита, как это делает настоящий цикл.
        """
        self.journal_row("fsm", "state -> in_dev", detail)

    def refuses(self) -> bool:
        return fsm_advance._review_rework_gate_refuses(
            self.conn, self.task_id, self.t, ARTIFACT_BRANCH)

    def journal_details(self) -> str:
        return " ".join(r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,)))


# ---------------------------------------------------------------------
# AC-1 (первая половина требования 1) + AC-2 + AC-6: опорное время —
# автокоммит шага reviewer, не последний коммит, тронувший REVIEW.md.

class IncidentScenarioTest(ReviewReworkGateGitTest):
    """Инцидент 05.09: код (developer, T2) идёт ПОСЛЕ вердикта ревьювера
    (T1), но ПЕРЕД более поздней правкой леджера тем же developer'ом (T3,
    T100) — единственный коммит REVIEW.md, который сегодня считается
    опорным, это T3, и T2 < T3 ошибочно читается как «переделка не
    отработана»."""

    def _build(self) -> None:
        self.commit_review("changes_requested", 1, T_REVIEWER,
                           REVIEWER_AUTOCOMMIT_MESSAGE)
        self.enter_in_dev()
        self.commit_code(T_CODE_AFTER)
        self.commit_review("changes_requested", 1, T_LEDGER_EDIT,
                           DEVELOPER_AUTOCOMMIT_MESSAGE,
                           footer="Леджер: замечание 1 — отработано")

    def test_ac1_baseline_is_reviewer_autocommit_not_a_later_review_md_touch(self):
        """Ловит мутацию: опорное время по-прежнему берётся как время
        ПОСЛЕДНЕГО коммита, тронувшего REVIEW.md (сегодняшнее поведение),
        а не время автокоммита шага reviewer — тогда коммит developer
        (T2), сделанный МЕЖДУ вердиктом (T1) и более поздней правкой
        леджера (T3), ошибочно оценивался бы как «до опорного времени»
        (T2 < T3), и рубеж отказывал бы переходу, хотя штатный шаг
        developer уже был.
        """
        self._build()

        self.assertFalse(
            self.refuses(),
            "коммит developer (T2) после вердикта ревьювера (T1) обязан "
            "пропускать переход независимо от более поздней правки "
            "леджера (T3)")

    def test_ac2_developer_ledger_edit_does_not_move_the_baseline(self):
        """Ловит мутацию: правка леджера замечаний developer'ом (автокоммит
        его шага, тронувший REVIEW.md) засчитывается кандидатом на опорное
        время, потому что она технически самая свежая среди коммитов
        REVIEW.md — будучи самым свежим, этот коммит всё равно не имеет
        права участвовать в вычислении опорного времени по AC-1.
        """
        self._build()

        self.assertFalse(
            self.refuses(),
            "автокоммит шага developer, тронувший REVIEW.md, не обязан "
            "двигать опорное время вперёд, даже будучи самым свежим "
            "коммитом REVIEW.md")

    def test_ac6_incident_scenario_code_then_developer_review_md_touch_passes(self):
        """Тест сценария инцидента (AC-6, дословно): коммит кода
        (developer), затем автокоммит артефактов шага developer,
        тронувший REVIEW.md, — переход `in_dev -> review` обязан пройти.

        Ловит мутацию: любая регрессия к сегодняшнему поведению (опорное
        время = последний коммит REVIEW.md) воспроизводит ровно инцидент
        05.09 — рубеж отказывает переходу, хотя шаг developer состоялся.
        """
        self._build()

        self.assertFalse(self.refuses())


# ---------------------------------------------------------------------
# AC-1 (вторая половина требования 1): нет коммита-автокоммита шага
# reviewer — опорное время берётся из записи журнала.

class BaselineFallsBackToJournalTest(ReviewReworkGateGitTest):
    """Ни один коммит, тронувший REVIEW.md, не является автокоммитом шага
    reviewer — включая САМЫЙ СВЕЖИЙ (правка Оператора вручную,
    T_LATE_NON_AUTOCOMMIT, ПОСЛЕ всего остального) — так тест отличим от
    сегодняшнего поведения «опорное время = дата последнего коммита
    REVIEW.md»: если бы рубеж по-прежнему брал дату этого последнего
    коммита, коммит developer МЕЖДУ вердиктом журнала и этой поздней
    правкой читался бы как «до опорного времени» и отказывал бы —
    единственный способ пройти корректно здесь — использовать fallback
    на запись журнала (AC-1, вторая часть требования 1), реальный момент
    вердикта которого РАНЬШЕ этой поздней правки.
    """

    def setUp(self):
        super().setUp()
        self.commit_review("changes_requested", 1, T_CODE_BEFORE,
                           f"{TASK_ID}: первая правка REVIEW.md вручную")

    def test_ac1_reviewer_journal_entry_is_the_baseline_when_no_autocommit_exists(self):
        """Ловит мутацию: опорное время по-прежнему берётся как дата
        ПОСЛЕДНЕГО коммита REVIEW.md (сегодняшнее поведение) вместо
        fallback на запись журнала — тогда более поздняя правка Оператора
        вручную (T_LATE, ни разу не автокоммит шага reviewer) ошибочно
        сдвигала бы опорное время вперёд, и коммит developer (T2), сделанный
        МЕЖДУ реальным вердиктом журнала (T1) и этой поздней правкой,
        читался бы как «до опорного времени» — рубеж отказывал бы, хотя
        шаг developer уже состоялся ПОСЛЕ настоящего вердикта.
        """
        self.journal_row("reviewer", "agent run finished",
                         "REVIEW.md: changes_requested, итерация 1",
                         when=T_REVIEWER)
        self.enter_in_dev()
        self.commit_code(T_CODE_AFTER)
        self.commit_review("changes_requested", 1, T_LEDGER_EDIT,
                           f"{TASK_ID}: вторая правка REVIEW.md вручную",
                           footer="Вторая правка — иной текст, не леджер")

        self.assertFalse(
            self.refuses(),
            "запись журнала agent run finished роли reviewer обязана "
            "работать опорным временем наравне с git-коммитом — более "
            "поздняя правка REVIEW.md вручную (не автокоммит шага "
            "reviewer) не имеет права сдвигать опорное время вперёд")


# ---------------------------------------------------------------------
# AC-3: рубеж пропускает переход, если ПОСЛЕ опорного времени есть
# коммит developer ИЛИ соответствующая запись журнала (два независимых
# условия OR, требование 2).

class DeveloperStepAfterBaselinePassesTest(ReviewReworkGateGitTest):

    def setUp(self):
        super().setUp()
        self.commit_review("changes_requested", 1, T_REVIEWER,
                           REVIEWER_AUTOCOMMIT_MESSAGE)
        self.enter_in_dev()

    def test_ac3_code_commit_after_baseline_passes(self):
        """Ловит мутацию: сравнение `code_ts > review_ts` испорчено
        (нестрогое неравенство, развёрнутое сравнение) — единственный,
        безо всякой примеси леджера, коммит developer ПОСЛЕ вердикта
        ревьювера обязан пропускать переход.
        """
        self.commit_code(T_CODE_AFTER)

        self.assertFalse(self.refuses())

    def test_ac3_journal_developer_step_after_state_entry_passes_without_a_qualifying_commit(self):
        """Ловит мутацию: рубеж fsm_advance по-прежнему смотрит ТОЛЬКО на
        git-коммиты и не учитывает журнальный сигнал (сегодняшнее
        поведение, второе условие требования 2 отсутствует вовсе) —
        запись `agent run finished` роли developer ПОСЛЕ записи `state ->
        in_dev` этого визита обязана пропускать переход сама по себе, даже
        когда единственный коммит developer в кодовой ветке — ДО вердикта
        (git-условие требования 2 само по себе отказало бы).
        """
        self.commit_code(T_CODE_BEFORE)
        self.journal_row("developer", "agent run finished", "rc=0")

        self.assertFalse(self.refuses())


# ---------------------------------------------------------------------
# AC-4: критерий «был ли шаг developer после опорного момента» — ОДНА
# общая функция с auto.py (сегодня `_role_step_since_state_entry`), не
# два независимо реализованных правила.

class SharedRoleStepCriterionTest(ReviewReworkGateGitTest):

    def setUp(self):
        super().setUp()
        self.commit_review("changes_requested", 1, T_REVIEWER,
                           REVIEWER_AUTOCOMMIT_MESSAGE)
        # Коммит developer строго ДО вердикта — git-условие требования 2
        # само по себе отказало бы; единственный сигнал «переход можно
        # пропустить» здесь — журнальный, разбираемый ниже.
        self.commit_code(T_CODE_BEFORE)

    def test_ac4_legit_first_entry_detail_is_treated_as_satisfied_like_auto_py(self):
        """Ловит мутацию: рубеж fsm_advance реализует ВТОРОЕ, независимое
        от auto.py журнальное правило (просто «есть ли запись agent run
        finished роли developer после state -> in_dev»), вместо
        переиспользования ОБЩЕЙ функции (требование 4, AC-4, сегодня
        `auto._role_step_since_state_entry`) — независимая копия не знала
        бы про исключение «легитимный первый вход»
        (`auto._is_legit_first_entry_detail`/`_LEGIT_FIRST_ENTRY_DETAILS`,
        ANSWER-3 REVIEW.md 01M1R8B3ZKXQT0Z0G6QQQDV906) и отказывала бы
        здесь переходу — общая функция обязана распознать легитимный
        первый вход и пропустить, даже когда самого шага developer после
        него ещё не было.
        """
        legit_detail = auto._LEGIT_FIRST_ENTRY_DETAILS[0]
        self.journal_row("fsm", "state -> in_dev", legit_detail)
        # ни одной записи "agent run finished" роли developer после неё нет

        self.assertFalse(
            self.refuses(),
            "легитимный первый вход в in_dev (без шага developer после "
            "него) обязан пропускать переход тем же основанием, что уже "
            "применяет auto._role_step_since_state_entry к своему гейту")


# ---------------------------------------------------------------------
# AC-5: отказ называет оба момента времени и источник опорного времени.

class RefusalNamesBothMomentsAndSourceTest(ReviewReworkGateGitTest):

    def setUp(self):
        super().setUp()
        self.commit_review("changes_requested", 1, T_REVIEWER,
                           REVIEWER_AUTOCOMMIT_MESSAGE)
        self.enter_in_dev()
        self.commit_code(T_CODE_BEFORE)

    def test_ac5_refusal_names_baseline_developer_commit_and_the_source(self):
        """Ловит мутацию: отказ по-прежнему называет только номер
        итерации (сегодняшний текст `_review_rework_gate_refuses`) — без
        обоих моментов времени и источника опорного времени Оператору
        нечем проверить, что именно сравнил рубеж (требование 3, AC-5).
        """
        refused = self.refuses()

        self.assertTrue(refused)
        detail = self.journal_details()
        self.assertIn("2026-08-01", detail,
                      "отказ обязан называть опорное время (вердикт "
                      "ревьювера)")
        self.assertIn("2026-07-31", detail,
                      "отказ обязан называть время последнего коммита "
                      "developer")
        self.assertIn("reviewer", detail.lower(),
                      "отказ обязан называть источник опорного времени — "
                      "автокоммит шага reviewer")


# ---------------------------------------------------------------------
# AC-7: сценарий «ревьювер вынес changes_requested, developer не
# запускался» — рубеж отказывает переходу так же, как раньше.

class DeveloperNeverRanRefusesTest(ReviewReworkGateGitTest):

    def test_ac7_reviewer_changes_requested_developer_never_ran_refuses(self):
        """Ловит мутацию: условие OR требования 2 реализовано так широко,
        что рубеж перестаёт отказывать вовсе (например, забыт разбор
        случая «журнальных записей вообще нет») — сценарий «developer не
        запускался» обязан по-прежнему отказывать, как и до этой задачи
        (регрессия №13, 01M1RHFRQ2C0P4A57XJJ1WZV8N).
        """
        self.commit_review("changes_requested", 1, T_REVIEWER,
                           REVIEWER_AUTOCOMMIT_MESSAGE)
        self.enter_in_dev()
        self.commit_code(T_CODE_BEFORE)

        self.assertTrue(self.refuses())


# AC-8: skip — существующие тесты регрессии №13 (tests/test_auto_cycle.py,
# планка 01M1RHFRQ2C0P4A57XJJ1WZV8N) уже исполняются штатным CI-гейтом на
# каждом коммите ветки задачи (.github/workflows/ci.yml, джоб python,
# unittest discover -s tests -v), и именно его зелёный статус требует
# merge_gate (orchestrator/fsm.py, cmd_approve при state == "merge_gate").
# Дублирующий здесь subprocess-прогон всего набора не даёт новой гарантии
# сверх штатного гейта — тот же приём, что уже применён в
# tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/acceptance_tests/
# test_ac20_full_suite_regression.py для того же класса критерия.


if __name__ == "__main__":
    unittest.main()
