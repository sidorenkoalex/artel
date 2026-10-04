"""`_tests_writing_*`, `_origin_push_gate`, `_registry_gate`,
`_freshness_refuses` (SPEC 01M2CYQR0357VAQFZ5VACJD9TD, требование 1) —
перенесено дословно из `orchestrator/fsm_advance.py`."""
from scripts import guard

from .. import (acceptance, artifact_branch, artifacts, checkpoint, config,
                cycle_hint, fixation, github_adapter, gitcmd, store, workspace)
from ._base import GateRefusal
from .acceptance import blob_sha256, long_lived_manifest_rel


def _freshness_refuses(conn, task_id: str, t, meta, status: str) -> bool:
    """Свежесть вердикта REVIEW.md — НЕ через каркас `_run_gates`
    (PLAN «Подход»): исторический формат `action` (`"переход отклонён"`,
    без суффикса) и печати (`f"[{task_id}] {detail}"`, без префикса
    «переход отклонён: ») отличается от остальных гейтов этого модуля —
    самостоятельный случай, не копия того же шаблона."""
    iteration = artifacts.fresh_verdict_iteration(meta, t["reviewed_iter"])
    if iteration is not None:
        return False
    detail = (
        f"вердикт REVIEW.md (status={status}, "
        f"iteration={meta.get('iteration', '—')}) уже учтён — "
        f"жду новый прогон ревьювера с iteration: {t['reviewed_iter'] + 1}"
    )
    store.journal(conn, task_id, "fsm", "переход отклонён", detail)
    print(f"[{task_id}] {detail}")
    print("  дальше: " + cycle_hint.launch_text(
        conn, task_id, "run", "(прогон ревьювера)"))
    return True


def _origin_push_gate(conn, task_id: str, t) -> GateRefusal | None:
    """Голова ветки задачи на origin — предусловие входа в verifying
    (SPEC 01M1GS5HZ1JXFGKVR95HEW0AEZ, требования 1-3, AC-1..AC-5; ADR-0015,
    требование 2 — рубеж переехал с входа `review()` на вход `in_dev ->
    verifying` целиком, без дублирования на новом месте), вызывается
    только для не-канареечных задач, в `in_dev()` ниже.

    Канареечная задача (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование
    11/AC-11) не зовёт этот гейт вовсе (см. `in_dev()`): её `verifying`
    не ждёт CI и не читает origin (`canary._kill_at_verifying` убивает
    задачу сразу по входу) — push на origin-заглушку
    (`canary.ORIGIN_STUB_URL`) гарантированно проваливается по
    построению, не по сбою."""
    push_ok, push_detail = github_adapter.ensure_head_in_origin(
        conn, task_id, t["branch"])
    if push_ok:
        return None
    hint = f"почини доступ к origin и повтори artel.py advance {task_id}"
    return GateRefusal("переход отклонён: голова не в origin", push_detail, hint)


def _registry_gate(conn, task_id: str, tdir, review_text, meta) -> GateRefusal | None:
    """Реестр замечаний (SPEC T100, требование 5): вердикт approved не
    проходит этот гейт, пока в реестре есть запись со статусом отличным
    от accepted — ни fixed, ни rejected сами по себе не закрывают
    замечание (ANSWER-1, симметрия). Вызывается только когда
    `guard.requires_registry(meta)` истинно (schema_version >= 3, см.
    `_review_approved`); guard уже подтвердил структуру этого REVIEW.md
    (`fsm.guard_refuses` в `review()`) — здесь читается тот же текст,
    отдельного чтения не заводится."""
    registry_text = review_text
    if registry_text is None:
        registry_text = (tdir / "REVIEW.md").read_text(encoding="utf-8")
    unresolved = [r["id"] for r in guard.registry_records(registry_text)
                 if r.get("status") != "accepted"]
    if not unresolved:
        return None
    detail = (f"реестр замечаний не закрыт: "
             f"{', '.join(unresolved)} — каждая запись обязана "
             f"дойти до status: accepted явным решением "
             f"ревьювера, прежде чем approved пройдёт гейт")
    hint = (f"доведи записи {', '.join(unresolved)} до "
           f"accepted и повтори artel.py advance {task_id}")
    return GateRefusal("переход отклонён: реестр замечаний", detail, hint)


