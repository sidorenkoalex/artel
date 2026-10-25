"""`_acceptance_lock_refuses`, `_acceptance_run_refuses` (SPEC
01M2CYQR0357VAQFZ5VACJD9TD, требование 1) — перенесено дословно из
`orchestrator/fsm_advance.py`.

Ни одна из двух функций не проходит через каркас `_base._run_gates`
(SPEC требование 3, PLAN «Подход») — `_acceptance_run_refuses`
докстрингом фиксирует это решение дословно, перенесено без правки."""
import contextlib
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from scripts import guard

from .. import (acceptance, agent_log, appendix_tree, artifact_branch, config,
               fsm, gitcmd, project_profile, store, workspace, yamlmini)
from ..reporters import outcome
from .plan_appendix import (PLAN_APPENDIX_GATE_FAILURE_ACTION,
                            PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION)
from .refusal_classes import (ACCEPTANCE_CODE_COPY_REFUSAL_ACTION,
                              BRANCH_CRITERION_REFUSAL_ACTION)

LONG_LIVED_MANIFEST_ACTION = "переход отклонён: перечень долгоживущих тестов"
# Подсказка отказа сверки перечня (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ,
# требование 7) — та же, что у лока каталога приёмочных тестов по смыслу:
# спор с тестом решает Оператор, не правка.
LONG_LIVED_MANIFEST_HINT = ("код чинится под тест; правка теста — "
                            "`amend-tests` по решению Оператора")
# Хвост отказа дерева с приложениями PLAN на рубеже `in_dev -> verifying`
# (`appendix_tree.suite_tree(not_run=...)`): без прогона здесь остаётся
# планка, а не полный набор.
PLANK_NOT_RUN = "планка и долгоживущие файлы задачи не запускались"


def long_lived_manifest_rel(task_id: str) -> str:
    return f"tasks/{task_id}/acceptance_tests/{guard.LONG_LIVED_MANIFEST_NAME}"


def blob_sha256(rev: str, rel: str, repo: Path | None = None) -> str | None:
    """SHA-256 БАЙТОВ файла `rel` в дереве `rev` (Р2: сумма — от дерева
    коммита, не от текста рабочего каталога и не от текста, прочитанного с
    перекодировкой концов строк); `None` — git не ответил или пути нет.
    `gitcmd.carpentry` — единственный вход git пульта, отдающий байты;
    `repo` — клон проекта задачи (ADR-0021 п.1); не назван — клон артели."""
    if repo is None:
        repo = workspace.repo(config.DEFAULT_TARGET)
    res = gitcmd.carpentry(repo, ["show", f"{rev}:{rel}"], None,
                           text=False)
    if res is None or res.returncode != 0:
        return None
    return hashlib.sha256(res.stdout).hexdigest()


def long_lived_manifest(task_id: str, t, target: str
                        ) -> tuple[dict[str, str] | None, str]:
    """({путь: sha256}, "") перечня долгоживущих файлов из дерева коммита
    лока `tests_locked_sha` — неизменного, в отличие от головы ветки
    документов, правку которой ловит сверка лока; (None, причина) — git не
    ответил, перечень испорчен, контекст проекта не разрешён или у артели
    нет профиля тестов (SPEC 01M45FJVGQT1K0P8HDEXZX6HS7, требования 4-5:
    отказ, а не пропуск).

    Пустой словарь — сверять нечего: задача вне области правила (проект
    без профиля тестов — пропуск журналирует вызывающий рубеж; `skip_tests`
    — лока нет), либо лок снят до внедрения перечня (задача 2 ADR-0020) и
    файла в дереве лока нет. У задачи, залоченной после внедрения, перечень
    в дереве лока есть всегда: выход из `tests_writing` без записанного
    перечня отказывает."""
    if not t["tests_locked_sha"]:
        return {}, ""
    decision = project_profile.for_task_target(target, task_id)
    if decision.refusal:
        return None, decision.refusal
    if decision.profile is None:
        return {}, ""
    locked = t["tests_locked_sha"]
    rel = long_lived_manifest_rel(task_id)
    repo = workspace.task_repo(task_id)
    listed = gitcmd.ls_tree_files(locked, rel, repo=repo)
    if listed is None:
        return None, f"git не ответил на дерево лока {locked}"
    if not listed:
        return {}, ""
    text, reason = gitcmd.show(locked, rel, repo=repo)
    if text is None:
        return None, f"перечень в дереве лока {locked} не прочитан: {reason}"
    return guard.parse_long_lived_manifest(text)


