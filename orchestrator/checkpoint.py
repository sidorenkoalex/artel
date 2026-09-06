"""WIP-чекпоинты рабочего дерева задачи: таймаут шага (SPEC T041),
аварийное завершение (SPEC T074), `pause --now` (SPEC T074) и автокоммит
артефактов успешного шага (SPEC T059). Перенесено из orchestrator/runner.py
без изменения поведения (T091, декомпозиция диспетчеров fsm/runner).
"""
import re
import shutil
from pathlib import Path

from . import config, fixation, gitcmd, store, workspace, yamlmini

# Критерий допустимости файла первого уровня `acceptance_tests/` (SPEC
# 01M1SAA01YRRTWAVADT2F81RRQ, AC-1): планка приёмки несёт только эти
# имена/расширения непосредственно в `acceptance_tests/` — вложенные
# подкаталоги (кроме `__pycache__`, отфильтрованного раньше `.gitignore`,
# см. `ignored` в `_commit_external_step_artifacts`) и прочие файлы —
# посторонние, инцидент 05.09 (`acceptance_tests/docs/codebase-map.md` из
# `scripts/codebase_map.py`, запущенного с cwd внутри каталога планки).
_ACCEPTANCE_TESTS_DIR = "acceptance_tests/"
_ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL = re.compile(
    r"^(test_.*\.py|_sandbox\.py|markers\.py|__init__\.py|.+\.md|.+\.txt)$")


def _is_stray_acceptance_test_file(task_rel: str) -> bool:
    """`task_rel` — путь относительно `tasks/<id>/` (например
    `acceptance_tests/docs/codebase-map.md` или `PLAN.md`). `True` — файл
    внутри `acceptance_tests/`, не входящий в разрешённый набор первого
    уровня; файлы вне `acceptance_tests/` этим правилом не задеты вовсе."""
    if not task_rel.startswith(_ACCEPTANCE_TESTS_DIR):
        return False
    inner = task_rel[len(_ACCEPTANCE_TESTS_DIR):]
    if "/" in inner:
        return True
    return not _ACCEPTANCE_TESTS_ALLOWED_TOP_LEVEL.match(inner)

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
        committed, sha = _commit_worktree_change(
            wt, message, exclude=f"tasks/{task_id}")
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
        committed, sha = _commit_worktree_change(
            wt, message, exclude=f"tasks/{task_id}")
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
        committed, sha = _commit_worktree_change(
            wt, message, exclude=f"tasks/{task_id}")
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
            "посторонние файлы в каталоге планки",
            f"в каталоге планки посторонние файлы: {', '.join(stray)}")

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
    """
    message = f"{task_id}: WIP-чекпоинт перед подтяжкой main"
    committed, sha = _commit_worktree_change(wt, message,
                                             exclude=f"tasks/{task_id}")
    if not committed:
        return ""
    detail = f"{message} (sha {sha})" if sha else message
    store.journal(conn, task_id, "orchestrator",
                  "WIP-чекпоинт перед подтяжкой main", detail)
    store.record_fixation(conn, task_id)
    return detail


def _commit_worktree_change(wt: Path, message: str,
                            exclude: str | None = None) -> tuple[bool, str]:
    """(закоммичено, sha) — `add -A` + `commit` служебной идентичностью
    В ЗАДАННОМ worktree; `закоммичено=False` — нечего коммитить или git
    не ответил на любом из шагов.

    Общая обвязка `commit_timeout_checkpoint` и `commit_step_artifacts`
    (SPEC T059) — обе отличаются только сообщением коммита и моментом
    вызова, сама последовательность git-операций (и её деградация без
    git) — одна на двоих.

    `exclude` — путь (пример: `tasks/<id>`), исключаемый из коммита ПОСЛЕ
    `add -A` через `git reset` (SPEC 01M1NBWTSXEJB24PXR417YF1VA, AC-1):
    мандат `developer` — все пути worktree, кроме `tasks/<id>/` (та часть
    переносится в артефактную ветку отдельно, не через эту функцию). Все
    три WIP-чекпоинта роли `developer` (`commit_timeout_checkpoint`,
    `commit_abnormal_checkpoint`, `commit_pause_now_checkpoint`, SPEC
    01M1NKTF173WV5CPDZ1C3WW69K, REVIEW.md итерация 2, R1-F1) передают
    его одинаково; `None` (по умолчанию) — для остальных ролей мандата
    кода нет вовсе, эта функция для них не вызывается (см.
    `_discard_out_of_mandate_changes`).
    """
    added = gitcmd.in_repo(wt, "add", "-A")
    if added.returncode != 0:
        return False, ""
    if exclude is not None:
        reset = gitcmd.in_repo(wt, "reset", "-q", "--", exclude)
        if reset.returncode != 0:
            return False, ""
    staged = gitcmd.in_repo(wt, "diff", "--cached", "--quiet")
    if staged.returncode != 1:  # 0 — нечего коммитить, иное — git не ответил
        return False, ""
    commit = gitcmd.in_repo(
        wt, "-c", f"user.name={fixation.FIXATION_AUTHOR_NAME}",
        "-c", f"user.email={fixation.FIXATION_AUTHOR_EMAIL}",
        "commit", "-q", "-m", message)
    if commit.returncode != 0:
        return False, ""
    return True, gitcmd.head_sha(wt)