def _tests_writing_stray_plank_files_gate(conn, task_id: str) -> GateRefusal | None:
    """Требование 3/AC-8 (SPEC 01M2ARQRDV4YY9TVPHXN2E7136): пока запись
    журнала `checkpoint.STRAY_ACCEPTANCE_FILES_ACTION` («посторонние файлы
    в каталоге планки» — checkpoint отбросил файлы этого же шага
    `test_author`, `checkpoint._commit_external_step_artifacts`) остаётся
    ПОСЛЕДНЕЙ записью с момента входа задачи в текущий визит состояния
    `tests_writing`, выход отклоняет переход, называя отброшенные файлы
    поимённо — иначе задача прошла бы трассируемость AC и сухой сбор
    планкой, ссылающейся на файл, которого нет ни на артефактной ветке,
    ни в следующем шаге developer (класс дефекта инцидента 06.09, SPEC
    «Контекст»: `_shared.py` был отброшен молча, трассируемость его не
    видела вовсе, а тесты планки падали ImportError только на приёмке).

    «Текущий визит состояния» — записи журнала ПОСЛЕ последней `state ->
    tests_writing` (обычный маркер `store.set_state`); нет такой записи
    вовсе (лёгкие песочницы, где переход состояния делается напрямую
    правкой строки БД, минуя `store.set_state`, либо самый первый вход
    задачи в состояние без единой записи журнала) — сверять от начала всего
    журнала, тот же вырожденный приём деградации, что и у
    `auto._role_step_since_state_entry` («сверять нечем» не значит
    «не сверять вовсе», здесь означает «весь имеющийся журнал — один
    визит»).

    Запись НЕ последняя (за ней есть более поздняя активность визита —
    например, повторный шаг `test_author` после починки, заметка
    Оператора) — не блокирует: устаревшая, уже замещённая запись не
    имеет права держать переход бесконечно.

    Записи `actor == "lease"` («lease взят»/«lease перехвачен»,
    `orchestrator/lease.py::acquire`) исключаются из сравнения целиком:
    это бухгалтерия ПРОЦЕССА, вызывающего `advance` сейчас (пишется
    самим `lease.run_locked` ДО того, как управление вообще дошло до
    этого гейта), не активность визита состояния — без исключения
    первый же холодный вызов `advance` для задачи без предсуществующего
    lease (обычный путь однократного `artel.py advance <id>`, не только
    тестовая песочница) журналировал бы «lease взят» ПОЗЖЕ отброшенной
    записи планки и гейт молчал бы всегда, даже когда отброшенные файлы
    реально остались последней содержательной записью визита."""
    rows = [r for r in store.task_steps(conn, task_id) if r["actor"] != "lease"]
    marker = "state -> tests_writing"
    since = 0
    for i, row in enumerate(rows):
        if row["action"] == marker:
            since = i + 1
    visit = rows[since:]
    if not visit:
        return None
    last = visit[-1]
    if last["action"] != checkpoint.STRAY_ACCEPTANCE_FILES_ACTION:
        return None
    detail = last["detail"] or ""
    prefix = checkpoint.STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX
    names = detail[len(prefix):] if detail.startswith(prefix) else detail
    refusal_detail = f"планка ссылается на отброшенные файлы: {names}"
    hint = (f"верни отброшенные файлы либо перепиши планку без них "
           f"(skills/test-authoring.md: общий код — только модули _*.py) "
           f"и повтори artel.py advance {task_id}")
    return GateRefusal("переход отклонён: посторонние файлы планки",
                       refusal_detail, hint)


def _tests_writing_acceptance_dir(task_id: str, tdir, target: str,
                                  branch: str, code_branch: str):
    """(планка, cwd) материализованной планки для сухого сбора на выходе
    `tests_writing` (требование 2) — тот же трёхветочный выбор каталога,
    что уже несут `_acceptance_run_refuses`/`_review_approved` ниже по
    конвейеру для прогона той же планки (внешний target — рабочая копия
    задачи в клоне target'а, ADR-0021 п.1-2; self на своей ветке —
    worktree задачи; иначе — `tdir`/`config.ROOT`): отдельная функция, не
    рефакторинг тех двух (PLAN «Подход») — обе уже плотно покрыты тестами
    T023-семьи, а совпадение здесь — три строки на ветку, не повод
    рисковать их поведением ради переиспользования."""
    if target != config.DEFAULT_TARGET:
        run_cwd, _err = workspace.ensure(task_id, code_branch)
        return acceptance.materialize_from_branch(task_id, branch, run_cwd), run_cwd
    if workspace.on_task_branch(task_id, code_branch, target) is True:
        run_cwd = workspace.path(task_id, target)
        return acceptance.materialize_from_branch(task_id, branch, run_cwd), run_cwd
    return tdir, config.ROOT


