"""kill switch и уборка хвостов задачи: каталог артефактов и ветка."""
import os
import shutil
import signal
import socket
import sys

from . import (ci, config, fixation, fsm, gitcmd, lease, liveness,
               repo_context, store, targets, workspace)


def _dir_in_main(task_id: str) -> bool | None:
    """Есть ли каталог задачи в дереве main главной копии. None — git не
    ответил.

    Легаси-каталог `config.TASKS/<id>` (задачи старше T094) лежит в рабочем
    дереве главной копии — о нём и спрашивается её git, только чтением.
    """
    res = gitcmd.in_repo(config.ROOT, "ls-tree", "-r", "--name-only", config.MAIN_BRANCH, "--",
                     f"tasks/{task_id}")
    if res.returncode != 0:
        return None
    return bool(res.stdout.strip())


def artifacts_in_main(task_id: str) -> bool | None:
    """Сохранены ли документы задачи историей: каталог задачи в дереве main
    либо ссылка документов `refs/artifacts/<id>` в репозитории задачи. None
    — git не ответил на вопрос о main.

    Достаточно самого факта наличия: артефакты задачи, убитой после
    мержа, — история (docs/design.md §6), её не трогаем целиком. С ADR-0021
    п.4 мерж каталог задачи в main не кладёт (SPEC
    01M4M67SGNEYMN9F1C7XVX24XE, требование 9) — документы такой задачи
    хранит только её ссылка.
    """
    in_main = _dir_in_main(task_id)
    if in_main is not False:
        return in_main
    from . import artifact_branch
    return bool(artifact_branch.ref_head(task_id))


def artifacts_tracked_here(task_id: str) -> bool | None:
    """Отслеживается ли каталог задачи здесь и сейчас. None — git не ответил.

    Смотрит индекс, а не дерево HEAD: закоммиченный в текущую ветку и
    просто добавленный `git add` каталоги одинаково опасны для rmtree.
    """
    res = gitcmd.in_repo(config.ROOT, "ls-files", "--", f"tasks/{task_id}")
    if res.returncode != 0:
        return None
    return bool(res.stdout.strip())


def drop_task_dir(task_id: str) -> str:
    """Убирает каталог артефактов убитой задачи; строка — что вышло.

    Бережёт каталог, который main отслеживает (`_dir_in_main`): rmtree
    оставил бы в главной копии удаления. Документы, сохранённые только
    ссылкой (`artifacts_in_main` по ссылке), локальную неотслеживаемую
    копию не берегут — история цела в ссылке, копия на диске — хвост."""
    tdir = config.TASKS / task_id
    in_main = _dir_in_main(task_id)
    if in_main is None:
        return f"каталог tasks/{task_id}/ оставлен: main не прочитан"
    if in_main:
        return f"каталог tasks/{task_id}/ оставлен: артефакты в main"
    if not tdir.exists():
        return f"каталога tasks/{task_id}/ нет"
    # Каталог убитой задачи мог уехать в чужую ветку через `git add -A`
    # разработчика — ровно инцидент T002 из SPEC. rmtree по отслеживаемым
    # файлам оставит в дереве удаления, которые следующий `git add -A`
    # утащит в тот же чужой коммит: мусор вместо уборки.
    tracked = artifacts_tracked_here(task_id)
    if tracked is None:
        return f"каталог tasks/{task_id}/ оставлен: индекс не прочитан"
    if tracked:
        here = gitcmd.current_branch(config.ROOT)
        fix = ("сними его из индекса и повтори kill"
               if here == config.MAIN_BRANCH
               else f"перейди на {config.MAIN_BRANCH} и повтори kill")
        return (f"каталог tasks/{task_id}/ оставлен: отслеживается в "
                f"{here or 'текущей ветке'} — {fix}")
    try:
        shutil.rmtree(tdir)
    except OSError as exc:
        return f"каталог tasks/{task_id}/ не удалён: {exc}"
    return f"удалён каталог tasks/{task_id}/"


def _merged_base(repo) -> str:
    """Ревизия main клона для `--merged`: `origin/<база>` — push мержа
    двигает её, локальную базу клона — нет."""
    return f"origin/{_base_of(repo)}"


def _merged(branch: str, repo) -> bool:
    """Ветка влита в линию main клона: в `origin/<база>` (туда уходит мерж
    пульта) либо в локальную базу клона."""
    return (gitcmd.branch_merged(branch, repo, _merged_base(repo))
            or gitcmd.branch_merged(branch, repo, _base_of(repo)))


def _base_of(repo) -> str:
    target = repo.parent.name if repo is not None else config.DEFAULT_TARGET
    ctx = repo_context.resolve(target)
    return ctx.base if ctx is not None else config.MAIN_BRANCH


