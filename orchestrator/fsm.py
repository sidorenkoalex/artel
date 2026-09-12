"""Переходы автомата: advance по артефактам, approve/reject Оператора.

Обработчики `cmd_advance` по состояниям — `orchestrator/fsm_advance.py`;
тело гейта `merge_gate` (конфликты, ожидание CI, сам merge) —
`orchestrator/fsm_merge_gate.py`; побочные эффекты после merge (карта
кодовой базы, RETRO) — `orchestrator/fsm_postmerge.py`; автогейт
acceptance — `orchestrator/fsm_autogate.py` (T091, декомпозиция
диспетчеров fsm/runner). Здесь остаются диспетчеры (`cmd_advance`,
`cmd_approve`, `cmd_reject`) и узлы, общие для нескольких состояний/
гейтов (сверка свежести ветки, чтения с ветки задачи, guard-отказ).
"""
import subprocess  # шов для tests/test_ac3_ac9_pull_message_fixtures.py:
                    # mock.patch.object(fsm.subprocess, "run", ...) —
                    # сам fsm.py вызовов subprocess не делает (они в pull.py)
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts import guard

from . import (artifact_source, artifacts, budget, config, fixation,
              github_adapter, gitcmd, lease, pull, repo_context, review,
              store, targets, yamlmini)
from .pull import _merge_conflict_note

# Буквальная строка «сигналов нет» (ANSWER-2, tasks/01M1KS8K9RXWHX2PW3ZKB0P903,
# AC-12) — снимок секции «Оценка объёма и деление» пустой/отсутствующей,
# не «неизвестно» (NULL остаётся зарезервирован за «снимок не удался/
# задача старше колонки», `report.py` различает эти два случая).
SPLIT_ASSESSMENT_NONE = "сигналов нет"

# Action журнала статуса CI, прочитанного в ветке `verifying` — общий
# текст с `orchestrator/auto.py` (SPEC T086, требование 1):
# `_verifying_poll_note` там ищет среди записей журнала ИМЕННО этот
# action, чтобы различить красный CI от «нет ответа»/«идёт», не опрашивая
# `ci.verifying_status` второй раз за ту же итерацию цикла.
VERIFYING_STATUS_ACTION = "статус CI ветки (verifying)"


def _verifying_elapsed_seconds(updated_at: str) -> float:
    """Секунды с момента входа в `verifying` (SPEC T086, требование 3):
    `updated_at` последнего `set_state -> verifying` пишется с точностью
    до микросекунд (`store.set_state`) — не секундным форматом `store.
    now()` (`liveness._age_seconds` парсит именно его для heartbeat).
    Второй формат разбирается тоже: строка `tasks.updated_at`, оставшаяся
    от завода задачи (`store.insert_task` пишет её через `now()`), не
    успевает смениться `set_state`-переходом там, где тест заводит
    `verifying` в обход самих переходов FSM прямой записью в БД.
    """
    try:
        entered = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S.%fZ")
    except ValueError:
        entered = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%SZ")
    return (datetime.now(timezone.utc) - entered.replace(
        tzinfo=timezone.utc)).total_seconds()


def _maybe_ensure_draft_mr(conn, task_id: str) -> None:
    """Draft MR — побочный эффект каждого входа в `in_dev` (SPEC T079,
    требование 1); идемпотентность несёт `github_adapter.ensure_draft_mr`
    сама (колонка `draft_mr_created`), так что этот узел зовётся
    одинаково с любой из точек входа в `in_dev`, не только с первой.
    """
    t = store.get_task(conn, task_id)
    github_adapter.ensure_draft_mr(conn, task_id, t)


# --- сверка свежести ветки до гейта (SPEC T051) ---------------------------

def _origin_main_source(target_name: str) -> tuple[str, str] | None:
    """(remote, ветка) main конкретного target'а (SPEC
    01M1NBWPKNBXP9ZXXQDJM7AXPJ, требование 5, AC-10, ANSWER-1): источник
    сверки/подтяжки берётся из конфигурации target задачи, не хардкожен
    как `origin` пульта. `None` — запись target'а не читается (файл или
    сама запись не годны): молчаливый откат на литерал `"origin"` был бы
    ОПАСНЕЕ обычной деградации «git не ответил» — сравнил/смержил бы
    задачу внешнего target против совсем другого репозитория (main
    пульта), не «ничего не сделал»; вызывающий код обязан деградировать
    так же, как при неответившем git (AC-8: расхождение/поломка
    конфигурации не имеет права двигать ни сверку, ни merge).

    Self-target (`config.DEFAULT_TARGET`) — прежний литерал `"origin"`
    (её пульт всегда несёт именно такой remote, ANSWER-1 «для self-target
    — origin пульта») БЕЗ обращения к `targets.yaml`: лёгкие песочницы
    этой сверки (`tests/test_branch_freshness_gate.py`, приёмочные тесты
    задачи) намеренно не заводят `config.TARGETS` для self-target
    сценария — чтение файла здесь безусловно сломало бы их (требование 4,
    AC-9). Любой другой target — `targets.target(name)["url"]` (адрес
    репозитория) как remote, её же `["base"]` как ветка: `targets.yaml`
    не несёт отдельного поля «имя remote» (протокол git одинаково
    принимает и имя настроенного remote, и голый URL вторым аргументом
    `git fetch`/`git merge`), а `["url"]` — уже существующее поле записи
    (ADR-0003 п.2), в точности «конфигурация target», которую требует
    AC-10.
    """
    if target_name == config.DEFAULT_TARGET:
        return "origin", config.MAIN_BRANCH
    try:
        entry = targets.target(target_name)
    except targets.TargetsError:
        return None
    return entry["url"], entry["base"]


