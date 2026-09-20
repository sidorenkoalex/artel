"""Гейт применимости приложений PLAN на выходе `in_dev` (SPEC
01M2YSHDKWFJN3XSJ618Z74FNF, требование 2) — по образцу соседнего
`zones.py`: `GateRefusal`/`_run_gates` из `_base.py`, сохранённая
публичная обёртка `_plan_appendix_gate_refuses`, реэкспорт в
`orchestrator/fsm_advance.py`.

До этой задачи приложения PLAN никто не разбирал: неприменимый дифф
(хунк без совпадающего диапазона, инцидент 11.09 — `git apply --check`
отвечает «patch with only garbage») доезжал до мержа, где применять его
было некому. Гейт переносит проверку ДО ревью: чинит приложение та же
роль, которая его написала, пока задача ещё в разработке.
"""
import shutil
import tempfile
from pathlib import Path

from scripts import guard

from .. import config, gitcmd, store
from ._base import GateRefusal, _run_gates

# Действие журнала отказа (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF, требование
# 2/AC-5). Префикс «переход отклонён» общий — по нему
# `store.refusal_history` доносит отказ до брифа роли (AC-6). Отдельное
# имя нужно `orchestrator/auto.py::_pre_advance_step`: причину этого
# отказа устраняет сама роль (приложение живёт в её PLAN.md), это класс
# «роль ещё не закончила», а не «нужны руки Оператора».
PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION = (
    "переход отклонён: приложение PLAN неприменимо")


def _base_worktree(base: str) -> tuple[Path | None, str]:
    """Временный detached worktree на sha `base` — тот же приём, что
    `fsm_merge_gate._scratch_worktree` уже несёт для мержа.

    Нужен по существу: `git apply --check` сверяет патч с РАБОЧИМ
    ДЕРЕВОМ, а SPEC называет базой сравнения `gitcmd.diff_base(branch)` —
    коммит, который в рабочем дереве задачи не вычекан. Проверять патч
    против дерева самой ветки задачи было бы другой проверкой: ветка
    несёт правки роли, и приложение, применимое к её дереву, могло бы не
    примениться к main.

    (путь, "") — успех; (None, причина) — git не ответил."""
    scratch = Path(tempfile.mkdtemp(prefix="artel-plan-appendix-"))
    res = gitcmd.git("worktree", "add", "--detach", str(scratch), base)
    if res is None or res.returncode != 0:
        shutil.rmtree(scratch, ignore_errors=True)
        return None, (res.stderr.strip()[:300] if res is not None
                      else "git не ответил")
    return scratch, ""


def _drop_base_worktree(repo: Path) -> None:
    gitcmd.git("worktree", "remove", "--force", str(repo))
    shutil.rmtree(repo, ignore_errors=True)


def git_apply(repo: Path, appendix: guard.PlanAppendix,
              check: bool = False) -> str:
    """`git apply` приложения в дереве `repo` — `check=True` даёт `git
    apply --check` (проверка без правки дерева, гейт `in_dev`),
    `check=False` — настоящее применение (цикл мержа). Пустая строка —
    git согласился; иначе его ответ, и он едет в журнал: без него и роль,
    и Оператор читают «неприменимо» без единой подсказки, ЧТО не сошлось.

    Одна функция на оба вызова НАРОЧНО: гейт и мерж обязаны отдавать
    git'у байт-в-байт один и тот же патч одним и тем же способом — иначе
    «проверено на выходе in_dev» перестаёт что-либо гарантировать о
    мерже.

    Дифф отдаётся git'у файлом, а не stdin: `gitcmd.git` не умеет
    `input=`, а заводить ради этого второй способ звать git значило бы
    обойти единственную точку вызова пакета."""
    patch = Path(tempfile.mkdtemp(prefix="artel-plan-appendix-patch-"))
    patch_file = patch / "appendix.diff"
    try:
        patch_file.write_text(appendix.diff, encoding="utf-8")
        args = ["apply"] + (["--check"] if check else []) + [str(patch_file)]
        res = gitcmd.in_repo(repo, *args)
    finally:
        shutil.rmtree(patch, ignore_errors=True)
    if res is not None and res.returncode == 0:
        return ""
    if res is None:
        return "git не ответил"
    return (res.stderr.strip() or res.stdout.strip()
            or f"git apply вернул {res.returncode}")[:300]


def _inapplicable_refusal(task_id: str, detail: str) -> GateRefusal:
    hint = (f"почини unified-дифф приложения в PLAN.md (проверь себя "
            f"`git apply --check` на чистом дереве) и повтори "
            f"artel.py advance {task_id}")
    return GateRefusal(PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION, detail,
                       hint)


def _plan_appendix_gate(conn, task_id: str, t,
                        plan_text: str) -> GateRefusal | None:
    """Каждое приложение PLAN проходит `git apply --check` против дерева
    базы сравнения ветки (SPEC 01M2YSHDKWFJN3XSJ618Z74FNF, требование 2;
    AC-5/AC-7).

    PLAN без разделов «## Приложение» гейт не трогает вовсе — ни одного
    вызова git (AC-7): выход по пустому списку стоит ДО определения базы
    сравнения, иначе каждая задача артели платила бы за механику, которой
    не пользуется.

    Ошибки разбора требования 1 (блок без заголовка `diff --git`, путь вне
    `config.PROTECTED_PATHS`) — тот же отказ: пропустить такой блок молча
    значит потерять правку до самого мержа, где о ней уже некому узнать.

    Внешний (не self) target — гейт не проверяется, тем же доводом, что
    `_zones_gate`/`_capacity_gate`: `config.PROTECTED_PATHS` — файлы
    пульта, а `git` здесь ходит в `config.ROOT`, не в клон target'а.
    """
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return None
    appendices, errors = guard.plan_appendices(plan_text)
    if errors:
        return _inapplicable_refusal(task_id, "; ".join(errors))
    if not appendices:
        return None

    base = gitcmd.diff_base(t["branch"])
    if base is None:
        # Fail-closed (ADR-0002), тем же приёмом, что `_zones_gate`: базы
        # нет — проверить применимость нечем, и пропускать приложение
        # непроверенным нельзя.
        detail = (f"приложения PLAN: git не ответил на определение базы "
                  f"сравнения для ветки {t['branch']} — проверить "
                  f"применимость нечем")
        return _inapplicable_refusal(task_id, detail)
    repo, reason = _base_worktree(base)
    if repo is None:
        detail = (f"приложения PLAN: дерево базы сравнения {base} не "
                  f"развёрнуто — {reason}")
        return _inapplicable_refusal(task_id, detail)
    try:
        for appendix in appendices:
            answer = git_apply(repo, appendix, check=True)
            if answer:
                detail = (f"приложение PLAN {appendix.path} не применяется "
                          f"к базе сравнения {base}: {answer}")
                return _inapplicable_refusal(task_id, detail)
    finally:
        _drop_base_worktree(repo)
    return None


def _plan_appendix_gate_refuses(conn, task_id: str, t,
                                plan_text: str) -> bool:
    """Сохранённая публичная обёртка (та же форма, что у соседних гейтов
    `in_dev`) — один гейт `_plan_appendix_gate` через каркас
    `_run_gates`."""
    return _run_gates(conn, task_id,
                      [lambda: _plan_appendix_gate(conn, task_id, t, plan_text)])
