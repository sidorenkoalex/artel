"""Обработчики `cmd_advance` — один на состояние (SPEC T091, декомпозиция
диспетчеров fsm/runner): каждая функция — прежнее тело своей ветки
if/elif `orchestrator/fsm.py::_cmd_advance`, перенесённое без изменения
поведения. Диспетчер (выбор обработчика по `t["state"]`) остаётся в
`fsm.py` — эти функции не вызываются напрямую иначе, кроме тестов,
идущих через публичный `fsm.cmd_advance`.
"""
from datetime import datetime

from scripts import guard

from . import (acceptance, agent_log, artifact_source, artifacts, budget,
              ci, config, fsm, fsm_autogate, gitcmd, github_adapter, store,
              workspace, yamlmini)
# Функция, не модуль (SPEC 01M1GCN1FPSC1A6WK9WD1Q1V8X, требование 5): этот
# же модуль ниже определяет обработчик состояния `review` под тем же
# именем `review` — `from . import review` тут вело бы к коллизии имён,
# как только определение функции переопределит имя модуля.
from .review import EMPTY_DIFF_TEXT as _EMPTY_DIFF_TEXT
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

    if status == "approved" and not t["is_canary"]:
        # Голова ветки задачи на origin — предусловие входа в verifying
        # (SPEC 01M1GS5HZ1JXFGKVR95HEW0AEZ, требования 1-3, AC-1..AC-5):
        # ДО потребления свежести вердикта (`store.update_task` ниже) —
        # иначе провалившийся push съел бы свежесть первым же заходом и
        # заблокировал повторный advance после починки origin (AC-5)
        # тем же «вердикт уже учтён», что и рефьюзл выше.
        #
        # Канареечная задача (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование
        # 11/AC-11) пропускается: её `verifying` не ждёт CI и не читает
        # origin вовсе (`canary._kill_at_verifying` убивает задачу сразу
        # по входу) — предусловие существует ТОЛЬКО ради последующего
        # опроса CI на реальном origin, которого у эфемерного клона нет
        # и не будет (origin-заглушка `canary.ORIGIN_STUB_URL`, требование
        # 2/3): push туда гарантированно проваливается по построению, не
        # по сбою — тот же принцип, каким уже пользуются
        # `github_adapter.ensure_draft_mr`/`undraft_mr` (`t["is_canary"]`).
        push_ok, push_detail = github_adapter.ensure_head_in_origin(
            conn, task_id, t["branch"])
        if not push_ok:
            store.journal(conn, task_id, "fsm",
                          "переход отклонён: голова не в origin", push_detail)
            print(f"[{task_id}] переход отклонён: {push_detail}")
            print(f"  дальше: почини доступ к origin и повтори "
                  f"artel.py advance {task_id}")
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
        # ветке пульта (`branch` уже резолвлен выше); материализуется НА
        # МЕСТЕ в workspace target'а (SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS,
        # требование 1-2, AC-1/AC-2/AC-5 — не во временный каталог, тот
        # же узел выбора рабочего каталога кода, что `runner.role_cwd`),
        # прогон идёт с `cwd`, равным этому же каталогу.
        acc_tdir = tdir
        run_cwd = config.ROOT
        if target != config.DEFAULT_TARGET:
            run_cwd = config.PROJECTS / target / "workspace"
            run_cwd.mkdir(parents=True, exist_ok=True)
            acc_tdir = acceptance.materialize_from_branch(task_id, branch,
                                                           run_cwd)
        elif workspace.on_task_branch(task_id, t["branch"]) is True:
            run_cwd = workspace.path(task_id)
            acc_tdir = run_cwd / "tasks" / task_id
        green, tail = acceptance.run(acc_tdir, code_root=run_cwd)
        # Fingerprint окружения (SPEC T101, требование 4б, AC-5) —
        # часть исхода прогона приёмочных тестов, тем же приёмом, что
        # и у события агентного шага (`runner.py`): значение поля
        # `detail` существующего журнального события, без новой
        # таблицы/колонки.
        fingerprint = agent_log.environment_fingerprint()
        if not green:
            detail = (f"acceptance_tests красные:\n{tail}\n"
                      f"окружение: {fingerprint}")
            store.journal(conn, task_id, "fsm",
                          "переход отклонён: приёмочные тесты", detail)
            print(f"[{task_id}] переход отклонён: приёмочные тесты "
                  f"красные")
            print(tail)
            print(f"  дальше: почини код (не тест) и повтори "
                  f"artel.py advance {task_id}")
            return False
        card = acceptance.summary(acc_tdir)
        store.journal(conn, task_id, "fsm", "приёмочные тесты пройдены",
                      f"{card}\nокружение: {fingerprint}")
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
        # несёт живого worktree, читаем из артефактной ветки пульта на
        # МЕСТО workspace target'а (SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS,
        # требования 1-2, AC-5 — не во временный каталог), чужой CI-запрос
        # (`branch` = код-ветка, выше) этого не касается — материализация
        # нужна только `acceptance_tests/`, не коду.
        acc_tdir = tdir
        if target != config.DEFAULT_TARGET:
            artifact_branch_name, _ = artifact_source.resolve(conn, task_id)
            code_dir = config.PROJECTS / target / "workspace"
            code_dir.mkdir(parents=True, exist_ok=True)
            acc_tdir = acceptance.materialize_from_branch(
                task_id, artifact_branch_name, code_dir)
        elif workspace.on_task_branch(task_id, t["branch"]) is True:
            acc_tdir = workspace.path(task_id) / "tasks" / task_id
        fsm_autogate._maybe_autogate_acceptance(conn, task_id, t, acc_tdir,
                                               t["reviewed_iter"])
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
    branch, foreign = artifact_source.resolve(conn, task_id)
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
    # Лок (требование 5): планка acceptance_tests/ для in_dev -> review.
    #
    # Foreign (A7, требование 2 — единая логика для ЛЮБОГО target,
    # включая артель, теперь всегда True): sha АРТЕФАКТНОЙ ВЕТКИ пульта
    # (`config.ROOT`, настоящий git, `branch` уже resolved выше) — не
    # `fixed_sha`, который `set_state` только что посчитал через
    # `fixation._fix_external`. Тот коммитит `config.PROJECTS/<target>/`
    # — репозиторий, в который M1-механика (артефактная ветка,
    # `checkpoint._commit_external_step_artifacts`) ничего не пишет
    # (найдено на AC-7/AC-8: сверка против него никогда не видит диффа
    # — «замок» пропускал бы ЛЮБУЮ правку `acceptance_tests/` молча,
    # `LockTest.test_edit_after_lock_blocks_in_dev_to_review`). Не-foreign
    # (сегодня недостижимо после генерализации self — оставлено на
    # случай песочницы без git, где `on_foreign_branch` всегда False) —
    # прежнее поведение, `fixed_sha`.
    locked_sha = (gitcmd.branch_head_sha(branch) if foreign
                 else store.get_task(conn, task_id)["fixed_sha"])
    store.update_task(conn, task_id, tests_locked_sha=locked_sha)
    fsm._maybe_ensure_draft_mr(conn, task_id)
    return False


