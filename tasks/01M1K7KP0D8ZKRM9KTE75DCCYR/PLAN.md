---
task: 01M1K7KP0D8ZKRM9KTE75DCCYR
type: plan
author_role: developer
status: draft
schema_version: 3
---

# PLAN: Скилы и правила в бриф роли — из main, не из ветки задачи

## Подход
Скилы (`skills/*.md`) и `CLAUDE.md` — правила системы, не артефакты
задачи: с этой задачи они читаются ветко-корректным чтением через git с
ГОЛОВЫ ветки `main` пульта (`gitcmd.show(config.MAIN_BRANCH, rel)`), тем
же приёмом, что инвариант 28 уже применяет к артефактам задачи
(`docs/invariants.md`) — только с обратным адресом. Артефакты задачи
(SPEC/PLAN/TZ/QUESTIONS/ANSWER) продолжают читаться с ветки задачи —
источник их чтения этой задачей не меняется (SPEC «Не входит»).

Два места читали эти компоненты с диска рабочей копии `config.ROOT`:
- `orchestrator/runner.py::_cmd_run` — скилы роли, буквальным
  `(config.ROOT / "skills" / f"{s}.md").read_text()`, без фингерпринта
  в журнале вовсе;
- `orchestrator/brief.py::developer_brief` — `CLAUDE.md`, буквальным
  `(config.ROOT / CONVENTIONS_REL).read_text()`.

Оба места переведены на `gitcmd.show`, оба журналируют sha256
фактически прочитанного main-текста той же механикой, что уже несёт
`brief._journal_component`/`_manifest_component` (действие журнала
«бриф: компонент», формат `<label>: sha256=<hex>`) — новый код не
изобретает второй способ журналирования.

Новая функция `brief.skills_text(conn, task_id, role, skill_names)`
инкапсулирует и чтение, и журналирование скилов (переиспользует
`brief.component_hash`, уже существующий), чтобы `runner.py` не заводил
собственную копию логики хэширования/журналирования компонента брифа.
Новая функция `brief._main_branch_text(task_id, rel)` — тот же приём для
одиночного файла (`CLAUDE.md`), с тем же вырожденным случаем «git не
ответил или файла там нет» → `sys.exit` с именованной причиной (тот же
приём, что уже несёт `_developer_spec_text` для SPEC.md).

`fixation.py`/`check_integrity` не тронуты (SPEC «Не входит», AC-5
зелён с рождения) — планка задачи (`tasks.fixed_sha`) сверяет голову
ветки задачи и чистоту `tasks/<id>/`, не содержимое скилов/CLAUDE.md;
смена main-компонента между срезами задачи не порождает инцидент
целостности уже сегодня, тест — регрессионная защита от возможной
будущей ошибки, не факт починки в этой задаче.

## Шаги

1. `orchestrator/brief.py`: добавить `_main_branch_text(task_id, rel)` и
   `skills_text(conn, task_id, role, skill_names)`; перевести
   `developer_brief` на `_main_branch_text` для `CLAUDE.md` вместо
   прямого чтения диска.
2. `orchestrator/runner.py::_cmd_run`: заменить чтение скилов с диска на
   `brief.skills_text(conn, task_id, role, skill_names)`; `sys.exit` с
   именованной причиной при отказе чтения (тот же приём, что и у
   соседнего `roles.RolesError`).
