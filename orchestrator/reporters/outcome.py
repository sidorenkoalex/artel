"""Итог прогона компонента из его отчёта (SPEC 01M590GJAF0EDV4NBC4C99MFVH, требования 1, 3, 5, 6, 18).

Отчёт `junit-xml` (JUnit XML раннера) и отчёт `pult-vitest` (JSON
отчётчика пульта `pult_vitest_reporter.js`, форма ANSWER-2, В2) читаются в
записи `CaseResult` по каждому тесту; вердикт прогона (`verdict`) судит
только записи и код возврата, не текст вывода раннера. Нет отчёта, он не
разобран или пуст при ненулевом коде — «неизвестно», не зелёный.

`summary_block` — сводка итога в форме короткого итога pytest (`FAILED
<id> - <вид падения>`, итоговая строка `N failed, M passed … in Xs`):
вызывающий дописывает её в конец вывода прогона, и прежние разборщики
пульта (`acceptance.run_summary_line`, `failed_entries`,
`suite_run.parse`) читают числа и упавших из неё — из отчёта.
"""
import json
import math
import os
from pathlib import Path
from typing import NamedTuple
from xml.etree import ElementTree

# Отчётчик пульта для `pult-vitest` — подстановка `{pult_reporter}`.
VITEST_REPORTER = Path(__file__).with_name("pult_vitest_reporter.js")

PASSED = "passed"
FAILED = "failed"
ERROR = "error"
SKIPPED = "skipped"

GREEN = "зелёный"
RED = "красный"
UNKNOWN = "неизвестно"

# Тест, прошедший с повтором внутри прогона, не зелёный (инвариант 41).
RETRY_NOTE = "повтор"

# Запись сбора pytest в xunit2 (`--continue-on-collection-errors`): атрибут
# `message` элемента `<error>`; трассировка — в тексте элемента.
COLLECTION_FAILURE = "collection failure"
DETAIL_LIMIT = 2000


class CaseResult(NamedTuple):
    """Итог одного теста компонента (ANSWER-2, В3): `id` — `<компонент>:<путь
    от корня репозитория>::<полное имя>`, `outcome` — `passed`/`failed`/
    `error`/`skipped`, `failure` — вид падения, `skip_reason` — причина
    пропуска, `time` — секунды; у `pult-vitest` ещё `mode`
    (`run`/`skip`/`todo`/`only`), `fails` (`it.fails`) и `retries`.

    `file_level` — запись ошибки уровня файла (импорт, сбор модуля), а не
    теста; `detail` — её текст: трассировка сбора pytest либо сообщение
    ошибки модуля Vitest (SPEC 01M5EDW6KD1ESCEVRSV2WPNXAP, требование 1).
    Поля — последними: позиционное построение прежних записей не
    сдвигается."""
    id: str
    outcome: str
    failure: str = ""
    skip_reason: str = ""
    time: float = 0.0
    mode: str = ""
    fails: bool = False
    retries: int = 0
    file_level: bool = False
    detail: str = ""


def _first_line(text: str) -> str:
    lines = (text or "").strip().splitlines()
    return lines[0].strip() if lines else ""


def _seconds(value) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return 0.0
    return seconds if math.isfinite(seconds) and seconds >= 0 else 0.0


def _root_path(workdir: str, rel: str) -> str:
    """Путь файла теста от корня репозитория: отчёт называет его от
    `workdir` компонента (AC-2)."""
    rel = rel.replace(os.sep, "/")
    joined = f"{workdir.strip('/')}/{rel}" if workdir else rel
    return os.path.normpath(joined).replace(os.sep, "/")


class _Ids:
    """Идентификаторы тестов одного отчёта: повтор того же имени получает
    номер `#n` (ADR-0026 п. 3)."""

    def __init__(self, component: str, workdir: str):
        from .. import project_profile  # project_profile -> store -> … -> acceptance
        self.test_id = project_profile.test_id
        self.component, self.workdir = component, workdir
        self.seen: dict[str, int] = {}

    def __call__(self, rel: str, name: str) -> str:
        text = self.test_id(self.component, _root_path(self.workdir, rel), name)
        count = self.seen.get(text, 0)
        self.seen[text] = count + 1
        return text if not count else self.test_id(
            self.component, _root_path(self.workdir, rel), name, count + 1)


