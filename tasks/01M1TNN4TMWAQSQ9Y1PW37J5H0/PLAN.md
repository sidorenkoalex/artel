---
task: 01M1TNN4TMWAQSQ9Y1PW37J5H0
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: рабочие файлы роли не доезжают до артефактной ветки и main — белый список каталога задачи, guard до снимка

## Подход

Формулировка по ANSWER-1 (вариант A): белый список требования 1 действует
ТОЛЬКО для `.md`-имён первого уровня `tasks/<id>/`
(`SPEC.md`/`PLAN.md`/`REVIEW.md`/`TEST_REPORT.md`/`QUESTIONS.md`/`TZ.md`/
`ANSWER-<n>.md`); файл ЛЮБОГО другого расширения — легальное вложение без
ограничений имени (иначе конфликт с уже залоченными `tests/
test_checkpoint_external_step_artifacts.py::test_binary_file_is_not_lost`
и `::test_all_files_binary_still_commits_and_clears_the_dir`, из-за
которого предыдущий заход test_author эскалировал требование
AC-9 — см. ANSWER-1). Скрытые файлы/каталоги (`.`-префикс) и
`__pycache__/` — посторонние независимо от расширения.

Один источник истины (требование 2/AC-6): `scripts/guard.py` несёт
критерий (`is_extraneous_task_root_file` + обёртки
`extraneous_task_root_files_in`/`scan_extraneous_task_root_files`, по
образцу уже существующей пары `is_extraneous_acceptance_test_file`/
`scan_extraneous_acceptance_files` из 01M1SAA01YRRTWAVADT2F81RRQ);
`orchestrator/checkpoint.py` и `orchestrator/fsm_merge_gate.py`
ИМПОРТИРУЮТ эти функции (`from scripts import guard`), не копируют
регэксп независимо — тот же приём, что `orchestrator/fsm.py` уже
применяет для остального guard'а.

Три точки контроля включаются в порядке, обратном тому, в котором
инцидент 06.09 прошёл мимо всех трёх (guard `--all` → checkpoint →
merge_gate), но реализуются одним PLAN — обоснование монолита уже дано
в SPEC («Оценка объёма и деление»): промежуточное состояние не закрывает
класс инцидента.

1. **guard.py** — `--all` (с `--artifact-branch` и без) называет
   посторонний `.md` файл первого уровня `tasks/<id>/` именованной
   ошибкой ДО попытки разбора frontmatter (стray-файлы исключаются из
   `files` заранее, тем же приёмом, что уже применён для
   `acceptance_tests/`).
2. **checkpoint.py** — `_commit_external_step_artifacts` (общий узел
   автокоммита успешного шага и всех трёх WIP-чекпоинтов таймаута/
   аварии/pause-now) фильтрует посторонние `.md` первого уровня ТЕМ ЖЕ
   критерием guard'а, одна запись журнала на весь список отброшенных
   путей.
3. **fsm_merge_gate.py** — `_publish_merge_artifacts` прогоняет
   `guard.extraneous_task_root_files_in` на `tasks/<id>/` СНИМКА
   артефактной ветки в scratch-репозитории (`_overlay_artifact_snapshot`
   уже наложен), ДО `_push_merged_main`; отказ — тем же журнальным
   классом («merge FAILED»), что и прочие отказы `merge_gate` (CI
   красный, конфликт merge, push FAILED), задача остаётся на
   `merge_gate` без эскалации, main не тронут.

Полное содержательное `guard.check()` (frontmatter/секции) на этом шаге
СОЗНАТЕЛЬНО не подключается: `tests/test_fsm_merge_gate_done_snapshot.py`
(зона AC-9 — обязан остаться зелёным без правки ассертов) коммитит в
артефактную ветку `PLAN.md` без валидного frontmatter (`"план\n"`) и
полагается на то, что merge_gate это пропускает; расширение до полного
content-check сломало бы этот тест новым классом отказа, не относящимся
к требованию 3 (посторонний файл), поэтому guard на merge_gate ограничен
ИМЕННО критерием посторонности требования 1 — ровно то, что называют
AC-7/AC-8.

**AC-3 (mockup.html)** — решение по ANSWER-1: белый список действует
ТОЛЬКО для `.md`, поэтому `tasks/T080/mockup.html` (расширение `.html`)
становится законным вложением автоматически, без специального
исключения по имени задачи и без удаления. Дополнительно T080 уже
закрыт (`docs/retro/T080.md` на месте) — независимо от правила
расширения, guard молчит по нему.

