---
task: 01M56TNTY7HEC85MC940KZR1ZJ
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: scripts/guard.py, orchestrator/advance_gates/test_integrity.py, tests/
budget_usd: 25
---

# SPEC: Гейт неослабления: помощники по области ослабления проекта

## Контекст
Часть задачи 01M56P60XS9AP4BH01YK35220D (требования 6, 10, 11 её SPEC в
части помощников; её AC-9, AC-10). Гейт неослабления тестов прослеживает
помощников по устройству артели: вызывающие ослабленного помощника ищутся
только в `tests/` (`orchestrator/advance_gates/test_integrity.py:631-650`,
`_helper_callers`), имя модуля переводится как `tests.x` → `tests/x.py`
(`scripts/guard.py:1013-1019`), импортированные функции прослеживаются
только из `tests/sandbox.py` (`guard.py:1087`), относительный импорт
разрешается от пути файла от корня репозитория (`guard.py:936,950-952`:
`backend/tests/test_x.py` → пакет `backend.tests`), и такое имя `_module`
отбрасывает по первому сегменту (`guard.py:1014`). Поэтому помощники чужого
стека (проект sled: `workdir: backend`, `weakening_scope:
[backend/tests/**/*.py]`; например `backend/tests/rbac_support.py`) гейту
невидимы, и потеря утверждения в них проходит без находки. Вызовы узла из
`orchestrator/review.py:650-652` и `orchestrator/fsm_merge_gate.py:144-146`
передают только предикат области; все три входа узла (`review_lines`,
`merge_gate_escalates`, `_test_integrity_gate`) имеют `task_id` и сходятся
в общем узле `_evaluate(conn, task_id, …)` (`test_integrity.py:1074`),
профиль проекта задачи читается `project_profile` (`for_task`/`decide`).

Редакция учитывает решения Оператора по аудиту SPEC 18.10 (О1–О4).

## Требования
1. Режим поиска вызывающих и прослеживания помощников задаёт признак
   `repo_context.is_artel` проекта задачи.
   - У внешнего проекта (`is_artel` ложен) поиск вызывающих ослабленного
     помощника и прослеживание помощников идут по области ослабления
     профиля проекта задачи (`weakening_scope`): импортированная функция
     прослеживается из любого модуля области, имя модуля переводится в
     путь от корня проекта с учётом `workdir` профиля (`tests.x` при
     `workdir: backend` → `backend/tests/x.py`; при пустом `workdir` →
     `tests/x.py`).
   - У артели (`is_artel` истинен) — как сейчас: вызывающие ищутся в
     `tests/`, импортированные функции прослеживаются только из
     `tests/sandbox.py`.
2. Режим (артель/внешний) передаётся в guard отдельно от `workdir`: режим
   внешнего проекта не выводится из наличия или пустоты `workdir`. Без
   аргумента режима — поведение артели при любом `workdir`.
3. Режим и профиль (в том числе `workdir` и `weakening_scope`) читаются на
   общем узле сравнения по `task_id` — из профиля проекта задачи, внутри
   зон задачи; поэтому их получают все три входа узла: рубеж
   `in_dev → verifying` (`_test_integrity_gate`), гейт мержа
   (`merge_gate_escalates`) и раздел ревью-пакета (`review_lines`). Вызовы
   узла из `orchestrator/review.py:650-652` и
   `orchestrator/fsm_merge_gate.py:144-146` не меняются. Если без их
   правки не обойтись — эскалация до правки.
4. У внешнего проекта относительный импорт помощника переводится в путь с
   учётом `workdir`: `from .x import f` в `backend/tests/test_y.py` при
   `workdir: backend` прослеживается к функции `f` модуля
   `backend/tests/x.py`.
5. У внешнего проекта помощник — только функция модуля, путь которого
   входит в `weakening_scope` профиля; функция модуля вне области (при
   `weakening_scope: [backend/tests/**/*.py]` — например
   `backend/app/x.py`) помощником не прослеживается.
6. `guard.TestModules` и `guard.method_literal_keys` меняются обратно
   совместимо: режим и `workdir` — необязательные аргументы, без них
   поведение прежнее; их вызов в `orchestrator/fsm.py:1053-1060` не
   правится.
7. У артели прежние исходы фиксируются тестами до правки и не меняются
   после неё: функция своего модуля без префикса `test_` — находка на
   вызывающем; функция `tests/sandbox.py` — находка; функция другого
   модуля `tests/` — находки нет; функция своего модуля с префиксом
   `test_` — не помощник; вызывающие ищутся только в `tests/`.
8. Тесты детерминированы, без сети; поведение чужого стека проверяется на
   учебном проекте с `workdir: backend` и `weakening_scope:
   [backend/tests/**/*.py]` (и, для требования 2, на учебном внешнем
   проекте с пустым `workdir` и `weakening_scope: [tests/**/*.py]`).

