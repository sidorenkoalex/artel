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

Процесс роли задачи с раннером `compose` планку сам не гонит: команда пишет
запрос в очередь каталога `suite-run`, исполняет его процесс пульта,
ведущий шаг роли, а итог читает `plank-run <id> --wait <минуты>` (SPEC
01M6TR3Q3SQSS1ZNGA4T7V39RW; очередь — `suite_run`, раздел «запросы роли»).
"""
import sys
from pathlib import Path

from . import (acceptance, agent_log, artifact_branch, config,
               project_profile, store, workspace)

USAGE = "plank-run <id> [<файл> | --wait <минуты>]"
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


def _plank_source(task_id: str, t, target: str, *,
                  ref_if_no_draft: bool = False) -> tuple:
    """(файлы черновика или `None`, имена файлов планки, источник словами)
    — черновик каталога документов в `tests_writing`, иначе зафиксированная
    планка ссылки документов; имена `None` — ссылка не прочитана.

    `ref_if_no_draft` — прогон по запросу роли: каталога черновика на диске
    нет (автокоммит прошлого шага перенёс его в ссылку и убрал, а выкладка
    каталога документов этого шага не состоялась) — зафиксированная планка."""
    if t["state"] == "tests_writing":
        docs_plank = (artifact_branch.docs_dir(task_id, target)
                      / "acceptance_tests")
        if not (ref_if_no_draft and not docs_plank.is_dir()):
            draft = _draft_files(docs_plank)
            return draft, sorted(draft), f"черновик {docs_plank}"
    ref = artifact_branch.branch_name(task_id)
    prefix = f"tasks/{task_id}/acceptance_tests/"
    paths = artifact_branch.ls_tree(task_id, ref, prefix.rstrip("/"))
    if paths is None and not artifact_branch.rev_sha(task_id, ref):
        paths = []  # ссылки нет — нет и зафиксированной планки
    if paths is None:
        return None, None, f"ссылка документов {ref}"
    names = sorted(p[len(prefix):] for p in paths if p.startswith(prefix))
    return None, names, f"зафиксированная планка {ref}"


def _pult_command(task_id: str) -> str:
    return f"python3 {config.ROOT / 'orchestrator' / 'artel.py'} plank-run {task_id}"


def request_file_refusal(conn, task_id: str, file_arg: str) -> str:
    """Причина отказа запросу роли с файлом `file_arg` (SPEC
    01M6TR3Q3SQSS1ZNGA4T7V39RW, требование 11): допустимы только файл
    планки задачи и её долгоживущий файл — тот же выбор, что у
    `cmd_plank_run`. Пусто — файл допустим."""
    t = store.get_task(conn, task_id)
    target = store.task_target(conn, task_id)
    if _long_lived_arg(file_arg, task_id, target):
        return ""
    _draft, names, source = _plank_source(task_id, t, target,
                                          ref_if_no_draft=True)
    if names is None:
        return (f"{source} не прочитана (git не ответил) — файл {file_arg} "
                f"не сверить с планкой задачи")
    if _selected(file_arg, task_id, names) is None:
        return (f"файл {file_arg} — не файл планки задачи ({source}: "
                f"{', '.join(names) or 'пусто'}) и не её долгоживущий файл")
    return ""


def _wait_minutes(text: str) -> int:
    limit = config.SUITE_RUN_MAX_WAIT_MIN
    try:
        minutes = int(text)
    except ValueError:
        minutes = -1
    if not 0 <= minutes <= limit:
        sys.exit(f"plank-run --wait: отказ — «{text}» не число минут от 0 до "
                 f"{limit} (config.SUITE_RUN_MAX_WAIT_MIN = {limit}: одно "
                 f"ожидание укладывается в вызов инструмента роли); прогон не "
                 f"тронут, жди повторным --wait")
    return minutes


def _cmd_wait(task_arg: str, extra: tuple) -> None:
    """`plank-run <id> --wait <минуты>`: итог последнего запроса планки
    задачи (SPEC 01M6TR3Q3SQSS1ZNGA4T7V39RW, требования 4, 17)."""
    from . import suite_run  # suite_run -> suite_lock -> acceptance
    if len(extra) != 1:
        sys.exit(f"{USAGE}: --wait требует одно число минут")
    minutes = _wait_minutes(extra[0])
    conn = suite_run._db()
    task_id = store.resolve_task_id(conn, task_arg)
    head = f"[{task_id}] plank-run"
    number = suite_run.latest_request(task_id, (suite_run.KIND_PLANK,))
    if number is None:
        sys.exit(f"{head}: отказ — у задачи {task_id} нет запроса plank-run, "
                 f"ждать нечего: запрос пишет `plank-run <id>` в шаге роли "
                 f"задачи с раннером compose")
    suite_run.wait_request(task_id, number, minutes, head,
                           _pult_command(task_id))


def _submitted(task_arg: str, file_arg: str | None) -> bool:
    """Процесс роли и раннер `compose` профиля задачи — запрос в очередь
    исполнителя шага вместо прогона (требование 1); `False` — прежний путь."""
    from . import runner, suite_run  # runner -> ... -> plank_run
    if not runner.in_role_environment():
        return False
    # БД — как у `suite-run`: у роли на Codex она открыта только на чтение.
    conn = suite_run._db()
    task_id = store.resolve_task_id(conn, task_arg)
    target = store.task_target(conn, task_id)
    if not suite_run.request_mode(conn, task_id, target):
        return False
    suite_run.submit_request(conn, task_id, suite_run.KIND_PLANK, file_arg,
                             f"[{task_id}] plank-run", _pult_command(task_id))
    return True


def cmd_plank_run(task_id: str, file_arg: str | None = None,
                  *extra: str, ref_if_no_draft: bool = False) -> None:
    """`ref_if_no_draft` — дочерний прогон исполнителя запросов роли
    (`_plank_source`)."""
    if file_arg == "--wait":
        _cmd_wait(task_id, extra)
        return
    if extra:
        sys.exit(f"plank-run: отказ — лишний аргумент «{extra[0]}»; "
                 f"использование: {USAGE}")
    if _submitted(task_id, file_arg):
        return
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    t = store.get_task(conn, task_id)
    target = store.task_target(conn, task_id)
    head = f"[{task_id}] plank-run"

    code_dir = _code_dir(task_id, target)
    if not code_dir.is_dir():
        sys.exit(f"{head}: отказ — рабочей копии кода задачи нет ({code_dir}); "
                 f"планку выложить некуда")

    draft, names, source = _plank_source(task_id, t, target,
                                         ref_if_no_draft=ref_if_no_draft)
    if names is None:
        sys.exit(f"{head}: отказ — {source} не прочитана "
                 f"(git не ответил); планка не выложена")
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
                     f"{acceptance.component_name(profile)} не "
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
    own = acceptance.task_own_profile(conn, task_id)
    if long_lived:
        # Файл уже в рабочей копии кода — выкладка планки не нужна, и
        # `tasks/<id>/` рабочей копии этот прогон не трогает.
        print(f"{head}: долгоживущий файл {file_arg}, cwd {code_dir}",
              flush=True)
        target_arg = _long_lived_target(file_arg, code_dir, own)
        # `compose_task_id` — только имя проекта Compose: раскладку планки
        # он не включает, в отличие от `task_id`.
        code, output = (acceptance.run_plank([target_arg], code_dir, profile=own,
                                             compose_task_id=task_id)
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