ARTIFACT_DISK_READ_ACTION = "переход отклонён: планка читает артефакты с диска"


def _tests_writing_artifact_source_gate(acc_tdir, task_id: str) -> GateRefusal | None:
    """Источник артефактов задачи в планке — только артефактная ветка
    (SPEC 01M2XJKKPHM5XDAE42838AMBQH, требование 5, AC-6/AC-7):
    статическая проверка `guard.scan_artifact_disk_reads` над всеми
    `*.py` материализованной планки `acc_tdir` — тем же каталогом, что
    сухой сбор ниже. Непустой результат отклоняет переход именованным
    действием `ARTIFACT_DISK_READ_ACTION`, текст ошибок guard (файл,
    строка, рецепт) — в `detail`. Отказ идёт обычным путём `_run_gates`
    (`store.journal(..., "fsm", ...)` с префиксом «переход отклонён: »),
    поэтому история отказов брифа test_author и стоп-кран T038 видят его
    тем же классом, что отказ сухого сбора: шаг роли повторяется,
    `brief._ROLE_NOT_FINISHED_REFUSAL_ACTIONS` его не вычитает.

    Зовётся из `_tests_writing_dry_collect_gate` ДО `acceptance.collect`,
    а не отдельным элементом списка `_run_gates` в `fsm_advance.
    tests_writing`: зоны задачи (`scripts/guard.py`, этот модуль,
    `tests/`) не включают `orchestrator/fsm_advance.py`, а статическая
    проверка дешевле субпроцесса pytest и даёт точнее диагноз."""
    errors = guard.scan_artifact_disk_reads(acc_tdir)
    if not errors:
        return None
    hint = (f"перепиши чтение артефактов планки на артефактную ветку "
            f"(skills/test-authoring.md) и повтори artel.py advance {task_id}")
    return GateRefusal(ARTIFACT_DISK_READ_ACTION, "; ".join(errors), hint)


TEST_GROUPS_ACTION = "переход отклонён: группы приёмочных тестов"


def _tests_writing_test_groups_gate(acc_tdir, task_id: str,
                                    target: str) -> GateRefusal | None:
    """Строка группы у каждого `test_*.py` планки и проверки долгоживущих
    файлов — признаки требования 3 и «Ловит мутацию» у каждого метода
    (SPEC 01M3N0BWYQ9KHVN41Z4G72706R, требования 1-4, 6-7; ADR-0020).
    Правила — `scripts/guard.py`, здесь только область и отказ.

    Только target `config.DEFAULT_TARGET` (требование 7) — включая
    канареечные задачи. Файлы — те же, что у сухого сбора (`acc_tdir`).

    Подсказка test_author — в `detail`, не только в печати: история
    отказов брифа роли читает журнал (требование 6)."""
    if target != config.DEFAULT_TARGET:
        return None
    files = guard.acceptance_test_files(acc_tdir)
    # Долгоживущий файл в планке — отказ с подсказкой перенести его в
    # `tests/` (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 4): временная
    # оговорка задачи 1 снята; проверки задачи 1 для такого файла остаются.
    errors = (guard.group_line_errors_from_files(files)
              + guard.long_lived_plank_errors(files, task_id)
              + guard.long_lived_errors_from_files(files, task_id))
    if not errors:
        return None
    hint = f"исправь файл планки и повтори artel.py advance {task_id}"
    return GateRefusal(TEST_GROUPS_ACTION,
                       "; ".join(errors) + f"\nдальше: {hint}", hint)


LONG_LIVED_ACTION = "переход отклонён: долгоживущие файлы tests/"


def _long_lived_refusal(task_id: str, detail: str) -> GateRefusal:
    hint = (f"test_author только добавляет файлы "
            f"{guard.long_lived_path_prefix(task_id)}<имя>.py со строкой "
            f"«Группа: {guard.GROUP_LONG_LIVED}»; верни прочее к базе ветки "
            f"и повтори artel.py advance {task_id}")
    return GateRefusal(LONG_LIVED_ACTION, f"{detail}\nдальше: {hint}", hint)