## Критерии приёмки
AC-1. Помощник `backend/tests/rbac_support.py` учебного внешнего проекта (`workdir: backend`, `weakening_scope: [backend/tests/**/*.py]`), потерявший утверждение на ветке и вызываемый из неизменённого теста `backend/tests/test_<x>.py` (импорт `from tests.rbac_support import …`), даёт находку гейта неослабления на каждом из трёх входов узла: отказ рубежа `in_dev → verifying`, эскалация гейта мержа (`merge_gate_escalates`) и строка находки в разделе ревью-пакета (`review_lines`).

AC-2. Учебный внешний проект с пустым `workdir` и `weakening_scope: [tests/**/*.py]`: функция модуля `tests/x.py` (не `tests/sandbox.py`), импортированная тестом и потерявшая утверждение на ветке, даёт находку гейта неослабления на вызывающем тесте.

AC-3. Учебный внешний проект (`workdir: backend`, `weakening_scope: [backend/tests/**/*.py]`): функция `f` модуля `backend/tests/x.py`, импортированная относительно (`from .x import f`) неизменённым тестом `backend/tests/test_<y>.py` и потерявшая утверждение на ветке, даёт находку гейта неослабления на вызывающем тесте.

AC-4. Учебный внешний проект (`workdir: backend`, `weakening_scope: [backend/tests/**/*.py]`): функция модуля `backend/app/x.py` (вне области), импортированная тестом `backend/tests/test_<y>.py` и потерявшая утверждение на ветке, помощником не прослеживается — находки на вызывающем тесте нет.

AC-5. У артели исходы помощников прежние (зафиксированы тестом до правки, проходят после неё): (а) функция своего модуля без префикса `test_`, потерявшая утверждение, даёт находку на вызывающем тесте; (б) функция `tests/sandbox.py`, потерявшая утверждение, даёт находку на вызывающем тесте другого файла `tests/`; (в) функция другого модуля `tests/` (не `tests/sandbox.py`), импортированная и потерявшая утверждение, находки на вызывающем тесте не даёт; (г) функция своего модуля с префиксом `test_` помощником не прослеживается; (д) вызывающий ослабленного помощника ищется только среди файлов `tests/`.

## Оценка объёма и деление
Сработавший сигнал: зона задевает механизм, на который опирается запись
`docs/invariants.md` № 38 (гейт неослабления тестов,
`orchestrator/advance_gates/test_integrity.py`, `scripts/guard.py`).

Решение — **монолит**, материал для Оператора: задача уже сама является
первой частью нарезки родителя 01M56P60XS9AP4BH01YK35220D (раздел
«Деление» его SPEC, рамка $25). Перевод имени модуля с учётом режима и
`workdir` (`guard.py`) и область поиска вызывающих (`test_integrity.py`) —
одна смена механики: перевод без поиска вызывающих по области не даёт
находки AC-1, поиск без перевода не прослеживает импорт; промежуточной
части с собственным проверяемым результатом нет. Инвариант 38 усиливается
для внешних проектов, у артели исходы прежние (AC-5).

## Не входит
- Правило импортов долгоживущих файлов (задача 01M5633WZ3Y3A0P4KKBZDB3KER).
- Не-Python стек.
- Сверка «Меняемого поведения» на гейте SPEC (`orchestrator/fsm.py:1053-1060`)
  для внешних проектов — она по-прежнему не видит помощников вне `tests/`.
- Пропуски через метку и модуль, async и параметризация — другие части
  задачи 01M56P60XS9AP4BH01YK35220D.
- Правка вне зон: `orchestrator/project_profile.py`,
  `orchestrator/advance_gates/mandate.py`, `orchestrator/acceptance.py`,
  `orchestrator/review.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/fsm.py`, `orchestrator/repo_context.py`, `targets.yaml`,
  `docs/backlog.md` — только чтение; потребность в правке — эскалация.

## Материалы
- `refs/artifacts/01M56P60XS9AP4BH01YK35220D:tasks/01M56P60XS9AP4BH01YK35220D/SPEC.md`
  — требования 6, 10, 11; AC-9, AC-10; раздел «Деление».
- `tasks/01M56TNTY7HEC85MC940KZR1ZJ/SPEC-AUDIT.md` — замечания О1–О4, по
  которым Оператор принял решения 18.10.
- `orchestrator/project_profile.py:72-100` — поля `weakening_scope`,
  `workdir`, `in_weakening_scope`; `project_profile.decide` (`:140`).
- `orchestrator/repo_context.py:154` — `is_artel`.
- `scripts/guard.py:929-958` — `_tests_import_bindings` (относительный
  импорт), `:1013-1019` — `_HelperScope._module`, `:1087` — импорт только
  из `tests/sandbox.py`.
- `orchestrator/advance_gates/test_integrity.py:1074` — общий узел
  `_evaluate`; `:1237`, `:1475`, `:1571` — входы `review_lines`,
  `_test_integrity_gate`, `merge_gate_escalates`.
