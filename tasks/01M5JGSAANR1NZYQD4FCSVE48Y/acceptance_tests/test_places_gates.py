"""Места гейта мержа, пакета ревьювера, автогейта и прогонов в контексте задачи: профиль компонента задачи (AC-7, AC-8, AC-11, AC-12, AC-22), отказ `for_task` трёх вариантов зон (AC-24) и исход строки таблицы (AC-9).

Группа: разовый
Красен до реализации: места зовут `decide(target)`/`profile_of(target)`/`full_suite_limit(target)` — у учебной записи из двух компонентов они отказывают («… исполняется после G1б») либо поднимают `ComponentsPending`/`TargetsError`: у задачи на `frontend` нет профиля `frontend` (пакет ревьювера не собирается, мерж отказывает, `checks_local` не исполняются, предел полного набора — исключение), а у задачи с отказом `for_task` исход не несёт текстов AC-3 (`_test_integrity_diff_gate` и `acceptance_suite` молча пропускают проверку).

Предмет — закрытые функции мест таблицы «Места задачи и исход при отказе
`for_task`» (SPEC называет их по файлу и строке): сквозной `approve` гейта
мержа и приёмки требует CI, форджа и полного набора, которых в песочнице
нет, а отказ первого места закрыл бы остальные. Файл разовый: после мержа
прямой вызов места теряет смысл «места таблицы».

Стенд — `_training.TrainingSandbox` (учебный проект `backend`/`frontend`,
строки задач с зонами варианта). Подменены внешние источники: git,
рабочая копия, прогон полного набора (`acceptance.run_full_suite`),
итог CI (`_acceptance_suite_run`), запуск автогейта
(`_maybe_autogate_acceptance`), узел гейта текста на мерже.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`decide_task`/`for_task`, места файла на `for_task`, `ComponentsPending`
только при отказе `for_task`, отказ вместо пропуска `checks_local` и
гейта текста на мерже, граница автогейта по компоненту задачи — все
методы файла зелёные.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _training import (BACKEND_FIELDS, FRONTEND_CHECK,  # noqa: E402
                       FRONTEND_FIELDS, FRONTEND_LIMIT, REFUSAL_VARIANTS,
                       TrainingSandbox, check_variant_text, fake_tree,
                       outcome_text, patch_all, single_entry, training_entry,
                       yielding)

from orchestrator import (acceptance, appendix_tree, artifact_source,  # noqa: E402
                          config, fsm_advance, fsm_autogate, fsm_merge_gate,
                          gitcmd, project_profile, repo_context, review, store,
                          suite_run, targets, workspace)
from orchestrator.advance_gates import outcome_integrity  # noqa: E402
from orchestrator.advance_gates import test_integrity  # noqa: E402

ARTIFACT = "refs/artifacts/T"
BASE = "basesha"
HEAD = "headsha"
ALPHA = ("import unittest\n\n\nclass AlphaTest(unittest.TestCase):\n\n"
         "    def test_one(self):\n        self.assertEqual(len('ab'), 2)\n")
ALPHA_WEAK = ("import unittest\n\n\nclass AlphaTest(unittest.TestCase):\n\n"
              "    def test_one(self):\n        self.assertTrue(len('ab'))\n")
AUTOGATE_SKIPPED = "автогейт приёмки пропущен"
G3B_TEXT = "до гейта неослабления по исходам (G3б) не исполняется"
GREEN = acceptance.FullSuiteRun(True, acceptance.FULL_SUITE_GREEN,
                                "полный набор зелёный", None,
                                "полный набор зелёный")


class Stop(Exception):
    """Остановка сценария после наблюдения места."""


class GatesSandbox(TrainingSandbox):

    def ctx(self, t):
        return repo_context.resolve(t.target)

    # --- гейт мержа ------------------------------------------------------

    def profile_exit(self, t):
        return outcome_text(fsm_merge_gate._profile_refusal_exit, self.conn,
                            t.id, t.target)

    def merge_text_gate(self, t):
        seen = []

        def escalates(conn, task_id, state, branch, artifact, scope=None):
            seen.append(scope)
            return False
        with patch_all(
                mock.patch.object(artifact_source, "resolve",
                                  return_value=(ARTIFACT, False)),
                mock.patch.object(fsm_merge_gate, "merge_gate_escalates",
                                  escalates)):
            value, text = outcome_text(fsm_merge_gate._test_integrity_diff_gate,
                                       self.conn, t.id, "merge_gate", t.branch,
                                       self.ctx(t))
        return value, text, seen

    def merge_locks(self, t):
        seen = []

        def manifest(conn, task_id):
            seen.append(task_id)
            return False
        with patch_all(
                mock.patch.object(artifact_source, "resolve",
                                  return_value=(ARTIFACT, False)),
                mock.patch.object(fsm_merge_gate, "_acceptance_lock_refuses",
                                  return_value=False),
                mock.patch.object(fsm_merge_gate, "_long_lived_manifest_refuses",
                                  manifest)):
            value, text = outcome_text(fsm_merge_gate._acceptance_locks_refuse,
                                       self.conn, t.id)
        return value, text, seen

    def merge_outcome(self, t):
        return outcome_text(outcome_integrity.merge_gate_escalates, self.conn,
                            t.id, "merge_gate", lambda: "mainsha")

    # --- пакет ревьювера -------------------------------------------------

    def package_exit(self, t):
        return outcome_text(review._exit_without_profile, self.conn, t.id,
                            t.target)

    def package_section(self, t, changed):
        """Раздел пакета: у файлов `changed` утверждение метода ослаблено
        (`assertEqual` на базе → `assertTrue` на голове)."""
        def show(ref, rel, repo=None):
            if rel in changed:
                return (ALPHA if ref == BASE else ALPHA_WEAK), ""
            return None, "файла нет в этой ветке"
        with patch_all(
                mock.patch.object(gitcmd, "diff_base", return_value=BASE),
                mock.patch.object(gitcmd, "diff_name_status",
                                  return_value=[("M", p, None) for p in changed]),
                mock.patch.object(gitcmd, "show", show),
                mock.patch.object(gitcmd, "ls_tree_files", return_value=[]),
                mock.patch.object(gitcmd, "branch_head_sha", return_value=HEAD),
                mock.patch.object(gitcmd, "git", lambda *a: subprocess.CompletedProcess(
                    a, 0, "\n", ""))):
            return outcome_text(review._changed_assertions_part, self.conn,
                                t.id, t.branch, ARTIFACT, t.target, "run")

    # --- автогейт --------------------------------------------------------

    def review_approved(self, t):
        store.set_state(self.conn, t.id, "review", "test",
                        expected_state=self.row(t)["state"], detail="сценарий")
        seen = []
        wt = self.root / "wt"
        wt.mkdir(exist_ok=True)
        with patch_all(
                mock.patch.object(workspace, "ensure", return_value=(wt, None)),
                mock.patch.object(acceptance, "plank_in_code_copy",
                                  lambda *a, **k: yielding(wt)),
                mock.patch.object(fsm_autogate, "_maybe_autogate_acceptance",
                                  lambda *a, **k: seen.append(a))):
            value, text = outcome_text(
                fsm_advance._review_approved, self.conn, t.id, self.row(t),
                self.root / "tdir", t.target, "review", ARTIFACT, "", {})
        return value, text, seen

    def plank_rule_refusal(self, t, target=None):
        rule = project_profile.plank_rule(target or t.target)
        return outcome_text(fsm_autogate._plank_rule_refusal, rule, self.row(t))

    # --- прогоны ---------------------------------------------------------

    def acceptance_suite(self, t):
        seen = []

        def checks(profile, root):
            seen.append(profile)
            if profile is None or not getattr(profile, "checks_local", ()):
                return True, ""
            return True, f"checks_local компонента {profile.component} — код 0"
        with patch_all(
                mock.patch.object(acceptance, "_acceptance_suite_run",
                                  return_value=GREEN),
                mock.patch.object(acceptance, "run_checks_local", checks)):
            value, text = outcome_text(acceptance.acceptance_suite, self.conn,
                                       self.root, t.id, t.branch, self.root,
                                       actor="operator")
        return value, text, seen

    def full_suite(self, t, command=None):
        seen = []

        def run(root, **kwargs):
            seen.append(kwargs)
            return True, "1 passed in 0.01s"
        root = self.root / "suite"
        root.mkdir(exist_ok=True)
        with patch_all(
                mock.patch.object(acceptance, "run_full_suite", run),
                mock.patch.object(acceptance, "suite_tree_hash", return_value=None)):
            value, text = outcome_text(acceptance.full_suite, root, t.id,
                                       command=command)
        return value, text, seen

    def suite_run(self, t):
        seen = []
        wt = self.root / "wt"
        wt.mkdir(exist_ok=True)

        def run(root, **kwargs):
            seen.append(kwargs)
            raise Stop()
        with patch_all(
                mock.patch.object(appendix_tree, "suite_tree",
                                  lambda *a, **k: yielding(fake_tree(wt))),
                mock.patch.object(acceptance, "run_full_suite", run)):
            value, text = outcome_text(suite_run._run, t.id, 1,
                                       suite_run.MODE_FULL,
                                       self.root / "suite.log")
        return value, text, seen

    def all_text(self, t, text: str) -> str:
        return f"{text}\n{self.journal_text(t)}"


# ===================================================================== AC-22

class Ac22GatePlacesTest(GatesSandbox):

    def test_ac22_merge_profile_refusal_exit_passes(self):
        """`_profile_refusal_exit` гейта мержа у задачи на `frontend` не отказывает.

        Ловит мутацию: место на `decide(target)` — `SystemExit` «merge
        отклонён: … после G1б» и запись `MERGE_PROFILE_REFUSAL_ACTION`.
        """
        t = self.task("frontend", "merge_gate")
        value, text = self.profile_exit(t)
        self.assertIsNone(value, self.note(text))
        self.assertEqual(self.details(t, fsm_merge_gate.MERGE_PROFILE_REFUSAL_ACTION),
                         [], self.note(text))

    def test_ac22_merge_text_gate_by_frontend_scope(self):
        """Гейт текста на мерже задачи на `frontend` зовёт узел гейта с областью `weakening_scope` компонента `frontend`.

        Ловит мутацию: место на `decide(target)` — узел не зовётся
        (молчаливый `False`); область — `backend` или артельная.
        """
        t = self.task("frontend", "merge_gate")
        _value, text, seen = self.merge_text_gate(t)
        self.assertEqual(len(seen), 1, self.note(text))
        scope = seen[0]
        self.assertTrue(scope("frontend/src/test_a.py"), self.note())
        self.assertFalse(scope("backend/tests/test_a.py"), self.note())
        self.assertFalse(scope("tests/test_a.py"), self.note())

    def test_ac22_merge_long_lived_checked(self):
        """Перечень долгоживущих на гейте мержа задачи на `frontend` сверяется, отказа профиля нет.

        Ловит мутацию: `_acceptance_locks_refuse` получает отказ
        `for_task` без зон — `MERGE_PROFILE_REFUSAL_ACTION` и `True` без
        сверки перечня.
        """
        t = self.task("frontend", "merge_gate")
        value, text, seen = self.merge_locks(t)
        self.assertIs(value, False, self.note(text))
        self.assertEqual(seen, [t.id], self.note(text))
        self.assertEqual(self.details(t, fsm_merge_gate.MERGE_PROFILE_REFUSAL_ACTION),
                         [], self.note(text))

    def test_ac22_review_package_exit_and_section(self):
        """Пакет ревьювера задачи на `frontend` собирается: выхода без профиля нет, раздел изменённых утверждений — по области `frontend` со строками гейта исходов.

        Сценарий: в `frontend/src/test_alpha.py` и
        `backend/tests/test_beta.py` ослаблено утверждение метода. Раздел
        называет первый, не называет второй, несёт строку гейта исходов
        для головы (компонент в границе).

        Ловит мутацию: `_exit_without_profile` на `decide(target)` —
        `SystemExit` «ревью-пакет не собран»; раздел на `decide(target)` —
        «Раздел не собран: …»; область раздела — `backend`.
        """
        t = self.task("frontend", "review")
        value, text = self.package_exit(t)
        self.assertIsNone(value, self.note(text))
        self.assertEqual(self.details(t, review.PACKAGE_REFUSED_ACTION), [],
                         self.note(text))
        value, text = self.package_section(
            t, ["frontend/src/test_alpha.py", "backend/tests/test_beta.py"])
        self.assertIsInstance(value, str, self.note(text))
        self.assertNotIn("Раздел не собран", value, self.note(text))
        self.assertIn("frontend/src/test_alpha.py", value, self.note(text))
        self.assertNotIn("backend/tests/test_beta.py", value, self.note(text))
        self.assertIn("гейт исходов", value, self.note(text))

    def test_ac22_autogate_after_review_runs(self):
        """Автогейт после ревью задачи на `frontend` проводится: записи «автогейт приёмки пропущен» нет, автогейт зван.

        Ловит мутацию: место на `decide(target)` — запись пропуска
        автогейта с причиной профиля, решение уходит Оператору.
        """
        t = self.task("frontend", "verifying")
        _value, text, seen = self.review_approved(t)
        self.assertEqual(self.details(t, AUTOGATE_SKIPPED), [], self.note(text))
        self.assertEqual(len(seen), 1, self.note(text))

    def test_ac22_autogate_plank_rule_in_bounds(self):
        """Автогейт по правилу планки у задачи на `frontend` (в границе, не канарейка) отказа «до G3б» не даёт.

        Ловит мутацию: `_plank_rule_refusal` через `_bounds(…, target)` на
        `decide(target)` — отказ «… (G3б) не исполняется …».
        """
        t = self.task("frontend", "acceptance")
        value, text = self.plank_rule_refusal(t)
        self.assertIsNone(value, self.note(text))

    def test_ac22_acceptance_suite_checks_local_of_frontend(self):
        """`approve` приёмки (узел `acceptance_suite`) у задачи на `frontend` исполняет `checks_local` компонента `frontend`.

        Ловит мутацию: `_task_profile` поднимает `ComponentsPending`, его
        перехват даёт `profile=None` — `checks_local` не исполняются.
        """
        t = self.task("frontend", "acceptance")
        _value, text, seen = self.acceptance_suite(t)
        self.assertEqual(len(seen), 1, self.note(text))
        self.assertEqual(getattr(seen[0], "component", None), "frontend",
                         self.note(text))
        self.assertEqual(tuple(seen[0].checks_local), tuple(FRONTEND_CHECK))

    def test_ac22_full_suite_limit_of_frontend(self):
        """Предел `acceptance.full_suite` в контексте задачи на `frontend` — `component_limit` компонента `frontend`.

        Сценарий: прогон без команды (`command=None`): `run_full_suite`
        получает предел `full_suite_timeout_sec` компонента `frontend`.

        Ловит мутацию: предел через `full_suite_limit(target)` —
        `TargetsError` у записи из нескольких компонентов.
        """
        t = self.task("frontend", "acceptance")
        _value, text, seen = self.full_suite(t)
        self.assertEqual(len(seen), 1, self.note(text))
        self.assertEqual(seen[0].get("limit", (None,))[0], FRONTEND_LIMIT,
                         self.note(repr(seen)))

    def test_ac22_task_profile_places_and_cleanup(self):
        """Места прогона `_task_profile`/`_task_own_profile` дают профиль `frontend`; уборка выкладки убирает каталог `<plank_layout>` компонента.

        Ловит мутацию: места на `profile_of(target)` — `ComponentsPending`;
        уборка, перехватив его, оставляет выкладку `frontend/src/.pv/<id>`.
        """
        t = self.task("frontend")
        self.assertEqual(acceptance._task_profile(self.conn, t.id).component,
                         "frontend", self.note())
        self.assertEqual(acceptance._task_own_profile(self.conn, t.id).component,
                         "frontend", self.note())
        code = self.clone
        laid = code / "frontend" / "src" / ".pv" / t.id
        laid.mkdir(parents=True)
        (laid / "p.test.jsx").write_text("// выкладка\n", encoding="utf-8")
        acceptance.drop_from_code_copy(t.id, code)
        self.assertFalse(laid.exists(), self.note("выкладка не убрана"))

    def test_ac22_suite_run_command_and_limit(self):
        """`suite-run <id>` задачи на `frontend` гонит каналом профиля `frontend` с его пределом.

        Ловит мутацию: `_profile_command(target)`/`full_suite_limit(target)`
        — отказ «suite-run №1: отказ — … не прочитан» без прогона.
        """
        t = self.task("frontend", "in_dev")
        _value, text, seen = self.suite_run(t)
        self.assertEqual(len(seen), 1, self.note(text))
        self.assertEqual(getattr(seen[0].get("command"), "component", None),
                         "frontend", self.note(repr(seen)))
        self.assertEqual(seen[0].get("limit", (None,))[0], FRONTEND_LIMIT,
                         self.note(repr(seen)))


# ===================================================================== AC-24

class Ac24GateRefusalsTest(GatesSandbox):

    def each(self, state, fn, where, journal=True):
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant, state)
                result = fn(t)
                text = result[1]
                if journal:
                    text = self.all_text(t, text)
                check_variant_text(self, text, variant, self.note(where))

    def test_ac24_merge_profile_refusal_exit(self):
        """`_profile_refusal_exit` у задачи с отказом `for_task` отказывает текстом AC-3 своего варианта.

        Ловит мутацию: место на `decide(target)` — текст «… после G1б».
        """
        self.each("merge_gate", self.profile_exit, "_profile_refusal_exit")

    def test_ac24_merge_text_gate(self):
        """Гейт текста на мерже у задачи с отказом `for_task` — отказ (не пропуск) с текстом AC-3.

        Ловит мутацию: `decision.profile is None` при отказе — молчаливый
        `False` без записи и без текста.
        """
        self.each("merge_gate", self.merge_text_gate, "гейт текста на мерже")

    def test_ac24_merge_long_lived(self):
        """Перечень долгоживущих на гейте мержа у задачи с отказом `for_task` отказывает текстом AC-3.

        Ловит мутацию: `for_task` без зон — прежний текст «… после G1б».
        """
        self.each("merge_gate", self.merge_locks, "_acceptance_locks_refuse")

    def test_ac24_merge_outcome_gate(self):
        """Гейт исходов на мерже у задачи с отказом `for_task` — отказ с текстом AC-3, не молчаливый пропуск.

        Ловит мутацию: `_bounds` на `decide(target)` — `False` без записи
        (мерж без гейта исходов).
        """
        self.each("merge_gate", self.merge_outcome, "гейт исходов на мерже")

    def test_ac24_review_package(self):
        """Пакет ревьювера у задачи с отказом `for_task` не собирается: выход `_exit_without_profile` и раздел пакета несут текст AC-3.

        Ловит мутацию: место на `decide(target)` — текст «… после G1б».
        """
        self.each("review", self.package_exit, "_exit_without_profile")
        self.each("review", lambda t: self.package_section(
            t, ["frontend/src/test_alpha.py"]), "раздел пакета")

    def test_ac24_autogate_after_review(self):
        """Автогейт после ревью у задачи с отказом `for_task` не проводится, запись пропуска несёт текст AC-3.

        Ловит мутацию: место на `decide(target)` — причина «… после G1б».
        """
        self.each("verifying", self.review_approved, "автогейт после ревью")

    def test_ac24_autogate_plank_rule(self):
        """Автогейт по правилу планки у задачи с отказом `for_task` отказывает текстом AC-3.

        Ловит мутацию: граница по `_bounds(…, target)` — причина «…
        (G3б) не исполняется» без текста `for_task`.
        """
        self.each("acceptance", self.plank_rule_refusal, "правило планки",
                  journal=False)

    def test_ac24_acceptance_suite(self):
        """`acceptance_suite` у задачи с отказом `for_task` — отказ с текстом AC-3, не зелёный итог без `checks_local`.

        Ловит мутацию: перехват `ComponentsPending` оставлен — итог CI
        зелёный, `checks_local` молча не исполняются.
        """
        self.each("acceptance", self.acceptance_suite, "acceptance_suite")

    def test_ac24_full_suite(self):
        """Полный набор в контексте задачи с отказом `for_task` — отказ с текстом AC-3.

        Ловит мутацию: предел через `full_suite_limit(target)` —
        `TargetsError` «… после G1б» без текста варианта.
        """
        self.each("acceptance", self.full_suite, "full_suite")

    def test_ac24_task_profile_places(self):
        """`_task_profile`/`_task_own_profile` у задачи с отказом `for_task` поднимают `ComponentsPending` с текстом AC-3; уборка выкладки — прежний выход без исключения.

        Ловит мутацию: `ComponentsPending` с причиной `profile_of` («…
        после G1б»); уборка роняет исключение.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                for fn in (acceptance._task_profile, acceptance._task_own_profile):
                    with self.assertRaises(targets.ComponentsPending) as got:
                        fn(self.conn, t.id)
                    check_variant_text(self, str(got.exception), variant,
                                       self.note(fn.__name__))
                code = self.root / "code"
                code.mkdir(exist_ok=True)
                acceptance.drop_from_code_copy(t.id, code)

    def test_ac24_suite_run(self):
        """`suite-run <id>` у задачи с отказом `for_task` отказывает строкой «suite-run №N: отказ — <текст AC-3>».

        Ловит мутацию: `_profile_command(target)` — причина «… после
        G1б».
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                value, text, seen = self.suite_run(t)
                self.assertEqual(seen, [], self.note("прогон при отказе"))
                line = value[0] if isinstance(value, tuple) else text
                self.assertIn(f"[{t.id}] suite-run №1: отказ — ", line, self.note(text))
                check_variant_text(self, line, variant, self.note("suite-run"))


# ===================================================================== AC-9

class Ac9GateOutcomesTest(GatesSandbox):

    def test_ac9_gate_places_refuse_by_table(self):
        """Места гейта мержа, пакета, автогейта и прогонов у задачи с зонами вне компонентов дают исход своей строки таблицы.

        Сценарий: вариант «зоны вне компонентов». `_profile_refusal_exit` —
        `SystemExit` и `MERGE_PROFILE_REFUSAL_ACTION`, задача на
        `merge_gate`; `_acceptance_locks_refuse` — `True` и та же запись;
        пакет — `SystemExit` и `PACKAGE_REFUSED_ACTION`; автогейт после
        ревью — запись «автогейт приёмки пропущен»; `acceptance_suite` —
        итог не зелёный; `suite-run` — строка отказа и `False`. Нигде нет
        эскалации.

        Ловит мутацию: отказ превращён в пропуск — нет записи, итог
        зелёный, `None`/`False` без текста; место эскалирует задачу.
        """
        t = self.task("outside", "merge_gate")
        value, text = self.profile_exit(t)
        self.assertIsInstance(value, SystemExit, self.note(text))
        self.assertTrue(self.details(t, fsm_merge_gate.MERGE_PROFILE_REFUSAL_ACTION))
        value, text, _seen = self.merge_locks(t)
        self.assertIs(value, True, self.note(text))
        self.assertEqual(self.row(t)["state"], "merge_gate")
        t = self.task("outside", "review")
        value, text = self.package_exit(t)
        self.assertIsInstance(value, SystemExit, self.note(text))
        self.assertTrue(self.details(t, review.PACKAGE_REFUSED_ACTION), self.note(text))
        t = self.task("outside", "verifying")
        self.review_approved(t)
        self.assertTrue(self.details(t, AUTOGATE_SKIPPED), self.note())
        t = self.task("outside", "acceptance")
        value, text, _seen = self.acceptance_suite(t)
        self.assertFalse(getattr(value, "green", False), self.note(text))
        value, text, _seen = self.suite_run(t)
        self.assertIsInstance(value, tuple, self.note(text))
        self.assertIs(value[1], False, self.note(text))
        rows = self.conn.execute(
            "SELECT id FROM tasks WHERE target=? AND state='escalated'",
            (self.project,)).fetchall()
        self.assertEqual(rows, [], self.note("эскалация места"))


# ===================================================================== AC-7

class Ac7RunPlacesTest(GatesSandbox):

    def test_ac7_task_profile_is_task_component(self):
        """`_task_profile` и `_task_own_profile` задачи с одним компонентом записи из нескольких компонентов — профиль этого компонента.

        Сценарий: задачи на `frontend` и на `backend`; поле `component` и
        `checks_local`/предел — компонента задачи.

        Ловит мутацию: `ComponentsPending` у записи из нескольких
        компонентов при любых зонах; профиль первого компонента записи
        вместо компонента задачи.
        """
        for variant, comp in (("frontend", "frontend"), ("backend", "backend")):
            t = self.task(variant)
            got = acceptance._task_profile(self.conn, t.id)
            self.assertEqual(got.component, comp, self.note(variant))
            self.assertEqual(acceptance._task_own_profile(self.conn, t.id).component,
                             comp, self.note(variant))
            self.assertEqual(got.full_suite_timeout_sec,
                             self.profile_of(comp).full_suite_timeout_sec)

    def test_ac7_components_pending_only_for_multi_refusal(self):
        """`ComponentsPending` — только при отказе `for_task` у записи из нескольких компонентов; у прочих отказ — `None`, `conn=None` — прежний путь артели.

        Сценарий: задача с отказом `for_task` (зоны вне компонентов) —
        `ComponentsPending`; задача проекта без записи в `targets.yaml` и
        задача записи из одного компонента без обязательного подполя —
        `None`; `conn=None` — профиль артели, как `decide(artel)`.

        Ловит мутацию: `ComponentsPending` поднимается и у прочих отказов
        (неразрешённый контекст, непрочитанный единственный компонент);
        `conn=None` идёт в `for_task` и падает.
        """
        t = self.task("outside")
        with self.assertRaises(targets.ComponentsPending):
            acceptance._task_profile(self.conn, t.id)
        missing = self.task("frontend", target=f"x{self.project}")
        self.assertIsNone(acceptance._task_profile(self.conn, missing.id))
        broken_fields = {k: v for k, v in FRONTEND_FIELDS.items()
                         if k != "mutation_claim_scope"}
        name = f"one{self.project}"
        self.append_entry(single_entry(name, "frontend", broken_fields))
        broken = self.task("frontend", target=name)
        self.assertTrue(project_profile.decide(name).refusal, self.note())
        self.assertIsNone(acceptance._task_profile(self.conn, broken.id))
        self.assertIsNone(acceptance._task_own_profile(self.conn, broken.id))
        artel = project_profile.decide(config.DEFAULT_TARGET).profile
        self.assertEqual(acceptance._task_profile(None, t.id), artel)

    def test_ac7_cleanup_removes_component_layout(self):
        """Уборка выкладки у задачи на `backend` убирает каталог `<plank_layout>` компонента `backend`, не трогая каталог `frontend`.

        Ловит мутацию: уборка перехватывает `ComponentsPending` и
        возвращается — выкладка `backend/tests/.pb/<id>` остаётся; уборка
        по первому компоненту записи вместо компонента задачи.
        """
        t = self.task("backend")
        code = self.clone
        own = code / "backend" / "tests" / ".pb" / t.id
        other = code / "frontend" / "src" / ".pv" / t.id
        for laid in (own, other):
            laid.mkdir(parents=True)
            (laid / "file.txt").write_text("выкладка\n", encoding="utf-8")
        acceptance.drop_from_code_copy(t.id, code)
        self.assertFalse(own.exists(), self.note("выкладка backend не убрана"))
        self.assertTrue(other.exists(), self.note("убрана чужая выкладка"))


# ===================================================================== AC-8

class Ac8AcceptanceSuiteTest(GatesSandbox):

    def test_ac8_checks_local_of_task_component(self):
        """`acceptance_suite` задачи на `frontend` исполняет `checks_local` компонента `frontend` и пишет запись `checks_local компонента`.

        Ловит мутацию: перехват `ComponentsPending` даёт `profile=None` —
        проверка не исполняется, записи нет.
        """
        t = self.task("frontend", "acceptance")
        value, text, seen = self.acceptance_suite(t)
        self.assertEqual([getattr(p, "component", None) for p in seen],
                         ["frontend"], self.note(text))
        self.assertTrue(self.details(t, acceptance.CHECKS_LOCAL_ACTION), self.note(text))
        self.assertTrue(getattr(value, "green", False), self.note(text))

    def test_ac8_refusal_is_not_silent(self):
        """`acceptance_suite` при отказе `for_task` — не зелёный итог с текстом отказа, не тихий пропуск `checks_local`.

        Сценарий: три варианта отказа; итог CI подменён зелёным. Итог —
        не зелёный (или исключение), текст исхода несёт текст AC-3.

        Ловит мутацию: перехват `ComponentsPending` в `acceptance_suite`
        оставлен — зелёный итог CI без `checks_local` и без причины.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant, "acceptance")
                value, text, _seen = self.acceptance_suite(t)
                self.assertFalse(getattr(value, "green", False), self.note(text))
                check_variant_text(self, self.all_text(t, text), variant,
                                   self.note("acceptance_suite"))


