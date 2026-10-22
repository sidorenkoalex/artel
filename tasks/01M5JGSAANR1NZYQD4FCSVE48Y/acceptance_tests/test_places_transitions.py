"""Места задачи на выходе из `tests_writing` и `in_dev`: профиль компонента задачи (AC-22), отказ `for_task` трёх вариантов зон (AC-24) и исход строки таблицы (AC-9).

Группа: разовый
Красен до реализации: места зовут `decide(target)`, а у учебной записи из двух компонентов он отказывает «… исполняется после G1б» — у задачи на `frontend` вместо профиля `frontend` приходит отказ (или откат на область по умолчанию у `_external_helpers`), а у задачи с отказом `for_task` текст отказа не несёт ни одного из трёх текстов AC-3.

Предмет — закрытые функции мест таблицы «Места задачи и исход при отказе
`for_task`» (SPEC называет их по файлу и строке): сквозной выход из
`in_dev` гонит их все одним `advance`, и отказ первого места закрыл бы
остальные, поэтому место — отдельный прямой вызов. После мержа тот же
вызов теряет смысл как «место таблицы» — файл разовый.

Стенд — `_training.TrainingSandbox`: `targets.yaml` песочницы с артелью и
учебным проектом (`backend` — `junit-xml`/pytest, `frontend` —
`pult-vitest`, `depends_on` вида `files` на `backend/seed/`), задача —
строка БД с зонами варианта. Внешние источники подменены: git (`gitcmd`),
ссылка документов (`artifact_branch.ls_tree`), рабочая копия, прогон
планки (`acceptance.run`). Исход места читается одним текстом
(`_training.outcome_text`): возвращённое значение, вывод, `SystemExit`,
журнал задачи.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`decide_task`/`for_task` в `project_profile` и места этого файла на
`for_task` (у `_external_helpers` — отказ вместо отката) — все методы файла
зелёные.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _training import (REFUSAL_VARIANTS, TrainingSandbox,  # noqa: E402
                       check_variant_text, fake_tree, outcome_text, patch_all,
                       yielding)

from orchestrator import (acceptance, appendix_tree, artifact_branch,  # noqa: E402
                          fsm_advance, gitcmd, project_profile, store,
                          workspace)
from orchestrator.advance_gates import acceptance as acceptance_gates  # noqa: E402
from orchestrator.advance_gates import outcome_integrity  # noqa: E402
from orchestrator.advance_gates import review as review_gates  # noqa: E402
from orchestrator.advance_gates import test_integrity  # noqa: E402
from orchestrator.advance_gates import zones as zones_gates  # noqa: E402

ARTIFACT = "refs/artifacts/T"
BASE = "basesha"
LOCKED = "locksha"
HEAD = "headsha"
NO_CLAIM = "def test_new():\n    assert True\n"
ALPHA = ("import unittest\n\n\nclass AlphaTest(unittest.TestCase):\n\n"
         "    def test_one(self):\n        pass\n")
MUTATION_ACTION = "переход отклонён: гейт заявки мутации"
ZONES_ACTION = "переход отклонён: гейт зон"
RED_PLANK_ACTION = "переход отклонён: приёмочные тесты"


class Stop(Exception):
    """Остановка сценария после наблюдения места."""


class PlacesSandbox(TrainingSandbox):

    # --- выход из tests_writing (fsm_advance.py:519) --------------------

    def run_tests_writing(self, t):
        return outcome_text(fsm_advance.tests_writing, self.conn, t.id,
                            self.row(t), self.root / "tdir", t.target,
                            "tests_writing")

    # --- заявка мутации (advance_gates/review.py:209) -------------------

    def mutation(self, t, files):
        def show(ref, path, repo=None):
            return (None, "новый файл") if ref == BASE else (NO_CLAIM, "")
        with patch_all(mock.patch.object(gitcmd, "diff_base", return_value=BASE),
                       mock.patch.object(gitcmd, "diff_names", return_value=files),
                       mock.patch.object(gitcmd, "show", show)):
            return outcome_text(review_gates._mutation_claim_gate, self.conn,
                                t.id, self.row(t), t.branch)

    # --- гейт текста (test_integrity.py:1756, :1299) --------------------

    def git_patches(self, deleted):
        sources = {(BASE, path): ALPHA for path in deleted}

        def show(ref, rel, repo=None):
            if (ref, rel) in sources:
                return sources[(ref, rel)], ""
            return None, "файла нет в этой ветке"

        def git(*args):
            return subprocess.CompletedProcess(args, 0, "\n", "")
        return patch_all(
            mock.patch.object(gitcmd, "diff_base", return_value=BASE),
            mock.patch.object(gitcmd, "diff_name_status",
                              return_value=[("D", p, None) for p in deleted]),
            mock.patch.object(gitcmd, "show", show),
            mock.patch.object(gitcmd, "ls_tree_files", return_value=[]),
            mock.patch.object(gitcmd, "branch_head_sha", return_value=HEAD),
            mock.patch.object(gitcmd, "git", git))

    def text_gate(self, t, deleted):
        with self.git_patches(deleted):
            return outcome_text(test_integrity._test_integrity_gate, self.conn,
                                t.id, self.row(t), ARTIFACT)

    # --- гейт зон (advance_gates/zones.py:287) --------------------------

    def zones_gate(self, t, files):
        status = subprocess.CompletedProcess([], 1, "", "нет рабочей копии")
        with patch_all(
                mock.patch.object(gitcmd, "diff_base", return_value=BASE),
                mock.patch.object(gitcmd, "diff_names", return_value=files),
                mock.patch.object(gitcmd, "diff_base_source",
                                  return_value="origin/main"),
                mock.patch.object(gitcmd, "in_repo", return_value=status),
                mock.patch.object(artifact_branch, "ls_tree", return_value=[]),
                mock.patch.object(gitcmd, "ls_tree_files", return_value=[]),
                mock.patch.object(gitcmd, "show",
                                  return_value=(None, "нет файла"))):
            return outcome_text(zones_gates._zones_gate, self.conn, t.id,
                                self.row(t), ARTIFACT, "")

    # --- перечень долгоживущих (advance_gates/acceptance.py:73, :111) ----

    def manifest(self, t, listed_path: str):
        store.update_task(self.conn, t.id, tests_locked_sha=LOCKED)
        digest = "a" * 64
        manifest_text = f"{digest}  {listed_path}\n"
        seen_dirs = []

        def ls_tree(ref, rel, repo=None):
            if ref == LOCKED:
                return [rel]
            seen_dirs.append(rel)
            return [listed_path] if listed_path.startswith(rel + "/") else []
        with patch_all(
                mock.patch.object(gitcmd, "ls_tree_files", ls_tree),
                mock.patch.object(gitcmd, "show",
                                  return_value=(manifest_text, "")),
                mock.patch.object(gitcmd, "branch_head_sha", return_value=HEAD),
                mock.patch.object(acceptance_gates, "blob_sha256",
                                  return_value=digest)):
            value, text = outcome_text(
                acceptance_gates._long_lived_manifest_refuses, self.conn, t.id)
        return value, text, seen_dirs

    # --- прогон приёмки (advance_gates/acceptance.py:561) ---------------

    def acceptance_run(self, t):
        calls = []
        wt = self.root / "wt"
        wt.mkdir(exist_ok=True)

        def run(tdir, **kwargs):
            calls.append(kwargs)
            return False, "красная планка сценария"
        with patch_all(
                mock.patch.object(workspace, "ensure", return_value=(wt, None)),
                mock.patch.object(workspace, "on_task_branch", return_value=True),
                mock.patch.object(appendix_tree, "suite_tree",
                                  lambda *a, **k: yielding(fake_tree(wt))),
                mock.patch.object(acceptance, "plank_in_code_copy",
                                  lambda *a, **k: yielding(wt)),
                mock.patch.object(acceptance, "plank_present", return_value=True),
                mock.patch.object(acceptance, "run", run)):
            value, text = outcome_text(
                acceptance_gates._acceptance_run_refuses, self.conn, t.id,
                self.row(t), self.root / "tdir", t.target, ARTIFACT)
        return value, text, calls

    def all_text(self, t, text: str) -> str:
        return f"{text}\n{self.journal_text(t)}"


# ===================================================================== AC-22

class Ac22TransitionPlacesTest(PlacesSandbox):

    def test_ac22_tests_writing_exit_takes_frontend_profile(self):
        """Выход из `tests_writing` задачи на `frontend` идёт дальше с профилем `frontend`, без отказа профиля.

        Сценарий: кодовая ветка «есть», чтение диффа кодовой ветки
        (`_tests_writing_code_diff`) — шпион, запоминающий профиль и
        останавливающий сценарий.

        Ловит мутацию: выход оставлен на `decide(target)` — запись
        «переход отклонён: профиль тестов проекта» и останов до чтения
        диффа; профиль задачи взят не того компонента (`backend`).
        """
        t = self.task("frontend", "tests_writing")
        seen = []

        def code_diff(task_id, branch, profile):
            seen.append(profile)
            raise Stop()
        with patch_all(mock.patch.object(gitcmd, "branch_exists", return_value=True),
                       mock.patch.object(fsm_advance, "_tests_writing_code_diff",
                                         code_diff)):
            _value, text = self.run_tests_writing(t)
        self.assertEqual(self.details(t, project_profile.REFUSAL_ACTION), [],
                         self.note(text))
        self.assertEqual(len(seen), 1, self.note(text))
        self.assertEqual(seen[0].component, "frontend", self.note())

    def test_ac22_mutation_claim_by_frontend_scope(self):
        """Заявка мутации задачи на `frontend` судит файлы области `mutation_claim_scope` компонента `frontend`.

        Сценарий: дифф добавляет тесты без заявки в `frontend/claims/`,
        `backend/tests/` и `tests/`. Отказ гейта заявки называет только
        файл области `frontend`.

        Ловит мутацию: гейт на `decide(target)` — отказ профиля вместо
        гейта заявки; область — `backend` или артельная `tests/test_*.py`.
        """
        t = self.task("frontend")
        files = ["frontend/claims/test_a.py", "backend/tests/test_b.py",
                 "tests/test_c.py"]
        value, text = self.mutation(t, files)
        self.assertEqual(getattr(value, "action", None), MUTATION_ACTION,
                         self.note(text))
        self.assertIn("frontend/claims/test_a.py: test_new", value.detail)
        self.assertNotIn("backend/tests/test_b.py", value.detail)
        self.assertNotIn("tests/test_c.py:", value.detail)

    def test_ac22_text_gate_by_frontend_scope(self):
        """Гейт текста задачи на `frontend` судит удаления в `weakening_scope` компонента `frontend`.

        Сценарий: удалены тестовые файлы `frontend/src/test_alpha.py` и
        `backend/tests/test_beta.py`. Отказ гейта неослабления тестов
        называет только первый.

        Ловит мутацию: гейт на `decide(target)` — отказ профиля; область
        гейта — `backend` или артельная `tests/**/*.py`.
        """
        t = self.task("frontend")
        value, text = self.text_gate(
            t, ["frontend/src/test_alpha.py", "backend/tests/test_beta.py"])
        self.assertEqual(getattr(value, "action", None),
                         test_integrity.TEST_INTEGRITY_REFUSAL_ACTION,
                         self.note(text))
        self.assertIn("frontend/src/test_alpha.py: удалён", value.detail)
        self.assertNotIn("backend/tests/test_beta.py", value.detail)

    def test_ac22_external_helpers_scope_of_frontend(self):
        """Область помощников гейта текста задачи на `frontend` — `in_weakening_scope` компонента `frontend`, не область по умолчанию.

        Сценарий: `_external_helpers` задачи на `frontend`; предикат области
        принимает `frontend/src/…` и не принимает артельную
        `tests/test_x.py` и `backend/tests/…`; `workdir` — компонента.

        Ловит мутацию: `_external_helpers` на `decide(target)` — откат на
        область по умолчанию (`tests/**/*.py`) с пустым `workdir`.
        """
        t = self.task("frontend")
        helpers = test_integrity._external_helpers(self.conn, t.id, None)
        self.assertIsNotNone(helpers, self.note())
        frontend = self.profile_of("frontend")
        self.assertEqual(helpers.workdir, frontend.workdir, self.note())
        self.assertTrue(helpers.scope("frontend/src/ui/helper.py"), self.note())
        self.assertFalse(helpers.scope("tests/test_x.py"), self.note())
        self.assertFalse(helpers.scope("backend/tests/helper.py"), self.note())

    def test_ac22_zones_gate_exempts_frontend_long_lived(self):
        """Гейт зон задачи на `frontend` освобождает долгоживущий файл по шаблону `frontend`, файл по правилу `backend` остаётся вне зон.

        Сценарий: зоны — `frontend/src/App.jsx`; дифф — сама зона,
        долгоживущий файл `frontend/src/ui/btn.<id>.test.jsx` и файл
        `backend/tests/test_<id>_x.py`. Отказ гейта зон называет только
        файл `backend` и не несёт причины профиля.

        Ловит мутацию: гейт на `decide(target)` — оба файла вне зон и
        хвост «свои долгоживущие файлы задачи зоной не признаны»;
        освобождение по шаблону `backend`.
        """
        t = self.task("frontend")
        own = f"frontend/src/ui/btn.{t.low}.test.jsx"
        foreign = f"backend/tests/test_{t.low}_x.py"
        value, text = self.zones_gate(t, ["frontend/src/App.jsx", own, foreign])
        self.assertEqual(getattr(value, "action", None), ZONES_ACTION,
                         self.note(text))
        self.assertIn(foreign, value.detail)
        self.assertNotIn(own, value.detail)
        self.assertNotIn("зоной не признаны", value.detail)

    def test_ac22_manifest_reads_frontend_long_lived_dir(self):
        """Перечень долгоживущих задачи на `frontend` сверяется по каталогу долгоживущих `frontend`.

        Сценарий: лок с перечнем из одного файла
        `frontend/src/ui/btn.<id>.test.jsx`; дерево головы несёт его под
        каталогом `frontend/src` с той же суммой. Сверка проходит (нет
        отказа), каталог головы читался — `frontend/src`.

        Ловит мутацию: `long_lived_manifest`/`_long_lived_manifest_refuses`
        на `decide(target)` — отказ «долгоживущие файлы задачи не сверены
        …» с причиной профиля; каталог `backend/tests` — файл «удалён».
        """
        t = self.task("frontend")
        value, text, dirs = self.manifest(t, f"frontend/src/ui/btn.{t.low}.test.jsx")
        self.assertIs(value, False, self.note(text))
        self.assertEqual(self.details(t, acceptance_gates.LONG_LIVED_MANIFEST_ACTION),
                         [], self.note(text))
        self.assertIn("frontend/src", dirs, self.note(str(dirs)))

    def test_ac22_acceptance_run_with_frontend_channel(self):
        """Прогон приёмки на выходе из `in_dev` задачи на `frontend` идёт каналом профиля `frontend` с записями прогона.

        Сценарий: рабочая копия, дерево приложений и выкладка планки
        подменены; `acceptance.run` — шпион, возвращающий красный исход.
        Аргумент `command` прогона — профиль компонента `frontend`,
        аргумент `records` есть (компонент в границе); итог — отказ
        «приёмочные тесты», не отказ профиля.

        Ловит мутацию: прогон на `decide(target)` — запись отказа профиля
        и прогона нет; канал — команда пульта без профиля.
        """
        t = self.task("frontend")
        value, text, calls = self.acceptance_run(t)
        self.assertEqual(self.details(t, project_profile.REFUSAL_ACTION), [],
                         self.note(text))
        self.assertEqual(len(calls), 1, self.note(text))
        command = calls[0].get("command")
        self.assertEqual(getattr(command, "component", None), "frontend",
                         self.note(repr(calls)))
        self.assertIn("records", calls[0], self.note(repr(calls)))
        self.assertTrue(self.details(t, RED_PLANK_ACTION), self.note(text))


# ===================================================================== AC-24

class Ac24TransitionRefusalsTest(PlacesSandbox):
    """Три варианта отказа `for_task` на каждом месте выхода: текст AC-3
    своего варианта в исходе места."""

    def test_ac24_tests_writing_exit(self):
        """Выход из `tests_writing` у задачи с отказом `for_task` отказывает текстом AC-3 своего варианта.

        Ловит мутацию: выход на `decide(target)` — отказ несёт «…
        исполняется после G1б», не текст варианта зон.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant, "tests_writing")
                _value, text = self.run_tests_writing(t)
                check_variant_text(self, self.all_text(t, text), variant,
                                   self.note("tests_writing"))

    def test_ac24_mutation_claim(self):
        """Гейт заявки мутации у задачи с отказом `for_task` отказывает текстом AC-3 своего варианта.

        Ловит мутацию: гейт на `decide(target)` — текст «… после G1б».
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                _value, text = self.mutation(t, ["frontend/claims/test_a.py"])
                check_variant_text(self, text, variant, self.note("заявка мутации"))

    def test_ac24_text_gate(self):
        """Гейт текста у задачи с отказом `for_task` отказывает текстом AC-3 своего варианта.

        Ловит мутацию: гейт на `decide(target)` — текст «… после G1б».
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                _value, text = self.text_gate(t, ["frontend/src/test_alpha.py"])
                check_variant_text(self, text, variant, self.note("гейт текста"))

    def test_ac24_external_helpers_entries(self):
        """Область помощников у задачи с отказом `for_task` не откатывается на область по умолчанию: вход пакета ревьювера и гейта мержа несут текст AC-3.

        Сценарий: удалён артельный по виду файл `tests/test_x.py` (в
        области по умолчанию). Вход `review_lines` и вход гейта мержа
        `merge_gate_escalates` — исход каждого (значение, вывод, журнал)
        несёт текст отказа варианта.

        Ловит мутацию: `_external_helpers` молча откатывается на область
        по умолчанию (`:1300–1301`) — исход без текста отказа, находка по
        `tests/test_x.py` как у артели.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                with self.git_patches(["tests/test_x.py"]):
                    _v, review_text = outcome_text(
                        test_integrity.review_lines, self.conn, t.id, t.branch,
                        ARTIFACT)
                check_variant_text(self, review_text, variant,
                                   self.note("review_lines"))
                with self.git_patches(["tests/test_x.py"]):
                    _v, merge_text = outcome_text(
                        test_integrity.merge_gate_escalates, self.conn, t.id,
                        "merge_gate", t.branch, ARTIFACT)
                check_variant_text(self, self.all_text(t, merge_text), variant,
                                   self.note("merge_gate_escalates"))

    def test_ac24_zones_gate(self):
        """Гейт зон у задачи с отказом `for_task` и файлом вне зон называет текст AC-3 своего варианта.

        Сценарий: варианты «оба компонента» и «вне компонентов» (у
        варианта «зоны не заданы» гейт зон не звонится вовсе — исход
        строки таблицы «при файлах вне зон» к нему неприменим: файлов вне
        заявленных зон без зон нет); дифф — долгоживущий файл `frontend` и
        файл вне зон.

        Ловит мутацию: гейт на `decide(target)` — хвост отказа с «… после
        G1б».
        """
        for variant in ("both", "outside"):
            with self.subTest(variant=variant):
                t = self.task(variant)
                _value, text = self.zones_gate(
                    t, [f"frontend/src/ui/btn.{t.low}.test.jsx", "other/x.py"])
                check_variant_text(self, text, variant, self.note("гейт зон"))

    def test_ac24_long_lived_manifest(self):
        """Перечень долгоживущих у залоченной задачи с отказом `for_task` отказывает текстом AC-3 своего варианта.

        Ловит мутацию: `long_lived_manifest` на `decide(target)` — причина
        «… после G1б».
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                _value, text, _dirs = self.manifest(
                    t, f"frontend/src/ui/btn.{t.low}.test.jsx")
                check_variant_text(self, self.all_text(t, text), variant,
                                   self.note("перечень долгоживущих"))

    def test_ac24_acceptance_run(self):
        """Прогон приёмки у задачи с отказом `for_task` отказывает текстом AC-3 своего варианта.

        Ловит мутацию: прогон на `decide(target)` — текст «… после G1б».
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                _value, text, _calls = self.acceptance_run(t)
                check_variant_text(self, self.all_text(t, text), variant,
                                   self.note("прогон приёмки"))

    def test_ac24_outcome_gate_in_dev(self):
        """Гейт исходов на выходе из `in_dev` у задачи с отказом `for_task` — отказ с текстом AC-3 своего варианта, не молчаливый пропуск.

        Ловит мутацию: `_bounds` на `decide(target)` — отказ превращается
        в `None` (гейта нет, пропуск молча).
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                t = self.task(variant)
                value, text = outcome_text(
                    outcome_integrity._outcome_integrity_gate, self.conn, t.id,
                    self.row(t), ARTIFACT)
                self.assertIsNotNone(value, self.note("гейт исходов молчит"))
                check_variant_text(self, self.all_text(t, text), variant,
                                   self.note("гейт исходов"))


