"""Переходы автомата: advance по артефактам, approve/reject Оператора.

Обработчики `cmd_advance` по состояниям — `orchestrator/fsm_advance.py`;
тело гейта `merge_gate` (конфликты, ожидание CI, сам merge) —
`orchestrator/fsm_merge_gate.py`; побочные эффекты после merge (карта
кодовой базы, RETRO) — `orchestrator/fsm_postmerge.py`; автогейт
acceptance — `orchestrator/fsm_autogate.py` (T091, декомпозиция
диспетчеров fsm/runner). Здесь остаются диспетчеры (`cmd_advance`,
`cmd_approve`, `cmd_reject`) и узлы, общие для нескольких состояний/
гейтов (сверка свежести ветки, чтения с ветки задачи, guard-отказ).
"""
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts import guard

from . import (acceptance, artifact_branch, artifact_source, artifacts, config, fixation,
              github_adapter, gitcmd, lease, review, store, targets,
              workspace, yamlmini)

# Буквальная строка «сигналов нет» (ANSWER-2, tasks/01M1KS8K9RXWHX2PW3ZKB0P903,
# AC-12) — снимок секции «Оценка объёма и деление» пустой/отсутствующей,
# не «неизвестно» (NULL остаётся зарезервирован за «снимок не удался/
# задача старше колонки», `report.py` различает эти два случая).
SPLIT_ASSESSMENT_NONE = "сигналов нет"

# Своя копия константы (та же строка, что и в orchestrator/fsm_postmerge.py
# и orchestrator/brief.py — каждый модуль держит её по своему поводу):
# здесь она нужна авторазрешению конфликта подтяжки (`_auto_resolve_map_
# conflict`), там — регенерации/коммиту карты после merge.
MAP_REL = "docs/codebase-map.md"

# Action журнала статуса CI, прочитанного в ветке `verifying` — общий
# текст с `orchestrator/auto.py` (SPEC T086, требование 1):
# `_verifying_poll_note` там ищет среди записей журнала ИМЕННО этот
# action, чтобы различить красный CI от «нет ответа»/«идёт», не опрашивая
# `ci.verifying_status` второй раз за ту же итерацию цикла.
VERIFYING_STATUS_ACTION = "статус CI ветки (verifying)"


def _verifying_elapsed_seconds(updated_at: str) -> float:
    """Секунды с момента входа в `verifying` (SPEC T086, требование 3):
    `updated_at` последнего `set_state -> verifying` пишется с точностью
    до микросекунд (`store.set_state`) — не секундным форматом `store.
    now()` (`liveness._age_seconds` парсит именно его для heartbeat).
    Второй формат разбирается тоже: строка `tasks.updated_at`, оставшаяся
    от завода задачи (`store.insert_task` пишет её через `now()`), не
    успевает смениться `set_state`-переходом там, где тест заводит
    `verifying` в обход самих переходов FSM прямой записью в БД.
    """
    try:
        entered = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S.%fZ")
    except ValueError:
        entered = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%SZ")
    return (datetime.now(timezone.utc) - entered.replace(
        tzinfo=timezone.utc)).total_seconds()


def _maybe_ensure_draft_mr(conn, task_id: str) -> None:
    """Draft MR — побочный эффект каждого входа в `in_dev` (SPEC T079,
    требование 1); идемпотентность несёт `github_adapter.ensure_draft_mr`
    сама (колонка `draft_mr_created`), так что этот узел зовётся
    одинаково с любой из точек входа в `in_dev`, не только с первой.
    """
    t = store.get_task(conn, task_id)
    github_adapter.ensure_draft_mr(conn, task_id, t)


# --- сверка свежести ветки до гейта (SPEC T051) ---------------------------

def _conflicting_files(wt_path) -> list[str]:
    """Файлы с неразрешённым конфликтом в worktree после неудачного `git
    merge` (SPEC T067, требование 1) — тем же приёмом, что уже читает
    `_handle_merge_conflict` для ДРУГОГО merge (main <- ветка задачи,
    T052), только здесь список нужен ДО решения абортить или разрешать
    самому, а не только для диагностики.

    Пустой список — git не ответил осмысленно (заглушки без реального
    git, инфраструктурный сбой самой команды `diff`) — вызывающий код
    в этом случае не находит РОВНО `[MAP_REL]` и уходит в прежний
    безусловный abort+escalate (требование 4, тот же вырожденный случай
    деградации, что у остальных примитивов подтяжки).
    """
    res = gitcmd.in_repo(wt_path, "diff", "--name-only", "--diff-filter=U")
    if res is None or res.returncode != 0:
        return []
    return sorted(set(res.stdout.split()))


def _auto_resolve_map_conflict(conn, task_id: str, wt_path, source_branch: str) -> bool:
    """Единственный конфликтующий файл — `docs/codebase-map.md` (SPEC
    T067, требования 1-2, 5): `checkout --theirs` + регенерация
    генератором НА СЛИТОМ дереве worktree задачи (`cwd=wt_path`, не
    `config.ROOT` — карта, которую сверяют критерии приёмки, это карта
    ВЕТКИ задачи, не главной копии пульта) + `add` + `commit`, который
    и завершает merge, начатый вызывающим кодом. `source_branch` — имя
    ветки, из которой шла подтяжка (REVIEW.md R3-F1: коммит-сообщение
    называет реальный источник, не жёсткий `config.MAIN_BRANCH`).

    `True` — merge завершён, подтяжка продолжается точно так же, как
    обычная удачная подтяжка без конфликта (требование 2); `False` —
    любой шаг не удался (checkout/регенерация/add/commit) — merge НЕ
    завершён, вызывающий код обязан сам сделать `git merge --abort` и
    эскалировать тем же путём, что и неразрешаемый конфликт (требование
    5, AC-5): здесь нарочно нет своего abort — единая точка отката
    ближе к месту, где решение «разрешать или нет» уже принято.
    """
    checkout = gitcmd.in_repo(wt_path, "checkout", "--theirs", MAP_REL)
    if checkout is None or checkout.returncode != 0:
        return False
    try:
        regen = subprocess.run(["python3", "scripts/codebase_map.py"],
                               cwd=wt_path, capture_output=True, text=True)
    except OSError:
        return False
    if regen.returncode != 0:
        return False
    added = gitcmd.in_repo(wt_path, "add", MAP_REL)
    if added is None or added.returncode != 0:
        return False
    commit = gitcmd.in_repo(wt_path, "commit", "-m",
                            f"{task_id}: подтяжка {source_branch}")
    if commit is None or commit.returncode != 0:
        return False
    store.journal(
        conn, task_id, "orchestrator",
        "конфликт подтяжки: карта авторазрешена регенерацией",
        f"{MAP_REL} — единственный конфликтующий файл, разрешён "
        f"checkout --theirs + регенерация scripts/codebase_map.py на "
        f"слитом дереве worktree задачи")
    return True


