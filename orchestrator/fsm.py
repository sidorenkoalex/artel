"""Переходы автомата: advance по артефактам, approve/reject Оператора."""
import subprocess
import sys
from pathlib import Path

from scripts import guard

from . import (acceptance, alerts, artifacts, budget, ci, cleanup, config,
              fixation, gates, gitcmd, lease, merge_lock, retro, store,
              workspace, yamlmini)

# Регенерация/коммит карты кодовой базы на merge_gate (SPEC T042).
MAP_REL = "docs/codebase-map.md"


def _map_content_without_sha(text: str) -> str:
    """Текст карты без строки `built_at_sha:` — сверка содержимым, тем же
    принципом, что и CI-джоб `codebase-map` (`.github/workflows/ci.yml`,
    ред. Оператора 26.08, SPEC T042 требование 2): `built_at_sha` меняется
    при каждой регенерации и сам по себе не повод коммитить.
    """
    return "\n".join(line for line in text.splitlines()
                     if not line.startswith("built_at_sha:"))


def _map_regen_incident(conn, task_id: str, message: str) -> None:
    """Провал шага карты — журнал и incident-алерт, не отказ merge
    (SPEC T042, требование 5)."""
    store.journal(conn, task_id, "orchestrator",
                  "регенерация карты FAILED", message)
    alerts.raise_alert(conn, store.task_target(conn, task_id), "incident",
                       "fsm.map_regen", message)


def _regenerate_and_commit_map(conn, task_id: str) -> None:
    """Регенерация `docs/codebase-map.md` после merge и коммит отдельным
    коммитом, если карта содержательно изменилась (SPEC T042, требования
    1-3); без содержательных отличий — откат правки, коммита нет.

    Зовётся ПОСЛЕ успешного merge, ДО push (требование 1, 4): что бы тут
    ни случилось, `git push` в вызывающем коде выполняется в любом случае
    (требование 5) — эта функция никогда не бросает исключение и не
    делает `sys.exit`, любой провал уходит в `_map_regen_incident`.
    """
    map_path = config.ROOT / MAP_REL
    try:
        committed = map_path.read_text(encoding="utf-8")
    except OSError as exc:
        _map_regen_incident(conn, task_id, f"{MAP_REL} не прочитан: {exc}")
        return
    # Не git-вызов (требование 6, AC-4) — прямой subprocess.run, тем же
    # приёмом, что brief._regenerate_map.
    try:
        regen = subprocess.run(["python3", "scripts/codebase_map.py"],
                               cwd=config.ROOT, capture_output=True, text=True)
    except OSError as exc:
        _map_regen_incident(conn, task_id,
                            f"регенерация {MAP_REL} не удалась: {exc}")
        return
    if regen.returncode != 0:
        reason = regen.stderr.strip()[:200] or f"код возврата {regen.returncode}"
        _map_regen_incident(conn, task_id,
                            f"регенерация {MAP_REL} не удалась: {reason}")
        return
    try:
        regenerated = map_path.read_text(encoding="utf-8")
    except OSError as exc:
        _map_regen_incident(conn, task_id, f"{MAP_REL} не прочитан: {exc}")
        return
    if _map_content_without_sha(regenerated) == _map_content_without_sha(committed):
        restore = gitcmd.git("checkout", "--", MAP_REL)
        if restore.returncode != 0:
            _map_regen_incident(
                conn, task_id,
                f"откат {MAP_REL} без содержательных отличий не удался: "
                f"{restore.stderr.strip()[:200]}")
        return
    added = gitcmd.git("add", MAP_REL)
    if added.returncode != 0:
        _map_regen_incident(conn, task_id,
                            f"git add {MAP_REL} не удался: "
                            f"{added.stderr.strip()[:200]}")
        return
    commit = gitcmd.git(
        "commit", "-m",
        f"карта кодовой базы: регенерация после merge {task_id}")
    if commit.returncode != 0:
        _map_regen_incident(conn, task_id,
                            f"коммит {MAP_REL} не удался: "
                            f"{commit.stderr.strip()[:200]}")


# Дайджест задачи в main на переходе в done/killed (SPEC T043). killed-RETRO
# доставляется не самим `kill` (решение (d) Оператора, tasks/T043/TZ.md —
# `orchestrator/cleanup.py` не трогается, инвариант 15 цел буквально), а
# ближайшим `merge_gate` ЛЮБОЙ задачи, тем же приёмом, что карта T042.


def _retro_incident(conn, task_id: str, message: str) -> None:
    """Провал шага RETRO — журнал и incident-алерт, не отказ merge (SPEC
    T043, требование 9), тем же приёмом, что `_map_regen_incident`."""
    store.journal(conn, task_id, "orchestrator", "RETRO FAILED", message)
    alerts.raise_alert(conn, store.task_target(conn, task_id), "incident",
                       "fsm.retro", message)


