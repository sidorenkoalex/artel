"""Мандат Оператора «Расширение зон разрешено: …» из ANSWER-n.md доходит до
коммита пульта так же, как до гейта зон (AC-1..AC-9).

Группа: долгоживущий
Красен до реализации: коммит пульта фильтрует пути только по zones/zones_extension/COMMON_ZONES и каталогу задачи — файл вне зон по мандату ANSWER Оператора снимается со стейджа как посторонний (автокоммит, WIP-чекпоинты таймаута/аварии/pause --now), чекпоинт перед подтяжкой отказывает переходу, восстановление удалений возвращает удалённый по мандату файл, pult_commit_failed_paths его не называет, а запись автокоммита не называет пути мандата (AC-1, AC-4..AC-9 в части «с мандатом»); половины «без мандата» и «ANSWER автокоммитом роли» (AC-2, AC-3 и соответствующие подслучаи) держат сегодняшнее поведение и зелёные с рождения.

Песочница — настоящий git (`tests/sandbox.py::RealGitSandbox`): репозиторий
пульта с bare `origin`; в `main` — файл зоны задачи `pkg/mod.py` и три
каталога вне зон `zq<случайно>/` по два файла (имена от зерна; `pkg/` по
алфавиту раньше любого `zq…`, порядок `git show --numstat` поэтому ставит
путь зоны перед путём мандата). Каждый сценарий — своя задача target по
умолчанию в `in_dev` с зонами `pkg/` и своей рабочей копией кода
(`workspace.ensure`).

Мандат Оператора — `answer.cmd_answer` (задача в `in_dev`, окружение роли
снято переменной `config.ARTEL_ROLE_ENV`). ANSWER «от роли» — файл,
положенный в каталог задачи рабочей копии и перенесённый в ссылку документов
автокоммитом шага роли `checkpoint.commit_step_artifacts` (новый файл либо
переписанный ANSWER Оператора); предпосылка сверяется по сообщению последнего
коммита файла в ссылке документов. Элемент мандата — сам файл или его
каталог (случайно). Гейт зон наблюдается через `fsm.cmd_advance` из `in_dev`
(PLAN.md и SPEC.md `schema_version: 1` — в ссылке документов тем же
автокоммитом шага), чекпоинт перед подтяжкой — через `pull.evaluate` при
`main`, ушедшей вперёд коммитом в `pkg/`. Зерно печатается и входит в текст
каждого провала.
"""
import contextlib
import io
import os
import random
import unittest
from unittest import mock

from orchestrator import answer, checkpoint, config, fsm, pull, store, workspace
from orchestrator.advance_gates.zones import ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION
from tests.sandbox import RealGitSandbox

LETTERS = "ABCDEFGHJKMNPQRSTVWXYZ"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
ZONE = "pkg/"
ZONE_FILE = "pkg/mod.py"
MARKER = "Расширение зон разрешено:"
ROLE_AUTOCOMMIT_INFIX = ": артефакты шага "
OLD_ZONES_ACTION = "переход отклонён: гейт зон"
PULL_STRAY_ACTION = "переход отклонён: посторонние файлы в worktree"
PULL_STRAY_REASON = "посторонние файлы в worktree — решение Оператора"
DOCS_REF_PREFIX = "refs/artifacts/"

PLAN_TEXT = """---
task: TASK_ID
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: фикстура мандата зон

## Подход
Фикстура сценария.

## Шаги
1. Правка.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Нет.
"""

PLAN_SECTION = """
## Расширение зон

Пути: PATHS

Обоснование: мандат Оператора в ANSWER.
"""

