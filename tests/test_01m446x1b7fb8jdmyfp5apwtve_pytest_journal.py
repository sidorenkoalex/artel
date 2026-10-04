"""Итоговая строка pytest из результата инструмента шага роли — в журнал задачи.

Группа: долгоживущий
Красен до реализации: пульт не пишет в журнал действие «прогон pytest» — результат инструмента потока Claude/Codex только копится для метрики трения, и сценарии с итоговой строкой pytest не находят ни одной записи; сценарии «без итоговой строки — ни одной записи» зелены и держат это свойство после реализации.

Шаг роли гоняется целиком через публичный `runner.run_agent_once` в
песочнице с настоящим git (`tests.sandbox.RealGitSandbox` + синхронный
origin): подменён только процесс агента (`runner.spawn_agent` отдаёт
заготовленные строки потока провайдера через `tests.sandbox.FakeProc`).
Провайдер шага — из карты исполнителей фикстуры (`use_role_map`): у Claude
дефолтный, у Codex — `provider: codex` с моделью раздела `codex`
каталога-фикстуры. Журнал — `store.task_steps`; лог шага — путь из detail
записи «agent run started» («лог: <path>»).

Числа итоговых строк, длительности, рамка из «=», маркеры текста
результатов и порядок вызовов порождаются `random` при каждом запуске;
зерно печатается и входит в текст каждого провала.
"""
import json
import random
import re
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from orchestrator import config, keychain, runner, stack, store
from tests.sandbox import (FIXTURE_CODEX_MODEL, FIXTURE_TIER, FakeProc,
                           RealGitSandbox, event)

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PYTEST_ACTION = "прогон pytest"
ROLE = "developer"
LOG_PATH_RE = re.compile(r"лог: ([^,]+)")


def random_task_id(rng: random.Random) -> str:
    """Идентификатор формы ULID (26 знаков алфавита Крокфорда)."""
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def random_marker(rng: random.Random) -> str:
    return "mrk" + "".join(rng.choice("abcdefghijkmnpqrstuvwxyz")
                           for _ in range(12))


def random_summary(rng: random.Random) -> str:
    """Итоговая строка pytest без рамки: «N failed, M passed in X.XXs» либо
    «M passed in X.XXs»."""
    passed = rng.randint(1, 900)
    seconds = f"{rng.randint(0, 600)}.{rng.randint(0, 99):02d}s"
    if rng.random() < 0.5:
        return f"{rng.randint(1, 40)} failed, {passed} passed in {seconds}"
    return f"{passed} passed in {seconds}"


def framed(rng: random.Random, summary: str) -> str:
    """Итоговая строка так, как её печатает pytest: в рамке из «=» либо
    голой строкой."""
    if rng.random() < 0.7:
        bar = "=" * rng.randint(5, 30)
        return f"{bar} {summary} {bar}"
    return summary


def pytest_output(rng: random.Random, summary: str, marker: str) -> str:
    """Текст результата инструмента с прогоном pytest: шапка, строка
    провала с маркером и итоговая строка последней."""
    return (f"============ test session starts ============\n"
            f"collected {rng.randint(1, 900)} items\n\n"
            f"tests/test_{marker}.py ..F.\n\n"
            f"FAILED tests/test_{marker}.py::Case::test_one - AssertionError\n"
            f"{framed(rng, summary)}\n")


def plain_output(marker: str) -> str:
    """Текст результата инструмента без итоговой строки pytest."""
    return (f"README.md\norchestrator\n{marker}.txt\n"
            f"def test_passed_flag():\n    return 'passed'\n")