# ===================================================================== AC-11

class Ac11AutogateBoundsTest(GatesSandbox):

    def test_ac11_bounds_by_task_component_and_canary(self):
        """Граница автогейта по правилу планки у записи из нескольких компонентов — компонент задачи в `in_outcome_bounds` и не канарейка.

        Сценарий: учебный проект; второй вариант проекта, где у `backend`
        нет `report` (вне границы). Задача на `frontend` — без отказа;
        канарейка на `frontend` — отказ «до G3б»; задача на `backend` вне
        границы — отказ «до G3б».

        Ловит мутацию: признак канарейки не читается — канарейка проходит;
        граница по любому компоненту записи — задача на `backend` вне
        границы проходит.
        """
        t = self.task("frontend", "acceptance")
        self.assertIsNone(self.plank_rule_refusal(t)[0], self.note())
        canary = self.task("frontend", "acceptance", canary=True)
        value, text = self.plank_rule_refusal(canary)
        self.assertIsInstance(value, str, self.note(text))
        self.assertIn(G3B_TEXT, value)
        name = f"nr{self.project}"
        no_report = {k: v for k, v in BACKEND_FIELDS.items()
                     if k not in ("report", "failure_errors", "plank_layout")}
        self.append_entry(training_entry(name, backend=no_report))
        back = self.task("backend", "acceptance", target=name)
        value, text = self.plank_rule_refusal(back)
        self.assertIsInstance(value, str, self.note(text))
        self.assertIn(G3B_TEXT, value)

    def test_ac11_other_records_keep_prior_result_on_bare_row(self):
        """У записи из одного компонента, `test_profile` и артели `_plank_rule_refusal(rule, t)` со строкой без зон и id даёт прежний исход.

        Сценарий: запись из одного `pult-vitest` компонента (в границе) —
        `None`, та же запись канарейкой — отказ «до G3б» с именем
        компонента; артель — правило по умолчанию, `None`. Строка задачи —
        словарь только с `target` и `is_canary`.

        Ловит мутацию: граница у прочих записей идёт через `for_task` по
        строке — `KeyError` на строке без `id`/зон.
        """
        name = f"one{self.project}"
        self.append_entry(single_entry(name, "web", FRONTEND_FIELDS))
        rule = project_profile.plank_rule(name)
        self.assertIsNone(fsm_autogate._plank_rule_refusal(
            rule, {"target": name, "is_canary": 0}))
        self.assertEqual(
            fsm_autogate._plank_rule_refusal(rule, {"target": name, "is_canary": 1}),
            f"автогейт: прогон планки компонента web по правилу — до гейта "
            f"неослабления по исходам (G3б) не исполняется; приёмку решает "
            f"Оператор")
        artel_rule = project_profile.plank_rule(config.DEFAULT_TARGET)
        self.assertIsNone(fsm_autogate._plank_rule_refusal(
            artel_rule, {"target": config.DEFAULT_TARGET, "is_canary": 0}))