def drop_task_branch(branch: str, repo) -> str:
    """Убирает локальную ветку убитой задачи; строка — что вышло.

    Удаляется и ветка, целиком содержащаяся в main
    (01M3EM7EFQ4X4CAYMNG35P9D7Y, требование 4). Прежнее правило «оставлена:
    смержена в main» («история killed-задачи») пересмотрено и снято:
    `gitcmd.branch_merged` спрашивает `git branch --merged main`, то есть
    голова ветки — предок main и каждый её коммит достижим из main, а
    merge задачи идёт `--no-ff` без squash (docs/retention.md) — удаление
    теряет только имя-указатель, не историю. Ценой прежнего правила были
    вечные сироты: ветка задачи, поделённой на гейте SPEC, собственных
    коммитов не получает вовсе (работа шла в артефактной ветке пульта),
    то есть формально «смержена» — и `doctor` (`orphans-branches`,
    требующая отсутствия кодовой ветки у `done`/`killed`) краснел
    постоянно.

    Ответ `branch_merged` решает теперь не «удалять ли», а «каким флагом
    и как назвать исход» (требование 5): на влитой — `-d` (safe delete,
    git сам откажет, если ветка внезапно не влита — та же единственная
    защита, которой пользуется `drop_merged_task_branch` ниже); на
    неслитой — `-D`, на ней `-d` откажет всегда. Два разных текста
    исхода — чтобы по журналу было видно, сняли указатель на уже
    сохранённую в main историю или ветку с несохранённой работой.

    Вызывается ПОСЛЕ уборки worktree (`workspace.remove`): ни `-d`, ни
    `-D` не удалят ветку, пока её держит worktree (SPEC T045,
    требование 5). `repo` — клон проекта задачи (ADR-0021 п.1).
    """
    if not branch:
        # Строка задачи из БД прошлых версий: ветка не записана — искать нечего.
        return "ветка задачи не записана — нечего удалять"
    if not gitcmd.branch_exists(branch, repo):
        return f"локальной ветки {branch} нет"
    merged = _merged(branch, repo)
    # `-D` и на влитой: `-d` сверяет с upstream/HEAD клона, а не с
    # `origin/main`, куда ушёл мерж; влитость уже установлена выше.
    res = gitcmd.in_repo(repo, "branch", "-D", branch)
    if res.returncode != 0:
        return f"ветка {branch} не удалена: {res.stderr.strip()[:200]}"
    return f"удалена {'влитая' if merged else 'неслитая'} ветка {branch}"


def drop_merged_task_branch(branch: str, repo) -> str:
    """Убирает ветку задачи, ТОЛЬКО ЧТО влитую в main (переход `merge_gate
    -> done`, tasks/T073/SPEC.md, требование 2): строка — что вышло.

    Отдельная от `drop_task_branch` (kill) не по правилу удаления — с
    01M3EM7EFQ4X4CAYMNG35P9D7Y (требование 4) влитую ветку удаляют обе, —
    а по тому, что здесь смержённость не вопрос: её только что установил
    сам переход `merge_gate -> done`, ветвиться по `gitcmd.branch_merged`
    и различать два исхода в тексте (требование 5 той же задачи) на этом
    пути не по чему и незачем. `-d` (safe delete), не `-D`: git сам
    откажет, если ветка внезапно не влита — единственная защита, которая
    тут нужна. Вызывается ПОСЛЕ уборки worktree (`workspace.remove`) —
    `-d` не удалит ветку, пока её держит worktree.

    В клоне проекта (ADR-0021 п.1) мерж уходит в `origin/<база>`, локальная
    база клона его не несёт: влитость сверяется с `origin/<база>`
    (`branch_merged`), и только влитая снимается — `-D` после этой сверки
    играет роль прежнего `-d`.
    """
    if not branch:
        return "ветка задачи не записана — нечего удалять"
    if not gitcmd.branch_exists(branch, repo):
        return f"локальной ветки {branch} нет"
    if not _merged(branch, repo):
        return (f"ветка {branch} не удалена: не влита в "
                f"{_merged_base(repo)}")
    res = gitcmd.in_repo(repo, "branch", "-D", branch)
    if res.returncode != 0:
        return f"ветка {branch} не удалена: {res.stderr.strip()[:200]}"
    return f"удалена ветка {branch}"


