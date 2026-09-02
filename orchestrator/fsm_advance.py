"""Обработчики `cmd_advance` — один на состояние (SPEC T091, декомпозиция
диспетчеров fsm/runner): каждая функция — прежнее тело своей ветки
if/elif `orchestrator/fsm.py::_cmd_advance`, перенесённое без изменения
поведения. Диспетчер (выбор обработчика по `t["state"]`) остаётся в
`fsm.py` — эти функции не вызываются напрямую иначе, кроме тестов,
идущих через публичный `fsm.cmd_advance`.
"""
import shutil

from scripts import guard

from . import (acceptance, artifact_source, artifacts, budget, ci, config,
              fsm, fsm_autogate, gitcmd, store, workspace, yamlmini)
# Функция, не модуль (SPEC 01M1GCN1FPSC1A6WK9WD1Q1V8X, требование 5): этот
# же модуль ниже определяет обработчик состояния `review` под тем же
# именем `review` — `from . import review` тут вело бы к коллизии имён,
# как только определение функции переопределит имя модуля.
from .review import git_diff_part as _review_git_diff_part

# Причина отказа гейта ёмкости — дословно (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X,
# AC-13): снимок задачи крупнее потолка `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES`
# не помещается ни в один прогон ревьювера — вердикт по такому объёму
# ненадёжен по построению, решение (разделить задачу или поднять потолок)
# — только Оператора (AC-14).
CAPACITY_GATE_REASON = "снимок не помещается в один контекст ревью — разделить задачу"


def spec_writing(conn, task_id: str, t, tdir, target: str, state: str) -> bool:
    # Батч вопросов analyst (SPEC T025, требование 4): файл на месте —
    # эскалация немедленно, не дожидаясь статуса SPEC.md, тем же
    # приёмом, что маркер `escalate` в tests_writing (T023). Второй
    # батч по тому же ТЗ структурно недостижим раньше ответа: пока
    # задача в escalated, run для неё не стартует.
    #
    # Рабочее дерево точно на чужой ветке-источнике `tasks/<id>/` (SPEC
    # T047, требования 1, 3; T094 требование 10 — артефактная ветка
    # пульта для внешнего target, `artifact_source.resolve`) — и статус
    # SPEC.md, и батч QUESTIONS.md читаются С НЕЁ (класс-дефект
    # T030/T046: главная копия пульта на main видит только то, что
    # закоммичено туда же, не в ветку задачи/артефактную ветку). Иначе —
    # прежний путь через диск, не тронутый T047.
    branch, foreign = artifact_source.resolve(conn, task_id)
    spec_text = None
    if foreign:
        # QUESTIONS.md необязателен (большинство задач его не заводят)
        # — отсутствие на ветке не отказ, тот же приём, что
        # `_tests_writing_ac_state` уже применяет к необязательному
        # каталогу `acceptance_tests/` (T031).
        q_rel = f"tasks/{task_id}/QUESTIONS.md"
        q_paths = gitcmd.ls_tree_files(branch, q_rel)
        if q_paths is None:
            detail = (f"дерево не на ветке задачи {branch} — не "
                      f"удалось проверить наличие QUESTIONS.md")
            store.journal(conn, task_id, "fsm",
                          "переход отклонён: дерево не на ветке задачи",
                          detail)
            print(f"[{task_id}] переход отклонён: {detail}")
            return False
        if q_paths:
            q_text = fsm._read_branch_text_or_refuse(conn, task_id, branch,
                                                      "QUESTIONS.md")
            if q_text is None:
                return False
            if fsm.guard_refuses(conn, task_id, tdir / "QUESTIONS.md",
                                 text=q_text):
                return True
            answer_baseline = fsm._answer_baseline_or_refuse(conn, task_id, tdir)
            if answer_baseline is None:
                return False
            store.update_task(
                conn, task_id, escalated_from="spec_writing",
                answer_baseline=answer_baseline)
            store.set_state(
                conn, task_id, "escalated", "fsm",
                expected_state=state,
                detail=f"analyst: батч вопросов по ТЗ — ветка {branch}:{q_rel}")
            print(f"[{task_id}] эскалация analyst: см. ветку {branch}, "
                  f"{q_rel}")
            return False
        spec_text = fsm._read_branch_text_or_refuse(conn, task_id, branch,
                                                     "SPEC.md")
        if spec_text is None:
            return False
        meta = yamlmini.frontmatter(spec_text) or {}
    else:
        questions = tdir / "QUESTIONS.md"
        if questions.exists():
            if fsm.guard_refuses(conn, task_id, questions):
                return True
            answer_baseline = fsm._answer_baseline_or_refuse(conn, task_id, tdir)
            if answer_baseline is None:
                return False
            store.update_task(
                conn, task_id, escalated_from="spec_writing",
                answer_baseline=answer_baseline)
            store.set_state(
                conn, task_id, "escalated", "fsm", expected_state=state,
                detail=f"analyst: батч вопросов по ТЗ — {questions}")
            print(f"[{task_id}] эскалация analyst: см. {questions}")
            return False
        meta = artifacts.frontmatter(tdir / "SPEC.md")
    if meta.get("status") == "ready":
        if fsm._dirty_refuses(conn, task_id, target, "SPEC.md"):
            return False
        if fsm.guard_refuses(conn, task_id, tdir / "SPEC.md", text=spec_text):
            return True
        # До смены состояния: потолок задачи должен стоять уже к тому
        # моменту, когда Оператор смотрит на неё на гейте SPEC.
        budget.apply_spec_budget(conn, t, meta)
        store.set_state(conn, task_id, "spec_gate", "fsm",
                        expected_state=state, detail="SPEC готов — ждёт approve")
    else:
        print(f"[{task_id}] SPEC.md ещё не ready — нечего продвигать")
    return False


