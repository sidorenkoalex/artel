"""Мандат тестов, данный `answer` на гейте SPEC, — сквозь approve, reject и автокоммит аналитика до рубежей неослабления (AC-1, AC-6, AC-7).

Группа: долгоживущий
Красен до реализации: на `spec_gate` `answer` отказывает общим отказом «answer доступна только для задачи в состоянии escalated» — ANSWER с мандатом не создаётся, поэтому нет записи журнала мандата и approve после него (AC-1), а рубеж неослабления находит ослабление без мандата (AC-6); AC-7 держит сегодняшнее поведение (указание без строки мандата мандата не даёт) и зелен с рождения.

Песочница — `tests.sandbox.GitignoreCommittedRealGitSandbox`: пульт и клон
артели — один настоящий git-репозиторий, голый origin. База — коммит на
main (и в origin) с файлом тестов фикстуры; задача артели заводится
`catalog.cmd_new`, SPEC/PLAN/планка коммитятся в ссылку документов задачи,
кодовая ветка задачи — коммитом в её рабочей копии (`workspace.ensure`),
ослабление — удалённый метод файла тестов. Коммит ANSWER — настоящий,
командой `answer.cmd_answer` в ссылку документов, без подмены коммита и
фиксации.

Связка «answer — ссылка документов — фиксация — approve/reject — автокоммит
шага — рубеж неослабления» и есть предмет. Шаг аналитика после reject —
его штатные края без агента: выкладка каталога документов из головы ссылки
(`runner.role_cwd`), правка SPEC.md в каталоге документов, автокоммит
`checkpoint.commit_step_artifacts`. Рубеж перехода `in_dev -> verifying` и
рубеж гейта мержа читаются публичными входами `test_integrity.uncovered`
(общий вход обоих рубежей: та же оценка диффа и мандата ANSWER, что у
перехода) и `test_integrity.merge_gate_escalates`; ссылка документов —
`artifact_source.resolve`.

Имена файла тестов, класса, методов, элементы мандата и порядок случаев —
от зерна; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом ветки `spec_gate` в `answer._cmd_answer`
(откачен, не закоммичен): все методы зелёные; мутант «ANSWER на `spec_gate`
без `store.record_fixation`» красит AC-1 (голый approve отказывает по
дрейфу фиксации).
"""
import contextlib
import io
import os
import random
import unittest
from unittest import mock

from orchestrator import (answer, artifact_source, catalog, checkpoint, config,
                          fsm, projects, runner, store, workspace)
from orchestrator.advance_gates import test_integrity
from tests import mandate_matrix
from tests.sandbox import GitignoreCommittedRealGitSandbox

WEAKEN = "Ослабление тестов разрешено:"
DOCS_REF_PREFIX = "refs/artifacts/"
MANDATE_ACTION = "ANSWER создан (мандат на ослабление тестов: {})"
INSTRUCTION_ACTION = "ANSWER создан: указание Оператора"
ALLOWED_ACTION = "ослабление тестов разрешено мандатом Оператора"
APPROVE_REFUSED = "approve отклонён"
SEP = "::"

ARTEL_TARGETS = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: file:///nonexistent/{config.DEFAULT_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {config.DEFAULT_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/
budget_usd: 30
---

# SPEC: фикстура мандата на гейте SPEC {marker}

## Контекст

Фикстура песочницы {marker}.

## Требования

1. Требование фикстуры {marker}.

## Критерии приёмки

AC-1. Фикстурный критерий {marker}.

## Не входит

Ничего.
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: фикстура

## Подход

Фикстура.

## Шаги

1. Фикстура.

## Покрытие требований

Фикстура.

## Влияние на систему