def _long_lived_manifest_refuses(conn, task_id: str) -> bool:
    """Общий узел сверки перечня долгоживущих файлов с головой кодовой
    ветки (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 7, рубежи Р4:
    `in_dev -> verifying`, `verifying -> review`, `review -> acceptance`,
    `approve` из `acceptance`, гейт мержа после `_sync_main_or_wait`).
    Каждый путь перечня обязан быть в дереве головы кодовой ветки с той же
    суммой; изменённый или удалённый файл — отказ с путём и подсказкой.
    Сбой git — отказ, не пропуск (ADR-0002, fail-closed).

    Строка задачи читается здесь, а не берётся у вызывающего: на гейте
    мержа его `t` мог быть прочитан до подтяжки main.

    Каталог долгоживущих файлов — профиля тестов проекта; у проекта без
    профиля сверка не выполняется и пишет об этом запись в журнал (SPEC
    01M45FJVGQT1K0P8HDEXZX6HS7, требование 3).

    `True` — переход отклонён (журнал и печать уже сделаны)."""
    t = store.get_task(conn, task_id)
    target = store.task_target(conn, task_id)
    decision = project_profile.for_task_target(target, task_id, conn)
    if t["tests_locked_sha"] and not decision.refusal \
            and decision.profile is None:
        project_profile.journal_skip(conn, task_id,
                                     project_profile.CHECK_MANIFEST, decision)
        return False
    digests, reason = long_lived_manifest(task_id, t, target)
    problems: list[str] = []
    if digests:
        repo = workspace.task_repo(task_id)
        head = gitcmd.branch_head_sha(t["branch"], repo=repo)
        present = (gitcmd.ls_tree_files(head, decision.profile.long_lived_dir,
                                        repo=repo) if head else None)
        if not head:
            reason = f"голова кодовой ветки {t['branch']} не прочитана"
        elif present is None:
            reason = f"git не ответил на дерево головы {head}"
        else:
            for path, digest in sorted(digests.items()):
                if path not in present:
                    problems.append(f"{path} удалён")
                    continue
                actual = blob_sha256(head, path, repo)
                if actual is None:
                    reason = f"{path} не прочитан на голове {head}"
                    break
                if actual != digest:
                    problems.append(f"{path} изменён")
    if reason:
        detail = (f"долгоживущие файлы задачи не сверены с перечнем: "
                  f"{reason} — сверка невозможна")
    elif problems:
        detail = (f"долгоживущие файлы задачи расходятся с перечнем лока "
                  f"{t['tests_locked_sha']}: {'; '.join(problems)} — "
                  f"{LONG_LIVED_MANIFEST_HINT}")
    else:
        return False
    store.journal(conn, task_id, "fsm", LONG_LIVED_MANIFEST_ACTION, detail)
    print(f"[{task_id}] переход отклонён: {detail}")
    return True