def review(conn, task_id: str, t, tdir, target: str, state: str) -> bool:
    # Рабочее дерево точно на чужой ветке-источнике `tasks/<id>/` (SPEC
    # T047, требование 2; T094 требование 10) — вердикт REVIEW.md
    # (status, iteration) читается С НЕЁ, тем же приёмом, что SPEC.md
    # выше (класс-дефект T030/T045: главная копия пульта на main не
    # видит вердикт, закоммиченный только в ветку/артефактную ветку).
    # Иначе — прежний путь через диск, не тронутый T047.
    branch, foreign = artifact_source.resolve(conn, task_id)
    review_text = None
    if foreign:
        review_text = fsm._read_branch_text_or_refuse(conn, task_id, branch,
                                                        "REVIEW.md")
        if review_text is None:
            return False
        meta = yamlmini.frontmatter(review_text) or {}
    else:
        meta = artifacts.frontmatter(tdir / "REVIEW.md")
    status = meta.get("status")
    if status not in config.REVIEW_VERDICTS:
        print(f"[{task_id}] REVIEW.md status={status} — жду вердикта")
        return False
    if fsm._dirty_refuses(conn, task_id, target, "REVIEW.md"):
        return False
    if fsm.guard_refuses(conn, task_id, tdir / "REVIEW.md", text=review_text):
        return True

    iteration = artifacts.fresh_verdict_iteration(meta, t["reviewed_iter"])
    if iteration is None:
        detail = (
            f"вердикт REVIEW.md (status={status}, "
            f"iteration={meta.get('iteration', '—')}) уже учтён — "
            f"жду новый прогон ревьювера с iteration: {t['reviewed_iter'] + 1}"
        )
        store.journal(conn, task_id, "fsm", "переход отклонён", detail)
        print(f"[{task_id}] {detail}")
        print(f"  дальше: artel.py run {task_id}  (прогон ревьювера)")
        return False
    store.update_task(conn, task_id, reviewed_iter=iteration)

    if status == "approved":
        # Реестр замечаний (SPEC T100, требование 5): вердикт approved
        # не проходит этот гейт, пока в реестре есть запись со статусом
        # отличным от accepted — ни fixed, ни rejected сами по себе не
        # закрывают замечание (ANSWER-1, симметрия). Применяется только
        # при schema_version >= 3 (требование 6); guard уже подтвердил
        # структуру этого REVIEW.md выше по функции (fsm.guard_refuses)
        # — здесь читается тот же текст, отдельного чтения не заводится.
        if guard.requires_registry(meta):
            registry_text = review_text
            if registry_text is None:
                registry_text = (tdir / "REVIEW.md").read_text(encoding="utf-8")
            unresolved = [r["id"] for r in guard.registry_records(registry_text)
                         if r.get("status") != "accepted"]
            if unresolved:
                detail = (f"реестр замечаний не закрыт: "
                          f"{', '.join(unresolved)} — каждая запись обязана "
                          f"дойти до status: accepted явным решением "
                          f"ревьювера, прежде чем approved пройдёт гейт")
                store.journal(conn, task_id, "fsm",
                              "переход отклонён: реестр замечаний", detail)
                print(f"[{task_id}] переход отклонён: {detail}")
                print(f"  дальше: доведи записи {', '.join(unresolved)} до "
                      f"accepted и повтори artel.py advance {task_id}")
                return False
        # Прогон приёмки (SPEC T023, требование 6): красный
        # acceptance-тест чинит код разработчик, не переписывает тест
        # (тесты залочены — см. ветку in_dev выше).
        #
        # SPEC T045, побочная находка (PLAN, «Подход»): после T045
        # главная копия пульта остаётся на main, не на ветке задачи —
        # `tasks/<id>/acceptance_tests` читается из worktree задачи,
        # если он заведён и стоит на своей ветке; иначе (легаси-
        # песочницы без реального git, worktree ещё не заведён)
        # прежний путь — с диска главной копии. Внешний target (SPEC
        # T094, требование 10, реестр PLAN.md пункт 2 «лок
        # acceptance_tests»): живого worktree с этим каталогом на диске
        # нет вовсе — `acceptance_tests/` живёт только в артефактной
        # ветке пульта (`branch` уже резолвлен выше), материализуется во
        # временный каталог на время прогона и убирается сразу после.
        acc_tdir = tdir
        cleanup_acc = None
        if target != config.DEFAULT_TARGET:
            acc_tdir = acceptance.materialize_from_branch(task_id, branch)
            cleanup_acc = acc_tdir
        elif workspace.on_task_branch(task_id, t["branch"]) is True:
            acc_tdir = workspace.path(task_id) / "tasks" / task_id
        try:
            green, tail = acceptance.run(acc_tdir)
            if not green:
                detail = f"acceptance_tests красные:\n{tail}"
                store.journal(conn, task_id, "fsm",
                              "переход отклонён: приёмочные тесты", detail)
                print(f"[{task_id}] переход отклонён: приёмочные тесты "
                      f"красные")
                print(tail)
                print(f"  дальше: почини код (не тест) и повтори "
                      f"artel.py advance {task_id}")
                return False
            card = acceptance.summary(acc_tdir)
        finally:
            if cleanup_acc is not None:
                shutil.rmtree(cleanup_acc, ignore_errors=True)
        store.journal(conn, task_id, "fsm", "приёмочные тесты пройдены",
                      card)
        print(f"[{task_id}] {card}")
        # Вставка verifying между review и acceptance (SPEC T079,
        # требование 4; ADR-0003 п.10): свежий approved + зелёные
        # acceptance_tests раньше вели напрямую в acceptance — теперь
        # ждут ещё и зелёного CI головного коммита ветки. Автогейт
        # acceptance (_maybe_autogate_acceptance) переехал на вход
        # `verifying -> acceptance` ниже — тот же вызов, новая точка.
        store.update_task(conn, task_id, verifying_attempts=0)
        store.set_state(conn, task_id, "verifying", "fsm",
                        expected_state=state,
                        detail="ревью пройдено — жду зелёного CI ветки")
    elif status == "changes_requested":
        iters = t["review_iters"] + 1
        if iters >= config.LIMIT_REVIEW_ITERS:
            store.set_state(conn, task_id, "escalated", "fsm",
                            expected_state=state,
                            detail=f"лимит ревью "
                            f"{config.LIMIT_REVIEW_ITERS} исчерпан")
        else:
            store.update_task(conn, task_id, review_iters=iters)
            store.set_state(conn, task_id, "in_dev", "fsm",
                            expected_state=state,
                            detail=f"замечания ревью, итерация {iters}")
            fsm._maybe_ensure_draft_mr(conn, task_id)
    elif status == "escalate":
        answer_baseline = fsm._answer_baseline_or_refuse(conn, task_id, tdir)
        if answer_baseline is None:
            return False
        store.update_task(conn, task_id, answer_baseline=answer_baseline)
        store.set_state(conn, task_id, "escalated", "fsm",
                        expected_state=state, detail="эскалация от ревьювера")
    return False