3. Тестовая инфраструктура (не локальные acceptance_tests — те залочены
   и не тронуты):
   - `tests/sandbox.py::fake_git` — добавить ответ на `show <ветка>:<путь>`
     (в лёгких песочницах без настоящих коммитов ответом служит диск
     `config.ROOT/<путь>`, который эти же песочницы уже наполняют
     фикстурами skills/CLAUDE.md).
   - `tests/test_multitarget.py::silent_git` — сузить отказ до
     `config --get` (докстринг теста и так называет цель «машина без
     identity», не «git полностью не отвечает»; раньше это не имело
     значения, поскольку скилы читались с диска в обход git).
   - `tests/test_review_package.py::CmdRunReviewPackageTest` — добавить
     содержимое skills/CLAUDE.md в `self.git.files` (фейк ветки `main`
     этого класса); `test_developer_step_has_no_package` — обновить точный
     список git-вызовов (добавились `show` скилов/CLAUDE.md, это теперь
     ожидаемо); `test_failed_diff_is_visible_in_the_journal` — сузить
     имитацию отказа с «git сломан целиком» (ломало бы и `show` скилов) до
     «ломается только сам diff пакета».
   - `tests/test_git_fixation.py::ExternalIntegrityIncidentBlocksRunTest` —
     фикстуры skills/CLAUDE.md перенесены ПЕРЕД `git commit` (были
     незакоммиченным диском после), иначе `git show main:...` их не находит.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | (не меняется — артефакты задачи, брифом не тронуто) |
| 3 | 1, 2 (журналирование той же механикой) |
| 4 | (не меняется — правила не планка, `fixation.py` не тронут) |
| 5 | 1, 2, 3 (юнит-регрессии в затронутых тестовых файлах) |

## Влияние на систему
Изменение сужено до способа чтения ДВУХ конкретных компонентов брифа
(скилы, CLAUDE.md) в двух модулях (`brief.py`, `runner.py`) — состав
брифа, чтение артефактов задачи, `fixation.py`/гейты/лимиты не тронуты.
Блок-радиус по тестам оказался шире ожидаемого: несколько файлов
(`tests/sandbox.py`, `tests/test_multitarget.py`,
`tests/test_review_package.py`, `tests/test_git_fixation.py`) гоняли
`runner.cmd_run` на лёгких git-заглушках, которые раньше не видели
запросов чтения скилов/CLAUDE.md через git (те шли в обход, с диска) —
эти заглушки обновлены точечно (см. «Шаги», п.3), ни один существующий
тест не ослаблен: списки/условия отказа сужены до буквально
задокументированного в их же докстрингах намерения, а не сняты.
Откат — вернуть оба чтения на `(config.ROOT / rel).read_text()`, тестовая
инфраструктура откатывается вместе (её правки — прямое следствие этой
задачи, не самостоятельные изменения).

### Подтяжка main (ADR-0012, ответ Оператора ANSWER-1, вариант A)
Ветка отстала от `main` на 62 коммита — за это время смержена стройка
A7 («Артель как внешний target»). `git merge main --no-edit` дал два
текстовых конфликта, оба разрешены по инструкции ANSWER-1:
- `docs/codebase-map.md` — взят `main`, карта тем же коммитом
  перегенерирована `scripts/codebase_map.py` (актуальна на голову
  мержа, несёт добавленную этой задачей `skills_text`).
- `tests/test_review_package.py::CmdRunReviewPackageTest.
  test_developer_step_has_no_package` — списки git-вызовов сведены:
  порядок сверен прогоном (`pytest tests/test_review_package.py`,
  79/79 OK), т.к. `artifact_source.resolve` после A7 больше не зовёт
  git вовсе (`rev-parse --abbrev-ref HEAD` из HEAD-версии теста ушёл),
  SPEC.md брифа теперь читается с артефактной ветки
  (`show artifact/<id>:...`) + `ls-tree` для ANSWER-n.md — поверх
  этого пути эта задача добавляет `show main:skills/*` (3 скила) и
  `show main:CLAUDE.md`.