def _origin_main_source(target_name: str) -> tuple[str, str] | None:
    """(remote, ветка) main конкретного target'а (SPEC
    01M1NBWPKNBXP9ZXXQDJM7AXPJ, требование 5, AC-10, ANSWER-1): источник
    сверки/подтяжки берётся из конфигурации target задачи, не хардкожен
    как `origin` пульта. `None` — запись target'а не читается (файл или
    сама запись не годны): молчаливый откат на литерал `"origin"` был бы
    ОПАСНЕЕ обычной деградации «git не ответил» — сравнил/смержил бы
    задачу внешнего target против совсем другого репозитория (main
    пульта), не «ничего не сделал»; вызывающий код обязан деградировать
    так же, как при неответившем git (AC-8: расхождение/поломка
    конфигурации не имеет права двигать ни сверку, ни merge).

    Self-target (`config.DEFAULT_TARGET`) — прежний литерал `"origin"`
    (её пульт всегда несёт именно такой remote, ANSWER-1 «для self-target
    — origin пульта») БЕЗ обращения к `targets.yaml`: лёгкие песочницы
    этой сверки (`tests/test_branch_freshness_gate.py`, приёмочные тесты
    задачи) намеренно не заводят `config.TARGETS` для self-target
    сценария — чтение файла здесь безусловно сломало бы их (требование 4,
    AC-9). Любой другой target — `targets.target(name)["url"]` (адрес
    репозитория) как remote, её же `["base"]` как ветка: `targets.yaml`
    не несёт отдельного поля «имя remote» (протокол git одинаково
    принимает и имя настроенного remote, и голый URL вторым аргументом
    `git fetch`/`git merge`), а `["url"]` — уже существующее поле записи
    (ADR-0003 п.2), в точности «конфигурация target», которую требует
    AC-10.
    """
    if target_name == config.DEFAULT_TARGET:
        return "origin", config.MAIN_BRANCH
    try:
        entry = targets.target(target_name)
    except targets.TargetsError:
        return None
    return entry["url"], entry["base"]


def _origin_main_sha(target_name: str) -> str | None:
    """sha текущего HEAD main конкретного target'а на её удалённом
    источнике (SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-1/AC-2/AC-8/AC-10) —
    своя копия узла `orchestrator/fsm_merge_gate.py::_origin_main_sha`
    (тот же приём дублирования по модулю, что уже несёт `MAP_REL` в
    начале файла): `fsm_merge_gate` импортирует `fsm`, обратный импорт
    завёл бы цикл. `_origin_main_sha` там остаётся про main АРТЕЛИ
    конкретно (плотницкий merge Stage0 — только self-target/`operator`
    гейт), эта — про main ЗАДАННОГО target'а (`_origin_main_source`).

    `git fetch` пишет только в объектную базу и `FETCH_HEAD` репозитория,
    в котором исполнен (`config.ROOT` — здесь всегда так, `gitcmd.git`,
    не `in_repo`), никогда в локальный `refs/heads/<MAIN_BRANCH>` — ни
    рабочее дерево, ни HEAD `config.ROOT`, ни зафиксированный там пин не
    задеты (AC-8). Возврат — конкретный sha, не литерал `"FETCH_HEAD"`:
    merge ниже идёт в ДРУГОМ git-worktree (worktree задачи), а начиная с
    git 2.5 `FETCH_HEAD` — файл, приватный для каждого worktree (как
    HEAD/index) — литерал `"FETCH_HEAD"` там не резолвится в то, что
    только что зафетчил `config.ROOT`. `None` — git не ответил на fetch
    или на `rev-parse`, либо конфигурация target'а не читается
    (`_origin_main_source`) — тот же вырожденный случай, что у остальных
    примитивов оркестратора: сверка ниже деградирует на «ничего не
    делать».
    """
    source = _origin_main_source(target_name)
    if source is None:
        return None
    remote, branch = source
    fetch = gitcmd.git("fetch", "-q", remote, branch)
    if fetch is None or fetch.returncode != 0:
        return None
    res = gitcmd.git("rev-parse", "FETCH_HEAD")
    return res.stdout.strip() if res is not None and res.returncode == 0 else None