def _write_and_stage_retro(conn, task_id: str, text: str) -> bool:
    """True — файл записан и добавлен в индекс git; False — провал
    (инцидент уже заведён)."""
    path = retro.retro_path(task_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        _retro_incident(conn, task_id, f"{path} не записан: {exc}")
        return False
    added = gitcmd.git("add", retro.retro_rel_path(task_id))
    if added.returncode != 0:
        _retro_incident(conn, task_id,
                        f"git add {retro.retro_rel_path(task_id)} не удался: "
                        f"{added.stderr.strip()[:200]}")
        return False
    return True


def _commit_retro(conn, task_id: str, message: str) -> None:
    commit = gitcmd.git("commit", "-m", message)
    if commit.returncode != 0:
        _retro_incident(conn, task_id,
                        f"коммит RETRO не удался: "
                        f"{commit.stderr.strip()[:200]}")


def _generate_and_commit_retro(conn, task_id: str, merge_sha: str) -> None:
    """done-RETRO мержащейся задачи + подбор killed-долгов (SPEC T043,
    требования 1, 2, 5-8) — коммит отдельный на каждую задачу (провал
    одной не должен мешать журналировать/чинить остальные по отдельности).

    Зовётся ПОСЛЕ успешного merge, ДО push (тем же местом, что
    `_regenerate_and_commit_map`): что бы тут ни случилось, `push` в
    вызывающем коде выполняется в любом случае (требование 9) — генерация
    контента обёрнута широким `except Exception` умышленно (не только
    `OSError`, как у карты): в отличие от регенерации карты, здесь
    несколько независимых источников чтения (журнал БД, SPEC, разбор
    acceptance_tests/), и ни один сбой любого из них не имеет права
    отменить сам переход.
    """
    try:
        text = retro.build_done(conn, task_id, merge_sha)
    except Exception as exc:  # noqa: BLE001 — см. докстринг: провал не критичен
        _retro_incident(conn, task_id, f"генерация RETRO не удалась: {exc}")
    else:
        if _write_and_stage_retro(conn, task_id, text):
            _commit_retro(conn, task_id, f"{task_id}: RETRO задачи")

    debts = [t["id"] for t in store.all_tasks(conn)
            if t["state"] == "killed" and not retro.retro_path(t["id"]).exists()]
    for debt_id in debts:
        try:
            debt_text = retro.build_killed(conn, debt_id)
        except Exception as exc:  # noqa: BLE001 — см. докстринг выше
            _retro_incident(conn, debt_id,
                            f"генерация killed-RETRO {debt_id} не удалась: {exc}")
            continue
        if _write_and_stage_retro(conn, debt_id, debt_text):
            _commit_retro(conn, debt_id,
                          f"{task_id}: killed-RETRO долга {debt_id}")


# --- сверка свежести ветки до гейта (SPEC T051) ---------------------------

def _conflicting_files(wt_path) -> list[str]:
    """Файлы с неразрешённым конфликтом в worktree после неудачного `git
    merge` (SPEC T067, требование 1) — тем же приёмом, что уже читает
    `_handle_merge_conflict` для ДРУГОГО merge (main <- ветка задачи,
    T052), только здесь список нужен ДО решения абортить или разрешать
    самому, а не только для диагностики.

    Пустой список — git не ответил осмысленно (заглушки без реального
    git, инфраструктурный сбой самой команды `diff`) — вызывающий код
    в этом случае не находит РОВНО `[MAP_REL]` и уходит в прежний
    безусловный abort+escalate (требование 4, тот же вырожденный случай
    деградации, что у остальных примитивов подтяжки).
    """
    res = gitcmd.in_repo(wt_path, "diff", "--name-only", "--diff-filter=U")
    if res is None or res.returncode != 0:
        return []
    return sorted(set(res.stdout.split()))


def _auto_resolve_map_conflict(conn, task_id: str, wt_path) -> bool:
    """Единственный конфликтующий файл — `docs/codebase-map.md` (SPEC
    T067, требования 1-2, 5): `checkout --theirs` + регенерация
    генератором НА СЛИТОМ дереве worktree задачи (`cwd=wt_path`, не
    `config.ROOT` — карта, которую сверяют критерии приёмки, это карта
    ВЕТКИ задачи, не главной копии пульта) + `add` + `commit`, который
    и завершает merge, начатый вызывающим кодом.

    `True` — merge завершён, подтяжка продолжается точно так же, как
    обычная удачная подтяжка без конфликта (требование 2); `False` —
    любой шаг не удался (checkout/регенерация/add/commit) — merge НЕ
    завершён, вызывающий код обязан сам сделать `git merge --abort` и
    эскалировать тем же путём, что и неразрешаемый конфликт (требование
    5, AC-5): здесь нарочно нет своего abort — единая точка отката
    ближе к месту, где решение «разрешать или нет» уже принято.
    """
    checkout = gitcmd.in_repo(wt_path, "checkout", "--theirs", MAP_REL)
    if checkout is None or checkout.returncode != 0:
        return False
    try:
        regen = subprocess.run(["python3", "scripts/codebase_map.py"],
                               cwd=wt_path, capture_output=True, text=True)
    except OSError:
        return False
    if regen.returncode != 0:
        return False
    added = gitcmd.in_repo(wt_path, "add", MAP_REL)
    if added is None or added.returncode != 0:
        return False
    commit = gitcmd.in_repo(wt_path, "commit", "-m",
                            f"{task_id}: подтяжка {config.MAIN_BRANCH}")
    if commit is None or commit.returncode != 0:
        return False
    store.journal(
        conn, task_id, "orchestrator",
        "конфликт подтяжки: карта авторазрешена регенерацией",
        f"{MAP_REL} — единственный конфликтующий файл, разрешён "
        f"checkout --theirs + регенерация scripts/codebase_map.py на "
        f"слитом дереве worktree задачи")
    return True


def _pull_main_or_escalate(conn, task_id: str, t, state: str) -> str:
    """Сверка свежести ветки задачи на входе в гейт (SPEC T051, требования
    1-7, 10; ADR-0006 п.2) и, начиная с T053 требование 5, ВНУТРИ окна
    `merge_gate` под мьютексом merge — один и тот же узел для всех трёх
    точек сверки (`in_dev -> review`, `acceptance -> merge_gate`,
    `merge_gate -> done`).

    Возврат — один из трёх исходов:
    - `"escalated"` — переход уже отклонён: задача уже эскалирована
      (состояние и диагностика уже записаны через `store.set_state`,
      требования 5-6); вызывающий код обязан немедленно вернуться, не
      выполняя сам переход;
    - `"fresh"` — ветка не отстала от `config.MAIN_BRANCH` (требование 7:
      поведение перехода прежнее байт-в-байт, никакой git-вызов не
      сделан);
    - `"pulled"` — подтяжка прошла и приёмочные тесты в подтянутом
      дереве зелёные. Точки `in_dev -> review`/`acceptance -> merge_gate`
      обе продолжают штатный переход одинаково что при `"fresh"`, что при
      `"pulled"` (T051, не различали их и раньше — общий `bool`); третья
      точка (`merge_gate -> done`, T053) обязана различать их сама: после
      `"pulled"` merge в этом же вызове НЕ выполняется (SPEC T053,
      требование 5) — сдвинутый головой ветки sha делает зафиксированный
      снимок невалидным для merge (инвариант 19 не ослабляется).

    Merge — единственный вне `merge_gate`, разрешённый ADR-0006 п.2: в
    worktree ЗАДАЧИ (`gitcmd.in_repo`, форма `-C`), вливает
    `config.MAIN_BRANCH`, ветку задачи в аргументах не упоминает и не
    трогает main ни байтом (требование 10) — не rebase (требование 3),
    существующие sha ветки остаются валидными предками.

    `gitcmd.commits_behind` вернул `None` — git не ответил (песочницы без
    реального git: `fake_git` и аналоги, требование 9) — тот же
    вырожденный случай деградации, что и у остальных git-примитивов
    оркестратора: сверка молча пропускается, `bool(None)` ложно ровно как
    и `bool(0)` (ветка не отстала) — оба ведут к одному и тому же
    «ничего не делать».

    Конфликт merge, где единственный конфликтующий файл —
    `docs/codebase-map.md` (SPEC T067), разрешается здесь же сам, не
    эскалируя: `_conflicting_files` + `_auto_resolve_map_conflict`. Любой
    другой конфликт (карта вместе с другим файлом, без карты вовсе, или
    авторазрешение само не удалось) — прежнее поведение T051/T052
    байт-в-байт: `git merge --abort` + `"escalated"`.
    """
    branch = t["branch"]
    behind = gitcmd.commits_behind(branch)
    if not behind:
        return "fresh"

    wt_path, error = workspace.ensure(task_id, branch)
    if error is not None:
        store.set_state(
            conn, task_id, "escalated", "fsm", expected_state=state,
            detail=f"подтяжка {config.MAIN_BRANCH} отменена: worktree "
            f"задачи не создан — {error}")
        return "escalated"

    merge = gitcmd.in_repo(wt_path, "merge", "--no-ff", config.MAIN_BRANCH,
                           "-m", f"{task_id}: подтяжка {config.MAIN_BRANCH}")
    if merge is None or merge.returncode != 0:
        resolved = False
        if merge is not None:
            files = _conflicting_files(wt_path)
            if files == [MAP_REL]:
                resolved = _auto_resolve_map_conflict(conn, task_id, wt_path)
        if not resolved:
            abort = gitcmd.in_repo(wt_path, "merge", "--abort")
            note = merge.stderr.strip()[:500] if merge is not None else "git не ответил"
            if abort is None or abort.returncode != 0:
                note += (f"; git merge --abort не удался: "
                        f"{abort.stderr.strip()[:200] if abort is not None else 'git не ответил'}")
            store.set_state(
                conn, task_id, "escalated", "fsm", expected_state=state,
                detail=f"конфликт подтяжки {config.MAIN_BRANCH} в ветку "
                f"{branch}: {note}")
            return "escalated"

    green, tail = acceptance.run(wt_path / "tasks" / task_id)
    if not green:
        store.set_state(
            conn, task_id, "escalated", "fsm", expected_state=state,
            detail=f"приёмочные тесты красные после подтяжки "
            f"{config.MAIN_BRANCH} (слияние сохранено, откат не "
            f"выполняется):\n{tail}")
        return "escalated"

    return "pulled"


# --- автогейт acceptance по политике gates.yaml (ADR-0007, SPEC T066) -----

AUTOGATE_PASS_MESSAGE = "acceptance пройден автогейтом (политика gates.yaml)"


def _autogate_conditions(conn, task_id: str, t, acc_tdir: Path,
                         iteration: int) -> tuple[list[str], str | None]:
    """(выполненные условия, причина первого невыполненного).

    Короткое замыкание на первом несовпадении — SPEC требование 4 просит
    ОДНУ строку причины, не собранный список всех отказов сразу. Условие
    "б" (приёмочные тесты задачи зелёные) сюда не входит отдельной
    проверкой: к этой точке код уже гарантированно прошёл `acceptance.run`
    зелёным (иначе переход не добрался бы до состояния `acceptance`
    вообще) — только записывается в перечень как выполненное.
    """
    ok: list[str] = []

    tests_dir = acc_tdir / "acceptance_tests"
    if not tests_dir.is_dir() or not any(tests_dir.glob("*.py")):
        return ok, ("автогейт: каталог приёмочных тестов пуст или "
                    "отсутствует")
    _, markers = guard.scan_acceptance_tests(acc_tdir)
    manual_ns = sorted(n for n, (kind, _) in markers.items() if kind == "manual")
    skip_ns = sorted(n for n, (kind, _) in markers.items() if kind == "skip")
    if manual_ns:
        return ok, (f"автогейт: критерии manual — "
                    f"{', '.join(f'AC-{n}' for n in manual_ns)}")
    if skip_ns:
        return ok, (f"автогейт: критерии skip — "
                    f"{', '.join(f'AC-{n}' for n in skip_ns)}")
    ok.append("каталог приёмочных тестов: 0 manual, 0 skip критериев")
    ok.append("приёмочные тесты задачи зелёные")

    wt_root = (workspace.path(task_id)
              if workspace.on_task_branch(task_id, t["branch"]) is True
              else None)
    if wt_root is None:
        return ok, ("автогейт: полный набор tests/ не проверен — worktree "
                    "задачи не заведён")
    green, _ = acceptance.run_full_suite(wt_root)
    if not green:
        return ok, "автогейт: полный набор tests/ красный"
    ok.append("полный набор tests/ в worktree ветки зелёный")

    if budget.budget_block(t) is not None:
        return ok, "автогейт: бюджет задачи исчерпан"
    ok.append(f"бюджет задачи не превышен (${t['spent_usd'] or 0.0:.2f} из "
              f"${t['budget_usd'] or 0.0:.2f})")

    total = store.total_spent(conn)
    if any(total >= config.PROGRAM_STOP_LOSS_USD * ratio
          for ratio in config.PROGRAM_ALERT_RATIOS):
        return ok, "автогейт: порог расхода программы (A1) пробит"
    ok.append("порог расхода программы (A1) не пробит")

    ok.append(f"вердикт REVIEW approved текущей итерации ({iteration})")
    return ok, None


def _maybe_autogate_acceptance(conn, task_id: str, t, acc_tdir: Path,
                               iteration: int) -> None:
    """После перехода `review -> acceptance` — попытка автогейта.

    Политика гейта acceptance не `auto` (включая неизвестное значение,
    отсутствие секции или нечитаемый `gates.yaml` — `gates.policy`
    вырождает всё это в `manual`) — функция не журналирует и не печатает
    НИЧЕГО: поведение обязано остаться байт-в-байт прежним (SPEC AC-5).

    Условие не выполнено — задача остаётся в `acceptance` (уже
    установлено вызывающим кодом) и ждёт Оператора; причина — одной
    строкой в журнале и в выводе (SPEC AC-4). Все условия выполнены —
    гейт проходится автогейтом: переход `acceptance -> merge_gate` тем
    же действием, `actor=autogate`, перечень условий в детали журнала
    (SPEC AC-1..AC-3).

    Сверка свежести ветки (T051) здесь намеренно не повторяется: между
    входом в `acceptance` (только что, этим же вызовом) и этим решением
    не проходит времени, в отличие от ручного approve после ожидания
    Оператора — второй такой же проверкой без временнóго окна нечего
    ловить.
    """
    if gates.policy("acceptance") != gates.AUTO:
        return
    ok_conditions, reason = _autogate_conditions(conn, task_id, t, acc_tdir,
                                                 iteration)
    if reason is not None:
        store.journal(conn, task_id, "fsm", "автогейт acceptance не пройден",
                      reason)
        print(f"[{task_id}] {reason} — жду Оператора")
        return
    print(f"[{task_id}] {AUTOGATE_PASS_MESSAGE}")
    store.set_state(conn, task_id, "merge_gate", "autogate",
                    expected_state="acceptance",
                    detail="; ".join(ok_conditions))
    print(f"  дальше: artel.py approve {task_id}  (выполнит merge)")


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


def _read_branch_text_or_refuse(conn, task_id: str, branch: str,
                                rel_name: str) -> str | None:
    """Текст `tasks/<id>/<rel_name>` С ВЕТКИ задачи; `None` — дерево на
    чужой ветке, а файл там не прочитан — отказ уже журналирован и
    напечатан (SPEC T031, T047: общий узел для мест, где отсутствие
    файла на ветке — не легитимное «ещё не готово», а именованный отказ,
    прецедент — прежнее инлайн-чтение PLAN.md в `in_dev`).

    Звать только когда `gitcmd.on_foreign_branch(branch)` истинно — сама
    функция это не проверяет, только читает и оформляет отказ.
    """
    text, reason = gitcmd.show(branch, f"tasks/{task_id}/{rel_name}")
    if text is None:
        detail = (f"дерево не на ветке задачи {branch} — {rel_name} "
                  f"ветки не прочитан ({reason})")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: дерево не на ветке задачи", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
    return text


def _answer_file_count(t, tdir: Path) -> int | None:
    """Число `ANSWER-*.md` задачи — с ВЕТКИ, если рабочее дерево на чужой
    ветке (SPEC T031/T047, тот же приём, что и остальные чтения этого
    файла в модуле), иначе с диска. `None` — git не ответил на чужой
    ветке (нельзя посчитать — не значит «ноль», вызывающий код решает,
    как трактовать).

    Считает файлы, не разбирает номер `n`: гейту возврата (`_cmd_approve`)
    достаточно знать, что число ANSWER-файлов ВЫРОСЛО относительно
    зафиксированного на эскалации снимка (`answer_baseline`), не какой
    именно номер у нового файла.
    """
    branch = t["branch"]
    if gitcmd.on_foreign_branch(branch):
        paths = gitcmd.ls_tree_files(branch, f"tasks/{t['id']}")
        if paths is None:
            return None
        return sum(1 for p in paths
                  if Path(p).name.startswith("ANSWER-")
                  and Path(p).name.endswith(".md"))
    return len(list(tdir.glob("ANSWER-*.md")))


def _answer_baseline_or_refuse(conn, task_id: str, t, tdir: Path) -> int | None:
    """Снимок числа ANSWER-*.md на момент эскалации — тем же приёмом
    отказа, что `_read_branch_text_or_refuse` (SPEC T031, T047): `None`
    от `_answer_file_count` — git не ответил на чужой ветке, а не «файлов
    ноль» — молчаливое схлопывание в `or 0` замаскировало бы именно тот
    класс сбоя, от которого рядом стоящий код (`q_paths is None` и
    остальные ветки этого модуля) отказывает громко (REVIEW T075
    итерация 1, замечание minor). Возврат `None` — отказ уже
    журналирован и напечатан, переход обязан не эскалировать в этот
    момент, а не эскалировать с недостоверным `baseline=0`."""
    count = _answer_file_count(t, tdir)
    if count is None:
        detail = (f"дерево не на ветке задачи {t['branch']} — число "
                  f"ANSWER-*.md не посчитано, эскалация отложена")
        store.journal(conn, task_id, "fsm",
                      "переход отклонён: дерево не на ветке задачи", detail)
        print(f"[{task_id}] переход отклонён: {detail}")
    return count


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

    `errors` несёт и ошибки трассируемости AC (T023), и ошибки маркера
    красноты (`guard.redness_marker_errors_from_files`/`scan_redness_markers`,
    SPEC T064) — единственное место, где обе проверки подключены к выходу
    именно из `tests_writing`: задача, чьё состояние это состояние уже
    прошло, сюда больше не попадает (обратная совместимость T064,
    требование 4, — структурно, через однонаправленность FSM).
    """
    if not gitcmd.on_foreign_branch(branch):
        tested, markers = guard.scan_acceptance_tests(tdir)
        errors = guard.acceptance_traceability_errors(tdir)
        errors = errors + guard.scan_redness_markers(tdir)
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
    redness_files: list[tuple[str, str]] = []
    for p in paths:
        if not p.endswith(".py"):
            continue
        text, _ = gitcmd.show(branch, p)
        if text is None:
            continue
        sources.append(text)
        if Path(p).name.startswith("test_"):
            redness_files.append((p, text))
    meta = yamlmini.frontmatter(spec_text) or {}
    tested, markers = guard.scan_ac_content(sources)
    errors = guard.traceability_errors_from_content(spec_text, meta, tested,
                                                     markers)
    errors = errors + guard.redness_marker_errors_from_files(redness_files)
    return tested, markers, errors


def cmd_advance(task_id: str, session_id: str | None = None) -> bool:
    """Единственная точка движения FSM: читает статусы артефактов.

    Возврат `True` — переход отклонён именно `guard_refuses()` (структура
    артефакта-условия сломана); `False` — любой другой исход, включая
    успешное продвижение и отказ по другой причине (артефакт не ready,
    грязная копия, вердикт не свежий и т.п., а также отказ по чужому
    живому lease — SPEC T044, требование 2). Различение нужно циклу
    `auto` (SPEC T034, требование 2): отказ guard'ом — гейт, на котором
    цикл обязан остановиться, а не звать `cmd_run` заново для того же
    состояния.

    Отказ по lease печатается и возвращает `False`, не бросает исключение
    (в отличие от остальных шести мутирующих команд, `sys.exit`): `advance`
    уже возвращает исход значением, а не исключением, во всех остальных
    ветках — новый способ отказа не должен становиться единственным,
    который `auto` не умеет поймать.
    """
    conn = store.db()
    return bool(lease.run_locked(
        conn, task_id, session_id,
        lambda sid: _advance_with_refixation(conn, task_id),
        on_refusal="print"))


def _advance_with_refixation(conn, task_id: str) -> bool:
    """`_cmd_advance` + перефиксация sha на пути отклонённого перехода
    (SPEC T076, требования 1-5): переход отклонён (guard/условие не
    пройдено), задача осталась в исходном состоянии, а голова ветки
    сдвинулась ТОЛЬКО коммитами собственного шага задачи (роль легитимно
    коммитила артефакты внутри шага, T069/T073) — фиксация подтягивается
    на текущую голову тем же итогом, каким её обновил бы успешный
    переход, без эскалации «инцидент целостности» на следующем старте
    шага.

    Успешный переход (состояние сменилось) уже перефиксировал sha сам
    через `store.set_state` -> `record_fixation` — здесь нечего делать
    (требование 5, проверка `state` замыкает функцию раньше сравнения
    sha). Посторонний коммит вне окна шага, класс «грязная копия»
    (голова не сдвинулась вовсе) — `fixation.read()` не изменился или
    `refixate_after_rejected_transition` вернула `False` — фиксация
    остаётся прежней, `check_integrity` эскалирует как и раньше
    (требования 3-4).
    """
    t_before = store.get_task(conn, task_id)
    state_before = t_before["state"]
    entry_sha = t_before["fixed_sha"]
    result = _cmd_advance(conn, task_id)
    if entry_sha and store.get_task(conn, task_id)["state"] == state_before:
        target = store.task_target(conn, task_id)
        current, _clean = fixation.read(task_id, target)
        if current and current != entry_sha:
            fixation.refixate_after_rejected_transition(
                conn, task_id, target, entry_sha, current)
    return result


def _cmd_advance(conn, task_id: str) -> bool:
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
        #
        # Рабочее дерево точно на чужой ветке (SPEC T047, требования 1, 3)
        # — и статус SPEC.md, и батч QUESTIONS.md читаются с ВЕТКИ задачи
        # (класс-дефект T030/T046: главная копия пульта на main видит
        # только то, что закоммичено туда же, не в ветку задачи). Иначе —
        # прежний путь через диск, не тронутый T047.
        branch = t["branch"]
        spec_text = None
        if gitcmd.on_foreign_branch(branch):
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
                q_text = _read_branch_text_or_refuse(conn, task_id, branch,
                                                     "QUESTIONS.md")
                if q_text is None:
                    return False
                if guard_refuses(conn, task_id, tdir / "QUESTIONS.md",
                                 text=q_text):
                    return True
                answer_baseline = _answer_baseline_or_refuse(conn, task_id, t, tdir)
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
            spec_text = _read_branch_text_or_refuse(conn, task_id, branch,
                                                     "SPEC.md")
            if spec_text is None:
                return False
            meta = yamlmini.frontmatter(spec_text) or {}
        else:
            questions = tdir / "QUESTIONS.md"
            if questions.exists():
                if guard_refuses(conn, task_id, questions):
                    return True
                answer_baseline = _answer_baseline_or_refuse(conn, task_id, t, tdir)
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
            if _dirty_refuses(conn, task_id, target, "SPEC.md"):
                return False
            if guard_refuses(conn, task_id, tdir / "SPEC.md", text=spec_text):
                return True
            # До смены состояния: потолок задачи должен стоять уже к тому
            # моменту, когда Оператор смотрит на неё на гейте SPEC.
            budget.apply_spec_budget(conn, t, meta)
            store.set_state(conn, task_id, "spec_gate", "fsm",
                            expected_state=state, detail="SPEC готов — ждёт approve")
        else:
            print(f"[{task_id}] SPEC.md ещё не ready — нечего продвигать")
        return False

    elif state == "review":
        # Рабочее дерево точно на чужой ветке (SPEC T047, требование 2) —
        # вердикт REVIEW.md (status, iteration) читается с ВЕТКИ задачи,
        # тем же приёмом, что SPEC.md выше (класс-дефект T030/T045: главная
        # копия пульта на main не видит вердикт, закоммиченный только в
        # ветку). Иначе — прежний путь через диск, не тронутый T047.
        branch = t["branch"]
        review_text = None
        if gitcmd.on_foreign_branch(branch):
            review_text = _read_branch_text_or_refuse(conn, task_id, branch,
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
        if _dirty_refuses(conn, task_id, target, "REVIEW.md"):
            return False
        if guard_refuses(conn, task_id, tdir / "REVIEW.md", text=review_text):
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
            # Прогон приёмки (SPEC T023, требование 6): красный
            # acceptance-тест чинит код разработчик, не переписывает тест
            # (тесты залочены — см. ветку in_dev выше).
            #
            # SPEC T045, побочная находка (PLAN, «Подход»): после T045
            # главная копия пульта остаётся на main, не на ветке задачи —
            # `tasks/<id>/acceptance_tests` читается из worktree задачи,
            # если он заведён и стоит на своей ветке; иначе (легаси-
            # песочницы без реального git, worktree ещё не заведён)
            # прежний путь — с диска главной копии.
            acc_tdir = tdir
            if workspace.on_task_branch(task_id, t["branch"]) is True:
                acc_tdir = workspace.path(task_id) / "tasks" / task_id
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
            store.journal(conn, task_id, "fsm", "приёмочные тесты пройдены",
                          card)
            print(f"[{task_id}] {card}")
            store.set_state(conn, task_id, "acceptance", "fsm",
                            expected_state=state,
                            detail="ревью пройдено — приёмка Оператором "
                            "(по критериям SPEC)")
            _maybe_autogate_acceptance(conn, task_id, t, acc_tdir, iteration)
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
        elif status == "escalate":
            answer_baseline = _answer_baseline_or_refuse(conn, task_id, t, tdir)
            if answer_baseline is None:
                return False
            store.update_task(conn, task_id, answer_baseline=answer_baseline)
            store.set_state(conn, task_id, "escalated", "fsm",
                            expected_state=state, detail="эскалация от ревьювера")
        return False

    elif state == "tests_writing":
        # test_author закончил: каждый AC-n — тест либо пометка
        # manual/skip/escalate (SPEC T023, требование 4).
        result = _tests_writing_ac_state(conn, task_id, t["branch"], tdir)
        if result is None:
            return False
        tested, markers, errors = result
        escalations = {n: reason for n, (kind, reason) in markers.items()
                      if kind == "escalate"}
        if escalations:
            detail = "; ".join(f"AC-{n}: {reason}"
                               for n, reason in sorted(escalations.items()))
            answer_baseline = _answer_baseline_or_refuse(conn, task_id, t, tdir)
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
        return False

    elif state == "in_dev":
        # разработчик закончил: PLAN ready и ветка запушена -> в ревью
        #
        # Рабочее дерево точно на чужой ветке (SPEC T031) — PLAN.md
        # читается с ВЕТКИ задачи (иначе гейт «PLAN.md не ready» молча
        # держит переход и на чужом чекауте нечего проверять дальше —
        # без этого лок ниже никогда не достигается со стороны AC-3);
        # иначе прежний путь через диск, не тронутый T031. Чтение —
        # общий узел `_read_branch_text_or_refuse` (T047), тот же приём
        # теперь и у SPEC.md/REVIEW.md выше.
        branch = t["branch"]
        foreign = gitcmd.on_foreign_branch(branch)
        plan_text = None
        if foreign:
            plan_text = _read_branch_text_or_refuse(conn, task_id, branch,
                                                     "PLAN.md")
            if plan_text is None:
                return False
            plan_meta = yamlmini.frontmatter(plan_text) or {}
        else:
            plan_meta = artifacts.frontmatter(tdir / "PLAN.md")
        if plan_meta.get("status") in ("ready", "approved"):
            if _dirty_refuses(conn, task_id, target, "PLAN.md"):
                return False
            if guard_refuses(conn, task_id, tdir / "PLAN.md", text=plan_text):
                return True
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
            if _pull_main_or_escalate(conn, task_id, t, state) == "escalated":
                return False
            store.set_state(conn, task_id, "review", "fsm",
                            expected_state=state, detail="MR готов — прогон ревьювера")
        else:
            print(f"[{task_id}] PLAN.md не ready — разработчик ещё работает")
        return False

    else:
        print(f"[{task_id}] состояние {state} двигается через approve/reject/run")
        return False


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


def _touches_protected_path(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in config.PROTECTED_PATHS)


def _handle_merge_conflict(conn, task_id: str, state: str, branch: str,
                           merge_res) -> None:
    """Разбор провала `git merge --no-ff <branch>` при `approve` из
    `merge_gate` (SPEC T052, требования 2-3; AC-3, AC-4, AC-5).

    Отличает содержательный конфликт (git начал merge, но не смог
    разрешить его сам) от инфраструктурного отказа: список файлов с
    неразрешённым конфликтом (`git diff --name-only --diff-filter=U`)
    пуст или git не ответил — конфликта в СОДЕРЖИМОМ нет, отказ прежний
    (`sys.exit`, задача остаётся в `merge_gate`, требование 3/AC-5).

    Список не пуст — содержательный конфликт: `git merge --abort`
    возвращает main в чистое состояние (требование 5), а задача уходит
    в `in_dev` (AC-3) либо, если конфликт задевает защищённый путь
    (`config.PROTECTED_PATHS`), в `escalated` (AC-4) — оба перехода
    несут перечень конфликтующих файлов в журнал через `detail`
    `store.set_state`. Если сам `git merge --abort` не удался, main
    остаётся с незавершённым merge — переход состояния НЕ выполняется
    (иначе main тихо остался бы грязным при формально успешном
    переходе, ломая последующие approve других задач); это
    инфраструктурный отказ той же природы, что и «git не ответил»
    выше — `sys.exit`, задача остаётся в `merge_gate`.
    """
    store.journal(conn, task_id, "orchestrator", "merge FAILED",
                  merge_res.stderr.strip()[:500])
    conflicts = gitcmd.git("diff", "--name-only", "--diff-filter=U")
    files = sorted(set(conflicts.stdout.split())) \
        if conflicts is not None and conflicts.returncode == 0 else []
    if not files:
        sys.exit(f"merge упал на git merge --no-ff {branch}:\n"
                 f"{merge_res.stderr}")

    abort = gitcmd.git("merge", "--abort")
    if abort is None or abort.returncode != 0:
        abort_err = abort.stderr.strip()[:500] if abort is not None else "git не ответил"
        store.journal(conn, task_id, "orchestrator", "merge --abort FAILED",
                      abort_err)
        sys.exit(f"[{task_id}] merge отклонён: конфликт в файлах "
                 f"{', '.join(files)}, но git merge --abort не смог "
                 f"вернуть main в чистое состояние ({abort_err}); "
                 f"main требует ручной уборки Оператором; задача осталась "
                 f"в merge_gate")

    file_list = ", ".join(files)
    protected = [f for f in files if _touches_protected_path(f)]
    if protected:
        detail = (f"конфликт merge затрагивает защищённый путь "
                  f"({', '.join(protected)}); конфликтующие файлы: "
                  f"{file_list}")
        store.set_state(conn, task_id, "escalated", "fsm",
                        expected_state=state, detail=detail)
    else:
        detail = (f"содержательный конфликт merge — возврат в разработку; "
                  f"конфликтующие файлы: {file_list}")
        store.set_state(conn, task_id, "in_dev", "fsm",
                        expected_state=state, detail=detail)


def _cmd_approve_merge_gate(conn, task_id: str, state: str, t) -> None:
    """Тело окна `merge_gate -> done`, исполняемое ПОД МЬЮТЕКСОМ merge
    (SPEC T053, требование 1): сверка главной копии -> сверка свежести
    ветки внутри окна (требования 5-8) -> зелёный CI -> checkout/pull/
    merge -> карта/RETRO -> push -> done.
    """
    branch = t["branch"]
    # Рабочая поверхность оркестратора (SPEC T045, требования 3-4,
    # AC-8 сценарий 2): merge — территория главной копии пульта на
    # main, не чужой ветки Оператора/сессии. Проверяется ДО двухшаговой
    # sha-сверки `confirm_fixation` выше (та уже пройдена к этой
    # точке) — отказ здесь не имеет права сам переключать главную
    # копию, только останавливать команду; не `sys.exit` (в отличие от
    # красного CI/провала git ниже — там инфраструктурный отказ, а не
    # рутинная сверка поверхности): задача остаётся на гейте
    # merge_gate, чтобы Оператор мог повторить approve тем же
    # процессом после перехода на main. Пустая строка — git не ответил
    # (вырожденный случай песочниц без реального git, тот же приём
    # деградации, что у `gitcmd.on_foreign_branch`) — сверять не с чем,
    # пропускается.
    root_branch = gitcmd.current_branch()
    if root_branch and root_branch != config.MAIN_BRANCH:
        detail = (f"главная копия пульта стоит на {root_branch}, не "
                  f"на {config.MAIN_BRANCH} — merge не выполняется; "
                  f"перейди на {config.MAIN_BRANCH} и повтори "
                  f"artel.py approve {task_id}")
        store.journal(conn, task_id, "fsm",
                      "approve отклонён: главная копия не на main",
                      detail)
        print(f"[{task_id}] approve отклонён: {detail}")
        return
    # Сверка свежести ветки ПОД МЬЮТЕКСОМ, до сверки CI (SPEC T053,
    # требования 5-8): main мог уйти вперёд, пока задача стояла на гейте
    # или ждала освобождения чужого merge-окна — дыра №2 из «Контекста»
    # SPEC. Подтяжка сдвигает head ветки задачи, зафиксированный снимок
    # инвалидируется — merge в main в ЭТОМ ЖЕ вызове не выполняется
    # (инвариант 19 не ослабляется), задача остаётся на гейте.
    pull_outcome = _pull_main_or_escalate(conn, task_id, t, state)
    if pull_outcome == "escalated":
        return
    if pull_outcome == "pulled":
        new_head = gitcmd.branch_head_sha(branch)
        print(f"[{task_id}] ветка подтянута к {config.MAIN_BRANCH} "
              f"(новый head {new_head}) — дождись зелёного CI этого head "
              f"и повтори artel.py approve {task_id}")
        return
    # Зелёный CI — условие мержа, проверяемое кодом, а не глазами
    # Оператора (SPEC T017, требование 6). Неизвестный статус — это
    # «нельзя»: иначе сломанный или неавторизованный `gh` бесшумно
    # возвращал бы систему к «смержим, посмотрим потом».
    green, note = ci.branch_status(branch)
    store.journal(conn, task_id, "orchestrator", "статус CI ветки", note)
    if not green:
        # Ре-ран флейка (SPEC T082, требование 7, AC-14..17) — только для
        # ПОДТВЕРЖДЁННО красного статуса: `status_kind` отличает его от
        # «CI ещё идёт» и «статус неизвестен» (ревью итерации 2, замечание
        # major 1) — эти два case не «не прошли», они «ещё не ответили»,
        # ре-ран уже идущего или несуществующего прогона ничего не решает
        # и не подтверждает, а запись в flake-rate «подтверждённый
        # красный» для них была бы ложью, обесценивающей саму метрику.
        # Для них — прежнее поведение (отказ без ре-рана: подожди ещё).
        if ci.status_kind(note) != "red":
            sys.exit(f"[{task_id}] merge отклонён: {note}\n"
                     f"  задача осталась на гейте merge; почини CI ветки "
                     f"{branch} и повтори: artel.py approve {task_id}")
        # `ci.trigger_rerun` реально перезапускает упавший CI-прогон
        # (`gh run rerun --failed`) и ждёт его завершения (`gh run
        # watch`) — не просто повторно читает тот же завершённый статус
        # («не входит»: задача про сам ре-ран прогона, не про сетевую
        # надёжность опроса). Итоговый вердикт всё равно принимает
        # `branch_status` — тем же способом, что и первый раз, а не
        # заключение `gh run watch`, у которого свои критерии зелёности.
        # Каждое срабатывание (флейк или подтверждённый красный) — в
        # метрику flake-rate журнала, флейк отдельно от подтверждённого
        # красного (AC-17).
        rerun_trigger_note = ci.trigger_rerun(branch)
        store.journal(conn, task_id, "orchestrator", "ре-ран CI запущен",
                      rerun_trigger_note)
        rerun_green, rerun_note = ci.branch_status(branch)
        store.journal(conn, task_id, "orchestrator",
                      "статус CI ветки (ре-ран)", rerun_note)
        if rerun_green:
            store.journal(
                conn, task_id, "orchestrator", "flake-rate",
                f"флейк: первый статус красный, ре-ран зелёный "
                f"({note} -> {rerun_note})")
            green, note = rerun_green, rerun_note
        else:
            store.journal(
                conn, task_id, "orchestrator", "flake-rate",
                f"подтверждённый красный: первый статус красный, ре-ран "
                f"тоже красный ({note} -> {rerun_note})")
            sys.exit(f"[{task_id}] merge отклонён: {rerun_note}\n"
                     f"  задача осталась на гейте merge; почини CI ветки "
                     f"{branch} и повтори: artel.py approve {task_id}")
    print(f"[{task_id}] {note}")
    for cmd in (["git", "checkout", config.MAIN_BRANCH],
                ["git", "pull", "--ff-only"]):
        res = gitcmd.git(*cmd[1:])
        if res.returncode != 0:
            store.journal(conn, task_id, "orchestrator", "merge FAILED",
                          res.stderr.strip()[:500])
            sys.exit(f"merge упал на {' '.join(cmd)}:\n{res.stderr}")
    merge_res = gitcmd.git("merge", "--no-ff", branch, "-m",
                           f"{task_id}: merge {branch}")
    if merge_res.returncode != 0:
        _handle_merge_conflict(conn, task_id, state, branch, merge_res)
        return
    # sha КОММИТА МЕРЖА — сразу после успешного merge, ДО любых
    # последующих служебных коммитов (карты, RETRO): адрес артефактов
    # RETRO (SPEC T043, требование 8) обязан указывать именно на этот
    # коммит, а не на более поздний, который сдвинул бы HEAD дальше.
    merge_sha = gitcmd.head_sha()
    # Карта кодовой базы (SPEC T042): после merge, до push; провал
    # шага карты не отменяет merge (требование 5) — push ниже
    # выполняется независимо от исхода `_regenerate_and_commit_map`.
    _regenerate_and_commit_map(conn, task_id)
    # Дайджест задачи в main (SPEC T043): после карты, до push, тем же
    # принципом некритичности — провал не отменяет переход.
    _generate_and_commit_retro(conn, task_id, merge_sha)
    push = gitcmd.git("push")
    if push.returncode != 0:
        store.journal(conn, task_id, "orchestrator", "merge FAILED",
                      push.stderr.strip()[:500])
        sys.exit(f"merge упал на git push:\n{push.stderr}")
    store.set_state(conn, task_id, "done", "orchestrator",
                    expected_state=state, detail=f"смержено: {branch}")
    # Worktree задачи отслужил (SPEC T045, требование 5, AC-6):
    # смержено, дальше агентным шагам там делать нечего.
    note = workspace.remove(task_id)
    store.journal(conn, task_id, "orchestrator", "worktree убран", note)
    # Ветка задачи — следом за worktree (tasks/T073/SPEC.md, требование 2):
    # `-d` откажет, пока ветку держит worktree, поэтому порядок обязателен.
    branch_note = cleanup.drop_merged_task_branch(branch)
    store.journal(conn, task_id, "orchestrator", "ветка убрана", branch_note)


def cmd_approve(task_id: str, sha: str | None = None,
               session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой (SPEC T044, требование 2)."""
    conn = store.db()
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_approve(conn, task_id, sha, sid))


