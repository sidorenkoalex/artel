"""Семейство гейта ёмкости diff снимка `_capacity_gate` (SPEC
01M2CYQR0357VAQFZ5VACJD9TD, требование 1) — перенесено дословно из
`orchestrator/fsm_advance.py`."""
from .. import config, gitcmd, repo_context, store
# Конкретные имена, не модуль целиком (SPEC 01M1GCN1FPSC1A6WK9WD1Q1V8X,
# требование 5, перенесено дословно вместе с `_capacity_gate`).
from ..review import EMPTY_DIFF_TEXT as _EMPTY_DIFF_TEXT
from ..review import git_diff_part as _review_git_diff_part
from ._base import GateRefusal, _run_gates

# Причина отказа гейта ёмкости — дословно (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X,
# AC-13): снимок задачи крупнее потолка `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES`
# не помещается ни в один прогон ревьювера — вердикт по такому объёму
# ненадёжен по построению, решение (разделить задачу или поднять потолок)
# — только Оператора (AC-14).
CAPACITY_GATE_REASON = "снимок не помещается в один контекст ревью — разделить задачу"


def _capacity_gate(conn, task_id: str, t) -> GateRefusal | None:
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

    `GateRefusal` — переход отклонён, отказ журналируется каркасом
    `_run_gates` (AC-13); гейт сам не эскалирует и не делает ничего
    автоматически (AC-14) — задача остаётся в `in_dev` до решения
    Оператора.

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

    Репозиторный контекст target'а (SPEC 01M1R5B33CC7E6BZK085XV3ZCX,
    требование 5, AC-10): для target ≠ self гейт больше не пропускается
    безусловно — база сравнения и diff считаются в клоне контекста
    target'а (`orchestrator/repo_context.py`), тем же способом, что и
    `review.git_diff_part` (AC-9). Контекст не читается (targets.yaml
    сломан/неизвестный target) — гейт деградирует на «пропустить», тем
    же приёмом, что `fsm._origin_main_source` (конфигурация не читается
    — сравнивать не с чем, не повод блокировать переход).

    `True` — переход отклонён (планка красная)."""
    ctx = repo_context.resolve(store.task_target(conn, task_id))
    if ctx is None:
        return None
    repo = repo_context.path_or_none(ctx)
    tasks_prefix = f"tasks/{task_id}/"
    # База сравнения — merge-base с origin/main или локальным main (tasks/
    # 01M1SG9T962WJJ31S282GWM0EN, AC-1/AC-3), не голый `config.MAIN_BRANCH`:
    # локальный пин по построению отстаёт от origin/main, которую ветка
    # задачи подтягивает, и раздувает снимок чужими коммитами.
    base = gitcmd.diff_base(t["branch"], repo=repo)
    action = "переход отклонён: гейт ёмкости diff"
    if base is None:
        detail = (f"гейт ёмкости: git не ответил на определение базы "
                 f"сравнения (merge-base с origin/{config.MAIN_BRANCH} "
                 f"либо локальным {config.MAIN_BRANCH}) для ветки "
                 f"{t['branch']} — сверка размера невозможна")
        hint = (f"разберись, почему git не отвечает на merge-base "
               f"для {t['branch']}, и повтори artel.py advance {task_id}")
        return GateRefusal(action, detail, hint)
    code_diff, _, reason = _review_git_diff_part(
        base, t["branch"], pathspec=(".", f":!{tasks_prefix}"), repo=repo)
    if reason:
        detail = (f"гейт ёмкости: git не ответил на diff снимка "
                 f"({base}...{t['branch']}) — сверка размера невозможна: "
                 f"{reason}")
        hint = (f"разберись, почему git не отвечает на diff "
               f"{base}...{t['branch']}, и повтори "
               f"artel.py advance {task_id}")
        return GateRefusal(action, detail, hint)
    code_size = (0 if code_diff == _EMPTY_DIFF_TEXT
                else len(code_diff.encode("utf-8")))
    if code_size <= config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES:
        return None
    artifacts_diff, _, artifacts_reason = _review_git_diff_part(
        base, t["branch"], pathspec=(tasks_prefix,), repo=repo)
    if artifacts_reason:
        artifacts_note = f"неизвестен (git не ответил: {artifacts_reason})"
    elif artifacts_diff == _EMPTY_DIFF_TEXT:
        artifacts_note = "0 байт (изменений нет)"
    else:
        artifacts_note = f"{len(artifacts_diff.encode('utf-8'))} байт"
    # Источник базы в сообщении (требование 4/AC-6) — Оператор видит, с чем
    # реально сравнивали, не только литерал diff-диапазона.
    source = gitcmd.diff_base_source(t["branch"], repo=repo)
    detail = (f"{CAPACITY_GATE_REASON} ({task_id} «{t['title']}», база "
             f"сравнения {base} от {source}): diff кода {code_size} байт "
             f"> потолка {config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES} байт "
             f"(исключённые артефакты {tasks_prefix}: {artifacts_note})")
    hint = "решение Оператора — разделить задачу или поднять потолок (ADR-0002)"
    return GateRefusal(action, detail, hint)


def _capacity_gate_refuses(conn, task_id: str, t, state: str) -> bool:
    """Сохранённая публичная обёртка (тесты `tests/test_capacity_gate.py`
    зовут её напрямую и читают журнал/stdout) — тот же единственный гейт
    `_capacity_gate`, применённый через каркас `_run_gates`."""
    return _run_gates(conn, task_id, [lambda: _capacity_gate(conn, task_id, t)])
