"""Переходы автомата: advance по артефактам, approve/reject Оператора."""
import subprocess
import sys
from pathlib import Path

from scripts import guard

from . import (acceptance, artifacts, budget, ci, config, fixation, gitcmd,
              store, yamlmini)


def guard_refuses(conn, task_id: str, path: Path, text: str | None = None) -> bool:
    """Прогон guard по артефакту-условию перехода; True — переход отменён.

    Структуру артефакта проверяет код на самом переходе, а не роль по
    договорённости и не CI задним числом (SPEC T017, требование 5): задачу
    двигают статусы артефактов, значит артефакт со сломанной структурой
    двигать её не должен. Отказ — журнал, названный файл и все причины
    списком: разбирать его будет Оператор, и трейсбека ему тут не надо.

    `text` — уже прочитанное содержимое (с ВЕТКИ задачи при чужом чекауте
    рабочей копии, SPEC T031) вместо чтения `path` с диска; `None` (по
    умолчанию) — прежнее поведение, `guard.check(path)`.
    """
    errors = guard.check(path) if text is None else guard.check_content(str(path), text)
    if not errors:
        return False
    store.journal(conn, task_id, "fsm", "переход отклонён guard'ом",
                  "; ".join(errors))
    print(f"[{task_id}] переход отклонён: {path.name} не проходит guard")
    for error in errors:
        print(f"  - {error}")
    print(f"  дальше: почини артефакт и повтори artel.py advance {task_id}")
    return True


def _dirty_refuses(conn, task_id: str, target: str, artifact_name: str) -> bool:
    """Отказ по грязной копии артефакта-условия перехода; True — переход
    отменён (SPEC T033, требование 1 — симметрия с `approve`).

    Та же сверка, что и `confirm_fixation` у `approve`: `fixation.read()`,
    не `fix()` — проверка не имеет права коммитить чужой WIP как побочный
    эффект сравнения (REVIEW.md T021, замечание 1 итерации 2). `current`
    пустой (git не ответил, коммитов ещё нет) — сверять не с чем, тот же
    вырожденный случай, на котором `confirm_fixation` пропускает дальше;
    старые (не-git) песочницы `advance` продолжают работать без изменений.

    Только догфуд (`target == config.DEFAULT_TARGET`, PLAN «Риски»):
    для внешнего target артефактный репозиторий коммитит сам оркестратор
    целиком уже ПОСЛЕ решения перейти (`fixation._fix_external`, вызов
    из `store.set_state`) — до перехода он закономерно не закоммичен,
    это не забытый коммит роли (та ADR-0003 §4 workspace вообще не
    коммитит сама), и наивная сверка отказывала бы там всегда.
    """
    if target != config.DEFAULT_TARGET:
        return False
    current, clean = fixation.read(task_id, target)
    if not current or clean:
        return False
    detail = (f"{artifact_name} не закоммичен — роль обязана коммитить "
              f"артефакты (скил conventions-core); закоммить и повтори advance")
    store.journal(conn, task_id, "fsm",
                  "переход отклонён: рабочая копия артефактов грязная", detail)
    print(f"[{task_id}] переход отклонён: {detail}")
    return True


