"""Двусторонний прогон смены ожидания из раздела SPEC «Меняемое поведение» на переходе `in_dev -> verifying` (SPEC 01M45FJD46BX45VHC36S4VS9QN, требование 10).

Смена ожидания, совпавшая с объявленным, ещё не доказывает, что
поведение сменилось и что тест его различает: литерал можно поменять в
тесте и не тронуть код. Доказательство — два прогона одного узла
`tests/<файл>.py::<Класс>::<метод>`: НОВАЯ версия файла теста (из головы
ветки) на дереве базы сравнения обязана упасть — тест различает
поведение; СТАРАЯ версия (из базы) на дереве головы тоже обязана упасть —
поведение действительно сменилось.

Падение засчитывается только по отчёту pytest об узле: провал фазы call с
исключением класса `AssertionError` (и его подклассов: `self.fail`,
`mock.assert_*`) либо `pytest.fail.Exception` («DID NOT RAISE»). Код
возврата процесса этого не различает: ошибка импорта, `NameError` или
сломанный `setUp` тоже дают ненулевой код, но доказывают лишь то, что
версия теста не исполнима на чужом дереве. Класс и фазу пишет крошечный
плагин pytest (`_PLUGIN_SOURCE`), который выкладывается во временный
каталог под уникальным именем модуля: положить в `PYTHONPATH` корень
пульта нельзя — пакет `orchestrator` пульта заслонил бы одноимённый пакет
проверяемого дерева.

Деревья — `git worktree add --detach` в клоне проекта задачи, во
временном каталоге вне рабочей копии (образец
`fsm_merge_gate._scratch_worktree`), по одному на базу и голову на весь
рубеж; уборка — в `finally`, при любом исходе. Таймаут pytest, молчание
git и любой иной сбой прогона — отказ (fail-closed), не пропуск.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import NamedTuple

from .. import acceptance, config, gitcmd

NEW_ON_BASE = "новая версия на базе"
OLD_ON_BRANCH = "старая версия на ветке"
NOT_PROOF = "не доказательство"
TIMEOUT = "таймаут"
PASSED = "пройден"

# Имя модуля плагина отчёта — уникальное, чтобы не встретиться ни с одним
# модулем проверяемого дерева; переменная окружения — путь файла отчёта.
PLUGIN_MODULE = "artel_two_sided_report"
REPORT_ENV = "ARTEL_TWO_SIDED_REPORT"

_PLUGIN_SOURCE = '''"""Отчёт пульта о классе и фазе исхода узлов (двусторонний прогон)."""
import json
import os

import pytest

_SETUP_FRAMES = {"setUp", "asyncSetUp", "setUpClass", "setUpModule"}


def _write(record):
    with open(os.environ["ARTEL_TWO_SIDED_REPORT"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\\n")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    record = {"nodeid": report.nodeid, "when": report.when,
              "outcome": report.outcome}
    if call.excinfo is not None:
        kind = call.excinfo.type
        frames = set()
        tb = call.excinfo.tb
        while tb is not None:
            frames.add(tb.tb_frame.f_code.co_name)
            tb = tb.tb_next
        record["exception"] = kind.__name__
        record["assertion"] = issubclass(kind, (AssertionError,
                                                pytest.fail.Exception))
        record["timeout"] = issubclass(kind, pytest.fail.Exception) and \\
            str(call.excinfo.value).startswith("Timeout")
        record["in_setup"] = bool(frames & _SETUP_FRAMES)
    _write(record)


def pytest_collectreport(report):
    if report.failed:
        _write({"nodeid": report.nodeid, "when": "collect",
                "outcome": "failed", "text": str(report.longrepr)[-2000:]})
'''

_ERROR_NAME = re.compile(r"\b(\w+(?:Error|Exception))\b")


class Method(NamedTuple):
    """Метод исхода 7а: путь файла в базе и в голове, квалифицированное
    имя, тексты файла теста в базе и в голове."""

    base_path: str
    head_path: str
    name: str
    base_source: str
    head_source: str

    @property
    def address(self) -> str:
        return f"{self.head_path}::{self.name}"


class Outcome(NamedTuple):
    """Итог прогона: `refusals` — строки отказа (пусто — доказано),
    `results` — {адрес метода: итог для записи исхода рубежа},
    `head_sha`/`base_sha` — деревья прогона."""

    refusals: list
    results: dict
    head_sha: str
    base_sha: str


def _git_reason(res) -> str:
    if res is None:
        return "git не ответил"
    return (res.stderr or res.stdout or "").strip()[:300] or \
        f"git вернул код {res.returncode}"


def _verdict(records: list, nodeid: str) -> str:
    """Итог одного узла по отчёту плагина: пустая строка — упал на
    утверждении (доказательство), `"green"` — прошёл, иначе — причина
    «не доказательство»."""
    own = [r for r in records if r.get("nodeid") == nodeid]
    if not own:
        broken = [r for r in records if r.get("when") == "collect"]
        if broken:
            match = _ERROR_NAME.search(broken[-1].get("text") or "")
            name = match.group(1) if match else "ошибка импорта"
            return f"ошибка сборки (collect): {name}"
        seen = sorted({r.get("nodeid") or "" for r in records})
        return f"узел не найден (pytest отчитал: {', '.join(seen)[:300]})"
    by_phase = {r["when"]: r for r in own}
    for phase in ("setup", "call", "teardown"):
        record = by_phase.get(phase)
        if record is None:
            continue
        if record["outcome"] == "skipped":
            return f"пропуск (фаза {phase})"
        if record["outcome"] != "failed":
            continue
        name = record.get("exception") or "?"
        if phase == "setup":
            return f"ошибка фазы setup: {name}"
        if phase == "teardown":
            return f"ошибка фазы teardown: {name}"
        if record.get("in_setup"):
            return f"ошибка setUp: {name}"
        if record.get("timeout"):
            return f"{TIMEOUT} теста (pytest-timeout): {name}"
        if record.get("assertion"):
            return ""
        return f"исключение {name} в фазе call"
    return "green"


def _run_side(tree: Path, nodes: list, plugin_dir: Path,
              report: Path) -> tuple:
    """(записи отчёта, причина сбоя) одного прогона pytest по `nodes` в
    дереве `tree`. Команда и окружение — те же, что у прогона планки
    (`acceptance._pytest_command`/`_pytest_env`)."""
    cmd = acceptance._pytest_command(*nodes, f"--rootdir={tree}",
                                     "-p", PLUGIN_MODULE)
    with acceptance._pytest_env() as env:
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in (str(plugin_dir), env.get("PYTHONPATH", "")) if p)
        env[REPORT_ENV] = str(report)
        try:
            res = subprocess.run(cmd, cwd=tree, env=env, capture_output=True,
                                 text=True,
                                 timeout=config.TWO_SIDED_PYTEST_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            return [], (f"{TIMEOUT} прогона pytest "
                        f"({config.TWO_SIDED_PYTEST_TIMEOUT_SEC} с)")
        except OSError as exc:
            return [], f"pytest не запустился: {exc}"
    records = []
    try:
        lines = report.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    if not records:
        # Плагин не записал ни одного узла — pytest не дошёл до сбора
        # (ошибка аргументов, плагина, конфигурации): причина — его вывод.
        tail = " ".join(((res.stdout or "") + (res.stderr or "")).split())
        return [], f"pytest не отчитал ни одного узла: {tail[-300:]}"
    return records, ""


def _failed(methods: list, reason: str, head_sha: str,
            base_sha: str) -> Outcome:
    """Сбой, общий всем методам рубежа: отказ называет каждый метод."""
    return Outcome([f"{m.head_path}: {m.name}: двусторонний прогон: {reason}"
                    for m in methods],
                   {m.address: reason for m in methods}, head_sha, base_sha)


def _place(tree: Path, rel: str, text: str) -> None:
    target = tree / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def run(repo: Path, code_branch: str, base_sha: str, methods: list) -> Outcome:
    """Двусторонний прогон `methods` (список `Method`) на деревьях базы
    сравнения `base_sha` и головы `code_branch` в клоне `repo`."""
    head_sha = gitcmd.branch_head_sha(code_branch, repo=repo)
    if not head_sha:
        return _failed(methods, f"git не ответил на голову ветки {code_branch}",
                       "", base_sha)
    # `resolve()`: временный каталог macOS — символическая ссылка
    # (`/var` -> `/private/var`), и pytest с `--rootdir` по пути ссылки
    # строит id узла без пути файла.
    scratch = Path(tempfile.mkdtemp(prefix="artel-two-sided-")).resolve()
    trees: list = []
    try:
        for side, sha in (("base", base_sha), ("head", head_sha)):
            tree = scratch / side
            res = gitcmd.in_repo(repo, "worktree", "add", "--detach",
                                 str(tree), sha)
            if res is None or res.returncode != 0:
                reason = (f"git worktree add ({side} {sha[:12]}) не "
                          f"удался: {_git_reason(res)}")
                return _failed(methods, reason, head_sha, base_sha)
            trees.append(tree)
        base_tree, head_tree = trees
        for method in methods:
            _place(base_tree, method.head_path, method.head_source)
            _place(head_tree, method.base_path, method.base_source)
        plugin_dir = scratch / "plugin"
        _place(plugin_dir, f"{PLUGIN_MODULE}.py", _PLUGIN_SOURCE)
        sides = (
            (NEW_ON_BASE, base_tree,
             {m.address: f"{m.head_path}::{m.name}" for m in methods},
             "зелёная — тест не различает поведение"),
            (OLD_ON_BRANCH, head_tree,
             {m.address: f"{m.base_path}::{m.name}" for m in methods},
             "зелёная — поведение не сменилось"))
        refusals, results = [], {m.address: [] for m in methods}
        for index, (label, tree, nodes, green) in enumerate(sides):
            report = scratch / f"report-{index}.jsonl"
            records, failure = _run_side(tree, sorted(set(nodes.values())),
                                         plugin_dir, report)
            for method in methods:
                if failure:
                    reason = failure
                else:
                    verdict = _verdict(records, nodes[method.address])
                    if not verdict:
                        continue
                    reason = green if verdict == "green" \
                        else f"{NOT_PROOF} — {verdict}"
                results[method.address].append(f"{label}: {reason}")
                refusals.append(f"{method.head_path}: {method.name}: "
                                f"двусторонний прогон: {label}: {reason}")
        return Outcome(refusals,
                       {address: "; ".join(found) or PASSED
                        for address, found in results.items()},
                       head_sha, base_sha)
    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой прогона не пропуск
        return _failed(methods, f"сбой {exc!r}", head_sha, base_sha)
    finally:
        for tree in trees:
            gitcmd.in_repo(repo, "worktree", "remove", "--force", str(tree))
        shutil.rmtree(scratch, ignore_errors=True)
