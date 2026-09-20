"""Обработчики `cmd_advance` — один на состояние (SPEC T091, декомпозиция
диспетчеров fsm/runner): каждая функция — прежнее тело своей ветки
if/elif `orchestrator/fsm.py::_cmd_advance`, перенесённое без изменения
поведения. Диспетчер (выбор обработчика по `t["state"]`) остаётся в
`fsm.py` — эти функции не вызываются напрямую иначе, кроме тестов,
идущих через публичный `fsm.cmd_advance`.

Семейства гейтов (SPEC 01M2CYQR0357VAQFZ5VACJD9TD) физически живут в
пакете `orchestrator/advance_gates/` — здесь остаются только обработчики
состояний, эффекты вердиктов (`_review_approved`,
`_review_changes_requested`, `_review_escalate`, `_in_dev_plan_escalate`,
`_apply_plan_budget`) и реэкспорт каждого перенесённого имени (алиас,
`is`-идентичный объект подмодуля `advance_gates`) — внешний код
(`orchestrator/answer.py`, тесты) продолжает обращаться к ним как к
`fsm_advance.<имя>`, не подозревая о переносе.
"""
from scripts import guard

from . import (acceptance, artifact_source, artifacts, budget, ci, config,
              fsm, fsm_autogate, gitcmd, store, workspace, yamlmini)
from .advance_gates._base import GateRefusal, _run_gates
from .advance_gates.acceptance import _acceptance_lock_refuses, _acceptance_run_refuses
from .advance_gates.capacity import (CAPACITY_GATE_REASON, _EMPTY_DIFF_TEXT,
                                     _capacity_gate, _capacity_gate_refuses)
from .advance_gates.plan_appendix import (
    PLAN_APPENDIX_GATE_FAILURE_ACTION,
    PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION, _plan_appendix_gate,
    _plan_appendix_gate_refuses)
from .advance_gates.review import (_code_sha_at_review_escalation,
                                   _mutation_claim_gate,
                                   _review_escalation_sha_gate,
                                   _review_rework_gate,
                                   _review_rework_gate_refuses,
                                   _reviewer_verdict_baseline)
from .advance_gates.tests_writing import (_freshness_refuses,
                                          _origin_push_gate, _registry_gate,
                                          _tests_writing_acceptance_dir,
                                          _tests_writing_dry_collect_gate,
                                          _tests_writing_stray_plank_files_gate)
from .advance_gates.zones import (_ZONES_MANDATE_MARKER,
                                  _answer_commit_is_role_step_autocommit,
                                  _answer_zones_mandate,
                                  _plan_zones_extension_paths,
                                  _protected_path_refusal_detail,
                                  _protected_paths_touched, _split_zone_paths,
                                  _touches_zone, _untracked_worktree_paths,
                                  _zones_gate, _zones_gate_refuses)


def _mark_artifact_escalation(conn, task_id: str, detail: str) -> None:
    """Маркер «ответ Оператора должен дойти до роли» (SPEC
    01M2XFSJ1Z7BS6HR69SAT1D81Y, требования 1-2) — отдельной записью
    журнала СРАЗУ после `state -> escalated` эскалации по содержимому
    артефакта роли, до возврата Оператора: `auto._role_step_since_state_entry`
    делает запись возврата, следующую за маркером, анкером рубежа
    переделки, и пред-advance не перечитывает ту же пометку/тот же батч
    раньше шага роли. `detail` — текст самой эскалации, как у
    `pull.PULL_CONFLICT_ROLE_STEP_MARKER` (`orchestrator/pull.py`)."""
    store.journal(conn, task_id, "fsm",
                  fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER, detail)


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
            detail = f"analyst: батч вопросов по ТЗ — ветка {branch}:{q_rel}"
            store.set_state(
                conn, task_id, "escalated", "fsm",
                expected_state=state, detail=detail)
            _mark_artifact_escalation(conn, task_id, detail)
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
            detail = f"analyst: батч вопросов по ТЗ — {questions}"
            store.set_state(
                conn, task_id, "escalated", "fsm", expected_state=state,
                detail=detail)
            _mark_artifact_escalation(conn, task_id, detail)
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


