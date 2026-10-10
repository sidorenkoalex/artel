---
task: 01M4JN2EDQP8Q3WVYK0TS95ZVC
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Сетевые адреса в tests/ — пульт ловит до CI

## Фаза A: план
- Покрытие требований полное: 1 → шаги 1, 4; 2 → шаги 1, 5; 3 → шаги 2, 3;
  4 → шаг 1. Шаг 5 (итерация 2) закрывает R1-F1.
- «Влияние на систему» теперь совпадает с кодом. Выход из `tests_writing`
  строже только у артели (`fsm_advance.py:468`, `repo_context.is_artel(target)`).
  Остаток в `amend-tests` назван честно: `orchestrator/amend.py:510` зовёт
  узел без флага, а файл только для чтения. Это подтверждает grep по
  потребителям `long_lived_errors_from_files`: вызовов ровно три, это
  `amend.py:510`, `tests_writing.py:339` и `:458`.
- Приложение 1 к `tests/test_invariants.py` в итерации 2 не менялось.
  В итерации 1 я проверял его через `git apply --check` и временным
  наложением.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Правило живёт в `scripts/guard.py`. Инвариант 35 зовёт `guard.network_address_hits` по приложению, утверждения не меняются (проверено в итерации 1). |
| 2 | OK | Признак адресов в `long_lived_errors_from_files` работает за флагом `network_addresses` (`guard.py:2792`). Отказ идёт тем же путём, что прочие признаки, в тексте есть файл:строка. У артели флаг включён, у чужого проекта снят (`fsm_advance.py:465-474`). |
| 3 | OK | `_network_address_gate` в итерации 2 не менялся. Ранее проверено: читаются только файлы диффа, при сбое git — отказ. |
| 4 | OK | Четыре пары исключений не тронуты. AC-5 и AC-6 зелёные в долгоживущем файле и в планке. |

## Замечания
Новых замечаний нет.

- Флаг `network_addresses` — именованный, с умолчанием `True`.
  Зафиксированный долгоживущий файл зовёт `long_lived_errors_from_files`
  без флага, поэтому остаётся зелёным. Прочие вызовы поведения не меняют.
- В `test_network_address_sign_only_for_artel`
  (`tests/test_fsm_advance_tests_writing_test_groups.py:161`) второй отказ
  у чужого проекта даёт имя файла планки (`test_ac.py` не по шаблону
  долгоживущего). Поэтому `len == 1` держится, а мутацию проверяет
  `assertNotIn("инвариант 35", …)`. Если подставить `network_addresses = True`,
  этот detail содержит «инвариант 35», и тест краснеет. Заявка исполнима.
- `LongLivedNetworkAddressScopeTest.test_guard_flag_drops_only_address_sign`
  сверяет, что флаг снимает ровно признак адресов
  (`[e for e in on if "инвариант 35" not in e] == off`) и что `off`
  непуст. Обе части заявки наблюдаемы.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | scripts/guard.py:2766, 2792; tests_writing.py:309, 422; fsm_advance.py:468 | Признак адресов инварианта 35 действовал для любого проекта с профилем | У чужого проекта был бы отказ по неприменимому правилу | Исправлено. Флаг `network_addresses` проброшен через оба гейта, `fsm_advance.tests_writing` передаёт `is_artel(target)`. Остаток в amend.py:510 описан в PLAN. Тесты: `LongLivedNetworkAddressScopeTest`, `test_network_address_sign_only_for_artel` — зелёные. |
| R1-F2 | accepted | orchestrator/advance_gates/tests_writing.py:60 | Отказ рубежа адресов — общее «переход отклонён» без суффикса | В журнале отказ отличает только `detail` (minor) | Отклонение обосновано: `refusal_classes.py` вне зон задачи. Компромисс записан в «Рисках» PLAN, предложение — в «Предложениях системе». Принимаю. |

## Вердикт
approved — R1-F1 исправлено по существу, обоснование отклонения R1-F2
принято, новых blocker/major нет.

## Проверено исполнением
- `python3 -m pytest -q tests/test_network_address_gate.py tests/test_fsm_advance_tests_writing_test_groups.py tests/test_01m4jn2edqp8q3wvyk0ts95zvc_network_address.py tests/test_long_lived_transitions.py tests/test_amend.py tests/test_fsm_advance_gate_smoke.py`
  — 70 passed, 50 subtests passed (69 с).
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4JN2EDQP8Q3WVYK0TS95ZVC`
  — 5 passed, код выхода pytest 0. Рабочее дерево после прогона чистое.
- `grep -n long_lived_errors_from_files orchestrator/ scripts/` — три
  вызова (`amend.py:510`, `tests_writing.py:339`, `:458`), как описано в PLAN.
- Временную мутацию `fsm_advance` (`network_addresses = True`) запустить не
  удалось: правка через sed не прошла подтверждение среды. Чувствительность
  `test_network_address_sign_only_for_artel` я разобрал по коду теста
  (см. «Замечания»). Разработчик в PLAN тоже отчитался об этой мутации.
- CI коммита 80cbaa11 зелёный (16 проверок, из пакета).

## Предложения системе
- Временная мутация ревьювера через `sed -i` в шаге требует подтверждения,
  которого никто не даст. Приём «временная мутация» из
  `skills/review-checklist.md` на практике выполним только через Edit с
  возвратом. Стоит упомянуть это в скиле.
