---
task: 01M1THKTJ7YT1K410G1KS17MK6
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 4
---

# REVIEW: ADR-0014, часть 1 — потолок ролей и обязательный budget_usd в SPEC

## Фаза A: проверка плана

PLAN не менялся со времени итерации 1 (правки этой итерации — только
код и тесты по замечаниям R1-F1/R1-F2, коммит `b0008ec0`). Покрытие
требований, размер шагов, обоснование двух независимых guard-проверок
и канал диф-приложения к защищённым путям — без изменений, замечаний
по плану нет (см. оценку итерации 1, она остаётся в силе).

## Соответствие SPEC

Ревью-пакет этой итерации нёс инкрементальный diff от sha `b0008ec0` до
HEAD (`dce4738e`) — тот sha сам оказался коммитом-фиксом разработчика
(`закрыты замечания ревью (R1-F1, R1-F2)`), поэтому показанный diff нёс
только шум последующей подтяжки main (ADR-0015 статус, `docs/backlog.md`,
чужой `ANSWER-1.md`) и не показывал сам фикс. Свёл вручную: `git show
b0008ec0` (сам фикс) и `git diff main...HEAD` (весь код задачи целиком,
9 файлов, 292/56) — обе команды в «Проверено исполнением».

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `ROLE_BUDGET_CAP = 100.0` с комментарием-ссылкой на ADR-0014, `DEFAULT_BUDGET_USD` не тронут (orchestrator/config.py:139-146). |
| 2 | OK | `SUPPORTED_SCHEMA_VERSION = 5`; `requires_budget_field`/`spec_budget_field_errors` версия-гейтингованы на `>= 5`, только `type: spec` (scripts/guard.py:1002-1052). |
| 3 | OK | `role_budget_cap_errors` без версии-гейтинга, `type in (spec, plan)` (scripts/guard.py:1060-1072), подсказка называет и деление, и эскалацию. |
| 4 | OK | `budget.spec_budget` сравнивает с `ROLE_BUDGET_CAP`, применяет в обе стороны; потолок Оператора не перебивается — `tests/test_spec_budget.py`, `SpecCeilingRespectsRoleBudgetCapTest`. |
| 5 | OK (было «реализовано не так» в R1) | `orchestrator/artel.py:34-42` теперь явно разводит два случая: «мусор в поле — предупреждение, прежний потолок» и «выше потолка ролей — guard отказывает переход целиком, задача остаётся в spec_writing». R1-F1 закрыто по существу. |
| 6 | OK | `orchestrator/budget.py` вне `spec_budget` не тронут; `ExhaustedBudgetIsNotBypassableTest`, `test_step_cost.CmdBudgetTest` зелёные без правок (см. «Проверено исполнением»). |
| 7 | OK | `docs/invariants.md:37`, инвариант 10, переформулирован буквально по тексту требования, ссылка на новый тестовый класс на месте. |
| 8 | OK | `SPLIT_SIGNAL_BUDGET_USD = 60` (orchestrator/config.py:372), строго между 45 и 70, именованная константа с комментарием-обоснованием. |
| 9 | OK | Оба диффа-приложения (`templates/*.md`, `skills/spec-authoring.md`) прошли `git apply --check` на чистом дереве — перепроверено независимо (см. «Проверено исполнением»). |
| 10 | реализовано не так (частично) | Логика и покрытие сценариев верны и подтверждены прогоном, но докстринги новых/изменённых тестовых методов не несут обязательной заявки `Ловит мутацию: …` (skills/test-authoring.md) — см. замечание R2-F1. |

## Замечания

- minor — `tests/test_spec_budget.py:100,117,127,133,335,366` и
  `tests/test_invariants.py:923(класс),957,984` — ни один из
  новых/изменённых тестовых методов этой задачи не несёт в докстринге
  обязательной заявки `Ловит мутацию: <что сломали>` (skills/
  test-authoring.md, требование к каждому тестовому методу; review-
  checklist Фаза B.3: «заявки нет вовсе → замечание»). Докстринги сами
  по себе неплохие — описывают сценарий и наблюдаемое свойство прозой
  (например, `test_value_above_the_role_cap_blocks_the_transition`
  явно называет, что сломалось бы при старой семантике), но без
  литеральной строки `Ловит мутацию: …` следующий ревьювер не может
  механически сверить заявленную мутацию с фактическим поведением
  теста — именно этот приём и требует скил, а не мысленную реконструкцию
  по прозе. Список полностью (класс целиком, не первый попавшийся):
  - `tests/test_spec_budget.py:100` `test_value_above_the_role_cap_is_refused`
  - `tests/test_spec_budget.py:117` `test_value_above_the_default_but_within_the_role_cap_is_taken`
  - `tests/test_spec_budget.py:127` `test_value_equal_to_the_default_is_taken` (докстринг переформулирован под новую семантику, заявки не было и до этой задачи — тоже в зоне правки)
  - `tests/test_spec_budget.py:133` `test_value_equal_to_the_role_cap_is_taken`
  - `tests/test_spec_budget.py:335` `test_value_above_the_role_cap_blocks_the_transition`
  - `tests/test_spec_budget.py:366` `test_value_above_the_default_but_within_the_role_cap_becomes_the_ceiling`
  - `tests/test_invariants.py:957` `SpecCeilingRespectsRoleBudgetCapTest.test_guard_refuses_the_spec_before_any_ceiling_change`
  - `tests/test_invariants.py:984` `SpecCeilingRespectsRoleBudgetCapTest.test_operator_ceiling_survives_a_spec_value_within_cap`
  Предложение: добавить строку `Ловит мутацию: …` в каждый из восьми
  докстрингов (например, для `test_guard_refuses_the_spec_before_any_ceiling_change`:
  «Ловит мутацию: сравнение `> ROLE_BUDGET_CAP` подменено на `>=`
  дефолт или снято вовсе — SPEC с завышенным `budget_usd` прошёл бы
  `check_content` без ошибки»). `tests/test_guard_split_signals.py`
  этой задачи замечание не касается — там заявка была и осталась
  (строка 279 и далее), правка только объяснила смену фикстуры.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/artel.py:34-42 | Справка `--help` описывала старую мягкую семантику вместо жёсткого блока guard'ом | Оператор не понял бы, почему задача зависла в `spec_writing` | Проверено: абзац переписан именно так, как требовало R1-F1 (два явно разведённых случая — мусор/выше потолка), текст сверен с фактическим кодом guard/budget. Закрываю. |
