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
"""
import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

from .. import acceptance
from .. import artifact_branch as docs_ref
from .. import artifact_source, gitcmd, project_profile, store, workspace
from ..reporters import outcome
from ._base import GateRefusal, _run_gates
from .acceptance import in_outcome_bounds
from .mandate import (TEST_ID_MANDATE_MARKER, TEST_WEAKENING_MANDATE_MARKER,
                      elements, id_elements)
from .zones import _answer_commit_is_role_step_autocommit

# Действия журнала (требование 6); литералы повторены в
# `refusal_classes.REFUSAL_CLASSES`.
OUTCOME_REFUSAL_ACTION = "переход отклонён: гейт неослабления по исходам"
BROKEN_REFUSAL_ACTION = f"{OUTCOME_REFUSAL_ACTION} — сломан правкой"
PREPARE_REFUSAL_ACTION = f"{OUTCOME_REFUSAL_ACTION} — подготовка"
PASSED_ACTION = "гейт неослабления по исходам пройден"
FLAKY_ON_BASE = "нестабилен и на базе"

# Гейт исходов на гейте мержа (SPEC 01M5DDTVZEA40ZB9BHEH4YDEE7, требования
# 1-4): действие находки без мандата повторено литералом в
# `refusal_classes.REFUSAL_CLASSES`.
MERGE_REFUSAL_ACTION = "merge отклонён: гейт неослабления по исходам"
MERGE_PREPARE_ACTION = f"{MERGE_REFUSAL_ACTION} — подготовка"
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
_RANK = {GONE: 0, BROKEN: 1, UNSTABLE: 2}
_OTHER_RANK = 3

BASE = "база"
HEAD = "голова ветки"
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
    `PASS_TO_PASS` судят перепрогоны, не эта функция."""
    base_map = {c.id: c for c in base}
    head_map = {c.id: c for c in head}
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


def fingerprint(elements_used) -> str:
    """Отпечаток мандата записи пройденного гейта (SPEC
    01M5DDTVZEA40ZB9BHEH4YDEE7, требование 1): sha256 (hex) элементов,
    покрывших находки, — отсортированы и соединены переводом строки,
    utf-8; таких элементов нет — «нет»."""
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