def _tests_writing_ac_state(conn, task_id: str, branch: str,
                            tdir: Path) -> tuple[set, dict, list[str]] | None:
    """(тестировано, пометки, ошибки трассируемости) на выходе из
    `tests_writing`; `None` — переход отклонён (уже журналирован).

    Рабочее дерево точно на чужой ветке (`gitcmd.on_foreign_branch`, SPEC
    T031, AC-3) — SPEC.md и acceptance_tests/ читаются с ВЕТКИ задачи
    (`git show`/`git ls-tree`), не с рабочей копии; иначе — прежний путь
    через диск (`guard.scan_acceptance_tests`/`acceptance_traceability_errors`),
    не тронутый T031: оба пути считают одним и тем же ядром
    (`guard.scan_ac_content`/`traceability_errors_from_content`), так что
    результат не расходится по источнику файлов, только по тому, где их
    искать.
    """
    if not gitcmd.on_foreign_branch(branch):
        tested, markers = guard.scan_acceptance_tests(tdir)
        errors = guard.acceptance_traceability_errors(tdir)
        return tested, markers, errors

    spec_rel = f"tasks/{task_id}/SPEC.md"
    tests_rel = f"tasks/{task_id}/acceptance_tests"
    spec_text, spec_reason = gitcmd.show(branch, spec_rel)
    paths = gitcmd.ls_tree_files(branch, tests_rel)
    if spec_text is None or paths is None:
        reason = spec_reason if spec_text is None else "acceptance_tests/ ветки не прочитан"
        detail = (f"дерево не на ветке задачи {branch} — {reason}, "
                  f"трассируемость AC не проверена")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: дерево не на ветке задачи", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        return None

    sources: list[str] = []
    for p in paths:
        if not p.endswith(".py"):
            continue
        text, _ = gitcmd.show(branch, p)
        if text is not None:
            sources.append(text)
    meta = yamlmini.frontmatter(spec_text) or {}
    tested, markers = guard.scan_ac_content(sources)
    errors = guard.traceability_errors_from_content(spec_text, meta, tested,
                                                     markers)
    return tested, markers, errors