def _origin_main_sha(target_name: str, *, repo: Path | None = None) -> str | None:
    """sha текущего HEAD main конкретного target'а на её удалённом
    источнике (SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-1/AC-2/AC-8/AC-10) —
    своя копия узла `orchestrator/fsm_merge_gate.py::_origin_main_sha`
    (тот же приём дублирования по модулю, что уже несёт `MAP_REL` в
    `orchestrator/pull.py`): `fsm_merge_gate` импортирует `fsm`, обратный
    импорт завёл бы цикл. `_origin_main_sha` там остаётся про main АРТЕЛИ
    конкретно (плотницкий merge Stage0 — только self-target/`operator`
    гейт), эта — про main ЗАДАННОГО target'а (`_origin_main_source`).

    Фетч и чтение результата идут через `gitcmd.fetch_ref_sha` (SPEC
    01M2ARQGY51B99YNP9PY806AN1) — временную приватную ссылку `refs/artel/
    fetch/<pid>-<uuid>`, БЕЗ обращения к общему `FETCH_HEAD` репозитория
    (до этой задачи здесь стоял голый `git fetch` + `rev-parse
    FETCH_HEAD` — общий на репозиторий/worktree файл, который
    параллельный шаг другой задачи мог переписать между двумя этими
    вызовами, инцидент 12.09 07:15Z). `git fetch` пишет только в
    объектную базу и саму приватную ссылку (удаляемую сразу после
    чтения), никогда в локальный `refs/heads/<MAIN_BRANCH>` — ни рабочее
    дерево, ни HEAD `config.ROOT`, ни зафиксированный там пин не задеты
    (AC-8). `None` — git не ответил на fetch или на `rev-parse`, либо
    конфигурация target'а не читается (`_origin_main_source`) — тот же
    вырожденный случай, что у остальных примитивов оркестратора: сверка
    ниже деградирует на «ничего не делать».

    `repo` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, требование 3, AC-4) — клон
    контекста target'а, когда target ≠ self: весь git-трафик
    `fetch_ref_sha` идёт ТАМ (`gitcmd.in_repo`), не в `config.ROOT` —
    ветки внешнего target в `config.ROOT` нет вовсе. Remote — литеральное
    имя `"origin"` (не `remote` из `_origin_main_source`, которая для
    внешнего target несёт адрес форджа, не настроенный в клоне git
    remote): клон внешнего target несёт свой `origin` по тому же
    соглашению, что и `config.ROOT` пульта (`orchestrator/repo_context.py`
    докстринг). `repo=None` (по умолчанию, self) — прежнее поведение
    байт-в-байт, включая `remote` из `_origin_main_source` (там уже
    литерал `"origin"` для self).
    """
    source = _origin_main_source(target_name)
    if source is None:
        return None
    remote, branch = source
    effective_remote = "origin" if repo is not None else remote
    sha, _ = gitcmd.fetch_ref_sha(effective_remote, branch, repo=repo)
    return sha or None