def _pull_main_or_escalate(conn, task_id: str, t, state: str) -> str:
    """Сверка свежести ветки задачи на входе в гейт (SPEC T051, требования
    1-7, 10; ADR-0006 п.2; переведена на origin — SPEC
    01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-1..AC-4/AC-8) и, начиная с T053
    требование 5, ВНУТРИ окна `merge_gate` под мьютексом merge — один и
    тот же узел для всех трёх точек сверки (`in_dev -> review`,
    `acceptance -> merge_gate`, `merge_gate -> done`).

    Сверка и merge идут против main НА УДАЛЁННОМ ИСТОЧНИКЕ target'а
    задачи (`_origin_main_sha`/`_origin_main_source`, требование 5,
    AC-10), НЕ против локального `config.MAIN_BRANCH` (пина главной
    копии): между двумя мержами пин двигает только отдельная
    операторская команда `pin-update` (A7), и решение по устаревшему
    пину ложно отвечало «ветка не отстала», хотя origin ушёл вперёд
    (инцидент 04.09, SPEC «Контекст»). Для self-target это буквально
    `origin` пульта и `config.MAIN_BRANCH` (ANSWER-1); для любого другого
    target — `url`/`base` его записи в `targets.yaml`. `config.
    MAIN_BRANCH` остаётся только ИМЕНЕМ ветки self-target, которую
    фетчим и с которой сравниваем/мержим, не источником сравнения/merge
    самим по себе.

    Возврат — один из четырёх исходов:
    - `"escalated"` — переход уже отклонён: задача уже эскалирована
      (состояние и диагностика уже записаны через `store.set_state`,
      требования 5-6); вызывающий код обязан немедленно вернуться, не
      выполняя сам переход;
    - `"refused"` — переход отклонён именованным отказом «планка не
      найдена в источнике» (SPEC 01M1R9YEK08XEQWBFX0929WFVJ, AC-3):
      артефактная ветка не несёт `tasks/<id>/acceptance_tests/`, а
      `tests_writing` не пропущена легитимно (`skip_tests` не задан в
      SPEC и SPEC несёт AC-разметку) — состояние НЕ меняется (задача
      остаётся там, где была), в отличие от `"escalated"`; вызывающий
      код обязан вернуться так же, как и на `"escalated"`;
    - `"fresh"` — ветка не отстала от main артели на origin (требование
      7: поведение перехода прежнее байт-в-байт при отсутствии
      отставания);
    - `"pulled"` — подтяжка прошла и приёмочные тесты, материализованные
      из артефактной ветки задачи (не из worktree кодовой ветки, SPEC
      01M1R9YEK08XEQWBFX0929WFVJ, AC-1/AC-2/AC-10), зелёные (в том числе
      вырожденный случай легитимно пропущенной `tests_writing`, AC-5 —
      планки нет в артефактной ветке, но это не отказ). Точки `in_dev ->
      review`/`acceptance -> merge_gate` обе продолжают штатный переход
      одинаково что при `"fresh"`, что при `"pulled"` (T051, не различали
      их и раньше — общий `bool`); третья точка (`merge_gate -> done`,
      T053) обязана различать их сама: после `"pulled"` merge в этом же
      вызове НЕ выполняется (SPEC T053, требование 5) — сдвинутый головой
      ветки sha делает зафиксированный снимок невалидным для merge
      (инвариант 19 не ослабляется).

    Merge — единственный вне `merge_gate`, разрешённый ADR-0006 п.2: в
    worktree ЗАДАЧИ (`gitcmd.in_repo`, форма `-C`), вливает
    зафетченный origin-sha main артели, ветку задачи в аргументах не
    упоминает и не трогает main ни байтом (требование 10) — не rebase
    (требование 3), существующие sha ветки остаются валидными предками.

    `_origin_main_sha()` вернула вырожденное значение (`None`/пустая
    строка — git/fetch/rev-parse не ответили, либо конфигурация
    target'а не читается; песочницы без реального git: `fake_git` и
    аналоги, требование 9) — функция возвращает `"fresh"` немедленно, не
    вызывая `commits_behind`/`merge` вовсе (REVIEW.md R1-F1, итерация 1):
    прежде на этом месте подставлялся литерал `"FETCH_HEAD"`, который
    честным no-op'ом НЕ является — `FETCH_HEAD` в `config.ROOT` почти
    всегда несёт результат чужого предыдущего фетча, а внутри worktree
    задачи резолвится в СВОЙ приватный `FETCH_HEAD` (git 2.5+), не в
    только что зафетченный `config.ROOT`. Ранний возврат — тот же
    вырожденный случай деградации, что и у остальных git-примитивов
    оркестратора: молча ничего не делает, как и `not behind` (ветка не
    отстала).

    Конфликт merge, где единственный конфликтующий файл —
    `docs/codebase-map.md` (SPEC T067), разрешается здесь же сам, не
    эскалируя: `_conflicting_files` + `_auto_resolve_map_conflict`. Любой
    другой конфликт (карта вместе с другим файлом, без карты вовсе, или
    авторазрешение само не удалось) — прежнее поведение T051/T052
    байт-в-байт: `git merge --abort` + `"escalated"`.
    """
    branch = t["branch"]
    target_name = t["target"] or config.DEFAULT_TARGET
    source = _origin_main_source(target_name)
    source_branch = source[1] if source is not None else config.MAIN_BRANCH
    base = _origin_main_sha(target_name)
    if not base:
        # Вырожденная _origin_main_sha — см. докстринг выше (R1-F1):
        # ранний выход, не литерал "FETCH_HEAD".
        return "fresh"
    behind = gitcmd.commits_behind(branch, base=base)
    if not behind:
        return "fresh"

    wt_path, error = workspace.ensure(task_id, branch)
    if error is not None:
        store.set_state(
            conn, task_id, "escalated", "fsm", expected_state=state,
            detail=f"подтяжка {source_branch} отменена: worktree "
            f"задачи не создан — {error}")
        return "escalated"

    merge = gitcmd.in_repo(wt_path, "merge", "--no-ff", base,
                           "-m", f"{task_id}: подтяжка {source_branch}")
    if merge is None or merge.returncode != 0:
        resolved = False
        if merge is not None:
            files = _conflicting_files(wt_path)
            if files == [MAP_REL]:
                resolved = _auto_resolve_map_conflict(conn, task_id, wt_path,
                                                       source_branch)
        if not resolved:
            abort = gitcmd.in_repo(wt_path, "merge", "--abort")
            note = merge.stderr.strip()[:500] if merge is not None else "git не ответил"
            if abort is None or abort.returncode != 0:
                note += (f"; git merge --abort не удался: "
                        f"{abort.stderr.strip()[:200] if abort is not None else 'git не ответил'}")
            store.set_state(
                conn, task_id, "escalated", "fsm", expected_state=state,
                detail=f"конфликт подтяжки {source_branch} в ветку "
                f"{branch}: {note}")
            return "escalated"

    # Планка — из АРТЕФАКТНОЙ ветки задачи, не из worktree кодовой ветки
    # (SPEC 01M1R9YEK08XEQWBFX0929WFVJ, требование 1, AC-1/AC-2): worktree
    # кодовой ветки роли чистят по ходу шага (регрессия №9) — прогон по
    # НЕЙ трактовал пустой/непрочитанный каталог как красную планку и
    # эскалировал «приёмочные тесты красные после подтяжки main», хотя
    # тестов там попросту никогда не было (SPEC «Контекст», инцидент
    # 01M1QHQ277PQQA894X97RVEX9Y). `materialize_from_branch` — тот же узел,
    # что уже несёт автогейт acceptance (`fsm_autogate.py`).
    artifact_branch_name, _ = artifact_source.resolve(conn, task_id)
    # hotfix(аварийный режим) 05.09, регрессия №14 флоу A7 (легализация —
    # ТЗ tz-legalize-acceptance-cwd-hotfix.md, п.3): для self-target с
    # живым worktree на ветке задачи планка материализуется В worktree
    # (`artifact_branch.materialize_task_dir` — тот же узел, что старт
    # шага роли `runner.py` и merge_gate), а прогон идёт с cwd=worktree.
    # Из временного каталога планка через `sys.path.insert(parents[3])`
    # и пути «три уровня вверх от файла» попадала в случайный путь:
    # импорт уходил в cwd=ROOT (код пина), файловые пути (`tests/…`)
    # не находились вовсе (01M1RR1PZC, AC-6). Внешний target и песочницы
    # без worktree — прежний временный каталог.
    code_root = None
    cleanup_root = None
    if (t["target"] == config.DEFAULT_TARGET
            and workspace.on_task_branch(task_id, t["branch"]) is True):
        code_root = workspace.path(task_id)
        if artifact_branch.materialize_task_dir(task_id, code_root):
            plank_root = code_root / "tasks" / task_id
        else:
            plank_root = acceptance.materialize_from_branch(
                task_id, artifact_branch_name)
            cleanup_root = plank_root
    else:
        plank_root = acceptance.materialize_from_branch(task_id,
                                                         artifact_branch_name)
        cleanup_root = plank_root
    try:
        if not (plank_root / "acceptance_tests").is_dir():
            # Планка не найдена в артефактной ветке — легитимно ТОЛЬКО
            # когда SPEC пропустила tests_writing (`skip_tests` задан) или
            # не несёт AC-разметки вовсе (AC-5, вырожденный случай, не
            # тронутый этой задачей); иначе — именованный отказ AC-3, не
            # молчаливый зелёный проход и не эскалация AC-4 (та остаётся
            # только для планки, которая реально прогналась и упала).
            #
            # SPEC.md читается общим узлом `_read_branch_text_or_refuse`
            # (не голым `gitcmd.show`, REVIEW.md R1-F1, итерации 1-3):
            # SPEC.md — обязательный артефакт, на артефактной ветке живой
            # задачи он есть всегда, поэтому сбой чтения (git не ответил,
            # ветка недоступна, гонка с материализацией) сам по себе уже
            # ненормален и не должен схлопываться в дефолтный `meta={}` →
            # `requires_ac_markup(...) == False` → молчаливый `"pulled"`
            # — узел уже журналирует и печатает именованный отказ.
            spec_text = _read_branch_text_or_refuse(
                conn, task_id, artifact_branch_name, "SPEC.md")
            if spec_text is None:
                return "refused"
            meta = yamlmini.frontmatter(spec_text) or {}
            if guard.requires_ac_markup(meta):
                detail = (
                    f"планка не найдена в источнике: артефактная ветка "
                    f"{artifact_branch_name} не несёт tasks/{task_id}/"
                    f"acceptance_tests/, а tests_writing не пропущена "
                    f"легитимно (skip_tests не задан в SPEC)")
                store.journal(
                    conn, task_id, "fsm",
                    "переход отклонён: планка не найдена в источнике",
                    detail)
                print(f"[{task_id}] переход отклонён: {detail}")
                return "refused"
            return "pulled"
        green, tail = acceptance.run(plank_root, code_root=code_root)
    finally:
        if cleanup_root is not None:
            shutil.rmtree(cleanup_root, ignore_errors=True)

    if not green:
        store.set_state(
            conn, task_id, "escalated", "fsm", expected_state=state,
            detail=f"приёмочные тесты красные после подтяжки "
            f"{source_branch} (слияние сохранено, откат не "
            f"выполняется):\n{tail}")
        return "escalated"

    return "pulled"


