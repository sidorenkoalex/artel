"""Мандат на ослабление тестов и матрица неослабления при записи ответа —
по области ослабления профиля проекта задачи (AC-1..AC-6).

Группа: долгоживущий
Красен до реализации: проверка элемента мандата ослабления при записи (`mandate.refusals`) знает только область артели `tests/**/*.py` и решения профиля задачи не читает, а ссылку на тест в матрице распознаёт только как `tests/…` — поэтому у внешнего проекта `answer` отказывает верному `backend/tests/…` текстом области артели и принимает `tests/…` (AC-2, AC-3), принимает мандат при отказе и пропуске решения профиля (AC-4, AC-6) и судит матрицу внешнего проекта по `tests/…` (AC-5); половина артели (AC-1, артельная часть AC-5) держит сегодняшнее поведение и зелёная с рождения.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): корень — клон
артели с bare `origin`, внешний проект — свой клон с bare `origin`
(`tests.sandbox.make_project_repo`). `targets.yaml` песочницы пишется
сценарием: запись артели — с её профилем тестов (`artel_target_entry`),
учебного внешнего проекта — с `weakening_scope: [backend/tests/**/*.py]`.
Задачи заводятся в `in_dev` прямой записью БД, рабочая копия —
`workspace.ensure`, документы задачи — автокоммитом шага
(`checkpoint.commit_step_artifacts`). Каналы — публичные команды
`answer.cmd_answer` и `answer.cmd_zones_extend`, переход —
`fsm.cmd_advance`; наблюдаются вывод команды (с текстом отказа), файлы
`ANSWER-n.md` в ссылке документов задачи и записи её журнала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
решение профиля задачи в `mandate.refusals` (отказ/пропуск — причина
решения, профиль — его маски, у артели — прежний текст) и область профиля
в проверке ссылки матрицы обоих каналов — все методы зелёные.

Имена файлов, классов и методов тестов в мандатах — случайные при каждом
запуске; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import unittest
from unittest import mock

from orchestrator import (answer, checkpoint, config, fsm, github_adapter,
                          idgen, project_profile, store, workspace)
from orchestrator.advance_gates import mandate, test_integrity
from tests.sandbox import (RealGitSandbox, artel_target_entry,
                           make_project_repo)

ARTEL = config.DEFAULT_TARGET
EXT = "uchebnyy"
SCOPE_DIR = "backend/tests"
SCOPE_MASK = f"{SCOPE_DIR}/**/*.py"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
SEP = "::"

WEAKENING = mandate.TEST_WEAKENING_MANDATE_MARKER
ZONES = "Расширение зон разрешено:"
ARTEL_REFUSAL = ("путь вне области tests/**/*.py — гейт неослабления "
                 "тестов другие пути не рассматривает")
INDEPENDENT_CHECK = "Независимая проверка: матрица подтверждена Оператором"

EXT_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

EXT_PROFILE = f"""    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: {SCOPE_DIR}
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [{SCOPE_MASK}]
      mutation_claim_scope: [{SCOPE_DIR}/**/test_*.py]
      report: junit-xml
      install: []