# ===================================================================== AC-9

class Ac9TransitionOutcomesTest(PlacesSandbox):
    """Исход строки таблицы у мест выхода: переход отклонён своим
    действием, задача не сдвинулась, эскалации нет."""

    def test_ac9_transition_places_refuse_by_table(self):
        """Места выхода из `tests_writing`/`in_dev` у задачи с зонами вне компонентов отказывают действием своей строки таблицы.

        Сценарий: вариант «зоны вне компонентов». Выход из `tests_writing`,
        заявка мутации, прогон приёмки — `REFUSAL_ACTION`; гейт текста —
        отказ; перечень долгоживущих — `LONG_LIVED_MANIFEST_ACTION`; гейт
        исходов — отказ (не `None`). Состояние задачи прежнее, причина
        отказа — текст `for_task`.

        Ловит мутацию: место превращает отказ `for_task` в пропуск —
        `None`/`False` без записи; гейт исходов молчит (`_bounds` даёт
        `None`); перечень пишет пропуск `journal_skip` вместо отказа.
        """
        t = self.task("outside", "tests_writing")
        value, text = self.run_tests_writing(t)
        self.assertIs(value, False, self.note(text))
        self.assertTrue(self.details(t, project_profile.REFUSAL_ACTION), self.note(text))
        self.assertEqual(self.row(t)["state"], "tests_writing")
        t = self.task("outside")
        value, text = self.mutation(t, ["frontend/claims/test_a.py"])
        self.assertEqual(getattr(value, "action", None),
                         project_profile.REFUSAL_ACTION, self.note(text))
        value, text = self.text_gate(t, ["frontend/src/test_alpha.py"])
        self.assertIsNotNone(getattr(value, "action", None), self.note(text))
        value, text, _dirs = self.manifest(t, f"frontend/src/a.{t.low}.test.jsx")
        self.assertIs(value, True, self.note(text))
        self.assertTrue(self.details(t, acceptance_gates.LONG_LIVED_MANIFEST_ACTION),
                        self.note(text))
        value, text, calls = self.acceptance_run(t)
        self.assertIs(value, True, self.note(text))
        self.assertEqual(calls, [], self.note("прогон при отказе"))
        self.assertTrue(self.details(t, project_profile.REFUSAL_ACTION), self.note(text))
        value, text = outcome_text(outcome_integrity._outcome_integrity_gate,
                                   self.conn, t.id, self.row(t), ARTIFACT)
        self.assertIsNotNone(getattr(value, "action", None), self.note(text))
        self.assertEqual(self.row(t)["state"], "in_dev", self.note())


if __name__ == "__main__":
    unittest.main()