def _junit_location(case, cwd: Path) -> tuple[str, str]:
    """(путь файла от `workdir`, полное имя) теста отчёта JUnit: файл — из
    атрибута `file`, иначе из `classname` (путь с `/` либо точечный путь
    модуля, найденный в `cwd`); класс — остаток `classname` за модулем."""
    name = case.get("name") or ""
    classname = case.get("classname") or ""
    path = case.get("file") or ""
    if not path:
        if "/" in classname:
            path, classname = classname, ""
        else:
            parts = classname.split(".")
            for size in range(len(parts), 0, -1):
                candidate = "/".join(parts[:size]) + ".py"
                if (Path(cwd) / candidate).is_file():
                    path, classname = candidate, ".".join(parts[size:])
                    break
            else:
                path, classname = classname, ""
    if os.path.isabs(path):
        path = os.path.relpath(path, cwd)
    module = path.rsplit(".", 1)[0].replace("/", ".")
    if classname in (path, module):
        classname = ""
    elif classname.startswith(module + "."):
        classname = classname[len(module) + 1:]
    full = f"{classname.replace('.', '::')}::{name}" if classname else name
    return path, full


def _junit_failure(element) -> str:
    kind = element.get("type") or ""
    message = _first_line(element.get("message") or "") or \
        _first_line(element.text or "")
    if kind and message and not message.startswith(kind):
        return f"{kind}: {message}"
    return message or kind


def parse_junit(report: Path, component: str, workdir: str,
                cwd: Path) -> tuple[list | None, str]:
    """(записи `CaseResult`, причина) отчёта JUnit `report`; `None` —
    отчёта нет или он не разобран, причина называет, что именно."""
    try:
        root = ElementTree.parse(report).getroot()
    except FileNotFoundError:
        return None, f"отчёт {report} не создан"
    except (OSError, ElementTree.ParseError) as exc:
        return None, f"отчёт {report} не разобран: {exc}"
    if root.tag not in ("testsuites", "testsuite"):
        return None, (f"отчёт {report} не разобран: корень <{root.tag}> — "
                      f"не JUnit")
    ids = _Ids(component, workdir)
    records = []
    for case in root.iter("testcase"):
        path, name = _junit_location(case, cwd)
        found = {child.tag: child for child in case
                 if child.tag in ("failure", "error", "skipped")}
        failure = skip_reason = detail = ""
        level = next((found[tag] for tag in ("error", "failure")
                      if tag in found and found[tag].get("message")
                      == COLLECTION_FAILURE), None)
        if level is not None:
            detail = (level.text or "")[:DETAIL_LIMIT]
        if "error" in found:
            outcome, failure = ERROR, _junit_failure(found["error"])
        elif "failure" in found:
            outcome, failure = FAILED, _junit_failure(found["failure"])
        elif "skipped" in found:
            outcome = SKIPPED
            skip_reason = _first_line(found["skipped"].get("message") or "") \
                or _first_line(found["skipped"].text or "")
        else:
            outcome = PASSED
        records.append(CaseResult(ids(path, name), outcome, failure,
                                  skip_reason, _seconds(case.get("time")),
                                  file_level=level is not None, detail=detail))
    return records, ""


def _vitest_case(item: dict, failure_errors) -> tuple[str, str, str]:
    """(исход, вид падения, причина пропуска) записи отчётчика пульта
    (требование 6): имя ошибки из `failure_errors` — провал проверки;
    иное имя, таймаут и падение хука — ошибка."""
    state = item.get("state")
    mode = str(item.get("mode") or "run")
    error_name = str(item.get("error_name") or "")
    if state == "pass":
        return PASSED, "", ""
    if state in ("skip", "todo"):
        return SKIPPED, "", f"{state} (mode: {mode})"
    if state != "fail":
        return ERROR, f"неизвестное состояние теста {state!r}", ""
    if item.get("hook"):
        return ERROR, (f"падение хука {item['hook']}: "
                       f"{error_name or 'ошибка без имени'}"), ""
    if item.get("timeout"):
        return ERROR, f"timeout: {error_name or 'превышено время теста'}", ""
    if error_name and error_name in failure_errors:
        return FAILED, error_name, ""
    return ERROR, error_name or "ошибка без имени", ""