def _seed_repeats_escalate(conn, task_id: str, t, long_lived: list[str],
                           run_cwd: Path, command) -> bool:
    """Повторы долгоживущих файлов задачи, несущих случайное зерно, после
    ЗЕЛЁНОГО первого прогона (SPEC 01M48FRD9RJDBBVT2SN0FY5G2A, требование
    2): каждый файл с импортом `random` гоняется ещё
    `config.LONG_LIVED_SEED_REPEATS` раз — число читается здесь, в момент
    рубежа. Повторы не останавливаются на первом красном: деталь называет
    зёрна всех красных повторов.

    Красный повтор — эскалация Оператору, не отказ разработчику:
    долгоживущие файлы залочены, разработчик их не правит, чинит Оператор
    командой `amend-tests` (решение Оператора 06.10 на гейте SPEC).

    `True` — задача переведена в `escalated` (журнал и печать сделаны)."""
    seeded = [rel for rel in long_lived
              if acceptance.carries_random_seed(run_cwd / rel)]
    if not seeded:
        return False
    repeats = config.LONG_LIVED_SEED_REPEATS
    red: dict[str, list[str]] = {}
    for number in range(1, repeats + 1):
        for test in acceptance.run_repeat(seeded, run_cwd, command=command):
            seeds = (", ".join(f"зерно: {s}" for s in test.seeds)
                     if test.seeds else "зерно не напечатано")
            note = f" ({test.note})" if test.note else ""
            red.setdefault(test.node, []).append(
                f"повтор {number}: {seeds}{note}")
    if not red:
        return False
    tests = "; ".join(f"{node} — {', '.join(runs)}"
                      for node, runs in red.items())
    detail = (f"тест зависит от случайного зерна: зелёный в первом прогоне, "
              f"красный в повторах ({repeats} повторов долгоживущих файлов "
              f"с импортом random): {tests}")
    store.update_task(conn, task_id, escalated_from="in_dev")
    store.set_state(conn, task_id, "escalated", "fsm",
                    expected_state=t["state"], detail=detail)
    print(f"  дальше: тест чинит Оператор командой amend-tests по ответу "
          f"на эскалацию задачи {task_id}")
    return True


# ------------------------------------------- записи отчёта по критериям
#
# Один разбор на выход из `tests_writing` (честный `FAIL_TO_PASS`) и на
# приёмку ветки (SPEC 01M5AQH8M2DKBV30NBY86J34A7, требования 3, 6): файлы
# задачи с тестами критериев, их компонент и путь в отчёте, номер критерия
# записи отчёта.

# Маркер файла планки, тесты которого на базе обязаны пройти (требование 5):
# тот же текст, что одна из форм `guard.REDNESS_MARKER`.
GREEN_FROM_BIRTH_MARKER = re.compile(r"Зелёный с рождения:[^\S\n]*\S")
_AC_LABEL_HEAD = re.compile(r"AC-(\d+): ")
_PYTEST_LABEL_HEAD = re.compile(r"test_ac(\d+)_")
# Разделитель полного имени теста в отчёте: у `pult-vitest` — цепочка
# `describe`, у JUnit — класс и метод.
_VITEST_NAME_SEP = " > "
_JUNIT_NAME_SEP = "::"


def in_outcome_bounds(profile) -> bool:
    """Профиль в границе проверок исхода тестов критериев (требование 2):
    компонент записи `components:` с `report`. Артель, `test_profile` (в
    том числе `pytest-own` с `report`) и компоненты без `report` — вне."""
    return (profile is not None and project_profile.reported(profile)
            and bool(getattr(profile, "from_components", False)))


@dataclass(frozen=True)
class CriterionFile:
    """Файл задачи с тестами критериев: `rel` — путь записей отчёта от
    корня репозитория, `name` — как файл называют находки (имя файла
    планки либо путь долгоживущего), `profile` — компонент-владелец,
    `labelled` — метка `AC-<n>: `, `numbers` — критерии его тестов по
    тексту, `green` — у файла планки маркер «Зелёный с рождения:»."""
    rel: str
    name: str
    profile: object
    labelled: bool
    numbers: frozenset
    plank: bool
    green: bool = False


def _plank_file_profile(name: str, rule, profiles):
    """Компонент файла планки `name`: по `PlankRule.component_of`; у
    правила по умолчанию компонентов в правиле нет — первый компонент с
    командой pytest (тот, чьей разметке файл подчиняется)."""
    if rule.is_default:
        pytest = [p for p in profiles if acceptance.is_pytest_command(p.command)]
        chosen = pytest or list(profiles)
        return chosen[0] if chosen else None
    comp = rule.component_of(name)
    return next((p for p in profiles if p.component == comp), None)


def _plank_record_rel(task_id: str, tests_dir: Path, name: str, profile,
                      run_cwd: Path) -> str:
    """Путь файла планки в записях отчёта: выкладка `<plank_layout>` с id
    задачи (требование 3) либо, без выкладки, сам файл каталога планки."""
    if profile.plank_layout:
        return f"{profile.plank_layout.replace('<id>', task_id)}/{name}"
    return os.path.relpath(tests_dir / name, run_cwd).replace(os.sep, "/")