def verifying(conn, task_id: str, t, tdir, target: str, state: str) -> bool:
    # Ожидание зелёного CI головного коммита ветки задачи (SPEC T079,
    # требования 5-7 + SPEC T086, требования 2-4). Четыре исхода
    # различает `ci.verifying_status` (роадмап P3, T040): зелёный,
    # «проверок нет вовсе», «проверки идут» (в т.ч. по gh run list),
    # CI красный — трактовка не меняется относительно T079/ADR-0009:
    # только зелёный двигает задачу, остальные три ждут, различаясь
    # только диагностикой в журнале. Владелец опроса и его частота —
    # теперь `auto` (orchestrator/auto.py, требование 1); этот вызов
    # остаётся тем же ОДНИМ опросом что и раньше при ручном advance
    # (требование 5, AC-8). Ни один исход не создаёт коммитов и не
    # «будит» CI (требование 7, AC-10).
    branch = t["branch"]
    outcome, note = ci.verifying_status(branch)
    store.journal(conn, task_id, "orchestrator",
                  fsm.VERIFYING_STATUS_ACTION, note)
    if outcome == ci.VERIFYING_GREEN:
        print(f"[{task_id}] {note}")
        store.set_state(conn, task_id, "acceptance", "fsm",
                        expected_state=state, detail=note)
        # Каталог acceptance_tests/ для автогейта (SPEC T094, требование
        # 10) — тем же приёмом, что `review()` выше: внешний target не
        # несёт живого worktree, читаем из артефактной ветки пульта во
        # временный каталог, чужой CI-запрос (`branch` = код-ветка,
        # выше) этого не касается — материализация нужна только
        # `acceptance_tests/`, не коду.
        acc_tdir = tdir
        cleanup_acc = None
        if target != config.DEFAULT_TARGET:
            artifact_branch_name, _ = artifact_source.resolve(conn, task_id)
            acc_tdir = acceptance.materialize_from_branch(
                task_id, artifact_branch_name)
            cleanup_acc = acc_tdir
        elif workspace.on_task_branch(task_id, t["branch"]) is True:
            acc_tdir = workspace.path(task_id) / "tasks" / task_id
        try:
            fsm_autogate._maybe_autogate_acceptance(conn, task_id, t, acc_tdir,
                                                   t["reviewed_iter"])
        finally:
            if cleanup_acc is not None:
                shutil.rmtree(cleanup_acc, ignore_errors=True)
        return False
    # Счётчик попыток остаётся информационной записью (требование 3,
    # AC-7) — эскалацию решает только прошедшее время с момента входа
    # в состояние, не число вызовов advance.
    store.update_task(
        conn, task_id, verifying_attempts=(t["verifying_attempts"] or 0) + 1)
    elapsed = fsm._verifying_elapsed_seconds(t["updated_at"])
    if elapsed >= config.VERIFYING_CEILING_SEC:
        store.set_state(conn, task_id, "escalated", "fsm",
                        expected_state=state,
                        detail=f"потолок ожидания CI в verifying "
                        f"исчерпан ({config.VERIFYING_CEILING_SEC}с) — "
                        f"последний статус: {note}")
        print(f"[{task_id}] потолок ожидания CI исчерпан — эскалация")
    else:
        print(f"[{task_id}] {note} — жду "
             f"({int(elapsed)}с/{config.VERIFYING_CEILING_SEC}с)")
    return False