def _capacity_gate_refuses(conn, task_id: str, t, state: str) -> bool:
    """Гейт ёмкости diff снимка на `in_dev -> review` (tasks/
    01M1GCN1FPSC1A6WK9WD1Q1V8X, требование 5, AC-12..AC-16): diff снимка
    БЕЗ `tasks/<id>/` (`git diff gitcmd.diff_base(ветка)...<ветка задачи>
    -- . ':!tasks/<id>/'`, tasks/01M1RA0N6FCFEQBB82K58GM12X, AC-1; база —
    точка расхождения с origin/main или локальным main, не голый
    `config.MAIN_BRANCH`, tasks/01M1SG9T962WJJ31S282GWM0EN) — тот же
    расчёт, что и «полный» `diff_type` в `review.review_package` при
    `iteration == 1` (T029) — не имеет права превышать
    `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES`. Копия артефактов задачи
    (SPEC/PLAN/залоченная планка) в кодовой ветке исключена из меры
    целиком — она не предмет ревью-диффа (ревьювер получает её отдельными
    компонентами пакета) и не имеет права раздувать гейт (AC-1/AC-4);
    diff кода сам по себе крупнее потолка отклоняет переход тем же
    способом, что и до этой задачи (AC-5). Пересчитывается заново на
    КАЖДОМ входе в гейт, не по инкременту прошлой итерации (AC-15).

    `True` — переход отклонён, отказ уже журналирован (AC-13); гейт сам
    не эскалирует и не делает ничего автоматически (AC-14) — задача
    остаётся в `in_dev` до решения Оператора.

    git не ответил на сам diff — fail-closed, не fail-open (R1-F2,
    REVIEW.md итерация 1, major): `git_diff_part` в этом случае отдаёт
    короткую строку `"(не собран: <reason>)"` вместо текста diff, и
    измерять байты именно этой строки значит пропускать переход, так и
    не выяснив фактический размер снимка — тот же принцип «неизвестный
    статус — это нельзя» (ADR-0002), что уже применён парой функций выше
    в этом же файле для лока `acceptance_tests/`. Второй diff (только
    `tasks/<id>/`, только на пути уже подтверждённого отказа — нужен лишь
    для второй цифры сообщения, AC-3) сбоем git отказ не отменяет: первая
    цифра (код) уже превысила потолок — вторая цифра в сообщении в этом
    случае явно названа «неизвестна», а не вымышленным числом.

    Diff артефактов реально пуст (git ответил успешно, но пустой строкой) —
    вторая цифра обязана быть 0, а не байтовым размером строки-плейсхолдера
    `review.EMPTY_DIFF_TEXT`, которую `git_diff_part` подставляет для показа
    (R1-F1, REVIEW.md итерации 1-3): сравнение с этой константой явно
    отличает «пусто» от «есть содержимое» перед подсчётом байт — тем же
    приёмом мерится и `code_size` ниже, хотя там пустой код-diff и так не
    превысил бы потолок.

    Внешний (не self) target — гейт не проверяется вовсе, тем же
    доводом «сознательно вне объёма этой итерации», что уже
    зафиксирован парой функций выше в этом же файле для лока
    `acceptance_tests/` с внешним target: `git diff config.MAIN_BRANCH
    ...<ветка задачи>` в `config.ROOT` — репозитории ПУЛЬТА — не видит
    настоящий код внешнего target (тот живёт в отдельном репозитории
    `config.PROJECTS/<target>/workspace`), а до самого перехода
    `tasks/<id>/` для внешнего target ещё не закоммичен в свою ветку
    (коммитит `fixation._fix_external` уже ПОСЛЕ решения перейти,
    `ExternalTargetAdvanceIgnoresDirtyCheckTest`) — fail-closed здесь
    заблокировал бы КАЖДЫЙ переход `in_dev -> review` для КАЖДОЙ задачи
    любого внешнего target навсегда, а не редкий сбой git."""
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return False
    tasks_prefix = f"tasks/{task_id}/"
    # База сравнения — merge-base с origin/main или локальным main (tasks/
    # 01M1SG9T962WJJ31S282GWM0EN, AC-1/AC-3), не голый `config.MAIN_BRANCH`:
    # локальный пин по построению отстаёт от origin/main, которую ветка
    # задачи подтягивает, и раздувает снимок чужими коммитами.
    base = gitcmd.diff_base(t["branch"])
    if base is None:
        detail = (f"гейт ёмкости: git не ответил на определение базы "
                 f"сравнения (merge-base с origin/{config.MAIN_BRANCH} "
                 f"либо локальным {config.MAIN_BRANCH}) для ветки "
                 f"{t['branch']} — сверка размера невозможна")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: гейт ёмкости diff", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        print(f"  дальше: разберись, почему git не отвечает на merge-base "
              f"для {t['branch']}, и повтори artel.py advance {task_id}")
        return True
    code_diff, _, reason = _review_git_diff_part(
        base, t["branch"], pathspec=(".", f":!{tasks_prefix}"))
    if reason:
        detail = (f"гейт ёмкости: git не ответил на diff снимка "
                 f"({base}...{t['branch']}) — сверка размера невозможна: "
                 f"{reason}")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: гейт ёмкости diff", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        print(f"  дальше: разберись, почему git не отвечает на diff "
              f"{base}...{t['branch']}, и повтори "
              f"artel.py advance {task_id}")
        return True
    code_size = (0 if code_diff == _EMPTY_DIFF_TEXT
                else len(code_diff.encode("utf-8")))
    if code_size <= config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES:
        return False
    artifacts_diff, _, artifacts_reason = _review_git_diff_part(
        base, t["branch"], pathspec=(tasks_prefix,))
    if artifacts_reason:
        artifacts_note = f"неизвестен (git не ответил: {artifacts_reason})"
    elif artifacts_diff == _EMPTY_DIFF_TEXT:
        artifacts_note = "0 байт (изменений нет)"
    else:
        artifacts_note = f"{len(artifacts_diff.encode('utf-8'))} байт"
    # Источник базы в сообщении (требование 4/AC-6) — Оператор видит, с чем
    # реально сравнивали, не только литерал diff-диапазона.
    source = gitcmd.diff_base_source(t["branch"])
    detail = (f"{CAPACITY_GATE_REASON} ({task_id} «{t['title']}», база "
             f"сравнения {base} от {source}): diff кода {code_size} байт "
             f"> потолка {config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES} байт "
             f"(исключённые артефакты {tasks_prefix}: {artifacts_note})")
    store.journal(conn, task_id, "fsm",
                  "переход отклонён: гейт ёмкости diff", detail)
    print(f"[{task_id}] переход отклонён: {detail}")
    print(f"  дальше: решение Оператора — разделить задачу или поднять "
          f"потолок (ADR-0002)")
    return True