def cmd_advance(task_id: str) -> None:
    """Единственная точка движения FSM: читает статусы артефактов."""
    conn = store.db()
    t = store.get_task(conn, task_id)
    state = t["state"]
    tdir = config.TASKS / task_id
    target = store.task_target(conn, task_id)

    if state == "spec_writing":
        # Батч вопросов analyst (SPEC T025, требование 4): файл на месте —
        # эскалация немедленно, не дожидаясь статуса SPEC.md, тем же
        # приёмом, что маркер `escalate` в tests_writing (T023). Второй
        # батч по тому же ТЗ структурно недостижим раньше ответа: пока
        # задача в escalated, run для неё не стартует.
        questions = tdir / "QUESTIONS.md"
        if questions.exists():
            if guard_refuses(conn, task_id, questions):
                return
            store.update_task(conn, task_id, escalated_from="spec_writing")
            store.set_state(conn, task_id, "escalated", "fsm",
                            f"analyst: батч вопросов по ТЗ — {questions}")
            print(f"[{task_id}] эскалация analyst: см. {questions}")
            return
        meta = artifacts.frontmatter(tdir / "SPEC.md")
        if meta.get("status") == "ready":
            if _dirty_refuses(conn, task_id, target, "SPEC.md"):
                return
            if guard_refuses(conn, task_id, tdir / "SPEC.md"):
                return
            # До смены состояния: потолок задачи должен стоять уже к тому
            # моменту, когда Оператор смотрит на неё на гейте SPEC.
            budget.apply_spec_budget(conn, t, meta)
            store.set_state(conn, task_id, "spec_gate", "fsm",
                            "SPEC готов — ждёт approve")
        else:
            print(f"[{task_id}] SPEC.md ещё не ready — нечего продвигать")

    elif state == "review":
        meta = artifacts.frontmatter(tdir / "REVIEW.md")
        status = meta.get("status")
        if status not in config.REVIEW_VERDICTS:
            print(f"[{task_id}] REVIEW.md status={status} — жду вердикта")
            return
        if _dirty_refuses(conn, task_id, target, "REVIEW.md"):
            return
        if guard_refuses(conn, task_id, tdir / "REVIEW.md"):
            return

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
            return
        store.update_task(conn, task_id, reviewed_iter=iteration)

        if status == "approved":
            # Прогон приёмки (SPEC T023, требование 6): красный
            # acceptance-тест чинит код разработчик, не переписывает тест
            # (тесты залочены — см. ветку in_dev выше).
            green, tail = acceptance.run(tdir)
            if not green:
                detail = f"acceptance_tests красные:\n{tail}"
                store.journal(conn, task_id, "fsm",
                              "переход отклонён: приёмочные тесты", detail)
                print(f"[{task_id}] переход отклонён: приёмочные тесты "
                      f"красные")
                print(tail)
                print(f"  дальше: почини код (не тест) и повтори "
                      f"artel.py advance {task_id}")
                return
            card = acceptance.summary(tdir)
            store.journal(conn, task_id, "fsm", "приёмочные тесты пройдены",
                          card)
            print(f"[{task_id}] {card}")
            store.set_state(conn, task_id, "acceptance", "fsm",
                            "ревью пройдено — приёмка Оператором "
                            "(по критериям SPEC)")
        elif status == "changes_requested":
            iters = t["review_iters"] + 1
            if iters >= config.LIMIT_REVIEW_ITERS:
                store.set_state(conn, task_id, "escalated", "fsm",
                                f"лимит ревью "
                                f"{config.LIMIT_REVIEW_ITERS} исчерпан")
            else:
                store.update_task(conn, task_id, review_iters=iters)
                store.set_state(conn, task_id, "in_dev", "fsm",
                                f"замечания ревью, итерация {iters}")
        elif status == "escalate":
            store.set_state(conn, task_id, "escalated", "fsm",
                            "эскалация от ревьювера")

    elif state == "tests_writing":
        # test_author закончил: каждый AC-n — тест либо пометка
        # manual/skip/escalate (SPEC T023, требование 4).
        result = _tests_writing_ac_state(conn, task_id, t["branch"], tdir)
        if result is None:
            return
        tested, markers, errors = result
        escalations = {n: reason for n, (kind, reason) in markers.items()
                      if kind == "escalate"}
        if escalations:
            detail = "; ".join(f"AC-{n}: {reason}"
                               for n, reason in sorted(escalations.items()))
            store.update_task(conn, task_id, escalated_from="tests_writing")
            store.set_state(conn, task_id, "escalated", "fsm",
                            f"test_author: критерий неисполним тестом — "
                            f"{detail}")
            print(f"[{task_id}] эскалация test_author: {detail}")
            return
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
            return
        store.set_state(conn, task_id, "in_dev", "fsm",
                        "приёмочные тесты готовы — трассируемость AC "
                        "пройдена")
        # Лок (требование 5): значение, которое set_state только что
        # посчитал в fixed_sha (T021), становится планкой acceptance_tests/
        # для in_dev -> review — тот же sha, не новая фиксация.
        store.update_task(conn, task_id,
                          tests_locked_sha=store.get_task(
                              conn, task_id)["fixed_sha"])

    elif state == "in_dev":
        # разработчик закончил: PLAN ready и ветка запушена -> в ревью
        #
        # Рабочее дерево точно на чужой ветке (SPEC T031) — PLAN.md
        # читается с ВЕТКИ задачи (иначе гейт «PLAN.md не ready» молча
        # держит переход и на чужом чекауте нечего проверять дальше —
        # без этого лок ниже никогда не достигается со стороны AC-3);
        # иначе прежний путь через диск, не тронутый T031.
        branch = t["branch"]
        foreign = gitcmd.on_foreign_branch(branch)
        plan_text = None
        if foreign:
            plan_text, plan_reason = gitcmd.show(
                branch, f"tasks/{task_id}/PLAN.md")
            if plan_text is None:
                detail = (f"дерево не на ветке задачи {branch} — PLAN.md "
                          f"ветки не прочитан ({plan_reason})")
                store.journal(conn, task_id, "fsm",
                              "переход отклонён: дерево не на ветке задачи",
                              detail)
                print(f"[{task_id}] переход отклонён: {detail}")
                return
            plan_meta = yamlmini.frontmatter(plan_text) or {}
        else:
            plan_meta = artifacts.frontmatter(tdir / "PLAN.md")
        if plan_meta.get("status") in ("ready", "approved"):
            if _dirty_refuses(conn, task_id, target, "PLAN.md"):
                return
            if guard_refuses(conn, task_id, tdir / "PLAN.md", text=plan_text):
                return
            locked = t["tests_locked_sha"]
            if locked:
                # Ветка задачи, не литерал "HEAD" (SPEC T031, AC-3): чужой
                # чекаут рабочей копии не должен сверять лок с чужой веткой
                # вместо своей. Свой чекаут (обычный путь) или ветка ещё
                # не создана ролью — тот же "HEAD", что и до T031.
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
                    return
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
                    return
            store.set_state(conn, task_id, "review", "fsm",
                            "MR готов — прогон ревьювера")
        else:
            print(f"[{task_id}] PLAN.md не ready — разработчик ещё работает")

    else:
        print(f"[{task_id}] состояние {state} двигается через approve/reject/run")


