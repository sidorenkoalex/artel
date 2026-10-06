---
task: 01M48WRE8BHFDY011Q0HQGQ91B
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Предел полного прогона tests/ — поле профиля тестов проекта

# ТЗ: предел полного прогона tests/ — поле профиля тестов проекта, штатная правка Оператором

Порядок: после 01M48FRD9RJDBBVT2SN0FY5G2A

Источник: 06.10. Канарейка 20261006T122912Z на 73ce3329: полный прогон
tests/ автогейта превысил `FULL_SUITE_TIMEOUT_SEC = 900`; замер Оператора
06.10 — под параллельной нагрузкой полный прогон долгоживущих файлов идёт
в 4–5 раз дольше. Решение Оператора поднять предел до 1500 с упёрлось в
отсутствие штатного пути: `doc-commit` принимает только `docs/**` и
конфиги (`roles.yaml`, `gates.yaml`, `targets.yaml`, `models.yaml`, наборы
моделей), push кода в main останавливает pre-push («только командой
пульта»), обход Оператор отклонил. Строка бэклога 06.10 «Правка кода и
лимита Оператором — команда пульта». Решение Оператора 06.10: завести.

Факты (пин 73ce3329, сверка кода 06.10):
- `orchestrator/config.py` (~195): `FULL_SUITE_TIMEOUT_SEC = 900`; читают
  `orchestrator/acceptance.py` (`run_full_suite` ~691, `_full_suite_outcome`
  ~640, `full_suite` ~959 и тексты таймаута ~602–607, ~787, ~808, ~837),
  `orchestrator/suite_run.py` (~311), `orchestrator/fsm_merge_gate.py`
  (~927). Тесты подменяют константу (`mock.patch.object(config,
  "FULL_SUITE_TIMEOUT_SEC", …)`), значение 900 ни один тест не закрепляет.
- `FULL_SUITE_LOCK_WAIT_SEC = 1800` (~207) закреплён долгоживущим тестом
  `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py::WaitLimitTest::test_ac6_config_declares_lock_wait_limit`.
- Профиль тестов проекта — `targets.yaml`, поле `test_profile` записи
  проекта; разбор — `orchestrator/project_profile.py`; поля сегодня:
  `command`, `long_lived_dir`, `long_lived_name`, `weakening_scope`,
  `mutation_claim_scope`, `report`, `install`. `targets.yaml` правит
  Оператор командой `doc-commit` (`orchestrator/notes.py::
  DOC_COMMIT_CONFIG_PATHS` ~134).

Требуется:
1. Необязательное поле профиля тестов `full_suite_timeout_sec` (целое,
   секунды, > 0): предел полного прогона tests/ проекта задачи на гейтах
   пульта (автогейт и approve приёмки, гейт мержа) и в `suite-run`. Поля
   нет — действует `config.FULL_SUITE_TIMEOUT_SEC` (900), как сегодня.
   Неверное значение (не целое, ≤ 0) — отказ разбора профиля с именем поля,
   тем же путём, что другие ошибки профиля.
2. Тексты таймаута (журнал, `detail`, вывод) называют действующий предел и
   его источник («профиль тестов проекта <имя>» или «config»).
3. `doctor` или `status` показывает действующий предел полного прогона
   проекта и источник (решение SPEC, где именно).
4. Тесты в `tests/` с заявками «Ловит мутацию»: поле профиля меняет предел
   прогона гейта; без поля — константа config; неверное значение — отказ
   профиля; текст таймаута называет предел и источник. Существующие тесты
   не ослабляются; `FULL_SUITE_LOCK_WAIT_SEC` не меняется.
5. После мержа Оператор вносит `full_suite_timeout_sec: 1500` в профиль
   артели командой `doc-commit targets.yaml` — это вне задачи, в PLAN —
   готовая строка.

Зоны: orchestrator/project_profile.py, orchestrator/acceptance.py,
orchestrator/suite_run.py, orchestrator/fsm_merge_gate.py,
orchestrator/doctor/, orchestrator/catalog.py, orchestrator/config.py,
tests/, docs/codebase-map.md.

Только чтение (не менять): orchestrator/notes.py, targets.yaml, conftest.py,
tests/test_invariants.py, docs/invariants.md, docs/adr/, docs/roadmap.md,
docs/backlog.md, docs/operator-session.md, templates/, skills/, CLAUDE.md,
models.yaml, roles.yaml, .github/workflows/ci.yml.

Не входит: общая команда правки констант config.py Оператором; изменение
`FULL_SUITE_LOCK_WAIT_SEC`, `FULL_SUITE_WORKERS`, `ACCEPTANCE_TIMEOUT_SEC`;
предел CI GitHub.

Рамка: $30.
