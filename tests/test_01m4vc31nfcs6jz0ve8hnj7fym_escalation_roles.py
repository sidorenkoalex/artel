"""Роли эскалаций прогона канарейки и чистота прогона по ним.

`canary.escalation_roles(steps)` по журналу задачи клона называет роль
каждой эскалации: роль состояния, в которое задача вошла последним
переходом `state -> X` до `state -> escalated` (без перехода — начальное
`spec_writing`), если до следующего перехода стоит маркер эскалации по
артефакту роли (`fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER`); иначе —
`unknown`. `models.unclean_reason` на шаблоне с выполненной ожидаемой
эскалацией допускает по одной эскалации `analyst` и `spec_auditor`;
строки без данных о ролях читаются по прежнему правилу.

Группа: долгоживущий
Красен до реализации: функции `canary.escalation_roles`, параметра `escalation_roles` у `store.insert_canary_run` и правила ролей в `models.unclean_reason` ещё нет — `AttributeError`/`TypeError`/прежняя причина «эскалаций 2, ожидаемая эскалация покрывает только одну».
"""

import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import canary, config, fsm, models, store

MARKER = fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER
FIXATION = "sha зафиксирован"
ESCALATED = "state -> escalated"
BUDGET_DETAIL = "бюджет исчерпан: $1.00 из $1.00"

# Тексты деталей, которые нарочно называют «чужие» роли: роль не берётся
# из текста детали (AC-2).
MISLEADING_DETAILS = (
    "analyst: батч вопросов по ТЗ", "developer: PLAN.md escalate",
    "spec_auditor", "reviewer: лимит", "test_author: AC-1 escalate", "",
    None, "unknown",
)


