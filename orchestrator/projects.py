"""Каталог проекта в .artel/: структура target'а (ADR-0003 3д).

Единица управления — проект: подключение, отключение и восстановление
это операции над одним каталогом. Здесь заводится сам каталог со всем,
что у проекта есть: эфемерный клон целевого (workspace), первичка
артефактов (tasks), производные знания (knowledge) и логи прогонов.

Своего git-репозитория у каталога проекта нет: репозиторий фиксации
области проекта (ADR-0003 п.15) упразднён (ADR-0021 п.2, этап 1, часть
б2) — зафиксированное состояние документов задачи — коммит ссылки
`refs/artifacts/<id>` в репозитории задачи (`artifact_branch.task_repo`).
"""
import sys
from pathlib import Path

from . import config, reference_cache, repo_context, store, targets, workspace

REFERENCE_LABEL = "справочник ядра"
NO_JOURNAL = "журнал недоступен — сначала init"
REFERENCE_USAGE = "reference <проект> [--sha <sha>]"


def project_dir(name: str) -> Path:
    return config.PROJECTS / name


def init_project(name: str) -> list[str]:
    """Создаёт каталоги target'а; список строк — что вышло с каждым.

    Идемпотентность — свойство самой операции, а не проверки «уже есть»:
    каталог создаётся с exist_ok, поэтому повторный вызов ничего не
    ломает и после подключения, и после ручного удаления одного из
    подкаталогов (недостающее доводится, существующее не трогается).
    """
    notes = []
    for sub in config.PROJECT_DIRS:
        path = project_dir(name) / sub
        existed = path.is_dir()
        path.mkdir(parents=True, exist_ok=True)
        notes.append(f"{'уже был' if existed else 'создан'}: {path}")
    return notes


def cmd_target_init(name: str) -> None:
    """Подключение target'а: каталог проекта по декларации targets.yaml и
    клон проекта (SPEC 01M4RRW7FT1EE77EY9Y462AZKC, требование 6).

    Имя сверяется с декларацией ДО каталогов: необъявленный проект не
    оставляет каталога-сироты. Клон — тем же `workspace.ensure_clone`, что
    у `new`: существующий не трогается; неудача — отказ с причиной, а
    созданные каталоги остаются (повтор `target-init` их доведёт)."""
    try:
        entry = targets.target(name)
    except targets.TargetsError as exc:
        sys.exit(f"target-init: {exc}")

    try:
        notes = init_project(name)
    except OSError as exc:
        sys.exit(f"target-init: каталог проекта {name} не создан: {exc}")

    print(f"target {name}: forge {entry['forge']}, база {entry['base']}, "
          f"гейт мержа {entry['merge_gate']}")
    for note in notes:
        print(f"  {note}")

    clone, error = workspace.ensure_clone(name)
    if error is not None:
        sys.exit(f"target-init: {error}")
    print(f"  клон проекта: {clone}")
    for line in _target_init_reference(name, entry, clone):
        print(f"  {line}")


def _target_init_reference(name: str, entry: dict, clone: Path) -> list[str]:
    """Справочник ядра после клона (SPEC 01M4TVBT9ZCRQDY669QV3S95MA,
    требование 5): строки сводки. Сбой сборки печатается причиной и
    `target-init` не отменяет — каталоги и клон остаются."""
    setting = entry.get(targets.REFERENCE_FIELD)
    if setting is None:
        return [f"{REFERENCE_LABEL}: выключен (нет поля {targets.REFERENCE_FIELD})"]
    if not store.db_usable():
        return [f"{REFERENCE_LABEL}: {NO_JOURNAL}"]
    sha, why = reference_cache.branch_commit(clone, entry["base"])
    if sha is None:
        return [f"{REFERENCE_LABEL}: не собран — коммит базы {entry['base']} "
                f"не узнан: {why}"]
    try:
        result = reference_cache.get_reference_for_target(
            store.db(), name, reason=reference_cache.REFERENCE_REASON, sha=sha)
    except Exception as exc:  # noqa: BLE001 — сбой сборки не отменяет target-init
        return [f"{REFERENCE_LABEL}: не собран — {type(exc).__name__}: {exc}"]
    return reference_summary(name, setting, sha, result)