def _pull_main_or_escalate(conn, task_id: str, t, state: str) -> str:
    """Сверка свежести ветки задачи на входе в гейт (SPEC T051, требования
    1-7, 10; ADR-0006 п.2; переведена на origin — SPEC
    01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-1..AC-4/AC-8) и, начиная с T053
    требование 5, ВНУТРИ окна `merge_gate` под мьютексом merge — один и
    тот же узел для всех трёх точек сверки (`in_dev -> review`,
    `acceptance -> merge_gate`, `merge_gate -> done`).

    Вычисление исхода (сверка `base`/`behind` против origin, `git merge`,
    авторазрешение конфликта карты, детализация неразрешённого конфликта,
    WIP-чекпоинт, материализация и прогон приёмочной планки) — целиком
    `orchestrator/pull.py::evaluate` (роадмап §3, фаза R, R3): эта функция
    остаётся точкой входа с прежней сигнатурой/контрактом возврата,
    переводя исход `pull.evaluate` (`Fresh`/`Pulled`/`Conflict`/`Refused`)
    в прежние строки `"fresh"`/`"pulled"`/`"escalated"`/`"refused"` —
    записи журнала/эскалации для каждого исхода несёт сам `pull.py`.

    `_origin_main_source`/`_origin_main_sha` (сверка свежести против
    origin target'а задачи, не локального `config.MAIN_BRANCH` — см. их
    докстринги) и `_read_branch_text_or_refuse` (чтение SPEC.md с чужой
    ветки, общее с другими функциями этого модуля) передаются в
    `pull.evaluate` ПАРАМЕТРАМИ, не импортом `fsm` тем модулем: так
    `mock.patch.object(fsm, "_origin_main_sha", ...)` (существующие
    тесты, AC-5) продолжает долетать до реального `git merge` — патч
    меняет ИМЕННО то имя, которое эта функция передаёт дальше как
    значение, вычисленное в момент вызова.

    Возврат — один из четырёх исходов, контракт которых не меняется этой
    задачей (AC-2): `"escalated"`/`"refused"`/`"fresh"`/`"pulled"` — их
    семантика (когда состояние меняется, что означает каждый) описана в
    `orchestrator/pull.py` докстринге `evaluate`/классов исходов.

    `repo_path` (SPEC 01M1R5B33CC7E6BZK085XV3ZCX, требование 3, AC-4):
    клон контекста target'а задачи (`orchestrator/repo_context.py`) —
    `None` для self (прежний путь через `workspace.ensure`, worktree
    `config.ROOT`), путь `.artel/projects/<target>/workspace` для любого
    другого target (сравнение и merge подтяжки идут прямо там, без
    отдельного worktree — внешний target уже стоит на своей ветке задачи
    в этом клоне, ТЗ-2). `origin_main_sha` передаётся замыканием,
    связанным с ТЕМ ЖЕ `repo_path` — весь git-трафик `gitcmd.fetch_ref_sha`
    внутри него идёт в тот же клон, не в `config.ROOT`.
    """
    ctx = repo_context.resolve(t["target"] or config.DEFAULT_TARGET)
    repo_path = repo_context.path_or_none(ctx)
    outcome = pull.evaluate(
        conn, task_id, t, state,
        origin_main_source=_origin_main_source,
        origin_main_sha=lambda name: _origin_main_sha(name, repo=repo_path),
        read_branch_text_or_refuse=_read_branch_text_or_refuse,
        repo_path=repo_path)
    if isinstance(outcome, pull.Fresh):
        return "fresh"
    if isinstance(outcome, pull.Pulled):
        return "pulled"
    if isinstance(outcome, pull.Refused):
        return "refused"
    return "escalated"


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


def _snapshot_split_assessment(conn, task_id: str, t) -> None:
    """Заполняет `diff_bytes`/`split_assessment` на входе в `merge_gate`
    (tasks/01M1KS8K9RXWHX2PW3ZKB0P903, требование 6; ANSWER-1, ANSWER-2)
    — материал для калибровки порогов `artel report`, не условие
    перехода: сбой git по любой из двух колонок оставляет её NULL и НЕ
    отказывает переходу (в отличие от `fsm_advance._capacity_gate_
    refuses`, которая именно отказывает на том же diff).

    Diff — только self target, тем же доводом, что и `_capacity_gate_
    refuses`: `git diff` в `config.ROOT` не видит код внешнего target.
    Секция «Оценка объёма и деление» читается с АРТЕФАКТНОЙ ветки —
    `tasks/<id>/` живёт только там (A7, `artifact_source.resolve`),
    независимо от target.
    """
    if store.task_target(conn, task_id) == config.DEFAULT_TARGET:
        diff, _, reason = review.git_diff_part(config.MAIN_BRANCH, t["branch"])
        if not reason:
            store.update_task(conn, task_id, diff_bytes=len(diff.encode("utf-8")))

    branch, _ = artifact_source.resolve(conn, task_id)
    spec_text, _ = gitcmd.show(branch, f"tasks/{task_id}/SPEC.md")
    if spec_text is not None:
        body = guard.section_body(spec_text, "Оценка объёма и деление").strip()
        store.update_task(conn, task_id,
                          split_assessment=body or SPLIT_ASSESSMENT_NONE)


