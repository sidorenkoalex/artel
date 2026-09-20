"""`_tests_writing_*`, `_origin_push_gate`, `_registry_gate`,
`_freshness_refuses` (SPEC 01M2CYQR0357VAQFZ5VACJD9TD, требование 1) —
перенесено дословно из `orchestrator/fsm_advance.py`."""
from scripts import guard

from .. import acceptance, artifacts, checkpoint, config, github_adapter, store, workspace
from ._base import GateRefusal


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
    print(f"  дальше: artel.py run {task_id}  (прогон ревьювера)")
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
    конвейеру для прогона той же планки (внешний target — workspace
    target'а; self на своей ветке — worktree задачи; иначе — `tdir`/
    `config.ROOT`): отдельная функция, не рефакторинг тех двух (PLAN
    «Подход») — обе уже плотно покрыты тестами T023-семьи, а совпадение
    здесь — три строки на ветку, не повод рисковать их поведением ради
    переиспользования."""
    if target != config.DEFAULT_TARGET:
        run_cwd = config.PROJECTS / target / "workspace"
        run_cwd.mkdir(parents=True, exist_ok=True)
        return acceptance.materialize_from_branch(task_id, branch, run_cwd), run_cwd
    if workspace.on_task_branch(task_id, code_branch) is True:
        run_cwd = workspace.path(task_id)
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


def _tests_writing_dry_collect_gate(acc_tdir, run_cwd,
                                    task_id: str) -> GateRefusal | None:
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
    pytest."""
    refusal = _tests_writing_artifact_source_gate(acc_tdir, task_id)
    if refusal is not None:
        return refusal
    collected, tail = acceptance.collect(acc_tdir, run_cwd)
    if collected:
        return None
    hint = f"почини импорт/синтаксис планки и повтори artel.py advance {task_id}"
    return GateRefusal("переход отклонён: планка не собирается", tail, hint)