def guard_refuses(conn, task_id: str, path: Path, text: str | None = None) -> bool:
    """Прогон guard по артефакту-условию перехода; True — переход отменён.

    Структуру артефакта проверяет код на самом переходе, а не роль по
    договорённости и не CI задним числом (SPEC T017, требование 5): задачу
    двигают статусы артефактов, значит артефакт со сломанной структурой
    двигать её не должен. Отказ — журнал, названный файл и все причины
    списком: разбирать его будет Оператор, и трейсбека ему тут не надо.

    `text` — уже прочитанное содержимое (с ВЕТКИ задачи при чужом чекауте
    рабочей копии, SPEC T031) вместо чтения `path` с диска; `None` (по
    умолчанию) — прежнее поведение, `guard.check(path)`.
    """
    errors = guard.check(path) if text is None else guard.check_content(str(path), text)
    if not errors:
        return False
    store.journal(conn, task_id, "fsm", "переход отклонён guard'ом",
                  "; ".join(errors))
    print(f"[{task_id}] переход отклонён: {path.name} не проходит guard")
    for error in errors:
        print(f"  - {error}")
    print(f"  дальше: почини артефакт и повтори artel.py advance {task_id}")
    return True


def _dirty_refuses(conn, task_id: str, target: str, artifact_name: str) -> bool:
    """Отказ по грязной копии артефакта-условия перехода; True — переход
    отменён (SPEC T033, требование 1 — симметрия с `approve`).

    Та же сверка, что и `confirm_fixation` у `approve`: `fixation.read()`,
    не `fix()` — проверка не имеет права коммитить чужой WIP как побочный
    эффект сравнения (REVIEW.md T021, замечание 1 итерации 2). `current`
    пустой (git не ответил, коммитов ещё нет) — сверять не с чем, тот же
    вырожденный случай, на котором `confirm_fixation` пропускает дальше;
    старые (не-git) песочницы `advance` продолжают работать без изменений.

    Только догфуд (`target == config.DEFAULT_TARGET`, PLAN «Риски»):
    для внешнего target артефактный репозиторий коммитит сам оркестратор
    целиком уже ПОСЛЕ решения перейти (`fixation._fix_external`, вызов
    из `store.set_state`) — до перехода он закономерно не закоммичен,
    это не забытый коммит роли (та ADR-0003 §4 workspace вообще не
    коммитит сама), и наивная сверка отказывала бы там всегда.
    """
    if target != config.DEFAULT_TARGET:
        return False
    current, clean = fixation.read(task_id, target)
    if not current or clean:
        return False
    detail = (f"{artifact_name} не закоммичен — роль обязана коммитить "
              f"артефакты (скил conventions-core); закоммить и повтори advance")
    store.journal(conn, task_id, "fsm",
                  "переход отклонён: рабочая копия артефактов грязная", detail)
    print(f"[{task_id}] переход отклонён: {detail}")
    return True


def _read_branch_text_or_refuse(conn, task_id: str, branch: str,
                                rel_name: str) -> str | None:
    """Текст `tasks/<id>/<rel_name>` С ВЕТКИ задачи; `None` — дерево на
    чужой ветке, а файл там не прочитан — отказ уже журналирован и
    напечатан (SPEC T031, T047: общий узел для мест, где отсутствие
    файла на ветке — не легитимное «ещё не готово», а именованный отказ,
    прецедент — прежнее инлайн-чтение PLAN.md в `in_dev`).

    Звать только когда `gitcmd.on_foreign_branch(branch)` истинно — сама
    функция это не проверяет, только читает и оформляет отказ.
    """
    text, reason = gitcmd.show(branch, f"tasks/{task_id}/{rel_name}")
    if text is None:
        detail = (f"дерево не на ветке задачи {branch} — {rel_name} "
                  f"ветки не прочитан ({reason})")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: дерево не на ветке задачи", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
    return text


