---
task: 01M1SHJX22EMEP4AJ9FFJJ09DC
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 5
---

# REVIEW: approve без набора sha: сверка фиксации механикой; перечитывание budget_usd на гейте SPEC

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (confirm_fixation сверяет живой sha с `tasks.fixed_sha` на 4 гейтах) | OK | Без изменений с итерации 1 — `orchestrator/fsm.py:575-600`, узел не тронут этой итерацией (R1-F2 правит только текст подсказки, не саму сверку); `test_ac2_matching_fixation_auto_confirms.py` — 2/2 (прогнано). |
| 2 (явный `approve <id> <sha>` — прежняя семантика) | OK | Ветка `sha is not None` (`orchestrator/fsm.py:601-615`) не тронута; `test_ac4_explicit_sha_semantics_unchanged.py` — 3/3 (прогнано), `tests/test_git_fixation.py` — 43/43 (прогнано). |
| 3 (удаление строки «sha только копированием» из `docs/operator-session.md`, диффом-приложением) | OK | Без изменений с итерации 1: строка на месте в файле (`docs/operator-session.md:133-134`), не закоммичена кодовой веткой (`git diff cd044f02 -- docs/operator-session.md` пуст); дифф-приложение PLAN.md применяется чисто — независимо перепроверено `git apply --check` на текущем HEAD. |
| 4 (approve на spec_gate перечитывает `budget_usd` из SPEC и применяет `apply_spec_budget`) | **OK — R1-F1 закрыт** | `orchestrator/budget.py:91-103` теперь различает `source == BUDGET_SOURCE_OPERATOR` (отказ всегда) и `source == BUDGET_SOURCE_SPEC and value == old` (отказ только при совпадении, иначе применяет новое значение). Мотивирующий сценарий SPEC («Контекст»: SPEC $35, потолок остался $45) воспроизведён и проверен обратным путём: `tests/test_spec_budget.py::test_approve_on_spec_gate_reapplies_a_changed_spec_value` — потолок $45 -> $35 на втором чтении, тест зелёный. |
| 5 (журнал при изменении потолка, без дублей при совпадении) | OK, вытекает из 4 | `test_approve_on_spec_gate_reapplies_a_changed_spec_value` (журнал: новая запись `"$35.00 (прежний потолок $45.00, ...)"`) и `test_approve_on_spec_gate_does_not_reapply_an_unchanged_spec_value` (журнал без дублей) — оба зелёные, оба закрывают именно тот разрыв, что был найден в R1-F1. |
| 6 (инвариант 25, `docs/invariants.md`) | OK (осознанно не в этой задаче) | Без изменений с итерации 1 — по ANSWER-3 файл возвращён к `origin/main` (`git diff origin/main -- docs/invariants.md` пуст), AC-9 `manual` с обоснованием остаётся легитимным. |

## Замечания

- **minor** — `tests/test_git_fixation.py:895` (`test_approve_without_sha_on_diverged_fixation_is_refused_and_names_both_shas`), `tests/test_git_fixation.py:925` (`test_approve_without_sha_on_dirty_copy_is_refused_and_state_unchanged`), `tests/test_spec_budget.py:540` (`test_approve_on_spec_gate_does_not_reapply_an_unchanged_spec_value`) — три из четырёх постоянных тестов, добавленных этой итерацией для R1-F3, несут содержательный докстринг (сценарий + наблюдаемое свойство описаны), но БЕЗ обязательной строки `Ловит мутацию: …` (`skills/test-authoring.md`, раздел «Чувствительность: у теста — заявленная мутация»; тот же пункт закреплён в `skills/review-checklist.md`, Фаза B п.3, как предмет проверки ревьювера). Четвёртый новый тест той же итерации, `tests/test_spec_budget.py::test_approve_on_spec_gate_reapplies_a_changed_spec_value` (строка ~520), тег несёт — конвенция файла соблюдена локально, но не во всех новых методах.
  Сами тесты по существу корректны и действительно ловят регрессии R1-F1/R1-F2 (проверено чтением ассертов и прогоном — `tests/test_git_fixation.py` 43/43 OK, `tests/test_spec_budget.py` 46/46 OK), дефект чисто в докстринге, не в логике теста.
  Предложение: добавить в каждый из трёх докстрингов строку `Ловит мутацию: <конкретная правдоподобная мутация>` — например, для `test_approve_without_sha_on_diverged_fixation_is_refused_and_names_both_shas` это подстановка `{fixed or current}` вместо `{current}` в подсказке повтора (регресс R1-F2); для `test_approve_without_sha_on_dirty_copy_is_refused_and_state_unchanged` — пропуск проверки `clean` при совпадающем sha; для `test_approve_on_spec_gate_does_not_reapply_an_unchanged_spec_value` — сравнение `source is not None` вместо `source == ... and value == old` (тот же класс регрессии, что и в соседнем тесте, у которого тег уже есть).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/budget.py:91-103 | `apply_spec_budget` не перечитывала изменённое значение из SPEC при `budget_source=spec` | Требование 4/5 не работало для мотивирующего сценария SPEC | Проверено: `source == BUDGET_SOURCE_OPERATOR` → отказ всегда; `source == BUDGET_SOURCE_SPEC and value == old` → отказ только при совпадении, иначе применяет и журналирует. `test_approve_on_spec_gate_reapplies_a_changed_spec_value`/`test_approve_on_spec_gate_does_not_reapply_an_unchanged_spec_value` зелёные (прогнано лично), сценарий из «Контекст» SPEC воспроизведён обратным путём и закрыт. |
