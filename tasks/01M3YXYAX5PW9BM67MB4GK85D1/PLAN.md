---
task: 01M3YXYAX5PW9BM67MB4GK85D1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Предполёт шага сверяет CLI и вход провайдера шага, а не провайдера роли

## Подход
Провайдер шага уже считает `runner._step_provider(t, role)`
(`orchestrator/runner.py`); предполёт его не получал. Решение:

- `doctor.preflight_checks(role, target, *, provider=None, task_set=None)`
  (`orchestrator/doctor/preflight.py`). Без именованных аргументов —
  прежний путь (`providers.for_role`). С ними — CLI, версия CLI и вход
  спрашиваются у переданного провайдера шага; половина
  «расхождение боевой цепочки роли» `check_model_provider_cli` пропускается
  (`combat_chain=False`: этот шаг идёт не по боевой цепочке, требование 3);
  каждый провал дописывается хвостом `[провайдер шага <п>, роль <р>,
  набор задачи <н>]` (`_named_by_set`, требование 2). Тело предполёта
  осталось внутри `preflight_checks` — его исходник читает
  `tests/test_stack_optional_tools.py` (порядок блокирующей группы).
- `runner._refuse_before_start` передаёт `provider`/`task_set` ТОЛЬКО шагу
  на модели набора (`_step_set_name` → новый общий `_set_step_model`, им
  же теперь пользуется `_step_provider`); задача без набора зовёт
  предполёт прежним вызовом `preflight_checks(role, target)` — поведение
  и вызов байт-в-байт прежние (требование 1, AC-3).
- `doctor.provider_preflight_checks` после провайдеров ролей карты
  спрашивает провайдеров `models.live_task_set_providers()`, которых
  среди них нет, — по каждой agent-роли (источник называет провайдеров,
  не роли; «вход по одной строке на роль» — та же идиома, что у боевых
  провайдеров). Закрытые задачи отсекает сам источник (требование 4,
  AC-5).
- AC-1 — в прочтении ANSWER-1 (Б): манифест и `stack.REQUIRED_TOOLS` не
  тронуты, правка только в предполёте.

## Шаги
1. `runner.py`: `_set_step_model`, `_step_set_name`, передача провайдера
   шага и набора в предполёт.
2. `doctor/preflight.py`: параметры `preflight_checks`, `combat_chain` у
   `check_model_provider_cli`, `_named_by_set`, добавка провайдеров
   наборов в `provider_preflight_checks`.
3. Тесты: долгоживущий файл задачи зелёный без правки; свой
   `tests/test_preflight_step_provider.py` (5 методов) на углы вне него;
   заглушка предполёта в `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`
   принимает именованные аргументы.
4. `docs/stack.md` — абзац «Предполёт шага задачи с набором»; карта
   `docs/codebase-map.md` перегенерирована.
5. Возврат из verifying (CI красный после мержа 01M3YCHVVEK14SK8GT4R0H7M2C
   в main): main уже подтянут (`1f544a05`); заглушка предполёта в
   `SetSandbox.setUp` долгоживущего файла той задачи
   `tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py:210`
   `lambda role, target: []` → `lambda role, target, **step: []` — та же
   правка, что в `test_01m3ychs4f08…`; утверждения не тронуты. Прочие
   позиционные заглушки (`grep "lambda role, target"`) — у задач без
   набора, именованных аргументов не получают. Карта перегенерирована
   после подтяжки (`docs/codebase-map.md` отставала).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (провайдер шага, без набора — прежнее) | 1, 2 |
| 2 (именованный отказ с провайдером, ролью, набором) | 2 |
| 3 (боевой провайдер вне шага не отказывает) | 1, 2 |
| 4 (`doctor` + провайдеры наборов в работе) | 2 |
| 5 (тесты AC-1…AC-3) | 3 |
| 6 (`docs/stack.md`) | 4 |

Прогоны (передний план, `-p timeout -o timeout=120`):
- `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py` +
  `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py` — 22 passed;
- `test_doctor`, `test_providers`, `test_providers_codex`,
  `test_doctor_agent_roles`, `test_stack_optional_tools`,
  `test_runner_model_preflight`, `test_task_model_set_units`,
  `test_journal_warning_once`, `test_models_doctor` — 304 passed;
- `test_runner_role_model`, `test_step_cost`, `test_agent_failure`,
  `test_provider_scoped_step_env`, `test_codex_login_shell_path`,
  `test_01m3se87r3m7hgwx8hg1anakr0_role_environment`, `test_model_sets`,
  `test_01m3ychp14179r32sfjvkqb32g_model_sets`, `test_stack`,
  `test_runner_wave_breaker`, `test_mutation_claim_gate` — 190 passed;
- `test_preflight_step_provider` — 5 passed; временные мутации
  (`combat_chain=True` всегда, добавка наборов без `- asked`, пометка на
  всех строках) красили заявленные методы, код возвращён;
- `test_stack_codex_section`, `test_stack_parity_table`,
  `test_stack_zones_pull_section`, `test_codebase_map` — 46 passed.
- после возврата: `test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension`,
  `test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight`,
  `test_01m3ychs4f08vtv6xx10vf92h3_task_model_set`,
  `test_preflight_step_provider` — 38 passed; `test_doctor`,
  `test_runner_model_preflight`, `test_task_model_set_units`,
  `test_codebase_map` — 192 passed.

## Влияние на систему
- Задача без набора: вызов предполёта и его состав не изменились
  (именованные аргументы не передаются) — существующие заглушки
  `lambda role, target: []` в десятке тестов работают как прежде.
- Заглушка в `tests/test_01m3ychs4f08vtv6xx10vf92h3_task_model_set.py`
  (долгоживущий файл ЗАКРЫТОЙ задачи 01M3YCHS…): сигнатура лямбды
  `lambda role, target: []` → `lambda role, target, **step: []` — шаги
  задач с набором теперь получают именованные аргументы. Ни один метод и
  ни одно утверждение не тронуты.
- Гейты, guard, лимиты, инварианты не трогаются; манифест стека
  (`stack.REQUIRED_TOOLS`) и `models.py` — без правки.
- `doctor` на пульте с набором в работе печатает строки провайдера набора
  (по строке входа на agent-роль) — добавочные подпроцессы
  `codex login status` только пока такая задача жива.
- Откат — revert коммита задачи.

## Риски
- Добавка `doctor` спрашивает провайдера набора по ВСЕМ agent-ролям, а не
  только по ролям, которые набор переводит: источник по SPEC —
  `live_task_set_providers`, который ролей не называет. Вход Codex от роли
  не зависит (`CodexProvider.environment`), так что исход у строк общий;
  лишь число строк больше минимума.

## Предложения системе
- `orchestrator/models.py::live_task_set_providers` отдаёт только
  провайдеров; `doctor` из-за этого спрашивает вход провайдера набора по
  всем ролям. Вариант с парами «роль — провайдер» сузил бы вывод (путь
  `models.py` в этой задаче только для чтения).
- Десяток тестов подменяет `doctor.preflight_checks` позиционной
  лямбдой `lambda role, target: []` — любое расширение сигнатуры ломает их
  все разом; общая заглушка в `tests/sandbox.py` сняла бы этот класс.
  Подтверждено: параллельная задача 01M3YCHVVEK14SK8GT4R0H7M2C принесла в
  main ещё одну такую лямбду — CI ветки покраснел уже после ревью.