**Правка итерации 2 (REVIEW.md итерация 1, замечание R1-F1, blocker)** —
`is_extraneous_task_root_file` (`scripts/guard.py:548-557`) в первой
итерации проверял допустимость `.md`-имени только для пути РОВНО из
одного сегмента (`len(parts) == 1`); файл в ЛЮБОЙ другой, впервые
заведённой поддиректории первого уровня (например
`tasks/<id>/wip/_head_map.md`) молча проходил все три точки контроля —
ровно класс инцидента 06.09 на один уровень вложенности глубже.
Починено: для `len(parts) == 1` поведение не изменилось; для
`len(parts) > 1` (любой путь глубже, `parts[0] != "acceptance_tests"`) —
файл посторонний БЕЗУСЛОВНО, независимо от расширения (единственная
легальная поддиректория первого уровня — `acceptance_tests/`).
`checkpoint.py`/`fsm_merge_gate.py` чинятся автоматически — оба
импортируют этот же предикат (требование 2/AC-6, один источник
истины). Регресс-тест `tests/test_guard_task_root_subdirectory.py`
(6 тестов) добавлен в `tests/`, не в залоченную планку приёмки (её
правка — эскалация, не правка разработчика): покрывает предикат
напрямую и все три точки контроля (`guard --all`,
`checkpoint.commit_step_artifacts`,
`fsm_merge_gate._guard_task_root_or_refuse`) на файле в новой
поддиректории; проверено даунгрейдом фикса (временный откат — 4 из 6
новых тестов красные) и восстановлением, см. «Проверено исполнением».

**Скилы (требование 5)** — unified-диф приложением
`tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/skills-note.patch` добавляет по одной
секции/пункту в `skills/coding-standards.md` (разработчик) и
`skills/review-checklist.md` (ревьювер) с формулировкой требования;
`git apply --check` на чистом дереве подтверждён (см. «Влияние на
систему»).

## Шаги

1. `scripts/guard.py`: белый список `TASK_ROOT_ALLOWED_MD`,
   `is_extraneous_task_root_file`, `extraneous_task_root_files_in`,
   `scan_extraneous_task_root_files`; подключение в `main()` (`--all`,
   оба режима) рядом с существующим фильтром `acceptance_tests/`.
2. `orchestrator/checkpoint.py`: импорт `from scripts import guard`;
   фильтр `task_root_stray` в `_commit_external_step_artifacts` тем же
   приёмом, что уже применён для `_is_stray_acceptance_test_file`, одна
   запись журнала на весь список.
3. `orchestrator/fsm_merge_gate.py`: импорт `from scripts import guard`;
   `_guard_task_root_or_refuse` вызывается из `_publish_merge_artifacts`
   сразу после `_overlay_artifact_snapshot`, до карты/RETRO/push —
   посторонний файл отказывает `sys.exit`'ом с журналом «merge FAILED»,
   scratch-дерево убирается.
4. Юнит-тесты: приёмочные планки задачи (16 тестов, AC-1..AC-8) +
   регрессия существующих `tests/test_guard*.py`,
   `tests/test_checkpoint*.py`, `tests/test_fsm_merge_gate*.py` (AC-9).
   По ходу обнаружен и починен конфликт класса «фикстура использует
   произвольное `.md`-имя вне белого списка» в `tests/
   test_step_autocommit.py` (4 места, имя `wip.md` → `PLAN.md`) — см.
   «Влияние на систему».
5. Приложение к PLAN: `tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/skills-note.patch`
   (unified-диф `skills/coding-standards.md` +
   `skills/review-checklist.md`), `git apply --check` подтверждён на
   чистом дереве.
6. (итерация 2, R1-F1) `scripts/guard.py::is_extraneous_task_root_file` —
   критерий постороннего файла проверяет допустимость ПЕРВОГО сегмента
   пути независимо от глубины остального пути, не только путь ровно из
   одного сегмента; новый файл `tests/test_guard_task_root_subdirectory.py`
   (6 тестов) — регрессия на файл в новой поддиректории первого уровня
   для всех трёх точек контроля.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 6 |
| 2 | 2, 6 |
| 3 | 3, 6 |
| 4 | 4, 6 |
| 5 | 5 |

## Влияние на систему

