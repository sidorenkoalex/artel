"""Общий тестовый шов T050: имитация конкурентного перехода состояния
между чтением, на основании которого вызыватель `set_state` принял
решение, и самим CAS-вызовом (используется AC-5, AC-6, AC-8).

Патчит `store.get_task`: ПЕРВЫЙ вызов для целевой задачи возвращает
настоящую строку как обычно, но перед возвратом переводит `tasks.state`
в `decoy_state` — как будто между чтением и записью успела вклиниться
другая сессия. Правильный вызыватель обязан использовать значение,
прочитанное этим самым (первым) вызовом, как `expected_state` следующего
`set_state` (SPEC требование 5) — тогда CAS увидит расхождение с
`decoy_state` и, в зависимости от роли, либо корректно откажет
(advance/approve/reject/merge — требование 4), либо перечитает и
повторит (kill — требование 6). Вызыватель, который читает состояние ЕЩЁ
РАЗ прямо перед CAS в обход этого правила, увидит `decoy_state` как
«текущее» и применит свой переход поверх него незаметно для теста.
"""
from contextlib import contextmanager
from unittest import mock

from orchestrator import store


@contextmanager
def single_shot_state_race(task_id: str, decoy_state: str):
    """Мутирует `tasks.state` задачи `task_id` в `decoy_state` РОВНО ОДИН
    раз — сразу после первого чтения строки через `store.get_task` внутри
    блока `with`. Последующие вызовы `store.get_task` ничего не мутируют
    и просто возвращают текущую (уже изменённую) строку."""
    real_get_task = store.get_task
    seen = {"n": 0}

    def patched(conn, tid):
        row = real_get_task(conn, tid)
        if tid == task_id:
            seen["n"] += 1
            if seen["n"] == 1:
                conn.execute("UPDATE tasks SET state=? WHERE id=?",
                            (decoy_state, tid))
                conn.commit()
        return row

    with mock.patch.object(store, "get_task", patched):
        yield
