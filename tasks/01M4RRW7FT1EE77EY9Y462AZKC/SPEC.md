---
task: 01M4RRW7FT1EE77EY9Y462AZKC
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/artel.py, orchestrator/catalog.py, orchestrator/projects.py, tests/, docs/codebase-map.md
budget_usd: 40
---

# SPEC: Проект задачи — флаг `new --target`, однозначный выбор проекта и клон в `target-init`

## Контекст
Роадмап §4, главная линия, ТЗ-2; решение Оператора 12.10.2026 — минимальный
путь к первой задаче на внешнем проекте (sled). Сегодня
`catalog.cmd_new` (`orchestrator/catalog.py` ~455) уже принимает keyword
`target` (`None` → `config.DEFAULT_TARGET`, артель), но командная строка
`new` (`orchestrator/artel.py`: `_NEW_USAGE` ~1368, `_parse_new_args` ~1371,
`_cmd_new` ~1550) флага проекта не знает и `target` не передаёт — все задачи
в БД заведены на `artel`. Имя проекта не сверяется с `targets.yaml` до
побочных эффектов, строку ТЗ «Проект:» пульт не разбирает, а
`target-init` (`orchestrator/projects.py::cmd_target_init` ~40) создаёт
только каталоги проекта и клон не заводит — клон появляется лишь при
`new`/`docs`/`doctor --fix` (`workspace.ensure_clone`).

## Требования

1. Команда `new "<название>" [--tz <файл>] [--set <набор>] [--target <имя>]`:
   значение флага `--target` передаётся в `catalog.cmd_new(target=...)`.
   Справка `_NEW_USAGE` и текст справки команды (общая справка CLI
   `orchestrator/artel.py`) называют флаг `--target <имя>`. Флаг без
   значения — отказ, как у `--tz`, задача не заводится.
   Рамка реализации (решение Оператора на гейте SPEC 12.10, В-2): флаг
   `--target <имя>` снимается из argv отдельным помощником по образцу
   `_new_set_arg` (`orchestrator/artel.py:1530-1542`) до
   `_parse_new_args`; форма возврата `_parse_new_args` (`(title, tz_path)`
   либо `None`) не меняется; когда флага нет и запись `targets.yaml` одна,
   `_cmd_new` вызывает `catalog.cmd_new` без keyword `target=` — тем же
   вызовом, что сегодня. Существующие утверждения
   `tests/test_task_model_set_units.py:166` и
   `tests/test_new_argv_parsing.py:24-30` не меняются.
2. Имя проекта сверяется с `targets.yaml` в `catalog.cmd_new` в самом
   начале — до чтения ТЗ, до `workspace.ensure_clone` и до расхода id,
   ветки и строки БД. Неизвестное имя — именованный отказ, в тексте
   которого перечислены объявленные в `targets.yaml` проекты; задача не
   заводится. Исключение (решение Оператора на гейте SPEC 12.10, В-1,
   вариант (а)): для `target=None` (артель) при нечитаемом `targets.yaml`
   (файла нет либо он не разбирается) сверка проекта пропускается с
   предупреждением в выводе, и `new` задачи артели работает как сегодня —
   по образцу `repo_context.resolve`, который разрешает артель без чтения
   `targets.yaml` (`orchestrator/repo_context.py:82-89`). То же — для `new`
   без `--target` в командной строке: при нечитаемом `targets.yaml`
   правило требования 3 не отказывает, задача уходит в артель.
3. Если в `targets.yaml` больше одной записи, `new` без `--target`
   отказывает именованно («укажи проект: --target <одно из …>» с перечнем
   объявленных проектов); задача не заводится. Пока запись одна (сегодня —
   только artel), `new` без флага заводит задачу в неё, как сейчас.
   Правило обязательности проекта действует только в командной строке
   (`_cmd_new` / `_parse_new_args`, через вспомогательную функцию в
   `orchestrator/catalog.py`); `catalog.cmd_new(target=None)` по-прежнему
   означает артель и не отказывает при любом числе записей
   `targets.yaml` — вызов без target из `orchestrator/canary_drive.py` и
   существующие вызыватели и тесты не меняются.
