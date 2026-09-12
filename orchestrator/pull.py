"""Исходы подтяжки главной ветки в ветку задачи (роадмап §3, фаза R,
пункт R3): логика прежней монолитной `orchestrator/fsm.py::
_pull_main_or_escalate` (218 строк — сверка свежести, `git merge`,
авторазрешение конфликта `docs/codebase-map.md`, детализация
неразрешённого конфликта, WIP-чекпоинт, материализация и прогон
приёмочной планки) разложена здесь отдельными короткими функциями.

`orchestrator/fsm.py::_pull_main_or_escalate` остаётся точкой входа
(прежняя сигнатура и контракт возврата `"escalated"`/`"refused"`/
`"fresh"`/`"pulled"`, три вызывающие точки не меняются): она сама
вычисляет `base`/`behind` (сверка свежести против origin, узлы
`fsm._origin_main_source`/`fsm._origin_main_sha` остаются в fsm.py —
общие с другими её функциями/`fsm_merge_gate.py`) и передаёт их сюда,
в `evaluate()`, вместе с этими же двумя узлами КАК ПАРАМЕТРАМИ
(`origin_main_source`/`origin_main_sha`) — не берёт их отсюда bare-именем:
`mock.patch.object(fsm, "_origin_main_sha", ...)` (существующие тесты,
AC-5) патчит имя в ПРОСТРАНСТВЕ ИМЁН `fsm`, а не здесь; читая его
оттуда параметром в момент вызова, `evaluate()` видит именно то
значение, что подставил патч, без обратной зависимости этого модуля
от `fsm.py` (которая завела бы цикл импорта — `fsm.py` и так уже
импортирует этот модуль). `read_branch_text_or_refuse` — та же
инъекция ради того же узла `fsm._read_branch_text_or_refuse`,
общего с другими функциями fsm.py (чтение SPEC.md/PLAN.md с чужой
ветки, именованный отказ уже внутри него).

`_merge_conflict_note` — единственное имя, которое существующие
тесты вызывают НАПРЯМУЮ через `fsm._merge_conflict_note(...)`
(`tests/test_fsm_merge_conflict_note.py`, не мок, чистая функция) —
`fsm.py` реэкспортирует его отсюда (AC-5).
"""
import subprocess

from . import (acceptance, alerts, artifact_source, checkpoint, config,
              gitcmd, store, workspace, yamlmini)
from scripts import ci_push_class, guard

# Файл, конфликт по которому подтяжка авторазрешает сама (SPEC T067) —
# своя копия константы (тот же приём, что и у `orchestrator/fsm_postmerge.
# py`/`orchestrator/brief.py`: каждый модуль держит её по своему поводу).
MAP_REL = "docs/codebase-map.md"

# Подстрока отказа git на грязном рабочем дереве ДО начала merge (SPEC
# 01M1RA0R9AH9RBAHD4A2Z5SEWQ, требование 4) — отличает инцидент очистки
# от содержательного конфликта («CONFLICT (content): ...»).
PULL_OVERWRITE_MARKER = "would be overwritten by merge"

# Фиксированный текст action (SPEC 01M290PYPV5T2NFW1Y0HB8BD6E, требование
# 1): эскалация `in_dev` по НЕРАЗРЕШЁННОМУ конфликту СОДЕРЖИМОГО подтяжки
# (единственная ветка `_handle_merge_failure` ниже, где `git merge --abort`
# завершает попытку, отличная от инцидента очистки worktree и от
# авторазрешаемого конфликта `docs/codebase-map.md`) метит задачу
# признаком «нужен шаг роли до следующего предварительного advance» —
# `orchestrator/auto.py::_role_step_since_state_entry`/`_pre_advance_step`
# читают этот текст по фиксированному действию журнала, не по вариативному
# detail. Скопирована в `orchestrator/brief.py` тем же приёмом, что уже
# дублирует `REFUSAL_ACTION_PREFIX` между store.py и auto.py (импорт
# auto.py <- fsm.py <- review.py <- brief.py уже существует — обратный
# импорт brief.py -> pull.py тут не нужен, значение читается как строка).
PULL_CONFLICT_ROLE_STEP_MARKER = (
    "конфликт подтяжки: нужен шаг роли до следующего предварительного advance")


