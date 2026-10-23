---
task: 01M5KP57JXWKKKCJKY47HT21W8
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

# Мандат Оператора (23.10.2026): правка двух существующих тестов миссии ревьювера (CR-2, решение А)

Ослабление тестов разрешено: tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::MissionTest::test_ac7_external_reviewer_mission_keeps_suite_run
Ослабление тестов разрешено: tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py::Ac8ReviewerChecksTest::test_ac8_external_reviewer_lists_pult_check_commands

Решение Оператора 23.10.2026 (находка CR-2026-10-22-2, вариант А): ревьюверу полный набор тестов запрещён; правило одно — `REVIEWER_FULL_SUITE_RULE` в миссии шага. Оба теста требуют `suite-run` в перечне команд ревьювера внешнего проекта и противоречат решению. Сценарии тестов не меняются; меняется только ожидание о `suite-run`:
- `test_ac7_external_reviewer_mission_keeps_suite_run`: вместо «миссия содержит `` `<pult> suite-run <id>` — полный набор тестов ``» — миссия содержит `role_prompt.REVIEWER_FULL_SUITE_RULE`, `` `<pult> plank-run <id>` `` и `` `<pult> guard <id>` ``, и в ней нет `suite-run <id>` без ` --failed`/` --wait`. Имя метода может отразить новое ожидание.
- `test_ac8_external_reviewer_lists_pult_check_commands`: перечень команд — `guard` и `plank-run` с полным путём пульта (вместо `guard`, `plank-run`, `suite-run`); «Права не сужены» по-прежнему нет; добавить: нет `suite-run <id>` без ` --failed`/` --wait`.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::MissionTest::test_ac7_external_reviewer_mission_keeps_suite_run — ожидание `suite-run <id>` в миссии ревьювера внешнего проекта | ревьювер внешнего проекта получает команду полного прогона — tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py:680 | нет — снимается решением Оператора 23.10 (вариант А): полный набор гоняют CI и гейты пульта | обратное свойство «полного прогона в миссии ревьювера нет»: tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py (заменённое утверждение), tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py | ок: решение Оператора 23.10 |
| tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py::Ac8ReviewerChecksTest::test_ac8_external_reviewer_lists_pult_check_commands — `suite-run` в перечне команд ревьювера внешнего проекта | перечень `guard`, `plank-run`, `suite-run` — tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py:203 | для `guard` и `plank-run` — да; для `suite-run` — нет, снимается решением Оператора 23.10 | tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py (утверждения `guard`, `plank-run`, «Права не сужены» остаются; добавлено отсутствие `suite-run <id>` без флагов), tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py | ок: решение Оператора 23.10 |
| tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py::Ac8ReviewerChecksTest::test_ac8_external_reviewer_lists_pult_check_commands — «Права не сужены» в миссии ревьювера внешнего проекта | tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py:202 | да | tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py:202 (утверждение не меняется) | ок |
| tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::MissionTest::test_ac7_external_reviewer_mission_keeps_suite_run — прочие свойства сценария (песочница, внешний проект, пустые компоненты брифа) | tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py:680–705 | да | tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py (сценарий прежний), tests/test_01m5kp57jxwkkkcjky47ht21w8_reviewer_full_suite_rule.py (миссии остальных ролей без правила) | ок |

Независимая проверка: адреса утверждений сверены с деревом пина 23.10 (`test_ac7…` — :680–705, `test_ac8…` — :185–204); замена сохраняет сценарии и все утверждения, кроме ожидания `suite-run`, которое снимается решением Оператора.