# ===================================================================== AC-12

class Ac12SuiteLimitTest(GatesSandbox):

    def test_ac12_task_context_limit_is_task_component(self):
        """Предел полного набора в контексте задачи — `component_limit` компонента задачи: `suite-run <id>` и `acceptance.full_suite`.

        Сценарий: задачи на `frontend` и на `backend` — пределы разные
        (`full_suite_timeout_sec` компонентов).

        Ловит мутацию: предел по `full_suite_limit(target)` (`TargetsError`)
        или по первому компоненту записи — у задачи на `frontend` предел
        `backend`.
        """
        for variant in ("frontend", "backend"):
            t = self.task(variant, "in_dev")
            expected = project_profile.component_limit(self.profile_of(variant))
            _value, text, seen = self.suite_run(t)
            self.assertEqual(len(seen), 1, self.note(text))
            self.assertEqual(seen[0]["limit"][0], expected[0], self.note(variant))
            _value, text, seen = self.full_suite(t)
            self.assertEqual(len(seen), 1, self.note(text))
            self.assertEqual(seen[0]["limit"][0], expected[0], self.note(variant))

    def test_ac12_merge_full_set_by_branch_diff(self):
        """Полный набор на мерже — компоненты `_selected_components` по диффу ветки, без сужения до компонента задачи.

        Сценарий: задача на `frontend`, дифф ветки задевает
        `backend/seed/` и `frontend/src/` — выбраны оба компонента в
        порядке записи.

        Ловит мутацию: полный набор мержа сужен до компонента задачи
        (`for_task`) — только `frontend`.
        """
        t = self.task("frontend", "merge_gate")
        with patch_all(
                mock.patch.object(gitcmd, "diff_base", return_value=BASE),
                mock.patch.object(gitcmd, "diff_names",
                                  return_value=["backend/seed/data.py",
                                                "frontend/src/App.jsx"])):
            got = fsm_merge_gate._selected_components(self.conn, t.id, [],
                                                      self.ctx(t))
        self.assertEqual([p.component for p in got], ["backend", "frontend"])


if __name__ == "__main__":
    unittest.main()
