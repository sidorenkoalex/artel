"""Авторазрешение конфликта подтяжки по карте кодовой базы: интерпретатор регенерации и запись журнала о сбое шага.

Группа: долгоживущий
Красен до реализации: test_ac1 — регенерация карты в `pull` зовёт голый `python3`, подложный `python3` первым в PATH падает кодом 1, и подтяжка эскалирует; test_ac4/test_ac5 — сбой шага авторазрешения сегодня молча закрывает путь автоматики, записи журнала с шагом, кодом возврата и хвостом stderr до эскалации нет.

Сценарий — публичная точка подтяжки `pull.evaluate` (без прогона планки,
`run_plank=False`) в лёгкой песочнице переходов
`tests/sandbox.py::LightTransitionSandbox`: ветка задачи отстала от main,
`git merge` конфликтует только по `docs/codebase-map.md` (хук
`self.in_repo_handlers`). Регенератор карты — заглушка
`scripts/codebase_map.py`, положенная в рабочую копию задачи; она
исполняется настоящим `subprocess.run` (песочница пропускает в него всё,
кроме плотницких git-примитивов). Подложный `python3` — исполняемый
скрипт оболочки во временном каталоге, поставленном первым в PATH.

Длина stderr сбоя, код возврата, номер отказавшего шага и текст
подложного `python3` — от зерна; зерно печатается и входит в текст
каждого провала.

Валидировано временным стабом реализации (регенерация под
`sys.executable`, запись журнала о сбое шага перед эскалацией): все тесты
файла зелёные, стаб удалён.
"""
import os
import random
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, pull, store
from tests.sandbox import LightTransitionSandbox

MAP_REL = "docs/codebase-map.md"
MERGE_STDOUT = f"CONFLICT (content): Merge conflict in {MAP_REL}\n"
ESCALATION_ACTION = "state -> escalated"
# Символ хвоста stderr сбоя: в тексте пульта и в фикстурах его нет, поэтому
# число его вхождений в записи журнала — длина попавшего туда хвоста.
TAIL_CHAR = "¤"
STDERR_LIMIT = 500

STUB_OK = (
    "import pathlib\n"
    "path = pathlib.Path('docs') / 'codebase-map.md'\n"
    "path.parent.mkdir(parents=True, exist_ok=True)\n"
    "path.write_text({text!r}, encoding='utf-8')\n")
STUB_FAIL = (
    "import sys\n"
    "sys.stderr.write({stderr!r})\n"
    "sys.exit({code})\n")


