---
task: 01M5WDB7F14SQ30QVWJY2XYBG2
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab Б1.1 — поля записи, ветка по шаблону, единая точка отправки с журналом и белым списком

## Подход
Три слоя, каждый в своём модуле зоны:

- **Поля записи** (`orchestrator/targets.py`): новые поля объявлены только в
  `LOCAL_FIELDS` (`policy`: `branch_template`, `ref_pattern`, `freshness`,
  `squash_before_mr`, `commit_template`, `co_author`, `push_options`,
  `push_options_forbidden`, `ci_required_jobs`, `mr_assignee`, `draft_mr`,
  `max_in_flight`; `machine`: `commit_author`). Проверка — `_check_delivery`
  в `merge_local`, отказ `TargetsError` называет `policy.<поле>`/
  `machine.<поле>`. `_flatten` переносит поле в плоскую запись только если оно
  задано — у записи без полей плоская запись прежняя. Норма опции отправки —
  одна функция `push_option_error` (загрузка и `-o` в argv); предикат белого
  списка — `push_whitelisted` («`merge_gate` не `operator`», ANSWER-1 п. 1),
  литерал только в `targets.py`.
- **Ветка задачи** (`orchestrator/catalog.py`, `orchestrator/fsm.py`):
  `branch_template`/`branch_name` строят имя (`{id}` в нижнем регистре,
  `{slug}`, `{ref}`); `_branch_ref_key` — ровно одна ссылка системы
  `ref_required` и полное совпадение с `ref_pattern` (сразу за `_new_refs`);
  `branch_refusal` — занятость в БД (задачи проекта в любом состоянии) и на
  сервере (`gitcmd.in_repo(<клон>, "ls-remote", "--heads", "origin", …)`,
  сбой — «имя ветки не проверено»). В `cmd_new` проверка стоит после id и до
  `_new_task_row` (которому теперь передаётся `branch`); при шаблоне по
  умолчанию сети нет. Деление: `_division_check` последним шагом зовёт
  `catalog.division_branches` — `{ref}` — отказ «ветка по ключу трекера…»;
  id частей выдаются заранее, имена проверяются (близнецы, БД, сервер), и
  `_spawn_division_subtasks` передаёт `task_id`/`branch` в `spawn_subtask`.
  Отказ — до записей гейта и до эпика `--as-epic`.
- **Единая точка отправки** (`orchestrator/gitcmd.py`): `_push_plan` —
  одна функция решения, через которую проходят `git`, `carpentry`, `read`,
  `read_env`, `read_stream` (у всех — параметр `task_id`; `in_repo`
  передаёт его в `git` только заданным, заглушки тестов его не знают).
  Подкоманда ищется после глобальных опций; встроенные подкоманды кроме
  `push`/`send-pack` проходят без работы. Проект — по `-C`/рабочему каталогу
  под областью проектов, по пути назначения или по `url` записи; клон артели
  исключён `_project_of_path`. Нечитаемый `targets.yaml` или нет записи
  внешнего проекта — отказ (г). Под белым списком — `_whitelist_refusal`
  (глобальные опции кроме `-C`, `GIT_CONFIG_*` в окружении, флаги, `-o`,
  назначение, refspec, удаления, аренда против последней записи «ветка
  отправлена», `remote.origin.pushurl|push|mirror` и `push.pushOption`
  клона), к разрешённой отправке добавляется `-c push.followTags=false -c
  push.pushOption=`; псевдоним клона — отказ. Для всех проектов: `-o` из
  `policy.push_options` к отправке ветки задачи (не к `refs/artifacts/*`),
  после кода 0 — запись «ветка отправлена» `<sha> <ветка>` (кроме
  `--delete`/`:<ref>`/`--dry-run`). Отказ пишется в журнал задачи отправки,
  иначе задачи контекста (`task_id`, `ARTEL_TASK`), иначе алерт `incident`
  `branch_push_whitelist`.

## Шаги
1. `targets.py`: поля, `_check_delivery`, `push_option_error`,
   `push_whitelisted`, перенос в `_flatten`.
2. `catalog.py` + `fsm.py`: ветка по шаблону в `new` и делении, проверки до
   `_new_task_row`/записей гейта.
3. `gitcmd.py`: `_push_plan` во всех пяти точках, журнал и белый список.
4. Тест `tests/test_gitcmd_push_point.py` (долгоживущий минимум точки
   отправки: планка задачи разовая), карта кодовой базы.