# Маркер мандата Оператора на расширение зон (SPEC 01M1P9QCHPHSCEA6TK13PV85SP,
# ANSWER-1.md, п.2, канал ADR-0012) — строка в ЛЮБОМ ANSWER-n.md задачи,
# разбирается только по этому префиксу; свободный текст ANSWER не
# анализируется.
_ZONES_MANDATE_MARKER = "Расширение зон разрешено:"


def _split_zone_paths(raw) -> list[str]:
    """Список путей через запятую — тот же формат, что несёт `zones:` части
    1 (01M1NKVPD2A79PQ6K0JVV1B2Q1) и строки `Пути:`/`Расширение зон
    разрешено:` ANSWER-1.md этой задачи. `raw` — `None`/пустая строка (поле
    не заполнено) даёт пустой список, не ошибку."""
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _touches_zone(path: str, zones: list[str]) -> bool:
    # «Путь == зона или начинается с неё» — та же формула префикса, что
    # `fsm_merge_gate._touches_protected_path` для `PROTECTED_PATHS`: зоны-
    # директории несут trailing `/` (COMMON_ZONES: "tests/"), зоны-файлы —
    # нет, сравниваются буквально.
    return any(path == z or path.startswith(z) for z in zones)


def _plan_zones_extension_paths(plan_text: str) -> list[str] | None:
    """Пути раздела `## Расширение зон` PLAN.md (ANSWER-1.md, п.1: строка
    `Пути: <путь1>, <путь2>`). `None` — раздела нет вовсе, либо в нём нет
    строки `Пути:` — исключение AC-3 не применяется, дифф сверяется только
    с `zones`/`zones_extension`/`COMMON_ZONES` (обычный AC-1)."""
    body = guard.section_body(plan_text, "Расширение зон")
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("Пути:"):
            return _split_zone_paths(line[len("Пути:"):])
    return None


