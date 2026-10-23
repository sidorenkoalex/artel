"""Команда `plank-run <id> [файл]`: штатный локальный прогон планки задачи в
шаге роли (SPEC 01M41R4YAM4NGEQXW1FWH7T22M, требования 1-2).

С ADR-0021 (этап 1) документы задачи живут в каталоге документов, а планку
в рабочую копию кода кладёт только пульт на время своего прогона. Команды
для такого же прогона у роли не было — она копировала планку руками и
убирала за собой; 03.10.2026 пять раз уборкой стал `shutil.rmtree("tasks")`
— весь отслеживаемый каталог задач рабочей копии. Здесь выкладка и уборка —
узлом пульта (`acceptance.plank_in_code_copy`): убирается только
`tasks/<id>/` рабочей копии кода, на любом исходе прогона.

Источник планки: в `tests_writing` — черновик `acceptance_tests/` каталога
документов задачи (его пишет test_author, в ссылку он попадёт только после
шага); в остальных состояниях — зафиксированная планка ссылки документов,
а не диск каталога документов.

`[файл]` — и путь долгоживущего файла своей задачи от корня рабочей копии
кода (`Profile.is_long_lived` профиля проекта задачи, SPEC
01M56G23ZQDHV2BKEVWWC22R96): роли внешнего проекта разрешён только
`artel.py` пульта, а команда профиля (`uv run pytest` в `workdir`) роли
неизвестна. Такой путь прогоняется тем же раннером без выкладки планки,
после тех же отказов до выкладки; планка ему не нужна.

Только чтение для пульта: строка задачи, журнал, ссылки и ветка задачи не
меняются, lease не берётся — поэтому команда в перечне команд роли
(`artel._ROLE_ALLOWED_COMMANDS`).
"""
import sys
from pathlib import Path

from . import (acceptance, agent_log, artifact_branch, config,
               project_profile, store, workspace)

NO_PLANK = "планки нет"
NO_SUMMARY_LINE = "итоговой строки нет"


def _code_dir(task_id: str, target: str) -> Path:
    """Рабочая копия кода задачи — `worktrees/<id>/` области её проекта
    (ADR-0021 п.1), тот же выбор, что у прогона пульта
    (`advance_gates/acceptance._acceptance_run_body`)."""
    return workspace.path(task_id, target)


def _is_plank_file(rel: str) -> bool:
    """Кеш байткода черновика (прогон test_author из каталога документов)
    — не часть планки."""
    return "__pycache__" not in rel.split("/") and not rel.endswith(".pyc")


def _draft_files(docs_plank: Path) -> dict[str, bytes]:
    if not docs_plank.is_dir():
        return {}
    files = {}
    for path in sorted(docs_plank.rglob("*")):
        rel = path.relative_to(docs_plank).as_posix()
        if path.is_file() and _is_plank_file(rel):
            files[rel] = path.read_bytes()
    return files


def _has_tests(names) -> bool:
    return any(Path(n).name.startswith("test_") and n.endswith(".py")
               for n in names)


def _component_names(names: list[str], rule, component: str | None
                     ) -> list[str]:
    """Файлы планки компонента проекта задачи по правилу не по умолчанию
    (SPEC 01M59Z0FW1699SJQ2FA5Y76CZ3, требование 8); компонент не назван
    (профиль не прочитан) — файлы любого компонента правила."""
    return [n for n in names
            if (rule.component_of(n) == component if component
                else rule.owns(n))]


def _component_masks(rule, component: str | None) -> list[str]:
    masks = rule.masks(component) if component else ()
    return list(masks or (m for c in rule.components for m in c.masks))


def _selected(arg: str, task_id: str, names: list[str]) -> str | None:
    """Путь от каталога планки для аргумента `[файл]` (с `::узлом` pytest,
    если он назван) либо `None`, если такого файла в планке нет. Принимает
    имя файла и его путь с префиксом `tasks/<id>/acceptance_tests/`."""
    path, sep, node = arg.partition("::")
    for prefix in (f"tasks/{task_id}/acceptance_tests/", "acceptance_tests/"):
        if path.startswith(prefix):
            path = path[len(prefix):]
    path = path.rstrip("/")
    if path in names or any(n.startswith(path + "/") for n in names):
        return path + sep + node
    return None


def _long_lived_arg(arg: str | None, task_id: str, target: str) -> bool:
    """Аргумент `[файл]` — путь долгоживущего файла своей задачи (от корня
    рабочей копии кода, с `::узлом` pytest или без) по профилю её проекта
    (SPEC 01M56G23ZQDHV2BKEVWWC22R96, требование 5). Профиля нет — `False`:
    прежний выбор только из планки."""
    if not arg:
        return False
    profile = project_profile.for_task_target(target, task_id).profile
    return profile is not None and \
        profile.is_long_lived(task_id, arg.partition("::")[0])


