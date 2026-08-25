---
task: T023
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: A4 — роль test_author: приёмочные тесты до кода

## Фаза A: гейт плана

Тот же PLAN.md (шаги 1–10) плюс шаг 11 «Итерация 3: замечания ревью 2» —
две точечные правки той же зоной, размером с проверяемый MR-шаг: новый
тест в `AcceptanceRunTest` и абзац в «Влияние на систему». Покрытие
требований и подход не изменились относительно итерации 1–2.
**Гейт плана: аппрув** (подтверждаю решение итераций 1–2).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (состояние tests_writing, роль test_author, скилы) | OK | Без изменений с итерации 1. |
| 2 (AC-разметка SPEC, skip_tests, старые SPEC валидны) | OK | Без изменений; `guard.py --all` перепроверил — 60 файлов, зелёный. |
| 3 (выход роли: acceptance_tests/, без второго документа) | OK | Без изменений. |
| 4 (трассируемость на выходе, эскалация неисполнимости) | OK | Без изменений. |
| 5 (лок фиксацией T021) | OK | Без изменений с итерации 2 — закрыто. |
| 6 (прогон приёмки review→acceptance, сводка) | OK | Замечание 1 итерации 2 (защита таймаута не codified тестом) закрыто — см. ниже. |
| 7 (триггер пересмотра лока) | OK | Без изменений. |
| 8 (маршрут эскалации test_author) | OK | Без изменений. |
| 9 (manual-критерий: живой прогон test_author) | N/A | Как в итерациях 1–2 — вне зоны кодового ревью. |

**Замечания итерации 2 — проверка закрытия:**

- Major (защита таймаута прогона не codified тестом) — закрыт.
  `tests/test_acceptance_tests_flow.py::AcceptanceRunTest.
  test_timeout_blocks_the_transition_and_names_the_limit` мокает
  `acceptance.subprocess.run` через `side_effect=subprocess.TimeoutExpired`
  (без реального сна, тем же приёмом, что `test_agent_failure.py:318`) и
  ДОПОЛНИТЕЛЬНО проверяет `run_mock.call_args.kwargs["timeout"] ==
  config.ACCEPTANCE_TIMEOUT_SEC`. Это существенно: голый `side_effect`
  срабатывает независимо от реально переданного `timeout=`, а вот
  проверка kwargs — нет. Перепроверил мутацией сам: убрал
  `timeout=config.ACCEPTANCE_TIMEOUT_SEC)` из вызова `subprocess.run` в
  `orchestrator/acceptance.py:run()` (`timeout=` из аргументов исчез,
  сигнатура вызова осталась рабочей), прогнал
  `python3 -m unittest tests.test_acceptance_tests_flow.AcceptanceRunTest`
  — новый тест покраснел (`AssertionError: None != 300`), остальные 5 в
  классе прошли; вернул правку `git checkout -- orchestrator/acceptance.py`.
  Ровно тот регресс, который итерация 1 просила исключить, теперь имеет
  тест, который его ловит.
- Minor (недокументированный бамп `schema_version` в трёх шаблонах) —
  закрыт документированием (второй вариант из предложения ревью 2).
  `tasks/T023/PLAN.md`, раздел «Влияние на систему» → блок
  Protected-paths теперь называет `templates/PLAN.md`/`templates/
  REVIEW.md`/`templates/TEST_REPORT.md` и объясняет причину бампа: не
  откат — тест `test_guard_schema.TemplatesCarryTheVersionTest.
  test_every_template_declares_the_current_version` (T017) требует, чтобы
  ВСЕ четыре шаблона несли ровно `SUPPORTED_SCHEMA_VERSION`. Перепроверил
  сам: `python3 -m unittest tests.test_guard_schema -v` — тест зелёный на
  текущем состоянии репозитория (все четыре шаблона на версии 2), что
  подтверждает необходимость бампа, о которой пишет PLAN.

Регрессия: `python3 -m unittest discover -s tests` — 480 тестов
(было 479, +1 новый тест таймаута), 3 упавших
(`test_multitarget.RoleEnvTest.*`, git-identity в окружении) — та же
среда-зависимая причина, что в итерациях 1–2, не относится к диффу T023.
`tests/test_acceptance_tests_flow.py` — 35/35 зелёные (было 34, +1).
`guard.py --all` — зелёный (60 файлов). Диф итерации 3 (`git diff
e1bdfe5 d71dcb2`) затрагивает ровно два файла — `tasks/T023/PLAN.md` и
`tests/test_acceptance_tests_flow.py` — никакого кода `orchestrator/`
или protected-paths сверх уже одобренного не тронуто.

## Замечания

Нет.

## Вердикт

approved. Оба замечания итерации 2 закрыты и перепроверены самостоятельно,
не только чтением PLAN: mutation-тест (снятие `timeout=` в
`orchestrator/acceptance.py:run()`) красит новый
`test_timeout_blocks_the_transition_and_names_the_limit` — защита теперь
codified, а не только описана в коде; документационное закрытие minor
подтверждено прогоном `test_guard_schema` (зелёный при текущем бампе,
падает при откате — сам PLAN это уже проверял, повторил независимо).
Полная регрессия (480 тестов, 3 упавших — среда, не диф) и
`guard.py --all` зелёные. Диф итерации 3 минимален и ровно соответствует
заявленному в шаге 11 PLAN — scope creep нет. Требования 1–9 закрыты
(9 — вне кодового ревью, как и в итерациях 1–2). Дальше — приёмка
Оператором (требование 9, живой прогон test_author) и переход
review → acceptance.
