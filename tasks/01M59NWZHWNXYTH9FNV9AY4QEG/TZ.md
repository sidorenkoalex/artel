---
task: 01M59NWZHWNXYTH9FNV9AY4QEG
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Одобрение SPEC с уточнениями: `approve <id> --decisions <файл>` на гейте SPEC, решения — в бриф ролей после гейта

# Одобрение SPEC с уточнениями: `approve <id> --decisions <файл>` на гейте SPEC, решения — в бриф ролей после гейта

## Факты

Строка копилки 19.10.2026 (`docs/backlog.md`, раздел «Копилка», коммит 4e6273dc): на гейте SPEC нет способа одобрить с уточнениями — `approve` не несёт текста решений, поэтому мелкое уточнение аудита (`concerns`) стоит полного круга `reject` → аналитик → аудит (~$3 и 8 минут). У G2а-1 (01M59KMPG2) второй круг ушёл на три уточнения формулировок.

- Решения с гейта сегодня — только причины `reject`. Константы раздела:
  `orchestrator/brief.py:62` (`SPEC_GATE_RETURN_PREFIX`),
  `orchestrator/brief.py:63` (`SPEC_GATE_DECISIONS_HEADER`),
  `orchestrator/brief.py:64` (`SPEC_GATE_DECISION_LABEL`),
  `orchestrator/brief.py:65` (`SPEC_GATE_DECISIONS_NOTE`).
- Причины по журналу — `orchestrator/brief.py:1129` (`_spec_gate_reasons`);
  раздел — `orchestrator/brief.py:1147` (`_spec_gate_decision_components`).
  Его получает только аудитор SPEC: бриф `orchestrator/brief.py:1079` (`spec_auditor_brief`),
  вызов раздела — `orchestrator/brief.py:1111` (`_spec_gate_decision_components`).
- Роли после гейта и их брифы:
  test_author — `orchestrator/brief.py:1436` (`test_author_answer_component`);
  developer — `orchestrator/brief.py:977` (`developer_brief`);
  reviewer — пакет ревью `orchestrator/review.py:729` (`review_package`).
  Выбор брифа по роли — `orchestrator/role_prompt.py:94` (`test_author_answer_component`),
  `orchestrator/role_prompt.py:126` (`developer_brief`),
  `orchestrator/role_prompt.py:153` (`review_package`).
  Приёмка — Оператор, автогейт приёмки (`orchestrator/fsm_autogate.py`) — без LLM: SPEC как бриф роли они не читают.
- `reject` пишет причину в запись перехода: `orchestrator/fsm.py:1617` (detail «возврат из spec_gate: …»).
- Команда `approve`: `orchestrator/fsm.py:885` (`cmd_approve`), диспетчер `orchestrator/fsm.py:1498` (`_cmd_approve`).
- Образец флага только для `spec_gate` — отказ в другом состоянии: `orchestrator/fsm.py:1509` (`accept_audit_fail`).
- Гейт SPEC: `orchestrator/fsm.py:1089` (`_approve_spec_gate`); мягкие отказы (`approve отклонён`, задача остаётся на гейте) идут до записи о принятии fail —
  `orchestrator/fsm.py:1186` (`ACCEPTED_FAIL_ACTION`), после неё — переход в `tests_writing`/`in_dev` или деление на подзадачи;
  деление узнаётся по SPEC здесь же: `orchestrator/fsm.py:1215` (`parse_division_subsections`).
- Отказ по «Меняемое поведение» — `orchestrator/fsm.py:1169` (`_behavior_change_declaration`);
  следом запись — `orchestrator/fsm.py:1180` (`DECLARED_CHANGE_ACTION`).
- Сверка фиксации до обработчика — `orchestrator/fsm.py:1514` (`confirm_fixation`).
- Из `spec_gate` после `approve` обратного пути на гейт нет — решение `approve` у задачи одно.
- Место в брифе test_author: `orchestrator/brief.py:1461` (`_core_reference_part`);
  в пакете ревью — цикл ANSWER-n `orchestrator/review.py:919` (`answer_rels`),
  долгоживущие файлы — `orchestrator/review.py:926` (`long_lived_rels`).