def cleanup_killed_task(conn, task_id: str, branch: str) -> None:
    """Убирает хвосты убитой задачи и перечисляет сделанное в журнале.

    Уборка идёт после смены состояния и не может её отменить: kill switch
    обязан срабатывать всегда. Поэтому любой невыясненный факт (git
    промолчал, main не найден) — это «оставлено» со своей причиной, а не
    исключение. Логи прогонов в .artel/logs/ не трогаются — история
    наблюдаемости переживает задачу.
    """
    # Не `branch_exists`: кроме факта нужна причина — отсутствующий main и
    # неустановленный git разбираются Оператором по-разному.
    repo = workspace.task_repo(task_id)
    main = gitcmd.in_repo(repo, "rev-parse", "--verify", "--quiet",
                          f"refs/heads/{_base_of(repo)}")
    if main is None or main.returncode != 0:
        reason = ((main.stderr.strip()[:200] if main is not None else "")
                  or f"ветки {_base_of(repo)} нет")
        notes = [f"уборка пропущена: {reason} — сверять не с чем"]
    elif gitcmd.current_branch(repo) == branch:
        # Агент шага работает в своём worktree (SPEC T045), а не в главной
        # копии, но Оператор мог руками зачекаутить ветку задачи в ROOT
        # (ADR-0003 3д — главная копия остаётся обычной рабочей копией
        # git). Удалить такую ветку git не даст, а снести закоммиченный
        # в неё каталог — оставить грязное дерево: ровно тот мусор, ради
        # которого уборка и заводилась.
        notes = [f"уборка пропущена: ветка {branch} сейчас checked out — "
                 f"перейди на {_base_of(repo)} и повтори kill"]
    else:
        # Worktree — первым: ветку с `-D` не удалить, пока её держит
        # worktree (SPEC T045, требование 5, AC-5).
        notes = [workspace.remove(task_id), drop_task_dir(task_id),
                 drop_task_branch(branch, repo)]

    store.journal(conn, task_id, "orchestrator", "уборка", "; ".join(notes))
    for note in notes:
        print(f"  {note}")


# Признаки срабатывания предела `http.lowSpeedTime` в stderr git-пуша
# (curl, код 28): по ним отказ пуша отличается от молчания хостинга.
_PUSH_SILENT_MARKS = ("Operation too slow", "curl 28")
_GH_SILENT_PREFIX = "gh молчал дольше"


def _left_reason(res, silent: bool, what: str) -> str:
    text = ((res.stderr or res.stdout).strip()[:200]
            or f"код {res.returncode}")
    if silent:
        return f"{what} не ответил за {config.GH_TIMEOUT_SEC} с ({text})"
    return f"отказ: {text}"


def _forge_of(target: str) -> str:
    try:
        return targets.target(target).get("forge") or ""
    except targets.TargetsError:
        return ""


def _close_project_pr(branch: str, url: str, task_id: str) -> str:
    res = ci.gh("pr", "close", branch, "--comment",
                f"задача ликвидирована в пульте: {task_id}", repo=url)
    if res.returncode == 0:
        return f"PR {branch}: закрыт"
    silent = (res.stderr or "").startswith(_GH_SILENT_PREFIX)
    return f"PR {branch}: оставлено — {_left_reason(res, silent, 'gh')}"


def _bounded(repo, *args: str):
    # Предел — в самом вызове (`gitcmd.git` без таймаута): хостинг,
    # принявший соединение и замолчавший, иначе держал бы шаг без конца.
    return gitcmd.in_repo(repo, "-c", "http.lowSpeedLimit=1", "-c",
                          f"http.lowSpeedTime={config.GH_TIMEOUT_SEC}", *args)


def _delete_origin_branch(repo, branch: str, head: str | None = None) -> str:
    """Удаление ветки в `origin`; `head` — голова, прочитанная до этого:
    удаление тогда условно по ней (`--force-with-lease`) — ветку, сдвинутую
    после чтения, хостинг не удалит. Без `head` — прежний пуш kill."""
    if head is None:
        res = _bounded(repo, "push", "origin", "--delete", branch)
    else:
        ref = f"refs/heads/{branch}"
        res = _bounded(repo, "push", f"--force-with-lease={ref}:{head}",
                       "origin", "--delete", ref)
    if res is None:
        return f"ветка origin {branch}: оставлено — git не ответил"
    if res.returncode == 0:
        return f"ветка origin {branch}: удалена"
    silent = any(mark in (res.stderr or "") for mark in _PUSH_SILENT_MARKS)
    return (f"ветка origin {branch}: оставлено — "
            f"{_left_reason(res, silent, 'origin')}")


