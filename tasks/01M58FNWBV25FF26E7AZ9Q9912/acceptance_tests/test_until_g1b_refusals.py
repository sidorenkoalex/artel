"""Отказы до G1б/G2б: запись с несколькими компонентами у читателей профиля, `_task_own_profile`, единственный компонент без пары долгоживущих полей.

Группа: разовый
Красен до реализации: запись с `components:` сегодня — ABSENT (поле не читается): `profile_of` не даёт UNREAD с признаком `multi`, `decide` отвечает пропуском, `full_suite_limit` — пределом `config`, `suite_run._profile_command` — отказом «нет профиля» без причины G1б, `acceptance_suite` зовёт `full_suite`, а проверка записи не знает требований к единственному компоненту (`long_lived` без пары, нет `long_lived_dir`/`long_lived_name`) и пропускает такие записи.

Почему разовый: поведение этого файла временное по плану волны ADR-0026 —
отказ «запись проекта с несколькими компонентами исполняется после G1б»
снимает G1б, отказ «long_lived исполняется после G2б» — G2б; кроме того
критерии называют закрытые имена (`suite_run._profile_command`,
`acceptance._task_own_profile`, уборка выкладки `acceptance._drop_layout`),
которые долгоживущему файлу недоступны.

Песочница — `tests.sandbox.SchemaConnTmpRootTest` (пути `config` во
временном каталоге, схема БД, `self.conn`): задача заводится строкой
`store.insert_task` с проектом сценария, `targets.yaml` песочницы пишется
текстом и читается `targets.load`. `acceptance.full_suite` подменён — его
вызов и аргументы и есть наблюдаемое; рабочая копия кода — каталог во
временном корне песочницы.
"""
import random
import string
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, ci, config, project_profile,
                          repo_context, store, suite_run, targets)
from tests.sandbox import ARTEL_TEST_PROFILE, SchemaConnTmpRootTest

G1B = "запись проекта с несколькими компонентами исполняется после G1б"
G2B = "long_lived исполняется после G2б"
ARTEL = config.DEFAULT_TARGET

HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

TWO_COMPONENTS = r"""    components:
      backend:
        command: [cargo, test]
        weakening_scope: [backend/**/*.rs]
        mutation_claim_scope: [backend/tests/*.rs]
        paths: [^backend/]
        long_lived: backend/tests/test_<id>_<name>.rs
      frontend:
        command: [npx, vitest, run]
        weakening_scope: [frontend/**/*.ts]
        mutation_claim_scope: [frontend/**/*.test.ts]
        paths: ^frontend/
        long_lived: frontend/tests/test_<id>_<name>.test.ts
        depends_on:
          backend:
            via: files
            paths: [^backend/api/]
"""