def _print_spec_gate_calibration_hint(conn, task_id: str, budget_usd: float,
                                      meta: dict, spec_text: str) -> None:
    """Печатает ориентир калибровки и действующий `budget_usd` рядом со
    строкой «дальше:» гейта SPEC и, при занижении больше чем на треть,
    предупреждение + запись в журнал (SPEC 01M1TQ11K4WJZD7ZE3MR0J4ZK4,
    требование 3, AC-9/AC-10). Не отказывает и не меняет потолок
    (AC-11) — только печатает и, при срабатывании, журналирует.
    """
    ac_count = len(guard.AC_ITEM.findall(
        guard.section_body(spec_text, "Критерии приёмки")))
    zone_files = budget.count_zone_paths(meta.get("zones"))
    orientir = budget.recommended_budget_usd(ac_count, zone_files)
    print(f"[{task_id}] калибровка: ориентир ~${orientir:.2f} "
         f"({ac_count} AC-n, {zone_files} файлов zones) — действующий "
         f"потолок ${budget_usd:.2f}")
    warning = budget.calibration_warning(budget_usd, orientir)
    if warning is not None:
        store.journal(conn, task_id, "fsm", "калибровка бюджета", warning)
        print(f"[{task_id}] ВНИМАНИЕ: {warning}")


def _answer_file_count(conn, task_id: str, tdir: Path) -> int | None:
    """Число `ANSWER-*.md` задачи — с ВЕТКИ-ИСТОЧНИКА `tasks/<id>/`
    (`artifact_source.resolve`, SPEC T031/T047/T094 требование 10, тот же
    приём, что и остальные чтения этого файла в модуле), если она чужая
    рабочей копии пульта, иначе с диска. `None` — git не ответил на чужой
    ветке (нельзя посчитать — не значит «ноль», вызывающий код решает,
    как трактовать).

    Считает файлы, не разбирает номер `n`: гейту возврата (`_cmd_approve`)
    достаточно знать, что число ANSWER-файлов ВЫРОСЛО относительно
    зафиксированного на эскалации снимка (`answer_baseline`), не какой
    именно номер у нового файла.
    """
    branch, foreign = artifact_source.resolve(conn, task_id)
    if foreign:
        paths = gitcmd.ls_tree_files(branch, f"tasks/{task_id}")
        if paths is None:
            return None
        return sum(1 for p in paths
                  if Path(p).name.startswith("ANSWER-")
                  and Path(p).name.endswith(".md"))
    return len(list(tdir.glob("ANSWER-*.md")))