def cleanup_project_remote(conn, task_id: str, branch: str) -> None:
    """Уборка в репозитории внешнего проекта (SPEC 01M568XFYM68EYHH0C16Y7D7F0):
    черновой PR задачи закрывается, ветка задачи удаляется из `origin`.

    Зовёт только `_cmd_kill`, выигравший переход в `killed`; деление на
    гейте SPEC и повторный kill терминальной задачи её не выполняют, а
    `cleanup_killed_task` — общий для них узел — её не зовёт. Исход
    локальной уборки не важен: нужно только имя ветки. PR — первым:
    удаление head-ветки на GitHub закрывает PR само, и комментарий потом
    не добавить. Ни один сбой не отменяет kill — это «оставлено» с
    причиной. `refs/artifacts/<id>` не трогаются — документы проекта
    публикуются в его репозиторий намеренно.
    """
    t = store.get_task(conn, task_id)
    if repo_context.is_artel(t) or not branch:
        return
    target = t["target"]
    ctx = repo_context.resolve(target)
    if ctx is None:
        notes = [f"PR {branch}: оставлено — {repo_context.unresolved_reason(target)}",
                 f"ветка origin {branch}: оставлено — "
                 f"{repo_context.unresolved_reason(target)}"]
    else:
        notes = []
        # Не GitHub — PR пульт там не заводит (`github_adapter.ensure_draft_mr`).
        if _forge_of(target) == "github":
            notes.append(_close_project_pr(branch, ctx.remote, task_id))
        notes.append(_delete_origin_branch(workspace.task_repo(task_id), branch))
    store.journal(conn, task_id, "orchestrator", "уборка", "; ".join(notes))
    for note in notes:
        print(f"  {note}")


def _origin_branch_head(repo, branch: str) -> tuple[str, str]:
    """(голова, "") / ("", "") — ветки нет / ("", причина) — `origin` не
    ответил: семантика `gitcmd.remote_ref_state`, но с пределом
    `http.lowSpeedTime` — чтение идёт под мьютексом мержа."""
    ref = f"refs/heads/{branch}"
    res = _bounded(repo, "ls-remote", "origin", ref)
    if res is None:
        return "", "git не ответил"
    if res.returncode != 0:
        return "", (res.stderr or "").strip()[:200] or "ls-remote не удался"
    for line in res.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1] == ref:
            return fields[0], ""
    return "", ""


def _merged_remote_outcome(repo, branch: str,
                           merged_sha: str) -> tuple[str, list[str]]:
    """(исход, подсказки) уборки ветки смерженной задачи в `origin`."""
    ref = f"refs/heads/{branch}"
    left = f"ветка origin {branch}: оставлено — "

    def delete_hint(head: str) -> str:
        return (f"вручную: git -C {repo} push --force-with-lease={ref}:{head} "
                f"origin --delete {ref}")

    head, reason = _origin_branch_head(repo, branch)
    if reason:
        return left + reason, [
            f"вручную: git -C {repo} ls-remote origin {ref}",
            delete_hint("<голова>")]
    if not head:
        return f"ветка origin {branch}: нет — удалять нечего", []
    if not gitcmd.is_ancestor(head, merged_sha, repo=repo):
        return (left + f"голова {head} не входит в смерженный main "
                       f"{merged_sha}",
                [f"сверка: git -C {repo} log --oneline {merged_sha}..{head}"])
    note = _delete_origin_branch(repo, branch, head=head)
    if note == f"ветка origin {branch}: удалена":
        return note, []
    return note, [delete_hint(head)]


def cleanup_merged_remote(conn, task_id: str, branch: str,
                          merged_sha: str) -> None:
    """Уборка ветки задачи в `origin` проекта после мержа (SPEC
    01M5FGJW4RBN9C9P48Q8MDHJX1): только на пути `merge_gate -> done` после
    успешного push мержа (`fsm_merge_gate._cleanup_merged_task`), у артели
    и у внешнего проекта — клон задачи и его `origin`, как у kill.

    Ветка удаляется, только если её голова в `origin` входит в смерженный
    main `merged_sha`, и условно по прочитанной голове. Задача уже `done`:
    ни один исход, включая исключение, не срывает мерж — это «оставлено» с
    причиной в одной записи «уборка». Подсказка ручной команды печатается
    после исхода и в журнал не пишется. `refs/artifacts/<id>` и ветки
    `artifact/*` не трогаются; `gh` не зовётся.
    """
    if not branch:
        return
    try:
        note, hints = _merged_remote_outcome(
            workspace.task_repo(task_id), branch, merged_sha)
    except Exception as exc:  # noqa: BLE001 — задача уже done, мерж не срывается
        note, hints = (f"ветка origin {branch}: оставлено — "
                       f"{type(exc).__name__}: {exc}"), []
    try:
        store.journal(conn, task_id, "orchestrator", "уборка", note)
    except Exception:  # noqa: BLE001 — то же: запись журнала мерж не срывает
        pass
    print(f"  {note}")
    for hint in hints:
        print(f"    {hint}")