def _tests_writing_code_diff(task_id: str, code_branch: str):
    """(записи диффа, {путь: текст}, отказ) — дифф кодовой ветки против её
    базы (`gitcmd.diff_base`, `gitcmd.diff_name_status`) и тексты
    добавленных долгоживущих файлов задачи на голове ветки (SPEC
    01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования 2, 5). Сбой git — отказ, а не
    пустой дифф: иначе нарушение прошло бы молча (ADR-0002)."""
    repo = workspace.task_repo(task_id)
    base = gitcmd.diff_base(code_branch, repo=repo)
    entries = (gitcmd.diff_name_status(base, code_branch, repo=repo)
              if base else None)
    if entries is None:
        return None, None, _long_lived_refusal(
            task_id, f"дифф кодовой ветки {code_branch} против базы не "
                     f"прочитан — git не ответил, проверка невозможна")
    files: dict[str, str] = {}
    for status, path, _new in entries:
        if status == "A" and guard.is_long_lived_test_path(task_id, path):
            text, reason = gitcmd.show(code_branch, path, repo=repo)
            if text is None:
                return None, None, _long_lived_refusal(
                    task_id, f"{path} не прочитан на голове {code_branch}: "
                             f"{reason}")
            files[path] = text
    return entries, files, None


def _diff_entry_error(task_id: str, status: str, path: str,
                      new_path: str | None) -> str | None:
    """Нарушение правила «только добавление» одной записью диффа
    (требование 2); `None` — запись законна."""
    if status[:1] in ("R", "C"):
        return (f"{path} -> {new_path}: переименование/копия — test_author "
                f"не трогает существующие файлы")
    if status == "M":
        return f"{path}: правка файла базы ветки — существующие файлы не трогаются"
    if status == "D":
        return f"{path}: удаление файла базы ветки — существующие файлы не трогаются"
    if status != "A":
        return f"{path}: изменение «{status}» — допустимо только добавление"
    if not path.startswith("tests/"):
        return f"{path}: путь вне tests/ — кодовая ветка несёт только файлы tests/"
    if not guard.is_long_lived_test_path(task_id, path):
        return (f"{path}: файл без префикса задачи — имя "
                f"{guard.long_lived_path_prefix(task_id)}<имя>.py")
    return None


def _tests_writing_long_lived_gate(task_id: str, code_branch: str, entries,
                                   files: dict[str, str]) -> GateRefusal | None:
    """Гейт «только добавление» на выходе из `tests_writing` (SPEC
    01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования 2-3; ADR-0020, п. 7 — второй
    рубеж за откатом чекпоинта): дифф кодовой ветки несёт только
    добавленные файлы `tests/` с префиксом задачи, путь каждого ещё не
    существует в `origin/main`, каждый — со строкой `Группа: долгоживущий`
    и проходит статические проверки задачи 1 (признаки, «Ловит мутацию»).
    Сухой сбор — тем же вызовом, что планка (`_tests_writing_dry_collect_
    gate`), он требует выписанной рабочей копии кодовой ветки."""
    errors = [error for status, path, new_path in entries
              if (error := _diff_entry_error(task_id, status, path, new_path))]
    if files:
        repo = workspace.task_repo(task_id)
        main_ref = gitcmd.diff_base_source(code_branch, repo=repo)
        on_main = gitcmd.ls_tree_files(main_ref, "tests", repo=repo)
        if on_main is None:
            return _long_lived_refusal(
                task_id, f"дерево {main_ref} не прочитано — git не ответил, "
                         f"проверка путей невозможна")
        for path in sorted(files):
            if path in on_main:
                errors.append(f"{path}: путь уже существует в {main_ref}")
            group, group_error = guard.plank_file_group(files[path])
            if group != guard.GROUP_LONG_LIVED and (group or group_error):
                errors.append(f"{path}: нет строки «Группа: "
                              f"{guard.GROUP_LONG_LIVED}» — в tests/ кодовой "
                              f"ветки только долгоживущие файлы")
        errors += guard.long_lived_errors_from_files(sorted(files.items()),
                                                     task_id)
        if workspace.on_task_branch(task_id, code_branch,
                                    config.DEFAULT_TARGET) is not True:
            errors.append(f"рабочая копия кодовой ветки {code_branch} не "
                          f"выписана — долгоживущие файлы не собрать")
    if not errors:
        return None
    return _long_lived_refusal(task_id, "; ".join(errors))