def _snapshot_split_assessment(conn, task_id: str, t) -> None:
    """Заполняет `diff_bytes`/`split_assessment` на входе в `merge_gate`
    (tasks/01M1KS8K9RXWHX2PW3ZKB0P903, требование 6; ANSWER-1, ANSWER-2)
    — материал для калибровки порогов `artel report`, не условие
    перехода: сбой git по любой из двух колонок оставляет её NULL и НЕ
    отказывает переходу (в отличие от `fsm_advance._capacity_gate_
    refuses`, которая именно отказывает на том же diff).

    Diff — только self target, тем же доводом, что и `_capacity_gate_
    refuses`: `git diff` в `config.ROOT` не видит код внешнего target.
    Секция «Оценка объёма и деление» читается с АРТЕФАКТНОЙ ветки —
    `tasks/<id>/` живёт только там (A7, `artifact_source.resolve`),
    независимо от target.
    """
    if store.task_target(conn, task_id) == config.DEFAULT_TARGET:
        diff, _, reason = review.git_diff_part(config.MAIN_BRANCH, t["branch"])
        if not reason:
            store.update_task(conn, task_id, diff_bytes=len(diff.encode("utf-8")))

    branch, _ = artifact_source.resolve(conn, task_id)
    spec_text, _ = gitcmd.show(branch, f"tasks/{task_id}/SPEC.md")
    if spec_text is not None:
        body = guard.section_body(spec_text, "Оценка объёма и деление").strip()
        store.update_task(conn, task_id,
                          split_assessment=body or SPLIT_ASSESSMENT_NONE)


def _answer_file_count(conn, task_id: str, tdir: Path) -> int | None:
    """Число `ANSWER-*.md` задачи — с ВЕТКИ-ИСТОЧНИКА `tasks/<id>/`
    (`artifact_source.resolve`, SPEC T031/T047/T094 требование 10, тот же
    приём, что и остальные чтения этого файла в модуле), если она чужая
    рабочей копии пульта, иначе с диска. `None` — git не ответил на чужой
    ветке (нельзя посчитать — не значит «ноль», вызывающий код решает,
    как трактовать).

    Считает файлы, не разбирает номер `n`: гейту возврата (`_cmd_approve`)
    достаточно знать, что число ANSWER-файлов ВЫРОСЛО относительно
    зафиксированного на эскалации снимка (`answer_baseline`), не какой
    именно номер у нового файла.
    """
    branch, foreign = artifact_source.resolve(conn, task_id)
    if foreign:
        paths = gitcmd.ls_tree_files(branch, f"tasks/{task_id}")
        if paths is None:
            return None
        return sum(1 for p in paths
                  if Path(p).name.startswith("ANSWER-")
                  and Path(p).name.endswith(".md"))
    return len(list(tdir.glob("ANSWER-*.md")))


def _answer_baseline_or_refuse(conn, task_id: str, tdir: Path) -> int | None:
    """Снимок числа ANSWER-*.md на момент эскалации — тем же приёмом
    отказа, что `_read_branch_text_or_refuse` (SPEC T031, T047): `None`
    от `_answer_file_count` — git не ответил на чужой ветке, а не «файлов
    ноль» — молчаливое схлопывание в `or 0` замаскировало бы именно тот
    класс сбоя, от которого рядом стоящий код (`q_paths is None` и
    остальные ветки этого модуля) отказывает громко (REVIEW T075
    итерация 1, замечание minor). Возврат `None` — отказ уже
    журналирован и напечатан, переход обязан не эскалировать в этот
    момент, а не эскалировать с недостоверным `baseline=0`."""
    count = _answer_file_count(conn, task_id, tdir)
    if count is None:
        branch, _ = artifact_source.resolve(conn, task_id)
        detail = (f"дерево не на ветке задачи {branch} — число "
                  f"ANSWER-*.md не посчитано, эскалация отложена")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: дерево не на ветке задачи", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
    return count


def _tests_writing_ac_state(conn, task_id: str, branch: str,
                            tdir: Path) -> tuple[set, dict, list[str]] | None:
    """(тестировано, пометки, ошибки трассируемости) на выходе из
    `tests_writing`; `None` — переход отклонён (уже журналирован).

    Рабочее дерево точно на чужой ветке (`gitcmd.on_foreign_branch`, SPEC
    T031, AC-3) — SPEC.md и acceptance_tests/ читаются с ВЕТКИ задачи
    (`git show`/`git ls-tree`), не с рабочей копии; иначе — прежний путь
    через диск (`guard.scan_acceptance_tests`/`acceptance_traceability_errors`),
    не тронутый T031: оба пути считают одним и тем же ядром
    (`guard.scan_ac_content`/`traceability_errors_from_content`), так что
    результат не расходится по источнику файлов, только по тому, где их
    искать.

    `errors` несёт ошибки трассируемости AC (T023), ошибки маркера
    красноты (`guard.redness_marker_errors_from_files`/`scan_redness_markers`,
    SPEC T064) и ошибки образца формата идентификатора задачи
    (`guard.id_format_sample_errors`/`scan_id_format_samples`, SPEC
    01M1H186VEVG6NF40YKH1338MD) — единственное место, где все три проверки
    подключены к выходу именно из `tests_writing`: задача, чьё состояние
    это состояние уже прошло, сюда больше не попадает (обратная
    совместимость T064, требование 4, — структурно, через
    однонаправленность FSM).
    """
    if not gitcmd.on_foreign_branch(branch):
        tested, markers = guard.scan_acceptance_tests(tdir)
        errors = guard.acceptance_traceability_errors(tdir)
        errors = errors + guard.scan_redness_markers(tdir)
        errors = errors + guard.scan_id_format_samples(tdir)
        return tested, markers, errors

    spec_rel = f"tasks/{task_id}/SPEC.md"
    tests_rel = f"tasks/{task_id}/acceptance_tests"
    spec_text, spec_reason = gitcmd.show(branch, spec_rel)
    paths = gitcmd.ls_tree_files(branch, tests_rel)
    if spec_text is None or paths is None:
        reason = spec_reason if spec_text is None else "acceptance_tests/ ветки не прочитан"
        detail = (f"дерево не на ветке задачи {branch} — {reason}, "
                  f"трассируемость AC не проверена")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: дерево не на ветке задачи", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        return None

    sources: list[str] = []
    redness_files: list[tuple[str, str]] = []
    id_format_files: list[tuple[str, str]] = []
    for p in paths:
        if not p.endswith(".py"):
            continue
        text, _ = gitcmd.show(branch, p)
        if text is None:
            continue
        sources.append(text)
        id_format_files.append((p, text))
        if Path(p).name.startswith("test_"):
            redness_files.append((p, text))
    meta = yamlmini.frontmatter(spec_text) or {}
    tested, markers = guard.scan_ac_content(sources)
    errors = guard.traceability_errors_from_content(spec_text, meta, tested,
                                                     markers)
    errors = errors + guard.redness_marker_errors_from_files(redness_files)
    errors = errors + guard.id_format_sample_errors(id_format_files)
    return tested, markers, errors