def reference_summary(name: str, setting: dict | None, sha: str,
                      result: reference_cache.Reference) -> list[str]:
    """Сводка справочника ядра: состояние, sha, размер, предел, доля,
    порог с источником и вывод по формулам брифа (`brief.py`: размер —
    байты UTF-8 полного текста кэша, «больше предела» при `size > limit`,
    предупреждение при `size * 10 > limit * 9`)."""
    head = f"{REFERENCE_LABEL} {name}: {result.state}"
    if result.state == "off":
        return [f"{head} (нет поля {targets.REFERENCE_FIELD})"]
    lines = [f"{head} — {result.note}" if result.note else head, f"sha: {sha}"]
    if setting is not None:
        threshold, source = reference_cache.min_uses(setting)
        lines.append(f"порог использования: {threshold} ({source})")
    if result.state == "absent":
        return lines
    size = len(result.text.encode("utf-8"))
    limit = config.CORE_REFERENCE_MAX_BYTES
    if size > limit:
        verdict = "больше предела — в бриф не попадёт"
    elif size * 10 > limit * 9:
        verdict = "больше 90% предела — бриф поднимет предупреждение"
    else:
        verdict = "в пределе"
    lines += [f"размер: {size} байт, предел {limit} байт "
              f"({size * 100 / limit:.1f}%)", f"вывод: {verdict}"]
    return lines


def cmd_reference(rest: list) -> None:
    """Команда `reference <проект> [--sha <sha>]`: сборка справочника ядра
    проекта по требованию и сводка (SPEC 01M4TVBT9ZCRQDY669QV3S95MA,
    требование 4). Проверки до любых действий: имя проекта, клон, форма
    `--sha`, БД пульта; без `--sha` — коммит `refs/heads/<base>` клона без
    `fetch`. Код выхода ненулевой при `absent`; размер больше предела —
    сообщение, не ошибка."""
    if rest[:1] in (["-h"], ["--help"]):
        print(REFERENCE_USAGE)
        return
    if not rest or rest[0].startswith("-"):
        sys.exit(f"reference: не назван проект\n{REFERENCE_USAGE}")
    name, extra = rest[0], rest[1:]
    sha = None
    if extra:
        if extra[0] != "--sha" or len(extra) != 2:
            sys.exit(f"reference: нераспознанные аргументы {' '.join(extra)}\n"
                     f"{REFERENCE_USAGE}")
        sha = extra[1]
    try:
        entry = targets.target(name)
    except targets.TargetsError as exc:
        sys.exit(f"reference: {exc}")
    clone = repo_context.clone_path(name)
    if not clone.is_dir():
        sys.exit(f"reference: клона проекта {name} нет ({clone}) — сначала "
                 f"target-init {name}")
    if sha is not None and not reference_cache.SHA_FORM.fullmatch(sha):
        sys.exit(f"reference: --sha {sha!r} — не полный sha из 40 "
                 f"шестнадцатеричных знаков")
    if not store.db_usable():
        sys.exit(f"reference: {NO_JOURNAL}")
    if sha is None:
        sha, why = reference_cache.branch_commit(clone, entry["base"])
        if sha is None:
            sys.exit(f"reference: коммит базы refs/heads/{entry['base']} "
                     f"не узнан: {why}")
    result = reference_cache.get_reference_for_target(
        store.db(), name, reason=reference_cache.REFERENCE_REASON, sha=sha)
    lines = reference_summary(name, entry.get(targets.REFERENCE_FIELD), sha, result)
    print("\n".join(lines))
    if result.state not in ("off", "fresh", "cached"):
        sys.exit(1)
