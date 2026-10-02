"""Команда `ci-rerun`: повтор упавшего CI ветки задачи в `verifying`
(SPEC 01M3F7C2DVYCEANQ8CF1FCSD87).

Вынесена из `orchestrator/fsm.py` дословно, без изменения поведения
(SPEC 01M3H3T8RKTVKTJJYEAGW19BPS, находка CR-2026-09-26-4) — по образцу
`orchestrator/amend.py` и `orchestrator/answer.py`: операторская команда
над задачей живёт своим модулем, в `fsm.py` остаются переходы автомата.

`fsm` импортируется ОТЛОЖЕННО, внутри функций: команде нужны
`fsm.VERIFYING_STATUS_ACTION` (action записи, из которой берётся sha
остановки цикла, требование 4) и `fsm._origin_main_sha` (вершина главной
ветки, требование 5), а `fsm.py` держит алиас `cmd_ci_rerun` этого
модуля — модульный импорт замкнул бы цикл. Приём тот же, которым
`fsm.py` зовёт `fsm_advance`/`fsm_merge_gate`; он же оставляет рабочими
подмены существующих тестов (`mock.patch.object(fsm, "_origin_main_sha",
…)`), которые импорт по имени сломал бы.
"""
import sys

from . import ci, config, cycle_hint, lease, store

CI_RERUN_ACTION = "повтор CI ветки (ci-rerun)"

# Отказ журналируется ДРУГИМ действием — тем же приёмом и по той же
# причине, что `amend._refuse_traceability` не переиспользует
# `AMEND_ACTION`: иначе отказ засчитывался бы сверкой требования 10 как
# состоявшийся повтор, и следующий вызов с тем же основанием проходил бы.
CI_RERUN_REFUSED_ACTION = "ci-rerun отклонён"

# Основание Оператора стоит в detail ПОСЛЕДНИМ, за этим маркером:
# требование 10 сверяет его ДОСЛОВНО, а основание может быть
# многострочным — `rpartition` по маркеру достаёт хвост как есть, тогда
# как разбор «первой строки» многострочное основание обрезал бы.
CI_RERUN_REASON_MARKER = "основание Оператора: "

# Три исхода ожидания повтора (требование 8): Оператор читает в журнале
# именно их, а не пересказ вывода `gh`.
CI_RERUN_OUTCOME_GREEN = "CI ветки стал зелёным"
CI_RERUN_OUTCOME_RED = "CI ветки снова красный"
CI_RERUN_OUTCOME_UNKNOWN = "исход неизвестен — `gh` не ответил"


def cmd_ci_rerun(task_id: str, reason: str | None,
                 session_id: str | None = None) -> None:
    """`ci-rerun <id> --reason "<основание>"` — повтор упавшего CI ветки
    задачи, стоящей в `verifying` (SPEC 01M3F7C2DVYCEANQ8CF1FCSD87).

    Исполняет решение Оператора «краснота ветки — флейк», которое до этой
    команды исполнялось либо `reject` в `in_dev` (лишний шаг разработчика
    на $2-5), либо `gh run rerun` руками. Сама автомат не двигает и роль
    не запускает (требование 9): после зелёного повтора задачу уводит
    дальше очередной опрос `cmd_advance` в `verifying`.

    Префикс -> полный id резолвится ЗДЕСЬ, до lease — тот же порядок, что
    у `amend.cmd_amend_tests`/`answer.cmd_answer`. Lease берётся по тому
    же основанию, что и у остальных мутирующих команд задачи: команда
    пишет журнал и дёргает внешний CI — параллельная сессия не должна
    делать это одновременно.
    """
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_ci_rerun(conn, task_id, reason))


def _ci_rerun_refuse(conn, task_id: str, text: str) -> None:
    """Именованный отказ команды: запись журнала + `sys.exit` — ничего не
    перезапуская и не трогая состояние задачи. Не возвращается никогда."""
    store.journal(conn, task_id, "operator", CI_RERUN_REFUSED_ACTION, text)
    sys.exit(f"[{task_id}] ci-rerun: отказ — {text}")


def _last_red_status_sha(conn, task_id: str) -> str:
    """Короткий sha коммита из ПОСЛЕДНЕЙ записи журнала о завершённом
    красном CI ветки; "" — такой записи нет (требование 4).

    Ищется именно `fsm.VERIFYING_STATUS_ACTION` + `ci.verifying_is_red` —
    та самая запись, на которой цикл `auto` остановился причиной
    `config.AUTO_STOP_VERIFYING_RED`: sha, к которому относится решение
    Оператора «это флейк», больше нигде не хранится.
    """
    from . import fsm  # отложенный импорт — см. докстринг модуля

    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] != fsm.VERIFYING_STATUS_ACTION:
            continue
        detail = row["detail"] or ""
        if ci.verifying_is_red(detail):
            return ci.red_status_sha(detail)
    return ""


