---
task: 01M58FNWBV25FF26E7AZ9Q9912
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/targets.py, orchestrator/project_profile.py, orchestrator/repo_context.py, orchestrator/acceptance.py, tests/
budget_usd: 45
---

# SPEC: G1а (часть 1) — компоненты проекта в записи targets.yaml: схема, profile_of, выбор по путям

## Контекст
Это первая задача волны G по ADR-0026 (`docs/adr/0026-project-components-and-outcome-gates.md`, принят Оператором 19.10.2026; «Решение», пп. 1–3). Сегодня профиль тестов проекта — одно поле записи `test_profile` (`orchestrator/targets.py:43-73`; проверка — `check` `:182-190` и `_check_profile` `:290-319`). Его разбирает `orchestrator/project_profile.py`: `Profile`, `decide` `:143`, `for_task` `:175`, `full_suite_limit` `:179`. Источник профиля — `repo_context.profile_of` (`orchestrator/repo_context.py:139-151`). Проект из нескольких частей с разными раннерами (sled: backend и frontend) так не описать. Задача вводит схему `components:`, её чтение читателями профиля и выбор компонентов по путям. Прогоны по компонентам исполняет задача G1б.

По ответу Оператора (ANSWER-1, п. 9) это **часть 1** прежней G1а. Проверки `doctor` (`tools`, `paths_source`, `workdir`; п. 5 ТЗ) и ключ кэша итога (п. 6 ТЗ) вынесены в отдельную задачу «G1а-2». Её заводят после мержа этой. `targets.yaml` разбирает `orchestrator/yamlmini.py` (`targets.load`, `targets.py:111`), а этот модуль не меняется (ANSWER-1, п. 1). Поэтому `components:` — отображение, а не блочный список.

## Требования

1. Запись проекта в `targets.yaml` может нести поле `components:` вместо `test_profile`. Если в записи есть оба поля, проверка записи (`targets.check`) отказывает.
2. Форма `components:` задана ANSWER-1, п. 1. Это непустое отображение «имя компонента → поля компонента». `targets.load` читает его без правки `yamlmini.py`. Имя компонента — ключ отображения, отдельного поля `name` нет. Имя не содержит `:`, иначе идентификатор из требования 7 не разобрать. Поля компонента — непустое отображение. Если `components:` пусто или не отображение, проверка отказывает.
3. Поля компонента и их формы заданы ТЗ (п. 1) и ANSWER-1 (пп. 1, 3, 5, 8). Каждое поле проверяется по форме. Отказ называет проект, компонент и поле. Неизвестное поле компонента (в том числе `name`) — отказ.
   - Прежние подполя профиля — тех же видов, что в `targets.PROFILE_FIELDS`: `command`, `long_lived_dir`, `long_lived_name`, `weakening_scope`, `mutation_claim_scope`, `full_suite_timeout_sec`, `runner`, `workdir`, `env`, `long_lived_imports`. Исключения перечислены ниже.
   - `report` — `junit-xml` или `pult-vitest`. Значение `pult-vitest` только допустимо: отчётчика пока нет, он появится в G1б.
   - `install`, `checks_local` — одна команда: непустой список непустых строк.
   - Правило `workdir`/`env` (`targets.PROFILE_OWN_RUNNER_ONLY`, `targets.py:73`, `:310-318`):
     - у записи с одним компонентом действует так же, как у `test_profile`: `workdir` или `env` при `runner`, отличном от `pytest-own` (в том числе без `runner`, то есть `pult-pytest`), — отказ формы;
     - у записи с несколькими компонентами не действует: `workdir` и `env` допустимы при любом `runner` (ANSWER-1, п. 3).
   - `long_lived` — шаблон пути от корня репозитория с обязательным заполнителем `<id>`. Кроме него допустимы только `<dir>` и `<name>`. В одном компоненте — либо `long_lived`, либо пара `long_lived_dir`/`long_lived_name`; обе формы сразу — отказ.
   - `plank_layout` — шаблон пути с обязательным `<id>`.
   - `repo` — непустая строка; если поля нет, это имя записи проекта. Значение, отличное от имени записи, — отказ с причиной «несколько репозиториев не исполняются».
   - `report_args`, `select`, `failure_errors`, `layers` — списки непустых строк.
   - `knowledge` — список путей от корня репозитория: относительных, без `..` и без ведущего `/`. Это не имя файла `*.yaml`, в отличие от одноимённого поля записи (`targets.py:80-81`).
   - `tests`, `test_support` — списки масок `project_profile.mask_matches`. Маска с `{` или `}` — отказ с причиной «альтернативы `{a,b}` не поддерживаются — разверните в несколько масок».
   - `paths` — регулярные выражения путей от корня репозитория: одна строка или потоковый список. Каждое выражение должно компилироваться `re.compile`. Выражение с `"`, `'`, `,`, `[` или `]` — отказ формы с причиной.
   - У записи с несколькими компонентами `paths` обязательно у каждого компонента и непусто: если поля нет или стоит `paths: []` — отказ.
   - `paths_source` — необязательное отображение ровно из подполей `file` и `key`; оба — непустые строки. Лишнее подполе — отказ.
   - `depends_on` — отображение «имя компонента-поставщика → поля». Поставщик — другой компонент той же записи, не сам компонент. Поля — ровно `via` и `paths`, оба обязательны; лишнее поле — отказ. `via` — одно из `paths`, `files`, `contract`. `paths` — той же формы, что `paths` компонента. `contract` только разбирается и проверяется по форме.
   - `tools` — отображение «имя инструмента → строка требуемой версии». Если `tools` не отображение или значение в нём не строка — отказ.
   - `long_lived_imports` у компонента записи артели (`config.DEFAULT_TARGET`) недопустимо — по тому же правилу, что у `test_profile` (`targets.PROFILE_EXTERNAL_ONLY`, `targets.py:184-190`).
