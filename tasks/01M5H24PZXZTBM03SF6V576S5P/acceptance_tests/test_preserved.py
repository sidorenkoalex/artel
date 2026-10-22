"""Прежнее поведение без `--parallel`, прежние отказы и неизменность потребителей реестра.

Группа: разовый
Зелёный с рождения: файл держит то, что задача обязана сохранить, — вывод, строки, файл результата и реестр последовательного прогона (литерал снят на коде до правок задачи), прежний отказ повтора шаблона и повтора run_stamp, нетронутые потребители реестра и утверждения прежних тестов.

Литерал AC-1 снят на коде ветки до правок этой задачи (база f653a66a) теми же
подменами: `run_stamp` и путь пула заменены метками `<STAMP>`/`<POOL>`.
Неизменность функций и утверждений сверяется с базой диффа задачи
(`_pult.DIFF_BASE`) по файлам рабочей копии кода (`_pult.CODE_ROOT`).
"""
import ast
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness import (CanaryParallelSandbox, FULL_SHA, SET_NAME,  # noqa: E402
                      SHORT_SHA, SUMMARY)
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402
from orchestrator import canary, config, store  # noqa: E402

SEQUENTIAL_LITERAL = """\
[canary] прогон <STAMP>: 2 задач из пула <POOL> в порядке прогона: alfa, beta; целевой sha 3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93 (явный --sha), набор nabor-kedr (developer → model-pihta; источник: набор)
[ведение] alfa.md ratio=config sha=3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93 метка=явный --sha набор=nabor-kedr сводка=developer → model-pihta; источник: набор codex=None
[ведение] beta.md ratio=config sha=3f2a9c41d07be5a8816c0f9e2d4b7a6c5e1f0d93 метка=явный --sha набор=nabor-kedr сводка=developer → model-pihta; источник: набор codex=None
[canary] прогон <STAMP> завершён
"""
# AC-1: ci — зелёный прогон существующих тестов последовательного пути (tests/test_new_argv_parsing.py, UsageNamesTemplateFlagTest, CanaryHelpTest) держит CI кодовой ветки; литерал вывода и неизменность утверждений — тесты этого файла
# AC-18: ci — зелёный прогон tests/test_canary_run_task.py, тестов реестра Б-2 и DeterministicTestsLintTest держит CI кодовой ветки (прогон их из планки дольше её таймаута 120 с); неизменность функций и утверждений — тест этого файла
RECORD_KEYS = {"pid", "process_start", "run_stamp", "sha", "set_name",
               "started_at", "tasks"}
FIXED_STAMP = "20310305T101500Z"


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2031, 3, 5, 10, 15, 0, tzinfo=timezone.utc)


class SequentialPathTest(CanaryParallelSandbox):
    def test_ac1_sequential_run_output_rows_result_and_registry_as_before(self):
        """Прогон без `--parallel` на подменах — вывод, строки, файл результата и реестр прежние.

        Вывод равен литералу, снятому на коде до правок; ведение идёт в
        процессе родителя с прежними аргументами; дочерних процессов нет;
        строки `canary_runs` и файл результата — прежние; во время ведения в
        реестре метка и запись с прежним набором полей, после прогона реестр пуст.

        Ловит мутацию: развилка `--parallel` переписала прежнюю ветку — первая
        строка получила дополнение без флага, либо ведение ушло в дочерние
        процессы, либо запись реестра получила новые поля.
        """
        seen = []

        def drive(template_path, run_stamp, ratio, target_sha, sha_label, plan,
                  codex_auth):
            record = self.registry / f"{run_stamp}-{os.getpid()}.json"
            seen.append((self.listing(), json.loads(record.read_text(encoding="utf-8"))))
            print(f"[ведение] {template_path.name} "
                  f"ratio={'config' if ratio == config.CANARY_DEVIATION_RATIO else ratio} "
                  f"sha={target_sha} метка={sha_label} набор={plan.name} "
                  f"сводка={plan.summary} codex={codex_auth}")
            store.insert_canary_run(
                store.db(), run_stamp, template_path.stem,
                "01FIXTURE" + template_path.stem.upper(), 3, 1.5, 0, 0, "merged",
                None, False, False, main_sha=target_sha, verdict="green",
                set_name=plan.name, models_summary=plan.summary or None)

        result = self.root / "result.json"
        argv = ["--k", "2", "--sha", SHORT_SHA, "--set", SET_NAME, "--template",
                "alfa,beta", "--result-file", str(result)]
        with mock.patch.object(canary, "_run_one_task", side_effect=drive):
            run = self.run_cli(argv)
        self.assertIsNone(run.exc, run.describe())
        self.assertEqual(run.attempts, [])
        self.assertEqual(run.errors, [])
        self.assertEqual(self.forbidden, [])
        stamp = run.stamp
        self.assertEqual(run.stdout.replace(stamp, "<STAMP>").replace(str(self.pool), "<POOL>"),
                         SEQUENTIAL_LITERAL)
        self.assertEqual(
            [(r["run_stamp"], r["title"], r["task_id"], r["outcome"], r["main_sha"],
              r["verdict"], r["set_name"], r["models_summary"]) for r in self.rows()],
            [(stamp, name, "01FIXTURE" + name.upper(), "merged", FULL_SHA, "green",
              SET_NAME, SUMMARY) for name in ("alfa", "beta")])
        self.assertEqual(json.loads(result.read_text(encoding="utf-8")), {
            "status": "complete",
            "runs": [{"id": 1, "title": "alfa", "task_id": "01FIXTUREALFA",
                      "verdict": "green", "outcome": "merged"},
                     {"id": 2, "title": "beta", "task_id": "01FIXTUREBETA",
                      "verdict": "green", "outcome": "merged"}]})
        self.assertEqual(len(seen), 2)
        for listing, record in seen:
            self.assertEqual(listing, sorted([f"{stamp}-{os.getpid()}.json",
                                              f"{stamp}.lock"]))
            self.assertEqual(set(record), RECORD_KEYS)
            self.assertEqual((record["pid"], record["run_stamp"], record["sha"],
                              record["set_name"], record["tasks"]),
                             (os.getpid(), stamp, FULL_SHA, SET_NAME, 2))
        self.assertEqual(self.listing(), [])