def criterion_files(task_id: str, tdir: Path, run_cwd: Path, rule, profiles,
                    long_lived: list[str], target: str) -> list[CriterionFile]:
    """Тестовые файлы планки каталога `tdir/acceptance_tests` и свои
    долгоживущие файлы `long_lived` (пути от `run_cwd`) с компонентом из
    `profiles`: файл планки — по правилу планки, долгоживущий — по
    компоненту, чьему шаблону он подходит. Файл без компонента пропущен."""
    files: list[CriterionFile] = []
    tests_dir = Path(tdir) / "acceptance_tests"
    if tests_dir.is_dir():
        for path in sorted(tests_dir.iterdir()):
            if not path.is_file() or not rule.is_test(path.name):
                continue
            profile = _plank_file_profile(path.name, rule, profiles)
            text = _read_text(path)
            if profile is None or text is None:
                continue
            labelled = rule.is_labelled(path.name)
            head = (guard.first_comment(text) if labelled
                    else guard.module_docstring(text)) or ""
            numbers, _markers = guard.scan_ac_content([(path.name, text)],
                                                      rule=rule)
            files.append(CriterionFile(
                _plank_record_rel(task_id, tests_dir, path.name, profile,
                                  Path(run_cwd)),
                path.name, profile, labelled, frozenset(numbers), True,
                bool(GREEN_FROM_BIRTH_MARKER.search(head))))
    for rel in long_lived:
        profile = next((p for p in profiles if p.long_lived_dir
                        and p.is_long_lived(task_id, rel)), None)
        text = _read_text(Path(run_cwd) / rel)
        if profile is None or text is None:
            continue
        rule_ll = project_profile.long_lived_rule(target, profile)
        labelled = rule_ll is not None and rule_ll.is_labelled(Path(rel).name)
        numbers, _markers = guard.scan_ac_content([(rel, text)], rule=rule_ll)
        files.append(CriterionFile(rel, rel, profile, labelled,
                                   frozenset(numbers), False))
    return files


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def record_location(record) -> tuple[str, str, str, int | None] | None:
    """(компонент, путь, полное имя, номер повтора) идентификатора записи;
    `None` — идентификатор не той формы."""
    try:
        return project_profile.parse_test_id(record.id)
    except ValueError:
        return None


def is_repeat(where) -> bool:
    """`where` (`record_location`) — повтор имени теста в файле: номер от 2.
    `#1` несёт первое вхождение имени, которое само кончается на
    `#<цифры>` (`project_profile.test_id`), повтором оно не является."""
    return where is not None and where[3] is not None and where[3] >= 2


def record_criterion(record, cfile: CriterionFile) -> int | None:
    """Номер критерия записи по метке в последнем сегменте полного имени
    (требование 3): `AC-<n>: ` в начале — у файла с меткой, `test_ac<n>_`
    — у pytest; `None` — запись не тест критерия."""
    where = record_location(record)
    if where is None:
        return None
    sep = (_VITEST_NAME_SEP if cfile.profile.report == project_profile.REPORT_VITEST
           else _JUNIT_NAME_SEP)
    last = where[2].rsplit(sep, 1)[-1]
    match = (_AC_LABEL_HEAD if cfile.labelled else _PYTEST_LABEL_HEAD).match(last)
    return int(match.group(1)) if match else None


def file_records(files: list[CriterionFile], runs: dict) -> dict:
    """{файл: [записи]} — записи прогона компонента файла (`runs`: имя
    компонента -> записи `CaseResult`) с путём файла."""
    found: dict = {f: [] for f in files}
    by_key = {(f.profile.component, os.path.normpath(f.rel)): f for f in files}
    for component, records in runs.items():
        for record in records:
            where = record_location(record)
            if where is None:
                continue
            cfile = by_key.get((component, os.path.normpath(where[1])))
            if cfile is not None:
                found[cfile].append(record)
    return found


def not_passed_kind(record) -> str:
    """Вид исхода записи, которая обязана пройти (тест на ветке, тест
    файла «Зелёный с рождения:»); пусто — прошла без повтора."""
    if is_repeat(record_location(record)):
        return "повтор имени теста в файле"
    if record.retries:
        return f"{outcome.RETRY_NOTE} внутри прогона: {record.retries}"
    if record.outcome == outcome.PASSED:
        return ""
    return outcome_kind(record)


