"""`_acceptance_lock_refuses`, `_acceptance_run_refuses` (SPEC
01M2CYQR0357VAQFZ5VACJD9TD, требование 1) — перенесено дословно из
`orchestrator/fsm_advance.py`.

Ни одна из двух функций не проходит через каркас `_base._run_gates`
(SPEC требование 3, PLAN «Подход») — `_acceptance_run_refuses`
докстрингом фиксирует это решение дословно, перенесено без правки."""
import contextlib
import hashlib
from pathlib import Path

from scripts import guard

from .. import (acceptance, agent_log, artifact_branch, config, fsm, gitcmd,
               store, workspace, yamlmini)
from .refusal_classes import ACCEPTANCE_CODE_COPY_REFUSAL_ACTION

LONG_LIVED_MANIFEST_ACTION = "переход отклонён: перечень долгоживущих тестов"
# Подсказка отказа сверки перечня (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ,
# требование 7) — та же, что у лока каталога приёмочных тестов по смыслу:
# спор с тестом решает Оператор, не правка.
LONG_LIVED_MANIFEST_HINT = ("код чинится под тест; правка теста — "
                            "`amend-tests` по решению Оператора")


def long_lived_manifest_rel(task_id: str) -> str:
    return f"tasks/{task_id}/acceptance_tests/{guard.LONG_LIVED_MANIFEST_NAME}"


def blob_sha256(rev: str, rel: str, repo: Path | None = None) -> str | None:
    """SHA-256 БАЙТОВ файла `rel` в дереве `rev` (Р2: сумма — от дерева
    коммита, не от текста рабочего каталога и не от текста, прочитанного с
    перекодировкой концов строк); `None` — git не ответил или пути нет.
    `gitcmd.carpentry` — единственный вход git пульта, отдающий байты;
    `repo` — клон проекта задачи (ADR-0021 п.1); не назван — клон артели."""
    if repo is None:
        repo = workspace.repo(config.DEFAULT_TARGET)
    res = gitcmd.carpentry(repo, ["show", f"{rev}:{rel}"], None,
                           text=False)
    if res is None or res.returncode != 0:
        return None
    return hashlib.sha256(res.stdout).hexdigest()


def long_lived_manifest(task_id: str, t, target: str
                        ) -> tuple[dict[str, str] | None, str]:
    """({путь: sha256}, "") перечня долгоживущих файлов из дерева коммита
    лока `tests_locked_sha` — неизменного, в отличие от головы ветки
    документов, правку которой ловит сверка лока; (None, причина) — git не
    ответил или перечень испорчен.

    Пустой словарь — сверять нечего: задача вне области правила (внешний
    target, `skip_tests` — лока нет), либо лок снят до внедрения перечня
    (задача 2 ADR-0020) и файла в дереве лока нет. У задачи, залоченной
    после внедрения, перечень в дереве лока есть всегда: выход из
    `tests_writing` без записанного перечня отказывает."""
    if target != config.DEFAULT_TARGET or not t["tests_locked_sha"]:
        return {}, ""
    locked = t["tests_locked_sha"]
    rel = long_lived_manifest_rel(task_id)
    repo = workspace.task_repo(task_id)
    listed = gitcmd.ls_tree_files(locked, rel, repo=repo)
    if listed is None:
        return None, f"git не ответил на дерево лока {locked}"
    if not listed:
        return {}, ""
    text, reason = gitcmd.show(locked, rel, repo=repo)
    if text is None:
        return None, f"перечень в дереве лока {locked} не прочитан: {reason}"
    return guard.parse_long_lived_manifest(text)


def _long_lived_manifest_refuses(conn, task_id: str) -> bool:
    """Общий узел сверки перечня долгоживущих файлов с головой кодовой
    ветки (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 7, рубежи Р4:
    `in_dev -> verifying`, `verifying -> review`, `review -> acceptance`,
    `approve` из `acceptance`, гейт мержа после `_sync_main_or_wait`).
    Каждый путь перечня обязан быть в дереве головы кодовой ветки с той же
    суммой; изменённый или удалённый файл — отказ с путём и подсказкой.
    Сбой git — отказ, не пропуск (ADR-0002, fail-closed).

    Строка задачи читается здесь, а не берётся у вызывающего: на гейте
    мержа его `t` мог быть прочитан до подтяжки main.

    `True` — переход отклонён (журнал и печать уже сделаны)."""
    t = store.get_task(conn, task_id)
    digests, reason = long_lived_manifest(task_id, t,
                                          store.task_target(conn, task_id))
    problems: list[str] = []
    if digests:
        repo = workspace.task_repo(task_id)
        head = gitcmd.branch_head_sha(t["branch"], repo=repo)
        present = gitcmd.ls_tree_files(head, "tests", repo=repo) if head else None
        if not head:
            reason = f"голова кодовой ветки {t['branch']} не прочитана"
        elif present is None:
            reason = f"git не ответил на дерево головы {head}"
        else:
            for path, digest in sorted(digests.items()):
                if path not in present:
                    problems.append(f"{path} удалён")
                    continue
                actual = blob_sha256(head, path, repo)
                if actual is None:
                    reason = f"{path} не прочитан на голове {head}"
                    break
                if actual != digest:
                    problems.append(f"{path} изменён")
    if reason:
        detail = (f"долгоживущие файлы задачи не сверены с перечнем: "
                  f"{reason} — сверка невозможна")
    elif problems:
        detail = (f"долгоживущие файлы задачи расходятся с перечнем лока "
                  f"{t['tests_locked_sha']}: {'; '.join(problems)} — "
                  f"{LONG_LIVED_MANIFEST_HINT}")
    else:
        return False
    store.journal(conn, task_id, "fsm", LONG_LIVED_MANIFEST_ACTION, detail)
    print(f"[{task_id}] переход отклонён: {detail}")
    return True


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
    names = artifact_branch.diff_names(task_id, locked, lock_ref,
                                       f"tasks/{task_id}/acceptance_tests")
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
        ignored = gitcmd.check_ignore(names, repo=workspace.task_repo(task_id))
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
    """Обёртка прогона приёмки (`_acceptance_run_body`): планка, выложенная
    в рабочую копию кода, убирается на выходе из блока при любом исходе —
    зелёном, красном, отказе до прогона и исключении внутри него (ADR-0021,
    этап 1; SPEC 01M409YKM3QE5KVRGV0G94F5ZC, требование 3)."""
    with contextlib.ExitStack() as cleanup:
        return _acceptance_run_body(conn, task_id, t, tdir, target, branch,
                                    cleanup)