class RefusalsTest(CanaryParallelSandbox):
    def test_ac5_repeated_template_refused_before_sha_registry_and_clone(self):
        """`--parallel` с повтором имени шаблона — прежний отказ `_named_pool_templates`.

        До отказа нет ни `_resolve_target_sha`, ни записи реестра, ни клона, ни
        дочернего процесса.

        Ловит мутацию: в параллельной ветке шаблоны выбираются своим кодом без
        сверки повтора — отказа нет, прогон доходит до origin и реестра.
        """
        self.children = {"alfa": {"mode": "exit", "hold": False}}
        run = self.run_cli(["--k", "2", "--sha", SHORT_SHA, "--set", SET_NAME,
                            "--template", "alfa,alfa", "--parallel"])
        self.assertIsInstance(run.exc, SystemExit, run.describe())
        self.assertIn("canary: --template повторяет имя шаблона: alfa",
                      str(run.exc.code))
        self.assertEqual(self.resolve_calls, [])
        self.assertEqual(self.forbidden, [])
        self.assertEqual(run.attempts, [])
        self.assertEqual(self.listing(), [])

    def test_ac17_refused_parallel_repeat_gives_no_stamp_and_no_children(self):
        """Повтор `run_stamp` живого прогона с `--parallel` — отказ без приёмника и без дочерних.

        Чужой живой прогон держит метку и запись того же `run_stamp` и уже
        записал строку: отказ «прогон <run_stamp> уже идёт», дочерних нет,
        файл результата повтора не несёт ни одной строки, чужие метка и запись
        не тронуты.

        Ловит мутацию: параллельный родитель зовёт приёмник `on_run_stamp` до
        записи реестра — файл результата отказанного повтора несёт строку
        чужого прогона.
        """
        self.children = {"alfa": {"mode": "exit", "hold": False},
                         "beta": {"mode": "exit", "hold": False}}
        self.registry.mkdir(parents=True, exist_ok=True)
        owner = os.getppid()
        mark = self.registry / f"{FIXED_STAMP}.lock"
        mark.write_text(f"{owner}\n", encoding="utf-8")
        record = self.registry / f"{FIXED_STAMP}-{owner}.json"
        record.write_text(json.dumps({"pid": owner, "run_stamp": FIXED_STAMP}),
                          encoding="utf-8")
        store.insert_canary_run(store.db(), FIXED_STAMP, "chuzhoy", "01FOREIGN", 1,
                                0.5, 0, 0, "merged", None, False, False,
                                main_sha=FULL_SHA, verdict="green",
                                set_name=SET_NAME, models_summary=SUMMARY)
        result = self.root / "result.json"
        with mock.patch.object(canary, "datetime", _FixedDateTime):
            run = self.run_parallel(["alfa", "beta"],
                                    extra=["--result-file", str(result)])
        self.assertIsInstance(run.exc, SystemExit, run.describe())
        self.assertIn(f"canary: прогон {FIXED_STAMP} уже идёт", str(run.exc.code))
        self.assertEqual(run.attempts, [])
        self.assertEqual(json.loads(result.read_text(encoding="utf-8"))["runs"], [])
        self.assertEqual(mark.read_text(encoding="utf-8"), f"{owner}\n")
        self.assertTrue(record.exists())