class RefusalSandbox(SchemaConnTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def word(self, size: int = 7) -> str:
        return "".join(self.rng.choice(string.ascii_lowercase)
                       for _ in range(size))

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def write(self, *entries: str) -> None:
        config.TARGETS.write_text("targets:\n" + "".join(entries),
                                  encoding="utf-8")

    def artel(self) -> str:
        return HEAD.format(name=ARTEL) + ARTEL_TEST_PROFILE

    def multi_project(self) -> str:
        name = f"p{self.word()}"
        self.write(self.artel(), HEAD.format(name=name) + TWO_COMPONENTS)
        return name

    def task(self, target: str) -> str:
        task_id = f"T{self.rng.randrange(10**8)}"
        store.insert_task(self.conn, task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}-x", target, 10.0)
        return task_id

    def code_copy(self, task_id: str) -> Path:
        """Рабочая копия кода во временном корне песочницы с выкладкой
        `tasks/<id>/` (не `config.ROOT` — его `drop_from_code_copy` не
        трогает)."""
        code = self.root / f"code-{self.word()}"
        docs = code / "tasks" / task_id
        docs.mkdir(parents=True)
        (docs / "PLAN.md").write_text("выкладка\n", encoding="utf-8")
        return code


# ------------------------------------------------------------------ AC-8

class MultiComponentReadersTest(RefusalSandbox):

    def test_ac8_readers_refuse_multi_component_record(self):
        """Все читатели профиля отказывают записи с двумя компонентами причиной G1б.

        Сценарий: в `targets.yaml` песочницы — артель и проект со случайным
        именем, у которого `components:` несёт `backend` и `frontend`; задача
        этого проекта в БД. `profile_of` — UNREAD с `multi` истинным и
        причиной G1б; `decide` и `for_task` — `Decision` без профиля и без
        пропуска, отказ с текстом «запись проекта с несколькими
        компонентами исполняется после G1б»; `full_suite_limit` —
        `TargetsError` с тем же текстом (не предел `config`);
        `suite_run._profile_command` — команды нет, отказ с тем же текстом.

        Ловит мутацию: `profile_of` отдаёт запись с несколькими компонентами
        как ABSENT — `decide` даёт пропуск, `full_suite_limit` — предел
        `config`, `_profile_command` — «нет профиля»; либо `profile_of`
        отдаёт PRESENT первого компонента — `decide` даёт профиль; либо
        `multi` не выставлен.
        """
        target = self.multi_project()
        task_id = self.task(target)
        answer = repo_context.profile_of(target)
        self.assertEqual(answer.outcome, repo_context.PROFILE_UNREAD,
                         self.note())
        self.assertIs(answer.multi, True, self.note())
        self.assertIn(G1B, answer.reason, self.note())
        for label, decision in (
                ("decide", project_profile.decide(target)),
                ("for_task", project_profile.for_task(self.conn, task_id))):
            with self.subTest(reader=label, seed=self.seed):
                self.assertIsNone(decision.profile, self.note(label))
                self.assertEqual(decision.skip, "", self.note(label))
                self.assertIn(G1B, decision.refusal, self.note(label))
        with self.subTest(reader="full_suite_limit", seed=self.seed):
            with self.assertRaises(targets.TargetsError,
                                   msg=self.note("предел вместо отказа")) as caught:
                project_profile.full_suite_limit(target)
            self.assertIn(G1B, str(caught.exception), self.note())
        with self.subTest(reader="suite_run._profile_command", seed=self.seed):
            command, refusal = suite_run._profile_command(target)
            self.assertIsNone(command, self.note())
            self.assertIn(G1B, refusal, self.note())


# ------------------------------------------------------------------ AC-9

class TaskOwnProfileRefusalTest(RefusalSandbox):

    def run_suite(self, target: str, fresh: bool):
        """`acceptance_suite` задачи проекта `target` с подменённым
        `full_suite` (итога CI нет: голова ветки не прочитана)."""
        task_id = self.task(target)
        root = self.root / f"tree-{self.word()}"
        root.mkdir()
        full = mock.Mock(return_value=mock.sentinel.result)
        with mock.patch.object(acceptance, "full_suite", full), \
                mock.patch.object(ci, "head_sha",
                                  lambda branch, repo=None: ("", "нет CI")):
            try:
                result = acceptance.acceptance_suite(
                    self.conn, root, task_id, f"task/{task_id.lower()}-x",
                    self.root, actor="test", fresh=fresh)
                error = None
            except Exception as exc:  # наблюдаемое — исход вызова
                result, error = None, exc
        return task_id, root, full, result, error

    def test_ac9_acceptance_suite_refuses_multi(self):
        """`acceptance_suite` на записи с двумя компонентами не зовёт `full_suite` и бросает `TargetsError` с причиной G1б.

        Сценарий: задача проекта, чья запись несёт два компонента;
        `acceptance_suite` со свежим прогоном и без (итога CI нет).
        `full_suite` не вызван ни разу; исключение — `targets.TargetsError`
        с текстом «запись проекта с несколькими компонентами исполняется
        после G1б».

        Ловит мутацию: `_task_own_profile` на UNREAD с `multi` по-прежнему
        возвращает `None` — полный набор идёт прежней формой пульта
        (`full_suite` вызван); либо отказ бросается иным исключением
        (`RuntimeError`/`ValueError`) вместо `TargetsError`.
        """
        target = self.multi_project()
        for fresh in (True, False):
            with self.subTest(fresh=fresh, seed=self.seed):
                _, _, full, _, error = self.run_suite(target, fresh)
                full.assert_not_called()
                self.assertIsInstance(error, targets.TargetsError,
                                      self.note(repr(error)))
                self.assertIn(G1B, str(error), self.note())

    def test_ac9_acceptance_suite_unchanged_other_outcomes(self):
        """UNREAD без `multi`, ABSENT и PRESENT `pult-pytest` — прежний вызов `full_suite` без `command`.

        Сценарий: три записи проекта задачи по очереди — `test_profile` без
        `command` (UNREAD, `multi` ложен), запись без профиля (ABSENT),
        `test_profile` без `runner` (PRESENT `pult-pytest`). `acceptance_suite`
        со свежим прогоном и без: исключения нет, `full_suite` вызван ровно
        раз прежней формой — `(root, task_id, fresh=True)` либо
        `(root, task_id)`, без `command`; итог — его возврат.

        Ловит мутацию: отказ `_task_own_profile` наступает на любом UNREAD
        (не только с `multi`) — битый `test_profile` перестаёт идти прежней
        формой; либо `pult-pytest` получает `command=`.
        """
        name = f"p{self.word()}"
        profile = ("    test_profile:\n"
                   "      long_lived_dir: tests\n"
                   "      long_lived_name: test_<id>_<name>.py\n"
                   "      weakening_scope: [tests/**/*.py]\n"
                   "      mutation_claim_scope: [tests/test_*.py]\n")
        records = {
            "UNREAD без multi": profile,
            "ABSENT": "",
            "PRESENT pult-pytest": profile.replace(
                "    test_profile:\n",
                "    test_profile:\n      command: [python3, -m, pytest]\n"),
        }
        for label, extra in records.items():
            self.write(self.artel(), HEAD.format(name=name) + extra)
            for fresh in (True, False):
                with self.subTest(case=label, fresh=fresh, seed=self.seed):
                    task_id, root, full, result, error = self.run_suite(
                        name, fresh)
                    self.assertIsNone(error, self.note(repr(error)))
                    expected = (mock.call(root, task_id, fresh=True) if fresh
                                else mock.call(root, task_id))
                    self.assertEqual(full.call_args_list, [expected],
                                     self.note(label))
                    self.assertIs(result, mock.sentinel.result, self.note())

    def test_ac9_drop_from_code_copy_on_multi(self):
        """`drop_from_code_copy` на записи с двумя компонентами убирает выкладку задачи, не зовёт уборку выкладки планки и не бросает исключения.

        Сценарий: задача проекта с двумя компонентами; в рабочей копии кода
        лежит выкладка `tasks/<id>/`. `drop_from_code_copy` завершается без
        исключения, каталога `tasks/<id>/` нет, подменённая
        `acceptance._drop_layout` не вызвана.

        Ловит мутацию: `drop_from_code_copy` не перехватывает отказ
        `_task_own_profile` с признаком `multi` — `TargetsError` выходит
        наружу; либо уборка `tasks/<id>/` переставлена после вызова
        `_task_own_profile` и не происходит; либо на отказе всё же зовётся
        уборка выкладки.
        """
        target = self.multi_project()
        task_id = self.task(target)
        code = self.code_copy(task_id)
        with mock.patch.object(acceptance, "_drop_layout") as drop:
            acceptance.drop_from_code_copy(task_id, code)
        self.assertFalse((code / "tasks" / task_id).exists(), self.note())
        drop.assert_not_called()

    def test_ac9_drop_from_code_copy_catch_is_narrow(self):
        """Иные исключения `_task_own_profile` и исключение самой уборки выкладки выходят из `drop_from_code_copy`.

        Сценарий: (1) `_task_own_profile` подменён и бросает
        `TargetsError` без признака `multi` (текст без причины G1б), затем
        `RuntimeError` — каждое выходит из `drop_from_code_copy` тем же
        объектом; (2) запись проекта задачи — `test_profile` с `runner:
        pytest-own`, `workdir` и `long_lived_dir` внутри него (выкладка
        планки под `long_lived_dir`), `_drop_layout` подменён и бросает
        `OSError` — оно выходит наружу.

        Ловит мутацию: перехват шире отказа — `except targets.TargetsError`
        или `except Exception` вокруг `_task_own_profile` и уборки выкладки
        глотает чужие исключения, и `drop_from_code_copy` молча
        возвращается.
        """
        target = self.multi_project()
        task_id = self.task(target)
        for exc in (targets.TargetsError(f"сломано {self.word()}"),
                    RuntimeError(f"сбой {self.word()}")):
            with self.subTest(exc=type(exc).__name__, seed=self.seed):
                code = self.code_copy(task_id)
                with mock.patch.object(acceptance, "_task_own_profile",
                                       side_effect=exc), \
                        self.assertRaises(type(exc)) as caught:
                    acceptance.drop_from_code_copy(task_id, code)
                self.assertIs(caught.exception, exc, self.note())
        own = f"p{self.word()}"
        workdir = f"w{self.word()}"
        self.write(self.artel(), HEAD.format(name=own) + (
            f"    test_profile:\n"
            f"      command: [python3, -m, pytest]\n"
            f"      long_lived_dir: {workdir}/tests\n"
            f"      long_lived_name: test_<id>_<name>.py\n"
            f"      weakening_scope: [{workdir}/tests/**/*.py]\n"
            f"      mutation_claim_scope: [{workdir}/tests/test_*.py]\n"
            f"      runner: pytest-own\n"
            f"      workdir: {workdir}\n"))
        own_task = self.task(own)
        code = self.code_copy(own_task)
        boom = OSError(f"уборка {self.word()}")
        with self.subTest(case="уборка выкладки бросает", seed=self.seed):
            with mock.patch.object(acceptance, "_drop_layout",
                                   side_effect=boom) as drop, \
                    self.assertRaises(OSError) as caught:
                acceptance.drop_from_code_copy(own_task, code)
            self.assertIs(caught.exception, boom, self.note())
            drop.assert_called_once()


# ------------------------------------------------------------------ AC-10

class SingleComponentLongLivedTest(RefusalSandbox):

    def single(self, name: str, comp: str, fields: str) -> str:
        return HEAD.format(name=name) + (
            f"    components:\n      {comp}:\n"
            f"        command: [python3, -m, pytest]\n"
            f"        weakening_scope: [tests/**/*.py]\n"
            f"        mutation_claim_scope: [tests/test_*.py]\n" + fields)

    def test_ac10_single_component_long_lived_refusals(self):
        """Единственный компонент без пары `long_lived_dir`/`long_lived_name` получает отказ формы; читатели отвечают отказом, не исключением.

        Сценарий: проект со случайным именем и единственным компонентом
        со случайным именем: (1) `long_lived: "tests/test_<id>_x.py"` без
        пары — `targets.load` отказывает текстом «long_lived исполняется
        после G2б», называющим компонент; (2) нет `long_lived_dir` (и нет
        `long_lived`) — отказ называет компонент и `long_lived_dir`; (3) то
        же для `long_lived_name`. На каждой записи `profile_of` — UNREAD с
        `multi` ложным, `decide` возвращает `Decision` с отказом и без
        профиля.

        Ловит мутацию: правило «единственный компонент обязан нести пару»
        не введено — запись проходит, `profile_of` даёт PRESENT, а `decide`
        падает `KeyError` в `Profile.from_values`; либо отказ `long_lived`
        без пары не называет причину G2б или компонент; либо `profile_of`
        выставляет `multi` на негодной записи.
        """
        name, comp = f"p{self.word()}", f"k{self.word()}"
        cases = (
            ("long_lived без пары",
             '        long_lived: "tests/test_<id>_x.py"\n', (comp, G2B)),
            ("нет long_lived_dir",
             "        long_lived_name: test_<id>_<name>.py\n",
             (comp, "long_lived_dir")),
            ("нет long_lived_name", "        long_lived_dir: tests\n",
             (comp, "long_lived_name")),
        )
        for label, fields, parts in cases:
            with self.subTest(case=label, seed=self.seed):
                self.write(self.artel(), self.single(name, comp, fields))
                with self.assertRaises(targets.TargetsError,
                                       msg=self.note(label)) as caught:
                    targets.load()
                text = str(caught.exception).replace(str(config.TARGETS), "")
                for part in parts:
                    self.assertIn(part, text, self.note(label))
                answer = repo_context.profile_of(name)
                self.assertEqual(answer.outcome, repo_context.PROFILE_UNREAD,
                                 self.note(label))
                self.assertIs(answer.multi, False, self.note(label))
                decision = project_profile.decide(name)
                self.assertIsNone(decision.profile, self.note(label))
                self.assertTrue(decision.refusal, self.note(label))

    def test_ac10_two_components_long_lived_without_pair_pass(self):
        """Запись с двумя компонентами, у которых `long_lived` без пары, проходит проверку записи.

        Сценарий: артель и проект со случайным именем, у которого
        `components:` несёт `backend` и `frontend` с `long_lived` и без
        `long_lived_dir`/`long_lived_name`. `targets.load` не отказывает и
        возвращает оба `long_lived`.

        Ловит мутацию: требование пары `long_lived_dir`/`long_lived_name`
        применено к каждому компоненту, а не только к единственному, —
        `targets.load` отказывает.
        """
        target = self.multi_project()
        comps = targets.load()[target]["components"]
        self.assertEqual(comps["backend"]["long_lived"],
                         "backend/tests/test_<id>_<name>.rs", self.note())
        self.assertNotIn("long_lived_dir", comps["frontend"], self.note())


if __name__ == "__main__":
    unittest.main()
