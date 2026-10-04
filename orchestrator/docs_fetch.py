"""Команда `docs <id> [файл]` / `docs --fetch-all`: документы задачи из
`origin` (ADR-0021 пп. 3, 13, этап 1; SPEC 01M41VTSE5N15P5P2WZF4GF2BQ).

Документы задачи живут в `refs/artifacts/<id>` репозитория её проекта, а
читатели вне конвейера (`show`, `retro_corpus`) видят только локальные
ссылки: на второй машине или после чистого клона документы закрытых задач
недоступны без подтягивания. `docs <id>` подтягивает ссылку задачи из
`origin` её репозитория (артели или внешнего проекта, по target задачи) и
печатает файл документов либо их перечень; `docs --fetch-all` —
все ссылки, одним `git fetch` на репозиторий.

Локальная ссылка сдвигается только вперёд (`artifact_branch.
fetch_from_origin`/`fetch_all_from_origin`): локальная с коммитами не из
`origin` не перезаписывается — вывод называет расхождение.

Процессу роли команда недоступна (её нет в `artel._ROLE_ALLOWED_COMMANDS`):
она ходит в сеть и переписывает локальные ссылки, в том числе ссылку живой
задачи с зафиксированным коммитом; документы своей задачи роли
материализует пульт.
"""
import sys

from . import artifact_branch, config, gitcmd, store, targets, workspace

USAGE = "Использование: artel.py docs <id> [файл] | artel.py docs --fetch-all"


def cmd_docs(rest: list) -> None:
    if not rest:
        sys.exit(USAGE)
    if rest[0] == "--fetch-all":
        _fetch_all()
        return
    _docs(rest[0], rest[1] if len(rest) > 1 else None)


def _main_copy_reader(task_id: str, ref: str):
    """Чтение исторической ссылки артели, которая есть только в git главной
    копии (238 ссылок до этапа 2 ADR-0021; SPEC 01M42PENCS26D0656X8FR7DFA7,
    требование 8, AC-13): только чтение по явному репозиторию — git главной
    копии не меняется. (голова, чтение файла, перечень) либо `None` —
    ссылки нет и там, или задача не артели."""
    conn = store.db()
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return None
    head = gitcmd.branch_head_sha(ref, repo=config.ROOT)
    if not head:
        return None
    return (head,
            lambda rel: gitcmd.show(head, rel, repo=config.ROOT),
            lambda rel_dir: gitcmd.ls_tree_files(head, rel_dir, repo=config.ROOT))


def _docs(task_id: str, name: str | None) -> None:
    task_id = store.resolve_task_id(store.db(), task_id)
    ref = artifact_branch.branch_name(task_id)
    workspace.ensure_clone(store.task_target(store.db(), task_id))
    outcome, detail = artifact_branch.fetch_from_origin(task_id)
    head = artifact_branch.ref_head(task_id)
    show = lambda rel: artifact_branch.show(task_id, head, rel)  # noqa: E731
    ls_tree = lambda rel_dir: artifact_branch.ls_tree(task_id, head, rel_dir)  # noqa: E731
    if not head:
        legacy = _main_copy_reader(task_id, ref)
        if legacy is not None:
            head, show, ls_tree = legacy
            outcome = artifact_branch.FETCH_SAME
            print(f"предупреждение: {ref} нет в клоне проекта и в origin — "
                  f"читается из git главной копии", file=sys.stderr)
    if not head:
        why = ("нет ни в origin, ни локально"
               if outcome == artifact_branch.FETCH_ABSENT
               else f"нет локально, из origin не подтянута — {detail}")
        sys.exit(f"docs {task_id}: ссылки документов задачи {ref} {why}")
    if outcome == artifact_branch.FETCH_DIVERGED:
        print(f"предупреждение: {detail}; читается локальная", file=sys.stderr)
    elif outcome in (artifact_branch.FETCH_ABSENT, artifact_branch.FETCH_FAILED):
        print(f"предупреждение: {ref} из origin не подтянута — {detail}; "
              f"читается локальная", file=sys.stderr)
    prefix = f"tasks/{task_id}/"
    if name is None:
        paths = ls_tree(prefix.rstrip("/"))
        if paths is None:
            sys.exit(f"docs {task_id}: перечень файлов {ref} ({head[:12]}) "
                     f"не прочитан")
        print(f"{ref} @ {head[:12]}:")
        for rel in paths:
            print(f"  {rel[len(prefix):] if rel.startswith(prefix) else rel}")
        return
    text, reason = show(prefix + name)
    if text is None:
        sys.exit(f"docs {task_id}: файла {prefix}{name} нет в {ref} "
                 f"({head[:12]}) — {reason}")
    sys.stdout.write(text)


def _target_names() -> list[str]:
    """Target'ы из targets.yaml, артель первой; файл не годен — только
    артель (о файле говорит `doctor`)."""
    try:
        names = list(targets.load())
    except targets.TargetsError as exc:
        print(f"предупреждение: {exc} — подтягивается только артель",
              file=sys.stderr)
        names = []
    return [config.DEFAULT_TARGET] + [n for n in names
                                      if n != config.DEFAULT_TARGET]


def _fetch_all() -> None:
    """Каждый репозиторий с `origin` — один fetch; исход по репозиторию —
    одной строкой с числом принесённых и обновлённых ссылок, расхождения —
    строкой на ссылку. Отказ любого репозитория — ненулевой код после
    прохода по всем."""
    failed = False
    seen = set()
    for target in _target_names():
        if target == config.DEFAULT_TARGET:
            # Ссылки артели — в её клоне (SPEC 01M42PENCS26D0656X8FR7DFA7,
            # требование 8), не в git главной копии.
            workspace.ensure_clone(target)
        repo = artifact_branch.repo_for_target(target)
        if repo in seen:
            continue
        seen.add(repo)
        if repo == artifact_branch._NO_REPO:
            print(f"{target}: пропущен — {artifact_branch.NO_REPO_REASON}")
            continue
        if not artifact_branch._origin_configured(repo):
            print(f"{target}: пропущен — origin не настроен")
            continue
        outcomes, reason = artifact_branch.fetch_all_from_origin(repo)
        if outcomes is None:
            print(f"{target}: отказ — {reason}")
            failed = True
            continue
        count = {}
        for outcome, _detail in outcomes.values():
            count[outcome] = count.get(outcome, 0) + 1
        print(f"{target}: принесено {count.get(artifact_branch.FETCH_BROUGHT, 0)}, "
              f"обновлено {count.get(artifact_branch.FETCH_UPDATED, 0)}, "
              f"без изменений {count.get(artifact_branch.FETCH_SAME, 0)}, "
              f"расходится с origin "
              f"{count.get(artifact_branch.FETCH_DIVERGED, 0)}")
        for task_id, (outcome, detail) in outcomes.items():
            if outcome in (artifact_branch.FETCH_DIVERGED,
                           artifact_branch.FETCH_FAILED):
                print(f"  {task_id}: {detail}")
                failed = failed or outcome == artifact_branch.FETCH_FAILED
    if failed:
        sys.exit(1)