class Journal:
    """Построитель журнала задачи клона: записи — словари с полями шага."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.steps = []

    def add(self, action: str, detail=None, actor: str = "fsm") -> "Journal":
        self.steps.append({"ts": f"2026-10-14T00:00:{len(self.steps):02d}Z",
                           "actor": actor, "action": action,
                           "detail": detail})
        return self

    def created(self) -> "Journal":
        return self.add("created", "Учебная задача", actor="catalog")

    def model_set(self) -> "Journal":
        return self.add("набор моделей задачи", "c-codex-all", actor="catalog")

    def role_step(self) -> "Journal":
        """`agent run started`/`agent run finished` — одна или несколько пар."""
        for _ in range(self.rng.randint(1, 3)):
            self.add("agent run started", "попытка", actor="runner")
            self.add("agent run finished", "ok", actor="runner")
        return self

    def enter(self, state: str, detail=None) -> "Journal":
        """Переход и фиксация за ним, как пишет `store.set_state`."""
        if detail is None:
            detail = self.rng.choice(MISLEADING_DETAILS)
        self.add(f"state -> {state}", detail)
        return self.add(FIXATION, "a" * 40)

    def marker(self) -> "Journal":
        return self.add(MARKER, self.rng.choice(MISLEADING_DETAILS))


def seeded_rng(test: unittest.TestCase) -> tuple[random.Random, int]:
    seed = random.randrange(2 ** 32)
    print(f"зерно: {seed}")
    return random.Random(seed), seed


def run_row(roles, **overrides) -> dict:
    """Строка `canary_runs` AC-5: green, ноль итераций ревью, без отказа
    автогейта, выполненная ожидаемая эскалация; `escalations` — длина
    перечня ролей."""
    row = {
        "run_stamp": "20261014T000000Z", "title": "canary-status-sort",
        "task_id": "01X", "steps": 7, "cost_usd": 1.0,
        "review_iterations": 0, "outcome": "merge_gate",
        "expected_escalation": "yes", "actual_escalation": 1,
        "marker_mismatch": 0, "verdict": "green", "set_name": "default",
        "models_summary": None, "acceptance_route": "autogate",
        "autogate_refusal": None,
    }
    if roles is not None:
        row["escalation_roles"] = roles
        row["escalations"] = len(roles.split(",")) if roles else 0
    row.update(overrides)
    return row


class EscalationRolesTest(unittest.TestCase):
    """`canary.escalation_roles` — чистая функция журнала, без песочницы."""

    def test_ac1_analyst_then_spec_auditor_on_real_clone_journal(self):
        """Журнал как у реального клона: ловушку увидели analyst и аудитор SPEC.

        Первая эскалация — без предшествующего `state -> spec_writing`,
        вторая — после `state -> spec_audit`, перед ней `agent run
        finished`, за ней фиксация и только потом маркер роли. Ожидается
        `["analyst", "spec_auditor"]`.

        Ловит мутацию: маркер ищется строго следующей записью за
        `state -> escalated` — фиксация между ними даёт
        `["unknown", "unknown"]` вместо `["analyst", "spec_auditor"]`.
        """
        rng, seed = seeded_rng(self)
        j = Journal(rng)
        j.created().model_set().role_step()
        j.add(ESCALATED, "analyst: батч вопросов").add(FIXATION, "a" * 40)
        j.marker()
        j.enter("spec_writing").role_step()
        j.enter("spec_audit").role_step()
        j.add(ESCALATED, "spec_auditor: SPEC-AUDIT escalate")
        j.add(FIXATION, "b" * 40).marker()
        self.assertEqual(canary.escalation_roles(j.steps),
                         ["analyst", "spec_auditor"], f"зерно: {seed}")

    def test_ac2_role_comes_from_last_transition_not_detail(self):
        """Роль — по последнему переходу `state -> X` до `escalated`.

        Для каждого X между переходом и эскалацией стоят записи шага роли,
        детали — случайные тексты с именами других ролей (в том числе
        «analyst: батч вопросов по ТЗ» у `spec_audit`); за эскалацией —
        фиксация, затем маркер.

        Ловит мутацию: роль читается из текста детали перехода либо из
        записи прямо перед `escalated` (`agent run finished`) — для
        `spec_audit` с деталью «analyst: …» получается `analyst`/`unknown`
        вместо `spec_auditor`; или `spec_writing` не сопоставлен `analyst`.
        """
        rng, seed = seeded_rng(self)
        cases = (("spec_audit", "spec_auditor", "analyst: батч вопросов по ТЗ"),
                 ("in_dev", "developer", None),
                 ("tests_writing", "test_author", None),
                 ("review", "reviewer", None),
                 ("spec_writing", "analyst", None))
        for state, role, detail in cases:
            with self.subTest(state=state, seed=seed):
                j = Journal(rng)
                j.created().role_step()
                j.enter(state, detail).role_step()
                j.add(ESCALATED, rng.choice(MISLEADING_DETAILS))
                j.add(FIXATION, "c" * 40).marker()
                self.assertEqual(canary.escalation_roles(j.steps), [role],
                                 f"зерно: {seed}")

    def test_ac3_initial_state_unmapped_state_and_no_escalation(self):
        """Без перехода — `analyst`; после `verifying` — `unknown`; без эскалаций — пусто.

        Ловит мутацию: эскалация без предшествующего перехода даёт
        `unknown` (начальное `spec_writing` не учтено); состояние вне
        сопоставления ролей даёт роль соседнего состояния или исключение;
        журнал без эскалаций даёт `None` вместо `[]`.
        """
        rng, seed = seeded_rng(self)
        j = Journal(rng)
        j.created().model_set().role_step()
        j.add(ESCALATED, "батч").add(FIXATION, "d" * 40).marker()
        self.assertEqual(canary.escalation_roles(j.steps), ["analyst"],
                         f"зерно: {seed}")

        j = Journal(rng)
        j.created().role_step().enter("spec_writing").role_step()
        j.enter("verifying")
        j.add("agent run finished", "ok", actor="runner")
        j.add(ESCALATED, "verify").add(FIXATION, "e" * 40).marker()
        self.assertEqual(canary.escalation_roles(j.steps), ["unknown"],
                         f"зерно: {seed}")

        j = Journal(rng)
        j.created().model_set().role_step().enter("spec_audit").role_step()
        j.enter("tests_writing").role_step()
        self.assertEqual(canary.escalation_roles(j.steps), [],
                         f"зерно: {seed}")

    def test_ac11_pult_escalation_is_unknown_marker_bounded_by_transition(self):
        """Бюджетная эскалация из `spec_audit` и из `spec_writing` — `unknown`.

        (а) ловушка analyst с маркером, затем бюджетная эскалация из
        `spec_audit` без маркера до следующего перехода — `["analyst",
        "unknown"]`; (б) бюджетная эскалация на старте без маркера, затем
        ловушка аудитора с маркером уже после следующих переходов —
        `["unknown", "spec_auditor"]`.

        Ловит мутацию: маркер ищется где угодно после `escalated` без
        границы следующего перехода — в (б) первой эскалации засчитан
        маркер второй, `["analyst", "spec_auditor"]`; или эскалация без
        маркера получает роль состояния (`spec_auditor`/`analyst`).
        """
        rng, seed = seeded_rng(self)
        a = Journal(rng)
        a.created().role_step()
        a.add(ESCALATED, "analyst: ловушка").add(FIXATION, "1" * 40).marker()
        a.enter("spec_writing").role_step()
        a.enter("spec_audit").role_step()
        a.add(ESCALATED, BUDGET_DETAIL).add(FIXATION, "2" * 40)
        a.enter("spec_audit")
        self.assertEqual(canary.escalation_roles(a.steps),
                         ["analyst", "unknown"], f"зерно: {seed}")

        b = Journal(rng)
        b.created().role_step()
        b.add(ESCALATED, BUDGET_DETAIL).add(FIXATION, "3" * 40)
        b.enter("spec_writing").role_step()
        b.enter("spec_audit").role_step()
        b.add(ESCALATED, "spec_auditor: ловушка").add(FIXATION, "4" * 40)
        b.marker()
        self.assertEqual(canary.escalation_roles(b.steps),
                         ["unknown", "spec_auditor"], f"зерно: {seed}")

    def test_ac11_pult_escalation_row_is_unclean_naming_unknown(self):
        """Строка AC-5 с перечнем (а) либо (б) — не чистая, причина называет `unknown`.

        Ловит мутацию: роль `unknown` пропускается критерием как
        допустимая (или считается «ожидаемой») — прогон с бюджетной
        эскалацией засчитан чистым.
        """
        for roles in ("analyst,unknown", "unknown,spec_auditor"):
            with self.subTest(roles=roles):
                reason = models.unclean_reason(run_row(roles))
                self.assertIsNotNone(reason)
                self.assertIn("эскалаций роли unknown: 1", reason)


class UncleanReasonByRolesTest(unittest.TestCase):
    """`models.unclean_reason`/`clean_run` по строке с данными о ролях."""

    def test_ac5_one_analyst_and_one_spec_auditor_are_clean(self):
        """`analyst,spec_auditor`, `analyst`, `spec_auditor` при выполненной ожидаемой — чистые.

        Ловит мутацию: критерий по-прежнему считает общее число эскалаций
        (`escalations > 1` — не чистый) — `analyst,spec_auditor` получает
        «эскалаций 2, ожидаемая эскалация покрывает только одну»; либо
        `spec_auditor` не входит в допустимые роли.
        """
        for roles in ("analyst,spec_auditor", "analyst", "spec_auditor"):
            with self.subTest(roles=roles):
                row = run_row(roles)
                self.assertIsNone(models.unclean_reason(row))
                self.assertTrue(models.clean_run(row))

    def test_ac6_other_roles_and_repeats_are_unclean_naming_the_role(self):
        """Чужая роль, `unknown` или повтор роли — не чистый, причина называет роль и число.

        Ловит мутацию: счётчик ролей не различает повтор (вторая
        эскалация analyst принята) или причина называет общее число
        вместо роли — подстрока `эскалаций роли analyst: 2` не находится.
        """
        cases = (("analyst,developer", "эскалаций роли developer: 1"),
                 ("analyst,analyst", "эскалаций роли analyst: 2"),
                 ("analyst,spec_auditor,spec_auditor",
                  "эскалаций роли spec_auditor: 2"),
                 ("unknown", "эскалаций роли unknown: 1"),
                 ("analyst,test_author", "эскалаций роли test_author: 1"),
                 ("analyst,reviewer", "эскалаций роли reviewer: 1"))
        for roles, expected in cases:
            with self.subTest(roles=roles):
                row = run_row(roles)
                reason = models.unclean_reason(row)
                self.assertIsNotNone(reason)
                self.assertIn(expected, reason)
                self.assertFalse(models.clean_run(row))

    def test_ac7_other_uncleanness_conditions_keep_their_reasons(self):
        """При `analyst,spec_auditor` прочие условия чистоты работают как прежде.

        Вердикт не green — причина с «вердикт»; одна итерация ревью —
        «итераций ревью 1»; отказ автогейта по вине роли — «отказ
        автогейта, вина: роль»; отказ по вине пульта — чистый.

        Ловит мутацию: новая ветка ролей возвращает `None` раньше проверки
        отказа автогейта (отказ по вине роли не пачкает прогон) или
        перекрывает причину вердикта/итераций ревью своей.
        """
        role_refusals = [r for r in (
            models.AUTOGATE_REFUSAL_PREFIX + "критерии manual: AC-3",
            models.AUTOGATE_REFUSAL_PREFIX + "критерий ci не пройден")
            if models.autogate_refusal_blame(r) == models.BLAME_ROLE]
        pult_refusals = [r for r in (
            models.AUTOGATE_REFUSAL_PREFIX + "бюджет задачи исчерпан",
            models.AUTOGATE_REFUSAL_PREFIX + "каталог приёмочных тестов пуст")
            if models.autogate_refusal_blame(r) == models.BLAME_PULT]
        self.assertTrue(role_refusals and pult_refusals)

        reason = models.unclean_reason(
            run_row("analyst,spec_auditor", verdict="red"))
        self.assertTrue(reason and reason.startswith("вердикт"), reason)
        reason = models.unclean_reason(
            run_row("analyst,spec_auditor", review_iterations=1))
        self.assertIn("итераций ревью 1", reason or "")
        for refusal in role_refusals:
            with self.subTest(refusal=refusal):
                reason = models.unclean_reason(
                    run_row("analyst,spec_auditor", autogate_refusal=refusal))
                self.assertIn(f"отказ автогейта, вина: {models.BLAME_ROLE}",
                              reason or "")
        for refusal in pult_refusals:
            with self.subTest(refusal=refusal):
                self.assertIsNone(models.unclean_reason(
                    run_row("analyst,spec_auditor", autogate_refusal=refusal)))

    def test_ac8_without_expected_escalation_any_role_is_unclean(self):
        """Без выполненной ожидаемой эскалации и `spec_auditor`, и `analyst` — не чистые.

        Перебираются три способа не выполнить ожидание: маркера нет,
        ожидалось «без эскалации», маркер разошёлся с фактом.

        Ловит мутацию: правило ролей применяется без проверки
        `expected_escalation_met` — одиночная эскалация `spec_auditor` на
        шаблоне без ловушки засчитана чистой.
        """
        unmet = ({"expected_escalation": None},
                 {"expected_escalation": "no", "marker_mismatch": 1},
                 {"expected_escalation": "yes", "actual_escalation": 0,
                  "marker_mismatch": 1})
        for roles in ("spec_auditor", "analyst"):
            for overrides in unmet:
                with self.subTest(roles=roles, overrides=overrides):
                    row = run_row(roles, **overrides)
                    self.assertFalse(models.expected_escalation_met(row))
                    self.assertIsNotNone(models.unclean_reason(row))
                    self.assertFalse(models.clean_run(row))


class RowsWithoutRolesTest(unittest.TestCase):
    """Строки без данных о ролях — прежнее правило по общему числу."""

    OLD_REASON = "эскалаций 2, ожидаемая эскалация покрывает только одну"

    def test_ac9_null_and_missing_key_rows_keep_old_rule(self):
        """`escalation_roles = None` и строка-словарь без ключа — прежнее правило.

        Две эскалации при выполненной ожидаемой — не чистая с прежней
        причиной, одна — чистая; отсутствие ключа не роняет чтение.

        Ловит мутацию: `NULL` трактуется как пустой перечень (эскалаций
        ролей нет — чистый) или ключ читается `row["escalation_roles"]`
        без защиты — `KeyError` на строке-словаре без ключа.
        """
        null_row = lambda n: dict(run_row(None), escalations=n,
                                  escalation_roles=None)
        bare_row = lambda n: dict(run_row(None), escalations=n)
        for name, make in (("NULL", null_row), ("без ключа", bare_row)):
            with self.subTest(row=name):
                self.assertIn(self.OLD_REASON,
                              models.unclean_reason(make(2)) or "")
                self.assertIsNone(models.unclean_reason(make(1)))
                self.assertTrue(models.clean_run(make(1)))

    def test_ac9_migrated_database_keeps_old_rows_null_and_verdicts(self):
        """БД с `canary_runs` прежней схемы после миграции: у старых строк `NULL`, вердикт прежний.

        Держит связку «миграция `store` — чтение `all_canary_runs` —
        критерий `models`»: таблица заводится прежним DDL, строки — до
        миграции, затем запись новой строки через `store.insert_canary_run`
        мигрирует таблицу.

        Ловит мутацию: миграция заполняет колонку у прежних строк пустой
        строкой (`DEFAULT ''`) — прогон с двумя эскалациями перекрашивается
        в чистый задним числом; или колонка не добавляется миграцией вовсе.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "state.db"
        raw = sqlite3.connect(str(db))
        raw.execute(
            "CREATE TABLE canary_runs ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT, run_stamp TEXT, title TEXT,"
            "  task_id TEXT, steps INTEGER, cost_usd REAL, review_iterations INTEGER,"
            "  escalations INTEGER, outcome TEXT, expected_escalation TEXT,"
            "  actual_escalation INTEGER, marker_mismatch INTEGER, created_at TEXT,"
            "  main_sha TEXT, verdict TEXT, set_name TEXT, models_summary TEXT,"
            "  acceptance_route TEXT, autogate_refusal TEXT)")
        for task_id, escalations in (("01OLD2", 2), ("01OLD1", 1)):
            raw.execute(
                "INSERT INTO canary_runs (run_stamp, title, task_id, steps,"
                " cost_usd, review_iterations, escalations, outcome,"
                " expected_escalation, actual_escalation, marker_mismatch,"
                " verdict, set_name) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("20261001T000000Z", "canary-status-sort", task_id, 7, 1.0, 0,
                 escalations, "merge_gate", "yes", 1, 0, "green",
                 config.CANARY_DEFAULT_SET))
        raw.commit()
        raw.close()
        with mock.patch.object(config, "DB", db):
            conn = store.db()
            store.insert_canary_run(
                conn, "20261014T000000Z", "canary-status-sort", "01NEW", 7,
                1.0, 0, 1, "merge_gate", "yes", True, False, verdict="green")
            rows = {row["task_id"]: row for row in store.all_canary_runs(conn)}
            conn.close()
        self.assertIsNone(rows["01OLD2"]["escalation_roles"])
        self.assertIsNone(rows["01OLD1"]["escalation_roles"])
        self.assertIn(self.OLD_REASON,
                      models.unclean_reason(rows["01OLD2"]) or "")
        self.assertIsNone(models.unclean_reason(rows["01OLD1"]))


