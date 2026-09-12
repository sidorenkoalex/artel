"""WIP-чекпоинты рабочего дерева задачи: таймаут шага (SPEC T041),
аварийное завершение (SPEC T074), `pause --now` (SPEC T074) и автокоммит
артефактов успешного шага (SPEC T059). Перенесено из orchestrator/runner.py
без изменения поведения (T091, декомпозиция диспетчеров fsm/runner).
"""
import shutil
from pathlib import Path

from scripts import guard

from . import config, fixation, gitcmd, store, workspace, yamlmini, zone_lock

# Критерий допустимости файла первого уровня `acceptance_tests/` (SPEC
# 01M1SAA01YRRTWAVADT2F81RRQ, AC-1): планка приёмки несёт только эти
# имена/расширения непосредственно в `acceptance_tests/` — вложенные
# подкаталоги (кроме `__pycache__`, отфильтрованного раньше `.gitignore`,
# см. `ignored` в `_commit_external_step_artifacts`) и прочие файлы —
# посторонние, инцидент 05.09 (`acceptance_tests/docs/codebase-map.md` из
# `scripts/codebase_map.py`, запущенного с cwd внутри каталога планки).
# Вспомогательные модули планки `_*.py` (`_sandbox.py`, `_util.py`, …) —
# легитимны: регрессия №18 (06.09) — `_util.py` тест-автора P1a был
# вычищен как посторонний, планка стала неисполнимой. hotfix Оператора.
#
# Критерий сам — `guard.is_extraneous_acceptance_test_file` (SPEC
# 01M290PVYG2VJK6442H5BAX9MA, AC-5): раньше здесь жила независимая копия
# той же регулярки, байт-в-байт совпадающая, но не вызов функции —
# подмена `guard.is_extraneous_acceptance_test_file` в тестах (например,
# на время миграции правила) не долетала бы досюда.
_ACCEPTANCE_TESTS_DIR = "acceptance_tests/"

# Действие и префикс детали журнала «посторонние файлы в каталоге планки»
# (SPEC 01M2ARQRDV4YY9TVPHXN2E7136, требование 3) — вынесены константами:
# гейт `fsm_advance.tests_writing` (AC-8) сверяет ПОСЛЕДНЮЮ запись журнала
# визита состояния с этим же действием и извлекает список отброшенных
# файлов из detail по этому же префиксу, не заводя независимую копию
# текста (тот же приём, что уже несёт `STRAY_WORKTREE_FILES_ACTION` ниже).
STRAY_ACCEPTANCE_FILES_ACTION = "посторонние файлы в каталоге планки"
STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX = "в каталоге планки посторонние файлы: "


def _is_stray_acceptance_test_file(task_rel: str) -> bool:
    """`task_rel` — путь относительно `tasks/<id>/` (например
    `acceptance_tests/docs/codebase-map.md` или `PLAN.md`). `True` — файл
    внутри `acceptance_tests/`, не входящий в разрешённый набор первого
    уровня; файлы вне `acceptance_tests/` этим правилом не задеты вовсе."""
    if not task_rel.startswith(_ACCEPTANCE_TESTS_DIR):
        return False
    inner = task_rel[len(_ACCEPTANCE_TESTS_DIR):]
    return guard.is_extraneous_acceptance_test_file(inner)


# RETRO.md первого уровня `tasks/<id>/` — легитимный наравне с
# `guard.TASK_ROOT_ALLOWED_MD` (SPEC 01M290PVYG2VJK6442H5BAX9MA, AC-5):
# сам список guard его не несёт (белый список планки — зона задачи
# 01M28NX43E, не меняется), поэтому исключение — здесь, поверх вызова
# guard, не правкой самого списка.
def _is_extraneous_task_root_file(rel: str) -> bool:
    if rel == "RETRO.md":
        return False
    return guard.is_extraneous_task_root_file(rel)


# Типы артефактов, для которых допустимо удаление правилом «последний
# коммит пути на артефактной ветке — автокоммит ЭТОЙ ЖЕ роли» ниже
# (REVIEW.md 01M1KT0792125J9ZNJNZJ86E9Q итерация 1, замечание R1-F1):
# единственный задокументированный и протестированный сценарий, где
# роль сама убирает СВОЙ файл — QUESTIONS.md после ответа Оператора
# (skills/spec-authoring.md). Frontmatter `type` — сигнал из СОДЕРЖИМОГО
# файла (валидируется guard'ом), не побочный продукт механики коммита,
# как «текст сообщения совпал»: тот сигнал один и тот же и для этого
# сценария, и для реального ПОВТОРНОГО шага ТОЙ ЖЕ роли в ТОМ ЖЕ
# состоянии без намерения что-то удалить (auto-цикл `in_dev`, пока
# PLAN.md не `ready`; `reject` из `acceptance`, возвращающий в `in_dev`
# без смены роли) — там ничто не гарантирует, что роль перепишет файл,
# который хочет сохранить (`orchestrator/brief.py::developer_brief` не
# кладёт содержимое прежнего PLAN.md в промпт, `task_dir` пуст на
# каждом шаге). PLAN.md/REVIEW.md/SPEC.md (`type: plan/review/spec`)
# никогда не кандидаты на удаление этим путём, даже если формально
# совпал автор последнего коммита.
_DELETABLE_ARTIFACT_TYPES = frozenset({"questions"})


