"""Ветка-источник `tasks/<id>/` живой задачи — общий резолвер (SPEC T094,
требование 10, реестр PLAN.md пункт 3: «Вопрос Оператору — требование
10», вариант А).

Self/догфуд (`config.DEFAULT_TARGET`): прежнее поведение T031/T047
байт-в-байт — кодовая ветка задачи, `foreign` по факту чекаута рабочей
копии пульта (`gitcmd.on_foreign_branch`). Любой другой target
(требование 8): `tasks/<id>/` живёт ТОЛЬКО в артефактной ветке пульта,
никогда в кодовой ветке целевого (та вообще не существует в `config.ROOT`
— это ветка ЧУЖОГО клона, `config.PROJECTS/<target>/workspace`) —
`foreign` поэтому всегда `True`.

Единственная точка входа, которую до этой задачи независимо
реализовывал только `orchestrator/brief.py::_artifact_source_branch`
(T094 итерация 1) — здесь вынесена в общий модуль, чтобы `fsm.py`/
`fsm_advance.py`/`acceptance.py` (T094 итерация 2) не заводили свою
копию того же решения «self или артефактная ветка» — предложение
самого PLAN.md T094 («не плодить копию логики в четырёх местах»).
"""
from . import config, gitcmd, store


def resolve(conn, task_id: str) -> tuple[str, bool]:
    """(ветка-источник `tasks/<id>/`, foreign)."""
    target = store.task_target(conn, task_id)
    if target != config.DEFAULT_TARGET:
        from . import artifact_branch
        return artifact_branch.branch_name(task_id), True
    branch = store.task_branch(conn, task_id)
    return branch, gitcmd.on_foreign_branch(branch)