def _cmd_approve(conn, task_id: str, sha: str | None, sid: str) -> None:
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
        # путь через диск, не тронутый T031. Чтение — общий узел
        # `_read_branch_text_or_refuse` (T047, SPEC T071): узел сам
        # журналирует и печатает именованный отказ, дублировать его текст
        # отдельным `sys.exit` не нужно — `return` останавливает попытку
        # approve без смены состояния тем же способом, что и остальные
        # вызовы узла в `_cmd_advance`.
        branch = t["branch"]
        if gitcmd.on_foreign_branch(branch):
            spec_text = _read_branch_text_or_refuse(conn, task_id, branch,
                                                     "SPEC.md")
            if spec_text is None:
                return
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
            store.set_state(conn, task_id, "in_dev", "operator",
                            expected_state=state, detail=detail)
            print(f"  дальше: artel.py run {task_id}  (запуск разработчика)")
        else:
            store.set_state(conn, task_id, "tests_writing", "operator",
                            expected_state=state,
                            detail="гейт SPEC пройден — приёмочные тесты до кода")
            print(f"  дальше: artel.py run {task_id}  (запуск test_author)")
    elif state == "acceptance":
        # Сверка свежести ветки до гейта (SPEC T051, требования 1, 4):
        # тот же узел, что и на входе в review — approve не выносит на
        # merge_gate срез, который мог устареть, пока задача ждала приёмки.
        if _pull_main_or_escalate(conn, task_id, t, state) == "escalated":
            return
        store.set_state(conn, task_id, "merge_gate", "operator",
                        expected_state=state, detail="приёмка пройдена")
        print(f"  дальше: artel.py approve {task_id}  (выполнит merge)")
    elif state == "merge_gate":
        # Мьютекс merge-окна (SPEC T053, требования 1-3): один держатель
        # на весь пульт, не на задачу — вторая сессия, вызвавшая approve
        # из merge_gate, пока мьютекс занят, получает немедленный
        # именованный отказ (`sys.exit`, тем же стилем, что и отказ lease
        # выше) вместо ожидания. `merge_lock.run_window` снимает мьютекс
        # при ЛЮБОМ исходе тела окна, включая `sys.exit` внутри него
        # (требование 3) — общая точка обвязки (SPEC T057, требование 2).
        merge_lock.run_window(
            conn, task_id, sid,
            lambda: _cmd_approve_merge_gate(conn, task_id, state, t))
    elif state == "escalated":
        # Ответ Оператора (SPEC T075, AC-3): эскалация со структурированным
        # вопросом роли (QUESTIONS.md/spec_writing, `AC-n: escalate`/
        # tests_writing, REVIEW.md `status: escalate`/review) зафиксировала
        # `answer_baseline` — число ANSWER-*.md на момент эскалации — в
        # том же месте кода, что и сам факт эскалации (не позже,
        # содержательным разбором артефактов здесь: `escalated_from`
        # неоднозначен между классами, докстрин AC-5 приёмочных тестов).
        # `None` — эскалация класса «лимит»/инцидент, ответа не требует,
        # как и до этой задачи.
        baseline = t["answer_baseline"]
        if baseline is not None:
            tdir = config.TASKS / task_id
            count = _answer_file_count(t, tdir)
            if count is None or count <= baseline:
                expected = f"tasks/{task_id}/ANSWER-{baseline + 1}.md"
                detail = (f"approve отклонён: не хватает {expected} — "
                          f"ответь Оператором (artel.py answer {task_id} "
                          f"<файл-с-ответом>) перед возвратом из эскалации")
                store.journal(conn, task_id, "fsm",
                              "approve отклонён: нет ANSWER", detail)
                print(f"[{task_id}] {detail}")
                return
        # Куда возвращать — знает только тот, кто эскалировал: провал агента
        # (cmd_run) пишет в escalated_from состояние своего шага, потому что
        # чинить надо этот шаг, а не начинать разработку заново. Эскалации по
        # вердикту ревьювера и по исчерпанным лимитам его не пишут и, как
        # раньше, уходят в in_dev: там работа и продолжается.
        back = t["escalated_from"] or "in_dev"
        store.update_task(conn, task_id, escalated_from=None, answer_baseline=None)
        store.set_state(conn, task_id, back, "operator",
                        expected_state=state, detail="эскалация разрешена, продолжаем")
        print(f"  дальше: artel.py run {task_id}")
    else:
        print(f"[{task_id}] в состоянии {state} нечего подтверждать")