def commit_timeout_checkpoint(conn, task_id: str, role: str) -> str:
    """WIP-чекпоинт ветки задачи при таймауте шага — без участия Оператора.

    Таймаут обрывает шаг агента посреди работы (SPEC T041, «Контекст»):
    до этой задачи незакоммиченный WIP оставался в рабочем дереве, и
    сверка целостности на следующем `run` (`fixation.check_integrity`)
    честно встречала грязную копию и уводила задачу в `escalated` —
    рестарт решался только руками Оператора (прецеденты T022, T037).
    Здесь ровно то же действие, что раньше делал Оператор вручную,
    автоматически: `git add -A` + `git commit` поверх текущего рабочего
    дерева (оно и есть ветка задачи — роль создаёт и выписывает её
    первым действием миссии, до всякого таймаута).

    Мандат роли (SPEC 01M1NBWTSXEJB24PXR417YF1VA, ANSWER-1): `developer`
    — единственная роль, чей WIP попадает в кодовую ветку, и только по
    путям вне `tasks/<id>/` (та часть переносится в артефактную ветку
    ниже, для ЛЮБОЙ роли, независимо от мандата кода). `analyst`/
    `test_author`/`reviewer` не коммитят в кодовую ветку ничего — их
    WIP вне `tasks/<id>/` откатывается (`_discard_out_of_mandate_changes`)
    с записью в журнал; инцидент-источник — hotfix
    01M1KT0792125J9ZNJNZJ86E9Q (REVIEW.md R2-F1): WIP-заглушка
    реализации `test_author` попала в кодовую ветку безусловным
    `git add -A` без разбора роли. Возвращаемое значение — как и раньше,
    только про КОДОВУЮ ветку (пусто для не-`developer`, AC-2): перенос
    `tasks/<id>/` в артефактную ветку — отдельный, не отражаемый в этом
    `detail` побочный эффект (тот же довод, что раньше был у пустого
    коммита — «нечего коммитить в кодовую ветку»).

    Коммитит, только если реально есть что коммитить (AC-4 — пустой
    коммит не заводится); ничего не коммитит и не журналит при отказе
    git на любом из шагов, а не только при «нечего коммитить» — тихий
    отказ здесь не хуже, чем при таймауте: `check_integrity` следующего
    `run` увидит либо прежнее чистое состояние, либо ту же грязную
    копию, что и до этой задачи, без нового способа сломаться.

    Идентичность коммита — служебная (`fixation.FIXATION_AUTHOR_*`), тем
    же приёмом, что уже применяет `fixation._fix_external` для коммита
    фиксации внешнего target: это действие оркестратора, а не роли и не
    Оператора, поэтому не берёт ни git-конфиг Оператора, ни авторство
    роли. Все git-операции — через `gitcmd`, не через прямой
    `subprocess`/`git` (SPEC требование 7).

    Коммит легитимно сдвигает HEAD ветки задачи мимо `store.set_state` —
    без повторной фиксации (`store.record_fixation`) следующий
    `fixation.check_integrity` увидел бы этот сдвиг как расхождение sha
    с зафиксированным на входе шага и увёл бы рестарт в инцидент
    целостности, ровно то, от чего чекпоинт должен избавить (AC-2).
    `check_integrity`/`fix()` при этом не меняются — фиксация читает их
    как обычно, просто с уже сдвинутым sha.

    Только догфуд (`target == config.DEFAULT_TARGET`, PLAN «Риски»,
    REVIEW.md T041 итерации 1, замечание major). С SPEC T045 (`runner.
    role_cwd`) догфуд-роль работает в СОБСТВЕННОМ worktree задачи
    (`workspace.path`), не в `config.ROOT`, — операции идут через
    `gitcmd.in_repo(workspace.path(task_id), ...)`, тем же приёмом, что
    `fixation._fix_dogfood` уже применяет к сверке чистоты worktree
    (SPEC T048). Коммитить в `config.ROOT` было бы неверно вдвойне — либо
    подхватило бы чужое незакоммиченное состояние главной копии под
    сообщением этой задачи, либо ничего не нашло бы, оставив настоящий
    WIP worktree'а нетронутым (класс-дефект T041×T045, докстринг
    исправлен в T048 — до этой правки функция ошибочно била по ROOT).
    Для внешнего target `check_integrity` смотрит не в workspace, а в
    артефактный репозиторий `.artel/projects/<target>/` (`fixation.read`/
    `_read_external`) — свой workspace ADR-0003 §4 вообще не коммитит
    (тот же довод, что `fsm._dirty_refuses`), поэтому чекпоинт workspace'а
    не решал бы исходную проблему AC-1/AC-2 для внешнего target. Пока
    `targets.yaml` объявляет только догфуд (ADR-0003 3д, «особый случай
    до A7»), эта ветка не задета вживую; расширение на внешний target —
    отдельная задача поверх многотаргетной архитектуры фиксации, не
    точечная правка этой функции.

    Git-обвязка (`add -A` → `diff --cached --quiet` → `commit`) —
    `_commit_worktree_change`, общая с `commit_step_artifacts` (SPEC
    T059): обе функции отличаются только сообщением коммита, текстом
    действия журнала и условием вызова (таймаут здесь, `rc == 0` там).
    """
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return ""
    wt = workspace.path(task_id)
    detail = ""
    if role == "developer":
        message = f"{task_id}: WIP-чекпоинт после таймаута шага {role}"
        committed, sha, _stray = _commit_worktree_change(
            conn, task_id, wt, message, exclude=f"tasks/{task_id}")
        if committed:
            detail = f"{message} (sha {sha})" if sha else message
            store.journal(conn, task_id, "orchestrator",
                          "WIP-чекпоинт после таймаута шага", detail)
            store.record_fixation(conn, task_id)
    else:
        discarded = _discard_out_of_mandate_changes(wt, task_id)
        if discarded:
            journal_detail = (f"{task_id}: WIP вне мандата роли {role} "
                              f"после таймаута шага откачен — {discarded}")
            store.journal(conn, task_id, "orchestrator",
                          "WIP-чекпоинт после таймаута шага — откат вне мандата",
                          journal_detail)

    _commit_external_step_artifacts(conn, task_id, role, config.DEFAULT_TARGET,
                                    timeout=True)
    return detail