def _last_ci_rerun_reason(conn, task_id: str) -> str | None:
    """Основание последнего СОСТОЯВШЕГОСЯ `ci-rerun` этой задачи; `None` —
    повторов ещё не было (или запись собрана не этим кодом, маркера в ней
    нет). Требование 10."""
    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] != CI_RERUN_ACTION:
            continue
        _, marker, tail = (row["detail"] or "").rpartition(
            CI_RERUN_REASON_MARKER)
        return tail if marker else None
    return None


def _ci_rerun_outcome(branch: str, rerun_note: str) -> tuple[str, bool]:
    """(текст исхода ожидания для журнала, удался ли повтор) — требование 8.

    Исход определяется повторным чтением статуса CI (`ci.verifying_status`
    уже после `gh run watch`), а не пересказом stderr `gh`: так запись
    журнала несёт вердикт пульта, а не чужое слово. «Повтор не запущен»
    (`ci.rerun_started`) разбирается раньше — там нового статуса не будет
    вовсе, и перечитанный красный означал бы «попробовали и снова упало»,
    хотя не запускалось ничего.

    Не-зелёный и не-красный исход (статус неизвестен, проверки ещё идут) —
    тот же «`gh` не ответил»: инвариант 19, неизвестный исход не зелёный.
    """
    if not ci.rerun_started(rerun_note):
        return f"{CI_RERUN_OUTCOME_UNKNOWN}: повтор не запущен", False
    outcome, note = ci.verifying_status(branch)
    if outcome == ci.VERIFYING_GREEN:
        return f"{CI_RERUN_OUTCOME_GREEN}: {note}", True
    if outcome == ci.VERIFYING_RED:
        return f"{CI_RERUN_OUTCOME_RED}: {note}", True
    return f"{CI_RERUN_OUTCOME_UNKNOWN}: {note}", False


def _cmd_ci_rerun(conn, task_id: str, reason: str | None) -> None:
    t =store.get_task(conn, task_id)
    branch = t["branch"]

    # Требование 3: основание — ДО любого обращения к `gh`. «Флага нет» и
    # «флаг пуст» — один и тот же отказ (тот же приём, что у
    # `amend._cmd_amend_tests`).
    if not (reason or "").strip():
        _ci_rerun_refuse(
            conn, task_id,
            "основание (--reason) пустое: повтор CI — решение Оператора, и "
            "журнал задачи обязан нести его причину")

    # Требование 10: то же основание второй раз — отказ. Стоит рядом с
    # проверкой выше (обе про `--reason`) и тоже до `gh`: иначе команда
    # превращается в кнопку «жать до зелёного» без решения по существу.
    previous = _last_ci_rerun_reason(conn, task_id)
    if previous is not None and previous == reason:
        _ci_rerun_refuse(
            conn, task_id,
            f"основание дословно совпадает с основанием последнего "
            f"повтора этой задачи ({previous!r}) — повторный ci-rerun "
            f"допустим только с новым основанием")

    # Требование 2: команда работает только в `verifying` и только при
    # завершённом красном CI. Статус читается до проверки состояния —
    # отказ обязан назвать и состояние, и статус (AC-1).
    outcome, note = ci.verifying_status(branch)
    if t["state"] != "verifying":
        _ci_rerun_refuse(
            conn, task_id,
            f"задача в состоянии {t['state']}, а повтор CI допустим только "
            f"в verifying; статус CI ветки {branch}: {note}")
    if outcome == ci.VERIFYING_STUCK:
        rerun_note = _stuck_rerun(conn, task_id, branch, note)
    elif outcome != ci.VERIFYING_RED:
        # Именно `== VERIFYING_RED`, не «не зелёный»: «проверки идут» и
        # «проверок нет вовсе» — это ре-ран идущего или несуществующего
        # прогона, он ничего не подтверждает (тот же довод, что у
        # `ci.status_kind` на гейте мержа). «Проверка зависла» — иное:
        # без перезапуска она не завершится вовсе (SPEC
        # 01M3Y75C9TY76083CG1PK00EM4, требование 3).
        _ci_rerun_refuse(
            conn, task_id,
            f"CI ветки {branch} не завершённо-красный (исход {outcome}) — "
            f"повторять нечего; статус: {note}")
    else:
        rerun_note = _red_rerun(conn, task_id, t, branch)
    outcome_text, answered = _ci_rerun_outcome(branch, rerun_note)

    # Требование 8: одна запись журнала — основание Оператора, id прогона
    # (внутри `rerun_note`) и исход ожидания.
    detail = (f"{rerun_note}; исход ожидания: {outcome_text}; "
              f"{CI_RERUN_REASON_MARKER}{reason}")
    store.journal(conn, task_id, "operator", CI_RERUN_ACTION, detail)
    print(f"[{task_id}] повтор CI ветки {branch}: {rerun_note}")
    print(f"[{task_id}] исход ожидания: {outcome_text}")
    if not answered:
        # Best-effort: сбой `gh` — именованный отказ, не трейсбек; запись
        # журнала выше уже названа тем же исходом (AC-9).
        sys.exit(f"[{task_id}] ci-rerun: отказ — {outcome_text}")
    if outcome_text.startswith(CI_RERUN_OUTCOME_GREEN):
        print("  дальше: " + cycle_hint.launch_text(
            conn, task_id, "auto", "(цикл прочитает новый статус CI сам и "
            "уведёт задачу из verifying)"))
    else:
        # Снова красный — второй повтор требует НОВОГО основания
        # (требование 10); подсказка называет и второй, обычный путь.
        print(f"  дальше: artel.py reject {task_id} \"причина\"  (вернуть в "
              f"разработку) либо ci-rerun с НОВЫМ основанием")