4. Строка ТЗ `Проект: <имя>` (в начале строки):
   - одна такая строка — обязана совпасть с проектом задачи (из флага или
     из правила требования 3); несовпадение — отказ до создания задачи;
   - строки нет — проверка не делается;
   - две и более строки — отказ до создания задачи;
   - для канарейки (`canary=True`) строка «Проект:» не разбирается (как и
     «Порядок:»).

   Порядок проверок: проект из флага или правила требования 3 → сверка с
   `targets.yaml` → сверка со строкой «Проект:» → только затем
   `workspace.ensure_clone`. Все отказы требований 1–4 происходят до
   `ensure_clone`: после отказа клон проекта на диске не появляется, id,
   ветка документов и строка БД не расходуются.
5. Проект задачи печатается в выводе `new` и пишется в запись журнала о
   заведении задачи.
6. `target-init <имя>`: имя сверяется с `targets.yaml` до создания
   каталогов проекта (неизвестное имя — отказ, каталоги не создаются);
   после каталогов команда заводит клон проекта тем же
   `workspace.ensure_clone` (идемпотентно — существующий клон не
   трогается); неудача клона — именованный отказ с причиной, созданные
   каталоги остаются. Существующие тесты, вызывающие `target-init` для
   проекта без заранее заведённого клона (`tests/test_doctor.py`,
   `tests/test_git_fixation.py`), переставляются: клон проекта
   (`make_project_repo` / клон артели) создаётся до `target-init`;
   проверки тестов не меняются. Устаревшие комментарии о том, что
   `target-init` клон не заводит, правятся: `tests/test_git_fixation.py:246`
   («`cmd_target_init` его не заводит, это ТЗ-2») и
   `tests/test_multitarget.py:273-275` («его заводит
   `workspace.ensure_clone`, не `target-init`»). Перечень — раздел
   «Меняемое поведение».
7. Свойства требований 1–6 держат тесты в `tests/` с заявками «Ловит
   мутацию» на мутации: флаг не передан в `cmd_new`; неизвестный проект
   создал задачу (или потратил id/ветку); при двух записях `new` без флага
   ушёл в artel; строка «Проект:» не сверена или сверена после создания
   задачи (или после клона); `target-init` не завёл клон; правило
   требования 3 перенесено в `cmd_new` и сломало вызов без target
   (канарейка); `target-init` создал каталоги проекта до сверки имени с
   `targets.yaml`; при нечитаемом `targets.yaml` `new` задачи артели
   (`target=None`) отказал (исключение требования 2). Для двух записей — временный `targets.yaml` в песочнице
   тестов (настоящий `targets.yaml` не меняется). Мутацию, которую уже
   ловит долгоживущий приёмочный тест автора тестов
   (`tests/test_01m4rrw7ft1ee77ey9y462azkc_*.py`), разработчик повторным
   тестом не дублирует. Существующие тесты не ослабляются.
8. Карта `docs/codebase-map.md` свежа: в той же задаче она регенерируется
   `python3 scripts/codebase_map.py` после правки кода (флаг `--target`,
   клон в `target-init`).

## Критерии приёмки

AC-1. `new "<название>" --target <имя>` с объявленным в `targets.yaml`
`<имя>` вызывает `catalog.cmd_new` с `target=<имя>`, и задача заводится со
значением `tasks.target = <имя>`. `_NEW_USAGE` и общая справка CLI
содержат `--target <имя>`. `new "<название>" --target` без значения —
отказ (выход с ненулевым кодом), задача не заведена.

AC-2. `catalog.cmd_new(..., target=<имя, которого нет в targets.yaml>)` —
отказ, текст которого называет все объявленные проекты `targets.yaml`; ТЗ
не читается (отказ наступает и при нечитаемом пути `--tz`),
`workspace.ensure_clone` не вызывается, новой строки в `tasks`, новой
ссылки документов задачи и каталога клона проекта не появляется.

