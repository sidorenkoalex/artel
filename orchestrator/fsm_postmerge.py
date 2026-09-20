"""Побочные эффекты merge_gate после успешного merge: карта кодовой базы
(SPEC T042) и RETRO (SPEC T043). Перенесено из orchestrator/fsm.py без
изменения поведения (T091, декомпозиция диспетчеров fsm/runner).

Зовётся ПОСЛЕ успешного merge, ДО push (orchestrator/fsm_merge_gate.py) —
что бы тут ни случилось, `git push` вызывающего кода выполняется в любом
случае: обе функции никогда не бросают исключение и не делают `sys.exit`,
любой провал уходит в свой incident-алерт.

`repo` (A7, Stage0, AC-9): корень, в котором физически читаются/пишутся
файлы и делаются git-коммиты — по умолчанию `None` (существующее
поведение байт-в-байт: `config.ROOT`, `gitcmd.git` без `-C`). Плотницкий
merge (`orchestrator/fsm_merge_gate.py::_cmd_approve_merge_gate`)
передаёт свой scratch-worktree — рабочее дерево и HEAD `config.ROOT` не
имеют права двигаться этим переходом (AC-8/AC-9).
"""
import json
import subprocess

from scripts import codebase_map

from . import alerts, config, gitcmd, retro, store

# Регенерация/коммит карты кодовой базы на merge_gate (SPEC T042) — своя
# копия константы, тем же приёмом, что уже применяют orchestrator/brief.py
# и orchestrator/fsm.py (branch freshness, docs/codebase-map.md там нужен
# по другому поводу — авторазрешение конфликта подтяжки).
MAP_REL = "docs/codebase-map.md"

# Запись журнала «наблюдатель роста карты» на каждом успешном мерже
# (01M1RFVWV6WWTXRC5F40K61632, требования 2, AC-5..AC-7) — читает
# `orchestrator/doctor.py::check_map_growth`.
MAP_SIZE_ACTION = "карта: размер"


def _journal_map_size(conn, task_id: str, text: str, repo) -> None:
    """detail = `map_stats(text)` + sha HEAD ПОСЛЕ завершения git-операций
    этого вызова (новый коммит карты, если он был сделан; иначе — тот же
    sha, что стоял до вызова, AC-5)."""
    stats = codebase_map.map_stats(text)
    stats["sha"] = gitcmd.head_sha(repo)
    detail = json.dumps(stats, ensure_ascii=False, separators=(",", ":"))
    store.journal(conn, task_id, "orchestrator", MAP_SIZE_ACTION, detail)


def _map_content_without_sha(text: str) -> str:
    """Текст карты без строки `built_at_sha:` — сверка содержимым, тем же
    принципом, что и CI-джоб `codebase-map` (`.github/workflows/ci.yml`,
    ред. Оператора 26.08, SPEC T042 требование 2): `built_at_sha` меняется
    при каждой регенерации и сам по себе не повод коммитить.
    """
    return "\n".join(line for line in text.splitlines()
                     if not line.startswith("built_at_sha:"))


def _map_regen_incident(conn, task_id: str, message: str) -> None:
    """Провал шага карты — журнал и incident-алерт, не отказ merge
    (SPEC T042, требование 5)."""
    store.journal(conn, task_id, "orchestrator",
                  "регенерация карты FAILED", message)
    alerts.raise_alert(conn, store.task_target(conn, task_id), "incident",
                       "fsm.map_regen", message)


def _git(repo, *args: str):
    return gitcmd.in_repo(repo, *args) if repo is not None else gitcmd.git(*args)


def _regenerate_and_commit_map(conn, task_id: str, repo=None) -> None:
    """Регенерация `docs/codebase-map.md` после merge и коммит отдельным
    коммитом, если карта содержательно изменилась (SPEC T042, требования
    1-3); без содержательных отличий — откат правки, коммита нет.

    Зовётся ПОСЛЕ успешного merge, ДО push (требование 1, 4): что бы тут
    ни случилось, `git push` в вызывающем коде выполняется в любом случае
    (требование 5) — эта функция никогда не бросает исключение и не
    делает `sys.exit`, любой провал уходит в `_map_regen_incident`.
    """
    root = repo if repo is not None else config.ROOT
    map_path = root / MAP_REL
    try:
        committed = map_path.read_text(encoding="utf-8")
    except OSError as exc:
        _map_regen_incident(conn, task_id, f"{MAP_REL} не прочитан: {exc}")
        return
    # Не git-вызов (требование 6, AC-4) — прямой subprocess.run, тем же
    # приёмом, что brief._regenerate_map.
    try:
        regen = subprocess.run(["python3", "scripts/codebase_map.py"],
                               cwd=root, capture_output=True, text=True)
    except OSError as exc:
        _map_regen_incident(conn, task_id,
                            f"регенерация {MAP_REL} не удалась: {exc}")
        return
    if regen.returncode != 0:
        reason = regen.stderr.strip()[:200] or f"код возврата {regen.returncode}"
        _map_regen_incident(conn, task_id,
                            f"регенерация {MAP_REL} не удалась: {reason}")
        return
    try:
        regenerated = map_path.read_text(encoding="utf-8")
    except OSError as exc:
        _map_regen_incident(conn, task_id, f"{MAP_REL} не прочитан: {exc}")
        return
    if _map_content_without_sha(regenerated) == _map_content_without_sha(committed):
        restore = _git(repo, "checkout", "--", MAP_REL)
        if restore.returncode != 0:
            _map_regen_incident(
                conn, task_id,
                f"откат {MAP_REL} без содержательных отличий не удался: "
                f"{restore.stderr.strip()[:200]}")
            return
        _journal_map_size(conn, task_id, committed, repo)
        return
    added = _git(repo, "add", MAP_REL)
    if added.returncode != 0:
        _map_regen_incident(conn, task_id,
                            f"git add {MAP_REL} не удался: "
                            f"{added.stderr.strip()[:200]}")
        return
    commit = _git(
        repo, "commit", "-m",
        f"карта кодовой базы: регенерация после merge {task_id}")
    if commit.returncode != 0:
        _map_regen_incident(conn, task_id,
                            f"коммит {MAP_REL} не удался: "
                            f"{commit.stderr.strip()[:200]}")
        return
    _journal_map_size(conn, task_id, regenerated, repo)


