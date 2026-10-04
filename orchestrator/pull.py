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
import shutil
import subprocess
import tempfile
from pathlib import Path

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
# 1; SPEC 01M3EM7A84KE0W690M02VWPNXF, требование 1): эскалация по
# НЕРАЗРЕШЁННОМУ конфликту СОДЕРЖИМОГО подтяжки (единственная ветка
# `_handle_merge_failure` ниже, где `git merge --abort` завершает попытку,
# отличная от инцидента очистки worktree и от авторазрешаемого конфликта
# `docs/codebase-map.md`) метит задачу признаком «нужен шаг роли до
# следующего предварительного advance» —
# `orchestrator/auto.py::_role_step_since_state_entry`/`_pre_advance_step`
# читают этот текст по фиксированному действию журнала, не по вариативному
# detail. Скопирована в `orchestrator/brief.py` тем же приёмом, что уже
# дублирует `REFUSAL_ACTION_PREFIX` между store.py и auto.py (импорт
# auto.py <- fsm.py <- review.py <- brief.py уже существует — обратный
# импорт brief.py -> pull.py тут не нужен, значение читается как строка).
PULL_CONFLICT_ROLE_STEP_MARKER = (
    "конфликт подтяжки: нужен шаг роли до следующего предварительного advance")

# Состояния, эскалация которых по тому же конфликту получает метку выше
# (SPEC 01M3EM7A84KE0W690M02VWPNXF, требования 1-2) — ровно те, из которых
# возврат из ЭТОЙ эскалации ведёт в `in_dev`, где следующий шаг и есть шаг
# разработчика, единственного, кому конфликт по силам разрешить. Основание
# набора: `escalated_from` пишут только эскалации собственных классов
# (провал агента, потолок бюджета, эскалация по содержимому артефакта
# роли), каждая непосредственно перед своей же сменой состояния, — а
# эскалация подтяжки его не пишет, и возврат считает состояние как
# `escalated_from or "in_dev"`. Три состояния — три точки подтяжки:
# `fsm::_approve_acceptance` и `canary::_pass_acceptance_gate`
# (`acceptance`), обработчик `fsm_advance::in_dev` (`in_dev`),
# `fsm_merge_gate::_sync_main_or_wait` (`merge_gate`). Состояние вне
# набора метку не получает: метка обещает читателям в `auto.py`, что шаг
# роли после возврата действительно состоится, — обещать это за
# состояние, из которого возврат уходит куда-то ещё, нечем.
PULL_CONFLICT_MARKED_STATES = ("in_dev", "acceptance", "merge_gate")

