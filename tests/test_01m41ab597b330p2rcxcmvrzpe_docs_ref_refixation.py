"""Перефиксирующие записи пульта не узаконивают сдвиг ссылки документов
задачи мимо пульта; законные записи пульта ложного инцидента не дают.

Группа: долгоживущий

Красен до реализации: `store.set_state`, `answer`, `zones-extend`, `amend-tests --from-branch`, `snapshot.commit_closing`, `doctor --fix`, `commit_pull_checkpoint` и `kill` перефиксируют голову ссылки без сверки с `tasks.fixed_sha` (подменённая голова уходит в `fixed_sha`, коммиты ложатся поверх неё, переход не эскалирует), а при нечитаемой голове `record_fixation` пишет в `fixed_sha` пустое значение — методы AC-1–AC-5 (кроме автокоммита шага), AC-8 (фиксация есть), AC-9, AC-10 (подмена), AC-13 (kill) красные; автокоммит шага (сверка `checkpoint` уже есть), законная цепочка AC-7/AC-10, AC-8 без фиксации и отказ гейта мержа держат существующее поведение и зелёные.

Сценарий на настоящем git: пульт — `self.root` (git главной копии), задача
артели заводится `catalog.cmd_new` (ссылка `refs/artifacts/<id>` в git
пульта), задача внешнего проекта — тем же `cmd_new` с `target=` (ссылка в
клоне проекта `config.PROJECTS/<проект>/workspace`, `make_project_repo`).
Шаблон SPEC подменён фикстурой со `status: ready`, чтобы `advance` из
`spec_writing` был настоящим переходом FSM.

Фиксация заводится записью пульта `store.record_fixation`, пока фиксации
ещё нет (тот же вход, что у первого чекпоинта шага): начальное содержимое
ссылки (планка, игнорируемый файл) кладётся до неё. «Роль сдвигает ссылку
мимо пульта» — ровно путь из SPEC: коммит в отдельной рабочей копии на
голове ссылки и `git update-ref` (со сверкой прежнего значения), без
единого вызова пульта. Наблюдения — git напрямую (`for-each-ref`), не узел
чтения пульта, и колонка `tasks.fixed_sha`.

«Именованная причина» инцидента — запись журнала (действие или деталь),
называющая «инцидент целостности» либо сдвиг «мимо пульта»; точную
формулировку тест не навязывает. Вид сдвига (пустой коммит или правка
SPEC.md), имя проекта и порядок законных записей — из `random`, зерно
печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (amend, answer, catalog, checkpoint, cleanup, config,
                          doctor, fixation, fsm, idgen, projects, runner,
                          snapshot, store)
from tests.sandbox import GitignoreCommittedRealGitSandbox, make_project_repo

REF_PREFIX = "refs/artifacts/"
INCIDENT_WORDS = ("инцидент целостности", "мимо пульта")
PROJECT_NAMES = ("sled", "sani", "drovni", "rozvalni")
MOVE_KINDS = ("пустой коммит", "правка SPEC.md")
TITLES = ("Перефиксация", "Сверка ссылки", "Подмена головы", "Запись пульта")
#: Файл, который `.gitignore` пульта (`GITIGNORE_TEXT` песочницы) игнорирует.
IGNORED_NAME = "notes.log"

SPEC_TEMPLATE = """---
task: TASK_ID
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: <название задачи>

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

PLANK_TEST = "import unittest\n\n\nclass T(unittest.TestCase):\n    pass\n"

ARTEL_TARGETS = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: file:///nonexistent/{config.DEFAULT_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {config.DEFAULT_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def incident_named(text: str) -> bool:
    low = (text or "").lower()
    return any(word in low for word in INCIDENT_WORDS)


