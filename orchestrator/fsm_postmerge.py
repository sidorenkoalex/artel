"""Побочные эффекты merge_gate после успешного merge: карта кодовой базы
(SPEC T042) и строка приложений PLAN для RETRO. Перенесено из
orchestrator/fsm.py без изменения поведения (T091, декомпозиция
диспетчеров fsm/runner). RETRO в main мерж больше не коммитит (ADR-0021
п.4, SPEC 01M4M67SGNEYMN9F1C7XVX24XE): оно живёт только в коммите закрытия
`refs/artifacts/<id>` (`orchestrator/snapshot.py`).

Карта зовётся ПОСЛЕ успешного merge, ДО push (orchestrator/fsm_merge_gate.py)
— что бы тут ни случилось, `git push` вызывающего кода выполняется в любом
случае: шаг никогда не бросает исключение и не делает `sys.exit`, любой
провал уходит в свой incident-алерт.

`repo` (A7, Stage0, AC-9): корень, в котором физически читаются/пишутся
файлы и делаются git-коммиты — по умолчанию `None` (существующее
поведение байт-в-байт: `config.ROOT`, `gitcmd.git` без `-C`). Плотницкий
merge (`orchestrator/fsm_merge_gate.py::_cmd_approve_merge_gate`)
передаёт свой scratch-worktree — рабочее дерево и HEAD `config.ROOT` не
имеют права двигаться этим переходом (AC-8/AC-9).
"""
import json
import subprocess
import sys

from scripts import codebase_map

from . import alerts, config, gitcmd, store

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
    """git в рабочей копии мержа `repo` — временной рабочей копии клона
    проекта (SPEC 01M42PENCS26D0656X8FR7DFA7, требование 2); `None` —
    корень пульта (`config.ROOT`), прежний адрес вызова без репозитория."""
    return gitcmd.in_repo(repo if repo is not None else config.ROOT, *args)


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
    # приёмом, что brief._regenerate_map. Интерпретатор — процесса пульта, не
    # `python3` из PATH (SPEC 01M4JMMH70NWJG72G422BFY1KC, требование 1): тот
    # может оказаться ниже требуемого и упасть на синтаксисе генератора.
    try:
        regen = subprocess.run([sys.executable, "scripts/codebase_map.py"],
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


# Строка RETRO о приложениях Оператора (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF,
# требование 6): дописывается не в `retro.build_done`, а поверх него —
# перечень применённых путей знает только цикл мержа. С ADR-0021 п.4 её
# дописывает к RETRO коммит закрытия (`orchestrator/snapshot.py`).
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