def tests_writing(conn, task_id: str, t, tdir, target: str, state: str) -> bool:
    # test_author закончил: каждый AC-n — тест либо пометка
    # manual/skip/escalate (SPEC T023, требование 4). Ветка-источник
    # `tasks/<id>/` (SPEC T094, требование 10) — артефактная ветка
    # пульта для внешнего target, не кодовая ветка целевого (та в
    # `config.ROOT` не существует вовсе).
    branch, _ = artifact_source.resolve(conn, task_id)
    result = fsm._tests_writing_ac_state(conn, task_id, branch, tdir)
    if result is None:
        return False
    tested, markers, errors = result
    escalations = {n: reason for n, (kind, reason) in markers.items()
                  if kind == "escalate"}
    if escalations:
        detail = "; ".join(f"AC-{n}: {reason}"
                           for n, reason in sorted(escalations.items()))
        answer_baseline = fsm._answer_baseline_or_refuse(conn, task_id, tdir)
        if answer_baseline is None:
            return False
        store.update_task(
            conn, task_id, escalated_from="tests_writing",
            answer_baseline=answer_baseline)
        store.set_state(conn, task_id, "escalated", "fsm",
                        expected_state=state,
                        detail=f"test_author: критерий неисполним тестом — "
                        f"{detail}")
        print(f"[{task_id}] эскалация test_author: {detail}")
        return False
    if errors:
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: трассируемость AC",
                      "; ".join(errors))
        print(f"[{task_id}] переход отклонён: не все критерии "
              f"покрыты тестом или пометкой")
        for e in errors:
            print(f"  - {e}")
        print(f"  дальше: допиши {tdir / 'acceptance_tests'} и повтори "
              f"artel.py advance {task_id}")
        return False
    store.set_state(conn, task_id, "in_dev", "fsm", expected_state=state,
                    detail="приёмочные тесты готовы — трассируемость AC "
                    "пройдена")
    # Лок (требование 5): значение, которое set_state только что
    # посчитал в fixed_sha (T021), становится планкой acceptance_tests/
    # для in_dev -> review — тот же sha, не новая фиксация.
    store.update_task(conn, task_id,
                      tests_locked_sha=store.get_task(
                          conn, task_id)["fixed_sha"])
    fsm._maybe_ensure_draft_mr(conn, task_id)
    return False