5. Возврат из verifying (CI 40365146908), два сторожа:
   - литерал окончательных состояний в `gitcmd.py` убран: «своя ветка»
     сверяется с `fsm.TERMINAL_STATES` через `gitcmd._dead_states()`
     (импорт `fsm` отложен — `fsm` сам импортирует `gitcmd`);
   - SQL вне хранилища (мандат ANSWER-2 на `orchestrator/store.py`):
     запрос занятости имени ветки из `catalog.branch_refusal` перенесён
     дословно в новую `store.project_branch_tasks`; тот же класс в
     `gitcmd.py` закрыт существующими функциями хранилища —
     `_project_tasks` -> `store.project_tasks`, `_last_sent_sha` ->
     `store.last_task_step_of`. Сторожа и их тесты не менялись.
   Прогон: сторож литерала, `test_multitarget.py`, долгоживущие файлы
   задачи, `test_gitcmd_push_point.py`, А0 — 115 passed; планка — 75
   passed; соседние `catalog`/`gitcmd`/`store`/`artifact_branch`/деление —
   160 passed.

## Расширение зон
Пути: orchestrator/store.py

Обоснование: причина возврата из verifying (CI 40365146908) — сторож
`tests/test_multitarget.py::SqlOnlyInStoreTest` требует SQL только в модуле
хранилища; запрос занятости имени ветки из `catalog.branch_refusal`
перенесён в новую `store.project_branch_tasks`. Мандат Оператора —
ANSWER-2.md («Расширение зон разрешено: orchestrator/store.py»), матрица
неослабления там же.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 (а), (б) | 3, 4, 5 |
| 3 (в), (г) | 1 (предикат, норма опции), 3, 4 |

Проверено: долгоживущие файлы задачи — 44 passed
(`tests/test_01m5wdb7f14sq30qvwjy2xybg2_*.py`); планка `plank-run` — 75
passed; `tests/test_gitcmd_push_point.py` — 3 passed, красный на мутациях
«`push_whitelisted` всегда False» и «`-o` и к `refs/artifacts/*`». Соседние
модули: `new`/деление/`targets`/внешние ссылки/А0 — 252 passed; отправки,
`merge_gate`, уборка, ссылки документов, токен хостинга, draft MR — 460
passed; А0 и точки чтения git — 86 passed.

## Влияние на систему
- Все запуски git пульта теперь проходят `_push_plan`. Быстрый путь: argv
  без подкоманды-отправки и со встроенной подкомандой возвращается сразу,
  без чтения `targets.yaml` и БД. Отправка читает `targets.yaml` и БД
  (задачи проекта), запись «ветка отправлена» — `store.journal`; ошибки
  sqlite при записи глотаются — отправка уже прошла, запись её не условие.
- Артель и проекты `operator`: кроме (а) и (б) отправки прежние — ни
  проверок argv, ни чтения конфигурации клона, ни `-c push.pushOption=`.
  Новая запись журнала «ветка отправлена» появляется у задач артели после
  отправки их ветки.
- Нечитаемый `targets.yaml` теперь отказывает отправку из клона внешнего
  проекта (требование 3 (г)) — у таких проектов и раньше хостинговая
  операция без записи шла без токена.
- `fsm._division_check` возвращает четвёрку (добавлены части с id и
  веткой); единственный вызывающий — `_approve_spec_gate`. `spawn_subtask`
  и `_new_task_row` получили необязательные `task_id`/`branch` — прежние
  вызовы не меняются.
- Гейты, лимиты, guard и существующие тесты не ослабляются и не
  правятся. Откат — revert merge-коммита задачи.

## Риски
- `doctor` 5.2 (пробный `push --dry-run`) для записи не `operator` будет
  отказан белым списком — вынесено в Б2 SPEC «Не входит».
- Команды вне зон (`github_adapter.py`, `artifact_branch.py`, `snapshot.py`,
  `cleanup.py`, `fsm_merge_gate.py`) `task_id` не передают — их отказы без
  `ARTEL_TASK` уходят в алерт (SPEC «Не входит», Б2).
- Окно гонки между проверкой имён частей и заведением частей — принято
  Оператором (SPEC «Не входит»).

## Предложения системе
- `tests/` долгоживущим файлам задачи закрыт импорт `orchestrator.gitcmd`
  (`scripts/guard.py::_GIT_MODULES`), поэтому свойства самой точки
  отправки держатся разовой планкой; долгоживущий минимум пришлось дописать
  разработчику отдельным файлом. Правилу не хватает исключения для задач,
  чей предмет — сам `gitcmd`.
