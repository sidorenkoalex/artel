---
task: 01M3SA3ANYZ7036AAGXZG753E3
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Команда models показывает фактическую модель роли

# ТЗ: Команда models показывает фактическую модель роли

Источник: строка копилки 30.09 (П2) «Команда `models` вводит в
заблуждение о боевом наборе»; решение Оператора 30.09.2026 завести задачу.

Факты (пин 34b298c7):
- Разрешение роли — `orchestrator/models.py::resolve_role`: роль с записью
  `role_models:` локального слоя идёт на модель записи мимо яруса
  (`_resolve_role_model`), провайдер — `role_providers:` роли, иначе
  провайдер модели в каталоге.
- Команда `models` (`orchestrator/models.py::cmd_models`) строит столбец
  «роли по ярусам» только по `tiers:` (`_roles_by_tier` + `tier_of_model`)
  и раздел `role_models:` не читает. На пульте 30.09 при
  `role_models: {analyst: gpt-5.6-terra, test_author: gpt-6-sol,
  developer: gpt-6-sol, reviewer: gpt-5.6-terra}` таблица печатает у
  `claude-opus-5-5` «strong: analyst, developer, reviewer, test_author»,
  а у моделей codex — «—». Фактические шаги 30.09 шли на codex (журнал
  steps: 01M3RWA2786HCAC8PT3XSBKQT4, 01M3S9HRZYT0C6TC1CZJPNYKZ1).
- `doctor` ту же цепочку показывает верно (строки `role-providers`,
  `role-models`) — расходится только `models`.
- Описание команды — `docs/stack.md`, раздел «Модели: каталог, ярусы,
  тариф», пункт «посмотреть, что где действует».

Требуется:
1. Столбец ролей таблицы `models` показывает, какие роли фактически
   запускаются на модели строки, — по тому же разрешению, что
   `resolve_role` (одна функция-источник, без второй копии правила).
   У каждой роли — источник: ярус (`strong: analyst`) или запись
   `role_models` (`role_models: analyst`). Роль, переведённая записью
   `role_models` на другую модель, у модели своего яруса не
   показывается. Заголовок столбца переименовать в «роли» (или
   равнозначно) — «роли по ярусам» больше не верно.
2. Под таблицей — итоговая строка на каждую роль-агента:
   «роль → модель → провайдер (источник)», тот же порядок и формат, что
   цепочка в строке `role-providers` `doctor`. Роль, чьё разрешение
   отказывает (`ResolutionError`), печатается с текстом отказа, команда
   при этом не падает.
3. Команда остаётся только чтением; непрочитанный локальный слой или
   карта исполнителей — прежние строки-причины над таблицей.
4. `docs/stack.md`: пункт «посмотреть, что где действует» описывает новый
   столбец и итоговые строки.
5. Тесты в `tests/`: слой с `role_models` на модель чужого провайдера —
   роль в строке модели записи с источником `role_models`, у модели яруса
   её нет («Ловит мутацию: столбец строится только по tiers»); итоговая
   строка совпадает с `resolve_role`; роль с отказом разрешения
   печатается с текстом отказа; прежние тесты `models` без `role_models`
   зелёные (правка ожидаемого заголовка столбца допустима).

Зоны: orchestrator/models.py, docs/stack.md, tests/.

Только чтение (не менять): orchestrator/roles.py, orchestrator/doctor.py,
orchestrator/runner.py, orchestrator/providers/, orchestrator/config.py,
models.yaml, roles.yaml, scripts/guard.py, skills/, templates/, docs/adr/,
docs/invariants.md, tests/test_invariants.py, docs/backlog.md, tasks/.

Не входит: наборы канарейки (`canary_sets:`) в выводе `models`; правки
`doctor`; провайдер opencode и модели X5 (отдельная задача).

Рамка: $15.