def _review_approved(conn, task_id: str, t, tdir, target: str, state: str,
                     branch: str, review_text, meta) -> bool:
    if guard.requires_registry(meta):
        if _run_gates(conn, task_id,
                      [lambda: _registry_gate(conn, task_id, tdir, review_text, meta)]):
            return False
    # Прогон приёмки и сверка головы на origin переехали на переход
    # `in_dev -> verifying` (ADR-0015, требование 2; `fsm_advance.in_dev`
    # выше) — approved с зелёным CI ведёт прямиком в acceptance, второй
    # раз ничего из этого не проверяется.
    store.set_state(conn, task_id, "acceptance", "fsm", expected_state=state,
                    detail="ревью пройдено — вход в приёмку")
    # Автогейт acceptance (ADR-0007, SPEC T066) — тем же приёмом, что
    # раньше стоял на входе `verifying -> acceptance` (`verifying()`
    # ниже, до ADR-0015): каталог планки резолвится тем же способом,
    # что и прогон приёмки в `in_dev` выше (worktree self-target либо
    # workspace внешнего, SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS).
    acc_tdir = tdir
    if target != config.DEFAULT_TARGET:
        code_dir = config.PROJECTS / target / "workspace"
        code_dir.mkdir(parents=True, exist_ok=True)
        acc_tdir = acceptance.materialize_from_branch(task_id, branch, code_dir)
    elif workspace.on_task_branch(task_id, t["branch"]) is True:
        acc_tdir = workspace.path(task_id) / "tasks" / task_id
    fsm_autogate._maybe_autogate_acceptance(conn, task_id, t, acc_tdir,
                                           t["reviewed_iter"])
    return False


def _review_changes_requested(conn, task_id: str, t, state: str) -> bool:
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
    return False


def _review_escalate(conn, task_id: str, t, tdir, state: str) -> bool:
    answer_baseline = fsm._answer_baseline_or_refuse(conn, task_id, tdir)
    if answer_baseline is None:
        return False
    store.update_task(conn, task_id, answer_baseline=answer_baseline)
    store.set_state(conn, task_id, "escalated", "fsm",
                    expected_state=state, detail="эскалация от ревьювера")
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
    if _freshness_refuses(conn, task_id, t, meta, status):
        return False

    if status == "approved":
        if _run_gates(conn, task_id,
                      [lambda: _review_escalation_sha_gate(conn, task_id, t)]):
            return False

    iteration = artifacts.fresh_verdict_iteration(meta, t["reviewed_iter"])
    store.update_task(conn, task_id, reviewed_iter=iteration)

    if status == "approved":
        return _review_approved(conn, task_id, t, tdir, target, state,
                                branch, review_text, meta)
    if status == "changes_requested":
        return _review_changes_requested(conn, task_id, t, state)
    return _review_escalate(conn, task_id, t, tdir, state)


def verifying(conn, task_id: str, t, tdir, target: str, state: str) -> bool:
    # Ожидание зелёного CI головного коммита ветки задачи (SPEC T079,
    # требования 5-7 + SPEC T086, требования 2-4; ADR-0015, требования
    # 1-2 — переход теперь ведёт в `review`, не в `acceptance`: CI
    # подтянутой головы проверяется ДО ревьювера, не после). Четыре
    # исхода различает `ci.verifying_status` (роадмап P3, T040): зелёный,
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
        store.set_state(conn, task_id, "review", "fsm",
                        expected_state=state, detail=note)
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
        escalation_detail = (f"test_author: критерий неисполним тестом — "
                             f"{detail}")
        store.set_state(conn, task_id, "escalated", "fsm",
                        expected_state=state, detail=escalation_detail)
        _mark_artifact_escalation(conn, task_id, escalation_detail)
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
    if _run_gates(conn, task_id,
                  [lambda: _tests_writing_stray_plank_files_gate(conn, task_id)]):
        return False
    acc_tdir, run_cwd = _tests_writing_acceptance_dir(
        task_id, tdir, target, branch, t["branch"])
    if _run_gates(conn, task_id,
                  [lambda: _tests_writing_dry_collect_gate(
                      acc_tdir, run_cwd, task_id)]):
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