def _live_cycle_holder(row) -> bool:
    """Живой держатель lease — признаки SPEC 01M28NX0M2WTVC38XVN75N01XD,
    требование 1 (те же, что уже проверяют по отдельности `doctor.
    check_leases` — свой host + адресуемый pid — и `lease.acquire`/
    `is_live` — свежий heartbeat): держатель на ЭТОМ host (иначе pid не
    проверяем и живость не подтвердить), его pid адресуем
    (`liveness._pid_alive`), heartbeat не протух (не старше
    `config.LEASE_STALE_AFTER_SEC`). Отсутствие lease — не «живой»."""
    if row is None:
        return False
    if row["hostname"] != socket.gethostname():
        return False
    if not liveness._pid_alive(row["pid"]):
        return False
    return liveness._age_seconds(row["heartbeat_ts"]) <= config.LEASE_STALE_AFTER_SEC


def _live_cycle_role(conn, task_id: str, row) -> str | None:
    """Роль держателя живого ЦИКЛА — None, если отказывать нечему: либо
    lease не живой (`_live_cycle_holder`), либо на текущем состоянии
    задачи прямо сейчас нет агентского шага (`runner.step_role`).

    Второе условие — не сужение требования 1, а его точный смысл: SPEC
    называет сценарий «живой ОТВЯЗАННЫЙ ЦИКЛ (`auto`/`run`)», а `auto`/
    `run` берут lease только вокруг реального шага роли (`runner.
    step_role(t) is not None`) — на состоянии без роли (например,
    `spec_writing` без `TZ.md`, прежний флоу «SPEC пишет Оператор») ни
    `auto`, ни `run` lease так не возьмут, а синтетическая строка
    `leases`, заведённая тестом или руками, «циклом» в смысле SPEC не
    является. Отсюда и текст отказа AC-1 («шаг <роль> с <время>») — без
    роли ему нечего называть.
    """
    if not _live_cycle_holder(row):
        return None
    from . import runner
    t = store.get_task(conn, task_id)
    return runner.step_role(t)


# Литерал действия журнала отказа — сверяется буквально приёмочным тестом
# AC-1 (`test_ac1_journal_names_the_refusal`).
KILL_REFUSAL_JOURNAL_ACTION = "kill отклонён: цикл жив"
# Литерал действия журнала подтверждения --yes — AC-2
# (`test_ac2_journal_names_the_yes_confirmation`).
KILL_CONFIRM_JOURNAL_ACTION = "kill подтверждён флагом --yes при живом цикле"


def _refuse_live_cycle(conn, task_id: str, role: str, row) -> None:
    """Отказ AC-1: текст называет держателя (pid, роль/шаг, время
    heartbeat) и обе следующие команды — не меняет ничего в задаче,
    вызывается ДО `lease.run_locked`, так что `force=True` до строки
    lease так и не добирается."""
    text = (f"[{task_id}] цикл жив (pid {row['pid']}, шаг {role} с "
           f"{row['heartbeat_ts']}) — остановить цикл: artel.py stop "
           f"{task_id}; ликвидировать задачу (ветка и worktree будут "
           f"удалены): artel.py kill {task_id} --yes")
    store.journal(conn, task_id, "operator", KILL_REFUSAL_JOURNAL_ACTION, text)
    sys.exit(text)


KILL_EMPTY_REASON_REFUSAL = "kill: --reason требует непустую причину"


def _kill_detail(reason: str | None) -> str:
    """Деталь перехода `state -> killed` (SPEC 01M5K11K3VV23VK177YWMWKJ14,
    требование 2): переводы строки причины — в пробел, чтобы строка «Итог:»
    RETRO, берущая эту деталь, осталась одной строкой."""
    if reason is None:
        return "kill switch"
    flat = reason.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return f"kill switch: {flat.strip()}"