4. Для записей с `test_profile` (сегодня это артель и sled) всё остаётся прежним: разбор, поля `Profile`, исходы `decide`/`for_task`/`full_suite_limit` и все тексты. Это касается и отказа `test_profile.report` («ожидается junit-xml», `targets.PROFILE_REPORTS`). Такая запись читается как один компонент с именем `default`. Прежнее поведение закрепляется тестами до правки кода (ТЗ п. 2).
5. `repo_context.profile_of` (ANSWER-1, п. 2; уточнение Оператора на гейте SPEC):
   - `ProfileAnswer` получает признак `multi: bool`, по умолчанию `False`. Прежние вызовы конструктора `ProfileAnswer` (в том числе в `tests/`) остаются верными без правки.
   - Запись с одним компонентом даёт исход PRESENT, `multi=False`. Значения профиля — подполя этого компонента из `targets.PROFILE_FIELDS`. Дальше `decide`/`for_task` ведут себя так же, как для записи с теми же подполями в `test_profile`.
   - Если у такого компонента нет подполя, обязательного у `test_profile` (`command`, `long_lived_dir`, `long_lived_name`, `weakening_scope`, `mutation_claim_scope`), исход — UNREAD, `multi=False`, причина называет компонент и подполе. `decide` отвечает отказом, без исключения.
   - Запись с несколькими компонентами даёт исход UNREAD, `multi=True`, причина — «запись проекта с несколькими компонентами исполняется после G1б».
   - Прочие исходы (ABSENT; UNREAD из-за негодного файла или записи) — прежние, `multi=False`.
6. Интерфейс в модуле `orchestrator/project_profile.py` (ТЗ п. 3; ADR-0026 п. 3):
   - `components(target: str) -> tuple` — компоненты записи проекта `target` в порядке записи. Запись с `test_profile` даёт один компонент `default`, запись ABSENT — пустой кортеж. Если файл или запись не годны — `targets.TargetsError`. У каждого элемента есть имя компонента и его поля.
   - `select_components(target: str, paths) -> tuple[str, ...]` — имена затронутых компонентов в порядке записи (требование 7). `paths` — набор путей от корня репозитория (итерируемое строк).
   - `test_id(component: str, path: str, name: str, n: int | None = None) -> str` и `parse_test_id(text: str) -> tuple[str, str, str, int | None]` — требование 8.