def _acceptance_run_body(conn, task_id: str, t, tdir, target: str,
                         branch: str, cleanup: contextlib.ExitStack) -> bool:
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

    Рабочая копия задачи не заведена или не выписана на ветку — отказ
    своим действием класса «чинит Оператор»
    (`ACCEPTANCE_CODE_COPY_REFUSAL_ACTION`, SPEC 01M446WEVJXARR5CDED8RE9CCR,
    требование 5.2): «приёмочные тесты» остаётся за красной планкой,
    которую чинит developer.

    `True` — переход отклонён (планка красная)."""
    def _missing_plank_refuses() -> bool:
        if acceptance.plank_present(acc_tdir / "acceptance_tests"):
            return False
        spec_text = fsm._read_foreign_branch_text_or_refuse(conn, task_id,
                                                             branch, "SPEC.md")
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
    # Долгоживущие файлы перечня (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ,
    # требование 9) — в том же прогоне, что планка; они лежат в `tests/`
    # кодовой ветки, поэтому исполнимы только из её рабочей копии.
    long_lived = None
    if target != config.DEFAULT_TARGET:
        run_cwd, error = workspace.ensure(task_id, t["branch"])
        if error is not None:
            # Без рабочей копии планка легла бы в пустой каталог и упала бы
            # на импорте кода — причина `ensure` понятнее этого исхода.
            detail = f"рабочая копия задачи не заведена: {error}"
            store.journal(conn, task_id, "fsm",
                          ACCEPTANCE_CODE_COPY_REFUSAL_ACTION, detail)
            print(f"[{task_id}] переход отклонён: {detail}")
            print(f"  дальше: artel.py workspace {task_id} и повтори "
                  f"artel.py advance {task_id}")
            return True
        acc_tdir = cleanup.enter_context(
            acceptance.plank_in_code_copy(task_id, branch, run_cwd))
        if _missing_plank_refuses():
            return True
    elif workspace.on_task_branch(task_id, t["branch"], target) is True:
        run_cwd = workspace.path(task_id, target)
        acc_tdir = cleanup.enter_context(
            acceptance.plank_in_code_copy(task_id, branch, run_cwd))
        # Сбой чтения перечня (`None`) раньше в `in_dev` уже отклонил
        # переход узлом сверки `_long_lived_manifest_refuses`.
        digests, _reason = long_lived_manifest(task_id, t, target)
        if digests is not None and t["tests_locked_sha"]:
            long_lived = sorted(digests)
        if _missing_plank_refuses():
            return True
    else:
        # Без рабочей копии на ветке задачи долгоживущие файлы перечня
        # исполнить негде; прогон одной планки молча выронил бы их группу
        # (требование 9) — отказ, как на выходе из `tests_writing`.
        digests, _reason = long_lived_manifest(task_id, t, target)
        if digests is None or digests:
            detail = (f"рабочая копия задачи не выписана на ветку "
                      f"{t['branch']} — долгоживущие файлы перечня исполнить "
                      f"негде")
            store.journal(conn, task_id, "fsm",
                          ACCEPTANCE_CODE_COPY_REFUSAL_ACTION, detail)
            print(f"[{task_id}] переход отклонён: {detail}")
            print(f"  дальше: artel.py workspace {task_id} и повтори "
                  f"artel.py advance {task_id}")
            return True
    if long_lived:
        green, tail = acceptance.run(acc_tdir, cwd=run_cwd, extra=long_lived)
    else:
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
    if long_lived is None:
        card = acceptance.summary(acc_tdir, branch=t["branch"],
                                  repo=workspace.task_repo(task_id))
    else:
        card = acceptance.summary(
            acc_tdir, branch=t["branch"],
            long_lived=[run_cwd / path for path in long_lived],
            repo=workspace.task_repo(task_id))
    store.journal(conn, task_id, "fsm", "приёмочные тесты пройдены",
                  f"{card}\nокружение: {fingerprint}")
    print(f"[{task_id}] {card}")
    return False
