---
task: 01M6N7CYKDAMAKENX60CBK7VQX
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ослабление тестов разрешено: tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py
Ослабление тестов разрешено: tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py
Ослабление тестов разрешено: tests/test_epic_draft_promote_unsupported_project.py

Основание: решения Оператора 05.11.2026 по QUESTIONS.md аналитика (вопросы 1 и 2).

## Вопрос 1 — мандат: вариант A

Объём мандата — только правка, которую требует открытие пары `github` + `target-human` (требование 1 ТЗ): параметр `("github", "target-human")` переносится из отказных случаев в поддержанные (`UNSUPPORTED`, `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:41-50`; `tests/test_epic_draft_promote_unsupported_project.py:24`, `:58-59`), тесты `test_ac2_github_target_human_reason_exact` и `test_ac2_github_target_human_actions_refuse` (`tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:188-223`) переходят от утверждения отказа к утверждению поддержки, `test_ac4_support_constants_exact` (`:266-280`) и точное сравнение констант поддержки в `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:172-174` — к новому составу `SUPPORTED_PAIRS`, `test_ac4_reason_text_names_pair_and_supported_list` (`tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:283-313`) — параметр `github-target-human` уходит из отказных, тексты причин в его коде (`:285-289`) и утверждение перечня (`:310`) — к новому перечню пар, тексты причин в константах (`GITLAB_REASON`/`TARGET_HUMAN_REASON`, `GHTH_REASON`/`GLOP_REASON`) — к новому перечню пар «github + operator, github + target-human, gitlab + target-human». Отказ `gitlab` + `operator` во всех действиях этих файлов (`new`, `run`, `auto`, `approve`, `epic draft promote`, строка `project-support` — `fail`) сохраняется с точным новым текстом причины. Поддержанные случаи `run`, `auto`, `approve` не доходят до настоящего `gh`: `ci.gh` подменён подделкой или действие останавливается ранним `Halt` после проверки поддержки. Гейт засчитывает мандат по пути файла, поэтому при `approve` дифф этих файлов сверяется с условиями матрицы: число случаев `gitlab` + `operator` не уменьшилось, точные равенства сохранены. Иные правки этих файлов, удаление случаев `gitlab` + `operator`, `skip`/`xfail` и правка прочих существующих тестов мандатом не разрешены.

Условие-замена: SPEC задаёт отдельными критериями (а) отказ `gitlab` + `operator` во всех перечисленных действиях с новым точным текстом причины и (б) поддержку `github` + `target-human` в тех же действиях без настоящего `gh`.

## Вопрос 2 — объём: вариант B

Монолит, рамка поднята до $85 (калибровка «больше 10 критериев и 8+ файлов»); `budget_usd: 85`. Деление не нужно: запреты требований 7–9 без открытия пары недостижимы в живом пути, а открытие без них небезопасно.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` — параметр `github` + `target-human` уходит из `UNSUPPORTED`, тексты `GITLAB_REASON`/`TARGET_HUMAN_REASON` — новый перечень пар | каждая неподдержанная пара отказывает в `new`, `run`, `auto`, `approve` и строке `project-support` (`test_ac1`…`test_ac7`, `:149-391`) | да: свойство «неподдержанная пара отказывает во всех действиях» держится на единственной оставшейся неподдержанной паре `gitlab` + `operator`; покрытие второй пары уходит вместе с её неподдержанностью (требование 1) | те же тесты на `gitlab` + `operator` с новым текстом причины + новые критерии SPEC (а) и (б) | ок при условии: в файле остаются все действия для `gitlab` + `operator` с точным текстом причины, константы поддержки (`:172-174`) сравниваются точно, а SPEC содержит критерии (а) и (б) |
| `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py` — `test_ac2_github_target_human_*` утверждают поддержку вместо отказа, `test_ac4_support_constants_exact` — новый состав `SUPPORTED_PAIRS`, константы причин — новый перечень | точный текст и отказ обеих неподдержанных пар; точный состав констант поддержки | да: точный состав констант утверждается по-прежнему (новый); отказ и точный текст `gitlab` + `operator` (`test_ac3_*`) остаются | этот же файл + критерий SPEC (б) | ок при условии: `test_ac3_*`, `test_ac4_support_constants_exact` и `test_ac4_reason_text_names_pair_and_supported_list` (случай `gitlab-operator`: `reason == expected` с новым текстом) сохраняют точное сравнение, а не ослабляются до «содержит» |
| `tests/test_epic_draft_promote_unsupported_project.py` — параметр `target-human` (`:24`, `:58-59`) | `epic draft promote` отказывает проекту неподдержанной пары | да: отказ проверяется на `gitlab` + `operator` | этот же файл на `gitlab` + `operator` + критерий SPEC (а) | ок при условии: в файле остаётся случай `gitlab` + `operator` с отказом |

Независимая проверка: подтверждаю — проверяющий 05.11 по origin/main 2b62f8a0 (два круга): ссылки и имена верны, объём покрывает все правки открытия пары (включая test_ac4_reason_text_names_pair_and_supported_list и константы unsupported_project.py:172-174), отказ gitlab + operator покрыт во всех действиях с точным текстом, формат строк мандата mandate.py принимает, рамка $85 — строка (85.0, None, None) BUDGET_CALIBRATION_TABLE.