def cmd_advance(task_id: str, session_id: str | None = None) -> bool:
    """Единственная точка движения FSM: читает статусы артефактов.

    Возврат `True` — переход отклонён именно `guard_refuses()` (структура
    артефакта-условия сломана); `False` — любой другой исход, включая
    успешное продвижение и отказ по другой причине (артефакт не ready,
    грязная копия, вердикт не свежий и т.п., а также отказ по чужому
    живому lease — SPEC T044, требование 2). Различение нужно циклу
    `auto` (SPEC T034, требование 2): отказ guard'ом — гейт, на котором
    цикл обязан остановиться, а не звать `cmd_run` заново для того же
    состояния.

    Отказ по lease печатается и возвращает `False`, не бросает исключение
    (в отличие от остальных шести мутирующих команд, `sys.exit`): `advance`
    уже возвращает исход значением, а не исключением, во всех остальных
    ветках — новый способ отказа не должен становиться единственным,
    который `auto` не умеет поймать.

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease/путей на диске — иначе `advance <префикс>` строил `tdir` из
    несуществующего каталога и ложно отказывал переход (REVIEW T094
    итерация 1, замечание 1: живой репро — `cmd_advance` с уникальным
    префиксом печатал «PLAN.md не ready» на задаче с реально готовым
    PLAN.md).
    """
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    return bool(lease.run_locked(
        conn, task_id, session_id,
        lambda sid: _advance_with_refixation(conn, task_id),
        on_refusal="print"))


def _advance_with_refixation(conn, task_id: str) -> bool:
    """`_cmd_advance` + перефиксация sha на пути отклонённого перехода
    (SPEC T076, требования 1-5): переход отклонён (guard/условие не
    пройдено), задача осталась в исходном состоянии, а голова ветки
    сдвинулась ТОЛЬКО коммитами собственного шага задачи (роль легитимно
    коммитила артефакты внутри шага, T069/T073) — фиксация подтягивается
    на текущую голову тем же итогом, каким её обновил бы успешный
    переход, без эскалации «инцидент целостности» на следующем старте
    шага.

    Успешный переход (состояние сменилось) уже перефиксировал sha сам
    через `store.set_state` -> `record_fixation` — здесь нечего делать
    (требование 5, проверка `state` замыкает функцию раньше сравнения
    sha). Посторонний коммит вне окна шага, класс «грязная копия»
    (голова не сдвинулась вовсе) — `fixation.read()` не изменился или
    `refixate_after_rejected_transition` вернула `False` — фиксация
    остаётся прежней, `check_integrity` эскалирует как и раньше
    (требования 3-4).
    """
    t_before = store.get_task(conn, task_id)
    state_before = t_before["state"]
    entry_sha = t_before["fixed_sha"]
    result = _cmd_advance(conn, task_id)
    if entry_sha and store.get_task(conn, task_id)["state"] == state_before:
        target = store.task_target(conn, task_id)
        current, _clean = fixation.read(task_id, target)
        if current and current != entry_sha:
            fixation.refixate_after_rejected_transition(
                conn, task_id, target, entry_sha, current)
    return result


def _cmd_advance(conn, task_id: str) -> bool:
    t = store.get_task(conn, task_id)
    state = t["state"]
    tdir = config.TASKS / task_id
    target = store.task_target(conn, task_id)

    # Обработчик на состояние (SPEC T091): каждое состояние — своя
    # функция в orchestrator/fsm_advance.py, отсюда только выбор.
    # Импорт внутри функции, не на уровне модуля (тем же приёмом, что
    # `runner._cmd_run` уже применяет к `doctor`, ADR-0003 3ж): fsm.py
    # несёт узлы, общие для advance/approve/merge_gate, поэтому не
    # должен статически зависеть от модулей, которые сами зависят от
    # него.
    from . import fsm_advance
    handler = {
        "spec_writing": fsm_advance.spec_writing,
        "review": fsm_advance.review,
        "verifying": fsm_advance.verifying,
        "tests_writing": fsm_advance.tests_writing,
        "in_dev": fsm_advance.in_dev,
    }.get(state)
    if handler is None:
        print(f"[{task_id}] состояние {state} двигается через approve/reject/run")
        return False
    return handler(conn, task_id, t, tdir, target, state)


# Состояния, на входе в approve которых требуется подтверждённый sha
# (SPEC T021, требование 4): именно те 4 ветки, которые ниже что-то
# подтверждают, а не просто отвечают «нечего подтверждать».
APPROVE_NEEDS_SHA = ("spec_gate", "acceptance", "merge_gate", "escalated")

# Минимальная длина префикса sha, принимаемого `approve` вместо полного
# значения (SPEC «approve: полный sha в подсказках», требование 2; SPEC
# «Не входит» — фиксированная величина, не предмет настройки в этой
# задаче). Тот же порядок приёма, что и уникальный префикс id задач
# (T094, `store.resolve_task_id`), но сверяется с ОДНИМ эталоном —
# зафиксированным sha ЭТОЙ задачи, не поиском среди множества
# кандидатов: «уникальный» здесь про отсечение случайных опечаток
# короткой длиной, не про отсутствие коллизий.
APPROVE_SHA_PREFIX_MIN = 8