def outcome_kind(record) -> str:
    """Вид исхода записи для текста находки: прошёл, пропуск или `todo` с
    `mode`, таймаут, падение хука, имя ошибки."""
    if record.outcome == outcome.PASSED:
        return "прошёл"
    if record.outcome == outcome.SKIPPED:
        if record.mode == "todo":
            return f"todo (mode: {record.mode})"
        if record.mode:
            return f"пропуск (mode: {record.mode})"
        return f"пропуск ({record.skip_reason or 'без причины'})"
    failure = record.failure or "без имени"
    if record.outcome == outcome.ERROR:
        if failure.startswith("timeout"):
            return f"таймаут теста ({failure})"
        if failure.startswith("падение хука"):
            return failure
        return f"ошибка {failure}"
    return f"падение {failure}"


def branch_criterion_problems(files: list[CriterionFile], runs: dict) -> list[str]:
    """Находки проверки ветки (требование 6): у каждого критерия, покрытого
    тестом файлов задачи, есть запись с его меткой, и все такие записи —
    `passed` без повторов."""
    by_number: dict[int, list] = {}
    for cfile, records in file_records(files, runs).items():
        for record in records:
            n = record_criterion(record, cfile)
            if n is not None:
                by_number.setdefault(n, []).append(record)
    problems = []
    for n in sorted(set().union(*(f.numbers for f in files)) if files else ()):
        records = by_number.get(n, [])
        if not records:
            problems.append(f"AC-{n} — теста нет в отчёте прогона ветки")
            continue
        bad = [f"{r.id} ({kind})" for r in records if (kind := not_passed_kind(r))]
        if bad:
            problems.append(f"AC-{n} — тест критерия не прошёл на ветке: "
                            f"{', '.join(bad)}")
    return problems


def _branch_criteria_refuses(conn, task_id: str, profile, acc_tdir: Path,
                             run_cwd: Path, long_lived: list[str] | None,
                             records: list) -> bool:
    """Тесты критериев в отчёте прогона ветки (требование 6) — после
    зелёного прогона: у профиля в границе каждый критерий, покрытый тестом
    зафиксированной планки и долгоживущих файлов перечня, представлен в
    отчёте записями, и все они прошли без повторов. `True` — отказ
    (журнал и печать сделаны)."""
    target = store.task_target(conn, task_id)
    files = criterion_files(task_id, acc_tdir, run_cwd,
                            project_profile.plank_rule(target), [profile],
                            list(long_lived or ()), target)
    cases = [r for r in records if isinstance(r, outcome.CaseResult)]
    problems = branch_criterion_problems(files, {profile.component: cases})
    if not problems:
        return False
    detail = "; ".join(problems)
    store.journal(conn, task_id, "fsm", BRANCH_CRITERION_REFUSAL_ACTION, detail)
    print(f"[{task_id}] переход отклонён: {detail}")
    print(f"  дальше: почини код (не тест) так, чтобы тест каждого критерия "
          f"исполнялся и проходил, и повтори artel.py advance {task_id}")
    return True


