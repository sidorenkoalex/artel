---
task: 01M45FJVGQT1K0P8HDEXZX6HS7
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Этап 3 ADR-0021, часть 1 из 3 — профиль тестов проекта и проверки тестов на repo_context

## Фаза A: план

- Таблица покрытия полна: требования 1–8 → шаги 1–6. Шаги — проверяемые
  единицы, не микрооперации.
- Подход (`repo_context.profile_of` + одно правило `project_profile.decide`
  на все места таблицы) не конфликтует с архитектурой. Развилка
  `advance_gates/review.py:355` оставлена по «Не входит» SPEC — верно.
- Приложения к `targets.yaml` и `tests/test_invariants.py` в PLAN есть.
  Применимость и зелёный `test_invariants.py` после наложения держит
  `test_plan_facts.py::test_ac14_*` планки, прогон зелёный.
- Расхождение с требованием 8 SPEC — замечание R1-F1 ниже. Раздел PLAN
  «Тесты» заявляет, что требования 1–6 «по переходам» закрывают
  долгоживущие файлы задачи и планка. Требования 3 и 5 для внешнего
  проекта долгоживущими файлами не покрыты, планку после мержа никто не
  гоняет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py::_check_profile`/`_profile_value_error`; долгоживущий `test_..._test_profile.py` зелёный |
| 2 | OK | `repo_context.profile_of` — три исхода; `project_profile.decide` |
| 3 | OK по коду, нет сторожа в `tests/` | `journal_skip` во всех местах таблицы. Ни один тест `tests/` запись о пропуске не сверяет (R1-F1) |
| 4 | OK | отказ артели без профиля на всех рубежах, пакет ревью — `review._exit_without_profile`; `test_..._profile_refusals.py` |
| 5 | OK по коду, нет сторожа в `tests/` для внешнего проекта с профилем | развилки сняты, области и каталог берутся из профиля. Для профиля, отличного от артельного, гейты проверяет только планка (R1-F1) |
| 6 | OK | ветка прогона в `config.ROOT` удалена (`advance_gates/acceptance.py`, `tests_writing.py`, `fsm_advance._review_approved`); AC-11 держат долгоживущие тесты |
| 7 | OK | приложения в PLAN, `git apply --check` и инварианты — `test_plan_facts.py::test_ac14_*` зелёные |
| 8 | не полностью | требования 3 и 5 (внешний проект) без тестов `tests/` (R1-F1). Смен утверждений нет, правки фикстур перечислены |

## Замечания

- **major** — `tests/` (нет файла). Затронутые места:
  `orchestrator/project_profile.py::journal_skip`, вызовы в
  `advance_gates/test_integrity.py::_test_integrity_gate`,
  `advance_gates/review.py::_mutation_claim_gate`,
  `advance_gates/acceptance.py::_long_lived_manifest_refuses` и
  `::_acceptance_run_body`, `fsm_advance.tests_writing`/`_review_approved`,
  `fsm_merge_gate._test_integrity_diff_gate`/`_acceptance_locks_refuse`,
  `review._changed_assertions_part`, `amend._profile_or_exit`; области из
  профиля в `_mutation_claim_gate` (`profile.in_mutation_claim_scope`), в
  `_test_integrity_gate` (`scope=profile.in_weakening_scope`), каталог и
  шаблон в `_tests_writing_long_lived_gate`/`_diff_entry_error`/`amend.*`.

  **Суть.** Свойства требования 3 (запись в журнал о каждой пропущенной
  проверке) и требования 5 для внешнего проекта с профилем (AC-5…AC-8)
  проверяет только планка — `acceptance_tests/test_profile_gates_git.py`,
  с пометкой `Группа: разовый`. Тестов в `tests/` на них нет. SPEC
  требование 8 требует тестов в `tests/` на требования 1–6, ADR-0018
  п. 3 — сторожа долгоживущего свойства после мержа. Существующие
  сценарии с `declared_without_profile` подменяют `journal_skip` и вызов
  не сверяют. `grep -rn "проверка тестов не выполняется\|journal_skip"
  tests/` находит только `tests/sandbox.py`. `in_mutation_claim_scope`
  на гейте с неартельным профилем не зовёт ни один тест `tests/`.

  **Проверено временной мутацией.** Две мутации разом:
  `journal_skip` → `return` и в `_mutation_claim_gate` возврат зашитого
  фильтра `f.startswith("tests/test_") and f.count("/") == 1` вместо
  `profile.in_mutation_claim_scope(f)`. Прогон 10 затронутых модулей
  `tests/` (оба долгоживущих файла задачи, `test_project_profile`,
  `test_mutation_claim_gate`, `test_test_integrity_gate`,
  `test_fsm_advance_tests_writing_test_groups`,
  `test_long_lived_manifest`, `test_external_code_copy_refusal`,
  `test_docs_dir_layout`, `test_01m45fjd46..._declared_change`) —
  170 passed. Обе мутации выжили, код возвращён.

  **Сценарий последствий.** После мержа планку не гоняет ни CI, ни
  автогейт. Правка, которая молча отключит запись о пропуске (нарушение
  «молча не отключается ничего», требование 3) или снова зашьёт
  артельную область в гейт заявки мутации или неослабления, пройдёт
  зелёный CI.

  **Предложение.** Добавить в `tests/` (свой файл, например
  `tests/test_project_profile_gates.py`, не долгоживущий файл задачи)
  тесты с заявками «Ловит мутацию»:
  1. Внешний проект без профиля: после перехода `in_dev → verifying` и
     выхода из `tests_writing` в журнале есть записи
     `проверка тестов не выполняется: <проверка>` с причиной «нет
     test_profile» по каждой проверке таблицы. Хватит проверки на
     уровне гейтов: `_mutation_claim_gate`, `_test_integrity_gate`,
     `_long_lived_manifest_refuses`, `review._changed_assertions_part` с
     настоящим `store.journal`.
  2. Внешний проект с неартельным профилем (например,
     `mutation_claim_scope: [checks/**/test_*.py]`,
     `weakening_scope: [checks/**/*.py]`): гейт заявки мутации отказывает
     по файлу из области профиля вне `tests/` и не требует заявки у
     `tests/test_x.py`. Гейт неослабления отказывает на ослаблении в
     `checks/` и молчит на том же диффе в `tests/`. Достаточно подмены
     `gitcmd.diff_base`/`diff_name_status`/`show`, как в существующих
     `tests/test_mutation_claim_gate.py`/`tests/test_test_integrity_gate.py`.
  3. Каталог и шаблон профиля в
     `advance_gates/tests_writing._diff_entry_error`: путь
     `<long_lived_dir>/<имя по шаблону>` законен, `tests/test_<id>_x.py`
     при `long_lived_dir: checks` — нарушение.

- **minor** (сведение, не к разработчику) — планка
  `acceptance_tests/test_profile_gates_git.py` несёт `Группа: разовый`,
  но проверяет свойства кода (AC-2, AC-3, AC-5…AC-8, AC-12), а не факты
  задачи. По ADR-0020 это ошибка границы групп. Планка залочена, правка —
  только `amend-tests` (ADR-0012). Если свойства из R1-F1 закрыть тестами
  в `tests/`, расхождение перестаёт оставлять код без сторожа, и правка
  планки не нужна. Отдельной записью в реестр не заношу.

- Сведение без замечания:
  `tests/test_acceptance_tests_flow.py::AcceptanceRunTest::test_no_acceptance_tests_directory_does_not_block_legacy_tasks`
  получил строку сценария `skip_tests`, утверждения не тронуты, PLAN это
  раскрывает. Прежний сценарий (SPEC v2 без `skip_tests` и без планки)
  проходил только через удалённый откат прогона в `config.ROOT`. На
  ветке задачи артель и до этой правки отказывала
  `_missing_plank_refuses`. Смена — следствие требования 6, проверка
  ужесточена, не ослаблена. Новый вариант сценария совпадает со случаем
  из докстринга метода.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/ (нет файла); orchestrator/project_profile.py::journal_skip, orchestrator/advance_gates/review.py::_mutation_claim_gate (`profile.in_mutation_claim_scope`), orchestrator/advance_gates/test_integrity.py::_test_integrity_gate (`scope=`), orchestrator/advance_gates/tests_writing.py::_diff_entry_error | Требование 3 (запись о пропуске) и требование 5 для внешнего проекта с профилем (области, каталог и шаблон из профиля) держит только планка с пометкой «разовый»; в `tests/` сторожа нет — две временные мутации выжили в 10 затронутых модулях (170 passed) | после мержа правка, молча отключающая запись о пропуске или зашивающая артельную область в гейт, пройдёт зелёный CI (нарушение SPEC треб. 8, ADR-0018 п. 3) | добавить тесты `tests/` с «Ловит мутацию» на запись о пропуске по проверкам таблицы, на гейты заявки мутации и неослабления с неартельным профилем и на каталог/шаблон в `_diff_entry_error` (перечень — в «Замечания») — разработчик: добавлен `tests/test_project_profile_gates.py` (11 методов с заявками): записи о пропуске на гейтах заявки мутации и неослабления, сверке перечня и разделе пакета ревью; гейты заявки мутации и неослабления с профилем `checks/**`; каталог и шаблон профиля в `_diff_entry_error`. Обе мутации ревьювера и ещё три (`scope=` убран, каталог `tests/` зашит, `is_long_lived` с артельными умолчаниями) красят файл — PLAN «Тесты» |

## Вердикт

changes_requested — закрыть R1-F1: добавить в `tests/` сторожей
требования 3 (записи о пропуске проверок у внешнего проекта без профиля)
и требования 5 для внешнего проекта с неартельным профилем (области заявки
мутации и неослабления, каталог и шаблон долгоживущего файла). Код
реализации, приложения и правки фикстур замечаний не имеют.

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py
  plank-run 01M45FJVGQT1K0P8HDEXZX6HS7` — 31 passed за 180 с (включая
  `test_ac14_*`: приложения применяются, `test_invariants.py` с ними
  зелёный), код выхода 0.
- `python3 -B -m pytest -q -p no:cacheprovider -p timeout -o timeout=120`
  по `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py`,
  `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`,
  `tests/test_project_profile.py`, `tests/test_mutation_claim_gate.py`,
  `tests/test_test_integrity_gate.py`,
  `tests/test_fsm_advance_tests_writing_test_groups.py`,
  `tests/test_long_lived_manifest.py`,
  `tests/test_external_code_copy_refusal.py`,
  `tests/test_docs_dir_layout.py`, `tests/test_multitarget.py`,
  `tests/test_repo_context.py` — 188 passed, 83 subtests passed.
- Временная мутация (R1-F1): `project_profile.journal_skip` → `return` и
  зашитый фильтр `tests/test_*.py` в `_mutation_claim_gate`. Прогон
  10 модулей (перечень в R1-F1) — 170 passed, мутации не пойманы. Код
  возвращён `git checkout -- orchestrator/`, `git status` пуст.
- `grep -n "DEFAULT_TARGET\|is_artel"` по модулям таблицы. Остались
  `advance_gates/review.py:355` (часть 3), `workspace.repo(DEFAULT_TARGET)`
  в `review.py:233,498`, `advance_gates/acceptance.py:37` — это не
  сравнения. Вывод совпадает с PLAN (AC-10).
- `workspace.on_task_branch` без `target` берёт `task_target(task_id)`
  (`orchestrator/workspace.py:225-236`). Вызов в
  `_tests_writing_long_lived_gate` без жёсткого `DEFAULT_TARGET`
  корректен для любого проекта.
- Полный набор `tests/` не гонялся (правило шага). CI коммита 098b8a0d
  зелёный по пакету.

## Предложения системе

- Скил test_author / автогейт групп: планка, проверяющая свойства кода
  гейтов, прошла лок с пометкой `Группа: разовый`. Гейт групп проверяет
  наличие строки, но не её соответствие предмету. Из-за этого
  долгоживущие свойства остались без сторожа в `tests/`, хотя задача
  требует его явно (требование 8). Кандидат: проверка в пакете ревью,
  что каждое требование, названное в «Тесты» SPEC, имеет хотя бы один
  тест `tests/`, а не только планку.