def _in_dev_plan_escalate(conn, task_id: str, tdir, plan_text: str,
                          state: str) -> bool:
    """PLAN.md status: escalate (01M1R8B3ZKXQT0Z0G6QQQDV906, требование 6) —
    тот же канал, что несёт REVIEW.md (`_review_escalate`); до этой задачи
    `in_dev` понимал только `ready`/`approved`, любой другой статус (в т.ч.
    escalate) падал в «PLAN.md не ready — разработчик ещё работает», и
    `auto` продолжал звать `developer` заново вместо остановки на
    эскалации (регрессия №11, симптом 2)."""
    answer_baseline = fsm._answer_baseline_or_refuse(conn, task_id, tdir)
    if answer_baseline is None:
        return False
    store.update_task(conn, task_id, answer_baseline=answer_baseline)
    escalation = guard.section_body(plan_text, guard.ESCALATION_SECTION).strip()
    detail = (f"эскалация от разработчика: {escalation}" if escalation
              else "эскалация от разработчика")
    store.set_state(conn, task_id, "escalated", "fsm",
                    expected_state=state, detail=detail)
    print(f"[{task_id}] эскалация разработчика: {detail}")
    return False


def _apply_plan_budget(conn, task_id: str, t, meta: dict) -> None:
    """Однократная переоценка потолка задачи по PLAN.md (ADR-0014 п.3,
    требования 1-5) — один шанс за всю жизнь задачи, не за итерацию.

    `review_iters`/`accept_rejects` оба ещё нулевые — только тогда PLAN.md,
    дошедший сюда, гарантированно первая сдача со `status: ready`: возврат
    в `in_dev` из ревью (`changes_requested`) растит `review_iters`
    (`_review_changes_requested` выше), возврат из приёмки (`reject`) —
    `accept_rejects` (`fsm._cmd_reject`) — оба возврата закрывают канал
    навсегда (требование 4), ни один из счётчиков переходами не сбрасывается
    (инвариант 4, docs/invariants.md).

    Вызывается прямо перед переходом в `verifying`, тем же местом в
    последовательности, каким `budget.apply_spec_budget` стоит перед
    `spec_gate` (`spec_writing` выше) — потолок обязан устояться до того,
    как задача продолжит тратить деньги на этом шаге.

    Разбор значения и потолок ролей — тот же `budget.spec_budget`, что и у
    SPEC (поле то же самое, правило то же самое, ADR-0014 требование 6):
    значение выше `ROLE_BUDGET_CAP` сюда в норме не доходит вовсе — раньше
    отказывает guard (требование 6, эта функция для такого случая
    отдельной обработки не добавляет; парсер отказывает и здесь — вторая,
    независимая линия защиты, тем же приёмом, что и `apply_spec_budget`).
    """
    if t["review_iters"] or t["accept_rejects"]:
        return
    old = t["budget_usd"] or 0.0
    value, refused = budget.spec_budget(meta)

    if refused:
        detail = f"{refused}, остаётся потолок ${old:.2f}"
        store.journal(conn, task_id, "fsm", "бюджет из PLAN отклонён", detail)
        print(f"[{task_id}] ВНИМАНИЕ: бюджет из PLAN отклонён: {detail}")
        return
    if value is None:
        return  # требование 2: поля нет — потолок не меняется, молча

    if t["budget_source"] == config.BUDGET_SOURCE_OPERATOR:
        detail = f"${value:.2f} — потолок задан Оператором, остаётся ${old:.2f}"
        store.journal(conn, task_id, "fsm", "бюджет из PLAN не применён", detail)
        print(f"[{task_id}] бюджет из PLAN не применён: {detail}")
        return
    if value <= old:
        detail = f"не применён: ниже потолка (${value:.2f} <= ${old:.2f})"
        store.journal(conn, task_id, "fsm", "бюджет из PLAN не применён", detail)
        print(f"[{task_id}] бюджет из PLAN не применён: {detail}")
        return

    store.update_task(conn, task_id, budget_usd=value,
                      budget_source=config.BUDGET_SOURCE_PLAN,
                      updated_at=store.now())
    detail = (f"${value:.2f} (прежний потолок ${old:.2f}, "
             f"источник {config.BUDGET_SOURCE_PLAN})")
    store.journal(conn, task_id, "fsm", "бюджет из PLAN", detail)
    print(f"[{task_id}] бюджет из PLAN: {detail}")