7. Выбор компонентов (ТЗ п. 3), `select_components`:
   - Компонент затронут, если путь подходит под его `paths` (`re.search` по пути от корня репозитория) или под маску его `test_support` (`mask_matches`).
   - Компонент затронут и как потребитель: если путь подходит под `paths` элемента его `depends_on` вида `paths` или `files`. Вид `contract` выбор не расширяет.
   - Если хоть один путь набора не задел ни одного компонента, выбор — все компоненты записи, а не пустой.
   - У записи с одним компонентом (в том числе `default` из `test_profile`) выбор — этот компонент при любом наборе путей. У записи ABSENT — пустой кортеж.
8. Идентификатор теста компонента (ADR-0026 п. 3). `test_id` формирует строку литерального формата `<компонент>:<путь файла от корня репозитория>::<полное имя>` и при заданном `n` дописывает `#<n>`. `parse_test_id` разбирает её обратно на части. Полное имя может само содержать `::` (класс и метод). Формат зон задачи и `no_paths` не меняется.
9. Отказ до G1б во всех читателях профиля (ТЗ п. 4; ANSWER-1, п. 2). Для записи с несколькими компонентами причина «запись проекта с несколькими компонентами исполняется после G1б» доходит до трёх читателей:
   - `decide`/`for_task` — отказ задаче (`Decision.refusal`);
   - `full_suite_limit` — `targets.TargetsError`;
   - `suite_run._profile_command` — отказ. Его ветка UNREAD уже есть, `suite_run.py` не меняется.
10. `acceptance._task_own_profile` (уточнение Оператора на гейте SPEC):
    - При UNREAD с `multi=True` функция отказывает: бросает `targets.TargetsError` с причиной из `profile_of`, как `full_suite_limit` в требовании 9. Вызывающий, который идёт через `decide`/`for_task`, получает тот же исход как `Decision`-отказ с этой причиной.
    - На всех прочих исходах — прежнее поведение. UNREAD с `multi=False` и ABSENT дают `None`. PRESENT даёт профиль `pytest-own` или `None` для `pult-pytest`. `tests/test_acceptance_suite_profile.py` остаётся без правки.
    - `acceptance.acceptance_suite` при этом отказе не зовёт `full_suite` и пропускает исключение `TargetsError` с причиной.
    - `acceptance.drop_from_code_copy` при этом отказе убирает `tasks/<id>/` как прежде, пропускает уборку выкладки (`_drop_layout`) и не падает. Перехват не шире отказа этого требования: прочие исключения уборки ведут себя как сейчас.
    - Прочие вызывающие `_task_own_profile` и `drop_from_code_copy` вне `acceptance.py` не правятся. При отказе `decide` они недостижимы: `runner.py:1218`, `checkpoint.py:1237`, `fsm_advance.py:607`, `amend.py:548`, `:723`, `:765`, `pull.py:665`, `plank_run.py:220`.
    - Ограничение ТЗ «в `acceptance.py` только ключ кэша» для этой функции снято Оператором (ANSWER-1, п. 2).
11. Тесты задачи детерминированы и не ходят в сеть. Учебные записи с одним и с двумя компонентами (`depends_on` вида `files`) записываются текстом файла и читаются через `targets.load`, а не только словарём в `targets.check` (ТЗ п. 7). Исключение — случаи, которые текстом `yamlmini` не записать, например имя компонента с `:` (`yamlmini.py:146` режет ключ по первому `:`). Их проверяют словарём в `targets.check`.

## Критерии приёмки

AC-1. Учебный текст `targets.yaml` с записью из двух компонентов `backend` и `frontend` проходит `targets.load` без отказа. Запись несёт `paths`, `test_support`, `depends_on` вида `files` у `frontend` на `backend`, `paths_source`, `tools`, `install`, `long_lived` и `knowledge` в формах требования 3. Разобранные значения доходят до вызывающего: имена компонентов и `depends_on.backend.via == "files"`. `project_profile.components` на этой записи даёт `backend` и `frontend` в порядке записи.