class Fresh:
    """Ветка не отстала от origin (или сверка выродилась) — подтяжка не нужна."""

    def __repr__(self) -> str:
        return "Fresh()"

    def __eq__(self, other) -> bool:
        return isinstance(other, Fresh)


class Pulled:
    """Подтяжка состоялась (или легитимно не требовала планки); `sha` —
    зафетченный sha main, влитый merge'ем."""

    def __init__(self, sha: str):
        self.sha = sha

    def __repr__(self) -> str:
        return f"Pulled(sha={self.sha!r})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Pulled) and other.sha == self.sha


class Conflict:
    """Подтяжка отказала и обязана эскалировать; `files` — конфликтующие
    файлы (пусто, если причина не в конфликте содержимого — worktree
    недоступен, инцидент очистки, красные приёмочные), `note` — уже
    готовый текст `detail` эскалации."""

    def __init__(self, files: list, note: str):
        self.files = files
        self.note = note

    def __repr__(self) -> str:
        return f"Conflict(files={self.files!r}, note={self.note!r})"

    def __eq__(self, other) -> bool:
        return (isinstance(other, Conflict) and other.files == self.files
                and other.note == self.note)


class Refused:
    """Именованный отказ (не эскалация): планка не найдена в источнике.
    `reason` — `None`, если чтение SPEC.md уже журналировано/напечатано
    общим узлом `fsm._read_branch_text_or_refuse` (нечего добавлять),
    иначе — готовый текст `detail`/сообщения отказа."""

    def __init__(self, reason: str | None):
        self.reason = reason

    def __repr__(self) -> str:
        return f"Refused(reason={self.reason!r})"

    def __eq__(self, other) -> bool:
        return isinstance(other, Refused) and other.reason == self.reason


def _conflicting_files(wt_path) -> list:
    """Файлы с неразрешённым конфликтом в worktree после неудачного `git
    merge` (SPEC T067, требование 1). Пустой список — git не ответил
    осмысленно — вызывающий код в этом случае не находит `[MAP_REL]` и
    уходит в безусловный abort+escalate."""
    res = gitcmd.in_repo(wt_path, "diff", "--name-only", "--diff-filter=U")
    if res is None or res.returncode != 0:
        return []
    return sorted(set(res.stdout.split()))


def _auto_resolve_map_conflict(conn, task_id: str, wt_path, source_branch: str) -> bool:
    """Единственный конфликтующий файл — `docs/codebase-map.md` (SPEC
    T067, требования 1-2, 5): `checkout --theirs` + регенерация на
    слитом дереве worktree задачи + `add` + `commit`, который завершает
    merge, начатый вызывающим кодом.

    `True` — merge завершён, подтяжка продолжается как обычная удачная
    подтяжка без конфликта; `False` — любой шаг не удался — merge НЕ
    завершён, вызывающий код обязан сам сделать `git merge --abort` и
    эскалировать тем же путём, что и неразрешаемый конфликт."""
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


def _merge_conflict_note(files: list, merge) -> str:
    """`detail` эскалации неразрешённого конфликта подтяжки (SPEC
    01M1REVMB50SND1KJ3CYQMV2ST, требование 1, AC-1..AC-3): список
    конфликтных файлов, затем хвосты `stdout`/`stderr` `git merge` (по
    500 символов каждый — git пишет «CONFLICT (content): …»/«Automatic
    merge failed» в `stdout`, не в `stderr`). Части, которых нет,
    в результат не попадают."""
    parts = []
    if files:
        parts.append("конфликтные файлы: " + ", ".join(files))
    if merge is not None:
        stdout_tail = merge.stdout.strip()[:500]
        if stdout_tail:
            parts.append(stdout_tail)
        stderr_tail = merge.stderr.strip()[:500]
        if stderr_tail:
            parts.append(stderr_tail)
    if not parts:
        return "git не ответил осмысленно" if merge is not None else "git не ответил"
    return "; ".join(parts)


# Префикс детали журнала `checkpoint.STRAY_WORKTREE_FILES_ACTION` (SPEC
# 01M290PVYG2VJK6442H5BAX9MA, AC-2): `_clean_worktree_before_merge` снимает
# его, чтобы не дублировать «посторонние файлы в worktree» дважды подряд
# внутри собственного отказа AC-3/AC-4 ниже.
_STRAY_DETAIL_PREFIX = f"{checkpoint.STRAY_WORKTREE_FILES_ACTION}: "


