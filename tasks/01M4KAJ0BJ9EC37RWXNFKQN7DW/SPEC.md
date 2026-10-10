---
task: 01M4KAJ0BJ9EC37RWXNFKQN7DW
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/amend.py, docs/codebase-map.md, tests/
budget_usd: 25
---

# SPEC: amend-tests — признак сетевых адресов только для артели

## Контекст
Узел проверки долгоживущих файлов `scripts/guard.py::long_lived_errors_from_files`
принимает параметр `network_addresses: bool = True`: при `True` в ошибки
входит признак адреса по DNS-имени (инвариант 35,
`guard.network_address_hits`). Выход из `tests_writing` передаёт
`network_addresses = repo_context.is_artel(target)`
(`orchestrator/fsm_advance.py` ~468, `orchestrator/advance_gates/tests_writing.py`),
поэтому у чужого проекта признака нет. `orchestrator/amend.py::_long_lived_errors`
(~493) зовёт узел без параметра (~510): `amend-tests` чужого проекта
отказывает долгоживущему тесту с адресом вроде `https://api.stripe.com/v1`
со ссылкой на неприменимый к нему инвариант 35, и обхода у Оператора нет.
Источник — бэклог 10.10, остаток ревью 01M4JN2EDQP8Q3WVYK0TS95ZVC, замечание R1-F1.

## Требования
1. `amend-tests` передаёт узлу проверки долгоживущих файлов признак проекта
   так же, как выход из `tests_writing`: у артели признак сетевых адресов
   действует, у чужого проекта — нет.
2. Остальные проверки долгоживущих файлов в `amend-tests` не меняются: у
   чужого проекта прочие ошибки долгоживущего файла по-прежнему дают отказ.
3. Ослабления для артели нет: долгоживущий файл задачи артели с адресом по
   DNS-имени по-прежнему даёт отказ `amend-tests` с файлом и строкой.
4. Смена ожидания существующих тестов `tests/` — только через раздел SPEC
   «Меняемое поведение» (инвариант 38); на момент SPEC таких методов нет.

## Критерии приёмки
AC-1. `amend-tests` задачи артели: долгоживущий файл с адресом
`https://example.test/x` даёт отказ; в тексте отказа — путь файла, номер
строки с адресом и ссылка на инвариант 35.

AC-2. `amend-tests` задачи чужого проекта (подменённый `is_artel` либо
target песочницы, не являющийся артелью): тот же долгоживущий файл с
`https://example.test/x` не даёт ошибки признака сетевых адресов.

AC-3. `amend-tests` задачи чужого проекта: если в долгоживущем файле с
адресом есть прочие ошибки проверки долгоживущих файлов, они по-прежнему
дают отказ — снят только признак адресов.

AC-4. Мутация «`amend-tests` зовёт узел проверки долгоживущих файлов без
признака проекта» (вызов без параметра `network_addresses`, то есть с
умолчанием `True`) ловится тестом: при ней AC-2 краснеет.

## Оценка объёма и деление
Сработавшие сигналы (по отказу guard): число затрагиваемых модулей/файлов
зоны (маска `tests/` считается широкой), затронут инвариантный механизм
(инвариант 35 — признак сетевых адресов), прогноз диффа не дан.

Прогноз диффа: 6 КиБ

Обоснование монолита: правка кода — одна передача признака проекта в один
вызов `orchestrator/amend.py` (~510) плюс регенерация карты; сторож её
свойства — тест `tests/` на ту же развилку. Код без теста не держит
требование 3 (ослабление для артели не поймано), тест без кода красен
(AC-2). Резать нечего: любая часть отдельно оставляет либо непроверенное
поведение, либо красную ветку. Инвариант 35 для артели не меняется
(требование 3), механизм `guard.network_address_hits` не правится.

## Не входит
- Действие отказа рубежа адресов (общее «переход отклонён», R1-F2 ревью
  01M4JN2EDQ).
- Полный прогон и его сигнал (задача 01M4K2767FXKZ8EW7AME81SZ9N).
- Адреса вне `tests/`.
- Правка путей только для чтения: `scripts/guard.py`,
  `orchestrator/advance_gates/tests_writing.py`, `orchestrator/fsm_advance.py`,
  `orchestrator/repo_context.py`, `orchestrator/acceptance.py`,
  `orchestrator/notes.py`, `orchestrator/suite_lock.py`, `orchestrator/config.py`,
  `orchestrator/store.py`, `tests/test_invariants.py`, `.github/workflows/ci.yml`,
  `docs/invariants.md`, `docs/triggers.md`, `docs/adr/`, `docs/roadmap.md`,
  `docs/backlog.md`, `docs/operator-session.md`, `templates/`, `skills/`,
  `CLAUDE.md`, `models.yaml`, `roles.yaml`, `targets.yaml`, `.artel/`.

## Материалы
- ТЗ: рамка $10; бюджет поставлен на пол калибровки $25
  (`config.BUDGET_CALIBRATION_FLOOR_USD`) — ниже пол не опускается.
- `orchestrator/amend.py:493-510` — `_long_lived_errors`, вызов
  `guard.long_lived_errors_from_files(sorted(files.items()), task_id)`.
- `orchestrator/repo_context.py:154` — `is_artel`.
- `docs/invariants.md`, строка 35 — тесты не читают сеть по DNS-имени.