| R1-F2 | accepted | orchestrator/fsm.py:591-599 | Подсказка повтора при расхождении sha называла зафиксированный (`fixed`) sha вместо живого (`current`) | Подсказанная команда детерминированно проваливалась повторно | Проверено: подстановка заменена на `{current}`; `test_approve_without_sha_on_diverged_fixation_is_refused_and_names_both_shas` явно проверяет `f"approve {self.TASK} {live_sha}"` в выводе — зелёный (прогнано лично). |
| R1-F3 | accepted | tests/test_git_fixation.py, tests/test_spec_budget.py | Новая логика (confirm_fixation при sha=None, перечитывание бюджета) не имела постоянного покрытия в `tests/` | Регрессия не ловилась бы после исчезновения эфемерной `acceptance_tests/` | Проверено: 4 постоянных теста добавлены и зелёные (прогнано лично, `test_git_fixation.py` 43/43, `test_spec_budget.py` 46/46) — сценарии расхождения/грязной копии/изменения значения/идемпотентности закрыты. Разметка докстрингов трёх из четырёх тестов — отдельная новая находка R2-F1, не отменяет закрытие самого R1-F3 (тесты по существу корректны). |
| R2-F1 | open | tests/test_git_fixation.py:895,925; tests/test_spec_budget.py:540 | Три из четырёх новых постоянных тестов (закрывающих R1-F3) без обязательной строки `Ловит мутацию: …` в докстринге | Ревьювер/будущий читатель не может сверить тест с заявленной мутацией без чтения кода теста; нарушает локальную конвенцию файла (четвёртый новый тест этой же итерации тег несёт) | См. замечание выше — добавить строку `Ловит мутацию: …` в каждый из трёх докстрингов. |

## Вердикт

changes_requested — R2-F1 (minor) обязателен к исправлению: реестр не закрыт целиком (гейт `review -> verifying` не пропустит `approved` при открытой записи), сама правка тривиальна (три строки докстринга, без изменения кода/тестовой логики). Блокеров и major-замечаний не найдено — R1-F1/F2/F3 закрыты по существу, код и постоянные тесты корректны.

## Проверено исполнением

- `python3 -m unittest tests.test_spec_budget tests.test_git_fixation -v` — 87/87 OK.
- `python3 -m unittest tests.test_cmd_approve_dispatch tests.test_zones_approve -v` — 9/9 OK.
- `python3 -m unittest discover -s tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/acceptance_tests -p "test_ac*.py" -v` — 16/16 OK (все исполняемые критерии планки; AC-5/AC-9 — manual с обоснованием, без изменений с итерации 1).
- `python3 scripts/guard.py tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/PLAN.md tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md` — ок.
- `git apply --check` на извлечённом из PLAN.md unified-диффе `docs/operator-session.md` — применяется чисто на текущем HEAD.
- `git diff origin/main -- docs/invariants.md` — пуст (ANSWER-3 исполнена).
- `git diff origin/main...HEAD --stat` — только `docs/codebase-map.md`, `orchestrator/budget.py`, `orchestrator/fsm.py`, `tests/test_git_fixation.py`, `tests/test_spec_budget.py`: соответствует зоне SPEC (`orchestrator/fsm.py, orchestrator/fixation.py, orchestrator/fsm_advance.py, orchestrator/budget.py, tests/`) плюс разрешённая регенерация карты; посторонних файлов нет.
- Читал `git show 916fb81b` (фактический фикс-коммит R1-F1/F2/F3, диф `orchestrator/budget.py`/`orchestrator/fsm.py`) — код совпадает с описанием в PLAN.md/реестре.
- `python3 scripts/codebase_map.py` — прогнан для проверки свежести: диф только в строке `built_at_sha` (законное отставание на 1 коммит по построению — self-reference, скил review-checklist п. про `built_at_sha`), содержимое карты идентично; изменение отменено (`git checkout -- docs/codebase-map.md`), рабочее дерево не менял.
- Полный набор `tests/` не гонял (запрещено скилом ревьювера — гоняет CI; CI коммита 916fb81b зелёный, 14 проверок, согласно пакету).

## Предложения системе

- Класс «докстринг теста содержателен, но без обязательной строки `Ловит мутацию: …»` проскочил мимо самого автора в одном и том же коммите (3 из 4 новых тестов) — стоит рассмотреть grep-проверку в guard/CI на наличие этой строки у каждого нового/изменённого `def test_...` (симметрично уже существующей проверке AC-пометок в acceptance_tests).
