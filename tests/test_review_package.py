"""Тесты ревью-пакета — входа ревьювера (см. tasks/T011/SPEC.md).

Реального git и реального CLI здесь нет: `gitcmd.git` подменяется фейком с
заготовленным diff, `subprocess.Popen` — фейковым процессом. Так
проверяется то, что задаёт стоимость прогона: состав и порядок пакета,
дисциплина частей большого diff/пакета (tasks/
01M1GCN1FPSC1A6WK9WD1Q1V8X — замена прежнего молчаливого усечения) и
запись размера в журнал.

Тесты не описывают формулировки миссии — только наблюдаемое: что ушло в
промпт агента, что легло в журнал и какие права у шага остались.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator import (catalog, config, context_package, gitcmd,  # noqa: E402
                          review, runner, store)
from tests.sandbox import (FakeProc, SpyRun, capture,  # noqa: E402
                           capture_new_task_id, fake_git)

SPEC_MD = """---
task: T001
type: spec
author_role: analyst
status: approved
---

# SPEC: ревью-пакет

## Требования
1. Пакет собирает оркестратор.
"""

PLAN_MD = """---
task: T001
type: plan
author_role: developer
status: ready
---

# PLAN: ревью-пакет

## Подход
Собрать пакет в cmd_run.
"""

REVIEW_MD = """---
task: T001
type: review
author_role: reviewer
status: changes_requested
iteration: 1
---

# REVIEW: ревью-пакет

## Замечания
major — orchestrator/artel.py:1 — усечение без пометки.
"""


FORM_MD = """---
task: T000
type: review
author_role: reviewer
status: draft
---

# REVIEW: <заголовок>