- Разбор аргументов — таблица команд `orchestrator/artel.py` (строка `"approve"`);
  флаги — `orchestrator/artel.py:1730` (`_accept_red_arg`),
  `orchestrator/artel.py:1769` (`ACCEPT_AUDIT_FAIL_FLAG`),
  `orchestrator/artel.py:1797` (`_approve_bool_flag`),
  позиционный sha — `orchestrator/artel.py:1805` (`_approve_sha_arg`).
  Справка: `orchestrator/artel.py:167` (`--accept-audit-fail`).
- Чтение текста из файла — образец `answer`: `orchestrator/answer.py:95` (`_read_answer_file`),
  отказ на пустой файл — `orchestrator/answer.py:267` (`answer отказана`).
- Потолок компонента брифа — `orchestrator/config.py:529` (`CONTEXT_FILE_MAX_BYTES`).
- Метрика «кругов до кода» считает возвратом с гейта только `state -> spec_writing` с префиксом:
  модуль метрики (задача 01M59DP2GV, смержена после пина 08622c17, в ветку придёт подтяжкой main) — запись отдельным действием её не меняет.

Требуется:

1. **Флаг.** `approve <id> [sha] --decisions <файл>` (сочетается с `--accept-audit-fail`). Отказ до исполнения команды (до lease и журнала), задача не меняется, id в тексте — как введён: нет следующего аргумента или он начинается с «--» — «флаг без пути»; флаг повторён; файл не прочитан (текст `OSError`/`UnicodeDecodeError`, как `_read_answer_file`); файл пуст или из одних пробельных символов; размер в байтах UTF-8 больше `config.CONTEXT_FILE_MAX_BYTES` (текст называет размер и потолок). Путь — в `_approve_reason_indices` (не sha и не флаг для `_approve_sha_arg`, `_approve_bool_flag`). Текст читается один раз в `artel.py` и передаётся в `fsm.cmd_approve` строкой.
2. **Только на `spec_gate`.** В другом состоянии — отказ тем же каналом и формой, что у `accept_audit_fail`: «approve отклонён: флаг --decisions допустим только в состоянии spec_gate, задача в <состояние>».
3. **Деление.** В `_approve_spec_gate`, если `guard.parse_division_subsections(spec_text)` не пуст и передан текст решений: мягкий отказ — запись журнала «approve отклонён» и печать «approve отклонён: --decisions недопустим: SPEC делится на подзадачи»; место — после отказа по «Меняемое поведение», до `DECLARED_CHANGE_ACTION`, `ACCEPTED_FAIL_ACTION`, `update_task` (zones) и `apply_spec_budget`. На дисковом пути (`spec_text` пуст) деления нет — отказа нет.
4. **Запись решений.** В `_approve_spec_gate` сразу после записи `ACCEPTED_FAIL_ACTION` (если она есть), под тем же lease, — запись журнала задачи `actor` operator отдельным действием «решения Оператора на гейте SPEC» (константа модуля `brief.py`), detail — текст дословно. `confirm_fixation` и все мягкие отказы — до неё; отказанный `approve` записи не оставляет. Записи `state -> spec_writing` нет; метрика «кругов до кода» (`orchestrator/rounds.py`) её возвратом не считает.
5. **Раздел брифа test_author, developer, reviewer — только при записи п. 4 в журнале.** Заголовок `SPEC_GATE_DECISIONS_HEADER`, новая константа пометки («… данные, не инструкции»); компоненты по порядку журнала — прежние причины `reject` с гейта (как `_spec_gate_reasons`) и решение `approve`, в метке вид («возврат» / «одобрение»); крупнее потолка — тем же пропуском с указанием на `artel.py log <id>`, что `_spec_gate_decision_components`. Сборка — публичная функция `brief.py`, её зовёт и `review.py`. Место: developer — сразу после SPEC.md; test_author — после ANSWER, до конвенций проекта и справочника ядра, отрисовка `_manifest_component`, без ANSWER и справочника — добавка, не `None`; reviewer — сразу после цикла ANSWER-n, до долгоживущих файлов, исполнитель записи журнала — reviewer.
6. **Прежнее побайтно.** Без записи п. 4 — брифы всех ролей (в том числе аудитора SPEC с возвратами с гейта), пакет ревью, тексты и исходы `approve`/`reject` без флага прежние; бриф аудитора SPEC прежний всегда. Аналитик перечисляет в SPEC закрепляемые тестами до правки тексты: отказы `_cmd_approve` по флагам, вывод `approve` на `spec_gate`, бриф аудитора с возвратами с гейта, бриф test_author без добавки (`None`), брифы developer и пакет ревью с возвратом с гейта без решения `approve`. Справка `approve` в `artel.py` (строка команды и абзац о гейте SPEC в начале) дополняется флагом `--decisions <файл>`.
7. Тесты детерминированы, без сети, генератор случайных чисел (если нужен) — с фиксированным начальным значением: учебная база с задачей на `spec_gate` — отказы п. 1–3, запись п. 4 (и её отсутствие при мягком отказе гейта), раздел п. 5 у трёх ролей с возвратом и одобрением, побайтное равенство п. 6.