class PairAdmissionByRolesTest(unittest.TestCase):
    """Сводка `models.pair_admission` над строками `canary_runs` из БД."""

    ROLE = "developer"
    MODEL = "model-x"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(config, "DB", Path(tmp.name) / "state.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.conn = store.db()
        self.addCleanup(self.conn.close)

    def insert(self, stamp: str, title: str, roles: list) -> None:
        store.insert_canary_run(
            self.conn, stamp, title, f"01{stamp[-4:]}", 7, 1.0, 0, len(roles),
            "merge_gate", "yes", True, False, verdict="green",
            models_summary=f"{self.ROLE} → {self.MODEL}",
            escalation_roles=roles)

    def document(self, classes: dict) -> dict:
        return {models.SETS_KEY: {}, models.PAIRS_KEY: {},
                models.CANARY_TEMPLATES_KEY: dict(classes)}

    def test_ac10_summary_names_role_reason_and_counts_clean_run(self):
        """Строка прогона с `analyst,developer` — «не чистый — … developer: 1», AC-5 — «чистый».

        Чистый прогон засчитан в число чистых и закрывает условие среднего
        класса; тот же прогон на шаблоне быстрого класса условие среднего
        класса не закрывает.

        Ловит мутацию: `pair_admission` считает чистоту своей формулой по
        общему числу эскалаций, а не `unclean_reason` — прогон
        `analyst,spec_auditor` печатается «не чистый» и не засчитывается;
        или строка не чистого прогона печатает прежнюю причину без роли.
        """
        rng, seed = seeded_rng(self)
        dirty, clean = sorted(rng.sample(range(1000, 9999), 2))
        dirty_stamp = f"20261014T00{dirty}Z"
        clean_stamp = f"20261014T00{clean}Z"
        self.insert(dirty_stamp, "canary-a", ["analyst", "developer"])
        self.insert(clean_stamp, "canary-b", ["analyst", "spec_auditor"])

        lines, missing = models.pair_admission(
            self.conn, self.ROLE, self.MODEL,
            self.document({"canary-a": models.TEMPLATE_MEDIUM,
                           "canary-b": models.TEMPLATE_MEDIUM}))
        dirty_line = next(l for l in lines if dirty_stamp in l)
        clean_line = next(l for l in lines if clean_stamp in l)
        self.assertIn("не чистый —", dirty_line, f"зерно: {seed}")
        self.assertIn("эскалаций роли developer: 1", dirty_line)
        self.assertTrue(clean_line.endswith(": чистый"), clean_line)
        self.assertIn("чистых прогонов: 1 ", "\n".join(lines))
        if models.ADMIT_MIN_CLEAN_RUNS > 1:
            self.assertTrue(any(
                f"чистых прогонов 1 из {models.ADMIT_MIN_CLEAN_RUNS}" in m
                for m in missing), missing)
        self.assertFalse(any(models.TEMPLATE_MEDIUM in m and "нет чистого" in m
                             for m in missing), missing)

        _lines, missing = models.pair_admission(
            self.conn, self.ROLE, self.MODEL,
            self.document({"canary-a": models.TEMPLATE_MEDIUM,
                           "canary-b": models.TEMPLATE_FAST}))
        self.assertTrue(any(models.TEMPLATE_MEDIUM in m and "нет чистого" in m
                            for m in missing), missing)


if __name__ == "__main__":
    unittest.main()
