---
task: 01M6EZXVFG405Y1BTFDSGBKS8E
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Мандат сессии при Операторе (права волны G) на правку сторожа А0 в части 4 Б2.3, 03.11.2026 — по мандату Оператора 26.10 на тесты, которые меняет ADR-0029.

Разрешено: в test_ac1, test_ac7, test_ac8 — ожидаемые списки поддержки, множество поддержанных пар и строки поддержанных пар; во всём файле — значения констант текстов причин (GITLAB_REASON, TARGET_HUMAN_REASON) под новые тексты unsupported_reason. Запрещено: тела test_ac2…test_ac6 (утверждения о журнале, tasks/steps, отказе до клона/git/агента/слияния, состоянии) и их параметры пар UNSUPPORTED (gitlab+operator, github+target-human) — без изменений; test_ac9 — только если этого требует перечень литералов.

Ослабление тестов разрешено: tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac1_entry_loads_and_reason_names_unsupported_value, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac2_new_refuses_without_side_effects, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac3_run_refuses_before_agent_and_git, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac4_auto_refuses_at_entry, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac5_approve_on_merge_gate_refuses_before_merge, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac6_approve_on_spec_gate_refuses, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac7_doctor_project_support_line, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac8_supported_project_new_is_not_refused

Независимая проверка: проверяющий сессии при Операторе 02.11 — «не ослабляет» при условиях (а) точное равенство кортежей и множества поддержанных пар, (б) отказ ac2–ac7 на обеих неподдержанных парах, (в) ac1/ac7 — обе поддержанные пары, ac8 — и gitlab+target-human, (г) тексты причин двух пар различимы и сверяются точно; мандат 03.11 уже: в ac2–ac6 — только константы текстов.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac1_entry_loads_and_reason_names_unsupported_value`: списки поддержки и пары | запись загружается, причина называет неподдержанное значение — `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:145` | остаётся | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:145` | ок |
| `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac2_new_refuses_without_side_effects`: только константа текста причины | `new` неподдержанного проекта отказывает без побочных действий — `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:172` | остаётся | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:172` | ок |
| `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac3_run_refuses_before_agent_and_git`: только константа текста причины | `run` отказывает до агента и git — `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:202` | остаётся | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:202` | ок |
| `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac4_auto_refuses_at_entry`: только константа текста причины | `auto` отказывает на входе — `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:232` | остаётся | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:232` | ок |
| `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac5_approve_on_merge_gate_refuses_before_merge`: только константа текста причины | `approve` на гейте мержа отказывает до слияния — `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:261` | остаётся | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:261` | ок |
| `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac6_approve_on_spec_gate_refuses`: только константа текста причины | `approve` на гейте SPEC отказывает — `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:290` | остаётся | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:290` | ок |
| `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac7_doctor_project_support_line`: пары поддержки | строка doctor fail для неподдержанного проекта — `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:346` | остаётся | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:346` | ок |
| `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac8_supported_project_new_is_not_refused`: поддержанные пары | поддержанный проект не отказывается — `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:384` | остаётся | `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:384` | ок |