class PytestJournalStepSandbox(RealGitSandbox):
    """Задача самой артели в `in_dev`, worktree заводит пульт."""

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        self.seed = time.time_ns()
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.use_catalog_fixture()
        self.use_role_map()
        stack_ok = [stack.StackCheck(name, "ok", "песочница")
                    for name in ("python", "git", "gh", "claude", "codex",
                                 "venv")]
        for patcher in (
                mock.patch.object(stack, "check_stack", lambda: list(stack_ok)),
                mock.patch.object(keychain, "token", lambda slot: "tok-test"),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.conn = store.db()

    def note(self, extra: str) -> str:
        return f"зерно {self.seed}: {extra}"

    def new_task(self) -> str:
        task_id = random_task_id(self.rng)
        store.insert_task(self.conn, task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}-zadacha",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        return task_id

    def run_step(self, task_id: str, lines: list) -> list:
        """Шаг роли с потоком `lines`; возврат — записи журнала задачи."""
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=lambda cmd, **kw: FakeProc(lines, 0)):
            with redirect_stdout(StringIO()):
                runner.run_agent_once(self.conn, task_id, ROLE, "промпт шага", 1)
        return store.task_steps(store.db(), task_id)

    def pytest_rows(self, rows) -> list:
        return [row for row in rows if row["action"] == PYTEST_ACTION]

    def step_log_text(self, rows) -> str:
        started = [row for row in rows if row["action"] == "agent run started"]
        self.assertTrue(started, self.note("шаг не начат — нет «agent run started»"))
        match = LOG_PATH_RE.search(started[-1]["detail"])
        self.assertIsNotNone(match, self.note(f"нет пути лога: {started[-1]['detail']}"))
        return Path(match.group(1).strip()).read_text(encoding="utf-8")

    def tool_results(self, count_pytest: int, count_plain: int) -> list:
        """Случайно перемешанные результаты: (вид, итоговая строка, маркер)."""
        items = ([("pytest", random_summary(self.rng), random_marker(self.rng))
                  for _ in range(count_pytest)]
                 + [("plain", None, random_marker(self.rng))
                    for _ in range(count_plain)])
        self.rng.shuffle(items)
        return items

    def assert_journal(self, rows, items) -> None:
        expected = [summary for kind, summary, _ in items if kind == "pytest"]
        got = self.pytest_rows(rows)
        self.assertEqual([row["detail"] for row in got], expected, self.note(
            "записи «прогон pytest» не совпали с итоговыми строками прогонов "
            "(по одной на прогон, без рамки «=», в порядке потока)"))
        for row in got:
            self.assertEqual(row["actor"], ROLE, self.note(
                f"actor записи — не роль шага: {row['actor']}"))


def claude_lines(items) -> list:
    """Поток Claude: на каждый результат — вызов Bash и его `tool_result`."""
    lines = []
    for number, (kind, summary, marker) in enumerate(items):
        call_id = f"toolu_{number}"
        command = (f"python3 -m pytest tests/test_{marker}.py" if kind == "pytest"
                   else f"ls {marker}")
        lines.append(event(type="assistant", message={
            "role": "assistant", "content": [{
                "type": "tool_use", "id": call_id, "name": "Bash",
                "input": {"command": command}}]}))
        text = (pytest_output(random.Random(number), summary, marker)
                if kind == "pytest" else plain_output(marker))
        lines.append(event(type="user", message={
            "role": "user", "content": [{
                "type": "tool_result", "tool_use_id": call_id,
                "content": text, "is_error": False}]}))
    lines.append(event(type="result", subtype="success", is_error=False,
                       result="готово", total_cost_usd=0.001))
    return lines


def codex_lines(items) -> list:
    """Поток `codex exec --json`: `item.started`/`item.completed` команды."""
    lines = [json.dumps({"type": "thread.started", "thread_id": "t-1"}) + "\n",
             json.dumps({"type": "turn.started"}) + "\n"]
    for number, (kind, summary, marker) in enumerate(items):
        item_id = f"item_{number}"
        command = (f"python3 -m pytest tests/test_{marker}.py" if kind == "pytest"
                   else f"ls {marker}")
        lines.append(json.dumps({"type": "item.started", "item": {
            "id": item_id, "type": "command_execution", "command": command,
            "aggregated_output": "", "exit_code": None,
            "status": "in_progress"}}, ensure_ascii=False) + "\n")
        text = (pytest_output(random.Random(number), summary, marker)
                if kind == "pytest" else plain_output(marker))
        lines.append(json.dumps({"type": "item.completed", "item": {
            "id": item_id, "type": "command_execution", "command": command,
            "aggregated_output": text, "exit_code": 1 if kind == "pytest" else 0,
            "status": "completed"}}, ensure_ascii=False) + "\n")
    lines.append(json.dumps({"type": "turn.completed", "usage": {
        "input_tokens": 1000, "cached_input_tokens": 0,
        "output_tokens": 100}}) + "\n")
    return lines