# Префикс сообщения автокоммита артефактов шага РОЛИ (`checkpoint.
# _commit_external_step_artifacts::own_commit_marker`) — общий для любой
# роли и обеих формулировок (обычной/с пометкой таймаута): роль встроена
# сразу после этого префикса, дальше в обоих случаях идёт «(автокоммит
# оркестратора...)». Единственный текстовый признак, которым коммит,
# заведомо НЕ бывший `cmd_answer` (тот коммитит отдельным сообщением
# `f"{task_id}: ANSWER-{n} — ответ Оператора"`, `orchestrator/answer.py`),
# узнаваем по подписи (REVIEW.md 01M1P9QCHPHSCEA6TK13PV85SP итерация 2,
# R2-F1).
_STEP_ARTIFACTS_COMMIT_PREFIX = "{task_id}: артефакты шага "


def _answer_commit_is_role_step_autocommit(branch: str, task_id: str,
                                           path: str) -> bool:
    """`True` — последний коммит `path` на артефактной ветке доказанно НЕ
    `cmd_answer` Оператора, а автокоммит шага роли (checkpoint.py) —
    именно так developer мог бы подложить себе поддельный
    `ANSWER-n.md` с маркером мандата в СВОЁМ ЖЕ шаге `in_dev` (R2-F1):
    `tasks/<id>/` роли — обычная директория на диске, автокоммит шага
    переносит в артефактную ветку любой файл без разбора по типу.

    Git не ответил (сбой команды, недостижимый sha) ИЛИ сообщение не
    совпало ни с одним известным маркером (лёгкая песочница без
    реального коммита — `tests/test_zones_gate.py`, докстринг модуля:
    «там git всегда отвечает» не про этот вызов) — `False`, не
    «доказанный автокоммит роли»: положительный сигнал здесь —
    ЕДИНСТВЕННОЕ основание отклонить мандат, симметрично тому, как
    `checkpoint._commit_external_step_artifacts` использует ТОТ ЖЕ
    признак (положительное совпадение с `own_commit_marker`) как
    единственное основание для удаления, а не наоборот."""
    res = gitcmd.git("log", "-1", "--format=%s", branch, "--", path)
    if res is None or res.returncode != 0:
        return False
    subject = res.stdout.strip()
    return subject.startswith(_STEP_ARTIFACTS_COMMIT_PREFIX.format(task_id=task_id))