def _long_lived_target(arg: str, code_dir: Path, own) -> str:
    """Цель pytest для долгоживущего пути. У `pytest-own` — абсолютный
    путь: `acceptance._own_target` переводит в `workdir` только путь без
    `::узла`, а абсолютный оставляет как есть. У раннера пульта — путь от
    корня рабочей копии: абсолютный сторож роли
    `conftest._is_targeted_path` целевым не признаёт."""
    if own is None:
        return arg
    path, sep, node = arg.partition("::")
    return str(code_dir / path) + sep + node


def _docs_in_code_copy(own_dir: Path) -> list[str]:
    """Файлы `tasks/<id>/` рабочей копии кода вне `acceptance_tests/` —
    документы, записанные туда по ошибке: уборка выкладки снесла бы их до
    того, как пульт после шага перенесёт их в ссылку документов."""
    if not own_dir.is_dir():
        return []
    return sorted(p.relative_to(own_dir).as_posix()
                  for p in own_dir.rglob("*")
                  if p.is_file() and not p.relative_to(own_dir).as_posix()
                  .startswith("acceptance_tests/"))


def _drift_from_ref(task_id: str, own_dir: Path) -> list[str] | None:
    """Файлы `acceptance_tests/` рабочей копии кода, расходящиеся с
    зафиксированной планкой ссылки документов (изменённые, новые и, если
    на диске планка есть, — недостающие): незафиксированная правка
    Оператора для `amend-tests`, которую выкладка и уборка `plank-run`
    стёрли бы молча (SPEC 01M4JD36367E5CG3GXDV429XTE, требование 3).
    Помощник пульта и кеш байткода — не планка. Пусто — на диске файлов
    планки нет или они совпадают со ссылкой; `None` — ссылка не прочитана."""
    plank_dir = own_dir / "acceptance_tests"
    disk = {rel: data for rel, data in _draft_files(plank_dir).items()
            if rel != acceptance.PLANK_HELPER_NAME}
    if not disk:
        return []
    ref = artifact_branch.branch_name(task_id)
    prefix = f"tasks/{task_id}/acceptance_tests/"
    paths = artifact_branch.ls_tree(task_id, ref, prefix.rstrip("/"))
    if paths is None and not artifact_branch.rev_sha(task_id, ref):
        paths = []
    if paths is None:
        return None
    fixed: dict[str, bytes] = {}
    for path in paths:
        if not path.startswith(prefix):
            continue
        text, _reason = artifact_branch.show(task_id, ref, path)
        if text is None:
            return None
        fixed[path[len(prefix):]] = text.encode("utf-8")
    return sorted(rel for rel in set(disk) | set(fixed)
                  if disk.get(rel) != fixed.get(rel))


