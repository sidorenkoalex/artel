"""Пакет orchestrator/doctor -- уборка осиротевших артефактных веток.

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""

from orchestrator import doctor


# --- уборка осиротевших артефактных веток (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T,
# требование 4/AC-4) --------------------------------------------------------

ORPHAN_ARTIFACT_BRANCH_SOURCE = "doctor.cleanup.artifact_branches"

# `git ls-remote --heads origin 'artifact/*'` — сверка веток-кандидатов с
# origin (SPEC 01M1REVP9WGRHDDNVEVE8BBH0Z, требование 1): один и тот же
# glob на весь прогон уборки, не по одному запросу на ветку (AC-3).
_REMOTE_ARTIFACT_GLOB = "artifact/*"
# Сентинел «аргумент не передан», отличимый от легитимных значений
# `None`/`set()`/`[]` (SPEC 01M1REVP9WGRHDDNVEVE8BBH0Z, «Подход» PLAN):
# явно переданное `remote`/`orphans` (в т.ч. `None`) — используется как
# есть, БЕЗ пересчёта; аргумент не передан — функция вычисляет его сама
# (обратная совместимость с прямыми вызовами существующих юнит-тестов и
# приёмочных `_sandbox.py`, где `doctor._orphan_artifact_branches(conn)`
# зовётся с одним аргументом).
_UNSET = object()


def _remote_artifact_branch_names() -> set[str] | None:
    """Имена веток `artifact/<id>`, присутствующих на `origin` (SPEC
    01M1REVP9WGRHDDNVEVE8BBH0Z, требование 1): единственное место,
    зовущее `git ls-remote --heads origin 'artifact/*'` — ровно один
    запрос на весь прогон уборки, не по одному на ветку-кандидата (AC-3).

    `None` — origin не ответил (git не ответил вовсе или вернул ненулевой
    код возврата, требования 5-6): вызывающий код обязан трактовать это
    как «критерий не вычислим», НЕ как «на origin ничего нет» — в
    отличие от `gitcmd.list_branches`/`remote_branch_sha`, где та же
    деградация к пустоте корректна, здесь пустота означала бы удалить
    ЛЮБУЮ локальную ветку как сироту (fail-closed, принцип целостности).
    """
    res = doctor.gitcmd.git("ls-remote", "--heads", "origin", doctor._REMOTE_ARTIFACT_GLOB)
    if res is None or res.returncode != 0:
        return None
    prefix = "refs/heads/"
    names = set()
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        if ref.startswith(prefix):
            names.add(ref[len(prefix):])
    return names


def _orphan_artifact_branches(conn, remote=_UNSET) -> list[str] | None:
    """Ветки `artifact/<id>` пульта, для которых НЕТ строки в БД
    (регистронезависимо — `artifact_branch.branch_name` работает с
    `task_id.lower()`) И которых нет среди веток `artifact/*` на origin
    (SPEC 01M1REVP9WGRHDDNVEVE8BBH0Z, требование 1, AC-1/AC-2: ОБА
    условия обязаны быть верны — ветка, живая хотя бы по одному из двух
    источников истины, сиротой не считается). Только чтение, без
    удаления — общая часть между `sweep_orphan_artifact_branches` (сама
    уборка) и `cmd_doctor` (честный CLI-вывод: нужно знать, были ли
    сироты, независимо от того, удалось ли их удалить).

    `remote` — предвычисленный набор веток origin (`_remote_artifact_
    branch_names`); по умолчанию (аргумент не передан) вычисляется
    здесь — вызывающий код, которому важно не делать второй запрос за
    один прогон (`cmd_doctor`, AC-3), передаёт уже вычисленное значение
    явно.

    `None` — origin не ответил (требование 6): вся функция тоже
    возвращает `None`, не пустой список — пустой список уже легитимно
    означает «сирот нет», спутать эти два случая означало бы посчитать
    origin пустым и удалить произвольную локальную ветку.
    """
    if remote is doctor._UNSET:
        remote = doctor._remote_artifact_branch_names()
    if remote is None:
        return None
    known_ids = {r["id"].lower() for r in doctor.store.all_tasks(conn)}
    branches = doctor.gitcmd.list_branches("artifact/") or []
    return sorted(
        b for b in branches
        if b[len("artifact/"):] not in known_ids and b not in remote)


def sweep_orphan_artifact_branches(conn, orphans=_UNSET) -> list[str] | None:
    """Удаляет ветки `artifact/<id>` пульта, отсутствующие И в БД, И на
    origin (SPEC «Контекст»: источник утечки — тест, заводящий задачу
    через `cmd_new` без подмены `config.ROOT`, коммитивший артефакты
    прямиком в НАСТОЯЩИЙ репозиторий пульта; расширено требованием 1
    задачи 01M1REVP9WGRHDDNVEVE8BBH0Z — на чужой копии, где локальной
    строки БД у живой задачи просто нет, критерий «только БД» сносил бы
    её). Только по явному вызову Оператора (`doctor --fix`), не
    автоматически — ветки живых задач не трогаются.

    `orphans` — предвычисленный список кандидатов (`_orphan_artifact_
    branches`); по умолчанию (аргумент не передан) вычисляется здесь —
    `cmd_doctor` передаёт уже вычисленный список явно, чтобы не делать
    второй запрос origin за один прогон уборки (AC-3).

    `orphans is None` (origin недоступен, требование 5/AC-6): уборка НЕ
    ВЫПОЛНЯЕТСЯ ВООБЩЕ — `git branch -D` не зовётся ни разу, incident не
    заводится, возврат — `None` (fail-closed, принцип целостности).

    Иначе — ровно один incident-алерт на весь прогон уборки, с
    перечислением удалённого в сообщении (не по алерту на каждую ветку —
    Оператору нужна одна строка на уборку, не журнал по счётчику
    находок). Возврат `git branch -D` проверяется (ANSWER-2 п.3, R1-F3):
    ветка, которую не удалось удалить, не попадает ни в возвращаемый
    список, ни в текст алерта как «удалено» — только в отдельную честную
    часть сообщения. Возвращает список ФАКТИЧЕСКИ удалённых имён веток;
    пустой — либо сирот не нашлось, либо ни одно удаление не удалось
    (`cmd_doctor` различает эти два случая в CLI-выводе через `orphans`,
    ANSWER-3 R1-F3).
    """
    if orphans is doctor._UNSET:
        orphans = doctor._orphan_artifact_branches(conn)
    if orphans is None:
        return None
    deleted = []
    failed = []
    for branch in orphans:
        res = doctor.gitcmd.git("branch", "-D", branch)
        (deleted if res is not None and res.returncode == 0 else failed).append(branch)
    if orphans:
        parts = []
        if deleted:
            parts.append(f"удалены: {', '.join(deleted)}")
        if failed:
            parts.append(f"НЕ удалены (ошибка git branch -D): {', '.join(failed)}")
        doctor.alerts.raise_alert(
            conn, None, "incident", doctor.ORPHAN_ARTIFACT_BRANCH_SOURCE,
            f"осиротевшие артефактные ветки: {'; '.join(parts)}")
    return deleted


def _print_orphan_branch_candidates(orphans: list[str]) -> None:
    """Требования 3-4 (SPEC 01M1REVP9WGRHDDNVEVE8BBH0Z): число кандидатов
    на удаление ПОЛНОСТЬЮ, но их имён — только первые `config.
    DOCTOR_ORPHAN_PREVIEW_LIMIT`, с пометкой про `doctor --fix`. Общая
    для режима предпросмотра (`doctor`) и для `--fix` (там — печатается
    ДО удаления, требование 4/AC-5)."""
    print(f"Осиротевшие артефактные ветки-кандидаты на удаление: "
         f"{len(orphans)} (первые {doctor.config.DOCTOR_ORPHAN_PREVIEW_LIMIT} имён "
         f"ниже; удалит `doctor --fix`)")
    for branch in orphans[:doctor.config.DOCTOR_ORPHAN_PREVIEW_LIMIT]:
        print(f"  {branch}")