AC-2. Каждое поле требования 3 с неверной формой даёт отказ `targets.check`, называющий компонент и поле. Подслучаев отказа не меньше одного на каждое поле:
- `components:` пустое; `components:` не отображение; поля компонента не отображение;
- неизвестное поле компонента, в том числе `name`; имя компонента с `:`;
- каждое прежнее подполе `command`, `long_lived_dir`, `long_lived_name`, `weakening_scope`, `mutation_claim_scope`, `full_suite_timeout_sec`, `runner`, `workdir`, `env`, `long_lived_imports` — значение не того вида, что в `targets.PROFILE_FIELDS`;
- `long_lived_imports` у компонента записи артели;
- `workdir`, а также `env`, у записи с одним компонентом при `runner: pult-pytest` или без `runner`;
- `report` вне `junit-xml|pult-vitest`;
- `install` пустой; `checks_local` пустой;
- `long_lived` без `<id>`; `long_lived` с иным заполнителем; `long_lived` вместе с `long_lived_dir`;
- `plank_layout` без `<id>`;
- `repo` — пустая строка; `repo`, отличный от имени записи, — отказ с текстом «несколько репозиториев не исполняются»;
- `report_args`, `select`, `failure_errors`, `layers` — каждое не список непустых строк;
- `knowledge` с путём, содержащим `..`; `knowledge` с путём с ведущим `/`; `knowledge` не список;
- `tests`, `test_support` — каждое не список; маска `tests` или `test_support` с `{` — отказ с текстом «альтернативы `{a,b}` не поддерживаются — разверните в несколько масок»;
- `paths`: выражение не компилируется; выражение содержит `,`, `[` или `]`; у записи с несколькими компонентами `paths` нет у компонента; у такой записи `paths: []`;
- `paths_source` без `key`; `paths_source` с лишним подполем;
- `depends_on` на несуществующий компонент; `depends_on` на сам компонент; `via` вне `paths|files|contract`; `depends_on` без `via`; `depends_on` без `paths`; `depends_on` с лишним полем;
- `tools` не отображение; значение `tools` не строка.

Без отказа проходят: `report: pult-vitest`; `workdir`/`env` без `runner` у компонента записи с несколькими компонентами.

AC-3. Запись, несущая одновременно `test_profile` и `components:`, получает отказ проверки записи.

AC-4. Записи с `test_profile` (артель и учебная запись внешнего проекта) ведут себя как до правки: `Profile`, исходы `decide`/`for_task`/`full_suite_limit` и их тексты те же. Отказ `test_profile.report: pult-vitest` даёт тот же текст, что раньше. `components` для такой записи — один компонент `default`, и `select_components` при любом наборе путей даёт `("default",)`. У записи без `test_profile` и без `components:` (ABSENT) оба вызова дают пустой кортеж.

AC-5. Запись с одним элементом `components:` даёт от `decide`/`for_task` тот же `Profile`, что запись с теми же подполями в `test_profile`. `profile_of` на ней даёт PRESENT с `multi=False`. Если у единственного компонента нет `long_lived_dir`, `decide` отвечает отказом с причиной, называющей это подполе, а не исключением.

AC-6. Выбор `select_components` на учебной записи AC-1, где `frontend` зависит от `backend` по `depends_on` вида `files`:
- путь backend вне `paths` того `depends_on` → `("backend",)`;
- путь, попавший в `paths` того `depends_on`, → `("backend", "frontend")`;
- путь, попавший в маску `test_support` компонента и не в его `paths`, → этот компонент;
- путь `docs/x.md` → `("backend", "frontend")`;
- набор из пути backend и `docs/x.md` → `("backend", "frontend")`;
- у записи с одним компонентом любой путь → этот компонент.

AC-7. Идентификатор теста компонента:
- `test_id("backend", "backend/tests/test_x.py", "TestA::test_b")` даёт литерал `"backend:backend/tests/test_x.py::TestA::test_b"`;
- с `n=2` даёт `"backend:backend/tests/test_x.py::TestA::test_b#2"`;
- `parse_test_id` каждой из этих строк возвращает исходные части: `("backend", "backend/tests/test_x.py", "TestA::test_b", None)` и `(…, 2)` соответственно.

Проверяются форма без `#<n>`, форма с `#<n>` и полное имя с `::`.