def cmd_plank_run(task_id: str, file_arg: str | None = None) -> None:
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    t = store.get_task(conn, task_id)
    target = store.task_target(conn, task_id)
    head = f"[{task_id}] plank-run"

    code_dir = _code_dir(task_id, target)
    if not code_dir.is_dir():
        sys.exit(f"{head}: отказ — рабочей копии кода задачи нет ({code_dir}); "
                 f"планку выложить некуда")

    draft = None
    if t["state"] == "tests_writing":
        docs_plank = (artifact_branch.docs_dir(task_id, target)
                      / "acceptance_tests")
        draft = _draft_files(docs_plank)
        names = sorted(draft)
        source = f"черновик {docs_plank}"
    else:
        ref = artifact_branch.branch_name(task_id)
        prefix = f"tasks/{task_id}/acceptance_tests/"
        paths = artifact_branch.ls_tree(task_id, ref, prefix.rstrip("/"))
        if paths is None and not artifact_branch.rev_sha(task_id, ref):
            paths = []  # ссылки нет — нет и зафиксированной планки
        if paths is None:
            sys.exit(f"{head}: отказ — ссылка документов {ref} не прочитана "
                     f"(git не ответил); планка не выложена")
        names = sorted(p[len(prefix):] for p in paths if p.startswith(prefix))
        source = f"зафиксированная планка {ref}"
    long_lived = _long_lived_arg(file_arg, task_id, target)
    if long_lived:
        # Своему долгоживущему файлу планка не нужна (требование 6), а
        # отказы до выкладки ниже он проходит тем же кодом (требование 5).
        long_lived_path = file_arg.partition("::")[0]
        if not (code_dir / long_lived_path).is_file():
            sys.exit(f"{head}: отказ — файла {long_lived_path} нет в рабочей "
                     f"копии кода ({code_dir}); pytest не запускался")
    else:
        # Планка проверяется по правилу планки проекта (SPEC
        # 01M59Z0FW1699SJQ2FA5Y76CZ3, требование 8); у правила по умолчанию
        # — прежний код и прежние тексты.
        rule = project_profile.plank_rule(target)
        if rule.refusal:
            sys.exit(f"{head}: отказ — {rule.refusal}; pytest не запускался")
        profile = (project_profile.for_task_target(target, task_id).profile
                   if not rule.is_default or (file_arg and "::" in file_arg)
                   else None)
        if rule.is_default:
            if not _has_tests(names):
                sys.exit(f"{head}: отказ — {NO_PLANK}: в источнике ({source}) "
                         f"нет файлов test_*.py; pytest не запускался")
        else:
            component = profile.component if profile is not None else None
            names = _component_names(names, rule, component)
            if not any(rule.is_test(n) for n in names):
                sys.exit(f"{head}: отказ — {NO_PLANK}: в источнике ({source}) "
                         f"нет файлов "
                         f"{', '.join(_component_masks(rule, component))}; "
                         f"pytest не запускался")
        if file_arg and "::" in file_arg and profile is not None and \
                not acceptance.is_pytest_command(profile.command):
            sys.exit(f"{head}: отказ — узел :: у компонента "
                     f"{acceptance._component_name(profile)} не "
                     f"поддерживается; передай файл")

    selected = None
    if file_arg and not long_lived:
        selected = _selected(file_arg, task_id, names)
        if selected is None:
            sys.exit(f"{head}: отказ — файла {file_arg} нет в планке "
                     f"({source}); в ней: {', '.join(names)}")

    own_dir = code_dir / "tasks" / task_id
    stray_docs = _docs_in_code_copy(own_dir)
    if stray_docs:
        sys.exit(f"{head}: отказ — в рабочей копии кода лежат файлы "
                 f"{own_dir}: {', '.join(stray_docs)}; документы задачи "
                 f"пишутся в каталог документов "
                 f"{artifact_branch.docs_dir(task_id, target)}, а plank-run "
                 f"убирает {own_dir} целиком")
    drift = _drift_from_ref(task_id, own_dir)
    if drift is None:
        sys.exit(f"{head}: отказ — ссылка документов "
                 f"{artifact_branch.branch_name(task_id)} не прочитана (git "
                 f"не ответил); сверить {own_dir / 'acceptance_tests'} не с "
                 f"чем, планка не выложена")
    if drift:
        sys.exit(f"{head}: отказ — в {own_dir / 'acceptance_tests'} файлы "
                 f"расходятся с зафиксированной планкой: {', '.join(drift)}; "
                 f"выкладка стёрла бы эту правку. Зафиксируй её: artel.py "
                 f"amend-tests {task_id} --reason «…» — или убери файлы "
                 f"сам; pytest не запускался")

    # Профиль `pytest-own` проекта задачи (SPEC 01M52EEHSRD93WMPHWB5VJYRKD);
    # иначе — раннер пульта, как прежде.
    own = acceptance._task_own_profile(conn, task_id)
    if long_lived:
        # Файл уже в рабочей копии кода — выкладка планки не нужна, и
        # `tasks/<id>/` рабочей копии этот прогон не трогает.
        print(f"{head}: долгоживущий файл {file_arg}, cwd {code_dir}",
              flush=True)
        target_arg = _long_lived_target(file_arg, code_dir, own)
        code, output = (acceptance.run_plank([target_arg], code_dir, profile=own)
                        if own is not None
                        else acceptance.run_plank([target_arg], code_dir))
    else:
        print(f"{head}: {source}, cwd {code_dir}", flush=True)
        with acceptance.plank_in_code_copy(
                task_id, artifact_branch.branch_name(task_id), code_dir,
                files=draft) as tdir:
            # Путь относителен от cwd pytest (рабочей копии кода): абсолютный
            # сторож роли `conftest._is_targeted_path` не признаёт целевым и
            # отказывает прогону в шаге роли (SPEC 01M41W15BK20WBTD9TMBTSXNZA).
            tests_rel = (tdir / "acceptance_tests").relative_to(code_dir).as_posix()
            target_arg = f"{tests_rel}/{selected}" if selected else tests_rel
            # `task_id` — у `pytest-own` цель уходит в выкладку под
            # `long_lived_dir` (SPEC 01M57JYJQC8VAHEWMXFNM7D1GS).
            code, output = (
                acceptance.run_plank([target_arg], code_dir, profile=own,
                                     task_id=task_id)
                if own is not None
                else acceptance.run_plank([target_arg], code_dir))
    print(output)
    # Итог компонента `pult-vitest` — по блоку Vitest (SPEC
    # 01M5ENWTDD8NP9SMPFX3JN08J9, требование 6), признак тот же, что у
    # насоса шага; у прочих, в том числе без профиля, — прежние строки.
    task_profile = project_profile.for_task_target(target, task_id).profile
    if task_profile is not None and \
            task_profile.report == project_profile.REPORT_VITEST:
        runner_name = "vitest"
        summaries = agent_log.vitest_summaries(output)
        summary = summaries[-1] if summaries else NO_SUMMARY_LINE
    else:
        runner_name = "pytest"
        summary = acceptance.run_summary_line(output) or NO_SUMMARY_LINE
    if code is None:
        sys.exit(f"{head}: итог {runner_name}: {summary}; прогон превысил "
                 f"{config.ACCEPTANCE_TIMEOUT_SEC}с и оборван")
    print(f"{head}: итог {runner_name}: {summary}; код выхода {runner_name}: "
          f"{code}")
    if code != 0:
        sys.exit(code)
