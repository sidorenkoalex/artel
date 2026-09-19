"""Семейство гейта зон `_zones_gate` и его прямые помощники (SPEC
01M2CYQR0357VAQFZ5VACJD9TD, требование 1) — перенесено дословно из
`orchestrator/fsm_advance.py`."""
from scripts import guard

from .. import checkpoint, config, gitcmd, store, workspace
from ._base import GateRefusal, _run_gates

# Маркер мандата Оператора на расширение зон (SPEC 01M1P9QCHPHSCEA6TK13PV85SP,
# ANSWER-1.md, п.2, канал ADR-0012) — строка в ЛЮБОМ ANSWER-n.md задачи,
# разбирается только по этому префиксу; свободный текст ANSWER не
# анализируется.
_ZONES_MANDATE_MARKER = "Расширение зон разрешено:"

# Действие отказа гейта зон в подслучае «мандат Оператора покрывает ВСЕ
# пути диффа вне зон, а раздел «## Расширение зон» PLAN.md отсутствует
# либо не совпадает с мандатом» (SPEC 01M2XFSNVGWA2VX5XFEYR93Y4Z,
# требование 1). Отдельное имя нужно `orchestrator/auto.py::
# _pre_advance_step`: причину этого отказа устраняет сама роль (PLAN.md —
# её артефакт), это класс «роль ещё не закончила», а не «нужны руки
# Оператора»; прежнее действие «переход отклонён: гейт зон» (мандата нет
# или он покрывает не все пути) остаётся классом Оператора и текстом
# байт-в-байт (требование 2). Префикс «переход отклонён» общий — по нему
# `store.refusal_history` доносит отказ до брифа роли (AC-4).
ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION = (
    "переход отклонён: гейт зон — мандат есть, раздел PLAN не оформлен")


def _split_zone_paths(raw) -> list[str]:
    """Список путей через запятую — тот же формат, что несёт `zones:` части
    1 (01M1NKVPD2A79PQ6K0JVV1B2Q1) и строки `Пути:`/`Расширение зон
    разрешено:` ANSWER-1.md этой задачи. `raw` — `None`/пустая строка (поле
    не заполнено) даёт пустой список, не ошибку."""
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _touches_zone(path: str, zones: list[str]) -> bool:
    # «Путь == зона или начинается с неё» — та же формула префикса, что
    # `fsm_merge_gate._touches_protected_path` для `PROTECTED_PATHS`: зоны-
    # директории несут trailing `/` (COMMON_ZONES: "tests/"), зоны-файлы —
    # нет, сравниваются буквально.
    return any(path == z or path.startswith(z) for z in zones)


def _protected_paths_touched(files: list[str]) -> list[str]:
    """Файлы `files`, задевающие `config.PROTECTED_PATHS` — тот же приём
    префикса, что `_touches_zone` (формула требования 1 SPEC
    01M27JPEGCGMDDRX5A98QWJW0Z). Порядок — как во входном списке
    (обычно порядок `git diff --name-only`), без сортировки."""
    protected = list(config.PROTECTED_PATHS)
    return [f for f in files if _touches_zone(f, protected)]


def _protected_path_refusal_detail(paths: list[str]) -> str:
    """Именованный текст отказа (SPEC 01M27JPEGCGMDDRX5A98QWJW0Z,
    требование 4/AC-4) — дословно общий с `fsm_merge_gate` (тот же текст
    на гейте зон и на гейте мержа)."""
    return (f"защищённый путь {', '.join(paths)} — правит только "
           f"Оператор коммитом в main; предложи правку приложением к "
           f"PLAN (unified-дифф)")


def _plan_zones_extension_paths(plan_text: str) -> list[str] | None:
    """Пути раздела `## Расширение зон` PLAN.md (ANSWER-1.md, п.1: строка
    `Пути: <путь1>, <путь2>`). `None` — раздела нет вовсе, либо в нём нет
    строки `Пути:` — исключение AC-3 не применяется, дифф сверяется только
    с `zones`/`zones_extension`/`COMMON_ZONES` (обычный AC-1)."""
    body = guard.section_body(plan_text, "Расширение зон")
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("Пути:"):
            return _split_zone_paths(line[len("Пути:"):])
    return None