AC-8. Проект, запись которого несёт два компонента:
- `profile_of` даёт UNREAD с `multi=True`;
- отказ `decide`/`for_task`, `TargetsError` от `full_suite_limit` и отказ `suite_run._profile_command` содержат текст «запись проекта с несколькими компонентами исполняется после G1б»;
- ни один из этих читателей не даёт профиль, исход «пропуск» или прежний предел `config`.

AC-9. Отказ `_task_own_profile`:
- Проект, запись которого несёт два компонента (`profile_of` — UNREAD, `multi=True`):
  - `acceptance.acceptance_suite` не зовёт `full_suite` и бросает `targets.TargetsError` с текстом «запись проекта с несколькими компонентами исполняется после G1б»;
  - `acceptance.drop_from_code_copy` убирает `tasks/<id>/` из рабочей копии и не бросает исключения.
- UNREAD с `multi=False` (битый `test_profile`), ABSENT и PRESENT с `runner: pult-pytest` — прежний вызов `full_suite` без `command`.

## Оценка объёма и деление
Сработавший сигнал — `budget_usd`: $45 при пороге $30. Файлов зоны вне общих — 4 (`orchestrator/targets.py`, `orchestrator/project_profile.py`, `orchestrator/repo_context.py`, `orchestrator/acceptance.py`), критериев — 9; оба числа ниже порогов.

Деление уже выполнил Оператор (ANSWER-1, п. 9): эта задача — часть 1, а «G1а-2» (`doctor` и ключ кэша) Оператор заводит после её мержа. Поэтому раздела «Деление» нет: подзадачу здесь не заявляем, чтобы пульт не завёл её второй раз.

Обоснование монолита части 1 — материал для решения Оператора:
- Схема (`targets.py`), её чтение (`repo_context.profile_of`) и отказ читателей (`project_profile.py`, `acceptance._task_own_profile`) — одна смена механики. Без отказа читателей проверка записи принимала бы `components:`, а полный набор (`_task_own_profile` → `None`) шёл бы прежней формой пульта на проекте с несколькими компонентами. Это был бы обход отказа до G1б.
- Выбор компонентов и идентификатор теста — функции над той же схемой, у них нет своих читателей. Отделить их — значит пройти отдельные шаги аналитика, аудита и ревью ради трёх функций в `project_profile.py`.
- Рамка $45 задана Оператором (ANSWER-1, п. 9). Она в пределах класса «до 10 критериев и до 4 файлов» (~$40) плюс одна итерация ревью.

## Не входит
- Проверки `doctor` (`tools` и сравнение версий, `paths_source` против переменной CI, существование `workdir`; ТЗ п. 5) — задача «G1а-2» после мержа этой (ANSWER-1, пп. 4, 6, 9). `orchestrator/doctor/` в зоны не входит.
- Перехват `TargetsError` в `doctor/cli.py:93-94` (`full_suite_timeout_check` → `full_suite_limit`) — тоже задача G1а-2. До G1а-2 записей с `components:` в `targets.yaml` нет, `targets.yaml` в этой задаче не меняется. Поэтому падение `doctor` на записи с несколькими компонентами в этой задаче недостижимо.
- Ключ кэша итога полного набора (`acceptance._own_suite_result_key`: файлы блокировки, `tools`; ТЗ п. 6) — «G1а-2» (ANSWER-1, п. 7). Поле `tools` в `Profile` не добавляется.
- Правка `orchestrator/yamlmini.py` и расширение разбора: блочные списки, потоковые отображения, вложенные списки, кавычки в потоковом списке (ANSWER-1, п. 1).
- Уникальность имени компонента — ограничение `yamlmini`, его в этой задаче не снять. Повторный ключ-имя компонента `yamlmini` молча перезаписывает (`yamlmini.py:155`, `:159`): ранее объявленный компонент с тем же именем пропадает из записи без отказа. Проверки уникальности сверх отображения в этой задаче нет.
- Правка `orchestrator/suite_run.py` (ANSWER-1, п. 2) и прочих вызывающих `_task_own_profile`/`drop_from_code_copy` вне `acceptance.py`: `runner.py`, `checkpoint.py`, `fsm_advance.py`, `amend.py`, `pull.py`, `plank_run.py`. При отказе `decide` они недостижимы (требование 10).
- В `orchestrator/acceptance.py` правятся только `_task_own_profile` и то, что нужно для его отказа внутри `acceptance.py` (`acceptance_suite`, `drop_from_code_copy`). Требование 10 это перечисляет.
- Исполнение прогонов по компонентам, отчёт JUnit, отчётчик Vitest, окружение Vitest, установка зависимостей пультом — задача G1б. Планка и долгоживущие файлы по компоненту, в том числе исполнение `long_lived`/`plank_layout`, — G2. Гейт неослабления по исходам — G3.
- Перевод записи sled в `targets.yaml` и правка черновика записи в ADR-0026 под схему требования 2 — этап 2 плана, их делает Оператор. `targets.yaml` и `docs/adr/0026-project-components-and-outcome-gates.md` только читаются.
- Многорепозиторное исполнение: `repo`, отличный от имени записи, отвергается (требование 3). `depends_on` вида `contract` только разбирается.
- Смена формата зон задачи и `no_paths`.
- Правка `orchestrator/advance_gates/`, `orchestrator/fsm*.py`, `scripts/guard.py`, `orchestrator/doctor/`, `docs/backlog.md` — только чтение. Если правка вне зон понадобится — эскалация.
- Смена ожиданий существующих тестов `tests/` — не требуется. В частности, `tests/test_acceptance_suite_profile.py` остаётся без правки (требование 10).
- Зелёный полный набор `tests/`, зелёный CI ветки, неизменность защищённых путей, непревышение бюджета — эти проверки держит пульт.