def cmd_reject(task_id: str, reason: str, session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой (SPEC T044, требование 2)."""
    conn = store.db()
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_reject(conn, task_id, reason))


def _cmd_reject(conn, task_id: str, reason: str) -> None:
    t = store.get_task(conn, task_id)
    state = t["state"]
    if state == "merge_gate":
        # Возврат из merge_gate (SPEC T052, требование 1, AC-1): один
        # переход в in_dev с причиной Оператора в журнале — не гейт
        # приёмки, accept_rejects её лимитом не считает (AC-7: счётчики
        # итераций других циклов возвратом из merge_gate не трогаются).
        store.set_state(conn, task_id, "in_dev", "operator",
                        expected_state=state,
                        detail=f"возврат из merge_gate: {reason}")
        return
    if state != "acceptance":
        sys.exit(f"[{task_id}] reject применим только в acceptance или "
                 f"merge_gate (сейчас {state})")
    rejects = t["accept_rejects"] + 1
    if rejects > config.LIMIT_ACCEPT_REJECTS:
        store.set_state(conn, task_id, "escalated", "fsm",
                        expected_state=state,
                        detail=f"лимит отказов приёмки исчерпан: {reason}")
    else:
        store.update_task(conn, task_id, accept_rejects=rejects)
        store.set_state(conn, task_id, "in_dev", "operator",
                        expected_state=state,
                        detail=f"приёмка отклонена: {reason}")