**Затронуто за пределами прямой правки.** Новый критерий guard'а
применяется на РЕАЛЬНОМ дереве `tasks/` этого репозитория при каждом
запуске `guard.py --all` (используется CI на `main`/`artifact/**`, а
также приёмочным тестом AC-3 через реальный subprocess). Проверено
`find tasks -mindepth 2 -maxdepth 2 -type f` по факту: единственные
`.md`-имена первого уровня на дереве — уже входящие в белый список
(`SPEC.md`/`PLAN.md`/`REVIEW.md`/`TZ.md`/`ANSWER-<n>.md`); единственное
исключение — `tasks/T080/mockup.html` (не `.md`, легально по ANSWER-1).
Единственная известная историческая аномалия — черновики
`tasks/01M1REVMB50SND1KJ3CYQMV2ST/_head_map*.md` и подобные — уже удалены
Оператором на `origin/main` коммитом `f29d97f2`, но ветка ЭТОЙ задачи
срезана ДО этого коммита (`git merge-base --is-ancestor f29d97f2 HEAD` —
`no`) и всё ещё несёт их на диске рабочей копии; это не создаёт красноты
для самой этой задачи — CI `task/**` не гоняет guard `--all` на
`tasks/` вовсе (источник истины — `artifact/**`, `.github/workflows/
ci.yml`), а артефактная ветка ЭТОЙ задачи несёт только
`tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/`. Слияние с `main` (которое подтянет
`f29d97f2`) — забота будущей подтяжки/merge_gate, не этого шага; в PLAN
специального исключения для этой исторической задачи не заводилось
(guard.py не грандфазерит её каким-либо специальным правилом — она
естественно очистится подтяжкой main до merge).

**Регресс, найденный и закрытый в этом же шаге.** `tests/
test_step_autocommit.py::test_dirty_tree_commits_to_artifact_branch_and_journals`
и три соседних теста того же файла использовали фикстурное имя
`wip.md` как обобщённый плейсхолдер «файл, который написала роль» —
не входящее в белый список, поэтому новый фильтр checkpoint'а стал
молча отбрасывать его, и тест, читающий содержимое файла из артефактной
ветки, начал падать (`tree.get(...) == None`). Это не файл из зоны
задачи (`tests/test_step_autocommit.py` не назван в AC-9 явно), но
общий принцип «не ломать существующие тесты» требует правки: имя
фикстуры заменено на `PLAN.md` (уже используется соседним классом того
же файла) — ассерты и намерение теста не изменились, изменилось только
имя файла-фикстуры. Аналогичный grep (`tests/test_timeout_checkpoint.py`,
тоже `wip.md`, 16 мест) НЕ потребовал правки — эти тесты проверяют
только код-ветку (`developer`, `tasks/<id>/` заведомо исключён оттуда
`exclude=`) и журнал по фильтрованному действию, не содержимое
артефактной ветки, поэтому остались зелёными без изменений (проверено
прогоном).

**Инварианты/гейты рядом не ослаблены.** Новое правило ТОЛЬКО сужает
(превращает молчаливый проезд постороннего файла в именованный отказ на
трёх новых точках) — ни один существующий тест `tests/test_guard*.py`,
`tests/test_checkpoint*.py`, `tests/test_fsm_merge_gate*.py` не
редактировался по ассертам (AC-9), все зелёные. Полное содержательное
`guard.check()` НЕ подключено к `merge_gate` (см. «Подход») — это
осознанное ограничение объёма этого требования, а не пропуск: описано
выше и не расширяет `merge_gate` дальше, чем просит AC-7/AC-8.

**Откат.** Три точки независимы по коду (guard.py/checkpoint.py/
fsm_merge_gate.py) — откат любой правки убирает только её отказ, не
трогая две другие; `git revert` по каждому файлу отдельно безопасен.

## Риски

- Скилы (`skills-note.patch`) — приложение, не код; применяет Оператор
  отдельным MR. До применения текст скила не содержит новой строки —
  роли следующего шага (developer/reviewer) не увидят её в брифе, пока
  Оператор не смержит патч.
- Историческая ветка `01M1REVMB50SND1KJ3CYQMV2ST` (черновики карты) на
  этой задаче не тронута — Оператор убирает её отдельно (SPEC «Не
  входит»), как и заявлено.

## Проверено исполнением