SPEC_TEXT = """---
task: TASK_ID
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: фикстура мандата зон

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

# Варианты источника мандата сценария.
OPERATOR = "мандат в ANSWER Оператора"
NO_ANSWER = "ANSWER нет"
OTHER_PATH = "мандат Оператора на другой путь"
ROLE_NEW = "новый ANSWER автокоммитом роли"
ROLE_REWRITE = "ANSWER Оператора переписан автокоммитом роли"
WITHOUT_MANDATE = (NO_ANSWER, OTHER_PATH)
ROLE_FORGED = (ROLE_NEW, ROLE_REWRITE)


class ZoneMandateSandbox(RealGitSandbox):
    """Файл зоны и каталоги вне зон в `main`, задачи в `in_dev` с зонами `pkg/`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        patcher.start()
        self.addCleanup(patcher.stop)

        self.original = {ZONE_FILE: "VALUE = 1\n"}
        self.outside: dict[str, list[str]] = {}
        while len(self.outside) < 3:
            folder = "zq" + self.word(6) + "/"
            first, second = self.word(5), self.word(5)
            files = [folder + first + ".md", folder + second + ".py"]
            if folder in self.outside or first == second or any(
                    config.is_protected_path(f) for f in files):
                continue
            self.outside[folder] = files
            for rel in files:
                self.original[rel] = f"# {rel}\nисходный текст\n"
        for rel, text in self.original.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "зона задачи и каталоги вне зон")
        self.add_synced_origin()
        self.conn = store.db()
        self.serial = 0

    # --- входы -------------------------------------------------------------

    def word(self, size: int) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def explain(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def pick(self, form: str | None = None) -> tuple[str, str]:
        """(файл вне зон, элемент мандата на него: сам файл или его каталог)."""
        folder = self.rng.choice(sorted(self.outside))
        path = self.rng.choice(self.outside[folder])
        form = form or self.rng.choice(("файл", "каталог"))
        return path, (path if form == "файл" else folder)

    def other_entry(self, path: str) -> str:
        """Элемент мандата на путь вне зон, не покрывающий `path`."""
        folder = self.rng.choice([d for d in sorted(self.outside)
                                  if not path.startswith(d)])
        return self.rng.choice([folder, self.rng.choice(self.outside[folder])])

    # --- задача и её рабочая копия -----------------------------------------

    def new_task(self) -> tuple[str, object]:
        self.serial += 1
        task_id = ("01M0000000000000000000MN" + LETTERS[self.serial // len(LETTERS)]
                   + LETTERS[self.serial % len(LETTERS)])
        branch = f"task/fixture-zone-mandate-{self.serial}"
        store.insert_task(self.conn, task_id, "Фикстура мандата зон", "in_dev",
                          branch, config.DEFAULT_TARGET, 25.0)
        store.update_task(self.conn, task_id, zones=ZONE)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.explain(f"рабочая копия не заведена: {error}"))
        return task_id, wt

    def modify(self, wt, rel: str) -> str:
        text = f"# правка {rel} ({self.seed})\n"
        (wt / rel).write_text(text, encoding="utf-8")
        return text

    def head_text(self, wt, rel: str) -> str:
        return self.git("-C", str(wt), "show", f"HEAD:{rel}")

    def wt_status(self, wt, rel: str) -> str:
        return self.git("-C", str(wt), "status", "--porcelain", "--", rel)

    def run_cmd(self, fn, *args) -> tuple[str, bool]:
        """(вывод вместе с текстом отказа, был ли ненулевой `SystemExit`)."""
        buf = io.StringIO()
        failed = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    failed = True
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), failed

    # --- ссылка документов ---------------------------------------------------

    def docs_ref(self, task_id: str) -> str:
        return DOCS_REF_PREFIX + task_id

    def answers(self, task_id: str) -> list[str]:
        ref = self.docs_ref(task_id)
        if not self.git("for-each-ref", "--format=%(objectname)", ref).strip():
            return []
        return [p.rsplit("/", 1)[-1] for p in self.git(
            "ls-tree", "-r", "--name-only", ref).splitlines()
            if p.rsplit("/", 1)[-1].startswith("ANSWER-")]

    def last_subject(self, task_id: str, name: str) -> str:
        return self.git("log", "-1", "--format=%s", self.docs_ref(task_id), "--",
                        checkpoint.task_dir_zone(task_id) + name).strip()

    def operator_answer(self, task_id: str, entries: list[str]) -> str:
        """ANSWER Оператора командой `answer`; возврат — имя нового файла."""
        before = set(self.answers(task_id))
        source = self.root / ".artel" / f"answer-{self.rng.randrange(1 << 30)}.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"{MARKER} {', '.join(entries)}\n\nОснование: решение "
                          f"Оператора ({self.seed}).\n", encoding="utf-8")
        out, failed = self.run_cmd(answer.cmd_answer, task_id, str(source))
        self.assertFalse(failed, self.explain(f"answer отказала:\n{out}"))
        created = sorted(set(self.answers(task_id)) - before)
        self.assertEqual(len(created), 1, self.explain(f"ANSWER не создан:\n{out}"))
        self.assertNotIn(ROLE_AUTOCOMMIT_INFIX, self.last_subject(task_id, created[0]),
                         self.explain("предпосылка: ANSWER Оператора закоммичен "
                                      "автокоммитом роли"))
        return created[0]

    def role_files(self, task_id: str, wt, files: dict[str, str]) -> None:
        """Файлы каталога задачи, перенесённые в ссылку автокоммитом шага роли."""
        folder = wt / checkpoint.task_dir_zone(task_id)
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (folder / name).write_text(text, encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, task_id, "developer")

    def role_answer(self, task_id: str, wt, entries: list[str],
                    rewrite: str | None = None) -> str:
        """ANSWER со строкой мандата, последний коммит которого — автокоммит
        шага роли: новый файл либо переписанный `rewrite`."""
        if rewrite is None:
            numbers = [int(n[len("ANSWER-"):-len(".md")])
                       for n in self.answers(task_id)]
            rewrite = f"ANSWER-{max(numbers, default=0) + 1}.md"
        self.role_files(task_id, wt, {rewrite: (
            f"# Ответ\n\n{MARKER} {', '.join(entries)}\n\nНаписано ролью "
            f"({self.seed}).\n")})
        subject = self.last_subject(task_id, rewrite)
        self.assertTrue(subject.startswith(task_id + ROLE_AUTOCOMMIT_INFIX),
                        self.explain(f"предпосылка: последний коммит {rewrite} — "
                                     f"не автокоммит роли: {subject!r}"))
        return rewrite

    def mandate_source(self, task_id: str, wt, case: str, path: str,
                       entry: str) -> None:
        """Заводит источник мандата варианта `case` на путь `path`."""
        if case == OPERATOR:
            extra = [self.other_entry(path)] if self.rng.random() < 0.5 else []
            entries = [entry] + extra
            self.rng.shuffle(entries)
            self.operator_answer(task_id, entries)
        elif case == OTHER_PATH:
            self.operator_answer(task_id, [self.other_entry(path)])
        elif case == ROLE_NEW:
            self.role_answer(task_id, wt, [entry])
        elif case == ROLE_REWRITE:
            name = self.operator_answer(task_id, [entry])
            self.role_answer(task_id, wt, [entry], rewrite=name)

    def seed_docs(self, task_id: str, wt, section: list[str] | None = None) -> None:
        """PLAN.md `ready` (с разделом «## Расширение зон» на `section`) и
        SPEC.md `schema_version: 1` — в ссылке документов."""
        plan = PLAN_TEXT.replace("TASK_ID", task_id)
        if section is not None:
            plan += PLAN_SECTION.replace("PATHS", ", ".join(section))
        self.role_files(task_id, wt, {
            "PLAN.md": plan, "SPEC.md": SPEC_TEXT.replace("TASK_ID", task_id)})

    # --- журнал --------------------------------------------------------------

    def last_row_id(self, task_id: str) -> int:
        rows = store.task_steps(self.conn, task_id)
        return rows[-1]["id"] if rows else 0

    def rows_after(self, task_id: str, before: int) -> list[dict]:
        return [dict(r) for r in store.task_steps(self.conn, task_id)
                if r["id"] > before]

    def stray_named(self, rows: list[dict], rel: str) -> bool:
        return any(r["action"] == checkpoint.STRAY_WORKTREE_FILES_ACTION
                   and rel in (r["detail"] or "") for r in rows)

    def zones_gate_actions(self, rows: list[dict]) -> list[str]:
        return [r["action"] for r in rows if r["action"] in (
            OLD_ZONES_ACTION, ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION)]

    def state(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["state"]

    # --- сверки --------------------------------------------------------------

    def assert_committed(self, wt, rel: str, text: str, rows: list[dict],
                         note: str) -> None:
        self.assertEqual(self.head_text(wt, rel), text, self.explain(
            f"{note}: {rel} не вошёл в коммит пульта"))
        self.assertEqual(self.wt_status(wt, rel), "", self.explain(
            f"{note}: {rel} остался незакоммиченным в рабочей копии"))
        self.assertFalse(self.stray_named(rows, rel), self.explain(
            f"{note}: {rel} назван в записи «посторонние файлы в worktree»: {rows}"))

    def assert_unstaged(self, wt, rel: str, rows: list[dict], note: str) -> None:
        self.assertEqual(self.head_text(wt, rel), self.original[rel],
                         self.explain(f"{note}: {rel} вошёл в коммит пульта"))
        self.assertNotEqual(self.wt_status(wt, rel), "", self.explain(
            f"{note}: правка {rel} пропала из рабочей копии"))
        self.assertTrue(self.stray_named(rows, rel), self.explain(
            f"{note}: {rel} не назван в записи «посторонние файлы в worktree»: "
            f"{rows}"))

    def checkpoint_scenario(self, case: str, commit, form: str | None = None):
        """Сценарий одного чекпоинта: (рабочая копия, путь, текст правки,
        текст правки файла зоны, новые записи журнала)."""
        task_id, wt = self.new_task()
        path, entry = self.pick(form)
        self.mandate_source(task_id, wt, case, path, entry)
        zone_text = self.modify(wt, ZONE_FILE)
        text = self.modify(wt, path)
        before = self.last_row_id(task_id)
        commit(task_id)
        return wt, path, text, zone_text, self.rows_after(task_id, before)


class SuccessAutocommitTest(ZoneMandateSandbox):

    def success(self, task_id: str) -> None:
        checkpoint.commit_success_checkpoint(self.conn, task_id, "developer")

    def test_ac1_operator_mandate_path_enters_success_autocommit(self):
        """Файл вне зон по мандату ANSWER Оператора входит в автокоммит шага developer.

        Сценарий: для каждой формы элемента мандата (сам файл, его каталог)
        своя задача; Оператор командой `answer` выдаёт мандат (иногда вместе
        с элементом на другой каталог); шаг developer правит файл зоны и
        файл вне зон под мандатом; пульт делает автокоммит после шага. В
        HEAD рабочей копии — новый текст обоих файлов, файл вне зон в
        рабочей копии чист и не назван ни в одной записи «посторонние файлы
        в worktree».

        Ловит мутацию: фильтр автокоммита читает только zones/
        zones_extension/COMMON_ZONES — файл по мандату снимается со стейджа
        и называется посторонним; мандат на каталог сверяется равенством
        строк, а не вложенностью — файл под каталогом мандата снимается.
        """
        for form in ("файл", "каталог"):
            with self.subTest(form=form):
                wt, path, text, zone_text, rows = self.checkpoint_scenario(
                    OPERATOR, self.success, form)
                note = f"автокоммит, мандат на {form}"
                self.assert_committed(wt, path, text, rows, note)
                self.assertEqual(self.head_text(wt, ZONE_FILE), zone_text,
                                 self.explain(f"{note}: файл зоны не закоммичен"))

    def test_ac2_path_without_mandate_is_unstaged_from_success_autocommit(self):
        """Файл вне зон без мандата на него снимается со стейджа автокоммита и называется посторонним.

        Сценарий: две задачи — без ANSWER и с ANSWER Оператора, где мандат
        выдан на другой каталог или файл вне зон; шаг developer правит файл
        зоны и файл вне зон. Файл зоны закоммичен; файл вне зон в HEAD с
        прежним текстом, правка осталась в рабочей копии, путь назван в
        записи «посторонние файлы в worktree».

        Ловит мутацию: наличие ANSWER с маркером мандата снимает фильтр зон
        целиком, без сверки элементов мандата с путём, — файл без своего
        мандата войдёт в коммит и не будет назван посторонним.
        """
        for case in WITHOUT_MANDATE:
            with self.subTest(case=case):
                wt, path, _text, zone_text, rows = self.checkpoint_scenario(
                    case, self.success)
                self.assert_unstaged(wt, path, rows, f"автокоммит, {case}")
                self.assertEqual(self.head_text(wt, ZONE_FILE), zone_text,
                                 self.explain(f"{case}: файл зоны не закоммичен"))

    def test_ac3_answer_last_committed_by_role_autocommit_is_not_a_mandate(self):
        """ANSWER с мандатом, последний коммит которого — автокоммит шага роли, мандатом коммита пульта не считается.

        Сценарий: две задачи — новый ANSWER-n.md со строкой мандата на файл,
        положенный ролью в каталог задачи и перенесённый автокоммитом шага;
        ANSWER Оператора с тем же мандатом, переписанный ролью тем же путём.
        Предпосылка сверена по сообщению последнего коммита файла в ссылке
        документов («<id>: артефакты шага …»). Шаг developer правит файл вне
        зон — он снят со стейджа и назван посторонним, как без мандата.

        Ловит мутацию: коммит пульта читает мандат собственным разбором всех
        ANSWER-*.md без правила происхождения — роль, положившая себе
        ANSWER, протаскивает файл вне зон в коммит пульта.
        """
        for case in ROLE_FORGED:
            with self.subTest(case=case):
                wt, path, _text, _zone, rows = self.checkpoint_scenario(
                    case, self.success)
                self.assert_unstaged(wt, path, rows, f"автокоммит, {case}")

    def test_ac9_autocommit_record_names_mandate_paths_apart_from_zone_paths(self):
        """Запись журнала автокоммита называет пути, вошедшие по мандату, отдельно от путей зон.

        Сценарий: Оператор выдаёт мандат на один-два файла вне зон из разных
        каталогов (элемент — сам файл); шаг developer правит файл зоны
        `pkg/mod.py` и эти файлы; пульт делает автокоммит. Среди новых
        записей журнала есть запись со словом «мандат», где после первого
        упоминания мандата назван каждый путь мандата и между этим
        упоминанием и путём мандата не стоит путь зоны; путь зоны назван в
        новых записях. `pkg/` по алфавиту раньше каталогов `zq…`, поэтому
        общий список закоммиченных путей ставит путь зоны первым.

        Ловит мутацию: запись автокоммита осталась прежней сводкой «пути (N
        строк)» без выделения мандата — слова «мандат» рядом с путём нет;
        под меткой мандата перечислены все закоммиченные пути подряд — путь
        зоны стоит между меткой и путём мандата.
        """
        task_id, wt = self.new_task()
        folders = self.rng.sample(sorted(self.outside), self.rng.randrange(1, 3))
        paths = sorted(self.rng.choice(self.outside[f]) for f in folders)
        self.operator_answer(task_id, paths)
        self.modify(wt, ZONE_FILE)
        for rel in paths:
            self.modify(wt, rel)
        before = self.last_row_id(task_id)

        self.success(task_id)

        rows = self.rows_after(task_id, before)
        texts = [f"{r['action']} | {r['detail'] or ''}" for r in rows]
        self.assertTrue(any(ZONE_FILE in t for t in texts), self.explain(
            f"путь зоны не назван в записях автокоммита: {texts}"))
        for rel in paths:
            with self.subTest(path=rel):
                separated = []
                for t in texts:
                    at = t.lower().find("мандат")
                    if at < 0:
                        continue
                    tail = t[at:]
                    pos = tail.find(rel)
                    if pos >= 0 and ZONE_FILE not in tail[:pos]:
                        separated.append(t)
                self.assertTrue(separated, self.explain(
                    f"нет записи, называющей {rel} как путь мандата отдельно от "
                    f"пути зоны: {texts}"))


class TimeoutCheckpointTest(ZoneMandateSandbox):

    def timeout(self, task_id: str) -> None:
        checkpoint.commit_timeout_checkpoint(self.conn, task_id, "developer")

    def test_ac4_timeout_checkpoint_follows_operator_mandate_only(self):
        """WIP-чекпоинт после таймаута коммитит файл по мандату Оператора и снимает файл без мандата.

        Сценарий: по задаче на каждый вариант — мандат Оператора на файл вне
        зон; без мандата (ANSWER нет либо мандат на другой путь, случайно);
        ANSWER с мандатом, закоммиченный автокоммитом роли (новый либо
        переписанный, случайно). Шаг developer правит файл вне зон и
        обрывается таймаутом. С мандатом Оператора файл в HEAD с новым
        текстом и не назван посторонним; в двух других вариантах он снят со
        стейджа и назван в записи «посторонние файлы в worktree».

        Ловит мутацию: мандат подключён только к автокоммиту успешного шага
        (`commit_success_checkpoint`), а WIP-чекпоинт по-прежнему фильтрует
        по одним зонам — файл по мандату снимается; либо WIP-чекпоинт берёт
        мандат без правила происхождения — ANSWER роли протаскивает файл.
        """
        cases = (OPERATOR, self.rng.choice(WITHOUT_MANDATE),
                 self.rng.choice(ROLE_FORGED))
        for case in cases:
            with self.subTest(case=case):
                wt, path, text, _zone, rows = self.checkpoint_scenario(
                    case, self.timeout)
                note = f"чекпоинт таймаута, {case}"
                if case == OPERATOR:
                    self.assert_committed(wt, path, text, rows, note)
                else:
                    self.assert_unstaged(wt, path, rows, note)


class PullCheckpointTest(ZoneMandateSandbox):

    def advance_main(self) -> str:
        """`main` уходит вперёд коммитом кода в `pkg/`; возврат — sha `main`."""
        rel = f"{ZONE}main_{self.word(6)}.py"
        (self.root / rel).write_text(f"MAIN = {self.seed}\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "main ушла вперёд")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        return self.git("rev-parse", config.MAIN_BRANCH).strip()

    def test_ac5_pull_checkpoint_commits_mandate_path_and_refuses_without_it(self):
        """Чекпоинт перед подтяжкой main коммитит файл по мандату Оператора, без мандата — прежний отказ перехода.

        Сценарий: по задаче на каждый вариант — мандат Оператора; без
        мандата (ANSWER нет либо мандат на другой путь, случайно); ANSWER
        автокоммитом роли (новый либо переписанный, случайно). В рабочей
        копии — незакоммиченная правка файла вне зон, `main` ушла вперёд
        коммитом кода, подтяжка — `pull.evaluate`. С мандатом Оператора
        исход не `Refused`, записи «переход отклонён: посторонние файлы в
        worktree» нет, файл в HEAD с новым текстом. В двух других вариантах
        исход `Refused` с причиной «посторонние файлы в worktree — решение
        Оператора», называющей файл, запись отказа в журнале есть, файл в
        HEAD с прежним текстом.

        Ловит мутацию: мандат подключён к автокоммиту и WIP-чекпоинтам, но
        не к `commit_pull_checkpoint` (`refuse_on_stray=True`) — подтяжка
        отказывает на файле по мандату; либо отказ подтяжки сверяет
        посторонние по своему списку зон без мандата — тот же отказ.
        """
        cases = (OPERATOR, self.rng.choice(WITHOUT_MANDATE),
                 self.rng.choice(ROLE_FORGED))
        for case in cases:
            with self.subTest(case=case):
                task_id, wt = self.new_task()
                path, entry = self.pick()
                self.mandate_source(task_id, wt, case, path, entry)
                text = self.modify(wt, path)
                base = self.advance_main()
                before = self.last_row_id(task_id)

                outcome = pull.evaluate(
                    self.conn, task_id, store.get_task(self.conn, task_id),
                    "in_dev",
                    origin_main_source=lambda name: ("origin", config.MAIN_BRANCH),
                    origin_main_sha=lambda name: base,
                    read_branch_text_or_refuse=lambda conn, tid, branch, rel:
                        SPEC_TEXT.replace("TASK_ID", tid))

                rows = self.rows_after(task_id, before)
                refusals = [r for r in rows if r["action"] == PULL_STRAY_ACTION]
                note = f"подтяжка, {case}: исход {outcome!r}"
                if case == OPERATOR:
                    self.assertNotIsInstance(outcome, pull.Refused,
                                             self.explain(note))
                    self.assertEqual(refusals, [], self.explain(note))
                    self.assertEqual(self.head_text(wt, path), text, self.explain(
                        f"{note}: {path} не закоммичен"))
                else:
                    self.assertIsInstance(outcome, pull.Refused, self.explain(note))
                    self.assertIn(PULL_STRAY_REASON, outcome.reason or "",
                                  self.explain(note))
                    self.assertIn(path, outcome.reason or "", self.explain(note))
                    self.assertTrue(refusals, self.explain(f"{note}: {rows}"))
                    self.assertEqual(self.head_text(wt, path), self.original[path],
                                     self.explain(f"{note}: {path} закоммичен"))


class OtherFilterPlacesTest(ZoneMandateSandbox):

    def test_ac6_abnormal_and_pause_now_checkpoints_follow_mandate(self):
        """WIP-чекпоинты аварийного завершения и `pause --now` коммитят файл по мандату и снимают файл без мандата.

        Сценарий: для каждого из двух чекпоинтов — задача с мандатом
        Оператора на файл вне зон и задача без мандата (ANSWER нет либо
        мандат на другой путь, случайно); шаг developer правит файл вне зон
        и завершается аварийно (`rc=1`) либо прерывается `pause --now`. С
        мандатом файл в HEAD с новым текстом и не назван посторонним; без
        мандата снят со стейджа и назван в записи «посторонние файлы в
        worktree».

        Ловит мутацию: мандат подключён к таймауту и автокоммиту, а общий
        помощник WIP-чекпоинтов вызывается для аварии/`pause --now` мимо
        него (своя ветка с прежним фильтром) — файл по мандату снимается;
        либо мандат применяется без сверки покрытия — файл без мандата
        коммитится.
        """
        checkpoints = {
            "аварийное завершение": lambda task_id: checkpoint.commit_abnormal_checkpoint(
                self.conn, task_id, "developer", "rc=1"),
            "pause --now": lambda task_id: checkpoint.commit_pause_now_checkpoint(
                self.conn, task_id, "developer"),
        }
        for label, commit in checkpoints.items():
            for case in (OPERATOR, self.rng.choice(WITHOUT_MANDATE)):
                with self.subTest(checkpoint=label, case=case):
                    wt, path, text, _zone, rows = self.checkpoint_scenario(
                        case, commit)
                    note = f"{label}, {case}"
                    if case == OPERATOR:
                        self.assert_committed(wt, path, text, rows, note)
                    else:
                        self.assert_unstaged(wt, path, rows, note)

    def test_ac6_restore_deletions_treats_mandate_path_as_zone(self):
        """Восстановление удалений developer не возвращает файл, удалённый по мандату, и возвращает файл без мандата.

        Сценарий: задача с мандатом Оператора на отслеживаемый файл вне зон
        (элемент — файл или его каталог) и задача без мандата; шаг developer
        удаляет этот файл в рабочей копии, затем
        `checkpoint.restore_out_of_bounds_deletions` для developer. С
        мандатом путь не в списке восстановленных и файла на диске нет; без
        мандата путь восстановлен с прежним текстом.

        Ловит мутацию: `restore_out_of_bounds_deletions` берёт зоны прежним
        списком без мандата — удаление по мандату откатывается из HEAD;
        мандат засчитывается без сверки покрытия — удаление без мандата
        остаётся.
        """
        for case in (OPERATOR, self.rng.choice(WITHOUT_MANDATE)):
            with self.subTest(case=case):
                task_id, wt = self.new_task()
                path, entry = self.pick()
                self.mandate_source(task_id, wt, case, path, entry)
                (wt / path).unlink()

                restored = checkpoint.restore_out_of_bounds_deletions(
                    self.conn, task_id, "developer", wt)

                note = f"восстановление удалений, {case}: {restored}"
                if case == OPERATOR:
                    self.assertNotIn(path, restored, self.explain(note))
                    self.assertFalse((wt / path).exists(), self.explain(note))
                else:
                    self.assertIn(path, restored, self.explain(note))
                    self.assertEqual((wt / path).read_text(encoding="utf-8"),
                                     self.original[path], self.explain(note))

    def test_ac6_pult_commit_failed_paths_counts_mandate_path_as_zone(self):
        """После отказа git на коммите пульта незакоммиченный файл по мандату назван результатом шага, файл без мандата — нет.

        Сценарий: задача с мандатом Оператора на файл вне зон и задача без
        мандата; в рабочей копии незакоммиченные правки файла зоны и этого
        файла, в журнале — свежая запись `PULT_COMMIT_GIT_FAILED_ACTION`.
        `checkpoint.pult_commit_failed_paths` с мандатом называет оба пути;
        без мандата — путь зоны и не называет путь вне зон.

        Ловит мутацию: `pult_commit_failed_paths` сверяет пути прежним
        списком зон без мандата — файл по мандату выпадает из результата
        шага, и переход не узнаёт о его незакоммиченности.
        """
        for case in (OPERATOR, self.rng.choice(WITHOUT_MANDATE)):
            with self.subTest(case=case):
                task_id, wt = self.new_task()
                path, entry = self.pick()
                self.mandate_source(task_id, wt, case, path, entry)
                self.modify(wt, ZONE_FILE)
                self.modify(wt, path)
                store.journal(self.conn, task_id, "orchestrator",
                              checkpoint.PULT_COMMIT_GIT_FAILED_ACTION,
                              f"{task_id}: git commit (rc=1): фикстура {self.seed}")

                found = checkpoint.pult_commit_failed_paths(self.conn, task_id)

                note = f"pult_commit_failed_paths, {case}: {found}"
                self.assertIsNotNone(found, self.explain(note))
                self.assertIn(ZONE_FILE, found, self.explain(note))
                if case == OPERATOR:
                    self.assertIn(path, found, self.explain(note))
                else:
                    self.assertNotIn(path, found, self.explain(note))


class GateParityTest(ZoneMandateSandbox):

    def gate_verdict(self, task_id: str) -> tuple[str, list[dict]]:
        """(действие отказа гейта зон на `advance` из `in_dev`, новые записи)."""
        before = self.last_row_id(task_id)
        out, _failed = self.run_cmd(fsm.cmd_advance, task_id)
        rows = self.rows_after(task_id, before)
        actions = self.zones_gate_actions(rows)
        self.assertEqual(len(actions), 1, self.explain(
            f"гейт зон не вынес ровно один отказ: {actions}\n{out}\n{rows}"))
        return actions[0], rows

    def test_ac7_gate_and_pult_commit_agree_on_mandate_paths(self):
        """Гейт зон и автокоммит пульта одинаково решают, покрыт ли путь мандатом.

        Сценарий: четыре задачи со случайным набором ANSWER — мандаты
        Оператора на путь и на другие пути вне зон, ANSWER роли с мандатом на
        путь (новые и переписанные ANSWER Оператора); в чётных задачах путь
        покрыт действующим мандатом Оператора, в нечётных — нет (мандат на
        него есть только в ANSWER роли или его нет вовсе). Шаг developer
        правит файл зоны и путь, пульт делает автокоммит, затем `advance` из
        `in_dev` с PLAN.md без раздела «## Расширение зон». Гейт признал
        путь покрытым, когда его отказ — «мандат есть, раздел PLAN не
        оформлен», и непокрытым при прежнем «переход отклонён: гейт зон»;
        коммит признал путь своим, когда HEAD несёт его новый текст. Оба
        вердикта совпадают друг с другом и с ожидаемым по набору ANSWER.

        Ловит мутацию: коммит пульта получил собственную копию разбора
        мандата, расходящуюся с гейтом — без правила исключения ANSWER
        автокоммита роли (коммит берёт путь, гейт — нет) или только по
        последнему ANSWER-n.md вместо всех (коммит снимает путь, который гейт
        признаёт покрытым).
        """
        for index in range(4):
            covered = index % 2 == 0
            with self.subTest(scenario=index, covered=covered):
                task_id, wt = self.new_task()
                self.seed_docs(task_id, wt)
                path, entry = self.pick()
                story = self.random_answers(task_id, wt, path, entry, covered)
                self.modify(wt, ZONE_FILE)
                text = self.modify(wt, path)
                checkpoint.commit_success_checkpoint(self.conn, task_id,
                                                     "developer")
                commit_covered = self.head_text(wt, path) == text

                action, rows = self.gate_verdict(task_id)
                gate_covered = action == ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION

                note = (f"сценарий {index}: путь {path}, элемент {entry}, "
                        f"ANSWER: {story}; гейт: {action}")
                self.assertEqual(gate_covered, covered, self.explain(
                    f"{note} — гейт разошёлся с набором ANSWER: {rows}"))
                self.assertEqual(commit_covered, gate_covered, self.explain(
                    f"{note} — коммит пульта разошёлся с гейтом зон"))

    def random_answers(self, task_id: str, wt, path: str, entry: str,
                       covered: bool) -> list[str]:
        """Случайный набор ANSWER; путь покрыт действующим мандатом Оператора
        ровно при `covered`. Возврат — описание набора для текста провала."""
        plan = []
        if covered:
            plan.append(("оператор", [entry]))
        for _ in range(self.rng.randrange(0, 2)):
            plan.append(("оператор", [self.other_entry(path)]))
        decoys = ["роль: новый"] * self.rng.randrange(0 if covered else 1, 3)
        if not covered and self.rng.random() < 0.5:
            plan.append(("оператор, потом роль", [entry]))
        self.rng.shuffle(plan)
        story = []
        victims = []
        for kind, entries in plan:
            name = self.operator_answer(task_id, entries)
            story.append(f"{name} {kind}: {entries}")
            if kind == "оператор, потом роль":
                victims.append(name)
        for name in victims:
            self.role_answer(task_id, wt, [entry], rewrite=name)
        for kind in decoys:
            name = self.role_answer(task_id, wt, [entry])
            story.append(f"{name} {kind}: {[entry]}")
        return story

    def test_ac8_zones_gate_still_requires_plan_section_for_committed_mandate_file(self):
        """Файл, закоммиченный автокоммитом по мандату, без раздела PLAN даёт прежний отказ гейта зон, с разделом — переход проходит.

        Сценарий: мандат Оператора на файл вне зон (элемент — файл или его
        каталог); шаг developer правит его, автокоммит пульта коммитит его
        (предпосылка сверена по HEAD). `advance` из `in_dev` с PLAN.md без
        раздела «## Расширение зон» — отказ гейта зон
        `ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION`, задача в `in_dev`.
        После того как PLAN.md получил раздел с тем же путём, что в мандате,
        повторный `advance` проходит: задача в `verifying`, отказов гейта
        зон среди новых записей нет, HEAD по-прежнему несёт файл.

        Ловит мутацию: путь мандата влит в общий список зон и для гейта зон
        (одна функция зон для коммита и гейта) — гейт пропускает файл по
        мандату без раздела PLAN, первый `advance` уводит задачу в
        `verifying`; либо гейт перестал узнавать уже закоммиченный файл как
        покрытый мандатом — с разделом переход отклонён.
        """
        task_id, wt = self.new_task()
        self.seed_docs(task_id, wt)
        path, entry = self.pick()
        self.operator_answer(task_id, [entry])
        text = self.modify(wt, path)
        checkpoint.commit_success_checkpoint(self.conn, task_id, "developer")
        self.assertEqual(self.head_text(wt, path), text, self.explain(
            f"предпосылка: {path} по мандату {entry} не закоммичен автокоммитом"))

        action, rows = self.gate_verdict(task_id)
        self.assertEqual(action, ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION,
                         self.explain(f"без раздела PLAN: {rows}"))
        self.assertEqual(self.state(task_id), "in_dev", self.explain(
            "без раздела PLAN задача ушла из in_dev"))

        self.seed_docs(task_id, wt, section=[entry])
        before = self.last_row_id(task_id)
        out, _failed = self.run_cmd(fsm.cmd_advance, task_id)
        rows = self.rows_after(task_id, before)
        self.assertEqual(self.zones_gate_actions(rows), [], self.explain(
            f"с разделом PLAN гейт зон отказал: {rows}\n{out}"))
        self.assertEqual(self.state(task_id), "verifying", self.explain(
            f"с разделом PLAN переход не прошёл: {rows}\n{out}"))
        self.assertEqual(self.head_text(wt, path), text, self.explain(
            f"после перехода HEAD не несёт {path}"))


if __name__ == "__main__":
    unittest.main()