def cmd_kill(task_id: str, session_id: str | None = None, *,
            confirmed: bool = False, reason: str | None = None) -> bool:
    """Берёт lease задачи перед работой (SPEC T044, требование 2).

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease/CAS/путей на диске — иначе `kill` неразрешённым префиксом
    брал lease по несуществующему ключу и зацикливался в `_cmd_kill` на
    вечно проигрывающем CAS (REVIEW T094 итерация 1, замечание 1: живой
    репро — `cmd_kill` с уникальным префиксом зависал бесконечно).

    `confirmed` (SPEC 01M28NX0M2WTVC38XVN75N01XD, требования 1-2) —
    флаг `--yes` командной строки: без него живой держатель (`_live_
    cycle_holder`) отказывает целиком, ничего не меняя (AC-1); с ним —
    прежнее полное поведение `kill`, только с дополнительной записью в
    журнал (AC-2). Мёртвый/отсутствующий держатель не смотрит на
    `confirmed` вовсе — путь остаётся прежним (AC-3).

    `reason` — причина `--reason` (SPEC 01M5K11K3VV23VK177YWMWKJ14):
    пустая отказывает до проверки живого цикла и lease, непустая попадает
    только в деталь записанного перехода. Возврат — записал ли этот вызов
    переход в `killed` (подсказка диспетчера о незаписанной причине)."""
    if reason is not None and not reason.strip():
        sys.exit(KILL_EMPTY_REASON_REFUSAL)
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    # Снимок lease ДО `run_locked` (SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P,
    # AC-10) — `force=True` ниже перезаписывает pid/session строки НА
    # СВОЙ ПРОЦЕСС (kill сам становится «держателем»), поэтому pid
    # живого отвязанного цикла нужно поймать раньше, иначе к моменту,
    # когда `_cmd_kill` его читает, там уже лежит pid самого kill.
    holder_before = store.lease_row(conn, task_id)
    live_role = _live_cycle_role(conn, task_id, holder_before)
    if live_role is not None:
        if not confirmed:
            _refuse_live_cycle(conn, task_id, live_role, holder_before)
        store.journal(conn, task_id, "operator", KILL_CONFIRM_JOURNAL_ACTION,
                     f"pid={holder_before['pid']}, hostname="
                     f"{holder_before['hostname']}")
    # `force=True` — kill обязан прервать задачу немедленно, даже если
    # lease сейчас держит живой отвязанный цикл со свежим heartbeat
    # (иначе kill отказал бы «сессия занята», ровно тем же текстом,
    # каким сегодня отказывает run/advance при живом конкуренте).
    return bool(lease.run_locked(
        conn, task_id, session_id,
        lambda sid: _cmd_kill(conn, task_id, holder_before, reason),
        force=True))



# Литерал действия журнала — источник «Сути» killed-RETRO следующего
# merge_gate (SPEC T048, требование 6, `orchestrator/retro.py`); строка
# сверяется буквально, тем же приёмом, что `retro._actor_costs`/
# `_escalations` уже сверяются с литералами `runner.py`/`store.py`.
KILL_TZ_JOURNAL_ACTION = "kill: TZ.md"


def _journal_tz_before_cleanup(conn, task_id: str, branch: str,
                               target: str) -> None:
    """Полный текст `TZ.md` (если он был) — в журнал БД ДО уборки ветки
    (SPEC T048, требование 5): main для убитой задачи не видел ни SPEC.md,
    ни TZ.md вовсе (требование 4), а сама ветка после `cleanup_killed_task`
    удаляется — читать станет неоткуда. Ветко-корректное чтение
    (`gitcmd.show`), тем же приёмом, что и `runner.step_role` (T031/T047,
    требование 7): TZ.md коммитится `cmd_new` сразу в ветку, не на диск.
    Файла нет (`new` без `--tz`) — журналить нечего, не отказ.

    Единая логика для ЛЮБОГО target, включая артель (A7, требование 2 —
    снятие особого случая догфуда): `tasks/<id>/` живёт в АРТЕФАКТНОЙ
    ветке пульта, не в `branch` (кодовая ветка задачи — код целевого,
    пульту вообще не принадлежит) — читается оттуда. `branch` остаётся
    параметром сигнатуры ради вызывающего кода (`_cmd_kill`), не
    участвует в чтении.
    """
    from . import artifact_branch
    source_branch = artifact_branch.branch_name(task_id)
    text, _ = artifact_branch.show(task_id, source_branch, f"tasks/{task_id}/TZ.md")
    if text is not None:
        store.journal(conn, task_id, "orchestrator",
                      KILL_TZ_JOURNAL_ACTION, text)


# Терминальные состояния FSM: kill из них — no-op на самом переходе
# (SPEC T050, требование 6) — уборка ниже всё равно остаётся безусловной.
# Список — `fsm.TERMINAL_STATES` (SPEC 01M5TB6VDVV6AM8DWPGVQE8CDW,
# требование 11).
TERMINAL_STATES = fsm.TERMINAL_STATES


