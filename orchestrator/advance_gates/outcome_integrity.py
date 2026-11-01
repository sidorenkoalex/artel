"""Гейт неослабления по исходам тестов на переходе `in_dev -> verifying` (SPEC 01M5CJVB5B5V55PQQVR2QRHWZN; ADR-0026, «Решение» п. 6).

Гейт по тексту (`test_integrity`) читает только Python-текст `tests/`:
тест Vitest он не видит вовсе, а тест, сломанный правкой кода или ставший
нестабильным, по тексту не отличим от прежнего. Этот гейт сравнивает
ИСХОДЫ: полный набор единственного компонента проекта гоняется на выписке
базы сравнения (`gitcmd.diff_base`) и на выписке головы кодовой ветки,
отчёты сравниваются по идентификаторам тестов (`project_profile.test_id`).

`PASS_TO_PASS` — тесты, прошедшие на базе без повторов. Красный на ветке
тест набора перепрогоняется ещё дважды на ветке и дважды на базе только
своим файлом (`acceptance._report_run`): итог — по записи теста, не по
вердикту прогона. Трижды красный на ветке при трижды зелёной базе —
«сломан правкой» (чинит роль); красный и зелёный вперемешку — «нестабилен
после правки»; красная база — не находка, а строка журнала «нестабилен и
на базе».

Сравнение двух отчётов (`compare`) находит исчезнувшие тесты базы, тесты,
ставшие пропуском, появившиеся `todo`/`fails` и новые тесты с пропуском,
`todo` или `fails`. Находку снимает мандат Оператора «Ослабление тестов
разрешено:» на путь файла или префикс `путь::имя` либо «Ослабление теста по
идентификатору разрешено:» на идентификатор теста целиком, с `#n` (SPEC
01M5D02N3B428V8BWC3PAM9QCT, требование 5; сбор — `_answer_mandates`, с
отбраковкой автокоммита роли тем же признаком, что у гейта по тексту).

Граница — `in_outcome_bounds` профиля решения `decide`: артель, запись
`test_profile`, запись из нескольких компонентов и канареечная задача
гейта не создают — ни прогона, ни записи журнала. Внутри границы любой
сбой подготовки — отказ, не пропуск (fail-closed, ADR-0002).

Тот же гейт стоит в окне мержа (`merge_gate_escalates`, SPEC
01M5DDTVZEA40ZB9BHEH4YDEE7): база — merge-base головы со свежим sha main.
Запись пройденного гейта несёт строку `голова …; база …; ключ …; мандат …`
— доказательство: запись с той же четвёркой избавляет мерж от прогона.

G3б-2 (SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J; ADR-0026, «Решение» пп. 6-7):
прежние версии изменённых и удалённых файлов тестов и поддержки (набор C)
и файлы утверждённых заменяемых тестов гоняются на третьей выписке —
голове с восстановленными из базы путями C и без добавленных веткой
файлов тестов и поддержки: тест, «подогнанный» правкой под сломанный код,
там красный. Утверждённая замена (`mandate.approved_replacements`)
сверяется на деле и снимает только «исчез» и «прежняя версия красная» своего
теста. Без слоя `python-ast` правка существующего файла тестов или
поддержки — находка строгого режима; добавленная строка кода с подстрокой
`CODE_EXCEPTION_TOKENS` — находка «исключение в коде». Обе снимает только
мандат на путь файла.

Режим `ci` (SPEC 01M5XZSKK8H096FD3CPN05BQNM): на гейте мержа у компонента
`full_suite: ci` исходы головы и базы — отчёты задания `ci_job`
(`forge.job_test_report`), без выписок, перепрогонов, третьей выписки и
доказательства `_proven` (`_judge_ci`). Отчёт головы — ровно её sha; отчёт
базы — точки ответвления, иначе её родителя с тем же деревом. Нет годного
отчёта стороны или отчёт базы неоднозначен — сбой подготовки. На выходе из
`in_dev` компонент `ci` судится локальными выписками, как прежде.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

from .. import acceptance
from .. import artifact_branch as docs_ref
from .. import (artifact_source, config, forge, gitcmd, liveness,
               project_profile, store, targets, workspace)
from ..reporters import outcome
from . import refusal_classes
from ._base import GateRefusal, _run_gates
from .acceptance import in_outcome_bounds
from .mandate import (TEST_ID_MANDATE_MARKER, TEST_WEAKENING_MANDATE_MARKER,
                      approved_replacements, elements, id_elements)
from .zones import _answer_commit_is_role_step_autocommit

# Действия журнала (требование 6); литералы повторены в
# `refusal_classes.REFUSAL_CLASSES`.
OUTCOME_REFUSAL_ACTION = "переход отклонён: гейт неослабления по исходам"
BROKEN_REFUSAL_ACTION = f"{OUTCOME_REFUSAL_ACTION} — сломан правкой"
PREPARE_REFUSAL_ACTION = f"{OUTCOME_REFUSAL_ACTION} — подготовка"
PASSED_ACTION = "гейт неослабления по исходам пройден"
FLAKY_ON_BASE = "нестабилен и на базе"

# Гейт исходов на гейте мержа (SPEC 01M5DDTVZEA40ZB9BHEH4YDEE7, требования
# 1-4): тексты действий — из `refusal_classes`, один источник с их классом
# (SPEC 01M5FRYVP4NF81VT00FYPHPWJH, требование 10).
MERGE_REFUSAL_ACTION = refusal_classes.OUTCOME_MERGE_REFUSAL_ACTION
MERGE_PREPARE_ACTION = refusal_classes.OUTCOME_MERGE_PREPARE_ACTION
PROVEN_ACTION = "гейт исходов: доказан"
NOT_RUN_LINE = "гейт исходов для головы {head} не исполнялся"
MANDATE_NONE = "нет"
COVERED_MARK = " — покрыто мандатом "
# Строка доказательства записи `PASSED_ACTION` — сразу после строки чисел.
PROOF_LINE = re.compile(r"^голова ([0-9a-f]{40}); база ([0-9a-f]{40}); "
                        r"ключ (\S+); мандат (\S+)$")

# Виды находок в порядке старшинства отказа (требование 6): исчезнувшие,
# «сломан правкой», «нестабилен после правки», прочие находки сравнения.
GONE = "исчез"
BROKEN = "сломан правкой"
UNSTABLE = "нестабилен после правки"
BECAME_SKIPPED = "стал пропуском"
TODO_APPEARED = "появилось todo"
FAILS_APPEARED = "появилось fails"
NEW_SKIPPED = "новый тест — пропуск"
NEW_TODO = "новый тест — todo"
NEW_FAILS = "новый тест — fails"
# Виды G3б-2 (SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J, требование 9) — после
# прежних, в порядке требования.
PRIOR_RED = "прежняя версия красная на коде ветки"
PRIOR_UNSTABLE = "прежняя версия нестабильна на коде ветки"
REPLACED_MISSING = "заменяемый тест не найден в отчёте базы"
REPLACED_NOT_GREEN = "заменяемый тест не зелёный на базе"
REPLACED_NEEDLESS = "замена не нужна: прежняя версия зелёная на коде ветки"
STRICT_EDIT = "строгий режим — правка существующего файла"
CODE_EXCEPTION = "исключение в коде"
# Режим `ci` (SPEC 01M5XZSKK8H096FD3CPN05BQNM, требование 6): прежнюю
# версию зелёного в базе заменяемого теста проверить негде.
REPLACED_UNCHECKABLE = "замена теста не проверяема в режиме ci"
_RANK = {GONE: 0, BROKEN: 1, UNSTABLE: 2, PRIOR_RED: 4, PRIOR_UNSTABLE: 5,
         REPLACED_MISSING: 6, REPLACED_NOT_GREEN: 7, REPLACED_NEEDLESS: 8,
         STRICT_EDIT: 9, CODE_EXCEPTION: 10, REPLACED_UNCHECKABLE: 11}
_OTHER_RANK = 3
# Находки, идентификатор которых — путь файла, а не тест: снимает их только
# мандат на путь (`_path_covering`).
_PATH_KINDS = (STRICT_EDIT, CODE_EXCEPTION)
_NEW_KINDS = (PRIOR_RED, PRIOR_UNSTABLE, REPLACED_MISSING, REPLACED_NOT_GREEN,
              REPLACED_NEEDLESS, STRICT_EDIT, CODE_EXCEPTION)
# Находки, которые снимает утверждённая замена своего теста (требование 4).
_REPLACEABLE_KINDS = (GONE, PRIOR_RED)
REPLACED = "заменён по SPEC"
REPLACEMENT_ELEMENT = "замена:{id}→AC-{n}"
REPLACEMENT_SOURCE = "замена SPEC → AC-{n}"
PRIOR_LINE = "прежние версии: файлов {files}; прогонов {runs}"
# Подстроки исключений в коде (требование 7): текстовый поиск в
# добавленных строках, без разбора синтаксиса.
CODE_EXCEPTION_TOKENS = ("v8 ignore", "istanbul ignore", "c8 ignore",
                         "eslint-disable", "import.meta.env.MODE",
                         "process.env.VITEST", "NODE_ENV")
_PYTHON_AST = "python-ast"

BASE = "база"
HEAD = "голова ветки"
PRIOR = "прежние версии"
# Каталог третьей выписки в `scratch` — рядом с выписками базы и головы.
_PRIOR_DIR = "prior"
_HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
# Перепрогонов красного теста на каждой стороне сверх полного прогона.
RERUNS = 2
_TODO_MODE = "todo"


class Finding(NamedTuple):
    """Находка по одному тесту: вид, идентификатор, исходы по прогонам."""
    kind: str
    id: str
    runs: str

    @property
    def line(self) -> str:
        return f"{self.kind}: {self.id} — {self.runs}"


class _Prepare(Exception):
    """Отказ подготовки: причина — текст исключения."""


def describe(case) -> str:
    """Исход записи для строки находки; `None` — записи нет."""
    if case is None:
        return "нет записи"
    text = case.outcome
    if case.mode == _TODO_MODE:
        text += " (todo)"
    if case.fails:
        text += " (fails)"
    if case.retries:
        text += f" (повторов {case.retries})"
    return text


def in_pass_to_pass(case) -> bool:
    """Тест прошёл на базе без повторов (требование 3)."""
    return case.outcome == outcome.PASSED and case.retries == 0


def red_on_branch(case) -> bool:
    """Красный в полном прогоне ветки: `failed`, `error` или `passed` с
    повтором; `skipped` — не красный, его ловит сравнение."""
    return case.outcome in (outcome.FAILED, outcome.ERROR) or \
        (case.outcome == outcome.PASSED and case.retries > 0)


def compare(base: list, head: list) -> list:
    """Находки сравнения двух списков `CaseResult` (требование 4), по одной
    на идентификатор, по старшинству и идентификатору. Красноту тестов
    `PASS_TO_PASS` судят перепрогоны, не эта функция.

    Запись ошибки уровня файла (`file_level`) — не тест: её исчезновение на
    ветке значит «ошибку исправили» (SPEC 01M5EDW6KD1ESCEVRSV2WPNXAP,
    требование 1)."""
    base_map = {c.id: c for c in base if not c.file_level}
    head_map = {c.id: c for c in head if not c.file_level}
    found = []
    for cid, b in base_map.items():
        h = head_map.get(cid)
        runs = f"база: {describe(b)}; ветка: {describe(h)}"
        if h is None:
            found.append(Finding(GONE, cid, runs))
        elif h.mode == _TODO_MODE and b.mode != _TODO_MODE:
            found.append(Finding(TODO_APPEARED, cid, runs))
        elif h.outcome == outcome.SKIPPED and b.outcome != outcome.SKIPPED:
            found.append(Finding(BECAME_SKIPPED, cid, runs))
        elif h.fails and not b.fails:
            found.append(Finding(FAILS_APPEARED, cid, runs))
    for cid, h in head_map.items():
        if cid in base_map:
            continue
        runs = f"база: нет записи; ветка: {describe(h)}"
        if h.mode == _TODO_MODE:
            found.append(Finding(NEW_TODO, cid, runs))
        elif h.outcome == outcome.SKIPPED:
            found.append(Finding(NEW_SKIPPED, cid, runs))
        elif h.fails:
            found.append(Finding(NEW_FAILS, cid, runs))
    return ordered(found)


def ordered(findings: list) -> list:
    return sorted(findings, key=lambda f: (_RANK.get(f.kind, _OTHER_RANK), f.id))


def skip_growth(base: list, head: list) -> str:
    """Итоговая строка отказа о росте числа пропусков компонента; пусто —
    не выросло (требование 4: не отдельная находка)."""
    before = sum(1 for c in base if c.outcome == outcome.SKIPPED)
    after = sum(1 for c in head if c.outcome == outcome.SKIPPED)
    if after <= before:
        return ""
    return f"число пропусков компонента выросло: база {before}, ветка {after}"


def covering(cid: str, mandate: dict):
    """Имя ANSWER-n, чей элемент мандата покрывает тест `cid` (требование
    5): путь его файла либо префикс `путь::имя`, за которым конец имени,
    `::`, `[` или `#`; `None` — не покрыт."""
    pair = _covering_element(cid, mandate)
    return pair[1] if pair is not None else None


def _covering_element(cid: str, mandate: dict):
    """(элемент мандата, ANSWER-n) — правило `covering`; `None` — не
    покрыт."""
    try:
        _comp, path, _name, _n = project_profile.parse_test_id(cid)
    except ValueError:
        return None
    rest = cid.partition(":")[2]
    for element, source in mandate.items():
        if element == path:
            return element, source
        if "::" not in element or not rest.startswith(element):
            continue
        tail = rest[len(element):]
        if not tail or tail.startswith(("::", "[", "#")):
            return element, source
    return None


def _covering(cid: str, mandate: dict, id_mandate: dict):
    """Имя ANSWER-n, покрывающего тест `cid`: мандат по идентификатору —
    только точным равенством (с `#n`, без префиксного правила), прежний
    мандат — `covering`; `None` — не покрыт."""
    pair = _covering_pair(cid, mandate, id_mandate)
    return pair[1] if pair is not None else None


def _covering_pair(cid: str, mandate: dict, id_mandate: dict):
    """(элемент мандата, ANSWER-n) по правилу `_covering`; `None` — не
    покрыт."""
    source = id_mandate.get(cid)
    if source is not None:
        return cid, source
    return _covering_element(cid, mandate)


def _path_covering(path: str, mandate: dict):
    """(элемент, ANSWER-n) прежнего маркера, равный пути `path` (SPEC
    01M5J0JYW3GZSSHHK3TYCYTQ3J, требования 5, 7): мандат по идентификатору
    и префикс `путь::имя` находку пути не снимают; `None` — не покрыта."""
    source = mandate.get(path)
    return (path, source) if source is not None else None


def _cover(finding: Finding, mandate: dict, id_mandate: dict,
           replacements: dict):
    """(элемент, источник), покрывающие находку; `None` — не покрыта.
    Находку пути — `_path_covering`; находку теста — мандат Оператора
    (`_covering_pair`), затем утверждённая замена, но только «исчез» и
    «прежняя версия красная» своего теста (требование 4)."""
    if finding.kind in _PATH_KINDS:
        return _path_covering(finding.id, mandate)
    pair = _covering_pair(finding.id, mandate, id_mandate)
    if pair is None and finding.kind in _REPLACEABLE_KINDS and \
            finding.id in replacements:
        n = replacements[finding.id]
        return (REPLACEMENT_ELEMENT.format(id=finding.id, n=n),
                REPLACEMENT_SOURCE.format(n=n))
    return pair


def _replacements(conn, task_id: str, profile) -> dict:
    """{идентификатор: номер критерия} утверждённых замен компонента
    профиля по последней записи утверждения."""
    found = {}
    for cid, n in approved_replacements(conn, task_id).items():
        try:
            component = project_profile.parse_test_id(cid)[0]
        except ValueError:
            continue
        if component == profile.component:
            found[cid] = n
    return found


def _replacement_elements(replacements: dict) -> list:
    """Элементы отпечатка всех утверждённых замен компонента (требование
    9): смена их состава или содержимого отменяет доказательство."""
    return [REPLACEMENT_ELEMENT.format(id=cid, n=n)
            for cid, n in replacements.items()]


def fingerprint(elements_used) -> str:
    """Отпечаток мандата записи пройденного гейта (SPEC
    01M5DDTVZEA40ZB9BHEH4YDEE7, требование 1): sha256 (hex) элементов,
    покрывших находки, и элементов `замена:…` утверждённых замен (SPEC
    01M5J0JYW3GZSSHHK3TYCYTQ3J, требование 9) — отсортированы и соединены
    переводом строки, utf-8; таких элементов нет — «нет»."""
    used = sorted(set(elements_used))
    if not used:
        return MANDATE_NONE
    return hashlib.sha256("\n".join(used).encode("utf-8")).hexdigest()


def _answer_mandates(artifact_branch: str, task_id: str) -> tuple:
    """({элемент прежнего маркера: ANSWER-n}, {идентификатор нового
    маркера: ANSWER-n}) по ВСЕМ `tasks/<id>/ANSWER-n.md` ссылки документов.
    Файл, чей последний коммит — доказанный автокоммит шага роли, не
    мандат Оператора (`zones._answer_commit_is_role_step_autocommit`):
    иначе developer выписал бы себе разрешение сам."""
    paths = docs_ref.ls_tree(task_id, artifact_branch, f"tasks/{task_id}") or []
    mandate: dict = {}
    id_mandate: dict = {}
    for p in sorted(paths):
        name = p.rsplit("/", 1)[-1]
        if not (name.startswith("ANSWER-") and name.endswith(".md")):
            continue
        if _answer_commit_is_role_step_autocommit(artifact_branch, task_id, p):
            continue
        text, _reason = docs_ref.show(task_id, artifact_branch, p)
        if text is None:
            continue
        source = name[:-len(".md")]
        for line in text.splitlines():
            for element in elements(line, TEST_WEAKENING_MANDATE_MARKER) or ():
                mandate.setdefault(element, source)
            for element in id_elements(line) or ():
                id_mandate.setdefault(element, source)
    return mandate, id_mandate


def _mandate_hint(task_id: str, path_mandate: bool = False) -> str:
    """Подсказка отказа с обоими маркерами, снимающими находку этого
    гейта (SPEC 01M5D02N3B428V8BWC3PAM9QCT, требование 5); при находке
    вида G3б-2 — ещё мандат на путь файла (SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J,
    требование 9)."""
    path_note = (f"; находку «{STRICT_EDIT}» и «{CODE_EXCEPTION}» снимает "
                 f"только мандат на путь файла — строка "
                 f"«{TEST_WEAKENING_MANDATE_MARKER} <путь файла>»"
                 if path_mandate else "")
    return (f"либо верни тесты на место, либо получи мандат Оператора — "
            f"строка «{TEST_WEAKENING_MANDATE_MARKER} <пути и имена>» или "
            f"«{TEST_ID_MANDATE_MARKER} <идентификатор теста>» (по строке на "
            f"идентификатор){path_note} в tasks/{task_id}/ANSWER-n.md "
            f"(команда artel.py answer {task_id} <файл>: в состоянии in_dev — без смены "
            f"состояния, в состоянии escalated — ответом на эскалацию; со "
            f"ссылкой на основание), и повтори artel.py advance {task_id}")


def _git_reason(res) -> str:
    if res is None:
        return "git не ответил"
    return (res.stderr or res.stdout or "").strip()[:300] or \
        f"git вернул код {res.returncode}"


def _full_runs(task_id: str, profile, trees: dict) -> dict:
    """{сторона: записи полного набора}; исход «не начат»/«неизвестно» или
    таймаут — `_Prepare` с названной стороной."""
    return {side: _full_run(task_id, profile, side, tree)
            for side, tree in trees.items()}


def _full_run(task_id: str, profile, side: str, tree: Path) -> list:
    """Записи полного набора стороны `side`; отказ — `_Prepare`."""
    run = acceptance.components_full_suite(tree, task_id, (profile,),
                                           fresh=True)
    if run.outcome in (acceptance.FULL_SUITE_NOT_STARTED,
                       acceptance.FULL_SUITE_TIMEOUT):
        raise _Prepare(f"полный набор на стороне «{side}»: {run.outcome} "
                       f"— {run.detail.strip()[:500]}")
    return ([] if run.outcome == acceptance.FULL_SUITE_NO_TESTS
            else list(run.tests))


def _rerun(profile, trees: dict, red: list, history: dict,
           sides: tuple = (HEAD, BASE)) -> int:
    """Перепрогоны красных тестов `red` по их файлам (требование 3) на
    сторонах `sides` (сторона ветки и база): дописывает в `history` {id:
    {сторона: [(красный, исход)]}}; число прогонов файлов. Отказ
    подготовки — `_Prepare`."""
    files: dict = {}
    for cid in red:
        path = project_profile.parse_test_id(cid)[1]
        files.setdefault(path, []).append(cid)
    limit = project_profile.component_limit(profile)[0]
    count = 0
    for _round in range(RERUNS):
        for side in sides:
            for path in sorted(files):
                run = acceptance.report_run(profile, trees[side], [path], limit)
                count += 1
                where = f"перепрогон {path} на стороне «{side}»"
                if run.refusal:
                    raise _Prepare(f"{where}: {run.refusal}")
                if run.timed_out:
                    raise _Prepare(f"{where}: таймаут ({limit} с)")
                if run.state not in (outcome.GREEN, outcome.RED):
                    raise _Prepare(f"{where}: исход «{run.state}» — {run.reason}")
                records = {c.id: c for c in run.tests}
                for cid in files[path]:
                    case = records.get(cid)
                    if side == BASE and (case is None
                                         or case.outcome == outcome.SKIPPED):
                        raise _Prepare(f"{where}: у теста {cid} {describe(case)}"
                                       f" — исход базы не судим")
                    green = case is not None and in_pass_to_pass(case)
                    history[cid][side].append((not green, describe(case)))
    return count


def _redness(red: list, history: dict) -> tuple:
    """(находки «сломан правкой»/«нестабилен после правки», тесты,
    нестабильные и на базе) по истории трёх прогонов каждой стороны."""
    found, flaky = [], []
    for cid in red:
        sides = history[cid]
        runs = "; ".join(f"{'ветка' if side == HEAD else 'база'}: "
                         f"{', '.join(text for _red, text in sides[side])}"
                         for side in (HEAD, BASE))
        if any(is_red for is_red, _text in sides[BASE]):
            flaky.append(cid)
        elif all(is_red for is_red, _text in sides[HEAD]):
            found.append(Finding(BROKEN, cid, runs))
        else:
            found.append(Finding(UNSTABLE, cid, runs))
    return found, flaky


def _prior_runs_text(sides: dict) -> tuple:
    """(исходы прежней версии, исходы базы) истории третьей выписки."""
    return tuple(", ".join(text for _red, text in sides[side])
                 for side in (PRIOR, BASE))


def _prior_redness(red: list, history: dict) -> tuple:
    """(находки «прежняя версия красная/нестабильна на коде ветки», тесты,
    нестабильные и на базе) — правило `_redness` по истории третьей
    выписки (SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J, требование 3)."""
    found, flaky = [], []
    for cid in red:
        sides = history[cid]
        prior, base = _prior_runs_text(sides)
        runs = f"прежняя версия: {prior}; база: {base}"
        if any(is_red for is_red, _text in sides[BASE]):
            flaky.append(cid)
        elif all(is_red for is_red, _text in sides[PRIOR]):
            found.append(Finding(PRIOR_RED, cid, runs))
        else:
            found.append(Finding(PRIOR_UNSTABLE, cid, runs))
    return found, flaky


def _record_paths(records) -> set:
    """Пути файлов записей отчёта, включая записи ошибок уровня файла."""
    found = set()
    for case in records:
        try:
            found.add(project_profile.parse_test_id(case.id)[1])
        except ValueError:
            continue
    return found


class _Files(NamedTuple):
    """Роли файлов компонента в гейте (SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J,
    требование 2): `base_paths`/`head_paths` — пути файлов записей полных
    отчётов базы и головы."""
    profile: object
    base_paths: set
    head_paths: set

    def is_test(self, path: str) -> bool:
        """Тестовый файл компонента: под масками `tests`, без них — среди
        файлов полного отчёта базы."""
        if self.profile.tests:
            return any(project_profile.mask_matches(mask, path)
                       for mask in self.profile.tests)
        return path in self.base_paths

    def is_support(self, path: str) -> bool:
        return any(project_profile.mask_matches(mask, path)
                   for mask in self.profile.test_support)

    def dropped_on_prior(self, path: str) -> bool:
        """Файл `A`, удаляемый на третьей выписке: под масками `tests` и
        `test_support`, у компонента без `tests` — любой под
        `weakening_scope` (ANSWER-2)."""
        if self.is_support(path):
            return True
        if self.profile.tests:
            return self.is_test(path)
        return self.profile.in_weakening_scope(path)

    def in_component(self, path: str) -> bool:
        """Файл компонента по `paths`; без `paths` — любой файл."""
        return not self.profile.paths or any(
            re.search(regex, path) for regex in self.profile.paths)


def _name_status(repo: Path, base_sha: str, head_sha: str) -> list:
    """Записи `diff --name-status` базы и головы; сбой — `_Prepare`, не
    пустой набор (требование 8)."""
    entries = gitcmd.diff_name_status(base_sha, head_sha, repo=repo)
    if entries is None:
        raise _Prepare(f"diff --name-status базы {base_sha[:12]} и головы "
                       f"{head_sha[:12]} не получен")
    return entries


def _unquote(text: str) -> str:
    """Путь вывода git, взятый в кавычки с экранированием в стиле C."""
    if not (len(text) >= 2 and text.startswith('"') and text.endswith('"')):
        return text
    escapes = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13,
               '"': 34, "\\": 92}
    body, out, i = text[1:-1], bytearray(), 0
    while i < len(body):
        ch = body[i]
        octal = body[i + 1:i + 4]
        if ch == "\\" and len(octal) == 3 and all(c in "01234567"
                                                  for c in octal):
            out.append(int(octal, 8) & 0xFF)
            i += 4
        elif ch == "\\" and body[i + 1:i + 2] in escapes:
            out.append(escapes[body[i + 1]])
            i += 2
        else:
            out += ch.encode("utf-8")
            i += 1
    return out.decode("utf-8", errors="replace")


def _added_lines(repo: Path, base_sha: str, head_sha: str) -> dict:
    """{путь головы: [(номер строки по голове, текст)]} строк, добавленных
    диффом `git diff -M -U0` базы и головы (требование 7): переименование
    без правки строк и двоичный файл ханков не дают. Вывод читается
    байтами: текст не в utf-8 не роняет гейт. Сбой — `_Prepare`
    (требование 8).

    Вывод не должен зависеть от конфига git процесса пульта (`pult_env`
    наследует `~/.gitconfig`): префиксы, `diff.relative` и textconv заданы
    явно, а заголовок `+++ ` неожиданной формы — тоже `_Prepare`, не
    молчаливый пропуск строк файла."""
    try:
        res = gitcmd.read(repo, "-c", "core.quotePath=false", "diff",
                          "--no-color", "--no-ext-diff", "--no-textconv",
                          "--no-relative", "--src-prefix=a/", "--dst-prefix=b/",
                          "-M", "-U0", base_sha, head_sha)
    except OSError as exc:
        raise _Prepare(f"diff -M -U0 базы {base_sha[:12]} и головы "
                       f"{head_sha[:12]} не получен: {exc}") from exc
    if res.returncode != 0:
        reason = (res.stderr or b"").decode("utf-8", errors="replace").strip()
        raise _Prepare(f"diff -M -U0 базы {base_sha[:12]} и головы "
                       f"{head_sha[:12]} не получен: "
                       f"{reason[:300] or f'git вернул код {res.returncode}'}")
    added: dict = {}
    path, old_left, new_left, number = None, 0, 0, 0
    for line in res.stdout.decode("utf-8", errors="replace").split("\n"):
        if old_left > 0 or new_left > 0:
            if line.startswith("+") and new_left > 0:
                if path is not None:
                    added.setdefault(path, []).append((number, line[1:]))
                number += 1
                new_left -= 1
                continue
            if line.startswith("-") and old_left > 0:
                old_left -= 1
                continue
            if line.startswith("\\"):
                continue
            old_left = new_left = 0
        if line.startswith("diff --git "):
            path = None
        elif line.startswith("+++ "):
            target = _unquote(line[4:])
            if target == "/dev/null":
                path = None
            elif target.startswith("b/"):
                path = target[2:]
            else:
                raise _Prepare(f"diff -M -U0 базы {base_sha[:12]} и головы "
                               f"{head_sha[:12]}: заголовок {line[:200]!r} "
                               f"без префикса b/")
        else:
            m = _HUNK_RE.match(line)
            if m:
                old_left = int(m.group(1) if m.group(1) is not None else 1)
                number = int(m.group(2))
                new_left = int(m.group(3) if m.group(3) is not None else 1)
    return added


def _strict_findings(profile, files: _Files, entries: list) -> list:
    """Находки строгого режима (требование 5): без `python-ast` — каждый
    существующий файл тестов или поддержки из диффа (у `R` — прежний путь),
    с `python-ast` — только файлы не `.py` под `test_support`."""
    strict = _PYTHON_AST not in project_profile.layers_of(profile)
    found = []
    for status, path, _new in entries:
        if status.startswith(("A", "C")):
            continue
        support = files.is_support(path)
        hit = (support or files.is_test(path)) if strict else \
            (support and not path.endswith(".py"))
        if hit:
            found.append(Finding(STRICT_EDIT, path, f"статус {status}"))
    return found


def _code_exception_findings(files: _Files, entries: list,
                             added: dict) -> list:
    """Находки «исключение в коде» (требование 7) по добавленным строкам
    файлов компонента вне тестовых файлов и `test_support`; у компонента
    без `tests` тестовым считается и файл `A` под `weakening_scope` с
    записями в отчёте головы. Вид файла — по пути головы: файл,
    переименованный из тестового пути в путь кода, — файл кода."""
    origin = {(new or path): status for status, path, new in entries}
    found = []
    for path in sorted(added):
        status = origin.get(path, "M")
        if not files.in_component(path):
            continue
        if files.is_test(path) or files.is_support(path):
            continue
        # Путь головы, новый на ветке (`A`, новый путь `R`/`C`), у
        # компонента без `tests` — тестовый по тому же правилу, что `A`.
        if (not files.profile.tests and status.startswith(("A", "R", "C"))
                and files.profile.in_weakening_scope(path)
                and path in files.head_paths):
            continue
        for number, text in added[path]:
            for token in CODE_EXCEPTION_TOKENS:
                if token in text:
                    found.append(Finding(CODE_EXCEPTION, path,
                                         f"строка {number}: {token}"))
    return found


def _prior_checkout(repo: Path, scratch: Path, trees: dict, base_sha: str,
                    head_sha: str, paths: list, files: _Files,
                    entries: list) -> Path:
    """Третья выписка (требование 3): голова в `scratch`, пути C — из
    базы, добавленные веткой файлы тестов и поддержки удалены. Заведённая
    дописывается в `trees` (уборка — у вызывающего)."""
    tree = scratch / _PRIOR_DIR
    res = gitcmd.in_repo(repo, "worktree", "add", "--detach", str(tree),
                         head_sha)
    if res is None or res.returncode != 0:
        raise _Prepare(f"выписка стороны «{PRIOR}» ({head_sha[:12]}) не "
                       f"создана: {_git_reason(res)}")
    trees[PRIOR] = tree
    res = gitcmd.in_repo(tree, "checkout", base_sha, "--",
                         *(f":(literal){p}" for p in paths))
    if res is None or res.returncode != 0:
        raise _Prepare(f"прежние версии {len(paths)} файлов из базы "
                       f"{base_sha[:12]} не восстановлены: {_git_reason(res)}")
    for status, path, _new in entries:
        if not status.startswith("A") or not files.dropped_on_prior(path):
            continue
        target = tree / path
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        elif target.is_symlink() or target.exists():
            target.unlink()
    return tree


def _prior_versions(task_id: str, profile, trees: dict, tree: Path,
                    paths: list, files: _Files, base: list) -> tuple:
    """(история прежних версий {id: {сторона: [(красный, исход)]}},
    красные, прогонов на третьей выписке): путь `test_support` в C —
    полный набор компонента, иначе только файлы C; судятся тесты
    `PASS_TO_PASS` базы, чей файл попал в прогон, красный — перепрогон
    на третьей выписке и на базе."""
    if any(files.is_support(p) for p in paths):
        records = _full_run(task_id, profile, PRIOR, tree)
        ran = None
    else:
        limit = project_profile.component_limit(profile)[0]
        run = acceptance.report_run(profile, tree, list(paths), limit)
        where = f"прогон прежних версий {len(paths)} файлов"
        if run.refusal:
            raise _Prepare(f"{where}: {run.refusal}")
        if run.timed_out:
            raise _Prepare(f"{where}: таймаут ({limit} с)")
        if run.state not in (outcome.GREEN, outcome.RED):
            raise _Prepare(f"{where}: исход «{run.state}» — {run.reason}")
        records, ran = list(run.tests), set(paths)
    by_id = {c.id: c for c in records}
    history = {}
    for b in base:
        if b.file_level or not in_pass_to_pass(b):
            continue
        if ran is not None and not (_record_paths([b]) & ran):
            continue
        case = by_id.get(b.id)
        green = case is not None and in_pass_to_pass(case)
        history[b.id] = {PRIOR: [(not green, describe(case))],
                         BASE: [(False, describe(b))]}
    red = sorted(cid for cid, sides in history.items() if sides[PRIOR][0][0])
    reruns = (_rerun(profile, trees, red, history, sides=(PRIOR, BASE))
              if red else 0)
    return history, red, 1 + reruns // 2


def _replacement_findings(replacements: dict, base_map: dict,
                          history: dict) -> tuple:
    """(находки требования 4, строки «заменён по SPEC») по утверждённым
    заменам компонента."""
    found, lines = [], []
    for cid, n in sorted(replacements.items()):
        b = base_map.get(cid)
        if b is None:
            found.append(Finding(REPLACED_MISSING, cid, "база: нет записи"))
            continue
        if not in_pass_to_pass(b):
            found.append(Finding(REPLACED_NOT_GREEN, cid,
                                 f"база: {describe(b)}"))
            continue
        sides = history.get(cid)
        if sides is None:
            raise _Prepare(f"прежняя версия заменяемого теста {cid} не "
                           f"прогнана на третьей выписке")
        prior, base = _prior_runs_text(sides)
        if any(is_red for is_red, _text in sides[BASE]):
            found.append(Finding(REPLACED_NOT_GREEN, cid,
                                 f"база: {base}; прежняя версия: {prior}"))
        elif not all(is_red for is_red, _text in sides[PRIOR]):
            found.append(Finding(REPLACED_NEEDLESS, cid,
                                 f"прежняя версия: {prior}; база: {base}"))
        else:
            lines.append(f"{REPLACED}: {cid} → AC-{n}")
    return found, lines


def _checkouts(repo: Path, scratch: Path, trees: dict, base_sha: str,
               head_sha: str) -> None:
    """Выписки базы `base_sha` и головы кодовой ветки `head_sha` в
    `scratch`; заведённые дописываются в `trees` (уборка — у вызывающего).
    База — параметр (SPEC 01M5DDTVZEA40ZB9BHEH4YDEE7, требование 2): на
    выходе из `in_dev` — `diff_base`, на мерже — merge-base головы со
    свежим sha main."""
    for side, key, sha in ((BASE, "base", base_sha), (HEAD, "head", head_sha)):
        tree = scratch / key
        res = gitcmd.in_repo(repo, "worktree", "add", "--detach", str(tree), sha)
        if res is None or res.returncode != 0:
            raise _Prepare(f"выписка стороны «{side}» ({sha[:12]}) не создана: "
                           f"{_git_reason(res)}")
        trees[side] = tree


def _diff_base(repo: Path, branch: str, _head_sha: str) -> str:
    """База выхода из `in_dev` — `gitcmd.diff_base`, как до задачи."""
    base_sha = gitcmd.diff_base(branch, repo=repo)
    if not base_sha:
        raise _Prepare(f"база сравнения ветки {branch} (diff_base) не определена")
    return base_sha


def _merge_base_of(main_sha_of):
    """База гейта на мерже (требование 2): `git merge-base <голова> <sha
    main>`, sha main — повторный фетч `main_sha_of()` после «fresh». Голова,
    влившая main, даёт базой этот main; документные коммиты main после
    точки расхождения в базу не входят."""
    def base_of(repo: Path, _branch: str, head_sha: str) -> str:
        main_sha = main_sha_of()
        if not main_sha:
            raise _Prepare("sha main не получен повторным фетчем после сверки "
                           "свежести — база гейта на мерже не определена")
        res = gitcmd.in_repo(repo, "merge-base", head_sha, main_sha)
        base_sha = (res.stdout.strip()
                    if res is not None and res.returncode == 0 else "")
        if not base_sha:
            raise _Prepare(f"merge-base головы {head_sha[:12]} и main "
                           f"{main_sha[:12]} не определён: {_git_reason(res)}")
        return base_sha
    return base_of


def _component_key(repo: Path, head_sha: str, profile, head_tree: Path) -> str:
    """Ключ компонента записи (требование 1): `_report_suite_result_key`
    по дереву головы с `base=False` и рабочей копией головы (файлы
    блокировки). `None` — сбой подготовки: без ключа нет ни доказательства,
    ни записи."""
    res = gitcmd.in_repo(repo, "rev-parse", f"{head_sha}^{{tree}}")
    tree = res.stdout.strip() if res is not None and res.returncode == 0 else ""
    key = (acceptance.report_suite_result_key(tree, profile, False,
                                               root=head_tree)
           if tree else None)
    if key is None:
        raise _Prepare(f"ключ компонента для головы {head_sha[:12]} не снят "
                       f"(дерево или суммы файлов блокировки не прочитаны)")
    return key


def proof_fields(detail: str):
    """(голова, база, ключ, отпечаток) строки доказательства детали записи
    `PASSED_ACTION`; `None` — строки нет (прежняя запись)."""
    for line in (detail or "").splitlines():
        m = PROOF_LINE.match(line.strip())
        if m:
            return m.groups()
    return None


_KINDS = (GONE, BROKEN, UNSTABLE, BECAME_SKIPPED, TODO_APPEARED,
          FAILS_APPEARED, NEW_SKIPPED, NEW_TODO, NEW_FAILS, *_NEW_KINDS,
          REPLACED_UNCHECKABLE)


def _runs_marker(kind: str) -> str:
    """Граница идентификатора и исходов строки находки вида `kind`."""
    # Исходы «сломан правкой»/«нестабилен» начинаются с ветки, находки
    # прежних версий и «замена не нужна» — с прежней версии, находки пути —
    # со статуса или строки, прочие — с базы (`_redness`, `compare`).
    if kind in (BROKEN, UNSTABLE):
        return " — ветка: "
    if kind in (PRIOR_RED, PRIOR_UNSTABLE, REPLACED_NEEDLESS):
        return " — прежняя версия: "
    if kind == STRICT_EDIT:
        return " — статус "
    if kind == CODE_EXCEPTION:
        return " — строка "
    return " — база: "


def _finding_of(line: str):
    """Вид и идентификатор (тест или путь) строки находки `Finding.line` —
    `Finding` без исходов: покрытие находки зависит от её вида (SPEC
    01M5J0JYW3GZSSHHK3TYCYTQ3J, требование 9); `None` — не разобрана."""
    for kind in _KINDS:
        prefix = f"{kind}: "
        if not line.startswith(prefix):
            continue
        cid, sep, _runs = line[len(prefix):].partition(_runs_marker(kind))
        return Finding(kind, cid, "") if sep else None
    return None


def _finding_id(line: str):
    """Идентификатор (тест или путь) строки находки `Finding.line`;
    `None` — не разобран."""
    found = _finding_of(line)
    return found.id if found is not None else None


def _covered_findings(detail: str) -> list:
    """Находки, покрытые мандатом, из записи `PASSED_ACTION` (строки «… —
    покрыто мандатом ANSWER-n»); неразобранная — `None`."""
    return [_finding_of(line.rpartition(COVERED_MARK)[0])
            for line in (detail or "").splitlines() if COVERED_MARK in line]


def _covered_ids(detail: str) -> list:
    """Идентификаторы находок, покрытых мандатом, из записи
    `PASSED_ACTION`; неразобранный — `None`."""
    return [None if f is None else f.id for f in _covered_findings(detail)]


def _passed_details(conn, task_id: str) -> list:
    return [r["detail"] or "" for r in store.task_steps(conn, task_id)
            if r["action"] == PASSED_ACTION]


def _proven(conn, task_id: str, artifact_branch: str, head_sha: str,
            base_sha: str, key: str, profile) -> bool:
    """Есть запись `PASSED_ACTION` с той же головой, базой, ключом и
    отпечатком ТЕКУЩЕГО мандата над покрытыми находками той записи
    (требование 3): отозванный элемент мандата меняет отпечаток. Покрытие
    пересчитывается по виду находки (`_cover`), в отпечаток входят все
    текущие утверждённые замены компонента (SPEC
    01M5J0JYW3GZSSHHK3TYCYTQ3J, требование 9)."""
    mandates = None
    replacements = _replacements(conn, task_id, profile)
    for detail in reversed(_passed_details(conn, task_id)):
        fields = proof_fields(detail)
        if fields is None or fields[:3] != (head_sha, base_sha, key):
            continue
        covered = _covered_findings(detail)
        if covered and mandates is None:
            mandates = _answer_mandates(artifact_branch, task_id)
        pairs = [None if f is None else _cover(f, *mandates, replacements)
                 for f in covered]
        if any(pair is None for pair in pairs):
            continue
        used = [element for element, _source in pairs]
        if fingerprint(used + _replacement_elements(replacements)) == \
                fields[3]:
            return True
    return False


def _judge(conn, task_id: str, branch: str, artifact_branch: str, profile,
           repo: Path, scratch: Path, trees: dict, base_of,
           merge: bool, extra: tuple = ()) -> GateRefusal | None:
    head_sha = gitcmd.branch_head_sha(branch, repo=repo)
    if not head_sha:
        raise _Prepare(f"голова кодовой ветки {branch} не прочитана")
    base_sha = base_of(repo, branch, head_sha)
    _checkouts(repo, scratch, trees, base_sha, head_sha)
    key = _component_key(repo, head_sha, profile, trees[HEAD])
    if merge and _proven(conn, task_id, artifact_branch, head_sha, base_sha,
                         key, profile):
        store.journal(conn, task_id, "fsm", PROVEN_ACTION,
                      f"для головы {head_sha[:7]} и базы {base_sha[:7]}")
        return None
    runs = _full_runs(task_id, profile, trees)
    base, head = runs[BASE], runs[HEAD]
    head_map = {c.id: c for c in head}
    red = sorted(c.id for c in base if in_pass_to_pass(c)
                 and c.id in head_map and red_on_branch(head_map[c.id]))
    history = {cid: {HEAD: [(True, describe(head_map[cid]))],
                     BASE: [(False, describe(next(c for c in base
                                                  if c.id == cid)))]}
               for cid in red}
    file_runs = _rerun(profile, trees, red, history) if red else 0
    senior, flaky = _redness(red, history)
    taken = {f.id for f in senior}
    findings = senior + [f for f in compare(base, head) if f.id not in taken]

    # G3б-2 (SPEC 01M5J0JYW3GZSSHHK3TYCYTQ3J, требования 2-5, 7-8).
    entries = _name_status(repo, base_sha, head_sha)
    added = _added_lines(repo, base_sha, head_sha)
    files = _Files(profile, _record_paths(base), _record_paths(head))
    replacements = _replacements(conn, task_id, profile)
    base_map = {c.id: c for c in base if not c.file_level}
    prior_paths = {path for status, path, _new in entries
                   if not status.startswith(("A", "C"))
                   and (files.is_test(path) or files.is_support(path))}
    prior_paths |= {project_profile.parse_test_id(cid)[1]
                    for cid in replacements if cid in base_map}
    prior_history, prior_runs, prior_line = {}, 0, []
    if prior_paths:
        paths = sorted(prior_paths)
        tree = _prior_checkout(repo, scratch, trees, base_sha, head_sha,
                               paths, files, entries)
        prior_history, prior_red, prior_runs = _prior_versions(
            task_id, profile, trees, tree, paths, files, base)
        prior_found, prior_flaky = _prior_redness(prior_red, prior_history)
        # Одна находка на идентификатор: прежний вид старше.
        taken = {f.id for f in findings}
        findings += [f for f in prior_found if f.id not in taken]
        flaky += [cid for cid in prior_flaky if cid not in flaky]
        prior_line = [PRIOR_LINE.format(files=len(paths), runs=prior_runs)]
    replaced_found, replaced_lines = _replacement_findings(
        replacements, base_map, prior_history)
    findings = ordered(findings + replaced_found
                       + _strict_findings(profile, files, entries)
                       + _code_exception_findings(files, entries, added))

    mandate, id_mandate = (_answer_mandates(artifact_branch, task_id)
                           if findings else ({}, {}))
    covered = [(f, _cover(f, mandate, id_mandate, replacements))
               for f in findings]
    uncovered = [f for f, pair in covered if pair is None]
    covered = [(f, pair) for f, pair in covered if pair is not None]
    flaky_lines = [f"{FLAKY_ON_BASE}: {cid}" for cid in flaky]
    if uncovered:
        lines = [f.line for f in uncovered]
        growth = skip_growth(base, head)
        if growth:
            lines.append(growth)
        action = (BROKEN_REFUSAL_ACTION
                  if all(f.kind == BROKEN for f in uncovered)
                  else OUTCOME_REFUSAL_ACTION)
        return GateRefusal(action, "\n".join(lines + flaky_lines),
                           _mandate_hint(task_id, any(
                               f.kind in _NEW_KINDS for f in uncovered)))
    counts = (f"тестов базы {len(base)}; тестов ветки {len(head)}; тестов, "
              f"прошедших перепрогон, {len(red)}; прогонов файлов "
              f"{file_runs}; находок, покрытых мандатом, {len(covered)}")
    used = [element for _f, (element, _s) in covered]
    proof = (f"голова {head_sha}; база {base_sha}; ключ {key}; мандат "
             f"{fingerprint(used + _replacement_elements(replacements))}")
    store.journal(conn, task_id, "fsm", PASSED_ACTION, "\n".join(
        [counts, proof, *prior_line, *flaky_lines, *replaced_lines,
         *(f"{f.line}{COVERED_MARK}{source}" for f, (_e, source) in covered),
         *extra]))
    return None


# Режим `ci` на гейте мержа (SPEC 01M5XZSKK8H096FD3CPN05BQNM, требования
# 1-8): годные статусы последней попытки задания `ci_job`.
_CI_FIT_STATUSES = ("success", "failed")
BASE_REPORT_ACTION = "гейт исходов: отчёт базы"
BASE_REPORT_LINE = "отчёт базы: задание {job} коммита {sha} (дерево совпадает с {point})"
NO_BASE_REPORT = "нет отчёта базы"
NO_HEAD_REPORT = "нет отчёта головы"
BASE_AMBIGUOUS = "отчёт базы неоднозначен: {ids}"


class _CiReport(NamedTuple):
    """Годный отчёт задания `ci_job`: коммит, `id` последней попытки,
    исходы `<classname>::<name>` → статус."""
    sha: str
    job_id: int
    outcomes: dict


def _ci_report(target: str, sha: str, job: str):
    """(`_CiReport` ровно `sha`, "") либо (`None`, причина негодности) —
    требование 2. Попытка — наибольший `id` заданий `job` в
    `forge.pipeline_status(sha).jobs`; номер до и после чтения отчёта
    совпадает, иначе статус и отчёт могли быть от разных попыток."""
    def last_attempt():
        res = forge.pipeline_status(target, sha)
        mine = [j for j in res.jobs if j.name == job]
        why = f" ({res.reason})" if res.reason else ""
        return (max(mine, key=lambda j: j.id or 0) if mine else None,
                f"задания CI «{job}» нет в конвейере коммита {sha[:12]}{why}")
    last, why = last_attempt()
    if last is None:
        return None, why
    where = f"задание CI «{job}» {last.id} коммита {sha[:12]}"
    result = forge.job_result(target, sha, job)
    report = forge.job_test_report(target, sha, job)
    again, _why = last_attempt()
    if again is None or again.id != last.id:
        return None, f"{where} перезапущено во время чтения"
    status = result.status
    if status is None:
        return None, f"{where}: статус не прочитан — {result.reason}"
    if status not in _CI_FIT_STATUSES:
        return None, f"{where} в статусе {status}"
    if status == "failed" and last.allow_failure:
        return None, f"{where} упало с правом падать (allow_failure)"
    if report.outcomes is None:
        return None, f"{where}: отчёт не разобран — {report.reason}"
    return _CiReport(sha, last.id, dict(report.outcomes)), ""


def _rev(repo: Path, *args: str) -> str:
    """Вывод `git <args>` в `repo`; сбой — `_Prepare`."""
    res = gitcmd.in_repo(repo, *args)
    if res is None or res.returncode != 0:
        raise _Prepare(f"git {' '.join(args)} не выполнен: {_git_reason(res)}")
    return res.stdout.strip()


def _ci_base_report(conn, task_id: str, repo: Path, target: str,
                    point: str, job: str) -> tuple:
    """(`_CiReport` базы, строка о родителе или "") — требование 4: отчёт
    точки ответвления, иначе родителя (`rev-list --parents`) с тем же
    деревом; поиск только чтением git и `forge`. Не найден — `_Prepare`
    «нет отчёта базы»."""
    found, why = _ci_report(target, point, job)
    if found is not None:
        return found, ""
    reasons = [f"точка ответвления {point[:12]}: {why}"]
    parents = _rev(repo, "rev-list", "--parents", "-n1", point).split()[1:]
    point_tree = _rev(repo, "rev-parse", f"{point}^{{tree}}")
    for parent in parents:
        if _rev(repo, "rev-parse", f"{parent}^{{tree}}") != point_tree:
            reasons.append(f"родитель {parent[:12]}: дерево другое")
            continue
        found, why = _ci_report(target, parent, job)
        if found is None:
            reasons.append(f"родитель {parent[:12]}: {why}")
            continue
        line = BASE_REPORT_LINE.format(job=found.job_id, sha=parent,
                                       point=point)
        store.journal(conn, task_id, "fsm", BASE_REPORT_ACTION, line)
        return found, line
    raise _Prepare(f"{NO_BASE_REPORT}: {'; '.join(reasons)}")


def _ci_cases(repo: Path, profile, report: _CiReport) -> tuple:
    """(записи `CaseResult`, неразобранные ключи) отчёта: модули ищутся в
    дереве коммита отчёта под `workdir` чтением git, без выписки."""
    args = ["-c", "core.quotePath=false", "ls-tree", "-r", "--name-only",
            "-z", report.sha]
    if profile.workdir:
        args += ["--", profile.workdir.strip("/") + "/"]
    res = gitcmd.in_repo(repo, *args)
    if res is None or res.returncode != 0:
        raise _Prepare(f"дерево коммита {report.sha[:12]} отчёта задания CI "
                       f"не прочитано: {_git_reason(res)}")
    files = {p for p in res.stdout.split("\0") if p}
    return outcome.parse_forge_report(report.outcomes, profile.component,
                                      profile.workdir, files)


def _ci_replacement_findings(replacements: dict, base_map: dict) -> list:
    """Находки утверждённых замен в режиме `ci` (требование 6): прежней
    версии зелёного в базе теста проверить негде — отказ, не сбой."""
    found = []
    for cid, _n in sorted(replacements.items()):
        b = base_map.get(cid)
        if b is None:
            found.append(Finding(REPLACED_MISSING, cid, "база: нет записи"))
        elif not in_pass_to_pass(b):
            found.append(Finding(REPLACED_NOT_GREEN, cid,
                                 f"база: {describe(b)}"))
        else:
            found.append(Finding(REPLACED_UNCHECKABLE, cid,
                                 f"база: {describe(b)}"))
    return found


def _judge_ci(conn, task_id: str, branch: str, artifact_branch: str, profile,
              repo: Path, base_of, extra: tuple = ()) -> GateRefusal | None:
    """Ядро гейта мержа компонента `full_suite: ci` (требования 1-8):
    исходы — отчёты задания `ci_job` головы и базы, читаются заново при
    каждом прогоне; находки G3б-2 — по диффу git без выписок."""
    head_sha = gitcmd.branch_head_sha(branch, repo=repo)
    if not head_sha:
        raise _Prepare(f"голова кодовой ветки {branch} не прочитана")
    base_sha = base_of(repo, branch, head_sha)
    target = store.task_target(conn, task_id)
    job = profile.ci_job
    head_report, why = _ci_report(target, head_sha, job)
    if head_report is None:
        raise _Prepare(f"{NO_HEAD_REPORT}: голова {head_sha[:12]}: {why}")
    base_report, parent_line = _ci_base_report(conn, task_id, repo, target,
                                               base_sha, job)
    base, unresolved = _ci_cases(repo, profile, base_report)
    odd = [key for key, _why in unresolved] + \
        [c.id for c in base if c.outcome == outcome.UNKNOWN]
    if odd:
        raise _Prepare(BASE_AMBIGUOUS.format(ids=", ".join(odd)))
    # Неразобранный ключ головы идентификатора не имеет: тест базы под ним
    # «исчез» по сравнению, совпадением он не засчитывается.
    head, _unresolved = _ci_cases(repo, profile, head_report)
    head_map = {c.id: c for c in head}
    senior = []
    for b in base:
        h = head_map.get(b.id)
        if in_pass_to_pass(b) and h is not None and \
                (red_on_branch(h) or h.outcome == outcome.UNKNOWN):
            text = describe(h) + (f" ({h.failure})" if h.outcome ==
                                  outcome.UNKNOWN else "")
            senior.append(Finding(BROKEN, b.id, f"ветка: {text}; база: "
                                                f"{describe(b)}"))
    taken = {f.id for f in senior}
    findings = senior + [f for f in compare(base, head) if f.id not in taken]

    entries = _name_status(repo, base_sha, head_sha)
    added = _added_lines(repo, base_sha, head_sha)
    files = _Files(profile, _record_paths(base), _record_paths(head))
    replacements = _replacements(conn, task_id, profile)
    base_map = {c.id: c for c in base if not c.file_level}
    findings = ordered(findings
                       + _ci_replacement_findings(replacements, base_map)
                       + _strict_findings(profile, files, entries)
                       + _code_exception_findings(files, entries, added))

    mandate, id_mandate = (_answer_mandates(artifact_branch, task_id)
                           if findings else ({}, {}))
    covered = [(f, _cover(f, mandate, id_mandate, replacements))
               for f in findings]
    uncovered = [f for f, pair in covered if pair is None]
    covered = [(f, pair) for f, pair in covered if pair is not None]
    if uncovered:
        lines = [f.line for f in uncovered]
        growth = skip_growth(base, head)
        if growth:
            lines.append(growth)
        action = (BROKEN_REFUSAL_ACTION
                  if all(f.kind == BROKEN for f in uncovered)
                  else OUTCOME_REFUSAL_ACTION)
        return GateRefusal(action, "\n".join(lines), _mandate_hint(
            task_id, any(f.kind in _NEW_KINDS for f in uncovered)))
    tree = _rev(repo, "rev-parse", f"{head_sha}^{{tree}}")
    # Ключ — без пробельных символов (`PROOF_LINE`), с именем компонента:
    # компоненты одного дерева головы различимы.
    key = (f"ci:{profile.component}:{tree}:{head_report.job_id}:"
           f"{base_report.job_id}")
    counts = (f"тестов базы {len(base)}; тестов ветки {len(head)}; задание "
              f"CI {job}: голова {head_report.job_id}, база "
              f"{base_report.job_id}; находок, покрытых мандатом, "
              f"{len(covered)}")
    used = [element for _f, (element, _s) in covered]
    proof = (f"голова {head_sha}; база {base_sha}; ключ {key}; мандат "
             f"{fingerprint(used + _replacement_elements(replacements))}")
    store.journal(conn, task_id, "fsm", PASSED_ACTION, "\n".join(
        [counts, proof, *([parent_line] if parent_line else []),
         *(f"{f.line}{COVERED_MARK}{source}" for f, (_e, source) in covered),
         *extra]))
    return None


def _bounds(is_canary, target: str):
    """Профиль задачи в границе гейта (`in_outcome_bounds` профиля
    решения `decide`, не канарейка); `None` — вне границы."""
    if is_canary:
        return None
    decision = project_profile.decide(target)
    if decision.refusal or decision.skip or \
            not in_outcome_bounds(decision.profile):
        return None
    return decision.profile


def _outcome_integrity_gate(conn, task_id: str, t,
                            artifact_branch: str) -> GateRefusal | None:
    """Гейт (требования 1-6): вне границы — `None` без прогона и записи;
    иначе прогоны, сравнение, мандат; сбой подготовки — отказ. Запись
    из нескольких компонентов — компоненты диффа (`_components_gate`)."""
    target = t["target"] or config.DEFAULT_TARGET
    if project_profile.is_multi(target):
        if t["is_canary"]:
            return None
        decision = project_profile.for_task_target(target, task_id, conn)
        if decision.profile is None:
            return GateRefusal(project_profile.REFUSAL_ACTION,
                               decision.refusal,
                               project_profile.refusal_hint(task_id))
        return _components_gate(conn, task_id, t["branch"], artifact_branch,
                                target, _diff_base, merge=False)
    profile = _bounds(t["is_canary"], t["target"])
    if profile is None:
        return None
    return _gate(conn, task_id, t["branch"], artifact_branch, profile,
                 _diff_base, merge=False)


# Название проверки записи пропуска гейта, когда вне границы все компоненты
# диффа (SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование 3).
CHECK_OUTCOME = "гейт неослабления по исходам"
OUT_OF_BOUNDS_LINE = "компонент {name}: вне границы гейта исходов"
_HEAD_LINE = "голова {head}"


def _components_gate(conn, task_id: str, branch: str, artifact_branch: str,
                     target: str, base_of, merge: bool) -> GateRefusal | None:
    """Гейт записи из нескольких компонентов (SPEC
    01M5JGSAANR1NZYQD4FCSVE48Y, требование 3): компоненты
    `select_components` путей диффа (с потребителями по `depends_on`), в
    порядке записи. Компонент в границе — свой прогон ядра `_gate` и своя
    запись; первый отказ останавливает гейт («компонент <имя>: …»).
    Компоненты вне границы — строкой в каждой записи; вне границы все —
    запись пропуска без прогона. Сбой чтения диффа — отказ подготовки."""
    repo = workspace.task_repo(task_id)
    bases: dict = {}

    def cached_base(repo_: Path, branch_: str, head_sha: str) -> str:
        # На мерже база — повторный фетч main: один на гейт, не на компонент.
        if head_sha not in bases:
            bases[head_sha] = base_of(repo_, branch_, head_sha)
        return bases[head_sha]
    reason = ""
    try:
        head_sha = gitcmd.branch_head_sha(branch, repo=repo)
        if not head_sha:
            raise _Prepare(f"голова кодовой ветки {branch} не прочитана")
        base_sha = cached_base(repo, branch, head_sha)
        paths = gitcmd.diff_names(base_sha, head_sha, repo=repo)
        if paths is None:
            raise _Prepare(f"дифф базы {base_sha[:12]} и головы "
                           f"{head_sha[:12]} не получен — компоненты гейта "
                           f"не выбраны")
        profiles = project_profile.component_profiles(
            target, project_profile.select_components(target, paths))
    except _Prepare as exc:
        reason = str(exc)
    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск
        reason = f"сбой {exc!r}"
    if reason:
        return GateRefusal(PREPARE_REFUSAL_ACTION, reason,
                           f"разберись с подготовкой прогона и повтори "
                           f"artel.py advance {task_id}")
    outside = tuple(OUT_OF_BOUNDS_LINE.format(name=p.component)
                    for p in profiles if not in_outcome_bounds(p))
    inside = [p for p in profiles if in_outcome_bounds(p)]
    if not inside:
        project_profile.journal_skip(
            conn, task_id, CHECK_OUTCOME, project_profile.Decision(
                target, skip="\n".join([_HEAD_LINE.format(head=head_sha),
                                        *outside])))
        return None
    for profile in inside:
        refusal = _gate(conn, task_id, branch, artifact_branch, profile,
                        cached_base, merge, extra=outside)
        if refusal is not None:
            return refusal._replace(
                detail=f"компонент {profile.component}: {refusal.detail}")
    return None


def _gate(conn, task_id: str, branch: str, artifact_branch: str, profile,
          base_of, merge: bool, extra: tuple = ()) -> GateRefusal | None:
    """Ядро гейта на обоих рубежах: выписки, ключ, (на мерже)
    доказательство, прогоны, сравнение, мандат; сбой подготовки — отказ
    `PREPARE_REFUSAL_ACTION`, не пропуск. `extra` — строки, дописываемые в
    запись пройденного гейта (компоненты вне границы)."""
    repo = workspace.task_repo(task_id)
    if merge and profile.full_suite == targets.FULL_SUITE_CI:
        return _gate_ci(conn, task_id, branch, artifact_branch, profile,
                        repo, base_of, extra)
    # `resolve()`: временный каталог macOS — символическая ссылка, а пути
    # отчёта раннер считает от реального корня выписки.
    scratch = Path(tempfile.mkdtemp(prefix="artel-outcome-")).resolve()
    trees: dict = {}
    try:
        # Маркер владельца — до первого `git worktree add`: каталог,
        # брошенный обрывом процесса, `doctor --fix` узнаёт сиротой.
        (scratch / liveness.GATE_OWNER_MARKER).write_text(
            str(os.getpid()), encoding="utf-8")
        return _judge(conn, task_id, branch, artifact_branch, profile,
                      repo, scratch, trees, base_of, merge, extra)
    except _Prepare as exc:
        reason = str(exc)
    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск
        reason = f"сбой {exc!r}"
    finally:
        for tree in trees.values():
            gitcmd.in_repo(repo, "worktree", "remove", "--force", str(tree))
        shutil.rmtree(scratch, ignore_errors=True)
    return GateRefusal(PREPARE_REFUSAL_ACTION, reason,
                       f"разберись с подготовкой прогона и повтори artel.py "
                       f"advance {task_id}")


def _gate_ci(conn, task_id: str, branch: str, artifact_branch: str, profile,
             repo: Path, base_of, extra: tuple) -> GateRefusal | None:
    """Ядро гейта мержа в режиме `ci` (`_judge_ci`) без выписок; сбой
    подготовки — отказ `PREPARE_REFUSAL_ACTION`, не пропуск."""
    try:
        return _judge_ci(conn, task_id, branch, artifact_branch, profile,
                         repo, base_of, extra)
    except _Prepare as exc:
        reason = str(exc)
    except Exception as exc:  # noqa: BLE001 — fail-closed: сбой не пропуск
        reason = f"сбой {exc!r}"
    return GateRefusal(PREPARE_REFUSAL_ACTION, reason,
                       f"разберись с подготовкой и повтори artel.py approve "
                       f"{task_id}")


def _outcome_integrity_gate_refuses(conn, task_id: str, t,
                                    artifact_branch: str) -> bool:
    """Публичная обёртка гейта — та же форма, что у соседей по `in_dev`
    (`_test_integrity_gate_refuses`): `artifact_branch` — источник
    `tasks/<id>/` (мандат), `t["branch"]` — кодовая ветка."""
    return _run_gates(conn, task_id,
                      [lambda: _outcome_integrity_gate(conn, task_id, t,
                                                       artifact_branch)])


def merge_gate_escalates(conn, task_id: str, state: str, main_sha_of) -> bool:
    """Гейт исходов в окне мержа (SPEC 01M5DDTVZEA40ZB9BHEH4YDEE7,
    требования 2-4): цель и признак канарейки — из БД; вне границы —
    `False` без фетча и записей. Доказательство для головы и базы — запись
    «доказан» без прогона; иначе прогон тем же ядром, что на `in_dev`.
    Мандат — с ветки-источника `tasks/<id>/` (`artifact_source.resolve`).

    Находка без мандата (и «сломан правкой») — запись
    `MERGE_REFUSAL_ACTION` с находками и `escalated`, `True`. Сбой
    подготовки — запись `MERGE_PREPARE_ACTION` и `sys.exit`: задача на
    `merge_gate`, push нет, пропуска гейта нет."""
    # Граница по цели — до строки задачи: вне границы шаг не читает БД
    # сверх `task_target`, как прежний маршрут мержа.
    target = store.task_target(conn, task_id)
    if project_profile.is_multi(target):
        t = store.get_task(conn, task_id)
        if t["is_canary"]:
            return False
        _merge_profile_refusal_exit(conn, task_id, target)
        artifact_branch, _foreign = artifact_source.resolve(conn, task_id)
        refusal = _components_gate(conn, task_id, t["branch"],
                                   artifact_branch, target,
                                   _merge_base_of(main_sha_of), merge=True)
    else:
        profile = _bounds(False, target)
        if profile is None:
            return False
        t = store.get_task(conn, task_id)
        if t["is_canary"]:
            return False
        artifact_branch, _foreign = artifact_source.resolve(conn, task_id)
        refusal = _gate(conn, task_id, t["branch"], artifact_branch, profile,
                        _merge_base_of(main_sha_of), merge=True)
    if refusal is None:
        return False
    if refusal.action == PREPARE_REFUSAL_ACTION:
        store.journal(conn, task_id, "fsm", MERGE_PREPARE_ACTION,
                      refusal.detail)
        sys.exit(f"[{task_id}] {MERGE_PREPARE_ACTION}: {refusal.detail}\n"
                 f"  задача осталась на гейте merge; разберись с подготовкой "
                 f"прогона и повтори artel.py approve {task_id}")
    store.journal(conn, task_id, "fsm", MERGE_REFUSAL_ACTION, refusal.detail)
    store.set_state(conn, task_id, "escalated", "fsm", expected_state=state,
                    detail=refusal.detail)
    print(f"[{task_id}] {MERGE_REFUSAL_ACTION}: задача эскалирована\n"
          f"{refusal.detail}\n  дальше: находку снимает мандат Оператора — "
          f"строка «{TEST_WEAKENING_MANDATE_MARKER} <пути и имена>» или "
          f"«{TEST_ID_MANDATE_MARKER} <идентификатор теста>» в "
          f"tasks/{task_id}/ANSWER-n.md")
    return True


def _merge_profile_refusal_exit(conn, task_id: str, target: str) -> None:
    """Компонент задачи на записи из нескольких компонентов не выбран
    (`for_task`) — отказ мержа, не пропуск гейта и не эскалация (SPEC
    01M5JGSAANR1NZYQD4FCSVE48Y, требование 2): задача остаётся на
    `merge_gate`."""
    decision = project_profile.for_task_target(target, task_id, conn)
    if decision.profile is not None:
        return
    # fsm_merge_gate импортирует этот модуль на верхнем уровне.
    from ..fsm_merge_gate import MERGE_PROFILE_REFUSAL_ACTION
    store.journal(conn, task_id, "fsm", MERGE_PROFILE_REFUSAL_ACTION,
                  decision.refusal)
    sys.exit(f"[{task_id}] merge отклонён: {decision.refusal}\n"
             f"  задача осталась на гейте merge; почини зоны задачи или "
             f"targets.yaml и повтори: artel.py approve {task_id}")


def review_lines(conn, task_id: str, head_sha: str) -> list:
    """Строки гейта исходов для пакета ревьювера (требование 5): по
    последней записи `PASSED_ACTION` с головой `head_sha` — числа базы и
    ветки, перепрогоны, «нестабилен и на базе», находки под мандатом с
    ANSWER; записи нет — строка «не исполнялся». Запись из нескольких
    компонентов — `_components_review_lines`."""
    if project_profile.is_multi(store.task_target(conn, task_id)):
        return _components_review_lines(conn, task_id, head_sha)
    for detail in reversed(_passed_details(conn, task_id) if head_sha else []):
        fields = proof_fields(detail)
        if fields is None or fields[0] != head_sha:
            continue
        lines = [line for line in detail.splitlines()
                 if line.strip() and not PROOF_LINE.match(line.strip())]
        return [f"гейт исходов для головы {head_sha[:7]} и базы "
                f"{fields[1][:7]}: {lines[0] if lines else ''}",
                *(f"гейт исходов: {line}" for line in lines[1:])]
    return [NOT_RUN_LINE.format(head=head_sha[:7] or "(не прочитана)")]


def _record_lines(detail: str, fields) -> list:
    lines = [line for line in detail.splitlines()
             if line.strip() and not PROOF_LINE.match(line.strip())]
    return [f"гейт исходов для головы {fields[0][:7]} и базы "
            f"{fields[1][:7]}: {lines[0] if lines else ''}",
            *(f"гейт исходов: {line}" for line in lines[1:])]


def _components_review_lines(conn, task_id: str, head_sha: str) -> list:
    """Строки гейта исходов записи из нескольких компонентов (SPEC
    01M5JGSAANR1NZYQD4FCSVE48Y, требование 3): последняя запись
    `PASSED_ACTION` головы по каждому ключу компонента, в порядке записей;
    их нет, а есть запись пропуска головы — «не исполнялся» и строки
    компонентов вне границы из неё."""
    latest: dict = {}
    for detail in (_passed_details(conn, task_id) if head_sha else []):
        fields = proof_fields(detail)
        if fields is not None and fields[0] == head_sha:
            latest[fields[2]] = (detail, fields)
    if latest:
        return [line for detail, fields in latest.values()
                for line in _record_lines(detail, fields)]
    lines = [NOT_RUN_LINE.format(head=head_sha[:7] or "(не прочитана)")]
    skip_action = f"{project_profile.SKIP_ACTION}: {CHECK_OUTCOME}"
    head_line = _HEAD_LINE.format(head=head_sha)
    skips = [r["detail"] or "" for r in store.task_steps(conn, task_id)
             if head_sha and r["action"] == skip_action]
    for detail in reversed(skips):
        rows = detail.splitlines()
        if rows and rows[0] == head_line:
            lines += [f"гейт исходов: {row}" for row in rows[1:]]
            break
    return lines