def _discard_out_of_mandate_changes(wt: Path, task_id: str) -> str:
    """Откатывает WIP вне `tasks/<id>/` для роли без мандата кода (SPEC
    AC-2/AC-3): трекенные пути — `git checkout --` (буквальный механизм,
    названный критерием приёмки), новые нетрекенные файлы — удаление с
    диска (`checkout --` не властен над путём без истории в git).

    Переименование (`git status` код `R`, REVIEW.md итерация 3, R1-F1) —
    путь НАЗНАЧЕНИЯ обрабатывается как новый: у него, как и у `A`/`?`,
    нет истории в HEAD под этим именем, поэтому `checkout --` для него
    заведомо провалился бы (что раньше и происходило молча) — он
    убирается с диска напрямую. Путь ИСТОЧНИК при этом уже физически
    пропал (`git mv` переместил файл на диске) и восстанавливается
    отдельно, независимо от того, что источник может лежать внутри
    `tasks/<id>/` (частый случай — переименование файла артефактов роли
    наружу): без этого восстановления сам каталог задачи терял бы файл,
    не отражая это ни в каком коммите (порча `tasks/<id>/`, вскрыта
    независимым воспроизведением R1-F1 в этой итерации).

    Возвращает строку для журнала («путь, путь (N строк)») — пустую,
    если вне `tasks/<id>/` ничего не менялось. Число строк — сумма
    add+del `git diff HEAD --numstat` по каждому трекенному пути и длина
    файла (в строках) для каждого нового (включая назначение
    переименования) — тот же смысл «сколько отброшено», что и обычный
    `diff --stat`, посчитанный руками там, где самого коммита для
    `--stat` ещё нет. Восстановленный источник переименования в счётчик
    не входит — он не отброшен, а сохранён.

    Тихая деградация при отказе git на самом статусе — та же мысль, что
    у `_commit_worktree_change`: не откатывать по частям, если даже
    список путей прочитать не удалось.
    """
    task_prefix = f"tasks/{task_id}/"
    status = gitcmd.in_repo(wt, "status", "--porcelain=v1",
                            "--untracked-files=all")
    if status.returncode != 0:
        return ""
    changed = []
    for line in status.stdout.splitlines():
        if not line:
            continue
        code, rel = line[:2], line[3:]
        rename_src = None
        if code[:1] == "R" and " -> " in rel:
            # Переименование: `rel` дальше несёт путь НАЗНАЧЕНИЯ (тот, что
            # фильтруется/откатывается ниже), `rename_src` — путь ИСТОЧНИК,
            # восстанавливаемый отдельно после разбора назначения.
            rename_src, rel = rel.split(" -> ", 1)
        if not rel.startswith(task_prefix):
            changed.append((code, rel, rename_src))
    if not changed:
        return ""

    total_lines = 0
    paths = []
    for code, rel, rename_src in changed:
        path = wt / rel
        # Первый символ статуса `A`/`?`/`R` — путь не в HEAD под этим
        # именем: `A`/`?` — застейджен ролью до чекпоинта либо просто
        # новый нетрекенный; `R` — путь назначения переименования, тоже
        # без истории под этим именем. Все три убираются с диска
        # напрямую, а не восстанавливаются из HEAD (`checkout --` не
        # властен над путём без истории).
        new_path = code[:1] in ("A", "?", "R")
        if new_path:
            if path.is_file():
                try:
                    total_lines += len(
                        path.read_text(encoding="utf-8").splitlines())
                except (OSError, UnicodeDecodeError):
                    pass
        else:
            numstat = gitcmd.in_repo(wt, "diff", "HEAD", "--numstat", "--", rel)
            if numstat.returncode == 0 and numstat.stdout.strip():
                parts = numstat.stdout.strip().split("\t")
                for n in parts[:2]:
                    if n.isdigit():
                        total_lines += int(n)
        gitcmd.in_repo(wt, "reset", "-q", "--", rel)
        if new_path:
            if path.exists():
                path.unlink()
        else:
            gitcmd.in_repo(wt, "checkout", "--", rel)
        if rename_src is not None:
            # Источник переименования ЕСТЬ в HEAD (в отличие от
            # назначения) — `reset` возвращает его запись индекса к HEAD
            # (`git mv` застейджил его как удаление), `checkout`
            # восстанавливает содержимое на диске, откуда его физически
            # убрал `git mv`.
            gitcmd.in_repo(wt, "reset", "-q", "--", rename_src)
            gitcmd.in_repo(wt, "checkout", "--", rename_src)
        paths.append(rel)

    return f"{', '.join(paths)} ({total_lines} строк)"


def commit_abnormal_checkpoint(conn, task_id: str, role: str, cause: str) -> str:
    """WIP-чекпоинт при аварийном завершении шага: rc != 0 или обрыв
    stdout-пайпа без таймаута (SPEC T074, требование 3 — расширение
    правила T041 «чекпоинт только на таймауте»: до этой задачи оба
    случая оставляли WIP как есть — rc != 0 сознательно (T041, «не
    входит»), обрыв пайпа с rc=0 попадал под безусловный успешный
    `commit_step_artifacts` и получал сообщение обычного автокоммита,
    неотличимое от штатного успеха шага (см. `tasks/T074/acceptance_tests/
    test_ac9_checkpoint_on_abnormal_step_end.py`, докстринг модуля).

    Сообщение и действие журнала несут слово «чекпоинт» (та же природа,
    что `commit_timeout_checkpoint`) плюс `cause` — короткая пометка
    причины («rc=1», «обрыв потока»), которую вызыватель формирует под
    свой сценарий; `commit_timeout_checkpoint` не тронут — таймаут
    остаётся отдельной веткой со своим прежним сообщением.

    Мандат роли и перенос `tasks/<id>/` в артефактную ветку — дословно
    `commit_timeout_checkpoint` (SPEC 01M1NKTF173WV5CPDZ1C3WW69K,
    REVIEW.md итерация 2, R1-F1 — переоткрыт: правка `commit_timeout_
    checkpoint` для мандата `developer`/отката вне мандата, полученная
    подтяжкой main, не была применена сюда, и материализованный
    `runner.role_cwd` артефакт любой роли, включая роли без мандата
    кода, безусловно коммитился в кодовую ветку на аварийном
    завершении шага — тот же класс, что итерация 1 уже закрывала для
    всех трёх WIP-чекпоинтов). `developer` — код вне `tasks/<id>/`
    (`exclude`), остальные роли — откат WIP вне `tasks/<id>/`
    (`_discard_out_of_mandate_changes`); `tasks/<id>/`, материализованный
    или изменённый на этом шаге, переносится в артефактную ветку
    `_commit_external_step_artifacts` для ЛЮБОЙ роли, а не рукой этой
    функции — единственный путь, каким `tasks/<id>/` попадает в git
    (требование 3).

    Остальное поведение — дословно `commit_timeout_checkpoint`: только
    догфуд, коммитит, только если есть что коммитить, тихая деградация
    без git, общая обвязка `_commit_worktree_change` (SPEC T059), повторная
    фиксация (`store.record_fixation`) — тот же довод, что там.
    """
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return ""
    wt = workspace.path(task_id)
    detail = ""
    if role == "developer":
        message = f"{task_id}: WIP-чекпоинт после аварийного завершения шага {role} ({cause})"
        committed, sha, _stray = _commit_worktree_change(
            conn, task_id, wt, message, exclude=f"tasks/{task_id}")
        if committed:
            detail = f"{message} (sha {sha})" if sha else message
            store.journal(conn, task_id, "orchestrator",
                          "WIP-чекпоинт после аварийного завершения шага", detail)
            store.record_fixation(conn, task_id)
    else:
        discarded = _discard_out_of_mandate_changes(wt, task_id)
        if discarded:
            journal_detail = (f"{task_id}: WIP вне мандата роли {role} "
                              f"после аварийного завершения шага откачен — {discarded}")
            store.journal(conn, task_id, "orchestrator",
                          "WIP-чекпоинт после аварийного завершения шага — откат вне мандата",
                          journal_detail)

    _commit_external_step_artifacts(conn, task_id, role, config.DEFAULT_TARGET)
    return detail


