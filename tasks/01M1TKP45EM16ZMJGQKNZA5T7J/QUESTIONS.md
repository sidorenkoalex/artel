---
task: 01M1TKP45EM16ZMJGQKNZA5T7J
type: questions
author_role: analyst
status: ready
schema_version: 2
---

# QUESTIONS: эталон лёгкой песочницы приёмочных планок в tests/sandbox.py

## Вопросы

1. **Требование 2 называет `tests/test_fsm_merge_conflict_note.py` одним
   из трёх модулей, которые «переводятся на эталон» лёгкой песочницы —
   но этот файл технически не подходит под описание: это чистые
   unit-тесты одной функции (`fsm._merge_conflict_note`), без единого
   патча `config`/`gitcmd`/`TmpRootTest`, без временного каталога и без
   `write_plan_ready`/`write_acceptance_plank`/`advance_from_in_dev` —
   переводить в нём нечего (проверено: `grep` по файлу не находит ни
   одного из этих имён). Настоящий дублирующийся код именно для
   инцидента «причина конфликта подтяжки» (01M1REVMB50SND1KJ3CYQMV2ST,
   на который явно ссылается ТЗ) обнаружен в другом месте — залоченной
   планке `tasks/01M1REVMB50SND1KJ3CYQMV2ST/acceptance_tests/
   test_pull_conflict_detail.py`, которая байт-в-байт несёт ту же
   копию `setUp`/`write_plan_ready`/`write_acceptance_plank`/
   `advance_from_in_dev`, что и два других файла из требования 2 (сейчас
   этот файл зелёный — исправлен прежней ручной правкой `amend-tests`,
   упомянутой в «Контексте» ТЗ). Эта планка НЕ входит в зоны ТЗ (в
   отличие от `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/`,
   которая явно названа и зонирована в требовании 4 как единственное
   исключение из «не входит: правка залоченных планок»).
   Как понимать требование 2 для третьего файла?
   — варианты:
   A) Буквально: критерий требования 2 для `tests/
      test_fsm_merge_conflict_note.py` считается выполненным без
      изменений (переводить нечего — файл уже не несёт копии
      песочницы); `tasks/01M1REVMB50SND1KJ3CYQMV2ST/acceptance_tests/`
      остаётся вне зоны и не трогается этой задачей.
   B) Это опечатка/подмена адреса в ТЗ: требование 2 в действительности
      имеет в виду `tasks/01M1REVMB50SND1KJ3CYQMV2ST/acceptance_tests/
      test_pull_conflict_detail.py` вместо `tests/
      test_fsm_merge_conflict_note.py` — этот путь добавляется в зоны
      как второе (наряду с 01M1NBWPKNBXP9ZXXQDJM7AXPJ) исключение из
      «не входит» (та же логика: задача done, не «в работе»).
   C) Оба: `tests/test_fsm_merge_conflict_note.py` остаётся в
      требовании 2 как есть (без изменений), и вдобавок `tasks/
      01M1REVMB50SND1KJ3CYQMV2ST/acceptance_tests/
      test_pull_conflict_detail.py` добавляется в зоны отдельным
      пунктом требования 2.
   — дефолт: A (минимальный периметр правки — без расширения зон за
     пределы явно названных в ТЗ путей; критерий для третьего файла
     выполняется тем, что переводить в нём действительно нечего).

## Контекст

Прочитан TZ.md целиком. Изучены: `tests/sandbox.py` (текущий набор
общих помощников — `TmpRootTest`, `disk_backed_show`/
`disk_backed_ls_tree_files`, `fake_git`, `SpyRun`, но БЕЗ
`write_plan_ready`/`write_acceptance_plank`/`advance_from_in_dev`/
`assert_acceptance_run_called`, которые нужно завести по требованию 1);
`tests/test_fsm_map_conflict_autoresolve.py` и `tests/
test_branch_freshness_gate.py` (оба несут байт-в-байт совпадающую
копию `write_plan_ready`/`write_acceptance_plank`/
`advance_from_in_dev` и схожую обвязку `setUp` — однозначные кандидаты
требования 2); `tests/test_fsm_merge_conflict_note.py` (чистые
unit-тесты `fsm._merge_conflict_note`, без песочницы — см. вопрос
выше); `tasks/01M1REVMB50SND1KJ3CYQMV2ST/acceptance_tests/
test_pull_conflict_detail.py` (несёт ту же копию, что и два файла
из требования 2, сейчас зелёная); `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/
acceptance_tests/_sandbox.py` — прогнан локально
(`python3 -m pytest tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests`):
6 из 9 тестов красные с сообщением «планка не найдена в источнике» —
подтверждён класс (а) из «Контекста» ТЗ: `OriginDivergedSandbox` в этой
планке никогда не кладёт `SPEC.md`/`acceptance_tests/` в артефактную
ветку (в отличие от `write_plan_ready`, которая туда PLAN.md кладёт
через `artifact_branch.commit_files`), поэтому `acceptance.
materialize_from_branch` не находит планку. Требование 4 (диагностика +
починка + зелёный main) содержательно ясно и вопросов не вызывает.
`skills/test-authoring.md` и `scripts/guard.py` (структура `check()`,
`warnings` уже существуют как отдельный от `errors` список) изучены —
требование 3 тоже ясно.

## Блокирует

Без ответа на вопрос 1 нельзя корректно зафиксировать AC требования 2
в SPEC.md — формулировка AC либо ошибочно потребует от разработчика
несуществующей правки в `tests/test_fsm_merge_conflict_note.py`, либо
(при самостоятельной подмене адреса аналитиком без согласования)
расширит зону задачи на путь, которого нет в ТЗ. SPEC.md до ответа не
пишется (черновика ещё не было).