def _group_kill_lease_step(conn, task_id: str) -> None:
    """AC-4 (SPEC 01M1PNBSHR2PMFECMP7C204MF1): при живом процессе лизы —
    SIGTERM всей группе процессов записанного AC-2 агентного шага, после
    грейса SIGKILL, ДО снятия lease и уборки worktree/ветки (вызывается
    из `_cmd_kill` перед `lease.release_any`).

    Свой host — та же защита, что уже применяет `pause.cmd_pause_now` к
    межхостовой адресации: pid/pgid чужого host нельзя ни подтвердить,
    ни безопасно сигналить локальным `os.killpg` (числовое совпадение
    с ЛОКАЛЬНЫМ процессом было бы случайным попаданием, не адресацией).
    Лиза мертва или без записанного pgid — нечего снимать (AC-6 берёт
    на себя мёртвый lease отдельным путём, под `doctor --fix`).

    Отдельно и независимо от `_cmd_kill`'а снимка `holder_before`/SIGKILL
    отвязанного цикла (SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P, AC-10) — `pgid`
    здесь несёт группу АГЕНТСКОГО подпроцесса конкретного шага (`runner.
    spawn_agent`, собственная сессия), не группу самого процесса цикла
    (`auto`/`run`, `leases.pid`): это две независимые группы процессов,
    убить нужно обе, иначе одна из них осиротеет.
    """
    row = store.lease_row(conn, task_id)
    if row is None or not row["pgid"]:
        return
    if row["hostname"] != socket.gethostname():
        return
    if not liveness._pid_alive(row["pid"]):
        return
    count = liveness.terminate_process_group(row["pgid"])
    store.journal(conn, task_id, "orchestrator",
                  "kill: группа процессов шага снята",
                  liveness.group_kill_detail(row["pgid"], count))


def _cmd_kill(conn, task_id: str, holder_before=None,
              reason: str | None = None) -> bool:
    """Kill switch: убивает задачу из ЛЮБОГО нетерминального состояния,
    даже если конкурентная сессия успела перейти между чтением состояния
    и CAS-попыткой (SPEC T050, требования 6-7, инвариант №14).

    Единственный вызыватель `set_state`, которому разрешено повторять
    проигрыш CAS (требование 6, в отличие от advance/approve/reject/merge
    — требование 4): проигрыш называет фактическое состояние
    (`store.CasConflict.actual`) без лишнего `get_task` — им и
    повторяется попытка. Задача уже терминальна (на входе или гонка
    подвела туда же) — сообщается и завершается без ошибки (требование
    6), но не отменяет уборку хвостов ниже — `test_repeated_kill_finds_
    nothing_and_does_not_fail` (tests/test_kill_cleanup.py) требует, чтобы
    повторный kill на уже killed задаче всё равно доводил её до конца.
    """
    t = store.get_task(conn, task_id)
    target = t["target"] or config.DEFAULT_TARGET
    state = t["state"]
    if state not in TERMINAL_STATES:
        drift = fixation.ref_drift(conn, task_id)
        if drift is not None and drift.moved:
            _warn_moved_ref(conn, task_id, drift)
        else:
            _refuse_unsynced_docs(conn, task_id)
    _journal_tz_before_cleanup(conn, task_id, t["branch"], target)
    won = False
    while not won and state not in TERMINAL_STATES:
        try:
            store.set_state(conn, task_id, "killed", "operator",
                            expected_state=state,
                            detail=_kill_detail(reason))
            won = True
        except store.CasConflict as exc:
            state = exc.actual
    if not won:
        print(f"[{task_id}] уже {state} — kill не требуется")
    # Группа процессов записанного AC-2 агентного шага — ДО снятия lease
    # (AC-4): `lease.release_any` ниже уже не сможет прочитать pgid по
    # ещё живому держателю после того, как строка исчезнет.
    _group_kill_lease_step(conn, task_id)
    # SPEC 01M1NWCHVTYQ0M8PCJ1YJ2N78P, требование 6, AC-10: `kill` обязан
    # прервать НЕМЕДЛЕННО, включая живой отвязанный процесс цикла, если
    # тот ещё несёт lease. `holder_before` — снимок lease,
    # снятый ДО того, как `run_locked(force=True)` (вызыватель) уже
    # перезаписал строку СВОИМ pid/session — читать lease заново здесь
    # адресовало бы уже не тот процесс. Чужой host не трогаем — тем же
    # приёмом различения, что уже применяют `doctor.check_leases`/
    # `check_merge_lock`. Независимо от `_group_kill_lease_step` выше —
    # тот снимает группу АГЕНТСКОГО подпроцесса шага, эта ветка отдельно
    # снимает сам процесс цикла (`auto`/`run`), не входящий в ту группу.
    if (holder_before is not None
            and holder_before["hostname"] == socket.gethostname()
            and liveness._pid_alive(holder_before["pid"])):
        try:
            os.kill(holder_before["pid"], signal.SIGKILL)
        except OSError:
            pass
    # kill обязан снять lease задачи безусловно, «любым путём» (SPEC
    # 01M1G..., требование 3, AC-6) — независимо от того, взял ли его
    # штатный `run_locked` этого же вызова «с нуля» (тот отпустил бы его
    # сам только в этом случае, см. `orchestrator/lease.py`).
    lease.release_any(conn, task_id, "orchestrator", "kill: lease снят")
    if won:
        _commit_closing(conn, task_id)
    cleanup_killed_task(conn, task_id, t["branch"])
    if won:
        cleanup_project_remote(conn, task_id, t["branch"])
    return won