class Ac1ClaudeToolResultTest(PytestJournalStepSandbox):

    def test_ac1_claude_pytest_summary_journalled_once_per_run(self):
        """Шаг Claude: прогоны pytest вперемешку с прочими вызовами инструментов.

        Поток несёт 1–3 результата инструмента с выводом pytest (итоговая
        строка «N failed, M passed in X.XXs» или «M passed in X.XXs»,
        случайно в рамке из «=») и 1–2 результата без итоговой строки. В
        журнале задачи — ровно по одной записи «прогон pytest» на каждый
        прогон, в порядке потока, actor — роль шага, detail — итоговая
        строка без рамки; результат без итоговой строки записи не даёт.
        Маркеры из текста результатов (строка провала, листинг) в лог шага
        не попадают.

        Ловит мутацию: detail пишется с обрамляющими «=» (или всей
        последней строкой вывода) — detail не совпадёт с итоговой строкой;
        запись делается и на результат без итоговой строки (по слову
        «passed» в тексте) — записей станет больше прогонов; запись
        делается дважды (в живом потоке и при закрытии шага) — записей
        вдвое больше; результат инструмента пишется в лог шага — маркер
        найдётся в логе.
        """
        for _ in range(2):
            task_id = self.new_task()
            items = self.tool_results(self.rng.randint(1, 3),
                                      self.rng.randint(1, 2))
            rows = self.run_step(task_id, claude_lines(items))
            self.assert_journal(rows, items)
            log_text = self.step_log_text(rows)
            for _kind, _summary, marker in items:
                self.assertNotIn(f"FAILED tests/test_{marker}.py", log_text,
                                 self.note("вывод pytest попал в лог шага"))
                self.assertNotIn(f"{marker}.txt", log_text,
                                 self.note("листинг попал в лог шага"))

    def test_ac1_claude_result_without_summary_gives_no_record(self):
        """Шаг Claude, в котором ни один результат инструмента не несёт
        итоговой строки pytest.

        Результаты — листинги и текст со словами «passed»/«test», но без
        строки формы «… passed in X.XXs». Записей «прогон pytest» в журнале
        задачи нет ни одной.

        Ловит мутацию: распознавание итоговой строки по одному слову
        «passed» (без числа и «in X.XXs») — появится запись на листинг.
        """
        task_id = self.new_task()
        items = self.tool_results(0, self.rng.randint(1, 3))
        rows = self.run_step(task_id, claude_lines(items))
        self.assertEqual(self.pytest_rows(rows), [], self.note(
            "результат без итоговой строки pytest дал запись журнала"))


class Ac2CodexCommandResultTest(PytestJournalStepSandbox):

    def setUp(self):
        super().setUp()
        self.use_role_map(roles={ROLE: {"provider": "codex"}},
                          tiers={FIXTURE_TIER: FIXTURE_CODEX_MODEL},
                          allow_experimental=(FIXTURE_CODEX_MODEL,))
        # Исполняемый файл codex на машине не нужен: окружение роли ищет
        # его через `shutil.which` (тот же приём, что
        # tests/test_codex_login_shell_path.py). Без подмены шаг на
        # раннере CI без codex не начинается (amend-tests Оператора 05.10).
        real_which = runner.shutil.which
        patcher = mock.patch.object(
            runner.shutil, "which",
            lambda name, *a, **kw: ("/usr/local/bin/codex" if name == "codex"
                                    else real_which(name, *a, **kw)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac2_codex_pytest_summary_journalled_once_per_run(self):
        """Шаг Codex: результаты команд с прогоном pytest и без него.

        Поток `codex exec --json` несёт 1–3 `item.completed` команды с
        выводом pytest и 1–2 без итоговой строки. В журнале — ровно по одной
        записи «прогон pytest» на каждый прогон, той же формы, что у Claude:
        actor — роль шага, detail — итоговая строка без рамки «=».

        Ловит мутацию: запись итоговой строки встроена только в разбор
        потока Claude (`tool_result`), а результат команды Codex её не даёт
        — записей не будет ни одной; либо у Codex detail берётся всей
        последней строкой `aggregated_output` с рамкой — detail не совпадёт.
        """
        task_id = self.new_task()
        items = self.tool_results(self.rng.randint(1, 3), self.rng.randint(1, 2))
        rows = self.run_step(task_id, codex_lines(items))
        self.assertTrue(
            [row for row in rows if row["action"] == "agent run started"],
            self.note("шаг Codex не начат"))
        self.assert_journal(rows, items)

    def test_ac2_codex_result_without_summary_gives_no_record(self):
        """Шаг Codex, в котором ни одна команда не напечатала итоговую строку
        pytest, — записей «прогон pytest» нет.

        Ловит мутацию: у Codex запись делается на каждый результат команды
        (`command_execution`) независимо от текста — появятся записи.
        """
        task_id = self.new_task()
        items = self.tool_results(0, self.rng.randint(1, 3))
        rows = self.run_step(task_id, codex_lines(items))
        self.assertTrue(
            [row for row in rows if row["action"] == "agent run started"],
            self.note("шаг Codex не начат"))
        self.assertEqual(self.pytest_rows(rows), [], self.note(
            "результат команды без итоговой строки pytest дал запись"))


if __name__ == "__main__":
    unittest.main()
