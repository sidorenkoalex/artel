"""Команда `preflight <id>`: предпроверка выхода из `tests_writing` для роли
до сдачи шага (SPEC 01M4P4ZP37WV81410YTZHKQC8D).

Роль узнавала об отказе перехода только после сдачи шага: «сухого»
перехода нет — `advance` идёт под lease и пишет журнал. Предпроверка судит
по черновику test_author до автокоммита шага: планка и SPEC.md — с диска
каталога документов задачи (как `plank-run` в `tests_writing`),
долгоживущие файлы — из рабочей копии кода, включая незакоммиченные.
Считает теми же ядрами `scripts/guard.py`, что переход на выходе
`tests_writing` (`fsm._tests_writing_ac_state`,
`advance_gates/tests_writing._tests_writing_test_groups_gate` и
`_tests_writing_long_lived_gate`), с метками файлов формы перехода — строки
ошибок совпадают с теми, что переход пишет в журнал.

Только чтение: БД открывается `sqlite3` с `mode=ro` (без `store.db()`, WAL
и `migrate`), lease не берётся, журнал, коммиты, push, рабочие копии и
выкладка планки не трогаются — поэтому команда в перечне команд роли
(`artel._ROLE_ALLOWED_COMMANDS`) и работает при БД только на чтение.

Не связан с проверками окружения `orchestrator/doctor/preflight.py`.
"""
import sqlite3
import sys
from pathlib import Path

from scripts import guard

from . import (artifact_branch, config, project_profile, repo_context, store,
               workspace, yamlmini)

STATE = "tests_writing"
PLANK_DIR = "acceptance_tests"

# Фильтры входа: функции guard, которыми предпроверка отбирает входы, а не
# проверяет их (требование 2) — тот же фильтр, что у автокоммита
# (`checkpoint._commit_external_step_artifacts`).
INPUT_FILTERS = (guard.is_extraneous_acceptance_test_file,)

CHECK_PROFILE = "профиль тестов"
CHECK_TRACEABILITY = "трассируемость AC"
CHECK_REDNESS = "маркер красноты"
CHECK_ID_FORMAT = "образец id задачи"
CHECK_LONG_LIVED = "долгоживущие файлы"
CHECK_GROUPS = "строка группы"

PASSED = "пройдена"
REFUSED = "отказ"
NOT_CHECKED_PREFIX = "не проверяется предпроверкой (проверит переход): "
NO_PROFILE = "не проверяется предпроверкой: у проекта нет профиля тестов"
PROFILE_UNRESOLVED = ("не проверяется предпроверкой: профиль тестов проекта "
                      "не разрешён")

# Проверки выхода из `tests_writing`, которые предпроверка не исполняет
# (требование 6): (имя, функции guard, вызов которых в телах перехода пункт
# покрывает). Сторож сверяет функции guard перехода с вызовами модуля и
# этим перечнем (требование 12) — пункт называет только функции тех тел.
NOT_CHECKED = (
    ("сверка незакоммиченного результата шага "
     "(fsm._uncommitted_step_result_refuses)", ()),
    ("чтение SPEC.md и acceptance_tests/ со ссылки документов и путь чтения "
     "планки с диска (orchestrator/fsm.py:541–563)",
     ("guard.scan_acceptance_tests", "guard.acceptance_traceability_errors",
      "guard.scan_redness_markers", "guard.scan_id_format_samples")),
    ("эскалация по пометкам escalate (orchestrator/fsm_advance.py:493–510)", ()),
    ("дифф кодовой ветки против базы и правило «только добавление» "
     "(_tests_writing_code_diff, _diff_entry_error)", ()),
    ("путь долгоживущего файла уже существует в main "
     "(orchestrator/advance_gates/tests_writing.py:449–451)", ()),
    ("рабочая копия кодовой ветки выписана "
     "(orchestrator/advance_gates/tests_writing.py:461–463)", ()),
    ("посторонние файлы планки (_tests_writing_stray_plank_files_gate)", ()),
    ("рабочая копия кода (_tests_writing_code_copy_gate)", ()),
    ("сухой сбор вместе с источником артефактов планки "
     "(_tests_writing_dry_collect_gate, _tests_writing_artifact_source_gate)",
     ()),
    ("перечень долгоживущих файлов (_tests_writing_manifest_gate)", ()),
)


