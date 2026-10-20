---
task: 01M5AQH8M2DKBV30NBY86J34A7
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M5AQH8M2DKBV30NBY86J34A7
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы
1. AC-9, часть «проект из двух компонентов» — вариант (а). Точка входа гейта честного FAIL_TO_PASS: функция `_tests_writing_fail_to_pass_gate` в `orchestrator/advance_gates/tests_writing.py`, рядом с гейтами групп и долгоживущих, с подписью
   `_tests_writing_fail_to_pass_gate(conn, task_id: str, acc_tdir, run_cwd, covered: set[str], profiles: list) -> GateRefusal | None`
   - `acc_tdir` — каталог планки задачи, `run_cwd` — рабочая копия кода (база), `covered` — множество критериев AC-<n>, покрытых тестом;
   - `profiles` — профили компонентов: на переходе — список из одного профиля задачи (запись из одного компонента), в тесте двух компонентов — `project_profile.component_profiles(<проект>)`; профиль файла гейт выбирает сам (файл планки — `PlankRule.component_of`, долгоживущий — компонент шаблона `long_lived`);
   - возврат — как у соседних гейтов: `None` или `GateRefusal`.
   Тот же вызов — для защитной ветки AC-12 («правило планки не построено»). Переход зовёт функцию в списке гейтов выхода из `tests_writing` (требование 9 SPEC). Имя и подпись обязательны для developer.
2. Рамка задачи поднята Оператором до $95.
