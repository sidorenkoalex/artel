# Записка analyst — 01M6N7CYKDAMAKENX60CBK7VQX

## Выяснено
- ANSWER-1: мандат A на три файла тестов, монолит, budget_usd 85.
- Шаг 3 (возврат со spec_gate, четыре решения Оператора) — внесены в SPEC:
  1. Треб. 8/AC-8: признак `READS_CI_REQUIRED_JOBS` (gitlab_adapter True, _GitHub нет/False), `getattr(_hosting_registry().get(hosting), ..., False)`, не `CI_BY_PIPELINE`; AC-8 — подкласс `_GitHub` с True и gitlab-пространство имён с False; `[]` не закрепляется. Сверено: forge.py:365 реестр, gitlab_adapter.py:44 `CI_BY_PIPELINE = True`, forge.py:222 `_GitHub.CI_BY_PIPELINE = False`.
  2. AC-4: fail-перечень заменён (`**/`, `**/x`, `**/a`, `**/main.yml`, `.github/workflows/x`, `/a` и прежние); ok-случаи оставлены прежние пять (формула их покрывает). Треб. 3 дополнено: не пробой путём каталога и не одним именем. Сверено config.py:837-849: `**/` истинна только для пути, оканчивающегося `/`.
  3. AC-13: в файле эпика вид как на main (`reason = targets.unsupported_reason(name)`, epic:72-73, :87), без новой константы.
  4. Записки разработчику — в «Материалы».

## Где остановился
- SPEC.md: status ready, guard ок.

## Чего не хватило
- Ничего существенного: решения Оператора дали адреса.