def _stuck_rerun(conn, task_id: str, branch: str, note: str) -> str:
    """Перезапуск прогонов зависших проверок (SPEC
    01M3Y75C9TY76083CG1PK00EM4, требование 3); итог — `note` перезапуска
    для журнала, как у `ci.trigger_rerun`.

    Сверки красного пути (sha красной записи журнала, флейк ли против
    главной ветки) здесь не о чем: статус «проверка зависла» прочитан
    только что по текущей голове ветки, и упавших заданий в нём нет.
    Прогон находится по самой зависшей проверке, не по sha коммита: у
    коммита бывает два прогона, и перезапуск «не того» ничего не даст.
    """
    check_ids = ci.stuck_check_ids(note)
    if not check_ids:
        _ci_rerun_refuse(
            conn, task_id,
            f"в статусе зависшего CI ветки {branch} не названо ни одного id "
            f"check-run — перезапускать нечего; статус: {note}")
    run_ids = []
    for check_id in check_ids:
        run_id, why = ci.check_run_workflow_run(check_id)
        if not run_id:
            _ci_rerun_refuse(
                conn, task_id,
                f"прогон workflow зависшей проверки {check_id} не найден: "
                f"{why}")
        if run_id not in run_ids:
            run_ids.append(run_id)
    return "; ".join(ci.trigger_rerun(branch, run_id=run_id)
                     for run_id in run_ids)


def _red_rerun(conn, task_id: str, t, branch: str) -> str:
    """Сверки завершённо-красного CI перед повтором (требования 4-6) и
    сам повтор (требование 7); итог — `note` `ci.trigger_rerun`."""
    from . import fsm  # отложенный импорт — см. докстринг модуля

    # Требование 4: красный статус относится к тому же коммиту, что стоит
    # головой ветки сейчас. Уехала голова — красный статус про другой
    # коммит, и повторять по нему нечего.
    head, why = ci.head_sha(branch)
    if not head:
        _ci_rerun_refuse(conn, task_id,
                         f"текущая голова ветки {branch} не определена: {why}")
    red_sha = _last_red_status_sha(conn, task_id)
    if not red_sha:
        _ci_rerun_refuse(
            conn, task_id,
            f"в журнале задачи нет записи «{fsm.VERIFYING_STATUS_ACTION}» о "
            f"завершённом красном CI — не с чем сверять голову ветки "
            f"{branch} ({head})")
    if not head.startswith(red_sha):
        _ci_rerun_refuse(
            conn, task_id,
            f"голова ветки {branch} уехала: красный статус CI, на котором "
            f"остановился цикл, относится к коммиту {red_sha}, а голова "
            f"ветки сейчас — {head}")

    # Требования 5-6: флейк ветки или дефект главной ветки. Сверяются
    # ИМЕНА заданий (обоснование — SPEC, требование 5); неизвестный статус
    # любой из двух сторон — отказ, а не повтор (инвариант 19): иначе
    # первый же сбой `gh` возвращал бы систему к перезапуску, маскирующему
    # дефект главной ветки (урок 12.09, красная главная ветка 22-26.09).
    branch_failed, why = ci.failed_check_names(head)
    if branch_failed is None:
        _ci_rerun_refuse(
            conn, task_id,
            f"имена упавших заданий головы ветки {branch} не прочитаны: {why}")
    main_sha = fsm._origin_main_sha(t["target"] or config.DEFAULT_TARGET)
    if not main_sha:
        _ci_rerun_refuse(
            conn, task_id,
            f"вершина главной ветки не определена (голова origin/"
            f"{config.MAIN_BRANCH} не прочитана) — сверить красноту ветки "
            f"с главной веткой нечем, а неизвестный статус не зелёный")
    main_failed, why = ci.failed_check_names(main_sha)
    if main_failed is None:
        _ci_rerun_refuse(
            conn, task_id,
            f"статус вершины главной ветки {main_sha} неизвестен: {why} — "
            f"неизвестный статус не зелёный, повтор маскировал бы дефект "
            f"главной ветки")
    shared = sorted(branch_failed & main_failed)
    if shared:
        _ci_rerun_refuse(
            conn, task_id,
            f"дефект main, не флейк: задание {', '.join(shared)} красно и "
            f"на вершине главной ветки {main_sha} — перезапускать нечего, "
            f"чинить нужно main")

    # Требование 7: повтор исполняет существующий узел — поиск прогона по
    # sha с предпочтением упавшего, `gh run rerun --failed`, ожидание
    # `gh run watch`. Ровно один вызов: цикла «до зелёного» здесь нет,
    # второй повтор — второе решение Оператора с новым основанием.
    return ci.trigger_rerun(branch)