AC-3. При `targets.yaml` с двумя записями (временный файл песочницы)
`new "<название>"` без `--target` в командной строке отказывает текстом с
«--target» и перечнем объявленных проектов; задача не заведена (ни строки
БД, ни ссылки документов). При `targets.yaml` с одной записью `artel`
`new "<название>"` без флага заводит задачу с `tasks.target = artel`.

AC-4. При `targets.yaml` с двумя записями прямой вызов
`catalog.cmd_new("<название>")` без `target` (в том числе с
`canary=True`, как из `orchestrator/canary_drive.py`) не отказывает и
заводит задачу с `tasks.target = artel`.

AC-5. На объявленном не-artel проекте без клона (временный `targets.yaml`
песочницы с двумя записями — `artel` и этим проектом; клона проекта до
вызова на диске нет), задача с `target=<этот проект>`: ТЗ со строкой
`Проект: <имя>`, не совпадающей с проектом задачи, — отказ; ТЗ с двумя и
более строками `Проект:` — отказ. В обоих случаях отказ наступает до
`workspace.ensure_clone`: ни строки БД, ни ссылки документов, ни каталога
клона проекта после отказа нет. ТЗ с одной совпадающей строкой и ТЗ без
строки «Проект:» заводят задачу. При `canary=True` ТЗ со строкой
«Проект:», не совпадающей с проектом задачи, не вызывает отказа.

AC-6. На объявленном не-artel проекте без клона (временный `targets.yaml`
песочницы с двумя записями; клона проекта до вызова на диске нет)
`new "<название>" --target <этот проект>` заводит задачу; вывод `new`
содержит имя проекта, и запись журнала с действием `created` этой задачи
(`steps`) содержит имя проекта.

AC-7. `target-init <имя>` для объявленного проекта без клона создаёт
каталоги проекта и клон проекта (каталог `repo_context`/
`workspace.repo(<имя>)` — git-репозиторий); повторный `target-init` того
же проекта завершается без ошибки и существующий клон не трогает.
Неудача `workspace.ensure_clone` — отказ (ненулевой выход), текст которого
содержит причину неудачи; каталоги проекта после отказа остаются на
диске.

AC-8. `target-init <имя, которого нет в targets.yaml>` — отказ, и ни один
каталог проекта `<имя>` (`projects.project_dir(<имя>)`) не создан.

AC-9. При нечитаемом `targets.yaml` (файла нет либо он не разбирается)
`catalog.cmd_new("<название>")` без `target` и `new "<название>"` без
`--target` в командной строке не отказывают: задача заводится с
`tasks.target = artel`, а вывод содержит предупреждение о пропущенной
сверке проекта с `targets.yaml`.

## Меняемое поведение

Ожидания (литералы утверждений) существующих тестовых методов задача не
меняет: проверки `_NEW_USAGE` в `tests/test_new_argv_parsing.py` ищут
подстроку `new "<название>"`, которая в новой справке сохраняется, а
`tests/test_task_model_set_units.py` текст справки литералом не сверяет;
по рамке требования 1 не меняются и `tests/test_task_model_set_units.py:166`
(`cmd_new` вызван без `target=`), и `tests/test_new_argv_parsing.py:24-30`
(форма возврата `_parse_new_args`).
Ниже — перечень перестановок подготовки тестов по требованию 6 (без смены
утверждений): клон проекта создаётся до вызова `projects.cmd_target_init`;
плюс правка устаревших комментариев требования 6
(`tests/test_git_fixation.py:246`, `tests/test_multitarget.py:273-275`).

tests/test_git_fixation.py::ExternalTargetAdvanceIgnoresDirtyCheckTest::setUp —
`make_project_repo("sled")` до `cmd_target_init("sled")`; комментарий
~246 «`cmd_target_init` его не заводит, это ТЗ-2» правится.

tests/test_git_fixation.py::ExternalIntegrityIncidentBlocksRunTest::setUp —
`make_project_repo("sled")` до `cmd_target_init("sled")`.

tests/test_git_fixation.py::ExternalApproveDoesNotCommitOthersWorkInProgressTest::setUp —
`make_project_repo("sled")` до `cmd_target_init("sled")`.

