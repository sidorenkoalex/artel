---
task: 01M3H5FEXH5M9HGZYT3BCDX5C4
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Тесты манифеста стека не зависят от ярусов настоящего roles.yaml

# ТЗ: Тесты манифеста стека не зависят от ярусов настоящего roles.yaml

Источник: строка копилки 27.09 «main красный с a6da0abe». Прецедент
27.09: перевод роли analyst на ярус standard (пробная роль на Codex)
уронил тест на главной ветке; правка roles.yaml откатана (d910c523),
пробная роль выключена до этой задачи. Линия провайдеров: условие
возврата роли analyst на Codex.

Факты (origin/main d910c523):
- `tests/test_runner_role_model.py::_roles_yaml_text(role, tier)` строит
  карту исполнителей теста из настоящего `roles.yaml` репозитория
  (`_REAL_ROLES_TEXT`): у ОДНОЙ названной роли строки `model:` и
  `model_tier:` заменяются на ярус теста, остальные роли остаются как в
  боевом файле.
- `tests/test_stack_optional_tools.py::_ManifestSandbox.use_tier` пишет
  локальный слой с моделью ТОЛЬКО для яруса теста (`strong`) и зовёт
  `_roles_yaml_text("developer", "strong")`. Пока все роли боевого файла
  стоят на `strong`, слой покрывает всех; роль на другом ярусе
  (analyst: standard) остаётся без модели, и
  `CheckStackLinesTest::test_missing_unused_tool_gives_no_line_at_all`
  получает красную строку `model-analyst`.
- Распределение ролей по ярусам — решение Оператора (roles.yaml,
  защищённый путь); тест манифеста проверяет другое свойство — состав
  строк инструментов.

Требуется:
1. Тесты, строящие карту исполнителей из настоящего `roles.yaml`, не
   зависят от того, на каких ярусах стоят роли, не названные тестом:
   локальный слой песочницы покрывает все ярусы (`models.TIERS`) либо
   карта теста приводит ярусы всех agent-ролей к ярусу теста — способ
   выбрать и обосновать в SPEC. Проверяемое тестами свойство не
   меняется, ни одна проверка не ослабляется и не удаляется.
2. Найти и перечислить в PLAN все тесты tests/ с той же зависимостью
   (потребители `_roles_yaml_text` и собственные копии приёма), не
   только упавший.
3. Регрессионный тест: при карте исполнителей, где одна agent-роль стоит
   на ярусе, отличном от остальных, тесты манифеста стека и модели роли
   зелёные.
4. Существующие tests/test_stack_optional_tools.py,
   tests/test_runner_role_model.py, tests/test_runner_model_preflight.py,
   tests/test_models_doctor.py зелёные.

Зоны: tests/.

Только чтение (не менять): roles.yaml, orchestrator/stack.py,
orchestrator/models.py, orchestrator/roles.py, docs/backlog.md,
tests/test_invariants.py.

Не входит: правка roles.yaml и локального слоя пульта; запуск набора
tests/ командой doc-commit для файлов конфигурации (отдельная строка
копилки).

Рамка: $25.
