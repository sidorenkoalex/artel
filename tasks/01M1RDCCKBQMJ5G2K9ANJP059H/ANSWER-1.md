---
task: 01M1RDCCKBQMJ5G2K9ANJP059H
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M1RDCCKBQMJ5G2K9ANJP059H
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Расширение зон разрешено: orchestrator/stack.py

1. Вариант (a). Мандат выше — на минимальное расширение: в
   `orchestrator/stack.py` добавляются функция
   `python_version_string() -> str` и константа из ответа 2; существующая
   публичная поверхность части 1 (`REQUIRED_PYTHON`, `REQUIRED_TOOLS`,
   `THIRD_PARTY_EXCEPTIONS`, `check_stack`) не меняется. В PLAN.md
   оформи раздел «## Расширение зон» со строкой
   `Пути: orchestrator/stack.py` и этим обоснованием — гейт зон
   сверяет раздел с маркером мандата в этом ANSWER. Залоченная планка
   (`test_ac4_stack_ci_matches_manifest.py`, mock без `create=True`)
   остаётся как есть — функция появится.
2. Вариант (a). Константа `CURRENT_STABLE_PYTHON = (3, 13)` в
   `orchestrator/stack.py` (комментарий: версия локальной разработки и
   основных джобов CI; поднимается Оператором вместе с pyenv).
   `python_version_string()` возвращает её в формате `setup-python`
   («3.13») — это версия основных джобов CI. Вторая нога матрицы
   требования 2 — `REQUIRED_PYTHON` («3.11»), `scripts/stack_ci.py`
   читает её напрямую из манифеста и печатает по флагу (например,
   `--min`), литералов версий ни в `stack_ci.py`, ни в `ci.yml` нет.
3. Подтяжка main в ветку и перегенерация карты — верно, продолжай с
   этого состояния.