# Префикс сообщения автокоммита артефактов шага РОЛИ (`checkpoint.
# _commit_external_step_artifacts::own_commit_marker`) — общий для любой
# роли и обеих формулировок (обычной/с пометкой таймаута): роль встроена
# сразу после этого префикса, дальше в обоих случаях идёт «(автокоммит
# оркестратора...)». Единственный текстовый признак, которым коммит,
# заведомо НЕ бывший `cmd_answer` (тот коммитит отдельным сообщением
# `f"{task_id}: ANSWER-{n} — ответ Оператора"`, `orchestrator/answer.py`),
# узнаваем по подписи (REVIEW.md 01M1P9QCHPHSCEA6TK13PV85SP итерация 2,
# R2-F1).
_STEP_ARTIFACTS_COMMIT_PREFIX = "{task_id}: артефакты шага "


def _answer_commit_is_role_step_autocommit(branch: str, task_id: str,
                                           path: str) -> bool:
    """`True` — последний коммит `path` на артефактной ветке доказанно НЕ
    `cmd_answer` Оператора, а автокоммит шага роли (checkpoint.py) —
    именно так developer мог бы подложить себе поддельный
    `ANSWER-n.md` с маркером мандата в СВОЁМ ЖЕ шаге `in_dev` (R2-F1):
    `tasks/<id>/` роли — обычная директория на диске, автокоммит шага
    переносит в артефактную ветку любой файл без разбора по типу.

    Git не ответил (сбой команды, недостижимый sha) ИЛИ сообщение не
    совпало ни с одним известным маркером (лёгкая песочница без
    реального коммита — `tests/test_zones_gate.py`, докстринг модуля:
    «там git всегда отвечает» не про этот вызов) — `False`, не
    «доказанный автокоммит роли»: положительный сигнал здесь —
    ЕДИНСТВЕННОЕ основание отклонить мандат, симметрично тому, как
    `checkpoint._commit_external_step_artifacts` использует ТОТ ЖЕ
    признак (положительное совпадение с `own_commit_marker`) как
    единственное основание для удаления, а не наоборот."""
    res = gitcmd.git("log", "-1", "--format=%s", branch, "--", path)
    if res is None or res.returncode != 0:
        return False
    subject = res.stdout.strip()
    return subject.startswith(_STEP_ARTIFACTS_COMMIT_PREFIX.format(task_id=task_id))


def _answer_zones_mandate(branch: str, task_id: str) -> set[str]:
    """Объединение путей ВСЕХ маркеров `_ZONES_MANDATE_MARKER`, найденных в
    ЛЮБОМ `tasks/<id>/ANSWER-n.md` ветки задачи (ANSWER-1.md, п.2) — перебор
    файлов тем же приёмом, что `fsm._answer_file_count`.

    Файл, последний коммит которого — доказанный автокоммит шага роли
    (`_answer_commit_is_role_step_autocommit`), пропускается: это не
    `cmd_answer`, значит не мандат Оператора, независимо от текста
    внутри (R2-F1)."""
    paths = gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []
    mandate: set[str] = set()
    for p in paths:
        name = p.rsplit("/", 1)[-1]
        if not (name.startswith("ANSWER-") and name.endswith(".md")):
            continue
        if _answer_commit_is_role_step_autocommit(branch, task_id, p):
            continue
        text, _reason = gitcmd.show(branch, p)
        if text is None:
            continue
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(_ZONES_MANDATE_MARKER):
                mandate.update(_split_zone_paths(line[len(_ZONES_MANDATE_MARKER):]))
    return mandate


def _untracked_worktree_paths(task_id: str) -> list[str]:
    """Пути worktree self-target задачи с любым несохранённым изменением
    (`git status --porcelain=v1 --untracked-files=all`, SPEC
    01M290PVYG2VJK6442H5BAX9MA, AC-6) — untracked/staged/unstaged разом,
    независимо от того, попали ли они уже в коммит. Пустой список — git
    не ответил (гейт молча не расширяет список этим довеском — committed-
    дифф `_zones_gate` уже fail-closed на СВОИХ отказах выше) либо worktree
    и правда чист."""
    wt = workspace.path(task_id)
    status = gitcmd.in_repo(wt, "status", "--porcelain=v1",
                            "--untracked-files=all")
    if status is None or status.returncode != 0:
        return []
    paths = []
    for line in status.stdout.splitlines():
        if not line:
            continue
        rel = line[3:]
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        paths.append(rel)
    return paths