class DocsRefSandbox(GitignoreCommittedRealGitSandbox):
    """Пульт на настоящем git; задачи артели и внешнего проекта заводятся
    `catalog.cmd_new`, ссылку документов роль двигает мимо пульта."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.targets: dict[str, str] = {}

        config.TARGETS.write_text(ARTEL_TARGETS, encoding="utf-8")
        self.run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.run_cmd(catalog.cmd_init)
        self.use_role_map()

        templates = self.root / ".artel" / "templates-fixture"
        templates.mkdir(parents=True, exist_ok=True)
        (templates / "SPEC.md").write_text(SPEC_TEMPLATE, encoding="utf-8")
        for patcher in (
                mock.patch.object(config, "TEMPLATES", templates),
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def run_cmd(self, fn, *args, **kwargs) -> tuple[str, bool]:
        """(вывод команды вместе с текстом отказа, был ли `SystemExit`)."""
        buf = io.StringIO()
        exited = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                exited = True
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), exited

    def new_task(self, target: str | None = None) -> str:
        """Задача в `spec_writing` со SPEC.md в ссылке документов и без
        фиксации. Артель — `catalog.cmd_new`. Внешний проект — строка БД и
        первый автокоммит пульта (SPEC.md в каталоге документов): так
        ссылка с первого коммита живёт в git проекта; фиксация, заведённая
        автокоммитом, снимается — исходное состояние то же, что после
        `cmd_new`."""
        target = target or config.DEFAULT_TARGET
        title = self.rng.choice(TITLES)
        if target == config.DEFAULT_TARGET:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                task_id = catalog.cmd_new(title, target=target)
            self.targets[task_id] = target
            return task_id
        task_id = idgen.new_task_id()
        self.targets[task_id] = target
        conn = store.db()
        store.insert_task(conn, task_id, title, "spec_writing",
                          f"task/{task_id.lower()}-x", target, 25.0)
        spec = self.docs_dir(task_id) / "SPEC.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(SPEC_TEMPLATE.replace("TASK_ID", task_id),
                        encoding="utf-8")
        out, _exited = self.run_cmd(checkpoint.commit_step_artifacts, conn,
                                    task_id, "analyst")
        self.assertTrue(self.head(task_id), self.note(
            f"первый автокоммит не завёл ссылку в git проекта:\n{out}"))
        store.update_task(conn, task_id, fixed_sha=None)
        return task_id

    def external_target(self) -> str:
        name = self.rng.choice(PROJECT_NAMES) + str(self.rng.randrange(10, 100))
        make_project_repo(name, origin=False)
        return name

    def repo(self, task_id: str) -> Path:
        target = self.targets[task_id]
        if target == config.DEFAULT_TARGET:
            return self.root
        return config.PROJECTS / target / "workspace"

    def rgit(self, task_id: str, *args: str) -> str:
        return self.git("-C", str(self.repo(task_id)), *args)

    def ref(self, task_id: str) -> str:
        return REF_PREFIX + task_id

    def head(self, task_id: str) -> str:
        """Голова ссылки документов — git напрямую, мимо узла чтения пульта."""
        return self.rgit(task_id, "for-each-ref", "--format=%(objectname)",
                         self.ref(task_id)).strip()

    def fixed(self, task_id: str) -> str | None:
        return store.get_task(store.db(), task_id)["fixed_sha"]

    def state(self, task_id: str) -> str:
        return store.get_task(store.db(), task_id)["state"]

    def force_state(self, task_id: str, state: str, **fields) -> None:
        """Состояние задачи прямой записью БД — без перехода FSM, без
        записи в ссылку и без фиксации."""
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        conn.commit()
        if fields:
            store.update_task(conn, task_id, **fields)

    def docs_dir(self, task_id: str) -> Path:
        return config.PROJECTS / self.targets[task_id] / "tasks" / task_id

    def journal_mark(self, task_id: str) -> int:
        rows = store.task_steps(store.db(), task_id)
        return rows[-1]["id"] if rows else 0

    def journal_since(self, task_id: str, mark: int) -> str:
        return "\n".join(f"{r['action']}: {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), task_id)
                         if r["id"] > mark)

    def commit_docs(self, task_id: str, files: dict, message: str) -> str:
        """Коммит в ссылку документов мимо пульта: отдельная рабочая копия
        на голове ссылки, правка `files` (путь внутри каталога задачи ->
        текст; пусто — пустой коммит), `git commit` и `git update-ref` со
        сверкой прежнего значения. Возвращает новую голову."""
        old = self.head(task_id)
        self.assertTrue(old, self.note(f"ссылки {self.ref(task_id)} нет"))
        scratch = Path(tempfile.mkdtemp(prefix="artel-role-copy-"))
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        copy = scratch / "copy"
        self.rgit(task_id, "worktree", "add", "-q", "--detach", str(copy), old)
        try:
            for rel, text in files.items():
                path = copy / "tasks" / task_id / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            self.git("-C", str(copy), "add", "-A")
            self.git("-C", str(copy), "commit", "-q", "--allow-empty",
                     "-m", message)
            new = self.git("-C", str(copy), "rev-parse", "HEAD").strip()
        finally:
            self.rgit(task_id, "worktree", "remove", "--force", str(copy))
        self.rgit(task_id, "update-ref", self.ref(task_id), new, old)
        return new

    def pult_fix(self, task_id: str) -> str:
        """Первая фиксация документов записью пульта (фиксации ещё нет)."""
        self.assertIsNone(self.fixed(task_id),
                          self.note("предусловие: фиксации ещё нет"))
        store.record_fixation(store.db(), task_id)
        fixed = self.fixed(task_id)
        self.assertTrue(fixed, self.note("фиксация не заведена"))
        self.assertEqual(fixed, self.head(task_id),
                         self.note("фиксация не равна голове ссылки"))
        return fixed

    def ready_task(self, target: str | None = None, plank: bool = False,
                   ignored: bool = False) -> tuple[str, str]:
        """Задача с заведённой фиксацией: (id, зафиксированный sha).
        `plank` — в ссылке планка и `tests_locked_sha` на её коммите;
        `ignored` — в ссылке файл, игнорируемый `.gitignore` пульта."""
        task_id = self.new_task(target)
        files = {}
        if plank:
            files["acceptance_tests/test_seed.py"] = PLANK_TEST
        if ignored:
            files[IGNORED_NAME] = "игнорируемый файл\n"
        if files:
            self.commit_docs(task_id, files, f"{task_id}: исходные документы")
        if plank:
            store.update_task(store.db(), task_id,
                              tests_locked_sha=self.head(task_id))
        return task_id, self.pult_fix(task_id)

    def role_moves_ref(self, task_id: str, files: dict | None = None) -> str:
        """Роль сдвигает ссылку мимо пульта; возвращает подменённую голову."""
        if files is None:
            kind = self.rng.choice(MOVE_KINDS)
            files = ({} if kind == MOVE_KINDS[0] else
                     {"SPEC.md": SPEC_TEMPLATE.replace("TASK_ID", task_id)
                      + "\nПодмена роли мимо гейта.\n"})
        moved = self.commit_docs(task_id, files, f"{task_id}: правка роли")
        self.assertNotEqual(moved, self.fixed(task_id),
                            self.note("предусловие: голова разошлась с фиксацией"))
        return moved

    def descendants(self, task_id: str, sha: str) -> set:
        """Головы ссылок репозитория задачи, в чьей истории есть `sha`."""
        out = self.rgit(task_id, "for-each-ref", "--contains", sha,
                        "--format=%(objectname)")
        return {line.strip() for line in out.splitlines() if line.strip()}

    def assert_untouched(self, task_id: str, fixed: str, moved: str,
                         where: str) -> None:
        """Подменённая голова не перефиксирована и поверх неё нет коммита."""
        self.assertEqual(self.fixed(task_id), fixed, self.note(
            f"{where}: tasks.fixed_sha изменён (был {fixed}, подмена {moved})"))
        self.assertEqual(self.head(task_id), moved, self.note(
            f"{where}: поверх подменённой головы {moved} лёг коммит"))

    def assert_incident_journaled(self, task_id: str, mark: int,
                                  where: str) -> None:
        text = self.journal_since(task_id, mark)
        self.assertTrue(incident_named(text), self.note(
            f"{where}: в журнале нет записи об инциденте "
            f"({' / '.join(INCIDENT_WORDS)}):\n{text}"))

    def advance(self, task_id: str) -> str:
        out, _exited = self.run_cmd(fsm.cmd_advance, task_id)
        return out

    def plant_root_decoy(self, task_id: str) -> None:
        """Ссылка задачи внешнего проекта копируется в git главной копии на
        зафиксированном значении: сверка, читающая git главной копии, увидит
        там голову, равную фиксации, а не живую голову проекта."""
        ref = self.ref(task_id)
        self.git("fetch", "-q", str(self.repo(task_id)), f"+{ref}:{ref}")

    # --- общие сценарии -------------------------------------------------

    def check_advance_incident(self, task_id: str, fixed: str) -> str:
        """AC-2: сдвиг мимо пульта, затем `advance` — эскалация с
        именованной причиной, ни перефиксации, ни коммита паспорта; старт
        следующего шага агента не запускает. Возвращает подменённую голову."""
        moved = self.role_moves_ref(task_id)
        mark = self.journal_mark(task_id)

        out = self.advance(task_id)

        self.assertEqual(self.state(task_id), "escalated", self.note(
            f"advance после сдвига мимо пульта не эскалировал:\n{out}"))
        self.assert_incident_journaled(task_id, mark, "advance")
        self.assert_untouched(task_id, fixed, moved, "advance")

        launches = []
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=lambda *a, **k: launches.append(a)):
            run_out, _exited = self.run_cmd(runner.cmd_run, task_id)
        self.assertEqual(launches, [], self.note(
            f"старт шага после инцидента запустил агента:\n{run_out}"))
        self.assert_untouched(task_id, fixed, moved, "run после инцидента")
        return moved

    def check_legit_chain(self, task_id: str, ops_extra: int = 2) -> list:
        """AC-7: законные записи пульта подряд в случайном порядке — после
        каждой `tasks.fixed_sha` равен голове ссылки, инцидента нет."""
        ops = {
            "переход FSM": self.op_transition,
            "автокоммит шага": self.op_autocommit,
            "answer": self.op_answer,
            "amend-tests": self.op_amend,
            "коммит закрытия": self.op_closing,
        }
        order = list(ops)
        self.rng.shuffle(order)
        order += [self.rng.choice(list(ops)) for _ in range(ops_extra)]
        mark = self.journal_mark(task_id)
        for n, name in enumerate(order):
            before = self.head(task_id)
            out, exited = ops[name](task_id, n)
            where = f"шаг {n + 1} «{name}» цепочки {order}"
            self.assertFalse(exited, self.note(f"{where}: отказ команды:\n{out}"))
            self.assertEqual(self.fixed(task_id), self.head(task_id), self.note(
                f"{where}: fixed_sha {self.fixed(task_id)} не равен голове "
                f"ссылки {self.head(task_id)} (до записи {before})\n{out}"))
            text = self.journal_since(task_id, mark)
            self.assertFalse(incident_named(text), self.note(
                f"{where}: ложный инцидент на законной записи пульта:\n{text}"))
        return order

    def op_transition(self, task_id: str, n: int) -> tuple[str, bool]:
        current = self.state(task_id)
        nxt = self.rng.choice([s for s in ("in_dev", "review", "verifying")
                               if s != current])
        return self.run_cmd(store.set_state, store.db(), task_id, nxt, "fsm",
                            expected_state=current,
                            detail="законный переход цепочки")

    def op_autocommit(self, task_id: str, n: int) -> tuple[str, bool]:
        plan = self.docs_dir(task_id) / "PLAN.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(f"# PLAN\n\nправка роли {n} ({self.seed})\n",
                        encoding="utf-8")
        return self.run_cmd(checkpoint.commit_step_artifacts, store.db(),
                            task_id, "developer")

    def op_answer(self, task_id: str, n: int) -> tuple[str, bool]:
        if self.state(task_id) != "escalated":
            self.force_state(task_id, "escalated",
                             escalated_from=self.state(task_id))
        path = self.root / ".artel" / f"answer-{n}.txt"
        path.write_text(f"Ответ Оператора {n}.\n", encoding="utf-8")
        return self.run_cmd(answer.cmd_answer, task_id, str(path))

    def op_amend(self, task_id: str, n: int) -> tuple[str, bool]:
        test = self.docs_dir(task_id) / "acceptance_tests" / f"test_chain_{n}.py"
        test.parent.mkdir(parents=True, exist_ok=True)
        test.write_text(PLANK_TEST, encoding="utf-8")
        out, exited = self.run_cmd(checkpoint.commit_step_artifacts,
                                   store.db(), task_id, "test_author")
        if exited:
            return out, exited
        more, exited = self.run_cmd(amend.cmd_amend_tests, task_id,
                                    "правка планки цепочки", from_branch=True)
        return out + more, exited

    def op_closing(self, task_id: str, n: int) -> tuple[str, bool]:
        return self.run_cmd(snapshot.commit_closing, store.db(), task_id,
                            "killed")


class AdvanceAfterRoleMoveTest(DocsRefSandbox):

    def test_ac1_advance_does_not_refix_moved_head(self):
        """Роль сдвинула ссылку мимо пульта, затем advance — подменённая голова не попадает в `tasks.fixed_sha`.

        Сценарий: задача артели с заведённой фиксацией; роль коммитит в
        ссылку документов (пустой коммит или правка SPEC.md) и двигает
        ссылку `git update-ref`; затем `advance` из `spec_writing` (SPEC
        ready — переход FSM состоялся бы). `tasks.fixed_sha` остаётся
        прежним и не равен подменённой голове.

        Ловит мутацию: `store.set_state` перефиксирует голову ссылки без
        сверки с прежней фиксацией (`_append_passport_line` ->
        `record_fixation`, как на пине) — подменённый sha оказывается в
        `tasks.fixed_sha`.
        """
        task_id, fixed = self.ready_task()
        moved = self.role_moves_ref(task_id)

        out = self.advance(task_id)

        self.assertNotEqual(self.fixed(task_id), moved, self.note(
            f"advance узаконил подменённую голову {moved}:\n{out}"))
        self.assertEqual(self.fixed(task_id), fixed, self.note(
            f"advance изменил фиксацию {fixed}:\n{out}"))

    def test_ac2_advance_escalates_without_passport_or_refixation(self):
        """Advance после сдвига мимо пульта — эскалация с именованной причиной, без перефиксации и коммита, агент не стартует.

        Сценарий: задача артели с фиксацией; роль сдвигает ссылку; затем
        `advance`. Задача в `escalated`; журнал несёт запись об инциденте
        (инцидент целостности / сдвиг мимо пульта); `tasks.fixed_sha`
        прежний; голова ссылки — подменённая (коммита поверх нет); `run`
        после этого агента не запускает.

        Ловит мутацию: сверка стоит только в `runner` на старте шага, а
        `advance` проводит переход по подменённым документам (задача в
        `spec_gate`); эскалация есть, но сам переход в `escalated`
        перефиксирует подменённую голову (`set_state` -> `record_fixation`);
        эскалация без записи журнала с причиной.
        """
        task_id, fixed = self.ready_task()
        self.check_advance_incident(task_id, fixed)


class OperatorCommandsAfterRoleMoveTest(DocsRefSandbox):

    def test_ac3_answer_does_not_commit_over_moved_head(self):
        """`answer` после сдвига мимо пульта — ответ не коммитится, фиксация прежняя, задача в эскалации с записью об инциденте.

        Сценарий: задача артели в `escalated` с фиксацией; роль сдвигает
        ссылку; Оператор `answer <id> <файл>`. Голова ссылки остаётся
        подменённой (ANSWER-n.md поверх неё не лёг), `tasks.fixed_sha`
        прежний, задача по-прежнему `escalated`, журнал называет инцидент.

        Ловит мутацию: `answer` коммитит ANSWER поверх головы ссылки и
        перефиксирует её без сверки с `tasks.fixed_sha` (как на пине) —
        голова сдвинута коммитом ответа, фиксация равна ему.
        """
        task_id, fixed = self.ready_task()
        self.force_state(task_id, "escalated", escalated_from="in_dev")
        moved = self.role_moves_ref(task_id)
        mark = self.journal_mark(task_id)
        path = self.root / ".artel" / "answer.txt"
        path.write_text("Ответ Оператора.\n", encoding="utf-8")

        out, _exited = self.run_cmd(answer.cmd_answer, task_id, str(path))

        self.assert_untouched(task_id, fixed, moved, f"answer\n{out}")
        self.assertEqual(self.state(task_id), "escalated", self.note(
            f"answer сменил состояние задачи:\n{out}"))
        self.assert_incident_journaled(task_id, mark, "answer")

    def test_ac3_zones_extend_does_not_commit_over_moved_head(self):
        """`zones-extend` после сдвига мимо пульта — правка зон не коммитится, фиксация прежняя, задача уходит в эскалацию.

        Сценарий: задача артели в `in_dev` с фиксацией; роль сдвигает
        ссылку; Оператор `zones-extend <id> <путь>`. Голова ссылки
        остаётся подменённой, `tasks.fixed_sha` прежний, задача в
        `escalated`, журнал называет инцидент.

        Ловит мутацию: `zones-extend` коммитит ANSWER-мандат поверх
        подменённой головы и перефиксирует её (как на пине); отказ без
        эскалации — задача остаётся в `in_dev`.
        """
        task_id, fixed = self.ready_task()
        self.force_state(task_id, "in_dev")
        moved = self.role_moves_ref(task_id)
        mark = self.journal_mark(task_id)

        out, _exited = self.run_cmd(answer.cmd_zones_extend, task_id,
                                    self.rng.choice(("docs/x.md", "orchestrator/y.py")))

        self.assert_untouched(task_id, fixed, moved, f"zones-extend\n{out}")
        self.assertEqual(self.state(task_id), "escalated", self.note(
            f"zones-extend после сдвига не эскалировал:\n{out}"))
        self.assert_incident_journaled(task_id, mark, "zones-extend")

    def test_ac4_amend_tests_does_not_lock_or_refix_moved_head(self):
        """`amend-tests` после сдвига мимо пульта (роль переписала планку) — ни коммита, ни лока, ни перефиксации.

        Сценарий: задача артели с залоченной планкой и фиксацией; роль
        коммитит в ссылку правку `acceptance_tests/` и двигает ссылку;
        Оператор `amend-tests <id> --from-branch --reason …` (режим,
        источник правки которого — голова ссылки). Голова ссылки остаётся
        подменённой, `tasks.fixed_sha` и `tests_locked_sha` прежние,
        журнал называет инцидент.

        Ловит мутацию: `amend-tests` сдвигает лок на подменённую голову и
        перефиксирует её (`_record_amend` -> `record_fixation`, как на
        пине) — правка планки ролью узаконена.
        """
        task_id, fixed = self.ready_task(plank=True)
        locked = store.get_task(store.db(), task_id)["tests_locked_sha"]
        moved = self.role_moves_ref(task_id, {
            "acceptance_tests/test_seed.py": PLANK_TEST + "\n# ослаблено ролью\n",
            "acceptance_tests/test_role.py": PLANK_TEST})
        mark = self.journal_mark(task_id)

        out, _exited = self.run_cmd(amend.cmd_amend_tests, task_id,
                                    "основание Оператора", from_branch=True)

        self.assert_untouched(task_id, fixed, moved, f"amend-tests\n{out}")
        self.assertEqual(store.get_task(store.db(), task_id)["tests_locked_sha"],
                         locked, self.note(f"лок сдвинут на подмену:\n{out}"))
        self.assert_incident_journaled(task_id, mark, "amend-tests")


class PultWritesAfterRoleMoveTest(DocsRefSandbox):

    def test_ac5_closing_commit_not_over_moved_head(self):
        """Коммит закрытия после сдвига мимо пульта не ложится поверх подменённой головы и не перефиксирует её.

        Сценарий: задача артели с фиксацией; роль сдвигает ссылку;
        `snapshot.commit_closing`. Голова ссылки — подменённая, фиксация
        прежняя, журнал называет инцидент.

        Ловит мутацию: `commit_closing` коммитит RETRO.md поверх головы и
        зовёт `record_fixation` без сверки (как на пине) — голова и
        фиксация сдвинуты коммитом закрытия.
        """
        task_id, fixed = self.ready_task()
        moved = self.role_moves_ref(task_id)
        mark = self.journal_mark(task_id)

        out, _exited = self.run_cmd(snapshot.commit_closing, store.db(),
                                    task_id, self.rng.choice(("killed", "done")))

        self.assert_untouched(task_id, fixed, moved, f"коммит закрытия\n{out}")
        self.assert_incident_journaled(task_id, mark, "коммит закрытия")

    def test_ac5_doctor_fix_not_over_moved_head(self):
        """`doctor --fix` (уборка игнорируемых файлов) после сдвига мимо пульта не коммитит поверх подменённой головы.

        Сценарий: в ссылке задачи артели лежит файл, игнорируемый
        `.gitignore` пульта, фиксация заведена; роль сдвигает ссылку;
        `doctor --fix` (строки проверок подменены пустым списком — предмет
        теста уборка). Голова ссылки — подменённая, фиксация прежняя,
        журнал задачи называет инцидент.

        Ловит мутацию: уборка игнорируемых файлов коммитит удаление поверх
        головы и перефиксирует её без сверки (как на пине).
        """
        task_id, fixed = self.ready_task(ignored=True)
        moved = self.role_moves_ref(task_id)
        mark = self.journal_mark(task_id)

        with mock.patch.object(doctor, "all_checks", lambda conn: []):
            out, _exited = self.run_cmd(doctor.cmd_doctor, fix=True)

        self.assert_untouched(task_id, fixed, moved, f"doctor --fix\n{out}")
        self.assert_incident_journaled(task_id, mark, "doctor --fix")

    def test_ac5_pull_checkpoint_does_not_refix_moved_head(self):
        """WIP-чекпоинт перед подтяжкой main после сдвига мимо пульта не перефиксирует подменённую голову.

        Сценарий: задача артели с фиксацией и рабочей копией кода
        (worktree ветки задачи) с незакоммиченным файлом; роль сдвигает
        ссылку документов; `checkpoint.commit_pull_checkpoint`. Голова
        ссылки — подменённая, фиксация прежняя, журнал называет инцидент.

        Ловит мутацию: чекпоинт подтяжки зовёт `store.record_fixation`
        безусловно после коммита кода (как на пине) — подменённая голова
        документов уходит в `tasks.fixed_sha`.
        """
        task_id, fixed = self.ready_task()
        branch = store.get_task(store.db(), task_id)["branch"]
        wt = Path(tempfile.mkdtemp(prefix="artel-code-copy-")) / "wt"
        self.addCleanup(shutil.rmtree, wt.parent, ignore_errors=True)
        self.git("worktree", "add", "-q", "-b", branch, str(wt),
                 config.MAIN_BRANCH)
        (wt / "module.py").write_text("код роли\n", encoding="utf-8")
        moved = self.role_moves_ref(task_id)
        mark = self.journal_mark(task_id)

        out, _exited = self.run_cmd(checkpoint.commit_pull_checkpoint,
                                    store.db(), task_id, wt)

        self.assert_untouched(task_id, fixed, moved, f"чекпоинт подтяжки\n{out}")
        self.assert_incident_journaled(task_id, mark, "чекпоинт подтяжки")

    def test_ac5_step_autocommit_not_over_moved_head(self):
        """Автокоммит каталога документов в конце шага после сдвига мимо пульта не коммитит поверх подменённой головы.

        Сценарий: задача артели с фиксацией; роль пишет PLAN.md в каталог
        документов и вдобавок сдвигает ссылку мимо пульта;
        `checkpoint.commit_step_artifacts`. Голова ссылки — подменённая,
        фиксация прежняя, журнал называет сдвиг.

        Ловит мутацию: при переносе сверки в общий узел автокоммит её
        потерял — PLAN.md закоммичен поверх подменённой головы
        (`_commit_step_artifacts_to_branch`) и голова перефиксирована.
        """
        task_id, fixed = self.ready_task()
        plan = self.docs_dir(task_id) / "PLAN.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(f"# PLAN\n\nшаг роли ({self.seed})\n", encoding="utf-8")
        moved = self.role_moves_ref(task_id)
        mark = self.journal_mark(task_id)

        out, _exited = self.run_cmd(checkpoint.commit_step_artifacts,
                                    store.db(), task_id,
                                    self.rng.choice(("developer", "reviewer")))

        self.assert_untouched(task_id, fixed, moved, f"автокоммит шага\n{out}")
        self.assert_incident_journaled(task_id, mark, "автокоммит шага")


class LegitChainTest(DocsRefSandbox):

    def test_ac7_legit_pult_writes_never_raise_incident(self):
        """Законные записи пульта подряд в случайном порядке не дают инцидента, фиксация всегда равна голове.

        Сценарий: задача артели с залоченной планкой и фиксацией, роль
        ссылку не трогает; в случайном порядке (каждая хотя бы раз, плюс
        повторы): переход FSM `store.set_state`, автокоммит шага (PLAN.md
        в каталоге документов), `answer` (задача в `escalated`),
        `amend-tests --from-branch` после автокоммита правки планки,
        коммит закрытия. После каждой записи `tasks.fixed_sha` равен
        голове ссылки, команда не отказала, в журнале нет инцидента.

        Ловит мутацию: узел сверки сравнивает с фиксацией после
        собственного коммита записи (паспорт, ANSWER, RETRO) или одна из
        записей пульта перестала перефиксировать свой коммит — следующая
        запись видит расхождение и объявляет ложный инцидент.
        """
        task_id, _fixed = self.ready_task(plank=True)
        self.check_legit_chain(task_id)


class GitSilentTest(DocsRefSandbox):

    def test_ac8_unreadable_head_is_not_refixed(self):
        """Фиксация есть, а голова ссылки не читается — запись пульта не пишет в `tasks.fixed_sha` непроверенное значение.

        Сценарий: задача внешнего проекта с фиксацией; git клона проекта
        недоступен (каталог `.git` убран); переход FSM `store.set_state` и
        затем WIP-чекпоинт подтяжки `commit_pull_checkpoint` (рабочая
        копия кода — отдельный worktree пульта). После каждой записи
        `tasks.fixed_sha` равен прежнему значению, и
        `fixation.check_integrity` отказывает (сверка на старте шага
        остаётся fail-closed).

        Ловит мутацию: `record_fixation` при неответившем git пишет в
        `tasks.fixed_sha` пустое значение (как на пине) — фиксация
        стирается, и `check_integrity` молча пропускает («сверять не с
        чем»).
        """
        target = self.external_target()
        task_id, fixed = self.ready_task(target)
        dot_git = self.repo(task_id) / ".git"
        hidden = dot_git.with_name(".git-hidden")
        dot_git.rename(hidden)
        self.addCleanup(lambda: hidden.exists() and hidden.rename(dot_git))

        out, _exited = self.run_cmd(store.set_state, store.db(), task_id,
                                    "spec_gate", "fsm",
                                    expected_state="spec_writing",
                                    detail="переход при молчащем git")
        self.assertEqual(self.fixed(task_id), fixed, self.note(
            f"переход при нечитаемой голове изменил фиксацию:\n{out}"))
        self.assertIsNotNone(fixation.check_integrity(store.db(), task_id),
                             self.note("сверка на старте шага пропускает"))

        branch = store.get_task(store.db(), task_id)["branch"]
        wt = Path(tempfile.mkdtemp(prefix="artel-code-copy-")) / "wt"
        self.addCleanup(shutil.rmtree, wt.parent, ignore_errors=True)
        self.git("worktree", "add", "-q", "-b", branch, str(wt),
                 config.MAIN_BRANCH)
        (wt / "module.py").write_text("код роли\n", encoding="utf-8")
        out, _exited = self.run_cmd(checkpoint.commit_pull_checkpoint,
                                    store.db(), task_id, wt)
        self.assertEqual(self.fixed(task_id), fixed, self.note(
            f"чекпоинт при нечитаемой голове изменил фиксацию:\n{out}"))
        self.assertIsNotNone(fixation.check_integrity(store.db(), task_id),
                             self.note("сверка на старте шага пропускает"))

    def test_ac8_without_fixation_writes_behave_as_before(self):
        """Фиксации нет — переход FSM после правки ссылки идёт как прежде и фиксирует голову.

        Сценарий: свежая задача (артели или внешнего проекта — случайно)
        без фиксации; в ссылку лёг коммит мимо пульта; `advance` из
        `spec_writing`. Задача в `spec_gate`, `tasks.fixed_sha` равен
        голове ссылки, записи об инциденте в журнале нет.

        Ловит мутацию: узел сверки считает отсутствие фиксации
        расхождением (`fixed_sha` пуст != голова) — переход отказывает
        или эскалирует, хотя сверять не с чем.
        """
        target = (self.external_target() if self.rng.random() < 0.5
                  else config.DEFAULT_TARGET)
        task_id = self.new_task(target)
        self.commit_docs(task_id, {}, f"{task_id}: коммит до фиксации")
        mark = self.journal_mark(task_id)

        out = self.advance(task_id)

        self.assertEqual(self.state(task_id), "spec_gate", self.note(
            f"target {target}: переход без фиксации не состоялся:\n{out}"))
        self.assertEqual(self.fixed(task_id), self.head(task_id), self.note(
            f"target {target}: фиксация не равна голове после перехода"))
        self.assertFalse(incident_named(self.journal_since(task_id, mark)),
                         self.note(f"target {target}: ложный инцидент"))


class ApproveAfterIncidentTest(DocsRefSandbox):

    def test_ac9_approve_exit_from_incident(self):
        """После инцидента advance — фиксация прежняя, `approve` без sha отказывает с обоими sha, `approve <живой sha>` узаконивает голову.

        Сценарий: сценарий AC-2 на задаче артели (эскалация по сдвигу
        мимо пульта); `tasks.fixed_sha` прежний; `approve <id>` без sha —
        вывод называет и зафиксированный, и живой sha, задача остаётся в
        `escalated`; `approve <id> <живой sha>` — задача выходит из
        эскалации, `tasks.fixed_sha` равен этой голове.

        Ловит мутацию: переход в эскалацию перефиксировал подменённую
        голову — `approve` без sha проходит молча; узел сверки блокирует и
        явный `approve <sha>` (выхода из инцидента нет).
        """
        task_id, fixed = self.ready_task()
        moved = self.check_advance_incident(task_id, fixed)

        out, _exited = self.run_cmd(fsm.cmd_approve, task_id)
        self.assertEqual(self.state(task_id), "escalated", self.note(
            f"approve без sha вывел задачу из инцидента:\n{out}"))
        self.assertIn(fixed, out, self.note(f"нет зафиксированного sha:\n{out}"))
        self.assertIn(moved, out, self.note(f"нет живого sha:\n{out}"))
        self.assertEqual(self.fixed(task_id), fixed, self.note(
            "approve без sha изменил фиксацию"))

        out, exited = self.run_cmd(fsm.cmd_approve, task_id, moved)
        self.assertNotEqual(self.state(task_id), "escalated", self.note(
            f"approve с живым sha не вывел из эскалации:\n{out}"))
        self.assertEqual(self.fixed(task_id), self.head(task_id), self.note(
            f"approve с явным sha не зафиксировал голову:\n{out}"))
        self.assertEqual(self.head(task_id), moved, self.note(
            f"голова после approve — не узаконенная Оператором:\n{out}"))


class ExternalTargetTest(DocsRefSandbox):

    def test_ac10_external_advance_after_role_move_escalates(self):
        """Внешний проект: advance после сдвига ссылки в git проекта — эскалация без паспорта и перефиксации; git главной копии не читается.

        Сценарий: задача внешнего проекта с фиксацией; копия её ссылки в
        git главной копии стоит на зафиксированном sha (приманка); роль
        сдвигает ссылку в git проекта; `advance`. Задача в `escalated`,
        журнал называет инцидент, фиксация прежняя, строки паспорта поверх
        подменённой головы нет, агент не стартует.

        Ловит мутацию: сверка читает голову ссылки в git главной копии,
        а не в репозитории проекта (`artifact_branch.task_repo`) — там
        голова равна фиксации, инцидента нет, паспорт ложится поверх
        подмены.
        """
        target = self.external_target()
        task_id, fixed = self.ready_task(target)
        self.plant_root_decoy(task_id)
        self.check_advance_incident(task_id, fixed)

    def test_ac10_external_legit_chain_no_incident(self):
        """Внешний проект: законные записи пульта (переход с паспортом и прочие) подряд не дают инцидента; git главной копии не читается.

        Сценарий: задача внешнего проекта с залоченной планкой и
        фиксацией; копия её ссылки в git главной копии застыла на первой
        фиксации (приманка); цепочка AC-7 в случайном порядке — переход
        FSM с коммитом паспорта в git проекта, автокоммит, `answer`,
        `amend-tests --from-branch`, коммит закрытия. После каждой записи
        фиксация равна голове ссылки в git проекта, инцидента нет.

        Ловит мутацию: сверка читает git главной копии — после первой же
        записи голова проекта уходит от приманки, и законная запись
        объявляется инцидентом; коммит паспорта не перефиксирован перед
        следующей сверкой.
        """
        target = self.external_target()
        task_id, _fixed = self.ready_task(target, plank=True)
        self.plant_root_decoy(task_id)
        self.check_legit_chain(task_id)


class KillAfterRoleMoveTest(DocsRefSandbox):

    def check_kill(self, task_id: str, fixed: str, moved: str) -> None:
        mark = self.journal_mark(task_id)

        out, exited = self.run_cmd(cleanup.cmd_kill, task_id)

        self.assertEqual(self.state(task_id), "killed", self.note(
            f"kill при расхождении не закрыл задачу:\n{out}"))
        self.assertEqual(self.fixed(task_id), fixed, self.note(
            f"kill перефиксировал подменённую голову {moved}:\n{out}"))
        kept = self.descendants(task_id, moved)
        self.assertEqual(kept, {moved}, self.note(
            f"подменённая голова {moved} не сохранена или поверх неё лёг "
            f"коммит (паспорт/закрытие): ссылки на {sorted(kept)}\n{out}"))
        journal = self.journal_since(task_id, mark)
        self.assertTrue(incident_named(journal), self.note(
            f"kill не записал инцидент в журнал:\n{journal}"))
        self.assertIn(moved, journal + out, self.note(
            f"sha подменённой головы не назван:\n{journal}\n{out}"))
        self.assertTrue(incident_named(out), self.note(
            f"вывод kill без именованного предупреждения:\n{out}"))

    def test_ac13_kill_working_task_after_role_move(self):
        """`kill` рабочей задачи при сдвиге мимо пульта закрывает её, не коммитя поверх подмены и не перефиксируя.

        Сценарий: задача артели в рабочем состоянии (`in_dev` либо
        `review`) с фиксацией; роль сдвигает ссылку; `kill <id>` без
        `approve <sha>`. Задача `killed`; `tasks.fixed_sha` прежний;
        подменённая голова жива (её держит ссылка) и ни одна ссылка не
        указывает на коммит поверх неё; журнал и вывод называют инцидент,
        sha подмены назван.

        Ловит мутацию: `kill` переводит в `killed` через `set_state` с
        перефиксацией и пишет коммит закрытия поверх подмены (как на пине);
        либо отказывает до `approve <sha>` — задача не закрыта; либо
        уборка `kill` стирает подменённую голову.
        """
        task_id, fixed = self.ready_task()
        self.force_state(task_id, self.rng.choice(("in_dev", "review")))
        moved = self.role_moves_ref(task_id)
        self.check_kill(task_id, fixed, moved)

    def test_ac13_kill_escalated_task_after_incident(self):
        """`kill` задачи, уже эскалированной по инциденту сдвига, закрывает её без коммита поверх подмены.

        Сценарий: сценарий AC-2 (advance после сдвига — эскалация по
        инциденту), затем `kill <id>`. Те же наблюдения, что у рабочей
        задачи: `killed`, фиксация прежняя, коммита поверх подмены нет,
        подмена сохранена, журнал и вывод называют инцидент.

        Ловит мутацию: `kill` из `escalated` пишет коммит закрытия и
        перефиксирует (как на пине); `kill` отказывает, требуя
        `approve <sha>`.
        """
        task_id, fixed = self.ready_task()
        moved = self.check_advance_incident(task_id, fixed)
        self.check_kill(task_id, fixed, moved)

    def test_ac13_merge_gate_refuses_closing_on_moved_head(self):
        """Гейт мержа при сдвиге мимо пульта отказывает закрытию `done` — задача не закрыта.

        Сценарий: задача артели в `merge_gate` с фиксацией; роль сдвигает
        ссылку; `approve <id>` без sha и `approve <id> <зафиксированный
        sha>`. Оба отказывают: задача в `merge_gate`, голова ссылки —
        подменённая (коммита закрытия нет), фиксация прежняя, журнал
        называет sha подмены.

        Ловит мутацию: гейт мержа перестал сверять голову ссылки с
        фиксацией перед закрытием (сверка снята ради `kill` либо
        перенесена после коммита закрытия) — задача уходит в `done` с
        RETRO поверх подмены.
        """
        task_id, fixed = self.ready_task()
        self.force_state(task_id, "merge_gate")
        moved = self.role_moves_ref(task_id)
        mark = self.journal_mark(task_id)

        for args in ((task_id,), (task_id, fixed)):
            out, _exited = self.run_cmd(fsm.cmd_approve, *args)
            self.assertEqual(self.state(task_id), "merge_gate", self.note(
                f"approve {args[1:]} закрыл задачу при сдвиге:\n{out}"))
            self.assert_untouched(task_id, fixed, moved, f"approve\n{out}")
        self.assertIn(moved, self.journal_since(task_id, mark), self.note(
            "отказ гейта мержа не назвал подменённую голову"))


if __name__ == "__main__":
    unittest.main()