def commit_pause_now_checkpoint(conn, task_id: str, role: str) -> str:
    """WIP-чекпоинт при `pause --now` бегущего шага (SPEC T074,
    требования 1 и 3): вызывается `orchestrator.pause.cmd_pause_now`
    ПОСЛЕ того, как процесс шага уже прерван — оркестратор чекпоинтит
    дерево worktree задачи так же, как при таймауте (T041/T059), но из
    ДРУГОГО процесса (того, что выполняет саму `pause --now`), не из
    того, что запускало шаг.

    Сообщение коммита несёт литерал «pause --now» (SPEC, требование 1:
    «пометка причины «pause --now»», AC-3) — им же, а не отдельным
    словом «чекпоинт» в отрыве от причины, ищет пометку приёмочный тест
    (`tasks/T074/acceptance_tests/
    test_ac2_ac3_ac4_ac5_interrupt_sequence.py`).

    Мандат роли и перенос `tasks/<id>/` в артефактную ветку — дословно
    `commit_timeout_checkpoint` (SPEC 01M1NKTF173WV5CPDZ1C3WW69K,
    REVIEW.md итерация 2, R1-F1 — переоткрыт: та же правка, применённая
    к `commit_timeout_checkpoint` подтяжкой main, сюда не долетела —
    материализованный `runner.role_cwd` артефакт любой роли, включая
    роли без мандата кода, безусловно коммитился в кодовую ветку на
    `pause --now`). `developer` — код вне `tasks/<id>/` (`exclude`),
    остальные роли — откат WIP вне `tasks/<id>/`
    (`_discard_out_of_mandate_changes`); `tasks/<id>/` переносится в
    артефактную ветку `_commit_external_step_artifacts` для ЛЮБОЙ роли.

    Остальное — общая обвязка `_commit_worktree_change` (только догфуд,
    коммитит только при реальном diff, тихая деградация без git,
    `store.record_fixation` — та же фиксация, что не даёт следующему
    `fixation.check_integrity` увидеть сдвиг HEAD как инцидент, AC-14).
    """
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return ""
    wt = workspace.path(task_id)
    detail = ""
    if role == "developer":
        message = f"{task_id}: WIP-чекпоинт pause --now (шаг {role} прерван)"
        committed, sha, _stray = _commit_worktree_change(
            conn, task_id, wt, message, exclude=f"tasks/{task_id}")
        if committed:
            detail = f"{message} (sha {sha})" if sha else message
            store.journal(conn, task_id, "orchestrator", "WIP-чекпоинт pause --now",
                          detail)
            store.record_fixation(conn, task_id)
    else:
        discarded = _discard_out_of_mandate_changes(wt, task_id)
        if discarded:
            journal_detail = (f"{task_id}: WIP вне мандата роли {role} "
                              f"pause --now откачен — {discarded}")
            store.journal(conn, task_id, "orchestrator",
                          "WIP-чекпоинт pause --now — откат вне мандата",
                          journal_detail)

    _commit_external_step_artifacts(conn, task_id, role, config.DEFAULT_TARGET)
    return detail


def _commit_summary(wt: Path, sha: str) -> str:
    """«путь, путь (N строк)» ФАКТИЧЕСКИ закоммиченного `sha` — считает
    `git show --numstat` УЖЕ ПОСЛЕ того, как `_commit_worktree_change`
    применила `exclude` и зонный фильтр (SPEC 01M290PVYG2VJK6442H5BAX9MA,
    R1-F1): предыдущая версия (`_staged_change_summary`) снимала слепок
    индекса ДО зонного фильтра и называла посторонний файл, снятый со
    стейджа и не попавший в коммит, «закоммиченным» — расхождение с
    соседней записью журнала `STRAY_WORKTREE_FILES_ACTION` о том же
    файле. Считать по уже сделанному коммиту, а не по предварительному
    индексу, устраняет расхождение по построению: `sha` называет ровно
    те пути, что реально вошли в дерево коммита.

    Число строк — сумма добавленных и удалённых по `git show --numstat`
    (для нового файла показывает его длину как «добавлено», для правки
    трекенного — обычный add+del). Пустая строка — git не ответил (та
    же тихая деградация, что у `_commit_worktree_change`)."""
    numstat = gitcmd.in_repo(wt, "show", "--numstat", "--format=", sha)
    if numstat.returncode != 0:
        return ""
    paths = []
    total_lines = 0
    for line in numstat.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added_n, deleted_n, path = parts
        for n in (added_n, deleted_n):
            if n.isdigit():
                total_lines += int(n)
        paths.append(path)
    if not paths:
        return ""
    return f"{', '.join(paths)} ({total_lines} строк)"


def commit_success_checkpoint(conn, task_id: str, role: str) -> str:
    """WIP-коммит кода пультом за роль `developer` на обычном успешном
    (`rc=0`, без таймаута/провала/обрыва потока — эти три случая уже
    покрыты `commit_timeout_checkpoint`/`commit_abnormal_checkpoint`)
    завершении шага, если рабочее дерево осталось грязным вне
    `tasks/<id>/` (SPEC 01M283NC4JJXK7QS68Y9ET8TBK, требования 1-3):
    до этой задачи роль полагалась на то, что закоммитит сама, и при
    невыполнении следующий переход `in_dev -> verifying` отказывал по
    грязной копии с вводящим в заблуждение текстом «PLAN.md не
    закоммичен» (SPEC «Контекст»).

    Мандат — строго `developer` (AC-5), и, В ОТЛИЧИЕ от трёх аварийных
    WIP-чекпоинтов, роль без мандата кода не получает здесь НИ отката
    (`_discard_out_of_mandate_changes`), НИ коммита — немедленный
    `return ""`. Причина: «прежнее поведение» для обычного успешного
    пути (что и требует сохранить AC-5) — это ПОЛНОЕ отсутствие эффекта,
    ни один из трёх аварийных чекпоинтов сегодня не вызывается вне
    таймаута/`rc!=0`/обрыва потока, значит откатывать здесь нечего
    имитировать — до этой задачи тут не было и отката.

    Сообщение коммита и действие журнала — буквальные строки SPEC
    (AC-2/AC-3), не текст соседних WIP-чекпоинтов (та же оговорка, что
    у `commit_abnormal_checkpoint` про `cause`, только здесь текст
    целиком фиксирован, без параметра). `detail` — вывод `_commit_summary`
    ПОСЛЕ коммита (список файлов + число строк, AC-3) плюс `sha`, тем же
    приёмом, что у остальных WIP-чекпоинтов; считается по уже сделанному
    коммиту, а не по индексу до зонного фильтра — иначе посторонний файл,
    снятый со стейджа `_commit_worktree_change`, попал бы в `detail` как
    закоммиченный (SPEC 01M290PVYG2VJK6442H5BAX9MA, R1-F1).

    Только догфуд, коммитит, только если реально есть что коммитить
    (`_commit_worktree_change` сам отказывает на пустом diff), тихая
    деградация без git — дословно `commit_timeout_checkpoint`.
    """
    if role != "developer":
        return ""
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return ""
    wt = workspace.path(task_id)
    exclude = f"tasks/{task_id}"
    message = (f"{task_id}: код закоммичен пультом за роль developer — "
              "шаг завершён с незакоммиченным кодом")
    committed, sha, _stray = _commit_worktree_change(
        conn, task_id, wt, message, exclude=exclude)
    if not committed:
        return ""
    summary = _commit_summary(wt, sha)
    detail = f"{summary} (sha {sha})" if sha else summary
    store.journal(conn, task_id, "orchestrator", "код закоммичен пультом за роль",
                  detail)
    store.record_fixation(conn, task_id)
    return detail