def _clean_worktree_before_merge(conn, task_id: str, wt_path) -> str | None:
    """Очистка worktree ДО `git merge` (SPEC 01M1RA0R9AH9RBAHD4A2Z5SEWQ,
    требования 1-2): незакоммиченная `docs/codebase-map.md` отбрасывается
    (merge её всё равно перегенерирует), прочий WIP вне `tasks/<id>/`
    фиксируется чекпоинтом — без этого git отказывал бы merge'у отдельно
    от содержательного конфликта («... would be overwritten by merge»).

    Возврат — `None` в штатном случае; список посторонних файлов (текстом,
    через запятую) — если `checkpoint.commit_pull_checkpoint` отказала
    коммиту целиком из-за пути вне зон задачи (SPEC
    01M290PVYG2VJK6442H5BAX9MA, AC-3): читается по СВЕЖЕЙ записи журнала
    `checkpoint.STRAY_WORKTREE_FILES_ACTION`, добавленной этим самым
    вызовом (тот же приём отсечки, что `auto._run_paused_refusal`), не по
    возврату `commit_pull_checkpoint` — её контракт (`str`) зафиксирован
    существующими `tests/test_timeout_checkpoint.py::
    CommitPullCheckpointTest`, менять его нельзя (AC-8)."""
    gitcmd.in_repo(wt_path, "checkout", "--", MAP_REL)
    journaled_before = len(store.task_steps(conn, task_id))
    checkpoint.commit_pull_checkpoint(conn, task_id, wt_path)
    for row in store.task_steps(conn, task_id)[journaled_before:]:
        if row["action"] == checkpoint.STRAY_WORKTREE_FILES_ACTION:
            detail = row["detail"]
            if detail.startswith(_STRAY_DETAIL_PREFIX):
                return detail[len(_STRAY_DETAIL_PREFIX):]
            return detail
    return None


def _run_merge(wt_path, base: str, task_id: str, source_branch: str):
    """`git merge --no-ff` зафетченного sha main в worktree задачи —
    не rebase, ветка задачи в аргументах не упоминается и не трогает
    main ни байтом (ADR-0006 п.2)."""
    return gitcmd.in_repo(wt_path, "merge", "--no-ff", base, "-m",
                          f"{task_id}: подтяжка {source_branch}")


def _handle_merge_failure(conn, task_id: str, state: str, branch: str,
                          source_branch: str, merge, wt_path) -> Conflict:
    """Merge не удался (`merge is None` или `returncode != 0`) — различает
    инцидент очистки worktree (SPEC 01M1RA0R9AH9RBAHD4A2Z5SEWQ, требование
    4/AC-6), авторазрешаемый конфликт карты (SPEC T067) и неразрешаемый
    конфликт — все три эскалируют (`store.set_state`), но с разным
    текстом; возвращает готовый `Conflict(files, note)`."""
    stderr = merge.stderr if merge is not None else ""
    if PULL_OVERWRITE_MARKER in stderr:
        note = stderr.strip()[:500]
        detail = (f"подтяжка {source_branch} в ветку {branch} отказала "
                  f"после попытки очистки worktree — {note}")
        store.set_state(conn, task_id, "escalated", "fsm", expected_state=state,
                        detail=detail)
        alerts.raise_alert(
            conn, task_id, "incident", "fsm",
            f"подтяжка {branch} отказала после очистки worktree: {note}")
        return Conflict([], detail)

    files = _conflicting_files(wt_path) if merge is not None else []
    if merge is not None and files == [MAP_REL] and _auto_resolve_map_conflict(
            conn, task_id, wt_path, source_branch):
        return None

    abort = gitcmd.in_repo(wt_path, "merge", "--abort")
    note = _merge_conflict_note(files, merge)
    if abort is None or abort.returncode != 0:
        note += (f"; git merge --abort не удался: "
                f"{abort.stderr.strip()[:200] if abort is not None else 'git не ответил'}")
    detail = f"конфликт подтяжки {source_branch} в ветку {branch}: {note}"
    store.set_state(conn, task_id, "escalated", "fsm", expected_state=state,
                    detail=detail)
    if state == "in_dev":
        # Требование 1 — только `in_dev` (СПЕК: «Эскалация состояния
        # in_dev по конфликту подтяжки»); `acceptance`/`merge_gate` (два
        # других вызывающих `fsm._pull_main_or_escalate`) не заводят
        # шага роли на возврате из escalated, метить их нечем.
        store.journal(conn, task_id, "fsm", PULL_CONFLICT_ROLE_STEP_MARKER, detail)
    return Conflict(files, detail)