def in_dev(conn, task_id: str, t, tdir, target: str, state: str) -> bool:
    # Разработчик закончил: PLAN ready и ветка запушена -> в verifying
    # (ADR-0015, требования 1-2: CI подтянутой головы проверяется ДО
    # ревьювера, не после — все семь рубежей этого перехода стоят здесь
    # целиком, ревью их повторно не звонит). PLAN.md читается С ВЕТКИ
    # задачи (SPEC T031/T094 требование 10), тем же приёмом
    # `_read_branch_text_or_refuse` (T047), что и SPEC.md/REVIEW.md.
    branch, foreign = artifact_source.resolve(conn, task_id)
    if foreign:
        plan_text = fsm._read_branch_text_or_refuse(conn, task_id, branch,
                                                     "PLAN.md")
        if plan_text is None:
            return False
    else:
        plan_text = (tdir / "PLAN.md").read_text(encoding="utf-8")
    plan_meta = yamlmini.frontmatter(plan_text) or {}
    status = plan_meta.get("status")
    if status not in ("ready", "approved", "escalate"):
        print(f"[{task_id}] PLAN.md не ready — разработчик ещё работает")
        return False
    if fsm._dirty_refuses(conn, task_id, target, "PLAN.md"):
        return False
    if fsm.guard_refuses(conn, task_id, tdir / "PLAN.md", text=plan_text):
        return True
    if status == "escalate":
        return _in_dev_plan_escalate(conn, task_id, tdir, plan_text, state)
    if _acceptance_lock_refuses(conn, task_id, t, branch, foreign):
        return False
    # Сверка свежести ветки до гейта (SPEC T051, требования 1, 4).
    if fsm._pull_main_or_escalate(conn, task_id, t, state) in (
            "escalated", "refused"):
        return False
    # Порядок и обёртки — прежние, зафиксированные R2 (01M1TKNXX5YN5KT4WHG4T
    # 44JWV, AC-5/AC-6): каждый гейт вызывается через свою «сохранённую
    # публичную обёртку» (`_xxx_gate_refuses`) отдельным вызовом, не одним
    # списком через `_run_gates` — обёртки остаются наблюдаемой единицей
    # снаружи (тесты `tests/test_zones_gate.py`/`test_capacity_gate.py`/
    # `test_fsm_review_rework_gate.py` зовут их напрямую), а поведение
    # (журнал/печать/остановка на первом отказе) не меняется — каждая
    # обёртка сама оборачивает свой единственный гейт `_run_gates`.
    if _capacity_gate_refuses(conn, task_id, t, state):
        return False
    if _zones_gate_refuses(conn, task_id, t, branch, plan_text):
        return False
    # Применимость приложений PLAN к защищённым путям (SPEC
    # 01M2YSHDKWFJN3XSJ618Z74FNF, требование 2) — сразу за гейтом зон: тот
    # отказывает правке защищённого пути В ДИФФЕ и адресует роль к
    # приложению, этот проверяет само приложение. PLAN без приложений
    # гейт не трогает (AC-7).
    if _plan_appendix_gate_refuses(conn, task_id, t, plan_text):
        return False
    if _run_gates(conn, task_id,
                  [lambda: _mutation_claim_gate(conn, task_id, t, branch)]):
        return False
    if _review_rework_gate_refuses(conn, task_id, t, branch):
        return False
    # Сверка головы на origin (ADR-0015, требование 2) — не для канареечной
    # задачи (SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 11/AC-11): её
    # `verifying` не ждёт CI и не читает origin (`canary._kill_at_verifying`
    # убивает задачу сразу по входу) — push на origin-заглушку
    # (`canary.ORIGIN_STUB_URL`) гарантированно проваливается по
    # построению, не по сбою, тем же исключением, что раньше стояло на
    # входе `review()`.
    if not t["is_canary"]:
        if _run_gates(conn, task_id, [lambda: _origin_push_gate(conn, task_id, t)]):
            return False
    if _acceptance_run_refuses(conn, task_id, t, tdir, target, branch):
        return False
    # До смены состояния — тем же приёмом, что `apply_spec_budget` перед
    # `spec_gate` выше: потолок обязан устояться до того, как задача
    # продолжит тратить деньги (ADR-0014 п.3).
    _apply_plan_budget(conn, task_id, t, plan_meta)
    store.update_task(conn, task_id, verifying_attempts=0)
    store.set_state(conn, task_id, "verifying", "fsm",
                    expected_state=state, detail="MR готов — жду зелёного CI ветки")
    return False