def _warn_moved_ref(conn, task_id: str, drift) -> None:
    """`kill` при голове ссылки документов, сдвинутой мимо пульта (SPEC
    01M41AB597B330P2RCXCMVRZPE, требование 10): экстренная остановка не
    ждёт `approve <sha>` и закрывает задачу, но переход и коммит закрытия
    поверх подмены не пишут ничего (`store.set_state`, `snapshot.
    commit_closing`), а подменённая голова остаётся в ссылке для разбора.
    Сверка с `origin` (`_refuse_unsynced_docs`) не делается: она досылает
    локальную ссылку в `origin`, то есть опубликовала бы подмену, а коммита
    закрытия, ради которого она стоит, здесь не будет."""
    store.journal(conn, task_id, "operator", fixation.DOCS_REF_INCIDENT_ACTION,
                  f"kill без коммита закрытия: {drift.text()}; подменённая "
                  f"голова {drift.head} сохранена в "
                  f"refs/artifacts/{task_id} для разбора")
    print(f"[{task_id}] ВНИМАНИЕ: {fixation.DOCS_REF_INCIDENT_ACTION} — "
          f"{drift.text()}\n  задача закрывается без паспорта и коммита "
          f"закрытия, фиксация не меняется; подменённая голова {drift.head} "
          f"сохранена в refs/artifacts/{task_id} для разбора")


# Литерал действия журнала отказа закрытия при документах, не совпадающих с
# `origin` (ADR-0021 п.3).
KILL_UNSYNCED_JOURNAL_ACTION = "kill отклонён: документы не совпадают с origin"


def _refuse_unsynced_docs(conn, task_id: str) -> None:
    """Закрытие отказывает, пока `refs/artifacts/<id>` не совпадает с
    `origin` (ADR-0021 п.3): коммит закрытия поверх истории, которой нет в
    `origin` (или которая там другая), закрыл бы задачу с документами,
    существующими только в одном месте. Отказ — до смены состояния: задача
    остаётся, где была, ссылка не меняется."""
    from . import artifact_branch
    refusal = artifact_branch.origin_sync_refusal(task_id)
    if refusal is None:
        return
    text = (f"[{task_id}] kill {refusal}\n  задача не закрыта; сведи "
            f"{artifact_branch.branch_name(task_id)} с origin и повтори: "
            f"artel.py kill {task_id}")
    store.journal(conn, task_id, "operator", KILL_UNSYNCED_JOURNAL_ACTION,
                  refusal)
    sys.exit(text)


def _closing_outcome(conn, task_id: str) -> str:
    """Исход коммита закрытия — ФАКТИЧЕСКОЕ состояние задачи из БД (SPEC
    01M3KE80RNBCY9G48E75Z14TA7, требование 1; ADR-0021 п.3: признак
    «закрыта» — по БД), а не литерал «killed»: этот узел зовут ОБА пути
    закрытия — `kill` (`_cmd_kill` выше) и мерж (`fsm_merge_gate.
    _commit_closing`). Состояние на момент вызова уже записано на обоих
    путях: `_finalize_done_state` пишет `done` ДО коммита закрытия,
    `_cmd_kill` — `killed` до своего.

    Состояние не терминальное (строка БД читается, но задача почему-то не
    закрыта) — прежний `"killed"`: коммит закрытия зовут только пути
    закрытия, и молчаливое «done» на незакрытой задаче было бы хуже.
    """
    t = store.get_task(conn, task_id)
    state = t["state"] if t is not None else ""
    return state if state in TERMINAL_STATES else "killed"


def _commit_closing(conn, task_id: str, merge_sha: str = "",
                    applied_appendices=None) -> None:
    """Коммит закрытия (`snapshot.commit_closing`) — один узел на оба пути
    закрытия, `kill` и мерж; канарейка идёт тем же потоком (ADR-0021
    п.13). `merge_sha`/`applied_appendices` передаёт путь мержа — RETRO
    закрытия несёт sha мержа и перечень приложений PLAN (SPEC
    01M4M67SGNEYMN9F1C7XVX24XE, требование 3). Отложенный импорт:
    `snapshot` -> `retro` -> `cleanup` — прямой импорт на уровне модуля
    замкнул бы этот же файл в цикл."""
    from . import snapshot
    note = snapshot.commit_closing(conn, task_id, _closing_outcome(conn, task_id),
                                   merge_sha=merge_sha,
                                   applied_appendices=applied_appendices)
    print(f"  {note}")