def _tests_writing_manifest_gate(conn, task_id: str, code_branch: str,
                                 paths: list[str]) -> GateRefusal | None:
    """Перечень долгоживущих файлов в ветку документов (SPEC
    01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 6, формат Р2) — ДО записи
    `tests_locked_sha`, чтобы перечень попал в дерево коммита лока и его
    правку ловила нынешняя сверка лока. Суммы — от байтов файлов в дереве
    головы кодовой ветки. Перечень без записей — пустой файл, тоже
    записывается: отсутствие файла в дереве лока значит «лок снят до
    внедрения перечня», а не «файлов нет». Сбой git — отказ."""
    repo = workspace.task_repo(task_id)
    head = gitcmd.branch_head_sha(code_branch, repo=repo)
    digests: dict[str, str] = {}
    for path in paths:
        digest = blob_sha256(head, path, repo) if head else None
        if digest is None:
            return _long_lived_refusal(
                task_id, f"{path}: сумма на голове {code_branch} не "
                         f"посчитана — git не ответил, перечень не записан")
        digests[path] = digest
    rel = long_lived_manifest_rel(task_id)
    drift = fixation.ref_drift(conn, task_id)
    if drift is not None and drift.moved:
        # Перечень поверх подмены не пишется; переход ниже сам уведёт
        # задачу в эскалацию инцидентом (`store.set_state`).
        return None
    if drift is not None:
        # Голова не прочитана (git не ответил или ссылки нет): запись в
        # отсутствующую ссылку дала бы корневой коммит, а его перефиксация
        # узаконила бы удаление ссылки ролью.
        return GateRefusal(
            f"переход отклонён: {fixation.DOCS_REF_UNREAD_ACTION}",
            f"{rel} не записан в ветку документов: {drift.text()}",
            f"восстанови {artifact_branch.branch_name(task_id)} или разбери "
            f"инцидент, затем artel.py advance {task_id}")
    sha = artifact_branch.commit_files(
        task_id, {rel: guard.render_long_lived_manifest(digests)},
        f"{task_id}: перечень долгоживущих тестов (выход из tests_writing)")
    if not sha:
        return _long_lived_refusal(
            task_id, f"{rel} не записан в ветку документов — git не ответил")
    store.journal(conn, task_id, "fsm", "перечень долгоживущих тестов записан",
                  f"{rel}: {len(digests)} файл(ов), sha {sha}")
    # Запись пульта перефиксирует свой коммит сама: переход ниже сверяет
    # голову с фиксацией (SPEC 01M41AB597B330P2RCXCMVRZPE, требование 4).
    store.record_fixation(conn, task_id)
    return None


def _tests_writing_dry_collect_gate(acc_tdir, run_cwd, task_id: str,
                                    extra: list[str] = ()) -> GateRefusal | None:
    """Требование 2/AC-4/AC-5: сухой сбор материализованной планки
    (`acceptance.collect`) ПОСЛЕ трассируемости AC и гейта AC-8, ДО
    перевода задачи в `in_dev` — отказ сбора (импорт/синтаксис планки)
    отклоняет переход тем же текстом действия («переход отклонён: планка
    не собирается»), что и остальные отказы `tests_writing`, чтобы стоп-
    кран T038 и история отказов брифа test_author (`brief.
    advance_refusal_history`) видели его как обычный отказ шага роли,
    не как повод остановиться навсегда (AC-6 — уже общий механизм,
    правки не требует).

    Первым — источник артефактов (`_tests_writing_artifact_source_gate`,
    SPEC 01M2XJKKPHM5XDAE42838AMBQH): планка, читающая `PLAN.md` с диска,
    отклоняется своим именованным действием без запуска субпроцесса
    pytest.

    `extra` — долгоживущие файлы `tests/` задачи: собираются тем же вызовом
    из рабочей копии кодовой ветки (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ,
    требование 3)."""
    refusal = _tests_writing_artifact_source_gate(acc_tdir, task_id)
    if refusal is not None:
        return refusal
    if extra:
        collected, tail = acceptance.collect(acc_tdir, run_cwd, extra=list(extra))
    else:
        collected, tail = acceptance.collect(acc_tdir, run_cwd)
    if collected:
        return None
    hint = f"почини импорт/синтаксис планки и повтори artel.py advance {task_id}"
    return GateRefusal("переход отклонён: планка не собирается", tail, hint)