def commit_step_artifacts(conn, task_id: str, role: str) -> str:
    """Автокоммит незакоммиченных артефактов роли по завершении успешного
    шага (rc=0), до advance-логики (SPEC T059, требования 1-3).

    Класс «роль завершила шаг rc=0, но не закоммитила артефакт»
    повторился 10 раз (REVIEW.md T041, T044, T045, T048, T051, T052) —
    каждый раз отказ `advance`, инцидент целостности и спасение
    Оператором вручную (`git add && git commit`); спасённый Оператором
    артефакт при этом был неотличим от роль-произведённого —
    `author_role` лгал о происхождении (наблюдение ревьювера T052). Эта
    функция делает то же самое действие сама, служебным коммитом
    оркестраторского авторства (`fixation.FIXATION_AUTHOR_*`), а не
    подделкой авторства роли: журнал несёт `actor=orchestrator`, тем же
    правом, каким оркестратор уже коммитит фиксацию и WIP-чекпоинт
    таймаута.

    Коммитит, только если реально есть что коммитить: роль уже
    закоммитила свои изменения сама → `_commit_worktree_change` не
    находит застейдженного диффа, пустой коммит не заводится и запись в
    журнал не пишется (требование 2). Молча отказывает при отказе git
    на любом из шагов — та же деградация без git, что у
    `commit_timeout_checkpoint` (требование 6).

    Единая логика для ЛЮБОГО target (A7, требование 2 — снятие особого
    случая догфуда): роль-разработчик/ревьювер/test_author пишет
    `tasks/<id>/` в СВОЙ рабочий каталог (`runner.role_cwd`) — она не
    знает об артефактной ветке пульта. `_commit_external_step_artifacts`
    перекладывает то, что роль там написала, в артефактную ветку пульта
    и убирает эти файлы из рабочего каталога — без этого шага первый же
    реальный шаг роли нарушал бы требование 8 (было исправлено этой же
    задачей SPEC T094, REVIEW.md итерация 1, замечание 2: до правки
    функция безусловно пропускала любой target, кроме self, — код
    роли-разработчика оставался лежать в клоне целевого, ничем не
    перенесённый). До A7 self/догфуд нёс собственную ветвь
    (`_commit_worktree_change` в её git-worktree, `workspace.path`) —
    убрана целиком вместе с однобраншевым флоу заведения задачи
    (`catalog._new_dogfood`, тоже убран этой задачей).
    """
    target = store.task_target(conn, task_id)
    return _commit_external_step_artifacts(conn, task_id, role, target)