def _capacity_gate_refuses(conn, task_id: str, t, state: str) -> bool:
    """Гейт ёмкости diff снимка на `in_dev -> review` (tasks/
    01M1GCN1FPSC1A6WK9WD1Q1V8X, требование 5, AC-12..AC-16): полный diff
    снимка (`git diff config.MAIN_BRANCH...<ветка задачи>`) — тот же
    расчёт, что и «полный» `diff_type` в `review.review_package` при
    `iteration == 1` (T029) — не имеет права превышать
    `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES`. Пересчитывается заново на
    КАЖДОМ входе в гейт, не по инкременту прошлой итерации (AC-15).

    `True` — переход отклонён, отказ уже журналирован (AC-13); гейт сам
    не эскалирует и не делает ничего автоматически (AC-14) — задача
    остаётся в `in_dev` до решения Оператора."""
    diff, _, _ = _review_git_diff_part(config.MAIN_BRANCH, t["branch"])
    size = len(diff.encode("utf-8"))
    if size <= config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES:
        return False
    detail = (f"{CAPACITY_GATE_REASON} ({task_id} «{t['title']}»): diff "
             f"снимка {size} байт > потолка "
             f"{config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES} байт")
    store.journal(conn, task_id, "fsm",
                  "переход отклонён: гейт ёмкости diff", detail)
    print(f"[{task_id}] переход отклонён: {detail}")
    print(f"  дальше: решение Оператора — разделить задачу или поднять "
          f"потолок (ADR-0002)")
    return True