def _mandate_hint(task_id: str) -> str:
    """Подсказка отказа с обоими маркерами, снимающими находку этого
    гейта (SPEC 01M5D02N3B428V8BWC3PAM9QCT, требование 5)."""
    return (f"либо верни тесты на место, либо получи мандат Оператора — "
            f"строка «{TEST_WEAKENING_MANDATE_MARKER} <пути и имена>» или "
            f"«{TEST_ID_MANDATE_MARKER} <идентификатор теста>» (по строке на "
            f"идентификатор) в tasks/{task_id}/ANSWER-n.md (команда artel.py "
            f"answer {task_id} <файл>: в состоянии in_dev — без смены "
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
    runs = {}
    for side, tree in trees.items():
        run = acceptance.components_full_suite(tree, task_id, (profile,),
                                               fresh=True)
        if run.outcome in (acceptance.FULL_SUITE_NOT_STARTED,
                           acceptance.FULL_SUITE_TIMEOUT):
            raise _Prepare(f"полный набор на стороне «{side}»: {run.outcome} "
                           f"— {run.detail.strip()[:500]}")
        runs[side] = ([] if run.outcome == acceptance.FULL_SUITE_NO_TESTS
                      else list(run.tests))
    return runs


def _rerun(profile, trees: dict, red: list, history: dict) -> int:
    """Перепрогоны красных тестов `red` по их файлам (требование 3):
    дописывает в `history` {id: {сторона: [(красный, исход)]}}; число
    прогонов файлов. Отказ подготовки — `_Prepare`."""
    files: dict = {}
    for cid in red:
        path = project_profile.parse_test_id(cid)[1]
        files.setdefault(path, []).append(cid)
    limit = project_profile.component_limit(profile)[0]
    count = 0
    for _round in range(RERUNS):
        for side in (HEAD, BASE):
            for path in sorted(files):
                run = acceptance._report_run(profile, trees[side], [path], limit)
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
    key = (acceptance._report_suite_result_key(tree, profile, False,
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
          FAILS_APPEARED, NEW_SKIPPED, NEW_TODO, NEW_FAILS)


def _finding_id(line: str):
    """Идентификатор теста строки находки `Finding.line`; `None` — не
    разобран."""
    for kind in _KINDS:
        prefix = f"{kind}: "
        if not line.startswith(prefix):
            continue
        # Исходы «сломан правкой»/«нестабилен» начинаются с ветки,
        # находки сравнения — с базы (`_redness`, `compare`).
        marker = " — ветка: " if kind in (BROKEN, UNSTABLE) else " — база: "
        cid, sep, _runs = line[len(prefix):].partition(marker)
        return cid if sep else None
    return None


def _covered_ids(detail: str) -> list:
    """Идентификаторы находок, покрытых мандатом, из записи `PASSED_ACTION`
    (строки «… — покрыто мандатом ANSWER-n»); неразобранный — `None`."""
    return [_finding_id(line.rpartition(COVERED_MARK)[0])
            for line in (detail or "").splitlines() if COVERED_MARK in line]


def _passed_details(conn, task_id: str) -> list:
    return [r["detail"] or "" for r in store.task_steps(conn, task_id)
            if r["action"] == PASSED_ACTION]


def _proven(conn, task_id: str, artifact_branch: str, head_sha: str,
            base_sha: str, key: str) -> bool:
    """Есть запись `PASSED_ACTION` с той же головой, базой, ключом и
    отпечатком ТЕКУЩЕГО мандата над покрытыми находками той записи
    (требование 3): отозванный элемент мандата меняет отпечаток."""
    mandates = None
    for detail in reversed(_passed_details(conn, task_id)):
        fields = proof_fields(detail)
        if fields is None or fields[:3] != (head_sha, base_sha, key):
            continue
        ids = _covered_ids(detail)
        if ids and mandates is None:
            mandates = _answer_mandates(artifact_branch, task_id)
        pairs = [None if cid is None else _covering_pair(cid, *mandates)
                 for cid in ids]
        if any(pair is None for pair in pairs):
            continue
        if fingerprint(element for element, _source in pairs) == fields[3]:
            return True
    return False


def _judge(conn, task_id: str, branch: str, artifact_branch: str, profile,
           repo: Path, scratch: Path, trees: dict, base_of,
           merge: bool) -> GateRefusal | None:
    head_sha = gitcmd.branch_head_sha(branch, repo=repo)
    if not head_sha:
        raise _Prepare(f"голова кодовой ветки {branch} не прочитана")
    base_sha = base_of(repo, branch, head_sha)
    _checkouts(repo, scratch, trees, base_sha, head_sha)
    key = _component_key(repo, head_sha, profile, trees[HEAD])
    if merge and _proven(conn, task_id, artifact_branch, head_sha, base_sha,
                         key):
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
    findings = ordered(senior + [f for f in compare(base, head)
                                 if f.id not in taken])
    mandate, id_mandate = (_answer_mandates(artifact_branch, task_id)
                           if findings else ({}, {}))
    covered = [(f, _covering_pair(f.id, mandate, id_mandate)) for f in findings]
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
                           _mandate_hint(task_id))
    counts = (f"тестов базы {len(base)}; тестов ветки {len(head)}; тестов, "
              f"прошедших перепрогон, {len(red)}; прогонов файлов "
              f"{file_runs}; находок, покрытых мандатом, {len(covered)}")
    proof = (f"голова {head_sha}; база {base_sha}; ключ {key}; мандат "
             f"{fingerprint(element for _f, (element, _s) in covered)}")
    store.journal(conn, task_id, "fsm", PASSED_ACTION, "\n".join(
        [counts, proof, *flaky_lines,
         *(f"{f.line}{COVERED_MARK}{source}" for f, (_e, source) in covered)]))
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
    иначе прогоны, сравнение, мандат; сбой подготовки — отказ."""
    profile = _bounds(t["is_canary"], t["target"])
    if profile is None:
        return None
    return _gate(conn, task_id, t["branch"], artifact_branch, profile,
                 _diff_base, merge=False)


def _gate(conn, task_id: str, branch: str, artifact_branch: str, profile,
          base_of, merge: bool) -> GateRefusal | None:
    """Ядро гейта на обоих рубежах: выписки, ключ, (на мерже)
    доказательство, прогоны, сравнение, мандат; сбой подготовки — отказ
    `PREPARE_REFUSAL_ACTION`, не пропуск."""
    repo = workspace.task_repo(task_id)
    # `resolve()`: временный каталог macOS — символическая ссылка, а пути
    # отчёта раннер считает от реального корня выписки.
    scratch = Path(tempfile.mkdtemp(prefix="artel-outcome-")).resolve()
    trees: dict = {}
    try:
        return _judge(conn, task_id, branch, artifact_branch, profile,
                      repo, scratch, trees, base_of, merge)
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
    profile = _bounds(False, store.task_target(conn, task_id))
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


def review_lines(conn, task_id: str, head_sha: str) -> list:
    """Строки гейта исходов для пакета ревьювера (требование 5): по
    последней записи `PASSED_ACTION` с головой `head_sha` — числа базы и
    ветки, перепрогоны, «нестабилен и на базе», находки под мандатом с
    ANSWER; записи нет — строка «не исполнялся»."""
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