def _commit_external_step_artifacts(conn, task_id: str, role: str,
                                    target: str, timeout: bool = False) -> str:
    """`commit_step_artifacts` для любого target (SPEC T094, требование
    8, AC-9): `tasks/<id>/`, написанный ролью в её рабочем каталоге,
    коммитится плотницки в артефактную ветку пульта
    (`orchestrator/artifact_branch.py`, тот же приём, что уже несёт
    `catalog._new_external_artifact_branch`) и убирается ОТТУДА —
    следующий шаг роли не увидит чужого прошлого содержимого как своё
    незакоммиченное, а кодовая ветка не подхватит `tasks/<id>/` ни одним
    будущим коммитом роли (требование 8: «кодовая ветка task/* свободна
    от артефактов задачи»).

    Каталога нет или он пуст — роль ничего не написала на этом шаге
    (например, чисто код без правки артефакта) — не отказ, тот же довод,
    что и у догфудной ветки («нечего коммитить»).

    Читает файлы БАЙТАМИ, не текстом (REVIEW.md T094 итерация 2,
    замечание 1 — major): раньше `read_text(encoding="utf-8")` молча
    пропускал (`continue`) любой не-UTF8/бинарный файл, а последующий
    `shutil.rmtree` ниже удалял его с диска без следа, даже если он так
    и не попал в артефактную ветку — асимметрия с self-путём
    (`_commit_worktree_change`, настоящий `git add -A`, коммитит любые
    байты). `artifact_branch.write_commit` принимает `bytes` наравне со
    `str` — потери не осталось для ни одного файла, читаемого с диска.

    Источник для self/артели — worktree КОДОВОЙ ветки задачи
    (`workspace.path(task_id)`), не `config.PROJECTS/<target>/workspace`:
    пересмотр планки решением Оператора 03.09 (вариант A второй
    эскалации задачи A7, канал ADR-0012, коммит `9a984c3`) — `role_cwd`
    для self возвращает именно этот worktree (T045), и источник
    автокоммита обязан совпасть с ним же, иначе роль пишет в один
    каталог, а автокоммит ищет в другом.

    Удаления переносятся тоже (SPEC 01M1KT0792125J9ZNJNZJ86E9Q,
    требование 4/AC-6), но НЕ полным зеркалированием диска на артефактную
    ветку целиком: роль на КАЖДОМ шаге видит пустой `task_dir` (эта же
    функция wipe'ает его в конце любого успешного коммита) и пишет туда
    только то, что меняет СЕЙЧАС, — файл другой роли/шага, не тронутый
    сегодня, обязан пережить чужой автокоммит (`tests/
    test_checkpoint_external_step_artifacts.py::
    test_second_step_accumulates_onto_the_first_not_replaces_it`, уже
    зелёный тест, ломать нельзя). Кандидат на удаление — путь, ПОСЛЕДНИЙ
    коммит которого на артефактной ветке — автокоммит ЭТОЙ ЖЕ роли (по
    тексту `message` ниже, уникален для пары task_id/role) — но сам по
    себе этот сигнал совпадает и с реальным ПОВТОРНЫМ шагом ТОЙ ЖЕ роли
    В ТОМ ЖЕ состоянии, где роль файл просто не тронула, не отказалась
    от него (REVIEW.md итерация 1, замечание R1-F1: auto-цикл `in_dev`,
    пока PLAN.md не `ready`; `reject` из `acceptance` — оба возвращают
    роль в `in_dev` с пустым `task_dir`, ничем не гарантируя, что она
    перепишет файл, который хочет сохранить). Второе условие сужает
    кандидата до реально документированного случая: frontmatter `type`
    файла обязан быть в `_DELETABLE_ARTIFACT_TYPES` (сейчас — только
    `questions`, пример — QUESTIONS.md analyst, правило скила
    spec-authoring — «удали QUESTIONS.md» перед новым SPEC.md). Путь,
    последний раз тронутый ДРУГИМ автором (другая роль, PASSPORT.md
    переходов, ANSWER Оператора), или чей `type` не в списке (PLAN.md,
    REVIEW.md, SPEC.md) — никогда не кандидат на удаление здесь,
    независимо от локального отсутствия. Исключение — удаление файлов
    `acceptance_tests/` ДО фиксации лока (см. блок ниже, SPEC
    01M1NKTF173WV5CPDZ1C3WW69K, требование 7/AC-13/AC-14/AC-15): planка
    приёмки ещё не зафиксирована, значит она ещё не «чужая», её меняет
    сам test_author.

    Конфликт-гвард (SPEC 01M1NKTF173WV5CPDZ1C3WW69K, требование 4,
    AC-6/AC-7): файл, который на этом шаге НЕ поменялся на диске
    относительно версии, материализованной `runner.role_cwd` на СТАРТЕ
    шага (`tasks.materialized_artifact_sha`), но который в артефактной
    ветке изменился ПОСЛЕ этого старта (правка Оператора на гейте между
    стартом и концом шага, инцидент 04.09) — исключается из переноса,
    заводит alert `kind=incident`, и НЕ рассматривается на удаление ниже
    (правка Оператора — не сигнал «роль его убрала»). Файл, который роль
    реально поменяла (диск разошёлся с baseline), — конфликта не ловит,
    коммитится как обычно: конфликт по одному файлу не блокирует перенос
    остальных (AC-7).

    Посторонние файлы `acceptance_tests/` (SPEC 01M1SAA01YRRTWAVADT2F81RRQ,
    требование 1, AC-1/AC-2) — критерий `_is_stray_acceptance_test_file`
    (тот же список, что называет SPEC: `test_*.py`, `_sandbox.py`,
    `markers.py`, `__init__.py`, `*.md`/`*.txt` первого уровня) исключает
    их из `files` ПОСЛЕ фильтра `.gitignore` выше, ДО конфликт-гварда и
    коммита — инцидент 05.09, `scripts/codebase_map.py` с cwd внутри
    каталога планки оставлял `acceptance_tests/docs/codebase-map.md` на
    диске, и он безусловно доезжал до артефактной ветки, откуда красил
    `guard --all` попыткой разбора его как артефакта. Одна запись журнала
    на весь список посторонних файлов шага, не по записи на файл
    (требование 2, AC-2) — цикл только собирает `stray`, сам вызов
    `store.journal` вне цикла.

    Посторонние файлы первого уровня `tasks/<id>/` (SPEC
    01M1TNN4TMWAQSQ9Y1PW37J5H0, требование 2, AC-4/AC-5/AC-6) — тот же
    приём, но критерий (`_is_extraneous_task_root_file`, тонкая обёртка
    над `guard.is_extraneous_task_root_file`) не независимая копия, а
    вызов `scripts.guard` (единый источник истины с `guard --all`,
    требование 2, AC-5 задачи 01M290PVYG2VJK6442H5BAX9MA — с
    исключением `RETRO.md`, которого сам список guard не несёт):
    инцидент 06.09, рабочие файлы роли (копии карты кодовой базы) в
    корне `tasks/<id>/` доехали до артефактной ветки и main без единой
    проверки.

    `timeout=True` (SPEC 01M1NBWTSXEJB24PXR417YF1VA, AC-4/AC-5) —
    `commit_timeout_checkpoint` зовёт этой веткой: тот же перенос, что и
    при штатном завершении шага, но сообщение коммита артефактной ветки
    несёт пометку «WIP после таймаута», чтобы читатель истории отличил
    «роль успела сама» от «оркестратор подобрал WIP после обрыва».
    Кандидат на удаление (`own_commit_marker` ниже) сверяется ПРЕФИКСОМ,
    не точным текстом сообщения — свой автокоммит любой из двух
    формулировок (обычной и с пометкой таймаута) остаётся распознаваемым
    как «последний коммит пути — автокоммит этой же роли», иначе
    чередование обычных шагов и обрывов по таймауту той же роли ломало
    бы удаление уже на второй итерации.

    Push артефактной ветки в origin (`artifact_branch.push`, ниже) теперь
    классифицирует причину отказа и журналирует и успех, и отказ (SPEC
    01M1TQ0X14Y5B3C87WC0Q31PK2, требования 1-2) — раньше отказ push
    молча пропадал (`bool` результат никем не читался).
    """
    from . import alerts, artifact_branch
    if target == config.DEFAULT_TARGET:
        workspace_root = workspace.path(task_id)
    else:
        workspace_root = config.PROJECTS / target / "workspace"
    task_dir = workspace_root / "tasks" / task_id
    if not task_dir.is_dir():
        return ""
    raw_files = {}
    for path in sorted(task_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace_root).as_posix()
        try:
            raw_files[rel] = path.read_bytes()
        except OSError:
            continue

    branch = artifact_branch.branch_name(task_id)
    own_commit_marker = f"{task_id}: артефакты шага {role} (автокоммит оркестратора"
    message = (f"{own_commit_marker}, WIP после таймаута)" if timeout
              else f"{own_commit_marker})")
    existing = gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []
    # Файлы, игнорируемые `.gitignore` пульта (SPEC 01M1KVG3KSCY47HWXWF5HM0E76,
    # требования 1-2), никогда не участвуют в автокоммите — ни на добавление
    # из рабочего каталога, ни на удаление уже зафиксированной ранее записи:
    # исключаются из ОБЕИХ сторон сравнения `files`/`existing` ДО diff'а,
    # симметрично для обоих направлений требования 2 (AC-3).
    ignored = gitcmd.check_ignore(set(raw_files) | set(existing))
    if ignored is None:
        # git не ответил на сверку .gitignore — та же тихая деградация без
        # git, что и у остального модуля (требование 6): не коммитить
        # вслепую без гарантии фильтрации, не откатываться на
        # безусловный rglob("*").
        return ""
    files = {rel: content for rel, content in raw_files.items()
             if rel not in ignored}
    existing = [rel for rel in existing if rel not in ignored]

    # Посторонние файлы `acceptance_tests/` (SPEC 01M1SAA01YRRTWAVADT2F81RRQ,
    # AC-1/AC-2) — исключаются из переноса, ОДНА запись журнала на весь шаг
    # (не по записи на файл): цикл ниже только собирает список, само
    # журналирование — один вызов после цикла.
    task_prefix = f"tasks/{task_id}/"
    stray = sorted(
        rel[len(task_prefix):] for rel in files
        if _is_stray_acceptance_test_file(rel[len(task_prefix):]))
    if stray:
        files = {rel: content for rel, content in files.items()
                 if rel[len(task_prefix):] not in stray}
        store.journal(
            conn, task_id, "orchestrator",
            STRAY_ACCEPTANCE_FILES_ACTION,
            f"{STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX}{', '.join(stray)}")

    # Посторонние файлы первого уровня tasks/<id>/ (SPEC
    # 01M1TNN4TMWAQSQ9Y1PW37J5H0, требование 2, AC-4/AC-5/AC-6) —
    # критерий допустимости импортирован из scripts.guard (один источник
    # истины с guard --all, не независимая копия): исключаются из
    # переноса, ОДНА запись журнала на весь список отброшенных путей.
    task_root_stray = sorted(
        rel[len(task_prefix):] for rel in files
        if _is_extraneous_task_root_file(rel[len(task_prefix):]))
    if task_root_stray:
        files = {rel: content for rel, content in files.items()
                 if rel[len(task_prefix):] not in task_root_stray}
        store.journal(
            conn, task_id, "orchestrator",
            "посторонние файлы в каталоге задачи",
            f"в каталоге задачи посторонние файлы: {', '.join(task_root_stray)}")

    t = store.get_task(conn, task_id)
    baseline_sha = t["materialized_artifact_sha"] or ""
    if baseline_sha:
        conflicted = []
        for rel in sorted(set(files) & set(existing)):
            baseline_text, _ = gitcmd.show(baseline_sha, rel)
            if baseline_text is None:
                continue  # файл появился на этом шаге — конфликтовать не с чем
            content = files[rel]
            try:
                disk_text = (content.decode("utf-8")
                            if isinstance(content, bytes) else content)
            except UnicodeDecodeError:
                continue  # бинарное содержимое — сравнение текстом бессмысленно
            if disk_text != baseline_text:
                continue  # роль сама поменяла файл — не конфликт, её правка идёт дальше
            current_text, _ = gitcmd.show(branch, rel)
            if current_text is not None and current_text != baseline_text:
                conflicted.append(rel)
        for rel in conflicted:
            del files[rel]
            alerts.raise_alert(
                conn, task_id, "incident", "checkpoint",
                f"конфликт артефактов: правка в ветке новее рабочего "
                f"каталога — {rel}")

    removed = []
    for rel in sorted(set(existing) - set(files)):
        subject = gitcmd.git("log", "-1", "--format=%s", branch, "--", rel)
        if not (subject is not None and subject.returncode == 0
                and subject.stdout.strip().startswith(own_commit_marker)):
            continue
        content, _ = gitcmd.show(branch, rel)
        meta = yamlmini.frontmatter(content) if content is not None else None
        deletable = meta is not None and meta.get("type") in _DELETABLE_ARTIFACT_TYPES
        if not deletable and role == "test_author" and t["state"] == "tests_writing" \
                and not t["tests_locked_sha"] \
                and rel.startswith(f"tasks/{task_id}/acceptance_tests/"):
            # SPEC 01M1NKTF173WV5CPDZ1C3WW69K, требование 7/AC-13/AC-15:
            # тесты `acceptance_tests/*.py` не несут frontmatter вовсе
            # (`_DELETABLE_ARTIFACT_TYPES` их никогда не увидит), но до
            # фиксации лока планка ещё правится самим test_author'ом —
            # её удаление им же обязано доехать до ветки тем же коммитом,
            # без повторной попытки (канарейка v2). После лока (AC-14)
            # `tests_locked_sha` уже не пуст — эта ветка не срабатывает,
            # прежнее правило (только `type: questions`) остаётся в силе.
            deletable = True
        if deletable:
            removed.append(rel)

    if not files and not removed:
        return ""
    commit_sha = artifact_branch.commit_files(task_id, files, message,
                                              remove=removed)
    if not commit_sha:
        return ""
    shutil.rmtree(task_dir, ignore_errors=True)
    artifact_branch.push(task_id)
    detail = f"{message} (артефактная ветка, sha {commit_sha})"
    if removed:
        detail += f"; удалено: {', '.join(removed)}"
    store.journal(conn, task_id, "orchestrator",
                  "автокоммит артефактов шага (артефактная ветка)", detail)
    store.record_fixation(conn, task_id)
    return detail