def _answer_baseline_or_refuse(conn, task_id: str, tdir: Path) -> int | None:
    """Снимок числа ANSWER-*.md на момент эскалации — тем же приёмом
    отказа, что `_read_branch_text_or_refuse` (SPEC T031, T047): `None`
    от `_answer_file_count` — git не ответил на чужой ветке, а не «файлов
    ноль» — молчаливое схлопывание в `or 0` замаскировало бы именно тот
    класс сбоя, от которого рядом стоящий код (`q_paths is None` и
    остальные ветки этого модуля) отказывает громко (REVIEW T075
    итерация 1, замечание minor). Возврат `None` — отказ уже
    журналирован и напечатан, переход обязан не эскалировать в этот
    момент, а не эскалировать с недостоверным `baseline=0`."""
    count = _answer_file_count(conn, task_id, tdir)
    if count is None:
        branch, _ = artifact_source.resolve(conn, task_id)
        detail = (f"дерево не на ветке задачи {branch} — число "
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

    `errors` несёт ошибки трассируемости AC (T023), ошибки маркера
    красноты (`guard.redness_marker_errors_from_files`/`scan_redness_markers`,
    SPEC T064) и ошибки образца формата идентификатора задачи
    (`guard.id_format_sample_errors`/`scan_id_format_samples`, SPEC
    01M1H186VEVG6NF40YKH1338MD) — единственное место, где все три проверки
    подключены к выходу именно из `tests_writing`: задача, чьё состояние
    это состояние уже прошло, сюда больше не попадает (обратная
    совместимость T064, требование 4, — структурно, через
    однонаправленность FSM).
    """
    if not gitcmd.on_foreign_branch(branch):
        tested, markers = guard.scan_acceptance_tests(tdir)
        errors = guard.acceptance_traceability_errors(tdir)
        errors = errors + guard.scan_redness_markers(tdir)
        errors = errors + guard.scan_id_format_samples(tdir)
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
    id_format_files: list[tuple[str, str]] = []
    for p in paths:
        if not p.endswith(".py"):
            continue
        text, _ = gitcmd.show(branch, p)
        if text is None:
            continue
        sources.append(text)
        id_format_files.append((p, text))
        if Path(p).name.startswith("test_"):
            redness_files.append((p, text))
    meta = yamlmini.frontmatter(spec_text) or {}
    tested, markers = guard.scan_ac_content(sources)
    errors = guard.traceability_errors_from_content(spec_text, meta, tested,
                                                     markers)
    errors = errors + guard.redness_marker_errors_from_files(redness_files)
    errors = errors + guard.id_format_sample_errors(id_format_files)
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

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease/путей на диске — иначе `advance <префикс>` строил `tdir` из
    несуществующего каталога и ложно отказывал переход (REVIEW T094
    итерация 1, замечание 1: живой репро — `cmd_advance` с уникальным
    префиксом печатал «PLAN.md не ready» на задаче с реально готовым
    PLAN.md).
    """
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
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

    # Обработчик на состояние (SPEC T091): каждое состояние — своя
    # функция в orchestrator/fsm_advance.py, отсюда только выбор.
    # Импорт внутри функции, не на уровне модуля (тем же приёмом, что
    # `runner._cmd_run` уже применяет к `doctor`, ADR-0003 3ж): fsm.py
    # несёт узлы, общие для advance/approve/merge_gate, поэтому не
    # должен статически зависеть от модулей, которые сами зависят от
    # него.
    from . import fsm_advance
    handler = {
        "spec_writing": fsm_advance.spec_writing,
        "review": fsm_advance.review,
        "verifying": fsm_advance.verifying,
        "tests_writing": fsm_advance.tests_writing,
        "in_dev": fsm_advance.in_dev,
    }.get(state)
    if handler is None:
        print(f"[{task_id}] состояние {state} двигается через approve/reject/run")
        return False
    return handler(conn, task_id, t, tdir, target, state)


# Состояния, на входе в approve которых требуется подтверждённый sha
# (SPEC T021, требование 4): именно те 4 ветки, которые ниже что-то
# подтверждают, а не просто отвечают «нечего подтверждать».
APPROVE_NEEDS_SHA = ("spec_gate", "acceptance", "merge_gate", "escalated")

# Минимальная длина префикса sha, принимаемого `approve` вместо полного
# значения (SPEC «approve: полный sha в подсказках», требование 2; SPEC
# «Не входит» — фиксированная величина, не предмет настройки в этой
# задаче). Тот же порядок приёма, что и уникальный префикс id задач
# (T094, `store.resolve_task_id`), но сверяется с ОДНИМ эталоном —
# зафиксированным sha ЭТОЙ задачи, не поиском среди множества
# кандидатов: «уникальный» здесь про отсечение случайных опечаток
# короткой длиной, не про отсутствие коллизий.
APPROVE_SHA_PREFIX_MIN = 8


def confirm_fixation(conn, task_id: str, sha: str | None) -> bool:
    """True — approve может продолжить; False — отклонено (не запрос sha).

    Живьём пересчитывает состояние через `fixation.read()`, а не читает
    `tasks.fixed_sha` напрямую для сравнения с САМИМ СОБОЙ — но именно
    `tasks.fixed_sha` служит эталоном сверки на ветке `sha is None`
    (SPEC 01M1SHJX22EMEP4AJ9FFJJ09DC, требование 1): approve обязан
    сверяться с ТЕКУЩИМ состоянием (ADR-0003 п.15, «сверка на каждом
    следующем гейте... = сравнение sha + чистота рабочей копии»), а не
    заново набранным Оператором значением. `read()`, не `fix()`
    (REVIEW.md T021, замечание 1 итерации 2): approve — точка ПРОВЕРКИ,
    не фиксации, и не имеет права коммитить незакоммиченный WIP чужой
    задачи того же target как побочный эффект сравнения — легитимный
    коммит перехода случится позже, в `store.set_state` → `fix()`, если
    сверка сошлась.

    Фиксации нет (`current == ""` — git не ответил, песочница без
    репозитория) — сверять не с чем: approve ведёт себя как до T021
    (требование 3, критерий 3).

    `sha is None` (SPEC 01M1SHJX22EMEP4AJ9FFJJ09DC, требования 1-2,
    AC-1..AC-3): живой `current`/`clean` сверяются с `tasks.fixed_sha` —
    совпало и чисто → `True` без печати запроса sha (переход, который
    сделает вызывающий код, сам зафиксирует и зажурналирует этот sha
    через `store.set_state` → `record_fixation`, отдельного журнала
    здесь для этого не нужно); разошлось или грязно → именованный отказ
    с ОБОИМИ sha (живым и зафиксированным) — мягкий `return False`, НЕ
    `sys.exit`: единственный существующий (ADR-0002) тест на эту ветку,
    `tests/test_git_fixation.py::ExternalApproveDoesNotCommitOthersWorkInProgressTest.
    test_approve_without_sha_does_not_commit_another_tasks_wip`, ждёт
    именно мягкого возврата, не исключения.

    `sha` передан явно — прежняя семантика T021 байт-в-байт (SPEC
    требование 2, AC-4): сверяется с ЖИВЫМ `current` (не с
    `tasks.fixed_sha`), отказ — `sys.exit`, тем же стилем, что и отказ
    merge по красному CI ниже. Короче `APPROVE_SHA_PREFIX_MIN` —
    именованный отказ про минимальную длину, ДО сравнения (SPEC T021
    требование 3, AC-4): короткий отрезок совпал бы с зафиксированным
    почти всегда случайно, отличить опечатку от намеренного префикса
    нечем. От `APPROVE_SHA_PREFIX_MIN` и длиннее — `current.startswith
    (sha)` принимает как полный sha (совпадает с собой целиком), так и
    любой его префикс той же длины (SPEC T021 требование 2, AC-2); не
    префикс — прежний отказ «не совпадает» с печатью зафиксированного
    sha (SPEC T021 требование 3, AC-3), байт-в-байт как до этой задачи.
    """
    target = store.task_target(conn, task_id)
    current, clean = fixation.read(task_id, target)
    if not current:
        return True
    if sha is None:
        fixed = store.get_task(conn, task_id)["fixed_sha"] or ""
        if fixed and current == fixed and clean:
            print(f"[{task_id}] approve: живой sha совпадает с "
                  f"зафиксированным {current} — переход подтверждён "
                  f"механикой")
            return True
        reason = (f"живой sha {current} расходится с зафиксированным "
                  f"{fixed or '(нет)'}" if current != fixed else
                  f"грязная копия артефактов при sha {current}")
        store.journal(conn, task_id, "operator", "approve отклонён", reason)
        print(f"[{task_id}] approve отклонён: {reason}")
        # Живой sha (`current`), не зафиксированный (`fixed`, REVIEW.md
        # 01M1SHJX22EMEP4AJ9FFJJ09DC итерация 1, R1-F2): явный путь ниже
        # (`matches = current.startswith(sha)`) сравнивает переданный sha
        # с ЖИВЫМ, значит и подсказанная команда обязана называть живой
        # sha — подсказка `fixed` детерминированно проваливалась бы
        # повторно на той же сверке. В ветке «грязная копия» current ==
        # fixed, подстановка не меняется.
        print(f"  перепроверь артефакты и повтори: artel.py approve "
              f"{task_id} {current}")
        return False
    if len(sha) < APPROVE_SHA_PREFIX_MIN:
        reason = (f"sha {sha!r} короче минимальной длины "
                  f"{APPROVE_SHA_PREFIX_MIN} символов — approve принимает "
                  f"полный sha или его уникальный префикс от "
                  f"{APPROVE_SHA_PREFIX_MIN} символов")
        store.journal(conn, task_id, "operator", "approve отклонён", reason)
        sys.exit(f"[{task_id}] approve отклонён: {reason}")
    matches = current.startswith(sha)
    if not matches or not clean:
        reason = (f"sha {sha} не совпадает с зафиксированным {current}"
                  if not matches else
                  f"грязная копия артефактов при sha {current}")
        store.journal(conn, task_id, "operator", "approve отклонён", reason)
        sys.exit(f"[{task_id}] approve отклонён: {reason}")
    return True


def cmd_approve(task_id: str, sha: str | None = None,
               session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой (SPEC T044, требование 2).

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease/CAS (REVIEW T094 итерация 1, замечание 1)."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_approve(conn, task_id, sha, sid))


def _spawn_division_subtasks(conn, task_id: str, t, state: str,
                             subsections: list) -> None:
    """Заводит по одной подзадаче на каждый подраздел секции «## Деление»
    (01M1SHJZCE0Y4DXAAWQ2W585A7, требования 2-3, AC-5/AC-6/AC-11) и
    переводит родителя в `killed` — единственное терминальное
    непродолжаемое состояние FSM, подходящее по смыслу «поделена»
    (`orchestrator/config.py::AUTO_STOP`, требование 2 SPEC).

    Ленивый импорт `catalog` — тем же приёмом, что `_approve_merge_gate`
    выше зовёт `fsm_merge_gate`: `catalog.py` не импортирует `fsm.py` на
    уровне модуля, цикла нет, но локальный импорт держит связку явной
    только там, где она нужна.
    """
    from . import catalog
    new_ids = [catalog.spawn_subtask(task_id, t["title"], sub["title"],
                                     sub["body_raw"], target=t["target"])
              for sub in subsections]
    ids_text = ", ".join(new_ids)
    store.set_state(conn, task_id, "killed", "operator",
                    expected_state=state, detail=f"поделена на: {ids_text}")


def _approve_spec_gate(conn, task_id: str, t, state: str, sid: str) -> None:
    # tests_writing до кода (SPEC T023, требование 1): пропускается
    # только явным skip_tests либо SPEC версии ниже 2 (без AC-разметки,
    # весь беклог T001–T022 — требование 7); иначе тесты пишутся
    # раньше, чем задачу увидит разработчик.
    #
    # Рабочее дерево точно на чужой ветке-источнике `tasks/<id>/`
    # (SPEC T031, AC-1; T094 требование 10 — ветка-источник теперь
    # артефактная ветка пульта для внешнего target, `artifact_source.
    # resolve`) — SPEC.md читается с НЕЁ (не молчаливый дефолт
    # «schema_version 1 без AC-разметки», журнал T030 ~17:35
    # 25.08.2026); иначе прежний путь через диск, не тронутый T031.
    # Чтение — общий узел `_read_branch_text_or_refuse` (T047, SPEC
    # T071): узел сам журналирует и печатает именованный отказ,
    # дублировать его текст отдельным `sys.exit` не нужно — `return`
    # останавливает попытку approve без смены состояния тем же
    # способом, что и остальные вызовы узла в `_cmd_advance`.
    branch, foreign = artifact_source.resolve(conn, task_id)
    if foreign:
        spec_text = _read_branch_text_or_refuse(conn, task_id, branch,
                                                 "SPEC.md")
        if spec_text is None:
            return
        meta = yamlmini.frontmatter(spec_text) or {}
    else:
        meta = artifacts.frontmatter(config.TASKS / task_id / "SPEC.md")
        spec_text = ""
    # Значение zones (01M1NKVPD2A79PQ6K0JVV1B2Q1, AC-3) сохраняется тем
    # же моментом входа approve на spec_gate, что и budget/split_
    # assessment рядом — meta уже прочитана выше, поле отсутствует у
    # SPEC старых версий (`meta.get` даёт None, колонка тогда NULL).
    store.update_task(conn, task_id, zones=meta.get("zones"))
    # Перечитывание budget_usd на гейте SPEC (SPEC
    # 01M1SHJX22EMEP4AJ9FFJJ09DC, требования 4-5): Оператор мог поправить
    # SPEC прямо на гейте (сузить рамку и т.п.) уже ПОСЛЕ того, как
    # `spec_writing -> spec_gate` (`fsm_advance.spec_writing`) применил
    # значение, действовавшее на тот момент — approve обязан перечитать
    # `meta` (уже прочитана выше той же веткой foreign/диск) тем же
    # `apply_spec_budget`. Идемпотентность (потолок Оператора не
    # перебивается; совпадающее значение не журналируется дважды) уже
    # целиком несёт сама функция через `budget_source` — второй вызов
    # той же функции с той же `t` не требует отдельного кода.
    budget.apply_spec_budget(conn, t, meta)
    _print_spec_gate_calibration_hint(conn, task_id, t["budget_usd"] or 0.0,
                                      meta, spec_text)
    # Заявка на деление (01M1SHJZCE0Y4DXAAWQ2W585A7, требования 2-3):
    # секция «## Деление» уже провалидирована guard'ом на переходе
    # `spec_writing -> spec_gate` (`fsm_advance.spec_writing`) — здесь её
    # достаточно распознать, не проверять заново. Ветвь срабатывает
    # ТОЛЬКО из состояния spec_gate (мы уже внутри этого обработчика) —
    # повторный approve того же родителя приходит уже из killed и здесь
    # не оказывается вовсе (диспетчер `_cmd_approve` ниже).
    subsections = guard.parse_division_subsections(spec_text)
    if subsections:
        _spawn_division_subtasks(conn, task_id, t, state, subsections)
        return
    skip_reason = meta.get("skip_tests")
    if skip_reason or not guard.requires_ac_markup(meta):
        detail = (f"тесты пропущены (skip_tests): {skip_reason}"
                  if skip_reason else
                  f"SPEC schema_version "
                  f"{meta.get('schema_version', 1)} — без AC-разметки, "
                  f"tests_writing недоступна")
        store.set_state(conn, task_id, "in_dev", "operator",
                        expected_state=state, detail=detail)
        _maybe_ensure_draft_mr(conn, task_id)
        print(f"  дальше: artel.py run {task_id}  (запуск разработчика)")
    else:
        store.set_state(conn, task_id, "tests_writing", "operator",
                        expected_state=state,
                        detail="гейт SPEC пройден — приёмочные тесты до кода")
        print(f"  дальше: artel.py run {task_id}  (запуск test_author)")


def _approve_acceptance(conn, task_id: str, t, state: str, sid: str) -> None:
    # Сверка свежести ветки до гейта (SPEC T051, требования 1, 4):
    # тот же узел, что и на входе в review — approve не выносит на
    # merge_gate срез, который мог устареть, пока задача ждала приёмки.
    if _pull_main_or_escalate(conn, task_id, t, state) in (
            "escalated", "refused"):
        return
    store.set_state(conn, task_id, "merge_gate", "operator",
                    expected_state=state, detail="приёмка пройдена")
    # Снимок объёма (tasks/01M1KS8K9RXWHX2PW3ZKB0P903, требование 6,
    # ANSWER-1/ANSWER-2): побочный эффект входа в merge_gate, не
    # условие перехода — сбой git здесь не держит гейт.
    _snapshot_split_assessment(conn, task_id, t)
    # Undraft Draft MR (SPEC T079, требование 2, AC-2): побочный
    # эффект входа в merge_gate, не условие перехода — отказ адаптера
    # не держит гейт (github_adapter.undraft_mr сама не бросает).
    github_adapter.undraft_mr(conn, task_id, store.get_task(conn, task_id))
    # Sha, зафиксированный ЭТИМ переходом (SPEC «approve: полный sha в
    # подсказках», требование 1) — готовая к копированию команда,
    # вместо голого `<id>`, которое Оператору иначе пришлось бы
    # достраивать по памяти (инцидент 02.09, мерж T101).
    sha_hint = fixation.approve_sha_hint(task_id, store.task_target(conn, task_id))
    print(f"  дальше: artel.py approve {task_id}{sha_hint}  (выполнит merge)")


def _approve_merge_gate(conn, task_id: str, t, state: str, sid: str) -> None:
    # Мьютекс merge-окна (SPEC T053, требования 1-3): один держатель
    # на весь пульт, не на задачу — вторая сессия, вызвавшая approve
    # из merge_gate, пока мьютекс занят, получает немедленный
    # именованный отказ (`sys.exit`, тем же стилем, что и отказ lease
    # выше) вместо ожидания. С SPEC T087 мьютекс не удерживается на
    # время ожидания CI после подтяжки (требование 2) — тело гейта и
    # его внешний цикл — orchestrator/fsm_merge_gate.py (SPEC T091):
    # берёт/отпускает мьютекс сама вокруг каждого захода в тело гейта,
    # а не единым `merge_lock.run_window` на весь вызов.
    from . import fsm_merge_gate
    fsm_merge_gate._cmd_approve_merge_gate_cycle(conn, task_id, sid, t,
                                                  state)


def _approve_escalated(conn, task_id: str, t, state: str, sid: str) -> None:
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
        count = _answer_file_count(conn, task_id, tdir)
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
    if back == "in_dev":
        _maybe_ensure_draft_mr(conn, task_id)
    print(f"  дальше: artel.py run {task_id}")


def _cmd_approve(conn, task_id: str, sha: str | None, sid: str) -> None:
    t = store.get_task(conn, task_id)
    state = t["state"]
    if state in APPROVE_NEEDS_SHA and not confirm_fixation(conn, task_id, sha):
        return
    # Таблица «состояние -> обработчик» (SPEC требование 3): каждый
    # обработчик — прежнее тело своей ветки `if state == ...` (переход
    # без изменения поведения); ветка «иначе» ниже несёт прежний текст
    # отказа. Тем же приёмом, что и `_cmd_advance` (SPEC T091).
    handler = {
        "spec_gate": _approve_spec_gate,
        "acceptance": _approve_acceptance,
        "merge_gate": _approve_merge_gate,
        "escalated": _approve_escalated,
    }.get(state)
    if handler is None:
        print(f"[{task_id}] в состоянии {state} нечего подтверждать")
        return
    handler(conn, task_id, t, state, sid)


def cmd_reject(task_id: str, reason: str, session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой (SPEC T044, требование 2).

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease/CAS — иначе `reject` с префиксом на `merge_gate` кидал
    необработанный `CasConflict` сквозь `lease.run_locked` (REVIEW T094
    итерация 1, замечание 1)."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
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
        _maybe_ensure_draft_mr(conn, task_id)
        return
    if state == "verifying":
        # Возврат из verifying (SPEC T079, требование 8, AC-10): тем же
        # приёмом, каким T052 расширила reject на merge_gate — один
        # переход в in_dev, без роста review_iters/accept_rejects.
        # Единственный ручной выход из verifying при красном CI —
        # симметрия инварианта 19 (требование 7): красный CI сам по себе
        # задачу не возвращает, только reject Оператора или потолок
        # ожидания (AC-9).
        store.set_state(conn, task_id, "in_dev", "operator",
                        expected_state=state,
                        detail=f"возврат из verifying: {reason}")
        _maybe_ensure_draft_mr(conn, task_id)
        return
    if state != "acceptance":
        sys.exit(f"[{task_id}] reject применим только в acceptance, "
                 f"merge_gate или verifying (сейчас {state})")
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
        _maybe_ensure_draft_mr(conn, task_id)