def _materialize_and_run_plank(conn, task_id: str, branch: str,
                               source_branch: str, wt_path, state: str,
                               base: str, read_branch_text_or_refuse):
    """Планка — из АРТЕФАКТНОЙ ветки задачи, материализованная НА МЕСТЕ, в
    тот же worktree, на котором только что прошёл merge (SPEC
    01M1R9YEK08XEQWBFX0929WFVJ/01M1RNZ6V7TTTTYAHBMF8JBQQS). Планка не
    найдена — легитимно только когда SPEC пропустила `tests_writing`
    (`skip_tests`) или не несёт AC-разметки; иначе — именованный отказ
    (SPEC 01M1R9YEK08XEQWBFX0929WFVJ, AC-3)."""
    artifact_branch_name, _ = artifact_source.resolve(conn, task_id)
    tdir = acceptance.materialize_from_branch(task_id, artifact_branch_name, wt_path)
    if not (tdir / "acceptance_tests").is_dir():
        spec_text = read_branch_text_or_refuse(conn, task_id, artifact_branch_name,
                                               "SPEC.md")
        if spec_text is None:
            return Refused(None)
        meta = yamlmini.frontmatter(spec_text) or {}
        if guard.requires_ac_markup(meta):
            detail = (
                f"планка не найдена в источнике: артефактная ветка "
                f"{artifact_branch_name} не несёт tasks/{task_id}/"
                f"acceptance_tests/, а tests_writing не пропущена "
                f"легитимно (skip_tests не задан в SPEC)")
            store.journal(
                conn, task_id, "fsm",
                "переход отклонён: планка не найдена в источнике", detail)
            print(f"[{task_id}] переход отклонён: {detail}")
            return Refused(detail)
        return Pulled(base)

    green, tail = acceptance.run(tdir, cwd=wt_path)
    if not green:
        detail = (f"приёмочные тесты красные после подтяжки {source_branch} "
                  f"(слияние сохранено, откат не выполняется):\n{tail}")
        store.set_state(conn, task_id, "escalated", "fsm", expected_state=state,
                        detail=detail)
        return Conflict([], detail)
    return Pulled(base)


def _git_in(repo_path, *args: str):
    """`gitcmd.git`/`gitcmd.in_repo` по наличию `repo_path` — свой мини-приём
    ровно тех двух примитивов, что уже несёт `gitcmd.py` (`git`/`in_repo`,
    оба публичные), без правки самого `gitcmd.py`: зона задачи
    (SPEC 01M2ARQMTYRNPR5HRXAPCBAXNY) — `orchestrator/pull.py`,
    `scripts/ci_push_class.py`, `tests/`, `gitcmd.py` в неё не входит и не
    покрыт `config.COMMON_ZONES`."""
    return gitcmd.in_repo(repo_path, *args) if repo_path else gitcmd.git(*args)


def _diff_names_in(repo_path, a: str, b: str) -> list | None:
    res = _git_in(repo_path, "diff", "--name-only", a, b)
    if res is None or res.returncode != 0:
        return None
    return [p for p in res.stdout.splitlines() if p]


def _doc_only_main_advance(branch: str, base: str, repo_path) -> list | None:
    """Файлы диффа main от точки расхождения (`merge-base(branch, base)`)
    до `base` — только если ВСЕ документные (`ci_push_class.is_doc_path`,
    SPEC 01M2ARQMTYRNPR5HRXAPCBAXNY, требование 1) И не пересекаются с
    диффом ветки от той же точки расхождения до `branch`. `None` —
    подтяжка нужна как прежде: недокументный либо пересекающийся файл, а
    также git, не ответивший ни на один из трёх запросов (`merge-base`,
    два `diff --name-only`) — fail-closed на ПРЕЖНЕЕ поведение
    (подтяжка), не на новое «пропустить» (AC-2)."""
    point_res = _git_in(repo_path, "merge-base", branch, base)
    if point_res is None or point_res.returncode != 0:
        return None
    point = point_res.stdout.strip()
    if not point:
        return None
    main_files = _diff_names_in(repo_path, point, base)
    if main_files is None or not all(ci_push_class.is_doc_path(f) for f in main_files):
        return None
    branch_files = _diff_names_in(repo_path, point, branch)
    if branch_files is None or set(main_files) & set(branch_files):
        return None
    return main_files


