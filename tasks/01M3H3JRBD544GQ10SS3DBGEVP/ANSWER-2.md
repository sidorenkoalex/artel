---
task: 01M3H3JRBD544GQ10SS3DBGEVP
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

# ANSWER-2: решение Оператора по конфликту подтяжки main

Конфликт: docs/codebase-map.md и tests/test_stack_optional_tools.py.
В главную ветку 27.09 смержена задача 01M3H5FEXH5M9HGZYT3BCDX5C4
(«Тесты манифеста стека не зависят от ярусов настоящего roles.yaml»,
вершина origin/main 5ec64e1c): она закрыла покрытие ярусов общим
помощником `_tiers_text` в tests/test_runner_role_model.py — локальный
слой песочницы называет модель у каждого яруса `models.TIERS`.

Как разрешать:

1. **Покрытие ярусов — по главной ветке.** В
   tests/test_stack_optional_tools.py принять вариант origin/main
   (`_tiers_text`); собственный `_tiers_block` ветки и его комментарий
   снять как дубль того же решения. Два способа покрыть ярусы в одном
   файле не оставлять.
2. **Нормализация провайдера — сохранить.** Правка ветки по замечанию
   R1-F1 (`roles_text_on_default_provider`: поле `provider:` в карте
   сценария ставит только сам тест) остаётся и накладывается поверх
   варианта главной ветки. Проверить тем же приёмом остальные три
   теста из R1-F1 (tests/test_providers.py, tests/test_doctor.py,
   tests/test_providers_codex.py) и новый
   tests/test_stack_roles_tier_spread.py из главной ветки.
3. **Замечание R1-F3 закрывается этим же:** обоснование со ссылкой на
   ярус `standard` у analyst в ветке больше не нужно — переписать PLAN
   «Риски» под фактическое состояние (ярусы покрывает главная ветка).
4. docs/codebase-map.md — перегенерировать генератором на слитом дереве.
5. Ни одна проверка существующих тестов не ослабляется и не удаляется;
   число тестовых методов в tests/test_stack_optional_tools.py после
   слияния не меньше, чем в origin/main.