def confirm_fixation(conn, task_id: str, sha: str | None) -> bool:
    """True — approve может продолжить; False — сообщил и ждёт sha (не отказ).

    Живьём пересчитывает состояние через `fixation.read()`, а не читает
    `tasks.fixed_sha`: approve обязан сверяться с ТЕКУЩИМ состоянием
    (ADR-0003 п.15, «сверка на каждом следующем гейте... = сравнение sha +
    чистота рабочей копии»), а не с тем, что было на момент прошлого
    перехода. `read()`, не `fix()` (REVIEW.md T021, замечание 1 итерации
    2): approve — точка ПРОВЕРКИ, не фиксации, и не имеет права коммитить
    незакоммиченный WIP чужой задачи того же target как побочный эффект
    сравнения — легитимный коммит перехода случится позже, в
    `store.set_state` → `fix()`, если сверка сошлась.

    Фиксации нет (`sha == ""` — git не ответил, песочница без
    репозитория) — сверять не с чем: approve ведёт себя как до T021
    (требование 3, критерий 3). Расхождение sha или грязная копия —
    `sys.exit`, тем же стилем, что и отказ merge по красному CI ниже.

    Переданный `sha` короче `APPROVE_SHA_PREFIX_MIN` — именованный отказ
    про минимальную длину, ДО сравнения с зафиксированным (SPEC
    требование 3, AC-4): короткий отрезок совпал бы с зафиксированным
    почти всегда случайно, отличить опечатку от намеренного префикса
    нечем. От `APPROVE_SHA_PREFIX_MIN` и длиннее — `current.startswith
    (sha)` принимает как полный sha (совпадает с собой целиком), так и
    любой его префикс той же длины (SPEC требование 2, AC-2); не
    префикс — прежний отказ «не совпадает» с печатью зафиксированного
    sha (SPEC требование 3, AC-3), байт-в-байт как до этой задачи.
    """
    target = store.task_target(conn, task_id)
    current, clean = fixation.read(task_id, target)
    if not current:
        return True
    if sha is None:
        print(f"[{task_id}] approve требует sha — зафиксирован {current}")
        print(f"  повтори: artel.py approve {task_id} {current}")
        return False
    if len(sha) < APPROVE_SHA_PREFIX_MIN:
        reason = (f"sha {sha!r} короче минимальной длины "
                  f"{APPROVE_SHA_PREFIX_MIN} символов — approve принимает "
                  f"полный sha или его уникальный префикс от "
                  f"{APPROVE_SHA_PREFIX_MIN} символов")
        store.journal(conn, task_id, "operator", "approve отклонён", reason)
        sys.exit(f"[{task_id}] approve отклонён: {reason}")
    matches = current.startswith(sha)
    if not matches or not clean:
        reason = (f"sha {sha} не совпадает с зафиксированным {current}"
                  if not matches else
                  f"грязная копия артефактов при sha {current}")
        store.journal(conn, task_id, "operator", "approve отклонён", reason)
        sys.exit(f"[{task_id}] approve отклонён: {reason}")
    return True


