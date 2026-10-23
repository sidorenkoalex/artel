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
import time
from pathlib import Path
from typing import NamedTuple

from .. import acceptance, config, gitcmd, liveness

NEW_ON_BASE = "новая версия на базе"
OLD_ON_BRANCH = "старая версия на ветке"
NOT_PROOF = "не доказательство"
TIMEOUT = "таймаут"
PASSED = "пройден"
# Исходы стороны в `Outcome.sides` (наблюдение, SPEC
# 01M4NZ5W9ZTKGTW7DGZQGMP2GP): упала на утверждении, зелёная, не
# запущена — предел наблюдения исчерпан.
SIDE_ASSERTION = "утверждение"
SIDE_GREEN = "зелёная"
SIDE_LIMIT = "не прогнан: предел"
NOT_ON_CHECK = "упал не на проверке"

# Имя модуля плагина отчёта — уникальное, чтобы не встретиться ни с одним
# модулем проверяемого дерева; переменная окружения — путь файла отчёта.
PLUGIN_MODULE = "artel_two_sided_report"
REPORT_ENV = "ARTEL_TWO_SIDED_REPORT"

_PLUGIN_SOURCE = '''"""Отчёт пульта о классе и фазе исхода узлов (двусторонний прогон)."""
import json
import linecache
import os
import sysconfig

import pytest

_SETUP_FRAMES = {"setUp", "asyncSetUp", "setUpClass", "setUpModule"}
_LIBRARY_DIRS = tuple(sorted({
    os.path.realpath(sysconfig.get_paths()[key]) + os.sep
    for key in ("stdlib", "platstdlib") if sysconfig.get_paths().get(key)}))


def _write(record):
    with open(os.environ["ARTEL_TWO_SIDED_REPORT"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\\n")


def _own(path, root):
    """Файл дерева прогона, не библиотеки: внутри корня, не под
    site-packages и не под каталогом стандартной библиотеки."""
    return path.startswith(root) and not path.startswith(_LIBRARY_DIRS) \\
        and not {"site-packages", "dist-packages"} & set(path.split(os.sep))


def _location(item, tb):
    """Место утверждения — последний кадр трассировки вне библиотек: у
    `self.assert*` это строка теста, а не `unittest/case.py`; у помощника
    другого файла — строка помощника. Путь — относительно корня дерева."""
    root = os.path.realpath(str(getattr(item.config, "rootpath", None)
                                or item.config.rootdir)) + os.sep
    found = None
    while tb is not None:
        path = os.path.realpath(tb.tb_frame.f_code.co_filename)
        if _own(path, root):
            found = (path, tb.tb_lineno)
        tb = tb.tb_next
    if found is None:
        return None
    path, line = found
    return {"path": os.path.relpath(path, root).replace(os.sep, "/"),
            "line": line, "text": linecache.getline(path, line).strip()}


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
        try:
            record["location"] = _location(item, call.excinfo.tb)
        except Exception:  # noqa: BLE001 — место лишь наблюдение, не вердикт
            record["location"] = None
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
    `head_sha`/`base_sha` — деревья прогона. `sides` — {адрес метода:
    {сторона: {"outcome": исход стороны, у упавшей на утверждении —
    "path"/"line"/"text" места утверждения}}}: его читает только
    наблюдение (SPEC 01M4NZ5W9ZTKGTW7DGZQGMP2GP, требование 1), вердикт
    прогона — по-прежнему `refusals`/`results`."""

    refusals: list
    results: dict
    head_sha: str
    base_sha: str
    sides: dict | None = None


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
        if record.get("kind"):
            # Вид записи отчёта профиля в границе (`_run_side_report`).
            return f"{NOT_ON_CHECK}: {record['kind']}"
        if record.get("assertion"):
            return ""
        return f"исключение {name} в фазе call"
    return "green"


def _variant_ids(records: list, nodeid: str) -> set:
    """Хвосты `[<id>]` вариантов параметризованного узла `nodeid` в отчёте
    (SPEC 01M56TNZ3E72XY9XSTAVS99CN2, требование 1). Вариант — id узла,
    продолженный ровно скобкой: соседний `::test_x_slow` вариантом
    `::test_x` не считается."""
    prefix = f"{nodeid}["
    return {r["nodeid"][len(nodeid):] for r in records
            if (r.get("nodeid") or "").startswith(prefix)}


def _side_verdict(records: list, nodeid: str, variants) -> tuple:
    """(итог стороны в форме `_verdict`, id узла, на котором он вынесен)
    по `variants` — хвостам вариантов, судимых на этой стороне; `None` —
    узел не параметризован, судится точный id. Сторона доказывает смену,
    только когда каждый её вариант упал на утверждении; первый не
    упавший называет себя."""
    if variants is None:
        return _verdict(records, nodeid), nodeid
    for variant in sorted(variants):
        verdict = _verdict(records, nodeid + variant)
        if verdict:
            return verdict, nodeid + variant
    return "", nodeid + min(variants)


def _common_variants(side_records: dict, nodes: dict) -> tuple:
    """({сторона: хвосты вариантов, судимые на ней, либо `None`}, причина
    отказа метода целиком). Вариантов нет ни на одной стороне — узел
    непараметризован, обе стороны судятся точным id (прежние исходы).
    Иначе на каждой стороне судятся варианты, общие обеим сторонам
    (сторона, чей прогон сорвался, отчёта не дала — тогда свои); общих
    нет — отказ, не «пройден»: пустой набор прохода не даёт."""
    found = {label: (_variant_ids(records, nodes[label])
                     if records is not None else None)
             for label, records in side_records.items()}
    if not any(found.values()):
        return {label: None for label in found}, ""
    ran = [ids for ids in found.values() if ids is not None]
    common = set.intersection(*ran) if len(ran) == len(found) else None
    if common is None:
        return {label: ids or None for label, ids in found.items()}, ""
    if not common:
        shown = "; ".join(
            f"{label}: {', '.join(sorted(ids)) or 'нет вариантов'}"
            for label, ids in found.items())
        return {}, f"нет вариантов, общих обеим сторонам ({shown})"
    return {label: common for label in found}, ""


def _location(records: list, nodeid: str) -> dict:
    """Место упавшего утверждения узла из записи фазы call плагина;
    пусто — плагин места не нашёл."""
    for record in records:
        if record.get("nodeid") == nodeid and record.get("when") == "call" \
                and isinstance(record.get("location"), dict):
            return record["location"]
    return {}


def _run_side(tree: Path, nodes: list, plugin_dir: Path,
              report: Path, timeout: float, profile=None) -> tuple:
    """(записи отчёта, причина сбоя) одного прогона pytest по `nodes` в
    дереве `tree`. Команда и окружение — те же, что у прогона планки
    (`acceptance._pytest_command`/`_pytest_env`).

    `profile` `pytest-own` (SPEC 01M52EEFNA1WH31962HVNT0YZ9): команда
    профиля в `workdir` дерева стороны, пути узлов переведены к нему
    (`--rootdir` — по-прежнему дерево: id узлов отчёта — от его корня;
    id от `workdir` приводит к корню `_root_form`), чистое окружение без `PYTHONPATH` пульта, свой сеанс; `workdir` вне
    дерева — сбой стороны без прогона.

    Профиль с итогом из отчёта (SPEC 01M590GJAF0EDV4NBC4C99MFVH,
    требование 8) — `_run_side_report`."""
    reported = acceptance.reported(profile)
    if reported is not None:
        return _run_side_report(tree, nodes, reported, timeout)
    own = acceptance.own(profile)
    cwd = tree
    if own is not None:
        cwd, refusal = acceptance.own_cwd(own, tree)
        if refusal:
            return [], refusal
        nodes = [acceptance.own_target(own, n, node=True) for n in nodes]
    cmd = acceptance.place_command(profile, *nodes, f"--rootdir={tree}",
                                    "-p", PLUGIN_MODULE)
    with acceptance.place_env(profile) as env:
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in (str(plugin_dir), env.get("PYTHONPATH", "")) if p)
        env[REPORT_ENV] = str(report)
        try:
            if own is not None:
                res = acceptance.run_in_session(cmd, cwd, env, timeout)
            else:
                res = subprocess.run(cmd, cwd=cwd, env=env,
                                     capture_output=True, text=True,
                                     timeout=timeout)
        except subprocess.TimeoutExpired:
            return [], f"{TIMEOUT} прогона pytest ({timeout:g} с)"
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
    if own is not None:
        for record in records:
            record["nodeid"] = _root_form(record.get("nodeid") or "", tree, cwd)
            location = record.get("location")
            if isinstance(location, dict) and location.get("path"):
                location["path"] = _root_form(location["path"], tree, cwd)
    return records, ""


def _run_side_report(tree: Path, nodes: list, profile,
                     timeout: float) -> tuple:
    """(записи в форме плагина, причина сбоя) стороны по профилю с отчётом:
    файлы узлов гонятся подмножеством компонента, итог узла — запись
    отчёта с тем же путём и именем (`passed`/`failed`/`skipped`; ошибка —
    падение не на утверждении). Отказ подготовки, предел и исход
    «неизвестно» — сбой стороны, не доказательство.

    Профиль в границе гейта исходов (SPEC 01M5DDTVZEA40ZB9BHEH4YDEE7,
    требование 6): провал проверки — только запись, для которой
    классификатор FAIL_TO_PASS `_check_failure_kind` даёт пусто; `failed`
    с иным именем ошибки, `error` и `passed` с повтором несут вид (`kind`)
    — «упал не на проверке». Вне границы — прежнее правило."""
    from .. import project_profile  # project_profile -> store -> … -> acceptance
    from ..reporters import outcome
    from .acceptance import in_outcome_bounds
    from .tests_writing import _check_failure_kind
    strict = in_outcome_bounds(profile)
    files = sorted({node.partition("::")[0] for node in nodes})
    run = acceptance.report_run(profile, tree, files, timeout)
    if run.refusal:
        return [], run.refusal
    if run.timed_out:
        return [], f"{TIMEOUT} прогона компонента ({timeout:g} с)"
    if run.state == outcome.UNKNOWN:
        return [], acceptance.unknown_line(run.reason)
    records = []
    for case in run.tests:
        try:
            _comp, path, name, _n = project_profile.parse_test_id(case.id)
        except ValueError:
            continue
        record = {"nodeid": f"{path}::{name}", "when": "call",
                  "outcome": "passed" if case.outcome == outcome.PASSED
                  else "skipped" if case.outcome == outcome.SKIPPED
                  else "failed"}
        if strict and (case.outcome in (outcome.FAILED, outcome.ERROR)
                       or (case.outcome == outcome.PASSED and case.retries)):
            kind = _check_failure_kind(case, profile)
            record["outcome"] = "failed"
            record["exception"] = (case.failure.partition(":")[0]
                                   or case.outcome)
            record["assertion"] = not kind
            if kind:
                record["kind"] = kind
        elif case.outcome in (outcome.FAILED, outcome.ERROR):
            record["exception"] = case.failure.partition(":")[0] or "?"
            record["assertion"] = case.outcome == outcome.FAILED
        records.append(record)
    return records, ""


def _root_form(nodeid: str, tree: Path, cwd: Path) -> str:
    """id узла (или путь) отчёта в форме от корня дерева `tree` (ANSWER-1
    SPEC 01M52EEFNA1WH31962HVNT0YZ9, п.2): команда профиля, сама задавшая
    pytest свой корень (`workdir`), даёт id от него — такой id, чей файл
    есть от `cwd`, но не от корня, переводится; прочие — как есть."""
    path, sep, rest = nodeid.partition("::")
    if not path or os.path.isabs(path) or (tree / path).exists() \
            or not (cwd / path).exists():
        return nodeid
    return os.path.relpath(cwd / path, tree).replace(os.sep, "/") + sep + rest


def _same_sides(reason: str) -> dict:
    return {label: {"outcome": reason}
            for label in (NEW_ON_BASE, OLD_ON_BRANCH)}


def _failed(methods: list, reason: str, head_sha: str,
            base_sha: str) -> Outcome:
    """Сбой, общий всем методам рубежа: отказ называет каждый метод."""
    return Outcome([f"{m.head_path}: {m.name}: двусторонний прогон: {reason}"
                    for m in methods],
                   {m.address: reason for m in methods}, head_sha, base_sha,
                   {m.address: _same_sides(reason) for m in methods})


def _place(tree: Path, rel: str, text: str) -> None:
    target = tree / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _side_timeout(deadline: float | None) -> float:
    """Таймаут стороны: `TWO_SIDED_PYTEST_TIMEOUT_SEC`, а при `deadline`
    (наблюдение) — меньшее из него и остатка до `deadline`."""
    timeout = config.TWO_SIDED_PYTEST_TIMEOUT_SEC
    if deadline is not None:
        timeout = min(timeout, deadline - time.monotonic())
    return timeout


def run(repo: Path, code_branch: str, base_sha: str, methods: list,
        deadline: float | None = None, profile=None) -> Outcome:
    """Двусторонний прогон `methods` (список `Method`) на деревьях базы
    сравнения `base_sha` и головы `code_branch` в клоне `repo`.

    `deadline` (`time.monotonic()`) — предел наблюдения (SPEC
    01M4NZ5W9ZTKGTW7DGZQGMP2GP, требование 6): сторона, для которой
    остатка нет, не запускается и получает исход `SIDE_LIMIT`. Гейт зовёт
    без него — таймаут стороны прежний.

    `profile` — профиль тестов проекта от вызывающего (`_run_side`); не
    передан — раннер пульта, как до SPEC 01M52EEFNA1WH31962HVNT0YZ9."""
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
        # Маркер владельца — до первого `git worktree add` (SPEC
        # 01M5FRYVP4NF81VT00FYPHPWJH, требование 5): каталог, брошенный
        # обрывом процесса, `doctor --fix` узнаёт сиротой.
        try:
            (scratch / liveness.GATE_OWNER_MARKER).write_text(
                str(os.getpid()), encoding="utf-8")
        except OSError as exc:
            return _failed(methods, f"маркер владельца выписки не записан: "
                           f"{exc}", head_sha, base_sha)
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
        observed = {m.address: {} for m in methods}
        # Обе стороны прогоняются до вердикта: параметризованный метод
        # судится по вариантам, общим обеим сторонам (SPEC
        # 01M56TNZ3E72XY9XSTAVS99CN2, требование 1).
        runs = {}
        for index, (label, tree, nodes, _green) in enumerate(sides):
            report = scratch / f"report-{index}.jsonl"
            timeout = _side_timeout(deadline)
            if timeout <= 0:
                runs[label] = ([], SIDE_LIMIT)
            else:
                runs[label] = _run_side(
                    tree, sorted(set(nodes.values())), plugin_dir, report,
                    timeout, profile)
        judged = {}
        for method in methods:
            judged[method.address] = _common_variants(
                {label: None if runs[label][1] else runs[label][0]
                 for label, *_rest in sides},
                {label: nodes[method.address]
                 for label, _tree, nodes, _green in sides})
            variants, reason = judged[method.address]
            if reason:
                observed[method.address] = _same_sides(reason)
                results[method.address].append(reason)
                refusals.append(f"{method.head_path}: {method.name}: "
                                f"двусторонний прогон: {reason}")
        for label, _tree, nodes, green in sides:
            records, failure = runs[label]
            for method in methods:
                variants, reason = judged[method.address]
                if reason:
                    continue
                if failure:
                    reason = failure
                    observed[method.address][label] = {"outcome": reason}
                else:
                    verdict, node = _side_verdict(
                        records, nodes[method.address], variants[label])
                    if not verdict:
                        observed[method.address][label] = {
                            "outcome": SIDE_ASSERTION,
                            **_location(records, node)}
                        continue
                    reason = green if verdict == "green" \
                        else f"{NOT_PROOF} — {verdict}"
                    variant = node[len(nodes[method.address]):]
                    if variant:
                        reason = f"вариант {variant}: {reason}"
                    observed[method.address][label] = {
                        "outcome": SIDE_GREEN if verdict == "green"
                        else reason}
                results[method.address].append(f"{label}: {reason}")
                refusals.append(f"{method.head_path}: {method.name}: "
                                f"двусторонний прогон: {label}: {reason}")
        return Outcome(refusals,
                       {address: "; ".join(found) or PASSED
                        for address, found in results.items()},
                       head_sha, base_sha, observed)
    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой прогона не пропуск
        return _failed(methods, f"сбой {exc!r}", head_sha, base_sha)
    finally:
        for tree in trees:
            gitcmd.in_repo(repo, "worktree", "remove", "--force", str(tree))
        shutil.rmtree(scratch, ignore_errors=True)