- `python3 -m unittest tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac1_ac2_guard_task_root_whitelist -v` — 8 ok.
- `python3 -m unittest tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac3_mockup_html_exception -v` — 1 ok.
- `python3 -m unittest tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac4_ac5_ac6_checkpoint_task_root_filter -v` — 5 ok.
- `python3 -m unittest tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac7_ac8_merge_gate_guard_before_push -v` — 2 ok.
- `python3 -m unittest tests.test_guard_extraneous_acceptance_files tests.test_guard_artifact_branch_mode tests.test_guard_schema tests.test_guard_split_signals tests.test_guard_zones tests.test_advance_guard` — 115 ok.
- `python3 -m unittest tests.test_step_autocommit tests.test_timeout_checkpoint tests.test_checkpoint_stray_acceptance_files tests.test_checkpoint_external_step_artifacts` — 57 ok (после фикса фикстуры `wip.md` → `PLAN.md` в `tests/test_step_autocommit.py`).
- `python3 -m unittest tests.test_fsm_merge_gate_done_snapshot -v` — 2 ok.
- `python3 -m unittest tests.test_merge_gate_ci_wait tests.test_split_assessment_merge_gate tests.test_ci_status_kind_gate tests.test_fsm_map_regen tests.test_fsm_retro tests.test_fsm_map_conflict_autoresolve tests.test_fsm_merge_conflict_note tests.test_capacity_gate` — 55 ok.
- `python3 -m unittest tests.test_acceptance_tests_flow -v` — 69 ok (в т.ч. `test_new_unrelated_file_does_not_trip_the_lock`, проверяющий посторонний `notes.md` вне зоны нового правила — `cmd_advance` не гоняет `guard --all` по всему дереву).
- `python3 -m py_compile scripts/guard.py orchestrator/checkpoint.py orchestrator/fsm_merge_gate.py tests/test_step_autocommit.py` — ок.
- `git apply --check tasks/01M1TNN4TMWAQSQ9Y1PW37J5H0/skills-note.patch` на чистом дереве — ок (патч применён во временную правку для генерации диффа и отменён `git checkout --`, рабочее дерево `skills/` чисто).

### Итерация 2 (правка R1-F1)

- `python3 -c "from scripts import guard; print(guard.is_extraneous_task_root_file('wip/_head_map.md'))"` — `True` (было `False` до правки).
- `python3 -m unittest tests.test_guard_task_root_subdirectory -v` — 6 ok; даунгрейд фикса (временный откат правки predicate) — 4 из 6 красные, восстановление — снова 6 ok (тесты ловят заявленную мутацию R1-F1).
- `python3 -m unittest tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac1_ac2_guard_task_root_whitelist tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac3_mockup_html_exception tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac4_ac5_ac6_checkpoint_task_root_filter tasks.01M1TNN4TMWAQSQ9Y1PW37J5H0.acceptance_tests.test_ac7_ac8_merge_gate_guard_before_push` — 16 ok (залоченная планка без правки ассертов).
- `python3 -m unittest tests.test_guard_task_root_subdirectory tests.test_guard_extraneous_acceptance_files tests.test_guard_artifact_branch_mode tests.test_guard_schema tests.test_guard_split_signals tests.test_guard_zones tests.test_advance_guard tests.test_step_autocommit tests.test_timeout_checkpoint tests.test_checkpoint_stray_acceptance_files tests.test_checkpoint_external_step_artifacts tests.test_fsm_merge_gate_done_snapshot tests.test_merge_gate_ci_wait tests.test_split_assessment_merge_gate tests.test_ci_status_kind_gate tests.test_fsm_map_regen tests.test_fsm_retro tests.test_fsm_map_conflict_autoresolve tests.test_fsm_merge_conflict_note tests.test_capacity_gate tests.test_acceptance_tests_flow` — 329 ok суммарно (AC-9 не нарушен).
- `python3 -m py_compile scripts/guard.py orchestrator/checkpoint.py orchestrator/fsm_merge_gate.py tests/test_guard_task_root_subdirectory.py` — ок.
- `python3 scripts/guard.py --all` на реальном дереве `tasks/` — «GUARD: ок (607 файлов)» (правка не задевает штатное дерево задачи, включая `tasks/T080/mockup.html` и `.md`-набор из «Влияния на систему»).
- `python3 scripts/codebase_map.py` — карта регенерирована этим же коммитом (правка `*.py` в зоне `scripts/`/`tests/`), diff — новый `built_at_sha` и запись `tests/test_guard_task_root_subdirectory.py` в графе импортов.

## Предложения системе