После мержа `tests/` целиком красным (49 failed из 1306) — но не из-за
конфликта, а из-за скрытого расхождения: A7 завёл параллельный слой
подмены `gitcmd.show`/`gitcmd.ls_tree_files` в `tests/sandbox.py`
(`disk_backed_show`/`disk_backed_ls_tree_files`, класс, отдельный от
моего `fake_git`), чей `_tasks_relative_path` жёстко ждёт `rel`,
начинающийся с `"tasks/"` (`assert parts[0] == "tasks"`). Мой код зовёт
`gitcmd.show(main, "skills/*.md")`/`gitcmd.show(main, "CLAUDE.md")` —
`rel` вне этого контракта, `assert` падал в КАЖДОМ из ~15 тестовых
файлов, патчащих `gitcmd.show` на `disk_backed_show` (`test_brief.py`,
`test_agent_prompt.py`, `test_invariants.py` и другие — список см.
вывод `grep -rn disk_backed_show tests/`). Правка — точечно расширить
`disk_backed_show` (не `_tasks_relative_path`, чтобы не трогать
инвариант для `ls-tree`, который зовётся только для `tasks/<id>`):
`rel` вне `tasks/` читается с `config.ROOT` (тот же диск, что песочницы
уже наполняют скилами/CLAUDE.md, `seed_developer_brief_fixtures`), не
с `config.TASKS`. Это тестовая инфраструктура, не залоченный артефакт
(`tests/sandbox.py` — общая песочница, не `tasks/<id>/acceptance_tests/`)
— тот же мандат разработчика, что и у остального п.3 «Шагов».
После правки: `python3 -m pytest tests/ -q` — 1306 passed, 0 failed
(408 subtests passed), один прежний ресурсный ворнинг sqlite3 в
`store.__del__` — не регрессия этой задачи (тот же поток/поведение до
и после мержа, не проверялось этой задачей).

`scripts/guard.py tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/PLAN.md
tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/SPEC.md
tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/TZ.md` — «GUARD: ок (3 файлов)».

Локальный прогон приёмки (`python3 -m unittest discover -s
tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/acceptance_tests -v`) — 6 из 8 зелены,
2 красные: AC-1/AC-2/AC-4/AC-6/AC-7/AC-8 подтверждают саму реализацию
этой задачи, AC-3 и AC-5 падают — см. «Эскалация» ниже: обе падают по
ОДНОЙ и той же причине вне зоны этой задачи (A7 переехала `tasks/<id>/`
self-таргета из ветки кода в артефактную ветку, залоченные фикстуры
`_sandbox.py` этого не знают).

## Риски
Расширение диапазона возможных отказов шага: раньше skills/CLAUDE.md не
могли не прочитаться иначе, чем ошибкой диска; теперь добавляется путь
отказа «git не ответил на `show`» (недостижимый `main`, разошедшийся
git-репозиторий и т.п.) — по духу тот же класс отказа, что уже несёт
`_developer_spec_text` для SPEC.md, с тем же приёмом (`sys.exit` с
именованной причиной, не тихий проглот).

## Предложения системе
(пусто)

## Эскалация

### Вопросы

**Вопрос 1 (блокирует)** — как поправить два залоченных (T023)
приёмочных теста этой задачи, чьи фикстуры устарели из-за стройки A7
(смержена в `main` этим же шагом подтяжки, см. «Влияние на систему»):
`tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/acceptance_tests/_sandbox.py::
TaskSandbox.write_and_commit_in_worktree` (использует
`TaskArtifactsStillReadFromTaskBranchTest.test_ac3_...`) и прямая
запись в `wt / f"tasks/{self.TASK}/WIP.md"` внутри
`test_ac5_no_integrity_incident_on_main_rule_change.py:58`?

Обе фикстуры пишут `tasks/<id>/*` прямо в **ветку/worktree кода**
задачи (`config.WORKTREES/<id>`, T045) — так self-таргет и работал до
A7. После A7 (`orchestrator/catalog.py::_new_external_artifact_branch`,
`orchestrator/artifact_source.py::resolve`) `tasks/<id>/` ЛЮБОГО
таргета, включая self, живёт ТОЛЬКО в артефактной ветке пульта
(`artifact/<id>`) — код читает и коммитит артефакты только туда,
ветка/worktree кода `tasks/<id>/` больше не содержит вовсе (кроме
транзитного момента между записью роли и автокоммитом оркестратора,
`checkpoint._commit_external_step_artifacts`). Отсюда два конкретных
провала:
- **AC-3** (`test_ac3_questions_and_answer_artifacts_still_read_from_
  task_branch`): `QUESTIONS.md`/`ANSWER-1.md`, закоммиченные
  `write_and_commit_in_worktree` в ветку кода, не попадают в
  `brief.analyst_map_component` — тот читает исключительно с
  артефактной ветки (`artifact_source.resolve`, `foreign=True`
  безусловно после A7).
