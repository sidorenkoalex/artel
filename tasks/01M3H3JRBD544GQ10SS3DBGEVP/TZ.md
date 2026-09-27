---
task: 01M3H3JRBD544GQ10SS3DBGEVP
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: doctor предполётит роль analyst и вход провайдера Codex

# ТЗ: doctor предполётит роль analyst и вход провайдера Codex

Источник: строка бэклога 27.09 «doctor не предполётит роль analyst»
(docs/backlog.md). Прецедент 27.09: роль analyst переведена на провайдер
Codex (ярус standard, локальный слой), а `doctor` не напечатал ни
строки входа по подписке, ни строки дома роли Codex, ни строки токена
роли analyst — вход проверялся руками. Линия провайдеров.

Факты (origin/main a6da0abe):
- `orchestrator/doctor/preflight.py::agent_roles` возвращает
  `sorted(set(config.STATE_ROLE.values()))`; `config.STATE_ROLE` =
  tests_writing → test_author, in_dev → developer, review → reviewer.
  Состояние spec_writing в словарь сознательно не входит
  (orchestrator/runner.py:91, orchestrator/auto.py:557 — роль analyst
  исполняет его только при наличии ТЗ), поэтому analyst в перечень ролей
  `doctor` не попадает.
- По `agent_roles()` идут `provider_preflight_checks` (предполёт
  провайдера каждой роли: CLI найден, версия, токен, дом роли),
  `check_role_providers` и `check_models_local` (цепочка «роль → ярус →
  модель → провайдер»). Отдельная строка `model-analyst` при этом
  печатается (другой перечень ролей).
- `CodexProvider.preflight(role)` (orchestrator/providers/codex.py:400)
  несёт проверки CLI, версии, входа и дома роли; docs/stack.md обещает
  строки `codex-chatgpt-auth` и `codex-role-home`.
- Карта исполнителей `roles.yaml`: agent-роли — analyst, test_author,
  developer, reviewer (`executor: agent`).

Требуется:
1. Перечень ролей `doctor` — все роли карты исполнителей с
   `executor: agent` (источник — `orchestrator/roles.py`, не
   `config.STATE_ROLE`); `config.STATE_ROLE` не меняется, его читатели
   (runner, auto, pause, doctor/leases) не затрагиваются.
2. Для роли analyst печатаются те же строки предполёта, что для
   остальных ролей: токен либо вход провайдера, дом роли, цепочка роли в
   `role-providers` и `models-local`. Роль на Codex даёт строки входа по
   подписке и дома роли Codex; роль на Claude — прежние строки.
3. Склейка одинаковых проверок сохраняется: строки, не зависящие от
   роли, остаются по одной на провайдера; вывод `doctor` для пульта, где
   все роли на Claude, меняется только добавлением строк роли analyst.
4. Нечитаемая карта исполнителей — прежний именованный отказ строки
   `role-providers`, без падения `doctor`.
5. Тесты (tests/): analyst входит в перечень; роль на Codex даёт строки
   входа и дома роли Codex; пульт без Codex не получает строк Codex;
   существующие tests/test_doctor.py, tests/test_models_doctor.py,
   tests/test_providers.py, tests/test_providers_codex.py,
   tests/test_runner_model_preflight.py зелёные, ни один не ослаблен.

Зоны: orchestrator/doctor/, tests/.

Только чтение (не менять): orchestrator/config.py (`STATE_ROLE` не
меняется), orchestrator/roles.py, orchestrator/providers/codex.py и
orchestrator/runner.py (зоны параллельной задачи о паритете окружения
шага Codex), orchestrator/auto.py, orchestrator/pause.py, roles.yaml,
docs/stack.md (зона пробной задачи 01M3H1Z489CKJ8FHSRS4TYTPX2 в полёте),
docs/backlog.md, tests/test_invariants.py.

Не входит: проверка остатка лимита подписки; правка текстов
docs/stack.md; изменение `config.STATE_ROLE`.

Рамка: $15.