## Замечания
"""


class FakeGit:
    """Подмена `gitcmd.git`: отвечает на diff и show заготовками, помнит вызовы.

    `files` — содержимое веток: путь → текст, как его отдал бы
    `git show <ветка>:<путь>`. Чего в словаре нет, того нет и в ветке.

    `raises_on` — команда («diff» или «show»), на которой фейк бросает
    `UnicodeDecodeError` вместо исхода. Так ведёт себя настоящий `git()`:
    декодирование живёт внутри `subprocess.run(text=True)`, поэтому файл в
    cp1251/latin-1 не даёт ненулевой код возврата, а бросает исключение.
    """

    def __init__(self, stat="orchestrator/artel.py | 2 +-", diff="diff --git a b",
                 returncode: int = 0, stderr: str = "", files=None,
                 raises_on: str = "", map_diff: str = ""):
        self.stat = stat
        self.diff = diff
        self.returncode = returncode
        self.stderr = stderr
        self.files = dict(files or {})
        self.raises_on = raises_on
        # T028: `--name-only` — сверка свежести docs/codebase-map.md
        # (orchestrator/brief.py), другой запрос, чем ревью-пакетный
        # `--stat`/полный diff ветки; по умолчанию «карта свежа» (пусто).
        self.map_diff = map_diff
        self.calls: list[list[str]] = []

    def __call__(self, *args: str) -> subprocess.CompletedProcess:
        self.calls.append(list(args))
        if args and args[0] == self.raises_on:
            raise UnicodeDecodeError("utf-8", b"caf\xe9 na\xefve", 3, 4,
                                     "invalid continuation byte")
        if args and args[0] == "show":
            return self.show(args)
        if (len(args) >= 3 and args[0] == "rev-parse" and args[1] == "--verify"
                and args[-1].startswith("refs/heads/")):
            # SPEC T048: `cmd_new` решает по этому ответу, заводить ли
            # задачу (AC-3, `gitcmd.branch_exists`) — «нет такой ветки»,
            # тем же приёмом, что и `tests.sandbox.fake_git`; отвечать
            # успехом на любой git-вызов, как ниже, значило бы «ветка уже
            # существует» для ЛЮБОГО имени и отказ `cmd_new` всегда.
            return subprocess.CompletedProcess(list(args), 1, "", "")
        if args and args[0] == "rev-parse":
            # T031: `gitcmd.on_foreign_branch` спрашивает текущую ветку и
            # существование ветки задачи вне пакета — пустой ответ, тот же
            # вырожденный случай «git не ответил», что и у остальных
            # заглушек `gitcmd.git` пакета (не подмешивать в `self.diff`).
            stdout = ""
        elif "--name-only" in args:
            stdout = self.map_diff
        elif "--stat" in args:
            stdout = self.stat
        else:
            stdout = self.diff
        return subprocess.CompletedProcess(
            list(args), self.returncode, "" if self.returncode else stdout,
            self.stderr)

    def show(self, args) -> subprocess.CompletedProcess:
        if self.returncode:  # git сломан целиком — не отвечает и на show
            return subprocess.CompletedProcess(list(args), self.returncode, "",
                                               self.stderr)
        _, rel = args[1].split(":", 1)
        if rel not in self.files:
            return subprocess.CompletedProcess(
                list(args), 128, "",
                f"fatal: path '{rel}' does not exist in '{args[1]}'")
        return subprocess.CompletedProcess(list(args), 0, self.files[rel], "")


class ContextPackageDisciplineTest(unittest.TestCase):
    """`context_package.discipline` — замена прежних `truncate_diff`/
    `truncate_package` (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X, AC-5/AC-6/AC-7/
    AC-8/AC-9/AC-10): текст под потолком части — как есть, крупнее —
    пронумерованные части без потери хвоста."""

    def test_text_under_the_part_cap_is_untouched(self):
        text = "х" * 100

        out, parts_n = context_package.discipline([text])

        self.assertEqual(out, text)
        self.assertEqual(parts_n, 0)

    def test_oversized_text_is_split_into_numbered_parts_with_sha256(self):
        lines = [f"+строка {n}" for n in range(1, 6000)]
        text = "\n".join(lines)
        self.assertGreater(len(text.encode("utf-8")),
                           config.CONTEXT_PART_MAX_BYTES)

        out, parts_n = context_package.discipline([text])

        self.assertGreater(parts_n, 1)
        self.assertIn("по порядку", out)
        self.assertIn("--- ЧАСТЬ 1/", out)
        self.assertIn(f"--- ЧАСТЬ {parts_n}/{parts_n}", out)
        for line in lines:
            self.assertIn(line, out.splitlines())
        self.assertNotIn("усечён", out)

    def test_cap_counts_bytes_not_characters(self):
        """Кириллица — два байта: потолок должен ловить её вдвое раньше."""
        text = "я" * config.CONTEXT_PART_MAX_BYTES

        out, parts_n = context_package.discipline([text])

        self.assertGreater(parts_n, 0, "потолок в символах пропустил бы этот текст")

    def test_split_parts_concatenate_back_to_the_original_byte_for_byte(self):
        text = "\n".join(f"+line-{n:05d}" for n in range(8000))

        parts = context_package.split_into_parts(text)

        self.assertGreater(len(parts), 1)
        self.assertEqual("".join(parts), text)

    def test_no_line_is_split_across_parts(self):
        """Сценарий сбоя прежнего усечения: строка длиннее потолка части
        целиком открывает свою часть, а не разрывается посередине."""
        line = "+" + "z" * 300_000
        text = "\n".join(line for _ in range(10))

        parts = context_package.split_into_parts(text)

        self.assertEqual(len(parts), 10)
        self.assertEqual("".join(parts), text)
        for part in parts:
            self.assertLessEqual(part.count("\n"), 1)


class DisciplineComponentBoundaryTest(unittest.TestCase):
    """Регресс R1-F1 (REVIEW.md итерация 1, major): деление на части
    обязано уважать границы КОМПОНЕНТОВ, а не резать по строкам всего
    склеенного тела вслепую — иначе крупный сосед мог подвести тело почти
    вплотную к границе части и разорвать соседний компонент (например
    diff), хотя его собственный размер меньше потолка (нарушение AC-8).

    Воспроизводит сценарий ревьювера: компонент-заполнитель ЧУТЬ меньше
    потолка части, следом — маленький компонент (аналог diff'а из
    нескольких строк) — раньше «### Diff» и последняя строка diff'а
    попадали в разные пронумерованные части."""

    def test_a_small_component_after_a_near_cap_filler_is_never_split(self):
        cap = config.CONTEXT_PART_MAX_BYTES
        filler = "х" * (cap - 300)  # почти вплотную к границе части
        small_component = "### Diff\n\n+строка 1\n+строка 2\n+строка 3\n"

        out, parts_n = context_package.discipline([filler, small_component])

        self.assertGreater(parts_n, 0, "тело обязано превысить потолок части")
        self.assertIn(
            small_component, out,
            "маленький компонент обязан появиться в тексте пакета целиком, "
            "одним непрерывным куском — не разорванным между частями")

    def test_small_components_stay_whole_regardless_of_position(self):
        cap = config.CONTEXT_PART_MAX_BYTES
        filler = "х" * (cap - 300)
        head = "### Задача\n\nT001 «Тест», ветка t/1\n"
        tail = "### Diff\n\n+строка 1\n+строка 2\n"

        out, parts_n = context_package.discipline([head, filler, tail])

        self.assertGreater(parts_n, 0)
        self.assertIn(head, out)
        self.assertIn(tail, out)

    def test_concatenation_of_parts_is_still_byte_for_byte_the_original(self):
        cap = config.CONTEXT_PART_MAX_BYTES
        components = ["### A\n\nМаркер-A\n", "х" * (cap - 300),
                     "### Diff\n\n+строка 1\n+строка 2\n+строка 3\n"]
        expected = "\n".join(components)

        out, parts_n = context_package.discipline(components)

        self.assertGreater(parts_n, 0)
        # Части встроены в `out` под заголовками «--- ЧАСТЬ N/M ... ---» —
        # проверяем инвариант через split_into_parts на самом ожидаемом
        # тексте, тем же способом, что и остальные тесты AC-6 этого файла.
        rebuilt = context_package._pack_components(components, "\n")
        self.assertEqual("".join(rebuilt), expected)


class RenderComponentTest(unittest.TestCase):
    """`context_package.render_component` — опись компонента (AC-1) и
    пропуск компонента крупнее потолка файла (AC-2)."""

    def test_component_under_the_cap_carries_size_and_sha256(self):
        text = "тело компонента\n"

        out = context_package.render_component("tasks/T001/SPEC.md", text)

        self.assertIn("tasks/T001/SPEC.md", out)
        self.assertIn(str(len(text.encode("utf-8"))), out)
        self.assertIn(context_package.sha256_of(text), out)
        self.assertIn("тело компонента", out)

    def test_component_over_the_cap_is_skipped_with_a_reason(self):
        text = "я" * (config.CONTEXT_FILE_MAX_BYTES + 1)

        out = context_package.render_component("CLAUDE.md", text)

        self.assertIn("CLAUDE.md", out)
        self.assertIn(str(len(text.encode("utf-8"))), out)
        self.assertIn(context_package.FILE_CAP_REASON, out)
        self.assertNotIn(text, out)


class ReviewPackageTest(unittest.TestCase):
    """Сборка пакета: все части на месте, порядок стабилен, размер посчитан."""

    TASK = "T001"
    BRANCH = "task/t001-revyu-paket"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.tdir = self.root / "tasks" / self.TASK
        self.tdir.mkdir(parents=True)
        for attr, value in (("ROOT", self.root), ("TASKS", self.root / "tasks")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        # Штатная картина: артефакты закоммичены в ветку задачи, а рабочее
        # дерево оркестратор оставил на main — в нём этих файлов нет.
        self.git = FakeGit(files={f"tasks/{self.TASK}/SPEC.md": SPEC_MD,
                                  f"tasks/{self.TASK}/PLAN.md": PLAN_MD,
                                  "templates/REVIEW.md": FORM_MD})
        git_patcher = mock.patch.object(gitcmd, "git", self.git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

    def put_in_worktree(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def build(self) -> dict:
        return review.review_package(self.TASK, "Ревью-пакет", self.BRANCH)

    def order_of(self, text: str, *marks: str) -> list[int]:
        found = []
        for mark in marks:
            self.assertIn(mark, text)
            found.append(text.index(mark))
        return found

    def test_all_parts_are_present_in_a_stable_order(self):
        """Требование 1: заголовок, SPEC, PLAN, стат-список и diff — по порядку."""
        text = self.build()["text"]

        marks = self.order_of(
            text,
            "### Задача", f"tasks/{self.TASK}/SPEC.md", f"tasks/{self.TASK}/PLAN.md",
            "### Изменённые файлы", "### Diff")

        self.assertEqual(marks, sorted(marks), "порядок частей пакета плавает")
        self.assertIn(self.BRANCH, text)
        self.assertIn("Пакет собирает оркестратор", text, "тело SPEC целиком")
        self.assertIn("Собрать пакет в cmd_run", text, "тело PLAN целиком")
        self.assertIn("orchestrator/artel.py | 2 +-", text)
        self.assertIn("diff --git a b", text)

    def test_stat_and_diff_are_taken_against_main(self):
        self.build()

        self.assertEqual([c for c in self.git.calls if c[0] == "diff"],
                         [["diff", "--stat", f"{config.MAIN_BRANCH}...{self.BRANCH}"],
                          ["diff", f"{config.MAIN_BRANCH}...{self.BRANCH}"]])

    def test_artifacts_are_read_from_the_same_point_as_the_diff(self):
        """Артефакты — из ветки задачи, а не из того, что сейчас в дереве."""
        self.build()

        self.assertEqual([c for c in self.git.calls if c[0] == "show"],
                         [["show", f"{self.BRANCH}:tasks/{self.TASK}/SPEC.md"],
                          ["show", f"{self.BRANCH}:tasks/{self.TASK}/PLAN.md"],
                          ["show", f"{self.BRANCH}:tasks/{self.TASK}/REVIEW.md"],
                          ["show", f"{self.BRANCH}:templates/REVIEW.md"]])

    def test_tree_on_main_does_not_empty_the_package(self):
        """Штатный ход оркестратора: после мержа соседней задачи дерево на main.

        Рабочего дерева с `tasks/T001` нет вовсе — пакет обязан собраться
        из ветки, а не объявить SPEC и PLAN отсутствующими (ревью 2).
        """
        self.assertFalse((self.root / "tasks" / self.TASK / "SPEC.md").exists(),
                         "в дереве артефактов нет — иначе тест ничего не ловит")

        package = self.build()

        self.assertIn("Пакет собирает оркестратор", package["text"], "тело SPEC")
        self.assertIn("Собрать пакет в cmd_run", package["text"], "тело PLAN")
        self.assertNotIn("не показан", package["text"])
        self.assertEqual(package["from_worktree"], [])

    def test_previous_review_survives_a_tree_on_main(self):
        """Хуже пропавшего PLAN: ревьювер не узнает, что итерация не первая."""
        self.git.files[f"tasks/{self.TASK}/REVIEW.md"] = REVIEW_MD

        text = self.build()["text"]

        self.assertIn("прошлая итерация", text)
        self.assertIn("усечение без пометки", text, "замечания прошлой итерации")

    def test_uncommitted_artifact_falls_back_to_the_worktree_and_says_so(self):
        """PLAN написан, но ещё не в коммите — показываем и называем источник."""
        del self.git.files[f"tasks/{self.TASK}/PLAN.md"]
        self.put_in_worktree(f"tasks/{self.TASK}/PLAN.md", PLAN_MD)

        package = self.build()

        self.assertIn("Собрать пакет в cmd_run", package["text"])
        self.assertIn(review.WORKTREE_NOTE.strip(), package["text"],
                      "подмена источника не проходит молча")
        self.assertEqual(package["from_worktree"], [f"tasks/{self.TASK}/PLAN.md"])

    def test_worktree_fallback_is_visible_in_the_note(self):
        """Расхождение дерева и diff Оператор разбирает по `log <id>`."""
        note = self.note_of(from_worktree=[f"tasks/{self.TASK}/PLAN.md"])

        self.assertIn(f"не из ветки, а из рабочего дерева: tasks/{self.TASK}/PLAN.md",
                      note)

    def test_unreadable_artifact_names_the_reason(self):
        """Битые байты в артефакте — строка с причиной, а не трейсбек из `run`."""
        del self.git.files[f"tasks/{self.TASK}/PLAN.md"]
        path = self.put_in_worktree(f"tasks/{self.TASK}/PLAN.md", "")
        path.write_bytes(b"\xff\xfe\x00PLAN")

        text = self.build()["text"]

        self.assertIn(f"tasks/{self.TASK}/PLAN.md", text)
        self.assertIn("не показан", text)
        self.assertIn("codec", text, "названа причина, а не просто «нет файла»")

    def test_review_form_is_part_of_the_package(self):
        """Единственное чтение, которое пакет обязан снять: форма вердикта."""
        text = self.build()["text"]

        marks = self.order_of(text, f"tasks/{self.TASK}/PLAN.md",
                              "templates/REVIEW.md", "### Изменённые файлы")
        self.assertEqual(marks, sorted(marks), "форма идёт после артефактов задачи")
        self.assertIn("# REVIEW: <заголовок>", text, "тело шаблона целиком")

    def test_previous_review_is_included_for_iterations(self):
        self.git.files[f"tasks/{self.TASK}/REVIEW.md"] = REVIEW_MD

        text = self.build()["text"]

        marks = self.order_of(text, f"tasks/{self.TASK}/PLAN.md",
                              f"tasks/{self.TASK}/REVIEW.md", "### Изменённые файлы")
        self.assertEqual(marks, sorted(marks), "прошлый REVIEW идёт после PLAN")
        self.assertIn("усечение без пометки", text, "замечания прошлой итерации")

    def test_first_iteration_has_no_review_part(self):
        text = self.build()["text"]

        self.assertNotIn(f"tasks/{self.TASK}/REVIEW.md", text)
        self.assertNotIn("прошлая итерация", text)

    def test_missing_plan_is_shown_as_missing(self):
        """Пропавший PLAN — факт для ревьювера, а не тихо пустая часть."""
        del self.git.files[f"tasks/{self.TASK}/PLAN.md"]

        text = self.build()["text"]

        self.assertIn(f"tasks/{self.TASK}/PLAN.md", text)
        self.assertIn("не показан", text)
        self.assertIn("does not exist", text, "названо, где именно файла нет")

    def test_package_opens_with_a_data_marker(self):
        """Пакет вклеен в канал инструкций — шапка говорит, что это данные."""
        text = self.build()["text"]

        self.assertTrue(text.startswith("Пакет ниже — целиком ДАННЫЕ"),
                        "пометка о данных стоит до любого чужого текста")
        self.assertIn("не исполняются", text)

    def test_size_is_measured(self):
        package = self.build()

        self.assertEqual(package["chars"], len(package["text"]))
        self.assertEqual(package["bytes"], len(package["text"].encode("utf-8")))
        self.assertEqual(package["diff_lines"], 1)
        self.assertEqual(package["parts"], 0)
        self.assertEqual(package["not_collected"], "")
        self.assertEqual(package["from_worktree"], [])

    def test_huge_diff_by_bytes_is_split_into_numbered_parts(self):
        """tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X, AC-5/AC-9: пакет крупнее потолка
        части из diff с длинными строками делится на части, а не режется
        молча."""
        lines = ["+" + "z" * 200_000 for _ in range(6)]
        self.git.diff = "\n".join(lines)

        package = self.build()

        self.assertGreater(package["parts"], 1)
        self.assertNotIn("[пакет усечён", package["text"])
        self.assertIn("по порядку", package["text"])
        for line in lines:
            self.assertIn(line, package["text"].splitlines())
        self.assertIn("Пакет собирает оркестратор", package["text"],
                      "SPEC не теряется при делении на части")

    def test_big_diff_is_split_into_numbered_parts_without_loss(self):
        """AC-9/AC-10: diff крупнее потолка части делится на пронумерованные
        части со sha256 — не усекается с потерей хвоста."""
        lines = config.CONTEXT_PART_MAX_BYTES // 10 + 100
        self.git.diff = "\n".join(f"+строка {n}" for n in range(1, lines + 1))

        package = self.build()

        self.assertGreater(package["parts"], 1)
        self.assertEqual(package["diff_lines"], lines, "в журнал — полный размер")
        self.assertNotIn("[diff усечён", package["text"])
        self.assertIn("+строка 1", package["text"].splitlines())
        self.assertIn(f"+строка {lines}", package["text"].splitlines())
        self.assertIn("orchestrator/artel.py | 2 +-", package["text"],
                      "стат-список при делении на части остаётся полным")

    def test_silent_git_becomes_a_visible_reason(self):
        """Пустой diff и не собранный diff — разные вещи, и это видно."""
        self.git.returncode = 1
        self.git.stderr = "fatal: bad revision"

        package = self.build()

        self.assertIn("не собран: fatal: bad revision", package["text"])
        self.assertEqual(package["diff_lines"], 0)
        self.assertEqual(package["parts"], 0)
        self.assertEqual(package["not_collected"], "fatal: bad revision",
                         "причина уезжает и в журнал, не только в текст пакета")

    def test_undecodable_diff_becomes_a_visible_reason(self):
        """Файл в latin-1 внутри ветки — причина в пакете, а не трейсбек из `run`.

        NUL-байта в таком файле нет, бинарным git его не считает и
        выкладывает его байты в diff как текст; декодирование падает уже
        внутри `git()` (ревью 3).
        """
        self.git.raises_on = "diff"

        package = self.build()

        self.assertIn("не собран", package["text"])
        self.assertIn("codec", package["text"], "названа причина, а не «нет diff»")
        self.assertEqual(package["diff_lines"], 0)
        self.assertIn("codec", package["not_collected"],
                      "причина уезжает и в журнал, не только в текст пакета")
        self.assertIn("Пакет собирает оркестратор", package["text"],
                      "остальной пакет собран: сбой diff не роняет сборку")

    def test_undecodable_artifact_becomes_a_visible_reason(self):
        """Тот же класс сбоя на пути `git show`: артефакт назван, сборка цела."""
        self.git.raises_on = "show"

        package = self.build()

        self.assertIn(f"tasks/{self.TASK}/SPEC.md", package["text"])
        self.assertIn("не показан", package["text"])
        self.assertIn("codec", package["text"])
        self.assertIn("diff --git a b", package["text"], "diff на месте")

    def test_empty_diff_is_stated_explicitly(self):
        self.git.diff = ""
        self.git.stat = ""

        package = self.build()

        self.assertIn("(изменений нет)", package["text"])
        self.assertEqual(package["not_collected"], "",
                         "пустая ветка — это не сбой сборки")

    def note_of(self, **over) -> str:
        package = {"chars": 1234, "bytes": 2345, "diff_lines": 56,
                   "parts": 0, "not_collected": "", "from_worktree": []}
        return review.package_note(package | over)

    def test_note_shows_size(self):
        note = self.note_of()

        self.assertIn("символов 1234", note)
        self.assertIn("байт 2345", note)
        self.assertIn("строк diff 56", note)
        self.assertNotIn("усечён", note)
        self.assertNotIn("не собран", note)
        self.assertNotIn("рабочего дерева", note)
        self.assertNotIn("частей", note)

    def test_note_shows_the_parts_count(self):
        """tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X: пакет, поделённый на части,
        называет их число в журнале — вместо прежнего «усечён»."""
        self.assertIn("пакет поделён на 3 частей", self.note_of(parts=3))

    def test_note_tells_a_failed_diff_from_an_empty_one(self):
        """Иначе «строк diff 0» у сбоя и у пустой ветки читается одинаково."""
        self.assertIn("diff не собран: fatal: bad revision",
                      self.note_of(not_collected="fatal: bad revision"))


class CmdRunReviewPackageTest(unittest.TestCase):
    """`run` в review: пакет уходит в промпт, размер — в журнал, права те же."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        # ROOT подменяем вместе с остальным: иначе откат на рабочее дерево
        # смотрел бы в настоящий репозиторий, где tasks/T001 существует, и
        # тест зависел бы от чужой задачи. Скилы и шаблоны копируем — их
        # cmd_run и cmd_new читают из ROOT.
        for name in ("skills", "templates"):
            shutil.copytree(REPO / name, root / name)
        # T028: бриф роли developer читает docs/codebase-map.md и CLAUDE.md
        # из ROOT — без них шаг разработчика падает ENOENT.
        (root / "docs").mkdir()
        (root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        for attr, value in (("ROOT", root),
                            ("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            # Курируемый слой ролей (T019): каталог заводит
                            # запуск шага — пусть заводит в песочнице, а не
                            # в .artel/ репозитория.
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            # SPEC T059: автокоммит успешного шага читает
                            # `workspace.path(task_id)` напрямую (не через
                            # подменённый ниже `workspace.ensure`) —
                            # непропатченный `WORKTREES` утёк бы на
                            # реальный worktree пульта (тот же довод, что у
                            # `PreviousVerdictShaTest` в этом же модуле).
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        # Артефакты живут в ветке задачи; рабочее дерево здесь на них не
        # похоже — так же, как у оркестратора после мержа соседней задачи.
        # `files` заполняется НИЖЕ, уже после `cmd_new` (SPEC T094: id —
        # ULID, а не предсказуемый "T001" — заранее ключи словаря не собрать).
        self.git = FakeGit(files={"templates/REVIEW.md": FORM_MD})
        git_patcher = mock.patch.object(gitcmd, "git", self.git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)
        # Этот модуль — про сборку ревью-пакета, не про worktree-механику
        # (SPEC T045): `FakeGit` отвечает на любую команду заготовкой diff,
        # не умеет осмысленно `worktree add/list`, а тесты (например,
        # `test_developer_step_has_no_package`) сверяют СПИСОК git-вызовов
        # шага буквально — обходим `workspace.ensure` напрямую, тем же
        # приёмом, что и preflight/keychain выше. Путь — сам `root` (SPEC
        # T048): `cmd_new` пишет `tasks/<id>` в НЕГО, и `self.tdir` ниже
        # обязан совпасть, иначе тест и код смотрят в разные каталоги.
        wt_patcher = mock.patch.object(
            runner.workspace, "ensure",
            lambda task_id, branch: (root, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)
        # A7 (generic-путь заведения, AC-5): `cmd_new` коммитит артефакты
        # плотницки (`artifact_branch.write_commit`) — та функция зовёт
        # `subprocess.run` НАПРЯМУЮ, минуя `gitcmd.git`/`FakeGit` выше;
        # `root` здесь не настоящий git-репозиторий — без этого патча
        # `cmd_new` падает `sys.exit` («git не ответил») ещё до сценария,
        # который тест проверяет (тот же приём, что `tests.sandbox.
        # TmpRootTest.setUp`).
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Ревью-пакет вместо свободного чтения")
        self.git.files.update({f"tasks/{self.TASK}/SPEC.md": SPEC_MD,
                               f"tasks/{self.TASK}/PLAN.md": PLAN_MD})
        # Вызовы `cmd_new` (branch_exists, коммит ТЗ/SPEC — SPEC T048) —
        # это подготовка песочницы, не часть шага, который проверяют тесты
        # буквальным списком `self.git.calls` (например,
        # `test_developer_step_has_no_package`).
        self.git.calls.clear()
        self.tdir = config.TASKS / self.TASK

    capture = staticmethod(capture)

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def run_agent(self, state: str) -> tuple[str, list[str]]:
        """Прогон шага; возвращает вывод и argv запущенного CLI.

        Промпт в argv не ищется: с T017 он уходит агенту файлом на stdin
        (SPEC T017, требование 4). Путь к файлу запоминается — его читает
        `prompt`.
        """
        self.set_state(state)
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out = self.capture(runner.cmd_run, self.TASK)
        self.prompt_path = Path(popen.call_args.kwargs["stdin"].name)
        return out, popen.call_args.args[0]

    def prompt(self) -> str:
        """Промпт шага — из файла, отданного процессу агента на stdin."""
        return self.prompt_path.read_text(encoding="utf-8")

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]

    def test_reviewer_prompt_carries_the_package(self):
        """Критерий приёмки 1: SPEC, PLAN, стат-список и diff — в промпте."""
        _, argv = self.run_agent("review")

        prompt = self.prompt()
        self.assertIn("--- РЕВЬЮ-ПАКЕТ ---", prompt)
        self.assertIn("Пакет собирает оркестратор", prompt, "SPEC целиком")
        self.assertIn("Собрать пакет в cmd_run", prompt, "PLAN целиком")
        self.assertIn("orchestrator/artel.py | 2 +-", prompt, "стат-список")
        self.assertIn("diff --git a b", prompt, "diff")
        self.assertIn("# REVIEW: <заголовок>", prompt, "форма вердикта")
        self.assertIn("review-checklist", prompt, "скилы роли остались в промпте")

    def test_prompt_holds_the_artifacts_with_the_tree_off_the_branch(self):
        """Дерево на main — пакет всё равно полон: артефакты берутся из ветки.

        A7 (generic-путь заведения, AC-5): `cmd_new` больше не пишет
        `tasks/<id>/` на диск main вовсе (артефакты живут только в
        артефактной ветке) — `self.tdir` уже не существует к этому
        моменту БЕЗ дополнительной симуляции; `rmtree` — best-effort,
        на случай если он всё же появился (не отказ, если нет)."""
        shutil.rmtree(self.tdir, ignore_errors=True)

        _, argv = self.run_agent("review")

        prompt = self.prompt()
        self.assertIn("Пакет собирает оркестратор", prompt, "SPEC целиком")
        self.assertNotIn("не показан", prompt)

    def test_worktree_fallback_is_journaled(self):
        """Расхождение источника и diff Оператор видит в `log <id>`.

        Откат берём на `templates/REVIEW.md`: в дереве этот файл есть,
        потому что `setUp` копирует `templates/` в песочницу под
        подменённый `ROOT`. Уберёте `copytree` — упадёт этот тест, а не то
        место, где сломали фикстуру.
        """
        del self.git.files["templates/REVIEW.md"]

        _, argv = self.run_agent("review")

        self.assertIn("не из ветки, а из рабочего дерева: templates/REVIEW.md",
                      self.journal_details("ревью-пакет собран")[0])
        self.assertIn(review.WORKTREE_NOTE.strip(), self.prompt(),
                      "источник назван и в самом пакете, не только в журнале")

    def test_package_size_lands_in_the_journal(self):
        """Критерий приёмки 2: размер входа виден в `log <id>` у старта ревью."""
        out, argv = self.run_agent("review")

        details = self.journal_details("ревью-пакет собран")
        self.assertEqual(len(details), 1)
        package = review.review_package(self.TASK, "Ревью-пакет вместо свободного чтения",
                                       store.db().execute(
                                           "SELECT branch FROM tasks WHERE id=?",
                                           (self.TASK,)).fetchone()[0])
        self.assertIn(f"символов {package['chars']}", details[0])
        self.assertIn(f"строк diff {package['diff_lines']}", details[0])
        self.assertIn("символов", self.capture(catalog.cmd_log, self.TASK))
        self.assertIn("ревью-пакет:", out, "размер виден Оператору сразу")

    def test_package_is_journaled_before_the_agent_starts(self):
        """Запись о пакете идёт до запуска — иначе она врёт о старте шага."""
        self.run_agent("review")

        actions = [r["action"] for r in store.db().execute(
            "SELECT action FROM steps WHERE task_id=? ORDER BY id", (self.TASK,))]
        self.assertLess(actions.index("ревью-пакет собран"),
                        actions.index("agent run started"))

    def test_split_into_parts_is_journaled_too(self):
        """tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X: пакет, поделённый на части,
        называет их число в журнале (замена прежнего «усечён»)."""
        lines = config.CONTEXT_PART_MAX_BYTES // 10 + 100
        self.git.diff = "\n".join(f"+строка {n}" for n in range(1, lines + 1))

        self.run_agent("review")

        self.assertIn("поделён на", self.journal_details("ревью-пакет собран")[0])

    def test_failed_diff_is_visible_in_the_journal(self):
        """Вердикт по пакету без diff должен объясняться из `log <id>`."""
        self.git.returncode = 1
        self.git.stderr = "fatal: bad revision"

        self.run_agent("review")

        detail = self.journal_details("ревью-пакет собран")[0]
        self.assertIn("diff не собран: fatal: bad revision", detail)

    def test_undecodable_diff_does_not_kill_the_run(self):
        """Один latin-1 файл в ветке не должен ронять `run` до записи в журнал.

        Сборка стоит перед `agent run started`, поэтому трейсбек здесь
        оставлял задачу висеть в `review` вообще без строки в `log <id>`, а
        причина сидела в файле, который ничем себя не выдаёт (ревью 3).
        """
        self.git.raises_on = "diff"

        _, argv = self.run_agent("review")

        detail = self.journal_details("ревью-пакет собран")[0]
        self.assertIn("diff не собран", detail)
        self.assertIn("codec", detail)
        self.assertIn("Пакет собирает оркестратор", self.prompt(),
                      "шаг всё равно стартовал, и с артефактами в пакете")

    def test_developer_step_has_no_package(self):
        """Требование «не входит»: контекст разработчика не меняется."""
        _, argv = self.run_agent("in_dev")

        self.assertNotIn("--- РЕВЬЮ-ПАКЕТ ---", self.prompt())
        self.assertEqual(self.journal_details("ревью-пакет собран"), [])
        # Шесть вызовов, и ни один — не о пакете: первый — `workspace.
        # on_task_branch` (SPEC T045, AC-8) спрашивает список worktree
        # перед стартом шага; второй — SPEC.md брифа читается С АРТЕФАКТНОЙ
        # ВЕТКИ пульта (A7, требование 2: `artifact_source.resolve` теперь
        # всегда `foreign=True`, даже для self, `orchestrator/brief.py`);
        # третий — сверка свежести docs/codebase-map.md для брифа роли
        # (orchestrator/brief.py, tasks/T028); четвёртый — та же
        # генерализация, что и у второго: `_latest_answer_rel` листает
        # `tasks/<id>/` артефактной ветки в поиске ANSWER-n.md (историю
        # эскалаций) через `ls-tree`, не `Path.glob` диска; последние два
        # — `role_env` берёт авторство коммита шага (`role_cwd`/
        # `workspace.ensure` подменены в setUp — их git-вызовы проверяет
        # tests/test_workspace.py). Автокоммит успешного шага (SPEC T059)
        # не следует вовсе: `_commit_external_step_artifacts` (A7,
        # generic-путь) коммитит workspace РОЛИ (`config.PROJECTS/<target>/
        # workspace/tasks/<id>`), которого фейковый агент этого теста не
        # писал — каталога нет, функция возвращает раньше любого git-
        # вызова (в отличие от прежнего безусловного `git add -A`
        # догфуда). Список точный: любой `show` diff/stat (чтение
        # ревью-пакета) в шаге разработчика по-прежнему провалит тест.
        self.assertEqual(self.git.calls,
                         [["worktree", "list", "--porcelain"],
                          ["show", f"artifact/{self.TASK.lower()}:"
                           f"tasks/{self.TASK}/SPEC.md"],
                          ["diff", "--name-only",
                           "0000000000000000000000000000000000000000",
                           "HEAD", "--", "orchestrator/*.py", "scripts/*.py",
                           "tests/*.py"],
                          ["ls-tree", "-r", "--name-only",
                           f"artifact/{self.TASK.lower()}", "--",
                           f"tasks/{self.TASK}"],
                          ["config", "--get", "user.name"],
                          ["config", "--get", "user.email"]],
                         "diff разработчику не собирается")

    def test_reviewer_rights_are_not_narrowed(self):
        """Требование 4: инструменты ревьювера те же, что у разработчика."""
        _, dev_argv = self.run_agent("in_dev")
        _, rev_argv = self.run_agent("review")

        def tools(argv: list[str]) -> str:
            return argv[argv.index("--allowedTools") + 1]

        self.assertEqual(tools(rev_argv), tools(dev_argv))
        self.assertIn("Bash(python3:*)", tools(rev_argv), "тесты запускать можно")


class IncrementalReviewPackageTest(ReviewPackageTest):
    """`review_package(iteration=..., prev_sha=...)` — diff от sha, не main
    (T029, SPEC требования 2, 5, 8, 9). Наследует фикстуру `ReviewPackageTest`
    (тот же `FakeGit`, тот же `build`-каркас), но собирает пакет напрямую с
    новыми параметрами вместо стандартных."""

    PREV_SHA = "abc1234"

    def build_incremental(self, iteration: int = 2, prev_sha: str | None = None
                          ) -> dict:
        return review.review_package(
            self.TASK, "Ревью-пакет", self.BRANCH,
            iteration=iteration, prev_sha=self.PREV_SHA if prev_sha is None
            else prev_sha)

    def test_diff_and_stat_are_taken_against_the_previous_verdict_sha(self):
        self.build_incremental()

        self.assertEqual(
            [c for c in self.git.calls if c[0] == "diff"],
            [["diff", "--stat", f"{self.PREV_SHA}...{self.BRANCH}"],
             ["diff", f"{self.PREV_SHA}...{self.BRANCH}"]],
            "iteration > 1 должен сравнивать не с main, а с sha "
            "предыдущего вердикта")

    def test_package_names_the_full_diff_command(self):
        """Требование 5: явная инструкция для полного diff по запросу."""
        text = self.build_incremental()["text"]

        self.assertIn(f"git diff {config.MAIN_BRANCH}...{self.BRANCH}", text)

    def test_first_iteration_does_not_carry_the_full_diff_instruction(self):
        """iteration == 1 — состав пакета не меняется (требование 1)."""
        text = self.build()["text"]

        self.assertNotIn("посмотри полный diff ветки отдельно", text,
                         "инструкция полного diff — только для iteration > 1")

    def test_package_reports_its_diff_type_and_iteration(self):
        package = self.build_incremental(iteration=3)

        self.assertEqual(package["diff_type"], "инкрементальный")
        self.assertEqual(package["iteration"], 3)

    def test_first_iteration_package_reports_the_full_diff_type(self):
        package = self.build()

        self.assertEqual(package["diff_type"], "полный")
        self.assertEqual(package["iteration"], 1)

    def test_missing_prev_sha_falls_back_to_the_full_diff(self):
        """Вырожденный случай (SPEC — тот же приём, что и в fixation.py):
        iteration > 1, но sha не найден — пакет не падает, а ведёт себя
        как при iteration == 1."""
        package = self.build_incremental(prev_sha="")

        self.assertEqual(package["diff_type"], "полный")
        self.assertEqual(
            [c for c in self.git.calls if c[0] == "diff"],
            [["diff", "--stat", f"{config.MAIN_BRANCH}...{self.BRANCH}"],
             ["diff", f"{config.MAIN_BRANCH}...{self.BRANCH}"]])


class PackageNoteDiffTypeTest(unittest.TestCase):
    """`package_note` дописывает тип diff и итерацию (требования 7, 8, 9)."""

    def note_of(self, **over) -> str:
        package = {"chars": 1234, "bytes": 2345, "diff_lines": 56,
                  "parts": 0, "not_collected": "", "from_worktree": []}
        return review.package_note(package | over)

    def test_full_diff_package_names_its_type_and_iteration(self):
        note = self.note_of(diff_type="полный", iteration=1)

        self.assertIn("полный", note)
        self.assertIn("итерация 1", note)

    def test_incremental_package_names_its_type_and_iteration(self):
        note = self.note_of(diff_type="инкрементальный", iteration=2)

        self.assertIn("инкрементальный", note)
        self.assertIn("итерация 2", note)

    def test_package_without_diff_type_keeps_the_old_note_shape(self):
        """Пакет, собранный вручную без этих полей (старые тесты), не падает
        и не получает лишнего текста."""
        note = self.note_of()

        self.assertNotIn("итерация", note)


class PreviousVerdictShaTest(unittest.TestCase):
    """`previous_verdict_sha` читает журнал hash-фиксации (T021), не изобретая
    новый учёт sha (SPEC требование 3)."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            # SPEC T048: `cmd_new` заводит настоящий worktree
                            # через `gitcmd` — непропатченный `WORKTREES`
                            # утёк бы на реальный пульт (tests/sandbox.py).
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Этому классу от `cmd_new` нужна только строка в БД — `gitcmd.git`
        # без подмены ушёл бы в РЕАЛЬНЫЙ git пульта (SPEC T048, требование
        # 1, `branch_exists`/`workspace.ensure`): лёгкая общая заглушка
        # (`tests.sandbox.fake_git`), тем же приёмом, что и в соседних
        # модулях.
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "sha предыдущего вердикта")
        self.conn = store.db()

    capture = staticmethod(capture)

    def fixate(self, sha: str) -> None:
        store.journal(self.conn, self.TASK, "fsm", "sha зафиксирован",
                     f"target=dogfood, sha={sha}, чисто=True")

    def test_no_fixation_history_is_empty(self):
        self.assertEqual(review.previous_verdict_sha(self.conn, self.TASK), "")

    def test_a_single_fixation_is_not_enough_yet(self):
        """Одна запись — это вход в первую review, сравнивать ещё не с чем."""
        self.fixate("1111111")

        self.assertEqual(review.previous_verdict_sha(self.conn, self.TASK), "")

    def test_second_to_last_fixation_is_the_previous_verdict(self):
        """review -> in_dev (вердикт) фиксирует sha_a; in_dev -> review
        (правка) фиксирует sha_b, уже текущий `fixed_sha`. Искомый —
        предпоследний, sha_a, не последний."""
        self.fixate("1111111")  # in_dev -> review, итерация 1
        self.fixate("2222222")  # review -> in_dev, вердикт итерации 1
        self.fixate("3333333")  # in_dev -> review, итерация 2 (текущий)

        self.assertEqual(
            review.previous_verdict_sha(self.conn, self.TASK), "2222222")

    def test_unrecognisable_sha_is_treated_as_missing(self):
        """git не ответил в момент той фиксации (T021, вырожденный случай) —
        не трейсбек, а откат на полный diff у вызывающего кода."""
        self.fixate("1111111")
        store.journal(self.conn, self.TASK, "fsm", "sha зафиксирован",
                     "target=dogfood, sha=—, чисто=False")
        self.fixate("3333333")

        self.assertEqual(review.previous_verdict_sha(self.conn, self.TASK), "")


if __name__ == "__main__":
    unittest.main()