## Материалы
- ТЗ: `tasks/01M58FNWBV25FF26E7AZ9Q9912/TZ.md`.
- Ответ Оператора: `tasks/01M58FNWBV25FF26E7AZ9Q9912/ANSWER-1.md`.
- Решения Оператора по `SPEC-AUDIT.md` даны возвратом с гейта SPEC 19.10: признак `multi`, форма отказа, интерфейс, AC-2/AC-7, правило `workdir`/`env` и `repo`, `paths: []`, `long_lived_imports` у артели.
- ADR-0026: «Решение», пп. 1–3. Черновик записи sled — раздел «Описание sled после ADR»; его форму Оператор приведёт к требованию 2.
- Разбор `yamlmini`: `orchestrator/yamlmini.py:16-20` (что не разбирается), `:145` (блочные списки), `:146` (ключ режется по первому `:`), `:174-195` (потоковые списки). Скаляр `22` без кавычек читается числом. Поэтому значение `tools` пишется строкой в кавычках, как и `env` (`targets._profile_value_error`, вид `mapping`).
- Текущий код:
  - `orchestrator/targets.py:43-73`, `:182-190`, `:290-319`, `:334-394`;
  - `orchestrator/project_profile.py:46-61` (`mask_matches`), `:65-121`, `:143-187`;
  - `orchestrator/repo_context.py:123-151` (`ProfileAnswer`, `profile_of`);
  - `orchestrator/acceptance.py:1285-1302` (`drop_from_code_copy`), `:2372`, `:2380-2400` (`_task_own_profile`);
  - `orchestrator/suite_run.py:271-294`.
- Прямые следствия ТЗ и ответа, внесённые сверх буквы:
  - имя компонента без `:` (требование 2) — иначе идентификатор требования 8 не разобрать;
  - исход UNREAD для единственного компонента без обязательного подполя `test_profile` (требование 5). Основание — «ведёт себя как `test_profile`»: у `test_profile` такое подполе обязательно, а `Profile.from_values` без него бросает `KeyError` в `decide`;
  - если хоть один путь набора не задел ни одного компонента, выбор — все компоненты (требование 7). Основание — ТЗ: «путь, не задевший ни одного компонента, — все компоненты»;
  - вид исключения `_task_own_profile` — `targets.TargetsError`, как у `full_suite_limit` (требование 10). Так у отказа одна форма на оба места;
  - отказ «несколько репозиториев не исполняются» применяется к `repo` любого компонента, не только единственного: многорепозиторное исполнение в этой волне не появляется.