def commit_pull_checkpoint(conn, task_id: str, wt: Path) -> str:
    """WIP-чекпоинт worktree задачи перед `git merge` в `fsm._pull_main_or_
    escalate` (SPEC 01M1RA0R9AH9RBAHD4A2Z5SEWQ, требование 2, AC-2/AC-3/
    AC-5): незакоммиченный код вне `tasks/<id>/`, оставшийся после
    отбрасывания `docs/codebase-map.md` (вызывающий код делает это
    отдельным `checkout --` до вызова этой функции — иначе изменённая
    карта попала бы в этот коммит вместо того, чтобы быть отброшенной),
    коммитится тем же приёмом, что и остальные три WIP-чекпоинта
    (`_commit_worktree_change`).

    Мандат — безусловно `developer` (SPEC требование 2: «мандат кода в
    этом worktree всегда у developer — единственной роли, чей WIP
    попадает в кодовую ветку»): в отличие от `commit_timeout_checkpoint`/
    `commit_abnormal_checkpoint`/`commit_pause_now_checkpoint`, здесь нет
    параметра `role` и ветки отката для прочих ролей — подтяжка main
    (все три точки вызова: `in_dev -> review`, `acceptance -> merge_gate`,
    `merge_gate -> done`) идёт над worktree кодовой ветки задачи, куда
    только код `developer` и попадает.

    Не проверяет `store.task_target`/не разрешает `wt` сама — вызывающий
    код (`fsm._pull_main_or_escalate`) уже получил `wt` от `workspace.
    ensure` для КОНКРЕТНОГО target'а задачи, в отличие от остальных трёх
    чекпоинтов, которые сами решают, чей worktree им коммитить (только
    догфуд, PLAN «Риски» тех задач). Пустая строка — нечего коммитить или
    git не ответил (та же тихая деградация, что и у остальных
    WIP-чекпоинтов).

    Посторонний файл вне зон задачи (SPEC 01M290PVYG2VJK6442H5BAX9MA,
    AC-1/AC-3) отменяет коммит ЦЕЛИКОМ, не только сам посторонний путь —
    `_commit_worktree_change(..., refuse_on_stray=True)`: вызывающий код
    (`orchestrator/pull.py::_clean_worktree_before_merge`) обязан отказать
    всей подтяжке, не просто исключить файл, как остальные три
    WIP-чекпоинта. Возврат всё равно `str` (пустая строка и на «нечего
    коммитить», и на этот отказ) — контракт зафиксирован существующими
    `tests/test_timeout_checkpoint.py::CommitPullCheckpointTest`; сам факт
    отказа и список посторонних путей вызывающий код читает по СВЕЖЕЙ
    записи журнала `STRAY_WORKTREE_FILES_ACTION` (тот же приём отсечки,
    что `auto._run_paused_refusal`), не по возврату этой функции.
    """
    message = f"{task_id}: WIP-чекпоинт перед подтяжкой main"
    committed, sha, _stray = _commit_worktree_change(
        conn, task_id, wt, message, exclude=f"tasks/{task_id}",
        refuse_on_stray=True)
    if not committed:
        return ""
    detail = f"{message} (sha {sha})" if sha else message
    store.journal(conn, task_id, "orchestrator",
                  "WIP-чекпоинт перед подтяжкой main", detail)
    store.record_fixation(conn, task_id)
    return detail


# Действие журнала «посторонние файлы в worktree» (SPEC
# 01M290PVYG2VJK6442H5BAX9MA, AC-2): единая запись на шаг, не по записи
# на файл — `_commit_worktree_change` пишет её сама, все четыре
# WIP-чекпоинта делят один и тот же текст. Публичное имя — `pull.py`
# читает его же, отличая отказ AC-3 от прочих исходов журнала (её
# собственный контракт возврата не меняется, см. `commit_pull_checkpoint`).
STRAY_WORKTREE_FILES_ACTION = "посторонние файлы в worktree"


