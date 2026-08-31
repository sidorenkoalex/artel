"""Бриф роли одним документом: SPEC/TZ + карта кодовой базы + конвенции
(tasks/T028).

Компоненты клеятся в текст промпта, а не выдаются инструкцией «прочитай
файл X сам» (SPEC T028, требование 2) — роль получает контекст без
повторных чтений репозитория. Свежесть карты — ленивая сверка при сборке
брифа тем же способом, каким уже пользуется CI-джоба `codebase-map`
(`.github/workflows/ci.yml`, tasks/T027): диапазон `built_at_sha..HEAD`
по путям `orchestrator/*.py`, `scripts/*.py`, `tests/*.py`. Расхождение —
регенерация до сборки; сбой регенерации или самой сверки — алерт и честная
пометка в тексте, не молчаливая выдача стухшей карты (ADR-0003 §3б,
«никогда молчаливое доверие»).
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

from . import alerts, config, gitcmd, store

MAP_REL = "docs/codebase-map.md"
CONVENTIONS_REL = "CLAUDE.md"
# Те же три glob'а, что и у CI-джобы codebase-map — общий способ сверки
# свежести карты (SPEC T028, требование 5).
MAP_WATCH_GLOBS = ("orchestrator/*.py", "scripts/*.py", "tests/*.py")
HEADER = "--- БРИФ РОЛИ ---"


def component_hash(text: str) -> str:
    """sha256 содержимого компонента: журнал остаётся верным содержимому,
    а не статической меткой (SPEC T028, требование 8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _built_at_sha(map_text: str) -> str:
    match = re.search(r"^built_at_sha:\s*(\S+)", map_text, re.M)
    return match.group(1) if match else ""


def _stale_paths(base_sha: str) -> list[str] | None:
    """Пути `orchestrator/scripts/tests`, изменившиеся между `base_sha` и
    HEAD; `None` — git не ответил на саму сверку (тот же вырожденный
    случай, что уже кодирует `gitcmd.diff_paths`).

    Не путать с пустым списком: пустой список — сверка прошла и
    расхождений нет (требование 6). `None` — сверка не прошла, и молчаливо
    трактовать её как «расхождений нет» запрещает ADR-0003 §3б ровно тем
    же способом, что и отказ регенерации (требование 7) — вызывающий код
    обязан завести тот же алерт и пометку, не тихо отдать карту как
    свежую (REVIEW T028 итерация 1, замечание major).
    """
    res = gitcmd.git("diff", "--name-only", base_sha, "HEAD", "--",
                     *MAP_WATCH_GLOBS)
    if res.returncode != 0:
        return None
    return [p for p in res.stdout.splitlines() if p]


def _regenerate_map(conn, task_id: str) -> tuple[str | None, str]:
    """Перегон `scripts/codebase_map.py` в корне пульта — тот же генератор,
    которым уже пользуется CI-джоба `codebase-map` (tasks/T027).

    Пишет файл на диск в `config.ROOT` (контракт генератора, tasks/T027) —
    в главную копию пульта; с worktree-нормой (T045) это НЕ cwd роли
    (тот — worktree задачи): текст карты читается в память для брифа,
    а правка в главной копии — побочный след генератора, не изменение
    для агента. Оставлять её незакоммиченной всё равно нельзя (грязная
    главная копия — ложные срабатывания сверок целостности; REVIEW T028
    итерация 1, blocker) — поэтому сразу после чтения регенерированного
    текста в память рабочее дерево возвращается к закоммиченному
    состоянию (`git checkout --`), и это происходит здесь же, до старта
    агента (`runner.cmd_run` зовёт сборку брифа раньше `run_agent_once`).
    Откат не удался — использованный текст всё равно возвращается (он уже
    прочитан), но заводится отдельный алерт: тихо оставить рабочее дерево
    грязным запрещает тот же принцип, что и молчаливую выдачу стухшей
    карты.

    Возвращает (текст_карты, причина_отказа) — текст `None` при отказе
    самой регенерации.
    """
    regen = subprocess.run(["python3", "scripts/codebase_map.py"],
                           cwd=config.ROOT, capture_output=True, text=True)
    if regen.returncode != 0:
        reason = regen.stderr.strip()[:200] or f"код возврата {regen.returncode}"
        return None, reason
    text = (config.ROOT / MAP_REL).read_text(encoding="utf-8")
    restore = gitcmd.git("checkout", "--", MAP_REL)
    if restore.returncode != 0:
        alerts.raise_alert(
            conn, store.task_target(conn, task_id), "incident",
            "brief.codebase_map_restore",
            f"{MAP_REL} регенерирован в рабочем дереве {config.ROOT}, но "
            f"откат правки (git checkout --) не удался — файл остаётся "
            f"незакоммиченным в общем рабочем дереве пульта")
    return text, ""


def _mark_stale(conn, task_id: str, text: str, base_sha: str, message: str,
                paths: list[str]) -> str:
    alerts.raise_alert(conn, store.task_target(conn, task_id), "incident",
                       "brief.codebase_map", message)
    note = (
        f"[КАРТА НЕАКТУАЛЬНА: {message}. Использованный built_at_sha="
        f"{base_sha or '—'}. Пути расхождения: {', '.join(paths)}.]\n\n")
    return note + text


def fresh_map_text(conn, task_id: str) -> str:
    """Текст `docs/codebase-map.md`, свежей или честно помеченной стухшей.

    Расхождение по `MAP_WATCH_GLOBS` в диапазоне `built_at_sha..HEAD` —
    регенерация до сборки брифа (требование 5, 6, AC-5, AC-6); сбой
    регенерации, как и сбой самой сверки свежести, — алерт
    (`alerts.raise_alert`, дедуп по (target, kind, source, message) уже
    встроен) и явная пометка в начале текста с использованным
    `built_at_sha` и путями расхождения, карта — прежняя, непереписанная
    версия (требование 7, AC-7).
    """
    text = (config.ROOT / MAP_REL).read_text(encoding="utf-8")
    base_sha = _built_at_sha(text)
    stale = _stale_paths(base_sha)
    if stale is None:
        return _mark_stale(
            conn, task_id, text, base_sha,
            "сверка свежести карты не удалась: git не ответил "
            "(diff --name-only)", ["неизвестно — git не ответил"])
    if not stale:
        return text
    regenerated, reason = _regenerate_map(conn, task_id)
    if regenerated is not None:
        return regenerated
    message = f"регенерация {MAP_REL} не удалась: {reason}"
    return _mark_stale(conn, task_id, text, base_sha, message, stale)


def _journal_component(conn, task_id: str, role: str, label: str,
                       text: str) -> str:
    """Хэш компонента — в журнал шага; собранный кусок текста — брифу."""
    store.journal(conn, task_id, role, "бриф: компонент",
                  f"{label}: sha256={component_hash(text)}")
    return f"### {label}\n\n{text.strip()}\n"


def _developer_spec_text(conn, task_id: str, branch: str, foreign: bool) -> str:
    """SPEC.md задачи — с ВЕТКИ задачи, если рабочее дерево пульта точно
    стоит не на ней (SPEC T031, AC-2), иначе рабочая копия, как до T031.

    `foreign` — уже посчитанный `gitcmd.on_foreign_branch(branch)`
    вызывающим кодом (SPEC T075): бриф читает несколько файлов задачи
    (SPEC/QUESTIONS/ANSWER) одним и тем же вопросом «на чужой ли ветке
    рабочее дерево» — второй git-вызов того же вопроса лишний.

    Голый `FileNotFoundError`-трейсбек на чужом чекауте (журнал T030,
    ~17:35 25.08.2026) заменяет именованный отказ — обеим ветвям чтения,
    не только git-пути: своя ветка ещё не создана ролью или git не
    ответил на вопрос «какая ветка» — тот же вырожденный случай, что и
    везде в T031, но файла на диске тогда тоже может не быть.
    """
    spec_rel = f"tasks/{task_id}/SPEC.md"
    if foreign:
        text, reason = gitcmd.show(branch, spec_rel)
        if text is None:
            sys.exit(f"[{task_id}] бриф не собран: {spec_rel} ветки "
                     f"{branch} не прочитан ({reason}) — дерево не на "
                     f"ветке задачи")
        return text
    try:
        return (config.ROOT / spec_rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit(f"[{task_id}] бриф не собран: {spec_rel} не прочитан "
                 f"({exc}) — дерево не на ветке задачи (ветка "
                 f"{branch or '—'} ещё не создана в git)")


def _branch_or_disk_text(task_id: str, branch: str, rel: str,
                         foreign: bool) -> str | None:
    """Текст `tasks/<id>/<rel>` — с ветки задачи, если рабочее дерево на
    чужой ветке (SPEC T031/T047, тот же приём, что `_developer_spec_text`),
    иначе с диска. `None` — файла нет ни там, ни там: отсутствие ANSWER/
    QUESTIONS — легитимное «эскалации не было», не отказ сборки брифа
    (в отличие от SPEC.md, чтение которого обязательно)."""
    if foreign:
        text, _ = gitcmd.show(branch, f"tasks/{task_id}/{rel}")
        return text
    path = config.TASKS / task_id / rel
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _latest_answer_rel(task_id: str, branch: str, foreign: bool) -> str | None:
    """Имя `ANSWER-n.md` с наибольшим `n` — с ветки или с диска; `None` —
    ANSWER-файлов у задачи ещё нет."""
    if foreign:
        paths = gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []
        names = [Path(p).name for p in paths]
    else:
        names = [p.name for p in (config.TASKS / task_id).glob("ANSWER-*.md")]
    numbers = []
    for name in names:
        if name.startswith("ANSWER-") and name.endswith(".md"):
            suffix = name[len("ANSWER-"):-len(".md")]
            if suffix.isdigit():
                numbers.append(int(suffix))
    if not numbers:
        return None
    return f"ANSWER-{max(numbers)}.md"


def _answer_component(conn, task_id: str, role: str, branch: str,
                      foreign: bool) -> str:
    """Добавка брифа с текстом последнего ANSWER-n.md задачи (SPEC T075,
    AC-6) — пустая строка, если ответов ещё нет: канал не обязан
    заполнять бриф, когда эскалации не было."""
    rel = _latest_answer_rel(task_id, branch, foreign)
    if rel is None:
        return ""
    text = _branch_or_disk_text(task_id, branch, rel, foreign)
    if text is None:
        return ""
    return _journal_component(conn, task_id, role, f"tasks/{task_id}/{rel}", text)


def _questions_component(conn, task_id: str, role: str, branch: str,
                         foreign: bool) -> str:
    """Добавка брифа с текстом QUESTIONS.md задачи (SPEC T075, AC-6) —
    пустая строка, если батча вопросов не было."""
    text = _branch_or_disk_text(task_id, branch, "QUESTIONS.md", foreign)
    if text is None:
        return ""
    return _journal_component(conn, task_id, role,
                              f"tasks/{task_id}/QUESTIONS.md", text)


def developer_brief(conn, task_id: str) -> str:
    """Бриф роли developer: SPEC задачи + карта + конвенции проекта одним
    документом (требования 1, 3, 4, 8); ANSWER-n.md последней эскалации
    — если она была (SPEC T075, AC-6: ответ обязан дойти до роли, а не
    только существовать в ветке)."""
    branch = store.task_branch(conn, task_id)
    foreign = gitcmd.on_foreign_branch(branch)
    spec_text = _developer_spec_text(conn, task_id, branch, foreign)
    map_text = fresh_map_text(conn, task_id)
    conventions_text = (config.ROOT / CONVENTIONS_REL).read_text(
        encoding="utf-8")
    parts = [
        _journal_component(conn, task_id, "developer",
                           f"tasks/{task_id}/SPEC.md", spec_text),
        _journal_component(conn, task_id, "developer", MAP_REL, map_text),
        _journal_component(conn, task_id, "developer", CONVENTIONS_REL,
                           conventions_text),
    ]
    answer_part = _answer_component(conn, task_id, "developer", branch, foreign)
    if answer_part:
        parts.append(answer_part)
    return f"{HEADER}\n\n" + "\n".join(parts)


def analyst_map_component(conn, task_id: str) -> str:
    """Добавка к входу analyst: карта тем же механизмом, что у developer
    (требование 9) — TZ.md остаётся прежним, отдельно не читаемым здесь
    входом, скилы и остальной вход роли не меняются. QUESTIONS.md и
    ANSWER-n.md последнего батча — если он был (SPEC T075, AC-6): роль
    видит и свой вопрос, и ответ на него, не только ответ без контекста."""
    branch = store.task_branch(conn, task_id)
    foreign = gitcmd.on_foreign_branch(branch)
    map_text = fresh_map_text(conn, task_id)
    parts = [_journal_component(conn, task_id, "analyst", MAP_REL, map_text)]
    q_part = _questions_component(conn, task_id, "analyst", branch, foreign)
    if q_part:
        parts.append(q_part)
    a_part = _answer_component(conn, task_id, "analyst", branch, foreign)
    if a_part:
        parts.append(a_part)
    return f"{HEADER}\n\n" + "\n".join(parts)


def test_author_answer_component(conn, task_id: str) -> str | None:
    """Промпт-добавка роли test_author: только ANSWER-n.md последней
    эскалации (SPEC T075, AC-6) — эта роль не получает SPEC/карту/
    конвенции отдельным брифом (`runner.py`, ветка `test_author`) ни до,
    ни после этой задачи, добавляется только новый минимум. `None` —
    ответов ещё нет, промпт шага остаётся прежним (без добавки)."""
    branch = store.task_branch(conn, task_id)
    foreign = gitcmd.on_foreign_branch(branch)
    part = _answer_component(conn, task_id, "test_author", branch, foreign)
    if not part:
        return None
    return f"{HEADER}\n\n{part}"