| R1-F2 | accepted | tests/test_spec_budget.py:2-9 | Модуль-докстринг описывал старую семантику «отказ выше дефолта» | Разработчик ориентировался бы по неверной шапке файла | Проверено: докстринг переписан ровно на предложенную формулировку («отказ от значения выше потолка ролей ROLE_BUDGET_CAP…»). Закрываю. |
| R2-F1 | open | tests/test_spec_budget.py:100,117,127,133,335,366; tests/test_invariants.py:957,984 | Восемь новых/изменённых тестовых методов без обязательной заявки `Ловит мутацию: …` в докстринге | Следующий ревьювер/разработчик не может механически сверить заявленную мутацию с поведением теста — снижает ценность теста как документации инварианта | Добавить строку `Ловит мутацию: …` в каждый из восьми докстрингов (см. замечание выше); отметить запись `fixed` в PLAN/следующей итерации REVIEW тем же id |

## Вердикт

changes_requested — один minor (R2-F1). R1-F1 и R1-F2 из итерации 1
проверены и закрыты (`accepted`) — по существу исправлены, текст
сверен с фактическим кодом. Логика, guard-проверки, семантика
`budget.spec_budget`, инвариант 10 и калибровка `SPLIT_SIGNAL_BUDGET_USD`
— всё корректно и покрыто тестами; единственное открытое замечание —
формальное отсутствие заявки `Ловит мутацию: …` в докстрингах новых
тестов, не влияет на корректность кода. Реестр не закрыт целиком (R2-F1
`open`), поэтому `approved` не ставлю — гейт `review -> verifying` его
всё равно отклонит, пока запись не станет `accepted`.

## Проверено исполнением

- `git log --oneline main..HEAD` и `git show b0008ec0 --stat` — сверил
  реальный код фикса R1-F1/R1-F2, т.к. инкрементальный diff пакета
  (`b0008ec0...HEAD`) его не показывал (base sha пакета сам оказался
  этим фикс-коммитом, дальше в ветке — только подтяжка main).
- `git diff main...HEAD --stat` — 9 файлов (`docs/codebase-map.md`,
  `docs/invariants.md`, `orchestrator/{artel,budget,config}.py`,
  `scripts/guard.py`, `tests/{test_guard_split_signals,test_invariants,
  test_spec_budget}.py`), 292 insertions/56 deletions — совпадает с
  зонами SPEC и разделом «Влияние на систему» PLAN.md один в один,
  side effects вне зоны нет.
- `python3 -m unittest tests.test_spec_budget tests.test_guard_split_signals tests.test_invariants tests.test_step_cost`
  — 167 тестов, все зелёные (~115s).
- `python3 -m unittest tests.test_guard_schema -v` —
  `TemplatesCarryTheVersionTest` красный (4 подслучая, `4 != 5`) —
  ожидаемое, задокументированное в PLAN.md временное состояние до
  применения диф-приложения Оператором (тот же класс, что прецедент
  01M1NKVPD2A79PQ6K0JVV1B2Q1), не дефект этой задачи.
- `python3 -m pytest tasks/01M1THKTJ7YT1K410G1KS17MK6/acceptance_tests -q`
  — 35 тестов, все зелёные.
- `git apply --check` на чистом дереве для обоих диффов-приложений из
  PLAN.md (извлечены скриптом из блоков ```diff```) — оба применяются
  без ошибок, перепроверено независимо.
- `grep -rn "role_budget_cap_errors\|requires_budget_field\|spec_budget_field_errors\|ROLE_BUDGET_CAP" docs/codebase-map.md`
  — новые функции и константа присутствуют в карте, регенерация после
  подтяжки main (коммит `b0008ec0`, `built_at_sha` поднят с `52aa4de3`
  на `8b18ec85` — коммит слияния) выполнена корректно.

## Предложения системе

- Ревью-пакет этой итерации указал SPEC.md и PLAN.md задачи как «не
  показан: в ветке файл не найден; в дереве файл не найден» — оба
  файла реально существуют в рабочем каталоге шага
  (`tasks/01M1THKTJ7YT1K410G1KS17MK6/{SPEC,PLAN}.md`, подтверждено
  `find`/`Read`). Ложное «не найден» для файлов, которые есть на
  диске, — риск: ревьювер, доверяющий описи буквально, мог бы
  эскалировать «SPEC потерян» вместо трёхминутной проверки диска.