# Фиксированный текст действия журнала (SPEC 01M3GKJ84XM5QPC6TK5EE307Q9,
# требование 7): аддитивный конфликт документов, слитый пультом. Список
# слитых файлов — в `detail`, тем же приёмом, что и запись о карте рядом:
# читатель журнала и тест находят запись по действию, не по перечислению.
ADDITIVE_CONFLICT_ACTION = "аддитивный конфликт слит"


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
    """Именованный отказ (не эскалация): планка не найдена в источнике либо
    перечень её долгоживущей группы не прочитан.
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


def _is_doc_path(rel: str) -> bool:
    """Документ в смысле аддитивного авторазрешения конфликта подтяжки
    (SPEC 01M3GKJ84XM5QPC6TK5EE307Q9, требование 4): путь внутри `docs/**`
    либо любой путь, оканчивающийся на `.md`.

    НЕ `ci_push_class.is_doc_path` (он читается этим же модулем рядом, для
    другого механизма — короткого замыкания «дифф main весь документный»):
    тот считает документами ещё и `tasks/**`, а `.md` — только в корне
    репозитория, и меняться под эту задачу не должен."""
    return rel.startswith("docs/") or rel.endswith(".md")


def _git_text(wt_path, *args: str, ok_codes=(0,)) -> str | None:
    """stdout git-команды в worktree задачи, либо `None` — git ответил
    кодом вне `ok_codes` или вывод не разобрался как текст.

    `UnicodeDecodeError` ловится здесь: `gitcmd.git` сворачивает в
    ненулевой код только `OSError`, а `subprocess.run(text=True)` на
    содержимом не в кодировке локали поднимает исключение мимо него —
    единственный узел всех новых чтений git закрывает этот класс сразу для
    стадий индекса, numstat и union-слияния, а не в одном из трёх мест.

    `ok_codes` — параметр, потому что `git diff --no-index` подразумевает
    `--exit-code`: код 1 у него означает «файлы различаются», штатный
    ответ, а не сбой."""
    try:
        res = gitcmd.in_repo(wt_path, *args)
    except UnicodeDecodeError:
        return None
    if res is None or res.returncode not in ok_codes:
        return None
    return res.stdout


def _side_added_lines(wt_path, base_file, side_file) -> int | None:
    """Число строк, ДОБАВЛЕННЫХ стороной слияния относительно базы (SPEC
    01M3GKJ84XM5QPC6TK5EE307Q9, требование 5), либо `None` — сторона не
    аддитивна: `git diff --no-index --numstat` обязан дать нуль в колонке
    удалений. Изменённая строка даёт удаление и аддитивной не считается;
    двоичный файл даёт «-» в обеих колонках и тоже не считается. Пустой
    вывод — стороны совпадают: ноль добавленных, ноль удалённых.

    Не `bool`, а число: то же самое `--numstat` даёт материал для
    пост-проверки union-слияния ниже (`_union_merged_text`, ответ
    Оператора ANSWER-1 п.1) — считать его вторым вызовом git незачем.

    Критерий применяется к файлу ЦЕЛИКОМ, не к конфликтным блокам
    (решение SPEC, требование 5): ошибка в эту сторону ведёт к прежней
    эскалации, не к потере строк."""
    out = _git_text(wt_path, "diff", "--no-index", "--numstat",
                    str(base_file), str(side_file), ok_codes=(0, 1))
    if out is None:
        return None
    added = 0
    for line in out.splitlines():
        columns = line.split("\t")
        if len(columns) < 2 or columns[1] != "0" or not columns[0].isdigit():
            return None
        added += int(columns[0])
    return added


def _line_count(text: str) -> int:
    """Число строк текста в том же счёте, в каком их считает `git diff
    --numstat`: последняя строка без завершающего перевода строки — всё
    равно строка, пустой текст — ноль строк."""
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _union_merged_text(wt_path, rel: str, stage_dir) -> str | None:
    """Union-слияние трёх стадий индекса конфликтного файла `rel`, либо
    `None` — аддитивность не доказана (SPEC 01M3GKJ84XM5QPC6TK5EE307Q9,
    требования 5-6, 8).

    Стадии, оставленные неудачным merge: `:1:` — база слияния, `:2:` —
    ветка задачи, `:3:` — main. Отсутствие любой из них (файл добавлен
    обеими сторонами — базы нет вовсе) закрывает путь автоматики:
    «относительно базы» для такого файла не определено.

    Результат — `git merge-file -p --union <стадия main> <стадия базы>
    <стадия ветки>`: union-слияние средствами git, которое по построению
    не выбрасывает ни одной строки, а порядок аргументов задаёт порядок
    добавок в конфликтной области (первый аргумент — первым), то есть
    «main, затем ветка задачи» (требование 6).

    Стадии выкладываются в каталог ВНЕ рабочего дерева: `git
    checkout-index --stage=all --temp` игнорирует `--prefix` и кладёт
    свои `.merge_file_*` в корень дерева, где посторонние незакоммиченные
    файлы ловит гейт зон следующего шага.

    Итог union-слияния сверяется с арифметикой «база плюс добавки» —
    fail-closed пост-проверка (решение Оператора ANSWER-1 п.1 по
    замечанию R1-F1 ревью итерации 1). Аддитивности САМИХ СТОРОН для
    сохранности документа недостаточно: когда хунки сторон стоят ближе
    четырёх строк базы друг к другу, git склеивает их в ОДНУ конфликтную
    область, а `--union` конкатенирует такие области целиком — строки
    базы между хунками попадают в итог дважды, а добавка ветки уезжает в
    чужой раздел документа. Обе стороны при этом честно «+N, −0», git
    отвечает нулём, и без этой сверки пульт закоммитил бы порчу как
    удачную подтяжку (проверено на базе `## Open / - open: A / ## Closed
    / - closed: B`, где каждая сторона дописала по пункту в оба списка).
    Расхождение числа строк итога с суммой «строки базы + добавки обеих
    сторон» закрывает путь автоматики: конфликт уходит в прежнюю
    эскалацию. Слияние, где обе стороны внесли ОДНУ И ТУ ЖЕ добавку, той
    же сверкой тоже уходит в эскалацию (git засчитает её один раз) — то
    же безопасное направление ошибки, что и у остального модуля."""
    stages = {}
    base_text = None
    for stage in (1, 2, 3):
        text = _git_text(wt_path, "show", f":{stage}:{rel}")
        if text is None:
            return None
        path = stage_dir / f"stage{stage}"
        try:
            path.write_text(text, encoding="utf-8")
        except OSError:
            return None
        stages[stage] = path
        if stage == 1:
            base_text = text
    main_added = _side_added_lines(wt_path, stages[1], stages[3])
    branch_added = _side_added_lines(wt_path, stages[1], stages[2])
    if main_added is None or branch_added is None:
        return None
    merged = _git_text(wt_path, "merge-file", "-p", "--union",
                       str(stages[3]), str(stages[1]), str(stages[2]))
    if merged is None:
        return None
    if _line_count(merged) != _line_count(base_text) + main_added + branch_added:
        return None
    return merged


def _merged_doc_texts(wt_path, docs: list) -> dict | None:
    """Слитые тексты всех документов `docs` — либо `None`, если хотя бы
    один не доказан аддитивным. Считается ЦЕЛИКОМ до первой записи на
    диск: неудача на втором документе иначе оставила бы первый уже
    перезаписанным, и `git merge --abort` ветки эскалации (требование 8 —
    прежнее поведение байт-в-байт) упёрся бы в незакоммиченную правку."""
    with tempfile.TemporaryDirectory() as tmp:
        merged = {}
        for number, rel in enumerate(docs):
            stage_dir = Path(tmp) / str(number)
            stage_dir.mkdir()
            text = _union_merged_text(wt_path, rel, stage_dir)
            if text is None:
                return None
            merged[rel] = text
        return merged


def _resolve_map_stage(wt_path) -> bool:
    """Карта кодовой базы в конфликтном наборе (SPEC T067, требования 1-2,
    5): `checkout --theirs` + регенерация на слитом дереве worktree задачи
    + `add`. Коммит — не здесь: merge завершает ОДИН коммит подтяжки на
    весь набор (SPEC 01M3GKJ84XM5QPC6TK5EE307Q9, требования 7 и 9)."""
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
    return added is not None and added.returncode == 0


def _map_journal_detail(files: list) -> str:
    """`detail` записи о карте. Набор из одной карты сохраняет
    СЕГОДНЯШНИЙ текст дословно (SPEC 01M3GKJ84XM5QPC6TK5EE307Q9,
    требование 9); в наборе с документами «единственный конфликтующий
    файл» было бы неправдой."""
    if files == [MAP_REL]:
        return (f"{MAP_REL} — единственный конфликтующий файл, разрешён "
                f"checkout --theirs + регенерация scripts/codebase_map.py на "
                f"слитом дереве worktree задачи")
    return (f"{MAP_REL} разрешён checkout --theirs + регенерация "
            f"scripts/codebase_map.py на слитом дереве worktree задачи; "
            f"остальные конфликтные файлы набора — аддитивные документы")


def _auto_resolve_conflict(conn, task_id: str, wt_path, source_branch: str,
                           files: list) -> bool:
    """Пульт разрешает конфликт подтяжки сам (SPEC T067; SPEC
    01M3GKJ84XM5QPC6TK5EE307Q9, требования 4-9): КАЖДЫЙ конфликтный файл —
    либо карта кодовой базы (разрешается регенерацией, как и до задачи),
    либо документ, каждый конфликт которого аддитивен (разрешается
    union-слиянием стадий индекса). Обе части завершает ТОТ ЖЕ один
    коммит подтяжки, что и удачный merge.

    `True` — merge завершён, подтяжка продолжается как обычная удачная
    подтяжка без конфликта; `False` — путь автоматики закрыт (не-документ
    в наборе, недоказанная аддитивность, любой неуспешный ответ git):
    merge НЕ завершён, вызывающий код обязан сам сделать `git merge
    --abort` и эскалировать тем же путём, что и до задачи."""
    docs = [rel for rel in files if rel != MAP_REL]
    if not all(_is_doc_path(rel) for rel in docs):
        return False
    merged = _merged_doc_texts(wt_path, docs) if docs else {}
    if merged is None:
        return False

    for rel, text in merged.items():
        try:
            (Path(wt_path) / rel).write_text(text, encoding="utf-8")
        except OSError:
            return False
        added = gitcmd.in_repo(wt_path, "add", rel)
        if added is None or added.returncode != 0:
            return False
    if MAP_REL in files and not _resolve_map_stage(wt_path):
        return False

    commit = gitcmd.in_repo(wt_path, "commit", "-m",
                            f"{task_id}: подтяжка {source_branch}")
    if commit is None or commit.returncode != 0:
        return False
    if MAP_REL in files:
        store.journal(
            conn, task_id, "orchestrator",
            "конфликт подтяжки: карта авторазрешена регенерацией",
            _map_journal_detail(files))
    if docs:
        store.journal(
            conn, task_id, "orchestrator", ADDITIVE_CONFLICT_ACTION,
            f"{', '.join(docs)} — union-слияние стадий индекса средствами "
            f"git merge-file, порядок добавок: main, затем ветка задачи")
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
    4/AC-6), конфликт, который пульт разрешает сам (карта кодовой базы —
    SPEC T067, аддитивные документы — SPEC 01M3GKJ84XM5QPC6TK5EE307Q9,
    требования 4-9; `None` возвратом, эскалации нет) и неразрешаемый
    конфликт; оба остальных исхода эскалируют (`store.set_state`), но с
    разным текстом — возвращается готовый `Conflict(files, note)`."""
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
    if merge is not None and files and _auto_resolve_conflict(
            conn, task_id, wt_path, source_branch, files):
        return None

    abort = gitcmd.in_repo(wt_path, "merge", "--abort")
    note = _merge_conflict_note(files, merge)
    if abort is None or abort.returncode != 0:
        note += (f"; git merge --abort не удался: "
                f"{abort.stderr.strip()[:200] if abort is not None else 'git не ответил'}")
    detail = f"конфликт подтяжки {source_branch} в ветку {branch}: {note}"
    store.set_state(conn, task_id, "escalated", "fsm", expected_state=state,
                    detail=detail)
    if state in PULL_CONFLICT_MARKED_STATES:
        # SPEC 01M3EM7A84KE0W690M02VWPNXF, требования 1-3: метятся все три
        # состояния набора, не одно `in_dev`. Основание — сама эта
        # эскалация `escalated_from` не пишет, а возврат берёт состояние
        # как `escalated_from or "in_dev"`: из `acceptance` и `merge_gate`
        # он уходит в `in_dev` ровно так же, и следующий шаг там — шаг
        # разработчика, до которого метка и обязана дожить. Без неё `auto`
        # после возврата делал предварительный advance, повторял ту же
        # подтяжку, ловил тот же конфликт и эскалировал снова — лишний
        # круг `answer`/`approve` Оператора на каждый конфликт (живой
        # случай 21.09, задача 01M31DRD81). `detail` — тот же, что у
        # записи эскалации: по нему Оператор читает, ЧЕМ помечена задача.
        store.journal(conn, task_id, "fsm", PULL_CONFLICT_ROLE_STEP_MARKER, detail)
    return Conflict(files, detail)