def _acceptance_lock_refuses(conn, task_id: str, t, branch: str,
                             foreign: bool) -> bool:
    """Лок `acceptance_tests/` на `in_dev -> review` (требование 5,
    SPEC T023-семьи): планка, залоченная `tests_writing`
    (`tests_locked_sha`), не имеет права измениться после лока — спор с
    тестом решается эскалацией, не правкой. `locked` — sha АРТЕФАКТНОЙ
    ВЕТКИ пульта (`config.ROOT`, настоящий git) на момент лока, когда
    `foreign` (A7, требование 2 — единая логика для ЛЮБОГО target, теперь
    всегда True) — сверяется ТАМ ЖЕ против текущей головы ТОЙ ЖЕ ветки
    (`branch`), не «HEAD» рабочего дерева (чужой чекаут не должен
    сверять лок с чужой веткой вместо своей). Не-foreign (сегодня
    недостижимо после генерализации self — песочница без git) — прежнее
    поведение: сверка по "HEAD" рабочего дерева main.

    `False` — лока нет вовсе либо он не нарушен."""
    locked = t["tests_locked_sha"]
    if not locked:
        return False
    lock_ref = branch if foreign else "HEAD"
    names = artifact_branch.diff_names(task_id, locked, lock_ref,
                                       f"tasks/{task_id}/acceptance_tests")
    if names is None:
        # git не ответил (недостижимый sha после rebase/squash, сбой
        # команды) — fail-closed тем же принципом, что и
        # fixation.check_integrity() при неответившем git (ADR-0002).
        detail = (f"лок acceptance_tests/ не проверен: git не "
                  f"ответил на sha {locked} — сверка невозможна")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: лок приёмочных тестов", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        print(f"  дальше: разберись, почему git не отвечает на "
              f"tests_locked_sha={locked}, и повтори "
              f"artel.py advance {task_id}")
        return True
    if names:
        # Разница только по файлам, игнорируемым `.gitignore` пульта
        # (SPEC 01M1KVG3KSCY47HWXWF5HM0E76, требование 3, AC-4) — не
        # спор с локом, тот же критерий, что у
        # `checkpoint._commit_external_step_artifacts`.
        ignored = gitcmd.check_ignore(names, repo=workspace.task_repo(task_id))
        if ignored is None:
            detail = (f"лок acceptance_tests/ не проверен: git не "
                      f"ответил на проверку .gitignore — сверка "
                      f"невозможна")
            store.journal(conn, task_id, "fsm",
                          "переход отклонён: лок приёмочных тестов", detail)
            print(f"[{task_id}] переход отклонён: {detail}")
            print(f"  дальше: разберись, почему git не отвечает на "
                  f"check-ignore, и повтори artel.py advance "
                  f"{task_id}")
            return True
        names = [n for n in names if n not in ignored]
    if names:
        detail = (f"acceptance_tests/ изменены после лока "
                  f"(sha {locked}) — спор с тестом = эскалация, "
                  f"не правка")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: лок приёмочных тестов", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        print(f"  дальше: верни acceptance_tests/ как было, "
              f"либо эскалируй разногласие Оператору")
        return True
    return False


def _acceptance_run_refuses(conn, task_id: str, t, tdir, target: str,
                            branch: str) -> bool:
    """Обёртка прогона приёмки (`_acceptance_run_body`): планка, выложенная
    в рабочую копию кода, убирается на выходе из блока при любом исходе —
    зелёном, красном, отказе до прогона и исключении внутри него (ADR-0021,
    этап 1; SPEC 01M409YKM3QE5KVRGV0G94F5ZC, требование 3)."""
    with contextlib.ExitStack() as cleanup:
        return _acceptance_run_body(conn, task_id, t, tdir, target, branch,
                                    cleanup)