def evaluate(conn, task_id: str, t, state: str, *, origin_main_source,
            origin_main_sha, read_branch_text_or_refuse,
            repo_path=None):
    """Исход подтяжки главной ветки target'а задачи в её ветку — вызывается
    из `fsm._pull_main_or_escalate`. `origin_main_source`/`origin_main_sha`/
    `read_branch_text_or_refuse` — узлы `fsm.py`, инъекция параметрами (не
    импорт `fsm` этим модулем — см. докстринг файла).

    `repo_path` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, требование 3, AC-4) —
    клон контекста target'а задачи (`orchestrator/repo_context.py`),
    когда target ≠ self: сравнение (`gitcmd.commits_behind`) и сам merge
    идут ПРЯМО ТАМ — внешний target уже стоит на своей ветке задачи в
    этом клоне (ТЗ-2), отдельный worktree (`workspace.ensure`,
    self-специфичный механизм) не заводится и не нужен. `None` (по
    умолчанию, self) — прежнее поведение байт-в-байт: worktree
    `config.ROOT` через `workspace.ensure`.

    `behind > 0`, но весь дифф main от точки расхождения — документные
    файлы (`ci_push_class.is_doc_path`), не пересекающиеся с диффом ветки
    (`_doc_only_main_advance`, SPEC 01M2ARQMTYRNPR5HRXAPCBAXNY) — тоже
    `Fresh()`, ДО заведения worktree: чисто документные коммиты main
    (копилка/бэклог/ADR) не обязаны вызывать подтяжку, когда они не
    затрагивают файлы самой ветки.
    """
    branch = t["branch"]
    target_name = t["target"] or config.DEFAULT_TARGET
    source = origin_main_source(target_name)
    source_branch = source[1] if source is not None else config.MAIN_BRANCH
    base = origin_main_sha(target_name)
    if not base:
        return Fresh()
    behind = gitcmd.commits_behind(branch, base=base, repo=repo_path)
    if not behind:
        return Fresh()

    doc_files = _doc_only_main_advance(branch, base, repo_path)
    if doc_files is not None:
        store.journal(
            conn, task_id, "fsm",
            f"свежесть: {len(doc_files)} документных коммитов main без подтяжки",
            ", ".join(doc_files[:10]))
        return Fresh()

    if repo_path is not None:
        wt_path = repo_path
    else:
        wt_path, error = workspace.ensure(task_id, branch)
        if error is not None:
            detail = (f"подтяжка {source_branch} отменена: worktree "
                      f"задачи не создан — {error}")
            store.set_state(conn, task_id, "escalated", "fsm",
                            expected_state=state, detail=detail)
            return Conflict([], detail)

    stray = _clean_worktree_before_merge(conn, task_id, wt_path)
    if stray is not None:
        # SPEC 01M290PVYG2VJK6442H5BAX9MA, AC-3/AC-4: посторонний файл на
        # чекпоинте перед подтяжкой отказывает переходу ЦЕЛИКОМ (`git
        # merge` не начинается, задача остаётся в прежнем состоянии — не
        # эскалирует, `store.set_state` здесь не звонится, в отличие от
        # `Conflict` ниже) — именованная причина, которой останавливается
        # `auto` вместо повторной попытки той же безнадёжной подтяжки.
        detail = (f"посторонние файлы в worktree — решение Оператора: "
                 f"{stray}")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: посторонние файлы в worktree",
                      detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        return Refused(detail)
    merge = _run_merge(wt_path, base, task_id, source_branch)
    if merge is None or merge.returncode != 0:
        outcome = _handle_merge_failure(conn, task_id, state, branch,
                                        source_branch, merge, wt_path)
        if outcome is not None:
            return outcome

    return _materialize_and_run_plank(conn, task_id, branch, source_branch,
                                      wt_path, state, base,
                                      read_branch_text_or_refuse)