def _answer_zones_mandate(branch: str, task_id: str) -> set[str]:
    """Объединение путей ВСЕХ маркеров `_ZONES_MANDATE_MARKER`, найденных в
    ЛЮБОМ `tasks/<id>/ANSWER-n.md` ветки задачи (ANSWER-1.md, п.2) — перебор
    файлов тем же приёмом, что `fsm._answer_file_count`.

    Файл, последний коммит которого — доказанный автокоммит шага роли
    (`_answer_commit_is_role_step_autocommit`), пропускается: это не
    `cmd_answer`, значит не мандат Оператора, независимо от текста
    внутри (R2-F1)."""
    paths = gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []
    mandate: set[str] = set()
    for p in paths:
        name = p.rsplit("/", 1)[-1]
        if not (name.startswith("ANSWER-") and name.endswith(".md")):
            continue
        if _answer_commit_is_role_step_autocommit(branch, task_id, p):
            continue
        text, _reason = gitcmd.show(branch, p)
        if text is None:
            continue
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(_ZONES_MANDATE_MARKER):
                mandate.update(_split_zone_paths(line[len(_ZONES_MANDATE_MARKER):]))
    return mandate


def _zones_gate_refuses(conn, task_id: str, t, branch: str,
                        plan_text: str) -> bool:
    """Сверка диффа ветки задачи с зонами на `in_dev -> review` (SPEC
    01M1P9QCHPHSCEA6TK13PV85SP, AC-1/AC-2/AC-3/AC-6): дополнительное
    предусловие существующего перехода, по образцу `_capacity_gate_refuses`
    выше — не новое состояние FSM (AC-4), отказ ложится в тот же `store.
    journal` под действием `"переход отклонён: ..."`, что и остальные отказы
    этого перехода (AC-5, T078 подхватывает через `store.refusal_history`).

    Внешний (не self) target — гейт не проверяется: тот же довод, что
    `_capacity_gate_refuses` — `git diff` в `config.ROOT` не видит код
    внешнего target.

    Задача без ЗАЯВЛЕННОЙ зоны вовсе (`zones` и `zones_extension` оба
    пусты) — гейт не звонится (AC-7): `zones` обязателен только для SPEC
    `schema_version >= 4` (`guard.requires_zones`); задача старой версии
    (или тестовая фикстура, заведённая мимо гейта SPEC) ничего не
    заявляла — сравнивать дифф не с чем, и буквальное прочтение AC-1
    («вне заявленных путей») отказало бы ей на КАЖДОМ файле вне
    COMMON_ZONES, регрессия для всего, что не участвует в этой механике."""
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return False
    declared = _split_zone_paths(t["zones"]) + _split_zone_paths(t["zones_extension"])
    if not declared:
        return False
    # База сравнения — merge-base с origin/main или локальным main (tasks/
    # 01M1SG9T962WJJ31S282GWM0EN, AC-1/AC-2), не голый `config.MAIN_BRANCH`:
    # иначе коммит main, ещё не влитый в ветку задачи, выглядит правкой
    # самой задачи и ложно отказывает переход как «вне зон».
    base = gitcmd.diff_base(t["branch"])
    if base is None:
        detail = (f"гейт зон: git не ответил на определение базы сравнения "
                 f"(merge-base с origin/{config.MAIN_BRANCH} либо "
                 f"локальным {config.MAIN_BRANCH}) для ветки {t['branch']} "
                 f"— сверка с зонами невозможна")
        store.journal(conn, task_id, "fsm", "переход отклонён: гейт зон",
                      detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        print(f"  дальше: разберись, почему git не отвечает на merge-base "
              f"для {t['branch']}, и повтори artel.py advance {task_id}")
        return True
    files = gitcmd.diff_names(base, t["branch"])
    if files is None:
        detail = (f"гейт зон: git не ответил на список файлов диффа "
                 f"(база {base}...{t['branch']}) — сверка с зонами "
                 f"невозможна")
        store.journal(conn, task_id, "fsm", "переход отклонён: гейт зон",
                      detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        print(f"  дальше: разберись, почему git не отвечает на diff "
              f"{base}...{t['branch']}, и повтори "
              f"artel.py advance {task_id}")
        return True

    zones = declared + list(config.COMMON_ZONES)
    out_of_zone = [f for f in files if not _touches_zone(f, zones)]
    if not out_of_zone:
        return False

    # Исключение AC-3: раздел «## Расширение зон» PLAN.md, подкреплённый
    # мандатом Оператора на ТЕ ЖЕ пути в ANSWER-*.md (ANSWER-1.md, п.1-2).
    extension_paths = _plan_zones_extension_paths(plan_text)
    if extension_paths is not None:
        mandate = _answer_zones_mandate(branch, task_id)
        uncovered_by_mandate = [p for p in extension_paths if p not in mandate]
        if not uncovered_by_mandate:
            still_out = [f for f in out_of_zone
                        if not _touches_zone(f, zones + extension_paths)]
            if not still_out:
                merged = sorted(set(_split_zone_paths(t["zones_extension"])
                                    + extension_paths))
                store.update_task(conn, task_id,
                                  zones_extension=",".join(merged))
                return False
            out_of_zone = still_out

    # Источник базы в сообщении (требование 4/AC-6) — Оператор видит, с чем
    # реально сравнивали, не только литерал diff-диапазона.
    source = gitcmd.diff_base_source(t["branch"])
    detail = (f"дифф трогает файлы вне заявленных zones и COMMON_ZONES "
             f"(база сравнения {base} от {source}): "
             f"{', '.join(out_of_zone)}")
    store.journal(conn, task_id, "fsm", "переход отклонён: гейт зон", detail)
    print(f"[{task_id}] переход отклонён: {detail}")
    print(f"  дальше: сократи дифф до заявленных zones либо оформи раздел "
          f"«## Расширение зон» в PLAN.md с обоснованием и мандатом "
          f"Оператора («{_ZONES_MANDATE_MARKER} <пути>» в ANSWER-n.md), и "
          f"повтори artel.py advance {task_id}")
    return True


# Именованная причина отказа (требование 4) — общий текст с
# `orchestrator/auto.py::REWORK_REFUSAL_ACTION` (второй, независимый
# рубеж того же класса регрессии).
_REWORK_REFUSAL_ACTION = "переход отклонён: замечания ревью не отработаны"

# Префикс сообщения автослияния «подтяжка main» на КОДОВОЙ ветке задачи
# (`fsm._pull_main_or_escalate`/`fsm._auto_resolve_map_conflict`:
# `f"{task_id}: подтяжка {source_branch}"`) — единственный вид коммита на
# кодовой ветке, не являющийся работой developer'а (SPEC «Контекст»:
# именно подтяжка была ЕДИНСТВЕННЫМ, что двигало кодовую ветку между
# итерациями в реальном инциденте регрессии №12/№13) — гейт ниже обязан
# его игнорировать, иначе рутинная подтяжка main маскировала бы
# неотработанные замечания под настоящий шаг developer.
_PULL_MAIN_COMMIT_INFIX = ": подтяжка "


def _commit_iso_date(ref: str, *path: str):
    """Дата последнего коммита `ref` (committer, `%cI`), затрагивающего
    `path` (без него — голова `ref`) — `datetime` с часовым поясом; `None`
    — git не ответил, коммитов нет, либо строка не разбирается как ISO8601
    (лёгкие песочницы без настоящего git — `fake_git`/заглушки, тот же
    вырожденный случай деградации, что и у `fsm._pull_main_or_escalate`)."""
    args = ["log", "-1", "--format=%cI", ref]
    if path:
        args += ["--", *path]
    res = gitcmd.git(*args)
    if res is None or res.returncode != 0:
        return None
    line = res.stdout.strip()
    if not line:
        return None
    try:
        return datetime.fromisoformat(line)
    except ValueError:
        return None


def _latest_developer_commit_iso_date(branch: str, task_id: str):
    """Дата последнего коммита КОДОВОЙ ветки `branch`, который НЕ является
    автослиянием «подтяжка main» (`_PULL_MAIN_COMMIT_INFIX`) — иначе гейт
    принял бы рутинную подтяжку main за настоящий шаг developer (см.
    докстринг `_PULL_MAIN_COMMIT_INFIX`). `None` — git не ответил, либо на
    ветке нет ни одного коммита, кроме подтяжек."""
    res = gitcmd.git("log", "--format=%cI\x1f%s", branch)
    if res is None or res.returncode != 0:
        return None
    prefix = f"{task_id}{_PULL_MAIN_COMMIT_INFIX}"
    for line in res.stdout.splitlines():
        ts, sep, subject = line.partition("\x1f")
        if not sep or subject.startswith(prefix):
            continue
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            continue
    return None


def _review_rework_gate_refuses(conn, task_id: str, t, branch: str) -> bool:
    """Гейт `in_dev -> review` (SPEC «регрессия №13» 01M1RHFRQ2C0P4A57XJJ1WZV8N,
    требование 3, AC-3/AC-4/AC-6/AC-7): REVIEW.md текущей итерации ещё
    `changes_requested`, а кодовая ветка не получила ни одного коммита
    developer'а ПОСЛЕ его коммита — переделка не отработана. Независимый
    от `auto.py` рубеж (по образцу `_capacity_gate_refuses` выше): держит
    и ручной `advance` Оператора, который журнальный гейт `auto.py` не
    видит вовсе.

    Сверка по ВРЕМЕНИ коммитов (`%cI`), не по sha и не по тексту:
    REVIEW.md живёт в АРТЕФАКТНОЙ ветке пульта, код — в ОТДЕЛЬНОЙ кодовой
    ветке (`artifact_source.resolve`, `foreign` всегда `True`), общего
    родителя у них нет — единственный осмысленный признак «после» здесь
    время, не sha.

    Внешний (не self) target — гейт не проверяется: тот же довод, что
    `_capacity_gate_refuses`/`_zones_gate_refuses` выше — `git log`/`show`
    в `config.ROOT` не видит код внешнего target.

    Git не ответил, дата не разобрана, или REVIEW.md вовсе не существует
    (легковесные песочницы без настоящего git — `fake_git`/`disk_backed_
    show`, первый вход задачи в `in_dev` до первого ревью) — гейт НЕ
    отказывает: тот же вырожденный случай деградации, что у
    `fsm._pull_main_or_escalate` (`git не ответил -> "fresh"`) —
    не найденный сигнал не значит «код не менялся», значит «сверить
    нечем».
    """
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return False
    review_text, _ = gitcmd.show(branch, f"tasks/{task_id}/REVIEW.md")
    if review_text is None:
        return False
    meta = yamlmini.frontmatter(review_text) or {}
    if meta.get("status") != "changes_requested":
        return False
    review_ts = _commit_iso_date(branch, f"tasks/{task_id}/REVIEW.md")
    if review_ts is None:
        return False
    code_ts = _latest_developer_commit_iso_date(t["branch"], task_id)
    if code_ts is None:
        return False
    if code_ts > review_ts:
        return False
    detail = (f"замечания ревью не отработаны: нет шага developer после "
              f"итерации {meta.get('iteration', '—')}")
    store.journal(conn, task_id, "fsm", _REWORK_REFUSAL_ACTION, detail)
    print(f"[{task_id}] переход отклонён: {detail}")
    print(f"  дальше: почини код (не спорь с ревью втихую) и повтори "
          f"artel.py advance {task_id}")
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
        plan_text = (tdir / "PLAN.md").read_text(encoding="utf-8")
        plan_meta = yamlmini.frontmatter(plan_text) or {}
    status = plan_meta.get("status")
    if status in ("ready", "approved", "escalate"):
        if fsm._dirty_refuses(conn, task_id, target, "PLAN.md"):
            return False
        if fsm.guard_refuses(conn, task_id, tdir / "PLAN.md", text=plan_text):
            return True
        if status == "escalate":
            # PLAN.md status: escalate (01M1R8B3ZKXQT0Z0G6QQQDV906,
            # требование 6) — тот же канал, что уже несёт REVIEW.md
            # (`review()` выше, ветка `elif status == "escalate":`), для
            # PLAN.md добавленный этой задачей: `in_dev` до сих пор понимал
            # только `ready`/`approved`, любой другой статус (в т.ч.
            # escalate) падал в «PLAN.md не ready — разработчик ещё
            # работает», и `auto` продолжал звать `developer` заново
            # вместо остановки на эскалации (регрессия №11, симптом 2).
            answer_baseline = fsm._answer_baseline_or_refuse(conn, task_id, tdir)
            if answer_baseline is None:
                return False
            store.update_task(conn, task_id, answer_baseline=answer_baseline)
            escalation = guard.section_body(
                plan_text, guard.ESCALATION_SECTION).strip()
            detail = (f"эскалация от разработчика: {escalation}" if escalation
                      else "эскалация от разработчика")
            store.set_state(conn, task_id, "escalated", "fsm",
                            expected_state=state, detail=detail)
            print(f"[{task_id}] эскалация разработчика: {detail}")
            return False
        locked = t["tests_locked_sha"]
        if locked:
            # `locked` (`tests_locked_sha`) — sha АРТЕФАКТНОЙ ВЕТКИ пульта
            # (`config.ROOT`, настоящий git) на момент лока, когда
            # `foreign` (`tests_writing`, A7 требование 2 — единая логика
            # для ЛЮБОГО target, включая артель, теперь всегда True) —
            # сверяется ТАМ ЖЕ, в `config.ROOT`, против текущей головы
            # ТОЙ ЖЕ ветки (`branch`), не «HEAD» рабочего дерева (чужой
            # чекаут не должен сверять лок с чужой веткой вместо своей).
            # Не-foreign (сегодня недостижимо после генерализации self —
            # песочница без git) — прежнее поведение: `locked` из
            # `fixed_sha`, сверка по "HEAD" рабочего дерева main.
            lock_ref = branch if foreign else "HEAD"
            names = gitcmd.diff_names(
                locked, lock_ref, f"tasks/{task_id}/acceptance_tests")
            if names is None:
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
            if names:
                # Разница только по файлам, игнорируемым `.gitignore`
                # пульта (SPEC 01M1KVG3KSCY47HWXWF5HM0E76, требование 3,
                # AC-4) — не спор с локом, тот же критерий, что у
                # `checkpoint._commit_external_step_artifacts`.
                ignored = gitcmd.check_ignore(names)
                if ignored is None:
                    detail = (f"лок acceptance_tests/ не проверен: git не "
                              f"ответил на проверку .gitignore — сверка "
                              f"невозможна")
                    store.journal(conn, task_id, "fsm",
                                  "переход отклонён: лок приёмочных тестов",
                                  detail)
                    print(f"[{task_id}] переход отклонён: {detail}")
                    print(f"  дальше: разберись, почему git не отвечает на "
                          f"check-ignore, и повтори artel.py advance "
                          f"{task_id}")
                    return False
                names = [n for n in names if n not in ignored]
            if names:
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
        if fsm._pull_main_or_escalate(conn, task_id, t, state) in (
                "escalated", "refused"):
            return False
        if _capacity_gate_refuses(conn, task_id, t, state):
            return False
        if _zones_gate_refuses(conn, task_id, t, branch, plan_text):
            return False
        if _review_rework_gate_refuses(conn, task_id, t, branch):
            return False
        store.set_state(conn, task_id, "review", "fsm",
                        expected_state=state, detail="MR готов — прогон ревьювера")
    else:
        print(f"[{task_id}] PLAN.md не ready — разработчик ещё работает")
    return False