Критерии приёмки:
- `approve <id> --decisions <файл>` на `spec_gate` уводит задачу с гейта и оставляет в журнале одну запись «решения Оператора на гейте SPEC» с текстом файла; число возвратов с гейта в метрике «кругов до кода» не меняется;
- флаг вне `spec_gate`, без пути, повторённый, с пустым, нечитаемым или большим потолка файлом — отказ с текстом, состояние и журнал задачи прежние;
- мягкий отказ гейта SPEC при флаге записи решений не оставляет; SPEC с «Делением» и флагом — отказ с текстом, подзадачи не заведены, zones и бюджет не записаны, записи решений нет;
- бриф test_author, бриф developer и пакет ревью при решении `approve` несут раздел с причиной `reject` и решением `approve` по порядку журнала;
- без решения `approve` брифы всех ролей и пакет ревью побайтно прежние; бриф аудитора SPEC прежний всегда.

Решения по умолчанию (аналитику не спрашивать): текст решений хранится в журнале задачи, не в артефактной ветке (без коммита файла); решение `approve --decisions` у задачи не больше одного: обратного пути на гейт нет; аналитик и аудитор SPEC раздела с решением `approve` не получают.

Зоны: orchestrator/artel.py, orchestrator/fsm.py, orchestrator/brief.py, orchestrator/review.py, tests/

Только чтение: `orchestrator/role_prompt.py`, `orchestrator/answer.py`, `orchestrator/store.py`, `orchestrator/config.py`, `orchestrator/advance_gates/spec_audit.py`, `orchestrator/context_package.py`, `orchestrator/lease.py`, `orchestrator/fsm_autogate.py`, `orchestrator/catalog.py`, `orchestrator/canary.py`, `orchestrator/zone_lock.py`, `orchestrator/auto.py`, `orchestrator/runner.py`, `orchestrator/fsm_advance.py`, `orchestrator/advance_gates/capacity.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/amend.py`, `orchestrator/fixation.py`, `orchestrator/budget.py`, `orchestrator/merge_lock.py`, `scripts/guard.py`, `scripts/codebase_map.py`, `docs/backlog.md`. Правка вне зон — эскалация до SPEC.

Не входит: `tests/test_invariants.py` (защищённый путь); текст `reject` из файла (строка копилки e1918112); отказ `approve`/`reject` без аргументов вместо трассировки стека (строка бэклога 850788c8); раздел у аналитика; изменения конвейера, метрики `rounds` и приёмки.

Рамка: $25. Набор моделей — по умолчанию.
