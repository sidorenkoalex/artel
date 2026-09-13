"""`_acceptance_lock_refuses`, `_acceptance_run_refuses` (SPEC
01M2CYQR0357VAQFZ5VACJD9TD, требование 1) — перенесено дословно из
`orchestrator/fsm_advance.py`.

Ни одна из двух функций не проходит через каркас `_base._run_gates`
(SPEC требование 3, PLAN «Подход») — `_acceptance_run_refuses`
докстрингом фиксирует это решение дословно, перенесено без правки."""
from scripts import guard

from .. import acceptance, agent_log, config, fsm, gitcmd, store, workspace, yamlmini


def _acceptance_lock_refuses(conn, task_id: str, t, branch: str,
                             foreign: bool) -> bool:
    """Лок `acceptance_tests/` на `in_dev -> review` (требование 5,
    SPEC T023-семьи): планка, залоченная `tests_writing`
    (`tests_locked_sha`), не имеет права измениться после лока — спор с
    тестом решается эскалацией, не правкой. `locked` — sha АРТЕФАКТНОЙ
    ВЕТКИ пульта (`config.ROOT`, настоящий git) на момент лока, когда
    `foreign` (A7, требование 2 — единая логика для ЛЮБОГО target, теперь
    всегда True) — сверяется ТАМ ЖЕ против текущей головы ТОЙ ЖЕ ветки
    (`branch`), не «HEAD» рабочего дерева (чужой чекаут не должен
    сверять лок с чужой веткой вместо своей). Не-foreign (сегодня
    недостижимо после генерализации self — песочница без git) — прежнее
    поведение: сверка по "HEAD" рабочего дерева main.

    `False` — лока нет вовсе либо он не нарушен."""
    locked = t["tests_locked_sha"]
    if not locked:
        return False
    lock_ref = branch if foreign else "HEAD"
    names = gitcmd.diff_names(locked, lock_ref, f"tasks/{task_id}/acceptance_tests")
    if names is None:
        # git не ответил (недостижимый sha после rebase/squash, сбой
        # команды) — fail-closed тем же принципом, что и
        # fixation.check_integrity() при неответившем git (ADR-0002).
        detail = (f"лок acceptance_tests/ не проверен: git не "
                  f"ответил на sha {locked} — сверка невозможна")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: лок приёмочных тестов", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        print(f"  дальше: разберись, почему git не отвечает на "
              f"tests_locked_sha={locked}, и повтори "
              f"artel.py advance {task_id}")
        return True
    if names:
        # Разница только по файлам, игнорируемым `.gitignore` пульта
        # (SPEC 01M1KVG3KSCY47HWXWF5HM0E76, требование 3, AC-4) — не
        # спор с локом, тот же критерий, что у
        # `checkpoint._commit_external_step_artifacts`.
        ignored = gitcmd.check_ignore(names)
        if ignored is None:
            detail = (f"лок acceptance_tests/ не проверен: git не "
                      f"ответил на проверку .gitignore — сверка "
                      f"невозможна")
            store.journal(conn, task_id, "fsm",
                          "переход отклонён: лок приёмочных тестов", detail)
            print(f"[{task_id}] переход отклонён: {detail}")
            print(f"  дальше: разберись, почему git не отвечает на "
                  f"check-ignore, и повтори artel.py advance "
                  f"{task_id}")
            return True
        names = [n for n in names if n not in ignored]
    if names:
        detail = (f"acceptance_tests/ изменены после лока "
                  f"(sha {locked}) — спор с тестом = эскалация, "
                  f"не правка")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: лок приёмочных тестов", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        print(f"  дальше: верни acceptance_tests/ как было, "
              f"либо эскалируй разногласие Оператору")
        return True
    return False


def _acceptance_run_refuses(conn, task_id: str, t, tdir, target: str,
                            branch: str) -> bool:
    """Прогон приёмки после подтяжки (SPEC T023, требование 6; ADR-0015,
    требование 2 — переехал с `in_dev -> review` на `in_dev -> verifying`,
    вместе с остальными шестью рубежами того же перехода): красный
    acceptance-тест чинит код разработчик, не переписывает тест (тесты
    залочены — см. `_acceptance_lock_refuses` выше). Не через `_run_gates`
    (PLAN «Подход») — `acc_tdir` нужен ПОСЛЕ прохода для
    `acceptance.summary`, пересчитывать его ценой повторного
    `acceptance.materialize_from_branch` не нужно, а печать здесь — три
    строки (сообщение, сырой `tail`, подсказка), не формат
    «сообщение+подсказка» остальных гейтов.

    SPEC T045, побочная находка: `tasks/<id>/acceptance_tests` читается
    из worktree задачи, если он заведён и стоит на своей ветке; иначе —
    прежний путь с диска главной копии. Внешний target (SPEC T094,
    требование 10): живого worktree нет вовсе — `acceptance_tests/`
    живёт только в артефактной ветке пульта (`branch` уже резолвлен),
    материализуется НА МЕСТЕ в workspace target'а (SPEC
    01M1RNZ6V7TTTTYAHBMF8JBQQS, требование 1-2, AC-1/AC-2/AC-5).

    `True` — переход отклонён (планка красная)."""
    def _missing_plank_refuses() -> bool:
        if (acc_tdir / "acceptance_tests").is_dir():
            return False
        spec_text = fsm._read_branch_text_or_refuse(conn, task_id, branch,
                                                     "SPEC.md")
        if spec_text is None:
            return True
        meta = yamlmini.frontmatter(spec_text) or {}
        if not guard.requires_ac_markup(meta):
            return False
        detail = (f"планка не найдена в источнике: артефактная ветка "
                  f"{branch} не несёт tasks/{task_id}/acceptance_tests/, а "
                  f"tests_writing не пропущена легитимно (skip_tests не "
                  f"задан в SPEC)")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: планка не найдена в источнике",
                      detail)
        print(f"[{task_id}] переход отклонён: {detail}")
        return True

    acc_tdir = tdir
    run_cwd = config.ROOT
    if target != config.DEFAULT_TARGET:
        run_cwd = config.PROJECTS / target / "workspace"
        run_cwd.mkdir(parents=True, exist_ok=True)
        acc_tdir = acceptance.materialize_from_branch(task_id, branch, run_cwd)
        if _missing_plank_refuses():
            return True
    elif workspace.on_task_branch(task_id, t["branch"]) is True:
        run_cwd = workspace.path(task_id)
        acc_tdir = acceptance.materialize_from_branch(task_id, branch, run_cwd)
        if _missing_plank_refuses():
            return True
    green, tail = acceptance.run(acc_tdir, cwd=run_cwd)
    # Fingerprint окружения (SPEC T101, требование 4б, AC-5) — часть
    # исхода прогона приёмочных тестов, значение поля `detail`
    # существующего журнального события, без новой таблицы/колонки.
    fingerprint = agent_log.environment_fingerprint()
    if not green:
        detail = f"acceptance_tests красные:\n{tail}\nокружение: {fingerprint}"
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: приёмочные тесты", detail)
        print(f"[{task_id}] переход отклонён: приёмочные тесты красные")
        print(tail)
        print(f"  дальше: почини код (не тест) и повтори "
              f"artel.py advance {task_id}")
        return True
    card = acceptance.summary(acc_tdir, branch=t["branch"])
    store.journal(conn, task_id, "fsm", "приёмочные тесты пройдены",
                  f"{card}\nокружение: {fingerprint}")
    print(f"[{task_id}] {card}")
    return False