def in_dev(conn, task_id: str, t, tdir, target: str, state: str) -> bool:
    # разработчик закончил: PLAN ready и ветка запушена -> в ревью
    #
    # Рабочее дерево точно на чужой ветке-источнике `tasks/<id>/` (SPEC
    # T031; T094 требование 10) — PLAN.md читается С НЕЁ (иначе гейт
    # «PLAN.md не ready» молча держит переход и на чужом чекауте нечего
    # проверять дальше — без этого лок ниже никогда не достигается со
    # стороны AC-3); иначе прежний путь через диск, не тронутый T031.
    # Чтение — общий узел `_read_branch_text_or_refuse` (T047), тот же
    # приём теперь и у SPEC.md/REVIEW.md выше.
    branch, foreign = artifact_source.resolve(conn, task_id)
    plan_text = None
    if foreign:
        plan_text = fsm._read_branch_text_or_refuse(conn, task_id, branch,
                                                     "PLAN.md")
        if plan_text is None:
            return False
        plan_meta = yamlmini.frontmatter(plan_text) or {}
    else:
        plan_meta = artifacts.frontmatter(tdir / "PLAN.md")
    if plan_meta.get("status") in ("ready", "approved"):
        if fsm._dirty_refuses(conn, task_id, target, "PLAN.md"):
            return False
        if fsm.guard_refuses(conn, task_id, tdir / "PLAN.md", text=plan_text):
            return True
        locked = t["tests_locked_sha"]
        if locked:
            # Ветка-источник tasks/<id>/, не литерал "HEAD" (SPEC T031,
            # AC-3): чужой чекаут рабочей копии не должен сверять лок с
            # чужой веткой вместо своей. Свой чекаут (обычный путь) или
            # ветка ещё не создана ролью — тот же "HEAD", что и до T031.
            #
            # Внешний target: `locked` (`tests_locked_sha`/`fixed_sha`)
            # остаётся на легаси-схеме фиксации (`fixation._fix_external`
            # — коммит `.artel/projects/<target>/`, PLAN.md, реестр
            # пункт 1, «не заменяя легаси-строку», требование 9) — sha
            # из ЭТОГО репозитория `config.ROOT` не знает независимо от
            # выбора `lock_ref` здесь. `gitcmd.diff_paths` поэтому не
            # ответит на `locked` и сверка ниже уйдёт в существующий
            # fail-closed отказ («лок не проверен») — не новый регресс
            # этой правки, а незакрытый остаток легаси-схемы `fixed_sha`
            # (сознательно вне объёма этой итерации, тот же довод, что
            # и у требования 9).
            lock_ref = branch if foreign else "HEAD"
            diff = gitcmd.diff_paths(
                locked, lock_ref, f"tasks/{task_id}/acceptance_tests")
            if diff is None:
                # git не ответил (недостижимый sha после rebase/squash,
                # сбой команды) — сверять нечего, но это не «нечего
                # сверять как задумано»: fail-closed тем же принципом,
                # что и fixation.check_integrity() при неответившем git
                # (ADR-0002, «неизвестный статус — это нельзя»).
                detail = (f"лок acceptance_tests/ не проверен: git не "
                          f"ответил на sha {locked} — сверка невозможна")
                store.journal(conn, task_id, "fsm",
                              "переход отклонён: лок приёмочных тестов",
                              detail)
                print(f"[{task_id}] переход отклонён: {detail}")
                print(f"  дальше: разберись, почему git не отвечает на "
                      f"tests_locked_sha={locked}, и повтори "
                      f"artel.py advance {task_id}")
                return False
            if diff:
                detail = (f"acceptance_tests/ изменены после лока "
                          f"(sha {locked}) — спор с тестом = эскалация, "
                          f"не правка")
                store.journal(conn, task_id, "fsm",
                              "переход отклонён: лок приёмочных тестов",
                              detail)
                print(f"[{task_id}] переход отклонён: {detail}")
                print(f"  дальше: верни acceptance_tests/ как было, "
                      f"либо эскалируй разногласие Оператору")
                return False
        # Сверка свежести ветки до гейта (SPEC T051, требования 1, 4):
        # последний шаг перед самим переходом — отставшая ветка либо
        # подтягивается и проходит приёмку, либо эскалирует и возврата
        # уже не будет.
        if fsm._pull_main_or_escalate(conn, task_id, t, state) == "escalated":
            return False
        if _capacity_gate_refuses(conn, task_id, t, state):
            return False
        store.set_state(conn, task_id, "review", "fsm",
                        expected_state=state, detail="MR готов — прогон ревьювера")
    else:
        print(f"[{task_id}] PLAN.md не ready — разработчик ещё работает")
    return False