def parse_vitest(report: Path, component: str, workdir: str,
                 failure_errors=()) -> tuple[list | None, str]:
    """(записи `CaseResult`, причина) JSON отчётчика пульта `report`;
    `None` — отчёта нет или он не той формы."""
    try:
        data = json.loads(Path(report).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"отчёт {report} не создан"
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return None, f"отчёт {report} не разобран: {exc}"
    tests = data.get("tests") if isinstance(data, dict) else None
    if not isinstance(tests, list):
        return None, f"отчёт {report} не разобран: нет списка tests"
    ids = _Ids(component, workdir)
    records = []
    for item in tests:
        if not isinstance(item, dict) or not item.get("name"):
            return None, (f"отчёт {report} не разобран: запись теста без "
                          f"имени: {item!r}"[:300])
        try:
            retries = int(item.get("retry_count") or 0)
        except (TypeError, ValueError):
            return None, (f"отчёт {report} не разобран: retry_count "
                          f"{item.get('retry_count')!r}")
        level = item.get("file_level") is True
        if level:
            # Ошибка модуля — не провал проверки, даже если её имя есть в
            # `failure_errors`: тесты файла не исполнялись.
            outcome, failure, skip_reason = (
                ERROR, str(item.get("error_name") or "ошибка без имени"), "")
        else:
            outcome, failure, skip_reason = _vitest_case(item, failure_errors)
        records.append(CaseResult(
            ids(str(item.get("file") or ""), str(item["name"])), outcome,
            failure, skip_reason, _seconds(item.get("duration_ms")) / 1000,
            str(item.get("mode") or "run"), bool(item.get("fails")), retries,
            file_level=level,
            detail=str(item.get("error_message") or "") if level else ""))
    return records, ""


# Статус теста отчёта задания CI (`forge.TestReport`) → исход записи (SPEC
# 01M5XZSKK8H096FD3CPN05BQNM, требование 8); иной статус — «неизвестно».
FORGE_OUTCOMES = {"success": PASSED, "failed": FAILED, "skipped": SKIPPED,
                  "error": ERROR}


def _forge_location(classname: str, name: str, workdir: str,
                    tree_files) -> tuple[str | None, str]:
    """(путь файла от `workdir`, полное имя) записи отчёта задания CI;
    путь `None` — модуль точечного `classname` не найден в дереве: самый
    длинный префикс частей, чей `.py` есть файлом под `workdir`."""
    if "/" in classname:
        return classname, name
    parts = classname.split(".")
    for size in range(len(parts), 0, -1):
        candidate = "/".join(parts[:size]) + ".py"
        if _root_path(workdir, candidate) in tree_files:
            return candidate, "::".join([*parts[size:], name])
    return None, ""


def forge_key_ids(outcomes: dict, component: str, workdir: str,
                  tree_files) -> tuple[dict, list]:
    """({ключ отчёта задания CI: идентификатор}, неразобранные ключи
    [(ключ, причина)]): ключ без `::` или с модулем, не найденным в дереве
    коммита отчёта, идентификатора не получает (требование 8)."""
    from .. import project_profile  # project_profile -> store -> … -> acceptance
    ids: dict = {}
    unresolved = []
    for key in sorted(outcomes):
        classname, sep, name = key.partition("::")
        path, full = (_forge_location(classname, name, workdir, tree_files)
                      if sep else (None, ""))
        if path is None:
            unresolved.append((key, f"модуль «{classname}» не найден в дереве "
                                    f"коммита отчёта"))
            continue
        ids[key] = project_profile.test_id(
            component, _root_path(workdir, path), full)
    return ids, unresolved


def parse_forge_report(outcomes: dict, component: str, workdir: str,
                       tree_files) -> tuple[list, list]:
    """(записи `CaseResult`, неразобранные ключи) отчёта задания CI
    `<classname>::<name>` → статус (требование 8). `tree_files` — пути от
    корня репозитория файлов дерева коммита отчёта.

    Неоднозначный перевод не зелёный (инвариант 41): статус вне
    `FORGE_OUTCOMES` и два ключа с одним идентификатором дают запись с
    исходом `UNKNOWN` и причиной в `failure`; ключ без `::` или с
    модулем, не найденным в дереве, идентификатора не получает — он в
    списке [(ключ, причина)]."""
    ids, unresolved = forge_key_ids(outcomes, component, workdir, tree_files)
    located: dict = {}
    for key, cid in ids.items():
        located.setdefault(cid, []).append(key)
    records = []
    for cid, keys in located.items():
        status = outcomes[keys[0]]
        if len(keys) > 1:
            records.append(CaseResult(cid, UNKNOWN, f"ключи отчёта "
                                                    f"{', '.join(keys)} дают "
                                                    f"один идентификатор"))
        elif status not in FORGE_OUTCOMES:
            records.append(CaseResult(cid, UNKNOWN, f"статус {status!r} вне "
                                                    f"{' | '.join(FORGE_OUTCOMES)}"))
        else:
            records.append(CaseResult(cid, FORGE_OUTCOMES[status]))
    return records, unresolved


def verdict(records: list | None, returncode: int | None,
            reason: str = "") -> tuple[str, str]:
    """(вердикт `GREEN`/`RED`/`UNKNOWN`, причина) прогона по записям отчёта
    и коду возврата (требование 3; инвариант 41): записей нет (`None`) —
    «неизвестно» с причиной разбора; отчёт без тестов при ненулевом коде —
    «неизвестно»; упавший тест или тест с повтором — красный; ненулевой
    код при отчёте без падений — «неизвестно»: что-то сломалось вне
    тестов отчёта."""
    if records is None:
        return UNKNOWN, reason or "отчёта нет"
    if not records:
        if returncode:
            return UNKNOWN, f"отчёт без тестов, код возврата {returncode}"
        return GREEN, ""
    bad = [r for r in records if r.outcome in (FAILED, ERROR)]
    if bad:
        return RED, f"{bad[0].id} — {bad[0].outcome}: {bad[0].failure}"
    retried = [r for r in records if r.retries > 0]
    if retried:
        return RED, (f"{retried[0].id} — {RETRY_NOTE}: "
                     f"{retried[0].retries} внутри прогона")
    if returncode:
        return UNKNOWN, (f"код возврата {returncode} при отчёте без упавших "
                         f"тестов")
    return GREEN, ""


def summary_line(records: list) -> str:
    """Итоговая строка в форме pytest по записям отчёта: тест с повтором
    считается упавшим — он красит прогон."""
    retried = sum(1 for r in records if r.outcome == PASSED and r.retries > 0)
    counts = (("failed", sum(1 for r in records if r.outcome == FAILED)
               + retried),
              ("passed", sum(1 for r in records if r.outcome == PASSED)
               - retried),
              ("error", sum(1 for r in records if r.outcome == ERROR)),
              ("skipped", sum(1 for r in records if r.outcome == SKIPPED)))
    parts = [f"{n} {kind}" for kind, n in counts if n] or ["0 passed"]
    seconds = sum(r.time for r in records)
    return f"{', '.join(parts)} in {seconds:.2f}s"


def summary_block(records: list) -> str:
    """Сводка итога из отчёта в форме короткого итога pytest (модуль)."""
    lines = ["=" * 20 + " short test summary info " + "=" * 20]
    for r in records:
        if r.outcome in (FAILED, ERROR):
            head = "FAILED" if r.outcome == FAILED else "ERROR"
            lines.append(f"{head} {r.id} - {r.failure}" if r.failure
                         else f"{head} {r.id}")
        elif r.retries > 0:
            lines.append(f"FAILED {r.id} - {RETRY_NOTE}: {r.retries} "
                         f"внутри прогона (тест прошёл не с первого раза)")
    lines.append(f"{'=' * 20} {summary_line(records)} {'=' * 20}")
    return "\n".join(lines)