# Состояния, на входе в approve которых требуется подтверждённый sha
# (SPEC T021, требование 4): именно те 4 ветки, которые ниже что-то
# подтверждают, а не просто отвечают «нечего подтверждать».
APPROVE_NEEDS_SHA = ("spec_gate", "acceptance", "merge_gate", "escalated")


def confirm_fixation(conn, task_id: str, sha: str | None) -> bool:
    """True — approve может продолжить; False — сообщил и ждёт sha (не отказ).

    Живьём пересчитывает состояние через `fixation.read()`, а не читает
    `tasks.fixed_sha`: approve обязан сверяться с ТЕКУЩИМ состоянием
    (ADR-0003 п.15, «сверка на каждом следующем гейте... = сравнение sha +
    чистота рабочей копии»), а не с тем, что было на момент прошлого
    перехода. `read()`, не `fix()` (REVIEW.md T021, замечание 1 итерации
    2): approve — точка ПРОВЕРКИ, не фиксации, и не имеет права коммитить
    незакоммиченный WIP чужой задачи того же target как побочный эффект
    сравнения — легитимный коммит перехода случится позже, в
    `store.set_state` → `fix()`, если сверка сошлась.

    Фиксации нет (`sha == ""` — git не ответил, песочница без
    репозитория) — сверять не с чем: approve ведёт себя как до T021
    (требование 3, критерий 3). Расхождение sha или грязная копия —
    `sys.exit`, тем же стилем, что и отказ merge по красному CI ниже.
    """
    target = store.task_target(conn, task_id)
    current, clean = fixation.read(task_id, target)
    if not current:
        return True
    if sha is None:
        print(f"[{task_id}] approve требует sha — зафиксирован {current}")
        print(f"  повтори: artel.py approve {task_id} {current}")
        return False
    if sha != current or not clean:
        reason = (f"sha {sha} не совпадает с зафиксированным {current}"
                  if sha != current else
                  f"грязная копия артефактов при sha {current}")
        store.journal(conn, task_id, "operator", "approve отклонён", reason)
        sys.exit(f"[{task_id}] approve отклонён: {reason}")
    return True