def _zones_gate(conn, task_id: str, t, branch: str,
                plan_text: str) -> GateRefusal | None:
    """Сверка диффа ветки задачи с зонами на `in_dev -> review` (SPEC
    01M1P9QCHPHSCEA6TK13PV85SP, AC-1/AC-2/AC-3/AC-6): дополнительное
    предусловие существующего перехода, по образцу `_capacity_gate`
    выше — не новое состояние FSM (AC-4), отказ ложится в тот же `store.
    journal` под действием `"переход отклонён: ..."`, что и остальные отказы
    этого перехода (AC-5, T078 подхватывает через `store.refusal_history`).

    Внешний (не self) target — гейт не проверяется: тот же довод, что
    `_capacity_gate` — `git diff` в `config.ROOT` не видит код внешнего
    target.

    Задача без ЗАЯВЛЕННОЙ зоны вовсе (`zones` и `zones_extension` оба
    пусты) — гейт не звонится (AC-7): `zones` обязателен только для SPEC
    `schema_version >= 4` (`guard.requires_zones`); задача старой версии
    (или тестовая фикстура, заведённая мимо гейта SPEC) ничего не
    заявляла — сравнивать дифф не с чем, и буквальное прочтение AC-1
    («вне заявленных путей») отказало бы ей на КАЖДОМ файле вне
    COMMON_ZONES, регрессия для всего, что не участвует в этой механике."""
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return None
    declared = _split_zone_paths(t["zones"]) + _split_zone_paths(t["zones_extension"])
    if not declared:
        return None
    # База сравнения — merge-base с origin/main или локальным main (tasks/
    # 01M1SG9T962WJJ31S282GWM0EN, AC-1/AC-2), не голый `config.MAIN_BRANCH`:
    # иначе коммит main, ещё не влитый в ветку задачи, выглядит правкой
    # самой задачи и ложно отказывает переход как «вне зон».
    base = gitcmd.diff_base(t["branch"])
    if base is None:
        detail = (f"гейт зон: git не ответил на определение базы сравнения "
                 f"(merge-base с origin/{config.MAIN_BRANCH} либо "
                 f"локальным {config.MAIN_BRANCH}) для ветки {t['branch']} "
                 f"— сверка с зонами невозможна")
        hint = (f"разберись, почему git не отвечает на merge-base "
               f"для {t['branch']}, и повтори artel.py advance {task_id}")
        return GateRefusal("переход отклонён: гейт зон", detail, hint)
    files = gitcmd.diff_names(base, t["branch"])
    if files is None:
        detail = (f"гейт зон: git не ответил на список файлов диффа "
                 f"(база {base}...{t['branch']}) — сверка с зонами "
                 f"невозможна")
        hint = (f"разберись, почему git не отвечает на diff "
               f"{base}...{t['branch']}, и повтори "
               f"artel.py advance {task_id}")
        return GateRefusal("переход отклонён: гейт зон", detail, hint)

    # Неотслеживаемые файлы worktree (SPEC 01M290PVYG2VJK6442H5BAX9MA,
    # AC-6): `diff_names` выше видит только committed-дифф — файл,
    # оставленный ролью нетрекенным (не закоммиченным и даже не
    # застейдженным), гейтом иначе не замечен вовсе. `git status
    # --porcelain` читает тем же путём, что и остальной модуль ниже
    # (fail-open на отказ git — этот довесок опционален, committed-дифф
    # выше уже fail-closed на СВОИХ отказах).
    #
    # Собственный каталог задачи (SPEC 01M2B6JNFD381MZT70CVB5NJQC,
    # требование 1/AC-1) исключается из этого довеска ДО мержа в `files`,
    # общим правилом с WIP-чекпоинтами (`checkpoint.task_dir_zone`):
    # `pull._materialize_and_run_plank` материализует
    # `tasks/<task_id>/acceptance_tests/` В worktree НА МЕСТЕ, оставляя
    # его неотслеживаемым между началом и концом подтяжки main — без
    # этого исключения довесок видел бы саму планку приёмки как путь вне
    # зон и отказывал бы переходу на ровном месте (12.09, четыре ложных
    # отказа задач волны 3, docs/backlog.md строка П1). Committed-дифф
    # (`out_of_zone` ниже, через `zones` без каталога задачи) этим
    # исключением не затронут — AC-2 (посторонний код-файл вне
    # `tasks/<task_id>/`) сохраняется байт-в-байт.
    untracked = _untracked_worktree_paths(task_id)
    if untracked:
        task_zone = checkpoint.task_dir_zone(task_id)
        untracked = [p for p in untracked if not _touches_zone(p, [task_zone])]
        files = files + [p for p in untracked if p not in files]

    # Защищённые пути (SPEC 01M27JPEGCGMDDRX5A98QWJW0Z, требования 2-3,
    # AC-2/AC-3) — отказывает БЕЗУСЛОВНО, раньше проверки zones/
    # расширения: заявленность пути в zones (AC-2) или подкреплённый
    # мандатом Оператора раздел «## Расширение зон» PLAN.md (AC-3,
    # обычное исключение ниже) защищённые пути не покрывают — мандат на
    # расширение зон не мандат на правку защищённого пути (факт 11.09,
    # «Контекст» SPEC).
    protected = _protected_paths_touched(files)
    if protected:
        detail = _protected_path_refusal_detail(protected)
        hint = (f"предложи правку unified-диффом в приложении к PLAN.md — "
               f"её применяет Оператор, не роль; повтори "
               f"artel.py advance {task_id} без правки защищённого пути в "
               f"диффе")
        return GateRefusal("переход отклонён: защищённый путь", detail, hint)

    zones = declared + list(config.COMMON_ZONES)
    out_of_zone = [f for f in files if not _touches_zone(f, zones)]
    if not out_of_zone:
        return None

    # Исключение AC-3: раздел «## Расширение зон» PLAN.md, подкреплённый
    # мандатом Оператора на ТЕ ЖЕ пути в ANSWER-*.md (ANSWER-1.md, п.1-2).
    # Мандат читается независимо от наличия раздела: он нужен и ниже, для
    # различения причины отказа (SPEC 01M2XFSNVGWA2VX5XFEYR93Y4Z,
    # требование 1) — до этой задачи «мандат есть, раздела нет» было
    # неотличимо от обычного отказа, и `auto` останавливался, не дав
    # роли шага на оформление раздела (инцидент 13.09, задача 01M2CYQR03).
    extension_paths = _plan_zones_extension_paths(plan_text)
    mandate = _answer_zones_mandate(branch, task_id)
    if extension_paths is not None:
        uncovered_by_mandate = [p for p in extension_paths if p not in mandate]
        if not uncovered_by_mandate:
            still_out = [f for f in out_of_zone
                        if not _touches_zone(f, zones + extension_paths)]
            if not still_out:
                merged = sorted(set(_split_zone_paths(t["zones_extension"])
                                    + extension_paths))
                store.update_task(conn, task_id,
                                  zones_extension=",".join(merged))
                return None
            out_of_zone = still_out

    # Источник базы в сообщении (требование 4/AC-6) — Оператор видит, с чем
    # реально сравнивали, не только литерал diff-диапазона.
    source = gitcmd.diff_base_source(t["branch"])
    detail = (f"дифф трогает файлы вне заявленных zones и COMMON_ZONES "
             f"(база сравнения {base} от {source}): "
             f"{', '.join(out_of_zone)}")

    # Мандат Оператора покрывает ВСЕ оставшиеся пути вне зон (та же
    # формула префикса, что у исключения AC-3 выше), не хватает только
    # раздела PLAN.md — отказ именуется отдельно (требование 1/AC-1):
    # чинить его будет роль, не Оператор. Покрыты не все пути или мандата
    # нет вовсе — прежний отказ ниже, байт-в-байт (требование 2/AC-2).
    mandate_paths = sorted(mandate)
    if mandate_paths and all(_touches_zone(f, mandate_paths) for f in out_of_zone):
        if extension_paths is None:
            plan_state = "отсутствует"
        else:
            plan_state = (f"не совпадает с мандатом (в разделе: "
                          f"{', '.join(extension_paths) or '—'})")
        detail = (f"{detail} — все они покрыты мандатом Оператора "
                  f"«{_ZONES_MANDATE_MARKER} {', '.join(mandate_paths)}», "
                  f"но раздел «## Расширение зон» PLAN.md {plan_state}")
        hint = (f"оформи раздел «## Расширение зон» в PLAN.md: строка "
                f"«Пути: {', '.join(mandate_paths)}» и обоснование, затем "
                f"повтори artel.py advance {task_id}")
        return GateRefusal(ZONES_MANDATE_WITHOUT_PLAN_REFUSAL_ACTION,
                           detail, hint)

    hint = (f"сократи дифф до заявленных zones либо оформи раздел "
           f"«## Расширение зон» в PLAN.md с обоснованием и мандатом "
           f"Оператора («{_ZONES_MANDATE_MARKER} <пути>» в ANSWER-n.md), и "
           f"повтори artel.py advance {task_id}")
    return GateRefusal("переход отклонён: гейт зон", detail, hint)


def _zones_gate_refuses(conn, task_id: str, t, branch: str,
                        plan_text: str) -> bool:
    """Сохранённая публичная обёртка (тесты `tests/test_zones_gate.py`
    зовут её напрямую и читают журнал/stdout) — тот же единственный гейт
    `_zones_gate`, применённый через каркас `_run_gates`."""
    return _run_gates(conn, task_id,
                      [lambda: _zones_gate(conn, task_id, t, branch, plan_text)])