"""

MATRIX_HEADERS = ("Что меняется", "Какое свойство сейчас держит",
                  "Остаётся ли свойство после изменения",
                  "Чем покрыто после", "Решение")

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: фикстура мандата ослабления

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

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: фикстура мандата ослабления

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""


def matrix(elements, covered_by: str) -> str:
    """Раздел матрицы неослабления: одна строка данных, называющая все
    `elements`; свойство остаётся, «Чем покрыто после» — `covered_by`,
    «Решение» — «ок» (без «ок при условии»)."""
    row = (", ".join(f"`{e}`" for e in elements), "фикстура сценария", "да",
           covered_by, "ок")
    return ("## Матрица неослабления\n\n"
            "| " + " | ".join(MATRIX_HEADERS) + " |\n"
            + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
            + "| " + " | ".join(row) + " |\n")


def class_source(cls: str, methods) -> str:
    body = "".join(f"\n    def {m}(self):\n        self.assertEqual(1, 1)\n"
                   for m in methods)
    return f"import unittest\n\n\nclass {cls}(unittest.TestCase):\n{body}"


class MandateScopeSandbox(RealGitSandbox):
    """Клон артели и клон учебного внешнего проекта; задачи в `in_dev`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        for patcher in (mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                        mock.patch.object(github_adapter, "ensure_draft_mr",
                                          lambda conn, task_id, t: None),
                        mock.patch("orchestrator.doctor.preflight_checks",
                                   lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
        self.ext_clone = make_project_repo(EXT)
        self.conn = store.db()
        self.write_targets()

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def ext_test_path(self) -> str:
        """Путь файла тестов под областью учебного проекта — на случайной
        глубине под `backend/tests/`."""
        subdirs = "".join(f"{self.word(4)}/"
                          for _ in range(self.rng.randrange(0, 3)))
        return f"{SCOPE_DIR}/{subdirs}test_{self.word()}.py"

    def qualified(self, path: str) -> str:
        return f"{path}{SEP}C{self.word().capitalize()}{SEP}test_{self.word()}"

    def why(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # -------------------------------------------------------- targets.yaml

    def write_targets(self, artel_profile: bool = True,
                      extra: str = "") -> None:
        """`targets.yaml` песочницы: артель (с профилем или без),
        учебный проект с профилем и хвост `extra` (записи сценария)."""
        artel = artel_target_entry()
        if not artel_profile:
            artel = artel.split("    test_profile:", 1)[0]
        text = ("targets:\n" + artel
                + EXT_ENTRY.format(name=EXT, base=config.MAIN_BRANCH)
                + EXT_PROFILE + extra)
        config.TARGETS.write_text(text, encoding="utf-8")

    # ------------------------------------------------------- задача и ветка

    def new_task(self, target: str, code: dict | None = None,
                 zones: str | None = None) -> str:
        """Задача `target` в `in_dev` с рабочей копией, кодом `code`
        ({путь: текст}, пусто — один файл кода) в ветке и PLAN.md/SPEC.md в
        ссылке документов."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-mandat"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          "in_dev", branch, target, config.DEFAULT_BUDGET_USD)
        if zones:
            store.update_task(self.conn, task_id, zones=zones)
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.why(f"рабочая копия не заведена: {error}"))
        self.code_path = f"pk{self.word()}/m{self.word()}.py"
        for rel, text in (code or {self.code_path: "X = 1\n"}).items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if text is None:
                path.unlink()
            else:
                path.write_text(text, encoding="utf-8")
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", f"{task_id}: код задачи")
        docs = config.PROJECTS / target / "tasks" / task_id
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "PLAN.md").write_text(PLAN_TEXT.format(task=task_id),
                                      encoding="utf-8")
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=task_id),
                                      encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, task_id, "developer")
        return task_id

    def commit_ext_base(self, rel: str, text: str) -> None:
        """Файл `rel` на базовой ветке клона учебного проекта и в его
        `origin` — до заведения рабочей копии задачи."""
        path = self.ext_clone / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        clone = str(self.ext_clone)
        self.git("-C", clone, "add", "-A")
        self.git("-C", clone, "commit", "-q", "-m", "база тестов")
        self.git("-C", clone, "push", "-q", "origin", config.MAIN_BRANCH)

    # -------------------------------------------------------------- каналы

    def run_cmd(self, fn, *args) -> tuple:
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

    def text_file(self, text: str) -> str:
        path = self.root / ".artel" / f"vvod-{self.rng.randrange(1 << 30)}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def weakening_answer(self, task_id: str, element: str,
                         covered_by: str) -> tuple:
        """`answer` с мандатом ослабления на `element`, строкой
        независимой проверки и годной по форме матрицей."""
        text = (f"{WEAKENING} {element}\n\n"
                f"Основание: решение Оператора ({self.seed}).\n\n"
                f"{INDEPENDENT_CHECK}\n\n" + matrix([element], covered_by))
        return self.run_cmd(answer.cmd_answer, task_id, self.text_file(text))

    def answers(self, task_id: str) -> list:
        """Файлы `ANSWER-n.md` ссылки документов задачи в клоне её проекта."""
        repo = str(workspace.task_repo(task_id))
        ref = f"refs/artifacts/{task_id}"
        if not self.git("-C", repo, "for-each-ref", "--format=%(objectname)",
                        ref).strip():
            return []
        return [line for line in self.git("-C", repo, "ls-tree", "-r",
                                          "--name-only", ref).splitlines()
                if line.rsplit("/", 1)[-1].startswith("ANSWER-")]

    def advance(self, task_id: str) -> tuple:
        """(новые записи журнала задачи, вывод `advance`)."""
        rows = store.task_steps(self.conn, task_id)
        before = rows[-1]["id"] if rows else 0
        out, _failed = self.run_cmd(fsm.cmd_advance, task_id)
        return [dict(r) for r in store.task_steps(self.conn, task_id)
                if r["id"] > before], out

    @staticmethod
    def text_of(rows, out: str) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in rows) + "\n--- вывод:\n" + out


# AC-1 -----------------------------------------------------------------------

class ArtelMandateUnchangedTest(MandateScopeSandbox):

    def test_ac1_artel_answer_and_bare_refusals_keep_artel_scope(self):
        """У артели `answer` принимает `tests/…::T::m` и отказывает `backend/tests/…` прежним текстом; `mandate.refusals` без задачи — так же.

        Задача артели в `in_dev`. Файл ответа с мандатом на случайный
        `tests/<…>/test_<…>.py::C…::test_…` (матрица годна, покрытие —
        `tests/…`) принимается: `ANSWER-1.md` в ссылке документов. Файл с
        мандатом на `backend/tests/test_<…>.py` отказывает текстом «путь
        вне области tests/**/*.py — гейт неослабления тестов другие пути не
        рассматривает», второго ANSWER нет. Те же два элемента через
        `mandate.refusals(текст, None)` без `conn`/`task_id`: первый — без
        отказов, второй — один отказ с тем же текстом.

        Ловит мутацию: область при записи берётся из профиля для любой
        задачи и без профиля падает в маску внешнего вида (или текст отказа
        артели переписан под маску профиля) — исправный артельный мандат
        отказывает либо отказ `backend/tests/…` не несёт прежнего текста;
        без задачи `refusals` перестаёт отказывать `backend/tests/…`.
        """
        task_id = self.new_task(ARTEL)
        good = self.qualified(f"tests/{self.word(4)}/test_{self.word()}.py")
        bad = f"{SCOPE_DIR}/test_{self.word()}.py"

        out, failed = self.weakening_answer(task_id, good,
                                            f"tests/test_{self.word()}.py")
        self.assertFalse(failed, self.why(f"answer отказала {good}:\n{out}"))
        self.assertEqual(1, len(self.answers(task_id)), self.why(out))

        out, failed = self.weakening_answer(task_id, bad,
                                            f"tests/test_{self.word()}.py")
        self.assertTrue(failed, self.why(f"answer приняла {bad}:\n{out}"))
        self.assertIn(ARTEL_REFUSAL, out, self.why(out))
        self.assertEqual(1, len(self.answers(task_id)),
                         self.why(f"ANSWER создан при отказе:\n{out}"))

        self.assertEqual([], mandate.refusals(f"{WEAKENING} {good}\n", None),
                         self.why(good))
        found = mandate.refusals(f"{WEAKENING} {bad}\n", None)
        self.assertEqual(1, len(found), self.why(str(found)))
        self.assertIn(ARTEL_REFUSAL, found[0], self.why(found[0]))
        self.assertIn(bad, found[0], self.why(found[0]))


# AC-2 -----------------------------------------------------------------------

class ExternalMandateScopeTest(MandateScopeSandbox):

    def test_ac2_external_answer_uses_project_weakening_scope(self):
        """У учебного проекта `answer` принимает `backend/tests/…::T::m` и отказывает `tests/…`, называя область `backend/tests/**/*.py`.

        Задача учебного внешнего проекта в `in_dev`. Мандат на случайный
        путь под `backend/tests/` (случайная глубина) с `::Класс::метод`
        принимается: `ANSWER-1.md` в ссылке документов клона проекта.
        Мандат на `tests/test_<…>.py` отказывает, текст отказа называет
        маску `backend/tests/**/*.py`, нового ANSWER нет.

        Ловит мутацию: проверка при записи по-прежнему зовёт
        `mandate.in_weakening_scope` (область артели) для задачи с профилем
        — верный путь проекта отказан, `tests/…` принят; текст отказа
        называет зашитую `tests/**/*.py` вместо масок профиля — маски
        `backend/tests/**/*.py` в выводе нет.
        """
        task_id = self.new_task(EXT)
        good = self.qualified(self.ext_test_path())
        bad = f"tests/test_{self.word()}.py"

        out, failed = self.weakening_answer(task_id, good, self.ext_test_path())
        self.assertFalse(failed, self.why(f"answer отказала {good}:\n{out}"))
        self.assertEqual(1, len(self.answers(task_id)), self.why(out))

        out, failed = self.weakening_answer(task_id, bad, self.ext_test_path())
        self.assertTrue(failed, self.why(f"answer приняла {bad}:\n{out}"))
        self.assertIn(bad, out, self.why(out))
        self.assertIn(SCOPE_MASK, out, self.why(out))
        self.assertEqual(1, len(self.answers(task_id)),
                         self.why(f"ANSWER создан при отказе:\n{out}"))


# AC-3 -----------------------------------------------------------------------

class ExternalMandateCountsAtGateTest(MandateScopeSandbox):

    def test_ac3_accepted_external_mandate_covers_gate_finding(self):
        """Мандат, принятый `answer` у внешнего проекта, снимает находку гейта неослабления на переходе `in_dev -> verifying`.

        На базе клона учебного проекта — файл тестов под `backend/tests/`
        (случайная глубина) с классом из двух методов; в ветке задачи один
        метод удалён. Первый `advance` без мандата пишет отказ гейта
        неослабления, называющий файл, задача остаётся в `in_dev`. Затем
        `answer` с мандатом `путь::Класс::удалённый_метод` принимается,
        журнал получает завершение шага developer (ANSWER отработан), и
        второй `advance` отказа гейта неослабления не пишет, а запись
        «ослабление тестов разрешено мандатом Оператора» называет файл.

        Ловит мутацию: `answer` проверяет элемент по области артели — мандат
        отказан, ANSWER нет, второй `advance` снова отказывает; проверка при
        записи берёт область не той формулой, что гейт (например, точное
        `backend/tests/*.py` без `**`), — мандат на файл во вложенном
        каталоге отказан при записи, хотя гейт его находку назвал.
        """
        path = self.ext_test_path()
        cls = f"C{self.word().capitalize()}"
        removed, kept = f"test_{self.word()}_a", f"test_{self.word()}_b"
        self.commit_ext_base(path, class_source(cls, [removed, kept]))
        task_id = self.new_task(EXT, code={path: class_source(cls, [kept])},
                                zones="backend/")

        rows, out = self.advance(task_id)
        refusals = [r for r in rows if r["action"]
                    == test_integrity.TEST_INTEGRITY_REFUSAL_ACTION]
        self.assertTrue(refusals, self.why("без мандата гейт не отказал:\n"
                                           + self.text_of(rows, out)))
        self.assertIn(path, refusals[0]["detail"] or "",
                      self.why(self.text_of(rows, out)))
        self.assertEqual("in_dev", store.get_task(self.conn, task_id)["state"],
                         self.why(self.text_of(rows, out)))

        element = f"{path}{SEP}{cls}{SEP}{removed}"
        out, failed = self.weakening_answer(task_id, element,
                                            f"{path}{SEP}{cls}{SEP}{kept}")
        self.assertFalse(failed, self.why(f"answer отказала {element}:\n{out}"))
        # Шаг developer после ANSWER (бриф несёт мандат): без него переход
        # держит гейт неотработанного ANSWER, до гейта неослабления не дойдя.
        store.journal(self.conn, task_id, "developer", "agent run finished")

        rows, out = self.advance(task_id)
        self.assertFalse(
            [r for r in rows
             if r["action"] == test_integrity.TEST_INTEGRITY_REFUSAL_ACTION],
            self.why("с мандатом гейт отказал:\n" + self.text_of(rows, out)))
        allowed = [r for r in rows if r["action"]
                   == test_integrity.TEST_INTEGRITY_ALLOWED_ACTION]
        self.assertTrue(allowed and path in (allowed[0]["detail"] or ""),
                        self.why("нет записи «разрешено» о файле:\n"
                                 + self.text_of(rows, out)))


# AC-4 -----------------------------------------------------------------------

class ProfileDecisionRefusesMandateTest(MandateScopeSandbox):

    def test_ac4_profile_refusal_or_skip_refuses_mandate_with_reason(self):
        """Решение профиля задачи — пропуск или отказ: `answer` с мандатом ослабления отказывает, называя причину решения, ANSWER нет.

        Пропуск — внешний проект без `test_profile`; отказ — внешний
        проект, чьё поле `test_profile` не читается (подполе неверного
        типа — `targets.yaml` не проходит проверку). Для каждого случая задача в `in_dev`, мандат на путь, верный
        для области учебного проекта. Предпосылка фикстуры — решение
        `project_profile.for_task` действительно пропуск/отказ; текст этой
        причины — в выводе отказа `answer`, ANSWER не создан.

        Ловит мутацию: при пропуске или отказе решения проверка падает в
        запасную область артели или в «профиля нет — проверять нечем,
        принять» — мандат на `tests/…`/`backend/tests/…` принят либо
        отказан текстом об области, без причины решения профиля.
        """
        skip_target, broken_target = f"bez{self.word(4)}", f"lom{self.word(4)}"
        make_project_repo(skip_target)
        make_project_repo(broken_target)
        good_profile = (EXT_ENTRY.format(name=broken_target,
                                         base=config.MAIN_BRANCH)
                        + EXT_PROFILE)
        skip_entry = EXT_ENTRY.format(name=skip_target, base=config.MAIN_BRANCH)
        self.write_targets(extra=skip_entry + good_profile)
        skip_task = self.new_task(skip_target)
        broken_task = self.new_task(broken_target)
        broken_profile = good_profile.replace(
            f"weakening_scope: [{SCOPE_MASK}]", "weakening_scope: 5")

        # Испорченное поле — последним: оно портит разбор файла целиком.
        for kind, task_id, tail in (
                ("пропуск", skip_task, good_profile),
                ("отказ", broken_task, broken_profile)):
            self.write_targets(extra=skip_entry + tail)
            with self.subTest(kind=kind):
                decision = project_profile.for_task(self.conn, task_id)
                reason = decision.skip if kind == "пропуск" else decision.refusal
                self.assertTrue(reason, self.why(f"фикстура: решение не "
                                                 f"{kind}: {decision}"))
                for element in (self.qualified(self.ext_test_path()),
                                f"tests/test_{self.word()}.py"):
                    out, failed = self.weakening_answer(
                        task_id, element, self.ext_test_path())
                    self.assertTrue(failed, self.why(
                        f"{kind}: answer приняла {element}:\n{out}"))
                    self.assertIn(reason, out, self.why(out))
                    self.assertEqual([], self.answers(task_id),
                                     self.why(f"{kind}: ANSWER создан:\n{out}"))


# AC-5 -----------------------------------------------------------------------

class MatrixTestReferenceByProfileTest(MandateScopeSandbox):

    def matrix_outcome(self, channel: str, task_id: str,
                       covered_by: str) -> tuple:
        """(отказано ли, вывод, прирост числа ANSWER) — канал `channel` с
        матрицей, где «Чем покрыто после» — `covered_by`."""
        before = len(self.answers(task_id))
        element = self.code_path_of[task_id]
        if channel == "answer":
            text = (f"{ZONES} {element}\n\nОснование: решение Оператора.\n\n"
                    + matrix([element], covered_by))
            out, failed = self.run_cmd(answer.cmd_answer, task_id,
                                       self.text_file(text))
        else:
            out, failed = self.run_cmd(
                answer.cmd_zones_extend, task_id, element, None,
                self.text_file(matrix([element], covered_by)))
        return failed, out, len(self.answers(task_id)) - before

    def test_ac5_matrix_coverage_reference_follows_project_scope(self):
        """Ссылка «Чем покрыто после» засчитывается по области профиля: у учебного проекта `backend/tests/…`, у артели `tests/…`, в обоих каналах.

        Задача учебного проекта и задача артели в `in_dev`. В каналах
        `answer` (мандат зон на файл кода ветки) и `zones-extend --matrix`
        матрица из одной строки «свойство остаётся», «Решение» — «ок»,
        покрытие — `backend/tests/<…>/test_<…>.py` или `tests/test_<…>.py`
        (случайные имена). У учебного проекта первая принимается (ANSWER
        добавлен), вторая отказывает (ANSWER не добавлен); у артели —
        наоборот.

        Ловит мутацию: `_TEST_REF_RE` оставлен на `tests/…` для всех задач —
        у учебного проекта `backend/tests/…` не покрытие, а `tests/…`
        покрытие; профиль подставлен только в одном канале (например в
        `answer`, а `zones-extend` по-прежнему без задачи) — канал-отстающий
        даёт прежние исходы; ссылкой стала любая `*.py` — у артели
        `backend/tests/…` принят.
        """
        ext_task = self.new_task(EXT)
        ext_code = self.code_path
        artel_task = self.new_task(ARTEL)
        self.code_path_of = {ext_task: ext_code, artel_task: self.code_path}
        cases = []
        for channel in ("answer", "zones-extend"):
            ext_ref = f"{self.ext_test_path()}{SEP}test_{self.word()}"
            artel_ref = f"tests/test_{self.word()}.py:{self.rng.randrange(1, 99)}"
            cases += [(channel, "внешний", ext_task, ext_ref, True),
                      (channel, "внешний", ext_task, artel_ref, False),
                      (channel, "артель", artel_task, ext_ref, False),
                      (channel, "артель", artel_task, artel_ref, True)]
        for channel, who, task_id, ref, accepted in cases:
            with self.subTest(channel=channel, who=who, ref=ref):
                failed, out, added = self.matrix_outcome(channel, task_id, ref)
                if accepted:
                    self.assertFalse(failed, self.why(f"отказ:\n{out}"))
                    self.assertEqual(1, added, self.why(out))
                else:
                    self.assertTrue(failed, self.why(f"принято:\n{out}"))
                    self.assertIn("не покрыто", out, self.why(out))
                    self.assertEqual(0, added, self.why(out))


# AC-6 -----------------------------------------------------------------------

class ArtelDegradedProfileRefusesMandateTest(MandateScopeSandbox):

    def test_ac6_artel_without_profile_refuses_mandate_with_reason(self):
        """У артели без `test_profile` `answer` с мандатом `tests/…::T::m` отказывает, называя причину решения профиля, ANSWER нет.

        Задача артели заведена при исправном `targets.yaml`; затем запись
        артели переписана без поля `test_profile`. Предпосылка фикстуры —
        `project_profile.for_task` даёт отказ. Мандат на случайный
        `tests/test_<…>.py::C…::test_…` (в области `tests/**/*.py`)
        отказан, текст причины решения профиля — в выводе, ANSWER нет.

        Ловит мутацию: у артели проверка при записи идёт по
        `mandate.in_weakening_scope` мимо решения профиля (оговорка
        требования 3 не реализована) — мандат принят и ANSWER создан.
        """
        task_id = self.new_task(ARTEL)
        self.write_targets(artel_profile=False)
        decision = project_profile.for_task(self.conn, task_id)
        self.assertTrue(decision.refusal,
                        self.why(f"фикстура: решение не отказ: {decision}"))

        element = self.qualified(f"tests/test_{self.word()}.py")
        out, failed = self.weakening_answer(task_id, element,
                                            f"tests/test_{self.word()}.py")
        self.assertTrue(failed, self.why(f"answer приняла {element}:\n{out}"))
        self.assertIn(decision.refusal, out, self.why(out))
        self.assertEqual([], self.answers(task_id),
                         self.why(f"ANSWER создан:\n{out}"))


if __name__ == "__main__":
    unittest.main()