def _base_text(rel: str) -> str:
    res = subprocess.run(["git", "-C", CODE_ROOT, "show", f"{DIFF_BASE}:{rel}"],
                         capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise AssertionError(f"git show {DIFF_BASE}:{rel}: {res.stderr}")
    return res.stdout


def _current_text(rel: str) -> str:
    return (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")


def _definitions(text: str) -> dict:
    tree = ast.parse(text)
    return {node.name: ast.get_source_segment(text, node)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


def _assert_lines(text: str) -> list:
    return [line.strip() for line in text.splitlines() if "assert" in line]


REGISTRY_READERS = {
    "orchestrator/notes.py": ["_silence_window_reason"],
    "orchestrator/fsm_merge_gate.py": ["_refuse_during_canary"],
    "orchestrator/canary.py": [
        "refuse_main_move_during_canary", "live_run_note", "_live_dir",
        "_live_verdict", "live_runs", "_mark_state", "_record_stamps",
        "live_marks", "_read_live_record", "registry_view", "_record_mark",
        "_mark_follows_record", "_drop_live_record"],
}
SEQUENTIAL_TESTS = {
    "tests/test_new_argv_parsing.py": None,
    "tests/test_canary_template_flag.py": "UsageNamesTemplateFlagTest",
    "tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py": "CanaryHelpTest",
}
REGISTRY_TESTS = {
    "tests/test_canary_run_task.py": None,
    "tests/test_01m5fa4nr91pcf47szt6v0q9hs_doctor_live.py": None,
    "tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py": None,
    "tests/test_01m5fa4nr91pcf47szt6v0q9hs_mark.py": None,
    "tests/test_01m5fa4nr91pcf47szt6v0q9hs_window.py": None,
    "tests/test_invariants.py": "DeterministicTestsLintTest",
}


class PreservedCodeTest(unittest.TestCase):
    def assert_assertions_kept(self, files: dict) -> None:
        for rel, scope in files.items():
            with self.subTest(rel):
                base, current = _base_text(rel), _current_text(rel)
                if scope is not None:
                    base = _definitions(base)[scope]
                    current = _definitions(current).get(scope)
                    self.assertIsNotNone(current, f"{rel}: класса {scope} нет")
                missing = list(_assert_lines(base))
                for line in _assert_lines(current):
                    if line in missing:
                        missing.remove(line)
                self.assertEqual(missing, [], f"{rel}: утверждения базы изменены")

    def test_ac1_existing_sequential_tests_keep_assertions(self):
        """Утверждения прежних тестов последовательного пути не правлены.

        `tests/test_new_argv_parsing.py`, `UsageNamesTemplateFlagTest` и
        `CanaryHelpTest`: каждая строка утверждения базы есть в текущем тексте.
        Их зелёный прогон держит CI кодовой ветки (пометка `ci` ниже).

        Ловит мутацию: новый параметр передаётся `cmd_canary` и без флага, а
        `assert_called_once_with` в `test_new_argv_parsing.py` «починен» правкой
        ожидаемых аргументов — строка утверждения базы пропала.
        """
        self.assert_assertions_kept(SEQUENTIAL_TESTS)

    def test_ac18_registry_consumers_untouched_and_registry_tests_kept(self):
        """Потребители и чтение реестра не тронуты; утверждения тестов Б-1а и Б-2 не правлены.

        Исходный текст `_silence_window_reason`, `_refuse_during_canary`,
        `refuse_main_move_during_canary`, `live_run_note` и функций чтения
        реестра равен тексту базы; `tests/test_invariants.py` не изменён;
        утверждения `tests/test_canary_run_task.py`, тестов Б-2 и
        `DeterministicTestsLintTest` не правлены. Их зелёный прогон держит CI
        кодовой ветки (пометка `ci` ниже).

        Ловит мутацию: `live_runs` научили пропускать записи дочерних (или
        `live_run_note` — читать `parent_pid`) ради параллельного режима —
        текст функции разошёлся с базой.
        """
        for rel, names in REGISTRY_READERS.items():
            base, current = _definitions(_base_text(rel)), _definitions(_current_text(rel))
            for name in names:
                with self.subTest(f"{rel}::{name}"):
                    self.assertIn(name, base)
                    self.assertEqual(current.get(name), base[name])
        self.assertEqual(_current_text("tests/test_invariants.py"),
                         _base_text("tests/test_invariants.py"))
        self.assert_assertions_kept(REGISTRY_TESTS)