# Дайджест задачи в main на переходе в done/killed (SPEC T043). killed-RETRO
# доставляется не самим `kill` (решение (d) Оператора, tasks/T043/TZ.md —
# `orchestrator/cleanup.py` не трогается, инвариант 15 цел буквально), а
# ближайшим `merge_gate` ЛЮБОЙ задачи, тем же приёмом, что карта T042.


def _retro_incident(conn, task_id: str, message: str) -> None:
    """Провал шага RETRO — журнал и incident-алерт, не отказ merge (SPEC
    T043, требование 9), тем же приёмом, что `_map_regen_incident`."""
    store.journal(conn, task_id, "orchestrator", "RETRO FAILED", message)
    alerts.raise_alert(conn, store.task_target(conn, task_id), "incident",
                       "fsm.retro", message)


def _write_and_stage_retro(conn, task_id: str, text: str, repo=None) -> bool:
    """True — файл записан и добавлен в индекс git; False — провал
    (инцидент уже заведён)."""
    path = retro.retro_path(task_id, repo)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        _retro_incident(conn, task_id, f"{path} не записан: {exc}")
        return False
    added = _git(repo, "add", retro.retro_rel_path(task_id))
    if added.returncode != 0:
        _retro_incident(conn, task_id,
                        f"git add {retro.retro_rel_path(task_id)} не удался: "
                        f"{added.stderr.strip()[:200]}")
        return False
    return True


def _commit_retro(conn, task_id: str, message: str, repo=None) -> None:
    commit = _git(repo, "commit", "-m", message)
    if commit.returncode != 0:
        _retro_incident(conn, task_id,
                        f"коммит RETRO не удался: "
                        f"{commit.stderr.strip()[:200]}")


# Строка RETRO о приложениях Оператора (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF,
# требование 6): дописывается здесь, а не в `retro.build_done` —
# `orchestrator/retro.py` вне зон той задачи, а перечень применённых путей
# знает только цикл мержа.
APPENDICES_RETRO_PREFIX = "Приложения Оператора применены:"


def _with_appendices_line(text: str, applied_appendices) -> str:
    """Текст RETRO со строкой перечня применённых приложений в конце.
    Приложений не было — текст возвращается байт-в-байт: RETRO задач без
    приложений не имеет права отличаться от сегодняшнего ни одним
    символом."""
    if not applied_appendices:
        return text
    return (f"{text}\n{APPENDICES_RETRO_PREFIX} "
            f"{', '.join(applied_appendices)}\n")


def _generate_and_commit_retro(conn, task_id: str, merge_sha: str,
                               repo=None, applied_appendices=None) -> None:
    """done-RETRO мержащейся задачи + подбор killed-долгов (SPEC T043,
    требования 1, 2, 5-8) — коммит отдельный на каждую задачу (провал
    одной не должен мешать журналировать/чинить остальные по отдельности).

    Зовётся ПОСЛЕ успешного merge, ДО push (тем же местом, что
    `_regenerate_and_commit_map`): что бы тут ни случилось, `push` в
    вызывающем коде выполняется в любом случае (требование 9) — генерация
    контента обёрнута широким `except Exception` умышленно (не только
    `OSError`, как у карты): в отличие от регенерации карты, здесь
    несколько независимых источников чтения (журнал БД, SPEC, разбор
    acceptance_tests/), и ни один сбой любого из них не имеет права
    отменить сам переход.

    `applied_appendices` (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF, требование 6) —
    пути приложений PLAN, применённых этим же мержем: строка с их
    перечнем дописывается к done-RETRO мержащейся задачи (долги killed
    ниже её не несут — приложения принадлежат ЭТОЙ задаче).
    """
    try:
        text = _with_appendices_line(retro.build_done(conn, task_id, merge_sha),
                                     applied_appendices)
    except Exception as exc:  # noqa: BLE001 — см. докстринг: провал не критичен
        _retro_incident(conn, task_id, f"генерация RETRO не удалась: {exc}")
    else:
        if _write_and_stage_retro(conn, task_id, text, repo):
            _commit_retro(conn, task_id, f"{task_id}: RETRO задачи", repo)

    debts = [t["id"] for t in store.all_tasks(conn)
            if t["state"] == "killed"
            and not retro.retro_path(t["id"], repo).exists()]
    for debt_id in debts:
        try:
            debt_text = retro.build_killed(conn, debt_id)
        except Exception as exc:  # noqa: BLE001 — см. докстринг выше
            _retro_incident(conn, debt_id,
                            f"генерация killed-RETRO {debt_id} не удалась: {exc}")
            continue
        if _write_and_stage_retro(conn, debt_id, debt_text, repo):
            _commit_retro(conn, debt_id,
                          f"{task_id}: killed-RETRO долга {debt_id}", repo)