- **AC-5** (`test_ac5_...`): `(wt / f"tasks/{self.TASK}/WIP.md").
  write_text(...)` падает `FileNotFoundError` — каталог
  `tasks/<id>/` в ветке/worktree кода теперь вообще не создаётся
  `cmd_new` (раньше создавался, отсюда родительский каталог
  существовал).

Это не дефект этой задачи и не конфликт мержа в буквальном смысле (оба
файла смержались БЕЗ маркеров конфликта — `git` не увидел текстового
пересечения) — это семантическое расхождение фикстуры с новой моделью
self-таргета A7, попадающее прямо под собственный пункт SPEC «Не
входит»: «Самостоятельное разрешение конфликта с параллельной стройкой
A7, ... если её изменения пересекаются с orchestrator/brief.py — это
эскалация Оператору». Пересечение здесь шире одного `brief.py`
(`artifact_source.py`/`checkpoint.py`/`catalog.py`), но того же класса.
ANSWER-1 прямо ограничил объём подтяжки: «Ничего сверх мержа и
разрешения конфликтов не менять» — правка залоченных `acceptance_tests/`
за эту рамку выходит.

Варианты:
- **A** — переписать обе фикстуры на коммит через
  `orchestrator/artifact_branch.py::commit_files` (или эквивалент) в
  артефактную ветку задачи вместо прямой записи в ветку/worktree кода —
  тот же приём, что уже несёт production-код после A7; правку делает
  developer после явного снятия лока Оператором на эти два файла.
- **B** — Оператор сам вносит правку (или поручает отдельной задаче
  «синхронизация локальных acceptance_tests с моделью self-таргета
  A7»), эта задача остаётся с AC-1/AC-2/AC-4/AC-6/AC-7/AC-8/AC-9
  зелёными и AC-3/AC-5 — как есть, до отдельного решения.
- **C** — другое решение Оператора.

Дефолт при молчании: не продолжать — оба теста блокируют
приёмочный гейт (`orchestrator/acceptance.py`), задача не может дойти
до `review` с зелёной приёмкой без ответа по этому пункту.

### Контекст

- Ветка подтянута из `main` (62 коммита, A7), два текстовых конфликта
  разрешены по ANSWER-1, зафиксировано в «Влияние на систему» —
  merge-коммит + коммит регенерации карты уже в истории ветки.
- `tests/` (юнит-тесты пульта) — 1306/1306 OK, 0 failed, после точечной
  правки `tests/sandbox.py::disk_backed_show` (НЕ залоченный файл, тот
  же мандат, что и остальная тестовая инфраструктура этой задачи —
  подробности в «Влияние на систему»).
- `scripts/guard.py` на PLAN.md/SPEC.md/TZ.md — «ок (3 файлов)».
- Локальная приёмка (`unittest discover -s tasks/
  01M1K7KP0D8ZKRM9KTE75DCCYR/acceptance_tests`): 6/8 зелены
  (AC-1/AC-2/AC-4/AC-6/AC-7/AC-8 — сама реализация задачи подтверждена
  «зелёный с рождения»/явными тестами), AC-3 (FAIL) и AC-5 (ERROR) —
  красные по причине выше, AC-9 — skip по замыслу (см. его докстринг).
- Реализация самой задачи (AC-1/AC-2/AC-4/AC-6/AC-8: скилы и CLAUDE.md
  читаются с головы `main`, fingerprint в журнале соответствует
  main-версии) не менялась и не откатывалась — эскалация только про
  залоченные фикстуры двух локальных приёмочных тестов.

### Блокирует

Переход `PLAN.md` из `escalate` в `ready`/сдача шага `in_dev` —
приёмочный гейт задачи требует зелёных `acceptance_tests/`
(`orchestrator/fsm_autogate.py`, ADR-0007), а AC-3/AC-5 не могут стать
зелёными без правки залоченных T023 файлов, на которую у роли
developer нет мандата без явного решения Оператора (вариант A/B/C
выше).