def _open_db_readonly() -> sqlite3.Connection | None:
    """Соединение с БД пульта только на чтение; `None` — файла БД нет."""
    if not config.DB.is_file():
        return None
    conn = sqlite3.connect(f"{config.DB.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _task_row(arg: str):
    """Строка задачи; отказ — сообщение на stderr и код 2 (требование 8):
    сообщение то же, что у `show` (`store.resolve_task_id`/`get_task`)."""
    conn = _open_db_readonly()
    if conn is None:
        print(f"БД пульта {config.DB} не найдена", file=sys.stderr)
        sys.exit(2)
    try:
        return store.get_task(conn, arg)
    except SystemExit as exc:
        print(exc.code, file=sys.stderr)
        sys.exit(2)
    finally:
        conn.close()


def _filtered(rel: str, rule=None) -> bool:
    return any(input_filter(rel, rule) for input_filter in INPUT_FILTERS)


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _plank_py_files(docs: Path, rule) -> list[tuple[str, str]]:
    """(путь от `acceptance_tests/`, текст) файлов `.py` черновика планки,
    которые автокоммит перенёс бы в ссылку документов. Правило планки не
    по умолчанию (SPEC 01M59KMPG2ZMK10V556VZVQD65, требование 7) — файлы
    компонентов правила, не только `.py`."""
    plank = docs / PLANK_DIR
    if not plank.is_dir():
        return []
    files = []
    pattern = "*.py" if rule.is_default else "*"
    for path in sorted(plank.rglob(pattern)):
        rel = path.relative_to(plank).as_posix()
        if not path.is_file() or _filtered(rel, rule):
            continue
        if not (rule.is_default or rule.owns(rel)):
            continue
        text = _read(path)
        if text is not None:
            files.append((rel, text))
    return files


def _long_lived_files(task_id: str, code_copy: Path,
                      profile) -> tuple[list[tuple[str, str]], list[str]]:
    """(путь от корня рабочей копии, текст) долгоживущих файлов задачи на
    диске рабочей копии кода — с незакоммиченными и неотслеживаемыми; и
    ошибки чтения."""
    directory = code_copy / profile.long_lived_dir
    if not directory.is_dir():
        return [], []
    files, errors = [], []
    for path in sorted(directory.rglob("*")):
        rel = path.relative_to(code_copy).as_posix()
        if not path.is_file() or not profile.is_long_lived(task_id, rel):
            continue
        text = _read(path)
        if text is None:
            errors.append(f"{rel}: не прочитан с диска рабочей копии кода")
        else:
            files.append((rel, text))
    return files, errors


def _traceability(task_id: str, docs: Path, plank: list[tuple[str, str]],
                  long_lived: list[tuple[str, str]], rule,
                  by_template: bool = False) -> list[str]:
    """Тем же ядром, что ветко-корректный путь `fsm._tests_writing_ac_state`:
    источники — все `.py` планки (у правила не по умолчанию — тестовые
    файлы по правилу), долгоживущие тексты покрывают AC; у профиля из
    шаблона `long_lived` (`by_template`) — парами (путь, текст) по правилу
    (SPEC 01M5AA5TS90RDJ2AFXB882WTPD, требование 7)."""
    spec_text = _read(docs / "SPEC.md")
    if spec_text is None:
        return [f"tasks/{task_id}/SPEC.md: не прочитан с диска каталога "
                f"документов {docs}"]
    extra_tested, extra_markers = guard.scan_ac_content(
        list(long_lived) if by_template
        else [text for _rel, text in long_lived], rule=rule)
    sources = ([text for _rel, text in plank] if rule.is_default
               else [(rel, text) for rel, text in plank if rule.is_test(rel)])
    tested, markers = guard.scan_ac_content(sources, rule=rule)
    tested = tested | extra_tested
    markers = {**extra_markers, **markers}
    meta = yamlmini.frontmatter(spec_text) or {}
    return guard.traceability_errors_from_content(spec_text, meta, tested,
                                                  markers, rule=rule)


def _plank_label(task_id: str, rel: str) -> str:
    return f"tasks/{task_id}/{PLANK_DIR}/{rel}"


def _groups(task_id: str, docs: Path, profile, rule,
            network_addresses: bool, project_imports) -> list[str]:
    """Состав и порядок `_tests_writing_test_groups_gate`; метка —
    `acceptance_tests/<файл>`, как у выложенной для сбора планки."""
    files = [(label, text) for label, text
             in guard.acceptance_test_files(docs, rule)
             if not _filtered(label.split("/", 1)[1], rule)]
    return (guard.group_line_errors_from_files(files, rule)
            + guard.long_lived_plank_errors(
                files, task_id, profile.long_lived_dir,
                profile.long_lived_name, rule=rule,
                example=profile.long_lived_hint(task_id))
            + guard.long_lived_errors_from_files(
                files, task_id, network_addresses=network_addresses,
                project_imports=project_imports, rule=rule)
            + guard.plank_ban_errors(files, rule))


def _long_lived(task_id: str, files: list[tuple[str, str]], profile, rule,
                network_addresses: bool, project_imports) -> list[str]:
    """Проверки `_tests_writing_long_lived_gate`, исполнимые без git: строка
    группы каждого файла, затем ядро долгоживущих файлов; `rule` — как у
    перехода (`project_profile.long_lived_rule`)."""
    errors = []
    for path, text in files:
        errors += guard.long_lived_group_errors([(path, text)],
                                                profile.long_lived_dir, rule)
    return (errors + guard.long_lived_errors_from_files(
        files, task_id, network_addresses=network_addresses,
        project_imports=project_imports, rule=rule)
        + guard.plank_ban_errors(files, rule))


def _report(check: str, errors: list[str]) -> bool:
    """Печатает заголовок проверки и строки ошибок; True — отказ."""
    print(f"{check}: {REFUSED if errors else PASSED}")
    for error in errors:
        print(f"  {error}")
    return bool(errors)


def cmd_preflight(arg: str) -> None:
    row = _task_row(arg)
    task_id = row["id"]
    if row["state"] != STATE:
        print(f"Задача {task_id} в состоянии {row['state']} — preflight "
              f"проверяет только выход из {STATE}", file=sys.stderr)
        sys.exit(2)
    target = row["target"] or config.DEFAULT_TARGET
    docs = artifact_branch.docs_dir(task_id, target)
    print(f"[{task_id}] предпроверка выхода из {STATE}: черновик {docs}")

    refused = False
    decision = project_profile.for_task_target(target, task_id)
    profile = decision.profile
    # Отказ построения правила планки отказывает и переход (SPEC
    # 01M59KMPG2ZMK10V556VZVQD65, требование 2); проверки ниже — по
    # умолчанию.
    rule = project_profile.plank_rule(target)
    profile_errors = [rule.refusal] if rule.refusal else []
    if decision.refusal:
        profile_errors = [decision.refusal, *profile_errors,
                          project_profile.refusal_hint(task_id)]
    refused = _report(CHECK_PROFILE, profile_errors)

    long_lived: list[tuple[str, str]] = []
    long_lived_read_errors: list[str] = []
    if profile is not None:
        code_copy = workspace.path(task_id, target)
        if code_copy.is_dir():
            long_lived, long_lived_read_errors = _long_lived_files(
                task_id, code_copy, profile)
        else:
            print(f"рабочей копии кода {code_copy} нет — долгоживущих файлов нет")

    plank = _plank_py_files(docs, rule)
    by_template = profile is not None and bool(profile.long_lived_template)
    refused |= _report(CHECK_TRACEABILITY,
                       _traceability(task_id, docs, plank, long_lived, rule,
                                     by_template))
    refused |= _report(CHECK_REDNESS, guard.redness_marker_errors_from_files(
        [(_plank_label(task_id, rel), text) for rel, text in plank
         if (Path(rel).name.startswith("test_") if rule.is_default
             else rule.is_test(rel))], rule=rule))
    refused |= _report(CHECK_ID_FORMAT, guard.id_format_sample_errors(
        [(_plank_label(task_id, rel), text) for rel, text in plank]))

    if profile is None:
        skipped = PROFILE_UNRESOLVED if decision.refusal else NO_PROFILE
        for check in (CHECK_LONG_LIVED, CHECK_GROUPS):
            print(f"{check}: {skipped}")
    else:
        network_addresses = repo_context.is_artel(target)
        # Правило импортов по проекту задачи — тем же узлом, что переход
        # (`tests_writing._project_imports`), но по `target` строки: БД
        # предпроверка не открывает.
        project_imports = project_profile.long_lived_imports(target, profile)
        long_lived_rule = project_profile.long_lived_rule(target, profile)
        refused |= _report(CHECK_LONG_LIVED, long_lived_read_errors + _long_lived(
            task_id, long_lived, profile, long_lived_rule, network_addresses,
            project_imports))
        refused |= _report(CHECK_GROUPS, _groups(task_id, docs, profile, rule,
                                                 network_addresses,
                                                 project_imports))

    for name, functions in NOT_CHECKED:
        suffix = f" — {', '.join(functions)}" if functions else ""
        print(f"{NOT_CHECKED_PREFIX}{name}{suffix}")
    sys.exit(1 if refused else 0)