class PullMapConflictSandbox(LightTransitionSandbox):
    """Задача в `in_dev`, ветка отстала, merge конфликтует только по
    карте; отказ git-шага авторазрешения включается `self.fail_step`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.wt_path.mkdir(parents=True, exist_ok=True)
        self.calls: list = []
        self.merged = False
        self.fail_step = None
        self.in_repo_handlers.append(self.conflict_handler)
        self.set_state("in_dev")

    # ------------------------------------------------------------ обвязка

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    @staticmethod
    def completed(repo, args, code: int, stdout: str = "",
                  stderr: str = "") -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess([str(repo), *args], code, stdout,
                                           stderr)

    def conflict_handler(self, repo, *args):
        """`rev-list --count` — ветка отстала; `merge` — конфликт по карте;
        `diff --diff-filter=U` — карта; `self.fail_step` — отказ git-шага
        авторазрешения ПОСЛЕ merge (до него тот же примитив — очистка
        рабочей копии, не предмет теста)."""
        if args[:2] == ("rev-list", "--count"):
            return self.completed(repo, args, 0, f"{self.rng.randint(1, 9)}\n")
        if args[:1] == ("merge",):
            self.calls.append(args)
            if "--abort" in args:
                return self.completed(repo, args, 0)
            self.merged = True
            return self.completed(repo, args, 1, MERGE_STDOUT)
        if args[:3] == ("diff", "--name-only", "--diff-filter=U"):
            return self.completed(repo, args, 0, f"{MAP_REL}\n")
        if not self.merged:
            return None
        self.calls.append(args)
        if self.fail_step is not None:
            prefix, code, stderr = self.fail_step
            if args[:len(prefix)] == prefix:
                return self.completed(repo, args, code, "", stderr)
        return None

    def write_regenerator(self, source: str) -> None:
        path = self.wt_path / "scripts" / "codebase_map.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def put_fake_python3_first(self) -> None:
        """Подложный `python3` первым в PATH: завершается кодом 1."""
        bindir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bindir, ignore_errors=True)
        fake = bindir / "python3"
        fake.write_text(
            "#!/bin/sh\n"
            f"echo 'подложный python3 {self.rng.randrange(10**6)}' >&2\n"
            "exit 1\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                   | stat.S_IXOTH)
        patcher = mock.patch.dict(
            os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def pull(self):
        return pull.evaluate(
            store.db(), self.TASK, self.task_row(), "in_dev",
            origin_main_source=lambda target: None,
            origin_main_sha=lambda target: "deadbeefcafefeed",
            read_branch_text_or_refuse=lambda *a, **k: None,
            repo_path=self.wt_path, run_plank=False)

    def steps(self, since: int = 0) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
                if r["id"] > since]

    def journal_text(self, rows) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}" for r in rows)

    def max_step_id(self) -> int:
        rows = self.steps()
        return rows[-1]["id"] if rows else 0

    def failing_stderr(self) -> str:
        return (f"Traceback {self.rng.randrange(10**6)}\n"
                + TAIL_CHAR * self.rng.randint(STDERR_LIMIT + 100, 4000))

    def assert_escalated_with_step_record(self, since: int, outcome, code: int,
                                          step_pattern: str,
                                          context: str) -> None:
        """Эскалация прежняя (состояние, `merge --abort`, без коммита,
        прежний текст) и до неё — запись с шагом, кодом и хвостом stderr."""
        rows = self.steps(since)
        context = self.note(f"{context}\n{self.journal_text(rows)}")
        self.assertIsInstance(outcome, pull.Conflict, context)
        self.assertEqual(self.state(), "escalated", context)
        aborts = [c for c in self.calls if c[:1] == ("merge",) and "--abort" in c]
        self.assertEqual(len(aborts), 1, context)
        self.assertEqual([c for c in self.calls if c[:1] == ("commit",)], [],
                         context)
        escalations = [r for r in rows if r["action"] == ESCALATION_ACTION]
        self.assertEqual(len(escalations), 1, context)
        escalation = escalations[0]
        self.assertTrue((escalation["detail"] or "").startswith(
            f"конфликт подтяжки {config.MAIN_BRANCH} в ветку "), context)
        self.assertIn(MAP_REL, escalation["detail"], context)
        self.assertNotIn(TAIL_CHAR, escalation["detail"], context)

        records = [r for r in rows if r["id"] < escalation["id"]
                   and TAIL_CHAR in f"{r['action']} {r['detail'] or ''}"]
        self.assertTrue(records, f"до эскалации нет записи с хвостом stderr "
                                 f"отказавшего шага; {context}")
        text = " ".join(f"{r['action']} {r['detail'] or ''}" for r in records)
        self.assertRegex(text.lower(), step_pattern,
                         f"запись не называет отказавший шаг; {context}")
        self.assertRegex(text, rf"(?<![0-9A-Za-z]){code}(?![0-9A-Za-z])",
                         f"запись не называет код возврата {code}; {context}")
        for record in records:
            tail = f"{record['action']} {record['detail'] or ''}".count(TAIL_CHAR)
            self.assertLessEqual(tail, STDERR_LIMIT,
                                 f"хвост stderr длиннее {STDERR_LIMIT}; {context}")


class PullMapRegenInterpreterTest(PullMapConflictSandbox):

    def test_ac1_map_conflict_resolves_with_fake_python3_first_in_path(self):
        """Подложный `python3` первым в PATH не мешает авторазрешить конфликт по карте.

        Сценарий: регенератор-заглушка пишет карту со случайной меткой;
        первым в PATH стоит `python3`, завершающийся кодом 1. Подтяжка
        main с конфликтом только в `docs/codebase-map.md` даёт `Pulled`,
        задача остаётся в `in_dev`, `merge --abort` не звучит, merge
        завершён коммитом, карта рабочей копии — та, что написал
        регенератор.

        Ловит мутацию: регенерация в `pull._resolve_map_stage` снова зовёт
        голый `python3` — подложный интерпретатор падает, исход `Conflict`,
        задача в `escalated`, звучит `merge --abort`.
        """
        marker = f"карта-заглушка {self.rng.randrange(10**9)}\n"
        self.write_regenerator(STUB_OK.format(text=marker))
        self.put_fake_python3_first()

        outcome = self.pull()

        context = self.note(f"исход {outcome!r}\n{self.journal_text(self.steps())}")
        self.assertIsInstance(outcome, pull.Pulled, context)
        self.assertEqual(self.state(), "in_dev", context)
        self.assertEqual([c for c in self.calls
                          if c[:1] == ("merge",) and "--abort" in c], [], context)
        self.assertEqual(len([c for c in self.calls if c[:1] == ("commit",)]), 1,
                         context)
        self.assertEqual((self.wt_path / MAP_REL).read_text(encoding="utf-8"),
                         marker, context)

    def test_ac4_broken_regenerator_escalates_after_journal_record(self):
        """Регенератор, падающий по настоящей причине, эскалирует прежним путём после записи журнала о сбое.

        Сценарий: заглушка `scripts/codebase_map.py` пишет в stderr длинный
        (больше 500 символов) хвост и завершается случайным ненулевым
        кодом. Подтяжка с конфликтом только по карте: исход `Conflict`,
        задача в `escalated`, `merge --abort` один раз, коммита нет, текст
        эскалации — прежний «конфликт подтяжки …» без хвоста регенератора.
        До записи эскалации в журнале есть запись, называющая регенерацию
        карты, код возврата и хвост stderr не длиннее 500 символов.

        Ловит мутацию: сбой регенерации по-прежнему молча возвращает
        `False` — записи с хвостом stderr до эскалации нет; запись несёт
        stderr целиком (без обрезки) — в ней больше 500 символов хвоста;
        запись делается после `set_state` — её id больше id эскалации;
        хвост регенератора вклеен в текст эскалации — текст эскалации
        изменился.
        """
        code = self.rng.randint(2, 120)
        self.write_regenerator(STUB_FAIL.format(stderr=self.failing_stderr(),
                                                code=code))
        since = self.max_step_id()

        outcome = self.pull()

        self.assert_escalated_with_step_record(
            since, outcome, code, r"регенерац|codebase_map|regen",
            f"регенератор упал кодом {code}")


class PullGitStepFailureTest(PullMapConflictSandbox):

    def test_ac5_git_step_failure_journals_step_code_and_tail(self):
        """Отказ git-шага авторазрешения (`checkout --theirs`, `add`) пишет запись журнала до прежней эскалации.

        Сценарий (оба шага по очереди, `subTest`; порядок — от зерна):
        регенератор исправен, но git-шаг авторазрешения карты отвечает
        случайным ненулевым кодом и длинным stderr. Исход `Conflict`,
        задача в `escalated`, `merge --abort` один раз, коммита нет, текст
        эскалации прежний; до эскалации — запись, называющая шаг, код
        возврата и хвост stderr не длиннее 500 символов.

        Ловит мутацию: запись журнала добавлена только для сбоя
        регенерации, а отказ `checkout --theirs`/`add` по-прежнему молча
        возвращает `False` — записи с хвостом stderr до эскалации нет;
        запись не называет шаг или код возврата; stderr не обрезан.
        """
        marker = f"карта-заглушка {self.rng.randrange(10**9)}\n"
        self.write_regenerator(STUB_OK.format(text=marker))
        steps = [(("checkout", "--theirs", MAP_REL), r"checkout"),
                 (("add", MAP_REL), r"\badd\b")]
        self.rng.shuffle(steps)
        for prefix, pattern in steps:
            with self.subTest(step=" ".join(prefix)):
                code = self.rng.randint(2, 120)
                self.fail_step = (prefix, code, self.failing_stderr())
                self.calls.clear()
                self.merged = False
                self.set_state("in_dev")
                since = self.max_step_id()

                outcome = self.pull()

                self.assert_escalated_with_step_record(
                    since, outcome, code, pattern,
                    f"git {' '.join(prefix)} отказал кодом {code}")


if __name__ == "__main__":
    unittest.main()