def cmd_approve(task_id: str, sha: str | None = None,
               session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой (SPEC T044, требование 2).

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease/CAS (REVIEW T094 итерация 1, замечание 1)."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_approve(conn, task_id, sha, sid))


def _cmd_approve(conn, task_id: str, sha: str | None, sid: str) -> None:
    t = store.get_task(conn, task_id)
    state = t["state"]
    if state in APPROVE_NEEDS_SHA and not confirm_fixation(conn, task_id, sha):
        return
    if state == "spec_gate":
        # tests_writing до кода (SPEC T023, требование 1): пропускается
        # только явным skip_tests либо SPEC версии ниже 2 (без AC-разметки,
        # весь беклог T001–T022 — требование 7); иначе тесты пишутся
        # раньше, чем задачу увидит разработчик.
        #
        # Рабочее дерево точно на чужой ветке-источнике `tasks/<id>/`
        # (SPEC T031, AC-1; T094 требование 10 — ветка-источник теперь
        # артефактная ветка пульта для внешнего target, `artifact_source.
        # resolve`) — SPEC.md читается с НЕЁ (не молчаливый дефолт
        # «schema_version 1 без AC-разметки», журнал T030 ~17:35
        # 25.08.2026); иначе прежний путь через диск, не тронутый T031.
        # Чтение — общий узел `_read_branch_text_or_refuse` (T047, SPEC
        # T071): узел сам журналирует и печатает именованный отказ,
        # дублировать его текст отдельным `sys.exit` не нужно — `return`
        # останавливает попытку approve без смены состояния тем же
        # способом, что и остальные вызовы узла в `_cmd_advance`.
        branch, foreign = artifact_source.resolve(conn, task_id)
        if foreign:
            spec_text = _read_branch_text_or_refuse(conn, task_id, branch,
                                                     "SPEC.md")
            if spec_text is None:
                return
            meta = yamlmini.frontmatter(spec_text) or {}
        else:
            meta = artifacts.frontmatter(config.TASKS / task_id / "SPEC.md")
        # Значение zones (01M1NKVPD2A79PQ6K0JVV1B2Q1, AC-3) сохраняется тем
        # же моментом входа approve на spec_gate, что и budget/split_
        # assessment рядом — meta уже прочитана выше, поле отсутствует у
        # SPEC старых версий (`meta.get` даёт None, колонка тогда NULL).
        store.update_task(conn, task_id, zones=meta.get("zones"))
        skip_reason = meta.get("skip_tests")
        if skip_reason or not guard.requires_ac_markup(meta):
            detail = (f"тесты пропущены (skip_tests): {skip_reason}"
                      if skip_reason else
                      f"SPEC schema_version "
                      f"{meta.get('schema_version', 1)} — без AC-разметки, "
                      f"tests_writing недоступна")
            store.set_state(conn, task_id, "in_dev", "operator",
                            expected_state=state, detail=detail)
            _maybe_ensure_draft_mr(conn, task_id)
            print(f"  дальше: artel.py run {task_id}  (запуск разработчика)")
        else:
            store.set_state(conn, task_id, "tests_writing", "operator",
                            expected_state=state,
                            detail="гейт SPEC пройден — приёмочные тесты до кода")
            print(f"  дальше: artel.py run {task_id}  (запуск test_author)")
    elif state == "acceptance":
        # Сверка свежести ветки до гейта (SPEC T051, требования 1, 4):
        # тот же узел, что и на входе в review — approve не выносит на
        # merge_gate срез, который мог устареть, пока задача ждала приёмки.
        if _pull_main_or_escalate(conn, task_id, t, state) in (
                "escalated", "refused"):
            return
        store.set_state(conn, task_id, "merge_gate", "operator",
                        expected_state=state, detail="приёмка пройдена")
        # Снимок объёма (tasks/01M1KS8K9RXWHX2PW3ZKB0P903, требование 6,
        # ANSWER-1/ANSWER-2): побочный эффект входа в merge_gate, не
        # условие перехода — сбой git здесь не держит гейт.
        _snapshot_split_assessment(conn, task_id, t)
        # Undraft Draft MR (SPEC T079, требование 2, AC-2): побочный
        # эффект входа в merge_gate, не условие перехода — отказ адаптера
        # не держит гейт (github_adapter.undraft_mr сама не бросает).
        github_adapter.undraft_mr(conn, task_id, store.get_task(conn, task_id))
        # Sha, зафиксированный ЭТИМ переходом (SPEC «approve: полный sha в
        # подсказках», требование 1) — готовая к копированию команда,
        # вместо голого `<id>`, которое Оператору иначе пришлось бы
        # достраивать по памяти (инцидент 02.09, мерж T101).
        sha_hint = fixation.approve_sha_hint(task_id, store.task_target(conn, task_id))
        print(f"  дальше: artel.py approve {task_id}{sha_hint}  (выполнит merge)")
    elif state == "merge_gate":
        # Мьютекс merge-окна (SPEC T053, требования 1-3): один держатель
        # на весь пульт, не на задачу — вторая сессия, вызвавшая approve
        # из merge_gate, пока мьютекс занят, получает немедленный
        # именованный отказ (`sys.exit`, тем же стилем, что и отказ lease
        # выше) вместо ожидания. С SPEC T087 мьютекс не удерживается на
        # время ожидания CI после подтяжки (требование 2) — тело гейта и
        # его внешний цикл — orchestrator/fsm_merge_gate.py (SPEC T091):
        # берёт/отпускает мьютекс сама вокруг каждого захода в тело гейта,
        # а не единым `merge_lock.run_window` на весь вызов.
        from . import fsm_merge_gate
        fsm_merge_gate._cmd_approve_merge_gate_cycle(conn, task_id, sid, t,
                                                      state)
    elif state == "escalated":
        # Ответ Оператора (SPEC T075, AC-3): эскалация со структурированным
        # вопросом роли (QUESTIONS.md/spec_writing, `AC-n: escalate`/
        # tests_writing, REVIEW.md `status: escalate`/review) зафиксировала
        # `answer_baseline` — число ANSWER-*.md на момент эскалации — в
        # том же месте кода, что и сам факт эскалации (не позже,
        # содержательным разбором артефактов здесь: `escalated_from`
        # неоднозначен между классами, докстрин AC-5 приёмочных тестов).
        # `None` — эскалация класса «лимит»/инцидент, ответа не требует,
        # как и до этой задачи.
        baseline = t["answer_baseline"]
        if baseline is not None:
            tdir = config.TASKS / task_id
            count = _answer_file_count(conn, task_id, tdir)
            if count is None or count <= baseline:
                expected = f"tasks/{task_id}/ANSWER-{baseline + 1}.md"
                detail = (f"approve отклонён: не хватает {expected} — "
                          f"ответь Оператором (artel.py answer {task_id} "
                          f"<файл-с-ответом>) перед возвратом из эскалации")
                store.journal(conn, task_id, "fsm",
                              "approve отклонён: нет ANSWER", detail)
                print(f"[{task_id}] {detail}")
                return
        # Куда возвращать — знает только тот, кто эскалировал: провал агента
        # (cmd_run) пишет в escalated_from состояние своего шага, потому что
        # чинить надо этот шаг, а не начинать разработку заново. Эскалации по
        # вердикту ревьювера и по исчерпанным лимитам его не пишут и, как
        # раньше, уходят в in_dev: там работа и продолжается.
        back = t["escalated_from"] or "in_dev"
        store.update_task(conn, task_id, escalated_from=None, answer_baseline=None)
        store.set_state(conn, task_id, back, "operator",
                        expected_state=state, detail="эскалация разрешена, продолжаем")
        if back == "in_dev":
            _maybe_ensure_draft_mr(conn, task_id)
        print(f"  дальше: artel.py run {task_id}")
    else:
        print(f"[{task_id}] в состоянии {state} нечего подтверждать")


def cmd_reject(task_id: str, reason: str, session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой (SPEC T044, требование 2).

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease/CAS — иначе `reject` с префиксом на `merge_gate` кидал
    необработанный `CasConflict` сквозь `lease.run_locked` (REVIEW T094
    итерация 1, замечание 1)."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_reject(conn, task_id, reason))


def _cmd_reject(conn, task_id: str, reason: str) -> None:
    t = store.get_task(conn, task_id)
    state = t["state"]
    if state == "merge_gate":
        # Возврат из merge_gate (SPEC T052, требование 1, AC-1): один
        # переход в in_dev с причиной Оператора в журнале — не гейт
        # приёмки, accept_rejects её лимитом не считает (AC-7: счётчики
        # итераций других циклов возвратом из merge_gate не трогаются).
        store.set_state(conn, task_id, "in_dev", "operator",
                        expected_state=state,
                        detail=f"возврат из merge_gate: {reason}")
        _maybe_ensure_draft_mr(conn, task_id)
        return
    if state == "verifying":
        # Возврат из verifying (SPEC T079, требование 8, AC-10): тем же
        # приёмом, каким T052 расширила reject на merge_gate — один
        # переход в in_dev, без роста review_iters/accept_rejects.
        # Единственный ручной выход из verifying при красном CI —
        # симметрия инварианта 19 (требование 7): красный CI сам по себе
        # задачу не возвращает, только reject Оператора или потолок
        # ожидания (AC-9).
        store.set_state(conn, task_id, "in_dev", "operator",
                        expected_state=state,
                        detail=f"возврат из verifying: {reason}")
        _maybe_ensure_draft_mr(conn, task_id)
        return
    if state != "acceptance":
        sys.exit(f"[{task_id}] reject применим только в acceptance, "
                 f"merge_gate или verifying (сейчас {state})")
    rejects = t["accept_rejects"] + 1
    if rejects > config.LIMIT_ACCEPT_REJECTS:
        store.set_state(conn, task_id, "escalated", "fsm",
                        expected_state=state,
                        detail=f"лимит отказов приёмки исчерпан: {reason}")
    else:
        store.update_task(conn, task_id, accept_rejects=rejects)
        store.set_state(conn, task_id, "in_dev", "operator",
                        expected_state=state,
                        detail=f"приёмка отклонена: {reason}")
        _maybe_ensure_draft_mr(conn, task_id)