Нет.
"""

PLANK_TEXT = '''"""Фикстура планки песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_fixture_plank(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 2)
'''


def word(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


def fixture_source(cls: str, methods: list) -> str:
    return (f"import unittest\n\n\nclass {cls}(unittest.TestCase):\n"
            + "".join(f"\n    def {m}(self):\n        self.assertEqual(1, 1)\n"
                      for m in methods))


class SpecGateFlowSandbox(GitignoreCommittedRealGitSandbox):
    """Задача артели с SPEC в ссылке документов и кодовой веткой; файл
    тестов фикстуры на main."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.add_synced_origin()
        config.TARGETS.write_text(ARTEL_TARGETS, encoding="utf-8")
        self.run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.run_cmd(catalog.cmd_init)
        self.use_role_map()
        templates = self.root / ".artel" / "templates-fixture"
        templates.mkdir(parents=True, exist_ok=True)
        (templates / "SPEC.md").write_text(
            SPEC_TEXT.format(task="TASK_ID", marker="шаблон"), encoding="utf-8")
        for patcher in (
                mock.patch.object(config, "TEMPLATES", templates),
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.cls = f"Fx{word(self.rng).capitalize()}Test"
        self.path = f"tests/test_fx_{word(self.rng)}.py"
        self.methods = [f"test_{word(self.rng)}_{i}"
                        for i in range(self.rng.randint(3, 4))]
        target = self.root / self.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fixture_source(self.cls, self.methods), encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    @staticmethod
    def run_cmd(fn, *args, **kwargs) -> tuple[str, bool]:
        """(вывод вместе с текстом ненулевого `SystemExit`, был ли он)."""
        buf = io.StringIO()
        failed = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    failed = True
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), failed

    def docs_head(self, task_id: str) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        DOCS_REF_PREFIX + task_id).strip()

    def answers(self, task_id: str) -> list[str]:
        if not self.docs_head(task_id):
            return []
        return sorted(p.rsplit("/", 1)[-1] for p in self.git(
            "ls-tree", "-r", "--name-only", DOCS_REF_PREFIX + task_id).splitlines()
            if p.rsplit("/", 1)[-1].startswith("ANSWER-"))

    def docs_dir(self, task_id: str):
        return config.PROJECTS / config.DEFAULT_TARGET / "tasks" / task_id

    def commit_docs(self, task_id: str, files: dict, message: str) -> None:
        """Коммит `files` (путь внутри каталога задачи -> текст) в ссылку
        документов: отдельная рабочая копия на её голове и `update-ref`."""
        old = self.docs_head(task_id)
        self.assertTrue(old, self.note("ссылки документов нет"))
        scratch = self.root / ".artel" / f"docs-copy-{self.rng.randrange(1 << 30)}"
        self.git("worktree", "add", "-q", "--detach", str(scratch), old)
        try:
            for rel, text in files.items():
                target = scratch.joinpath("tasks", task_id, rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            self.git("-C", str(scratch), "add", "-A")
            self.git("-C", str(scratch), "commit", "-q", "-m", message)
            new = self.git("-C", str(scratch), "rev-parse", "HEAD").strip()
        finally:
            self.git("worktree", "remove", "--force", str(scratch))
        self.git("update-ref", DOCS_REF_PREFIX + task_id, new, old)

    def new_task(self, state: str, weaken: list | None = None) -> str:
        """Задача артели в `state` с документами в ссылке и кодовой веткой;
        `weaken` — методы, удалённые из файла тестов фикстуры в ветке."""
        before = {row["id"] for row in store.all_tasks(store.db())}
        out, _failed = self.run_cmd(catalog.cmd_new,
                                    f"Мандат на гейте SPEC {self.rng.randrange(1 << 20)}",
                                    target=config.DEFAULT_TARGET)
        created = [row["id"] for row in store.all_tasks(store.db())
                   if row["id"] not in before]
        self.assertEqual(len(created), 1, self.note(f"задача не заведена:\n{out}"))
        task_id = created[0]
        branch = store.get_task(store.db(), task_id)["branch"]
        if not self.git("branch", "--list", branch).strip():
            self.git("branch", branch, config.MAIN_BRANCH)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        if weaken:
            (wt / self.path).write_text(fixture_source(
                self.cls, [m for m in self.methods if m not in weaken]),
                encoding="utf-8")
            self.git("-C", str(wt), "add", "-A")
            self.git("-C", str(wt), "commit", "-q", "-m", f"{task_id}: правка тестов")
        self.commit_docs(task_id, {
            "SPEC.md": SPEC_TEXT.format(task=task_id, marker=word(self.rng)),
            "PLAN.md": PLAN_TEXT.format(task=task_id),
            "acceptance_tests/test_plank.py": PLANK_TEXT}, "документы задачи")
        store.update_task(store.db(), task_id, state=state)
        store.record_fixation(store.db(), task_id)
        return task_id

    def answer_file(self, text: str) -> str:
        path = self.root / ".artel" / f"otvet-{self.rng.randrange(1 << 40)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def mandate_text(self, elements: list) -> str:
        return (f"Ответ Оператора {self.rng.randrange(10 ** 6)}.\n\n"
                f"{WEAKEN} {', '.join(elements)}\n"
                f"{mandate_matrix.INDEPENDENT_CHECK_LINE}\n\n"
                + mandate_matrix.matrix(elements))

    def give_answer(self, task_id: str, text: str, what: str) -> str:
        """`answer` принят: ровно один новый ANSWER в ссылке документов;
        возврат — его имя без `.md`."""
        before = set(self.answers(task_id))
        out, failed = self.run_cmd(answer.cmd_answer, task_id,
                                   self.answer_file(text))
        context = self.note(f"{what}\nфайл:\n{text}\nвывод:\n{out}")
        self.assertFalse(failed, context)
        new = set(self.answers(task_id)) - before
        self.assertEqual(len(new), 1, context)
        return new.pop()[:-len(".md")]

    def state(self, task_id: str) -> str:
        return store.get_task(store.db(), task_id)["state"]

    def set_state(self, task_id: str, state: str) -> None:
        store.update_task(store.db(), task_id, state=state)

    def rows(self, task_id: str) -> list:
        return list(store.task_steps(store.db(), task_id))

    def journal(self, task_id: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.rows(task_id))

    def analyst_step(self, task_id: str) -> None:
        """Края шага аналитика без агента: выкладка каталога документов из
        головы ссылки, новая редакция SPEC.md, автокоммит шага."""
        runner.role_cwd(store.db(), task_id, config.DEFAULT_TARGET)
        spec = self.docs_dir(task_id) / "SPEC.md"
        self.assertTrue(spec.is_file(), self.note("каталог документов не выложен"))
        spec.write_text(SPEC_TEXT.format(task=task_id, marker=word(self.rng)),
                        encoding="utf-8")
        checkpoint.commit_step_artifacts(store.db(), task_id, "analyst")

    def uncovered_text(self, task_id: str) -> str:
        """Находки рубежа неослабления без мандата (общий вход перехода
        `in_dev -> verifying` и гейта мержа) — одной строкой."""
        branch = store.get_task(store.db(), task_id)["branch"]
        docs, _foreign = artifact_source.resolve(store.db(), task_id)
        found, git_detail = test_integrity.uncovered(store.db(), task_id,
                                                     branch, docs)
        self.assertIsNotNone(found, self.note(f"git не ответил: {git_detail}"))
        return "\n".join(f.line for f in found)

    def merge_gate_escalates(self, task_id: str) -> bool:
        self.set_state(task_id, "merge_gate")
        branch = store.get_task(store.db(), task_id)["branch"]
        docs, _foreign = artifact_source.resolve(store.db(), task_id)
        return test_integrity.merge_gate_escalates(store.db(), task_id,
                                                   "merge_gate", branch, docs)


# ---------------------------------------------------------------- AC-1

class SpecGateMandateThenApproveTest(SpecGateFlowSandbox):

    def test_ac1_spec_gate_mandate_committed_and_bare_approve_passes_fixation(self):
        """Мандат тестов на `spec_gate` — настоящий коммит ANSWER, состояние прежнее, запись журнала; голый approve после него проходит.

        Сценарий: задача на `spec_gate` с зафиксированными документами;
        файл ответа — строка «Ослабление тестов разрешено:» на 1–3
        элемента (файл, класс или метод — от зерна), строка «Независимая
        проверка:», матрица. `answer` принят: ANSWER-1.md в ссылке
        документов несёт строку мандата, задача на `spec_gate`, в журнале
        запись «ANSWER создан (мандат на ослабление тестов: <элементы>)».
        Затем голый `fsm.cmd_approve` без перефиксации тестом уводит задачу
        из `spec_gate`, новой записи «approve отклонён» нет.

        Ловит мутацию: ANSWER на `spec_gate` закоммичен без
        `store.record_fixation` — голый approve отказывает по дрейфу
        фиксации («живой sha расходится с зафиксированным»), задача остаётся
        на `spec_gate`; либо запись журнала прежняя «ANSWER создан» без
        элементов.
        """
        task_id = self.new_task("spec_gate")
        elements = []
        for _ in range(self.rng.randint(1, 3)):
            n = word(self.rng)
            element = self.rng.choice((f"tests/test_{n}.py",
                                       f"tests/test_{n}.py{SEP}C{n.capitalize()}",
                                       f"tests/test_{n}.py{SEP}C{n.capitalize()}"
                                       f"{SEP}test_{n}"))
            if element not in elements:
                elements.append(element)
        text = self.mandate_text(elements)
        name = self.give_answer(task_id, text, "мандат на spec_gate")

        line = f"{WEAKEN} {', '.join(elements)}"
        shown = self.git("show", f"{DOCS_REF_PREFIX}{task_id}:"
                         + "/".join(("tasks", task_id, f"{name}.md")))
        context = self.note(f"журнал:\n{self.journal(task_id)}")
        self.assertIn(line, shown, context)
        self.assertEqual(self.state(task_id), "spec_gate", context)
        self.assertIn(MANDATE_ACTION.format(", ".join(elements)),
                      [r["action"] for r in self.rows(task_id)], context)

        refusals = len([r for r in self.rows(task_id)
                        if r["action"] == APPROVE_REFUSED])
        out, _failed = self.run_cmd(fsm.cmd_approve, task_id)

        context = self.note(f"approve:\n{out}\nжурнал:\n{self.journal(task_id)}")
        self.assertNotEqual(self.state(task_id), "spec_gate", context)
        self.assertEqual(len([r for r in self.rows(task_id)
                              if r["action"] == APPROVE_REFUSED]), refusals, context)


# ---------------------------------------------------------------- AC-6

class SpecGateMandateCountsAtGatesTest(SpecGateFlowSandbox):

    def test_ac6_spec_gate_mandate_counts_at_in_dev_and_merge_gates(self):
        """Мандат с `spec_gate` (и после reject с автокоммитом аналитика) засчитывается рубежом `in_dev -> verifying` и гейтом мержа, как мандат из `in_dev`.

        Сценарий: в кодовой ветке каждой задачи удалены 1–2 метода файла
        тестов фикстуры. Три задачи (порядок от зерна): (а) мандат на
        удалённые методы дан `answer` на `spec_gate`; (б) то же, затем
        `reject` (задача в `spec_writing`), шаг аналитика пишет новую
        редакцию SPEC.md и её автокоммит ложится в ту же ссылку
        документов; (в) контроль — мандат дан `answer` в `in_dev`. До
        мандата рубеж находит каждый удалённый метод. Задача переводится в
        `in_dev`: у всех трёх рубеж не находит ни одного удалённого метода,
        запись «ослабление тестов разрешено мандатом Оператора» называет
        ANSWER и методы; на `merge_gate` гейт мержа не эскалирует, задача
        остаётся на `merge_gate`.

        Ловит мутацию: ANSWER на `spec_gate` пишется не в ссылку документов
        задачи (или мимо `artifact_branch.commit_files`, файлом каталога
        документов) — выкладка и автокоммит шага аналитика его теряют, рубеж
        находит удалённый метод в случае (б), гейт мержа эскалирует.
        """
        removed_count = self.rng.randint(1, 2)
        cases = ["spec_gate", "spec_gate+reject", "in_dev"]
        self.rng.shuffle(cases)
        for case in cases:
            with self.subTest(case=case):
                removed = self.rng.sample(self.methods, removed_count)
                state = "in_dev" if case == "in_dev" else "spec_gate"
                task_id = self.new_task(state, weaken=removed)
                elements = [f"{self.path}{SEP}{self.cls}{SEP}{m}" for m in removed]
                before = self.uncovered_text(task_id)
                for method in removed:
                    self.assertIn(method, before, self.note(
                        f"{case}: предпосылка — рубеж не видит удаления "
                        f"{method}:\n{before}"))

                name = self.give_answer(task_id, self.mandate_text(elements), case)
                if case == "spec_gate+reject":
                    out, failed = self.run_cmd(fsm.cmd_reject, task_id,
                                               f"Переписать AC {word(self.rng)}")
                    self.assertFalse(failed, self.note(f"reject:\n{out}"))
                    self.assertEqual(self.state(task_id), "spec_writing", self.note(
                        f"reject не вернул аналитику:\n{out}\n{self.journal(task_id)}"))
                    head = self.docs_head(task_id)
                    self.analyst_step(task_id)
                    self.assertNotEqual(self.docs_head(task_id), head, self.note(
                        f"автокоммит аналитика не лёг в ссылку:\n{self.journal(task_id)}"))
                self.set_state(task_id, "in_dev")

                rest = self.uncovered_text(task_id)
                context = self.note(f"{case}: {name}\nнаходки:\n{rest}\n"
                                    f"журнал:\n{self.journal(task_id)}")
                for method in removed:
                    self.assertNotIn(method, rest, context)
                allowed = "\n".join(r["detail"] or "" for r in self.rows(task_id)
                                    if r["action"] == ALLOWED_ACTION)
                self.assertIn(name, allowed, context)
                for method in removed:
                    self.assertIn(method, allowed, context)

                self.assertFalse(self.merge_gate_escalates(task_id), context)
                self.assertEqual(self.state(task_id), "merge_gate", context)


# ---------------------------------------------------------------- AC-7

class InstructionGivesNoMandateTest(SpecGateFlowSandbox):

    def test_ac7_instruction_answer_without_mandate_line_gives_no_mandate(self):
        """ANSWER-указание в `in_dev` без строки мандата тестов — рубеж неослабления по-прежнему находит ослабление.

        Сценарий: задача в `in_dev`, в кодовой ветке удалён метод файла
        тестов фикстуры. Оператор даёт `answer` файлом-указанием без строки
        «Ослабление тестов разрешено:» — от зерна маркер с элементом
        удалённого метода процитирован в середине строки. Указание принято:
        ANSWER в ссылке документов, запись «ANSWER создан: указание
        Оператора». Рубеж `in_dev -> verifying` находит удалённый метод,
        записи «ослабление тестов разрешено мандатом Оператора» с этим
        ANSWER нет.

        Ловит мутацию: приём `answer` распознаёт маркер мандата тестов в
        любом месте строки (свой детектор вместо `mandate.elements`) —
        файл-указание с цитатой уходит в ветку мандата и отказ матрицы,
        ANSWER-указания нет.
        """
        removed = self.rng.choice(self.methods)
        task_id = self.new_task("in_dev", weaken=[removed])
        element = f"{self.path}{SEP}{self.cls}{SEP}{removed}"
        text = f"Указание Оператора {self.rng.randrange(10 ** 6)}: доведи PLAN.\n"
        if self.rng.random() < 0.5:
            text += f"Мандата нет: строку «{WEAKEN} {element}» не даю.\n"
        before = len(self.rows(task_id))
        name = self.give_answer(task_id, text, "указание в in_dev")
        context = self.note(f"журнал:\n{self.journal(task_id)}")
        self.assertIn(INSTRUCTION_ACTION,
                      [r["action"] for r in self.rows(task_id)[before:]], context)

        rest = self.uncovered_text(task_id)

        context = self.note(f"{name}\nнаходки:\n{rest}\nжурнал:\n{self.journal(task_id)}")
        self.assertIn(removed, rest, context)
        allowed = "\n".join(r["detail"] or "" for r in self.rows(task_id)
                            if r["action"] == ALLOWED_ACTION)
        self.assertNotIn(name, allowed, context)


if __name__ == "__main__":
    unittest.main()
