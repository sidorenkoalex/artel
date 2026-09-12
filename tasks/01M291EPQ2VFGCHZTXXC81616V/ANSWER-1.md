---
task: 01M291EPQ2VFGCHZTXXC81616V
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

## Ответы

1. Конфликт подтяжки main по `orchestrator/fsm_merge_gate.py`,
   `orchestrator/catalog.py` и `docs/codebase-map.md` — следствие базы
   ветки: она заведена от локального пина 699fa124, в котором ещё нет
   части 1 (01M291EJMA, мьютекс merge-окна на весь цикл `approve`,
   смержена в main 23:05Z 11.09) и поделённого родителя (01M29284PT,
   добавки `[поделена: …]`/`[часть N/M …]` в `cmd_status`, смержен
   06:14Z 12.09). Твой код очереди написан поверх старого
   `_cmd_approve_merge_gate_cycle`. Разрешение: `git merge origin/main`
   в worktree задачи и содержательное слияние, не выбор одной стороны:
   - `fsm_merge_gate.py`: поведение части 1 сохраняется целиком —
     мьютекс берётся один раз на весь цикл (включая ожидание CI) и
     снимается безусловно в `finally`; очередь `merge_queue` встраивается
     ПЕРЕД взятием мьютекса (вход в очередь, ожидание головы,
     затем `merge_lock.acquire`), потолок CI отсчитывается от первого
     пуша, как в SPEC требование 4. Сверься с текущим
     `orchestrator/merge_lock.py` и тестами
     `tests/test_merge_gate_ci_wait.py` из main — они должны остаться
     зелёными без правок (SPEC AC-10).
   - `catalog.py`: обе добавки к строке `status` остаются — «[поделена:
     …]»/«[часть N/M родителя …]» из main и твоя «[ждёт merge-окна: …]»;
     порядок — существующие добавки, затем новая.
   - `docs/codebase-map.md`: взять версию main и перегенерировать
     `python3 scripts/codebase_map.py` на слитом дереве.
   После слияния прогони `tests/test_merge_gate_ci_wait.py`,
   `tests/test_merge_lock*.py`, тесты `catalog`/`status`, свои новые
   тесты и планку задачи; закоммить merge-коммит и сдай шаг как обычно.