def _materialize_and_run_plank(conn, task_id: str, t, branch: str,
                               source_branch: str, wt_path, state: str,
                               base: str, read_branch_text_or_refuse):
    """Планка — из АРТЕФАКТНОЙ ветки задачи, материализованная НА МЕСТЕ, в
    тот же worktree, на котором только что прошёл merge (SPEC
    01M1R9YEK08XEQWBFX0929WFVJ/01M1RNZ6V7TTTTYAHBMF8JBQQS). Планка не
    найдена — легитимно только когда SPEC пропустила `tests_writing`
    (`skip_tests`) или не несёт AC-разметки; иначе — именованный отказ
    (SPEC 01M1R9YEK08XEQWBFX0929WFVJ, AC-3).

    `tasks/<task_id>/acceptance_tests/` убирается из worktree в `finally`
    (SPEC 01M2B6JNFD381MZT70CVB5NJQC, требование 2/AC-3), если каталога
    там не было ДО этого вызова `acceptance.materialize_from_branch`:
    диск нужен планке только на время прогона в этой функции, источник
    истины остаётся артефактная ветка задачи (SPEC «Не входит»). Каталог,
    реально существовавший на диске до материализации (устаревший прогон
    прошлой версии этой функции, ручное вмешательство), не трогается —
    только то, что материализовала САМА эта материализация. `finally`,
    не последняя строка перед `return` — уборка обязана отработать на
    ЛЮБОМ исходе функции (`Pulled` после зелёной планки, `Conflict` после
    красной, `Refused`, если планка не найдена, но SPEC требует
    AC-разметку), не только на счастливом пути; сам факт уборки не
    журналируется отдельной записью (требование 3/AC-5 — штатное
    действие, не событие, о котором стоит сообщать Оператору)."""
    artifact_branch_name, _ = artifact_source.resolve(conn, task_id)
    tests_dir = wt_path / "tasks" / task_id / "acceptance_tests"
    preexisting = tests_dir.is_dir()
    try:
        tdir = acceptance.materialize_from_branch(task_id, artifact_branch_name,
                                                   wt_path)
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

        # Долгоживущая группа (SPEC 01M3XVW94Z8E8R71XN7QWYMSP4, требования
        # 1-3) — тем же узлом и тем же вызовом, что прогон на
        # `in_dev -> verifying`: планка, целиком долгоживущая по ADR-0020,
        # без неё даёт pytest «collected 0 items» и ложную эскалацию.
        # Импорт здесь, не наверху: `advance_gates.acceptance` импортирует
        # `fsm`, а `fsm` — этот модуль.
        from .advance_gates import acceptance as acceptance_gates
        digests, reason = acceptance_gates.long_lived_manifest(
            task_id, t, t["target"] or config.DEFAULT_TARGET)
        if digests is None:
            # Сбой чтения — отказ, не прогон одной разовой группы
            # (ADR-0002, fail-closed): иначе зелёная разовая группа молча
            # пропустила бы непрогнанные долгоживущие файлы.
            detail = (f"перечень долгоживущих файлов планки не прочитан "
                      f"после подтяжки {source_branch}: {reason}")
            store.journal(
                conn, task_id, "fsm",
                "переход отклонён: перечень долгоживущих файлов не прочитан",
                detail)
            print(f"[{task_id}] переход отклонён: {detail}")
            return Refused(detail)
        long_lived = sorted(digests) if t["tests_locked_sha"] else []
        if long_lived:
            green, tail = acceptance.run(tdir, cwd=wt_path, extra=long_lived)
        else:
            green, tail = acceptance.run(tdir, cwd=wt_path)
        if not green:
            detail = (f"приёмочные тесты красные после подтяжки {source_branch} "
                      f"(слияние сохранено, откат не выполняется):\n{tail}")
            store.set_state(conn, task_id, "escalated", "fsm", expected_state=state,
                            detail=detail)
            return Conflict([], detail)
        return Pulled(base)
    finally:
        if not preexisting and tests_dir.is_dir():
            shutil.rmtree(tests_dir)