tests/test_doctor.py::RecoveryCheckTest::setUp — `make_project_repo("sled")`
до `cmd_target_init("sled")`.

tests/test_doctor.py::RecoveryCheckTest::test_artel_gets_the_same_recovery_sverka_as_any_target —
клон артели до `cmd_target_init(config.DEFAULT_TARGET)`.

## Оценка объёма и деление

Прогноз диффа: 30 КиБ.

Сработавшие сигналы: «число затрагиваемых модулей/файлов» (5 записей
`zones:` из ТЗ, из них `tests/` и `docs/codebase-map.md` — общие зоны
`config.COMMON_ZONES`; модулей кода — три: `orchestrator/artel.py`,
`orchestrator/catalog.py`, `orchestrator/projects.py`) и вслед за ним
«прогноз диффа не дан» (прогноз выше дан: ~30 КиБ — ниже половины потолка
гейта ёмкости, 128 КиБ). Остальные сигналы не срабатывают: 9 критериев,
`budget_usd` 40, формулировок неопределённости нет.

Материал для решения Оператора — **монолит**. Атомарной смены механики,
которую нельзя разрезать, здесь нет: технически отделима часть
«клон в `target-init`» (требование 6, AC-7..AC-8, зона
`orchestrator/projects.py` + перестановки в `tests/test_doctor.py`,
`tests/test_git_fixation.py`) от части «`new --target` и выбор проекта»
(требования 1–5, AC-1..AC-6, зоны `orchestrator/artel.py`,
`orchestrator/catalog.py`), и каждая из двух была бы мержима отдельно с
зелёной планкой. Довод за монолит — объём, не неделимость: три модуля
кода, малый дифф, ТЗ одной рамкой $40; деление добавило бы второй полный
цикл шагов (analyst, test_author, developer, reviewer) при выигрыше в
размере ревью, которого при ~30 КиБ нет. Решение — за Оператором на
гейте SPEC; при выборе нарезки — две части в порядке выше
(первая — `new --target`).

## Не входит

- Правка `scripts/codebase_map.py` — требование 8 только запускает его
  для регенерации карты.
- Запись sled в `targets.yaml` — Оператор отдельным doc-commit; настоящий
  `targets.yaml` задача не меняет.
- Бриф роли для внешнего проекта и `CLAUDE.md` целевого проекта (ТЗ-4,
  этап 2).
- Профиль тестов не на pytest пульта и песочница (ADR и B3).
- Токен проекта (ТЗ-4, этап 1).
- `doctor` для внешнего проекта (ТЗ-5).
- Разбор слов Оператора в чате (их переводит в `--target` ассистентская
  сессия).
- Правка путей «только чтение» ТЗ: `targets.yaml`, `orchestrator/targets.py`,
  `orchestrator/workspace.py`, `orchestrator/repo_context.py`,
  `orchestrator/config.py`, `orchestrator/canary_drive.py`,
  `orchestrator/fsm.py`, `orchestrator/brief.py`,
  `tests/test_invariants.py`, `docs/invariants.md`, `docs/adr/`,
  `docs/roadmap.md`, `docs/backlog.md`, `docs/operator-session.md`,
  `skills/`, `templates/`, `CLAUDE.md`, `roles.yaml`, `.github/`.
- Свежесть `docs/codebase-map.md` (требование 8) отдельным критерием
  приёмки не оформлена — её держит пульт (CI-джоб свежести карты).
- Неослабление существующих тестов (требование 7) отдельным критерием не
  оформлено — его держит пульт (гейт неослабления тестов).

## Материалы
- `tasks/01M4RRW7FT1EE77EY9Y462AZKC/TZ.md` — ТЗ-2, роадмап §4.
- `orchestrator/catalog.py::cmd_new`, `orchestrator/artel.py::_cmd_new` /
  `_parse_new_args` / `_new_set_arg`, `orchestrator/projects.py::cmd_target_init`,
  `orchestrator/workspace.py::ensure_clone`, `orchestrator/targets.py::target`/`load`.
- `tests/sandbox.py::make_project_repo` — клон внешнего проекта в
  песочнице тестов.
