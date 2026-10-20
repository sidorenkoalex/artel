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
"""
import shutil
import tempfile
from pathlib import Path
from typing import NamedTuple

from .. import acceptance
from .. import artifact_branch as docs_ref
from .. import gitcmd, project_profile, store, workspace
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
    try:
        _comp, path, _name, _n = project_profile.parse_test_id(cid)
    except ValueError:
        return None
    rest = cid.partition(":")[2]
    for element, source in mandate.items():
        if element == path:
            return source
        if "::" not in element or not rest.startswith(element):
            continue
        tail = rest[len(element):]
        if not tail or tail.startswith(("::", "[", "#")):
            return source
    return None


def _covering(cid: str, mandate: dict, id_mandate: dict):
    """Имя ANSWER-n, покрывающего тест `cid`: мандат по идентификатору —
    только точным равенством (с `#n`, без префиксного правила), прежний
    мандат — `covering`; `None` — не покрыт."""
    source = id_mandate.get(cid)
    return source if source is not None else covering(cid, mandate)


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


def _checkouts(repo: Path, branch: str, scratch: Path, trees: dict) -> None:
    """Выписки базы и головы кодовой ветки в `scratch`; заведённые
    дописываются в `trees` (уборка — у вызывающего)."""
    base_sha = gitcmd.diff_base(branch, repo=repo)
    if not base_sha:
        raise _Prepare(f"база сравнения ветки {branch} (diff_base) не определена")
    head_sha = gitcmd.branch_head_sha(branch, repo=repo)
    if not head_sha:
        raise _Prepare(f"голова кодовой ветки {branch} не прочитана")
    for side, key, sha in ((BASE, "base", base_sha), (HEAD, "head", head_sha)):
        tree = scratch / key
        res = gitcmd.in_repo(repo, "worktree", "add", "--detach", str(tree), sha)
        if res is None or res.returncode != 0:
            raise _Prepare(f"выписка стороны «{side}» ({sha[:12]}) не создана: "
                           f"{_git_reason(res)}")
        trees[side] = tree


def _judge(conn, task_id: str, t, artifact_branch: str, profile, repo: Path,
           scratch: Path, trees: dict) -> GateRefusal | None:
    _checkouts(repo, t["branch"], scratch, trees)
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
    covered = [(f, _covering(f.id, mandate, id_mandate)) for f in findings]
    uncovered = [f for f, source in covered if source is None]
    covered = [(f, source) for f, source in covered if source is not None]
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
    store.journal(conn, task_id, "fsm", PASSED_ACTION, "\n".join(
        [counts, *flaky_lines,
         *(f"{f.line} — покрыто мандатом {source}" for f, source in covered)]))
    return None


def _outcome_integrity_gate(conn, task_id: str, t,
                            artifact_branch: str) -> GateRefusal | None:
    """Гейт (требования 1-6): вне границы — `None` без прогона и записи;
    иначе прогоны, сравнение, мандат; сбой подготовки — отказ."""
    if t["is_canary"]:
        return None
    decision = project_profile.decide(t["target"])
    if decision.refusal or decision.skip or \
            not in_outcome_bounds(decision.profile):
        return None
    repo = workspace.task_repo(task_id)
    # `resolve()`: временный каталог macOS — символическая ссылка, а пути
    # отчёта раннер считает от реального корня выписки.
    scratch = Path(tempfile.mkdtemp(prefix="artel-outcome-")).resolve()
    trees: dict = {}
    try:
        return _judge(conn, task_id, t, artifact_branch, decision.profile,
                      repo, scratch, trees)
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