def _git_in(repo_path, *args: str):
    """git-команда в клоне проекта задачи `repo_path` (ADR-0021 п.1: для
    любого проекта, включая артель, — не главная копия)."""
    return gitcmd.in_repo(repo_path, *args)


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

    `repo_path` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, требование 3, AC-4;
    SPEC 01M42PENCS26D0656X8FR7DFA7, требование 2) — клон проекта задачи
    (`orchestrator/repo_context.py`) для любого проекта, включая артель:
    сравнение (`gitcmd.commits_behind`) идёт в нём, сам merge — в рабочей
    копии задачи `worktrees/<id>/` этого клона (`workspace.ensure`).

    `behind > 0`, но весь дифф main от точки расхождения — документные
    файлы (`ci_push_class.is_doc_path`), не пересекающиеся с диффом ветки
    (`_doc_only_main_advance`, SPEC 01M2ARQMTYRNPR5HRXAPCBAXNY) — тоже
    `Fresh()`, ДО заведения worktree: чисто документные коммиты main
    (копилка/бэклог/ADR) не обязаны вызывать подтяжку, когда они не
    затрагивают файлы самой ветки.
    """
    branch = t["branch"]
    target_name = t["target"] or config.DEFAULT_TARGET
    if repo_path is None:
        # Не назван — клон проекта задачи, тот же адрес для сравнения и
        # для `_doc_only_main_advance` (не `-C None` и не главная копия).
        repo_path = workspace.repo(target_name)
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

    return _materialize_and_run_plank(conn, task_id, t, branch, source_branch,
                                     wt_path, state, base,
                                     read_branch_text_or_refuse)