def task_dir_zone(task_id: str) -> str:
    """Собственный каталог задачи `tasks/<task_id>/` — зона, общая для
    WIP-чекпоинтов (`_zone_paths` ниже) и довеска неотслеживаемых файлов
    гейта зон (`fsm_advance._zones_gate`, SPEC
    01M2B6JNFD381MZT70CVB5NJQC, требование 1): материализованная планка
    приёмки (`acceptance.materialize_from_branch`) остаётся в worktree
    неотслеживаемой между стартом и концом подтяжки главной ветки — без
    единого источника этого правила оба места самостоятельно решали бы,
    что такое «свой каталог задачи», и могли бы разойтись."""
    return f"tasks/{task_id}/"


def _zone_paths(conn, task_id: str) -> list[str]:
    """Зоны, в пределах которых WIP-чекпоинт вправе коммитить путь
    worktree (SPEC 01M290PVYG2VJK6442H5BAX9MA, AC-1): объявленные `zones`
    + `zones_extension` задачи, `config.COMMON_ZONES` и собственный
    каталог `tasks/<id>/` (`task_dir_zone`).

    Задача, ни разу не заявившая зону (`zones` и `zones_extension` оба
    пусты — SPEC старой версии до `guard.requires_zones`, либо тестовая
    фикстура мимо гейта SPEC) — пустой список: `_stray_staged_paths`
    в этом случае не применяет фильтр вовсе, тем же доводом, что уже
    несёт `fsm_advance._zones_gate` («задача без заявленной зоны вовсе —
    гейт не звонится») — иначе любой путь старой задачи, ничего не
    заявившей, стал бы посторонним."""
    t = store.get_task(conn, task_id)
    raw = ",".join(p for p in (t["zones"], t["zones_extension"]) if p)
    declared = [p.strip() for p in raw.split(",") if p.strip()]
    if not declared:
        return []
    return declared + list(config.COMMON_ZONES) + [task_dir_zone(task_id)]


def _stray_staged_paths(wt: Path, zones: list[str]) -> list[str] | None:
    """Застейдженные пути (`git diff --cached --name-only`), не покрытые
    ни одной зоной `zones` — с учётом вложенности файл/каталог, тем же
    правилом, что `zone_lock._paths_overlap` (SPEC 01M290PVYG2VJK6442H5BAX9MA,
    AC-1). `zones` пуст — пустой список без единого вызова git: фильтр не
    применяется вовсе (см. `_zone_paths`). `None` — git не ответил на сам
    `diff --cached`."""
    if not zones:
        return []
    res = gitcmd.in_repo(wt, "diff", "--cached", "--name-only")
    if res is None or res.returncode != 0:
        return None
    stray = []
    for rel in res.stdout.splitlines():
        rel = rel.strip()
        if rel and not any(zone_lock._paths_overlap(rel, z) for z in zones):
            stray.append(rel)
    return stray


def _commit_worktree_change(conn, task_id: str, wt: Path, message: str,
                            exclude: str | None = None,
                            refuse_on_stray: bool = False
                            ) -> tuple[bool, str, list[str]]:
    """(закоммичено, sha, посторонние) — `add -A` + фильтр по зонам задачи
    + `commit` служебной идентичностью В ЗАДАННОМ worktree;
    `закоммичено=False` — нечего коммитить, git не ответил на любом из
    шагов, либо (`refuse_on_stray=True`) найден посторонний путь.

    Общая обвязка всех четырёх WIP-чекпоинтов (SPEC
    01M290PVYG2VJK6442H5BAX9MA, AC-1) — `commit_timeout_checkpoint`/
    `commit_abnormal_checkpoint`/`commit_pause_now_checkpoint`/
    `commit_pull_checkpoint` отличаются только сообщением коммита,
    моментом вызова и `refuse_on_stray`; сама последовательность
    git-операций (и её деградация без git) — одна на четверых.

    `exclude` — путь (пример: `tasks/<id>`), исключаемый из коммита ПОСЛЕ
    `add -A` через `git reset` (SPEC 01M1NBWTSXEJB24PXR417YF1VA, AC-1):
    мандат `developer` — все пути worktree, кроме `tasks/<id>/` (та часть
    переносится в артефактную ветку отдельно, не через эту функцию).
    `None` (по умолчанию) — для остальных ролей мандата кода нет вовсе,
    эта функция для них не вызывается (см. `_discard_out_of_mandate_changes`).

    После `exclude` застейдженный дифф сверяется с `_zone_paths` (AC-1):
    посторонний путь пишет ОДНУ запись журнала `STRAY_WORKTREE_FILES_ACTION`
    на весь список (AC-2), общую для обоих режимов ниже.

    `refuse_on_stray=False` (по умолчанию, три обычных WIP-чекпоинта) —
    посторонние пути снимаются со стейджа (`git reset -- <path>...`) и НЕ
    коммитятся, остальное коммитится как обычно.

    `refuse_on_stray=True` (только `commit_pull_checkpoint`, AC-3) — при
    непустом списке посторонних коммита не происходит ВООБЩЕ (весь стейдж
    снимается `git reset -q` без пути): вызывающий код обязан отказать
    переходу целиком, не просто исключить файл.
    """
    added = gitcmd.in_repo(wt, "add", "-A")
    if added.returncode != 0:
        return False, "", []
    if exclude is not None:
        reset = gitcmd.in_repo(wt, "reset", "-q", "--", exclude)
        if reset.returncode != 0:
            return False, "", []
    stray = _stray_staged_paths(wt, _zone_paths(conn, task_id))
    if stray is None:
        return False, "", []
    if stray:
        store.journal(conn, task_id, "orchestrator",
                      STRAY_WORKTREE_FILES_ACTION,
                      f"{STRAY_WORKTREE_FILES_ACTION}: {', '.join(stray)}")
        if refuse_on_stray:
            gitcmd.in_repo(wt, "reset", "-q")
            return False, "", stray
        unstage = gitcmd.in_repo(wt, "reset", "-q", "--", *stray)
        if unstage.returncode != 0:
            return False, "", stray
    staged = gitcmd.in_repo(wt, "diff", "--cached", "--quiet")
    if staged.returncode != 1:  # 0 — нечего коммитить, иное — git не ответил
        return False, "", stray
    commit = gitcmd.in_repo(
        wt, "-c", f"user.name={fixation.FIXATION_AUTHOR_NAME}",
        "-c", f"user.email={fixation.FIXATION_AUTHOR_EMAIL}",
        "commit", "-q", "-m", message)
    if commit.returncode != 0:
        return False, "", stray
    return True, gitcmd.head_sha(wt), stray