def _acceptance_run_body(conn, task_id: str, t, tdir, target: str,
                         branch: str, cleanup: contextlib.ExitStack) -> bool:
    """Прогон приёмки после подтяжки (SPEC T023, требование 6; ADR-0015,
    требование 2 — переехал с `in_dev -> review` на `in_dev -> verifying`,
    вместе с остальными шестью рубежами того же перехода): красный
    acceptance-тест чинит код разработчик, не переписывает тест (тесты
    залочены — см. `_acceptance_lock_refuses` выше). Не через `_run_gates`
    (PLAN «Подход») — `acc_tdir` нужен ПОСЛЕ прохода для
    `acceptance.summary`, пересчитывать его ценой повторного
    `acceptance.materialize_from_branch` не нужно, а печать здесь — три
    строки (сообщение, сырой `tail`, подсказка), не формат
    «сообщение+подсказка» остальных гейтов.

    SPEC T045, побочная находка: `tasks/<id>/acceptance_tests` читается
    из worktree задачи, если он заведён и стоит на своей ветке; иначе —
    прежний путь с диска главной копии. Внешний target (SPEC T094,
    требование 10): живого worktree нет вовсе — `acceptance_tests/`
    живёт только в артефактной ветке пульта (`branch` уже резолвлен),
    материализуется НА МЕСТЕ в workspace target'а (SPEC
    01M1RNZ6V7TTTTYAHBMF8JBQQS, требование 1-2, AC-1/AC-2/AC-5).

    Рабочая копия задачи не заведена или не выписана на ветку — отказ
    своим действием класса «чинит Оператор»
    (`ACCEPTANCE_CODE_COPY_REFUSAL_ACTION`, SPEC 01M446WEVJXARR5CDED8RE9CCR,
    требование 5.2): «приёмочные тесты» остаётся за красной планкой,
    которую чинит developer.

    Прогон идёт на дереве с наложенными приложениями PLAN — тем же узлом
    `appendix_tree.suite_tree`, что у автогейта, approve и `suite-run`
    (SPEC 01M4JD3SRN66SD6BM63XAGHB11, требования 1-2): тест задачи вправе
    краснеть без правки защищённого теста, которую везёт приложение, и
    прогон рабочей копии без неё был красен по построению.
    PLAN без приложений и проект не артели — рабочая копия, как прежде.
    Неприменимое приложение — именованный отказ без прогона.

    `True` — переход отклонён (планка красная) либо задача эскалирована
    повторами долгоживущих файлов (`_seed_repeats_escalate`)."""
    def _missing_plank_refuses() -> bool:
        if acceptance.plank_present(acc_tdir / "acceptance_tests"):
            return False
        spec_text = fsm._read_foreign_branch_text_or_refuse(conn, task_id,
                                                             branch, "SPEC.md")
        if spec_text is None:
            return True
        meta = yamlmini.frontmatter(spec_text) or {}
        if not guard.requires_ac_markup(meta):
            return False
        detail = (f"планка не найдена в источнике: артефактная ветка "
                  f"{branch} не несёт tasks/{task_id}/acceptance_tests/, а "
                  f"tests_writing не пропущена легитимно (skip_tests не "
                  f"задан в SPEC)")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: планка не найдена в источнике",
                      detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        return True

    # Профиль тестов проекта (SPEC 01M45FJVGQT1K0P8HDEXZX6HS7, требования
    # 3-6): контекст не разрешён или у артели нет профиля — отказ; у
    # проекта без профиля — планка командой пульта, без долгоживущих.
    decision = project_profile.for_task_target(target, task_id, conn)
    if decision.refusal:
        store.journal(conn, task_id, "fsm", project_profile.REFUSAL_ACTION,
                      decision.refusal)
        print(f"[{task_id}] переход отклонён: {decision.refusal}")
        print(f"  дальше: {project_profile.refusal_hint(task_id)}")
        return True
    # Прогон — в рабочей копии задачи в области проекта, одна ветка логики
    # для любого проекта (требование 6): прогон в главной копии пульта
    # проверял бы код пина, а не код задачи.
    run_cwd, error = workspace.ensure(task_id, t["branch"])
    if error is not None:
        # Без рабочей копии планка легла бы в пустой каталог и упала бы
        # на импорте кода — причина `ensure` понятнее этого исхода.
        detail = f"рабочая копия задачи не заведена: {error}"
        store.journal(conn, task_id, "fsm",
                      ACCEPTANCE_CODE_COPY_REFUSAL_ACTION, detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        print(f"  дальше: artel.py workspace {task_id} и повтори "
              f"artel.py advance {task_id}")
        return True
    if workspace.on_task_branch(task_id, t["branch"], target) is False:
        # `ensure` отдаёт уже заведённую копию, не сверяя её ветку: прогон
        # в ней проверял бы чужой код, а долгоживущие файлы перечня молча
        # выпали бы из группы (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ,
        # требование 9).
        detail = (f"рабочая копия задачи не выписана на ветку "
                  f"{t['branch']} — планку и долгоживущие файлы перечня "
                  f"исполнить негде")
        store.journal(conn, task_id, "fsm",
                      ACCEPTANCE_CODE_COPY_REFUSAL_ACTION, detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        print(f"  дальше: artel.py workspace {task_id} и повтори "
              f"artel.py advance {task_id}")
        return True
    # HEAD рабочей копии с её незакоммиченными правками (как `suite-run`):
    # рубеж судит то же дерево, что до приложений, плюс сами приложения.
    tree = cleanup.enter_context(appendix_tree.suite_tree(
        conn, task_id, run_cwd, not_run=PLANK_NOT_RUN))
    if tree.root is None:
        # Причину по содержимому PLAN чинит роль в своём PLAN.md — тем же
        # действием, что у гейта применимости; сбой git — нет.
        if tree.fixable:
            action = PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION
            hint = "почини приложение в PLAN.md"
        else:
            action = PLAN_APPENDIX_GATE_FAILURE_ACTION
            hint = "разберись, почему git не отвечает по ветке задачи,"
        store.journal(conn, task_id, "fsm", action, tree.refusal)
        print(f"[{task_id}] переход отклонён: {tree.refusal}")
        print(f"  дальше: {hint} и повтори artel.py advance {task_id}")
        return True
    run_cwd = tree.root
    acc_tdir = cleanup.enter_context(
        acceptance.plank_in_code_copy(task_id, branch, run_cwd))
    # Долгоживущие файлы перечня (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ,
    # требование 9) — в том же прогоне, что планка; они лежат в кодовой
    # ветке, поэтому исполнимы только из её рабочей копии. Сбой чтения
    # перечня (`None`) раньше в `in_dev` уже отклонил переход узлом сверки
    # `_long_lived_manifest_refuses`.
    long_lived = None
    command = None
    if decision.profile is None:
        project_profile.journal_skip(conn, task_id,
                                     project_profile.CHECK_LONG_LIVED_RUN,
                                     decision)
    else:
        # `pytest-own` и профиль с отчётом — профилем целиком, и в прогон,
        # и в повторы с зерном (SPEC 01M52EEHSRD93WMPHWB5VJYRKD,
        # 01M590GJAF0EDV4NBC4C99MFVH); `pult-pytest` — список.
        command = acceptance.place_channel(decision.profile)
        digests, _reason = long_lived_manifest(task_id, t, target)
        if digests is not None and t["tests_locked_sha"]:
            long_lived = sorted(digests)
    if _missing_plank_refuses():
        return True
    kwargs = {"command": command} if command else {}
    # Записи прогона — только у профиля в границе: по ним после зелёного
    # исхода сверяются тесты критериев (SPEC 01M5AQH8M2DKBV30NBY86J34A7,
    # требование 6); вне границы прогон и исходы прежние.
    records: list | None = None
    if in_outcome_bounds(decision.profile):
        records = []
        kwargs["records"] = records
    file_times: dict[str, float] = {}
    if long_lived:
        green, tail = acceptance.run(acc_tdir, cwd=run_cwd, extra=long_lived,
                                     file_times=file_times, **kwargs)
    else:
        green, tail = acceptance.run(acc_tdir, cwd=run_cwd, **kwargs)
    if long_lived:
        report = acceptance.long_lived_file_report(
            [(path, file_times.get(path)) for path in long_lived],
            config.LONG_LIVED_FILE_WARN_SEC)
        store.journal(conn, task_id, "fsm",
                      acceptance.LONG_LIVED_FILE_REPORT_ACTION, report)
    # Fingerprint окружения (SPEC T101, требование 4б, AC-5) — часть
    # исхода прогона приёмочных тестов, значение поля `detail`
    # существующего журнального события, без новой таблицы/колонки.
    fingerprint = agent_log.environment_fingerprint()
    if not green:
        detail = f"acceptance_tests красные:\n{tail}\nокружение: {fingerprint}"
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: приёмочные тесты", detail)
        print(f"[{task_id}] переход отклонён: приёмочные тесты красные")
        print(tail)
        print(f"  дальше: почини код (не тест) и повтори "
              f"artel.py advance {task_id}")
        return True
    if records is not None and _branch_criteria_refuses(
            conn, task_id, decision.profile, acc_tdir, run_cwd, long_lived,
            records):
        return True
    if long_lived and _seed_repeats_escalate(conn, task_id, t, long_lived,
                                             run_cwd, command):
        return True
    if long_lived is None:
        card = acceptance.summary(acc_tdir, branch=t["branch"],
                                  repo=workspace.task_repo(task_id))
    else:
        card = acceptance.summary(
            acc_tdir, branch=t["branch"],
            long_lived=[run_cwd / path for path in long_lived],
            repo=workspace.task_repo(task_id))
    store.journal(conn, task_id, "fsm", "приёмочные тесты пройдены",
                  f"{tree.mark(card)}\nокружение: {fingerprint}")
    print(f"[{task_id}] {card}")
    return False