def cmd_approve(task_id: str, sha: str | None = None) -> None:
    conn = store.db()
    t = store.get_task(conn, task_id)
    state = t["state"]
    if state in APPROVE_NEEDS_SHA and not confirm_fixation(conn, task_id, sha):
        return
    if state == "spec_gate":
        # tests_writing до кода (SPEC T023, требование 1): пропускается
        # только явным skip_tests либо SPEC версии ниже 2 (без AC-разметки,
        # весь беклог T001–T022 — требование 7); иначе тесты пишутся
        # раньше, чем задачу увидит разработчик.
        #
        # Рабочее дерево точно на чужой ветке (SPEC T031, AC-1) — SPEC.md
        # читается с ВЕТКИ задачи (не молчаливый дефолт «schema_version 1
        # без AC-разметки», журнал T030 ~17:35 25.08.2026); иначе прежний
        # путь через диск, не тронутый T031.
        branch = t["branch"]
        if gitcmd.on_foreign_branch(branch):
            spec_text, reason = gitcmd.show(
                branch, f"tasks/{task_id}/SPEC.md")
            if spec_text is None:
                detail = (f"SPEC.md ветки {branch} не прочитан ({reason}) "
                          f"— дерево не на ветке задачи")
                store.journal(conn, task_id, "fsm",
                              "approve отклонён: дерево не на ветке задачи",
                              detail)
                sys.exit(f"[{task_id}] approve отклонён: {detail}")
            meta = yamlmini.frontmatter(spec_text) or {}
        else:
            meta = artifacts.frontmatter(config.TASKS / task_id / "SPEC.md")
        skip_reason = meta.get("skip_tests")
        if skip_reason or not guard.requires_ac_markup(meta):
            detail = (f"тесты пропущены (skip_tests): {skip_reason}"
                      if skip_reason else
                      f"SPEC schema_version "
                      f"{meta.get('schema_version', 1)} — без AC-разметки, "
                      f"tests_writing недоступна")
            store.set_state(conn, task_id, "in_dev", "operator", detail)
            print(f"  дальше: artel.py run {task_id}  (запуск разработчика)")
        else:
            store.set_state(conn, task_id, "tests_writing", "operator",
                            "гейт SPEC пройден — приёмочные тесты до кода")
            print(f"  дальше: artel.py run {task_id}  (запуск test_author)")
    elif state == "acceptance":
        store.set_state(conn, task_id, "merge_gate", "operator",
                        "приёмка пройдена")
        print(f"  дальше: artel.py approve {task_id}  (выполнит merge)")
    elif state == "merge_gate":
        branch = t["branch"]
        # Зелёный CI — условие мержа, проверяемое кодом, а не глазами
        # Оператора (SPEC T017, требование 6). Неизвестный статус — это
        # «нельзя»: иначе сломанный или неавторизованный `gh` бесшумно
        # возвращал бы систему к «смержим, посмотрим потом».
        green, note = ci.branch_status(branch)
        store.journal(conn, task_id, "orchestrator", "статус CI ветки", note)
        if not green:
            sys.exit(f"[{task_id}] merge отклонён: {note}\n"
                     f"  задача осталась на гейте merge; почини CI ветки "
                     f"{branch} и повтори: artel.py approve {task_id}")
        print(f"[{task_id}] {note}")
        for cmd in (["git", "checkout", config.MAIN_BRANCH],
                    ["git", "pull", "--ff-only"],
                    ["git", "merge", "--no-ff", branch, "-m",
                     f"{task_id}: merge {branch}"], ["git", "push"]):
            res = subprocess.run(cmd, cwd=config.ROOT,
                                 capture_output=True, text=True)
            if res.returncode != 0:
                store.journal(conn, task_id, "orchestrator", "merge FAILED",
                              res.stderr.strip()[:500])
                sys.exit(f"merge упал на {' '.join(cmd)}:\n{res.stderr}")
        store.set_state(conn, task_id, "done", "orchestrator",
                        f"смержено: {branch}")
    elif state == "escalated":
        # Куда возвращать — знает только тот, кто эскалировал: провал агента
        # (cmd_run) пишет в escalated_from состояние своего шага, потому что
        # чинить надо этот шаг, а не начинать разработку заново. Эскалации по
        # вердикту ревьювера и по исчерпанным лимитам его не пишут и, как
        # раньше, уходят в in_dev: там работа и продолжается.
        back = t["escalated_from"] or "in_dev"
        store.update_task(conn, task_id, escalated_from=None)
        store.set_state(conn, task_id, back, "operator",
                        "эскалация разрешена, продолжаем")
        print(f"  дальше: artel.py run {task_id}")
    else:
        print(f"[{task_id}] в состоянии {state} нечего подтверждать")


def cmd_reject(task_id: str, reason: str) -> None:
    conn = store.db()
    t = store.get_task(conn, task_id)
    if t["state"] != "acceptance":
        sys.exit(f"[{task_id}] reject применим только в acceptance "
                 f"(сейчас {t['state']})")
    rejects = t["accept_rejects"] + 1
    if rejects > config.LIMIT_ACCEPT_REJECTS:
        store.set_state(conn, task_id, "escalated", "fsm",
                        f"лимит отказов приёмки исчерпан: {reason}")
    else:
        store.update_task(conn, task_id, accept_rejects=rejects)
        store.set_state(conn, task_id, "in_dev", "operator",
                        f"приёмка отклонена: {reason}")
