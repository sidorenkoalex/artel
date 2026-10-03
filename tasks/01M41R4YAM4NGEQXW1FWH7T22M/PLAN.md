---
task: 01M41R4YAM4NGEQXW1FWH7T22M
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Штатный локальный прогон планки в шаге роли; шаг роли не удаляет отслеживаемые файлы вне своих путей

## Подход

**Требования 1–2: команда `plank-run <id> [файл]`** — новый модуль
`orchestrator/plank_run.py::cmd_plank_run`, запись в таблице диспетчера
`orchestrator/artel.py::main` и в белом списке роли `_ROLE_ALLOWED_COMMANDS`.

- Рабочая копия кода — тот же выбор, что у прогона пульта
  (`advance_gates/acceptance._acceptance_run_body`): `workspace.path(id)` для
  артели, `.artel/projects/<target>/workspace` для внешнего target. Нет
  каталога (или он совпал с `config.ROOT`) — именованный отказ: в главной
  копии `drop_from_code_copy` ничего не убирает.
- Источник: `tests_writing` — файлы `acceptance_tests/` каталога документов
  (`artifact_branch.docs_dir`), без `__pycache__`/`.pyc`; прочие состояния —
  `artifact_branch.ls_tree` по `refs/artifacts/<id>` (диск каталога документов
  не читается). Нет ни одного `test_*.py` в источнике (в т.ч. нет ссылки
  вовсе) — отказ «планки нет» без выкладки и pytest.
- Выкладка/уборка — общий узел пульта `acceptance.plank_in_code_copy`: ему
  добавлен необязательный параметр `files` (явный набор — черновик) через
  новую `acceptance.materialize_files`; запись файлов вынесена из
  `materialize_from_branch` в общий `_write_plank` без изменения поведения.
  Уборка — прежний `drop_from_code_copy` в `finally`: только `tasks/<id>/`.
- Прогон — новая `acceptance.run_plank(targets, cwd)`: `_pytest_command`,
  `_pytest_env`, `timeout=config.ACCEPTANCE_TIMEOUT_SEC`, как у `run()`, но
  отдаёт код выхода pytest и весь вывод (у `run()` гейта — bool и хвост 2000
  символов). Печать: строка источника, вывод pytest, строка «итог pytest: …;
  код выхода pytest: N»; ненулевой код выхода pytest — код выхода команды.
  Таймаут — ненулевой выход с текстом «превысил Nс».
- `[файл]`: имя файла планки, допускаются префикс
  `tasks/<id>/acceptance_tests/` и узел pytest `::тест`; файла нет в
  источнике — отказ до выкладки.
- Защита от потери документов: если в `tasks/<id>/` рабочей копии лежат файлы
  вне `acceptance_tests/` (документ, записанный туда по ошибке; пульт заберёт
  его в ссылку после шага), команда отказывает, не трогая их — иначе уборка
  выкладки снесла бы их.
- Состояние пульта не меняется: ни `store.journal`, ни `update_task`, ни
  `record_fixation`, ни lease; запись журнала о прогоне не делается (SPEC
  «Не входит»).

**Требование 3: правила ролей.**
- `orchestrator/role_prompt.py::docs_dir_note` — вместо `copytree` называет
  `python3 <config.ROOT>/orchestrator/artel.py plank-run <id> [файл]` как
  единственный способ и прямо запрещает ручное копирование и удаление
  каталогов рабочего каталога с причиной (03.10.2026).
- Пункт 5 миссии test_author велел `python3 -m pytest
  tasks/<id>/acceptance_tests …` — в рабочем каталоге планки нет, и пункт
  противоречил бы абзацу выше. Переписан: «прогони командой `plank-run` …
  она выполнит `python3 -m pytest tasks/<id>/acceptance_tests -p
  no:cacheprovider -p timeout -o timeout=N`». Подстрока, которую сторожит
  `tests/test_role_prompt_test_author_mission.py`, сохранена дословно — тест
  не правился.
- `skills/test-authoring.md`, `skills/review-checklist.md`,
  `skills/coding-standards.md` — защищённые пути, диф в «Приложение» ниже.

**Требование 4: восстановление удалённых файлов** —
`checkpoint.restore_out_of_bounds_deletions(conn, id, role, wt)`:
`git status --porcelain=v1 -z --untracked-files=no` → удалённые пути HEAD
(`D` в любой колонке кроме `AD`, источник переименования) → вне разрешённых
путей роли (`_role_may_delete`: свой `tasks/<id>/` — всем; developer —
`_zone_paths` = зоны + расширение + `config.COMMON_ZONES` + `tasks/<id>/`, у
задачи без заявленных зон фильтра нет, как у `_stray_staged_paths`;
test_author — ещё свои долгоживущие файлы, их судьбу решает
`_test_author_checkpoint`) → `git --literal-pathspecs checkout HEAD -- …`
пачками по 200 путей → ОДНА запись журнала
`RESTORED_DELETIONS_ACTION` («удалённые вне путей роли файлы
восстановлены») с числом восстановленных и первыми пятью путями (одно
действие для всех ролей).

Точки вызова:
- test_author/reviewer/прочие — `_wip_checkpoint` (таймаут, аварийное
  завершение, `pause --now`) и `commit_success_checkpoint` (штатный путь) —
  ДО существующего отката вне мандата, поэтому откат удалённого уже не видит
  и запись восстановления одна.
- developer — ПОСЛЕ `_commit_worktree_change`, только когда тот вернул
  непустой `stray`: удаление вне зон после `add -A` всегда попадает в
  `stray`, снимается со стейджа и в коммит пульта не идёт (прежнее
  поведение), затем восстанавливается из HEAD. Почему не до коммита:
  `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`
  сверяет точный список вызовов git шага developer на чистом дереве, и
  безусловный `git status` до коммита менял бы его утверждение (правка
  утверждения существующего теста — эскалация). Привязка к `stray` даёт тот
  же результат без лишнего вызова git на чистом шаге.
- Удаления внутри зон developer не трогаются и коммитятся, как раньше.

## Шаги

1. `orchestrator/acceptance.py`: `_write_plank`, `materialize_files`,
   параметр `files` у `plank_in_code_copy`, `run_plank`.
2. `orchestrator/plank_run.py` (новый) + `orchestrator/artel.py`: таблица
   диспетчера, `_ROLE_ALLOWED_COMMANDS`, импорт, справка модулей.
3. `orchestrator/checkpoint.py`: `RESTORED_DELETIONS_ACTION`,
   `_deleted_tracked_paths`, `_role_may_delete`,
   `restore_out_of_bounds_deletions`; вызовы в `_wip_checkpoint` и
   `commit_success_checkpoint`.
4. `orchestrator/role_prompt.py`: `docs_dir_note`, пункт 5 миссии
   test_author.
5. `tests/test_plank_run_edges.py` — углы, не покрытые долгоживущими файлами
   задачи; карта `docs/codebase-map.md` регенерирована.
6. Приложение — диф к трём файлам `skills/` (ниже), проверен
   `git apply --check`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (выкладка узлом пульта, раннер/таймаут, итог и код выхода, уборка `tasks/<id>/`, источник по состоянию, `[файл]`) | 1, 2 |
| 2 (доступна роли, не меняет БД/журнал/ссылки; «планки нет») | 2 |
| 3 (правила ролей: skills — приложение; миссия `docs_dir_note`) | 4, 6 |
| 4 (восстановление удалений вне путей роли + запись журнала) | 3 |
| 5 (тесты с «Ловит мутацию») | долгоживущие файлы задачи + 5 |

AC-1…AC-7 и часть AC-8 о миссии — `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`,
`tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py` (оба зелёные, 8
тестов, 26 подтестов); AC-8 (приложение) и AC-9 —
`acceptance_tests/test_ac8_ac9_rules_and_tests.py`: AC-9 зелёный; AC-8
читает PLAN.md из ссылки документов, поэтому зелёным станет после автокоммита
этого PLAN.md — локально проверен подменой `gitcmd.show` на файл с диска
(см. «Проверено»).

### Проверено
- `python3 -m pytest tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py
  tests/test_01m41r4yam4ngeqxw1fwh7t22m_restore_deleted.py` — 8 passed.
- `tests/test_plank_run_edges.py` — 6 passed; каждая заявка «Ловит мутацию»
  проверена временной мутацией кода (7 мутаций — все 7 красные).
- Затронутые модули (передний план, `-p no:cacheprovider -p timeout -o
  timeout=120`): test_01m3xtf5506gf43hd51ece230t_role_refusal,
  test_artel_role_restricted_commands, test_role_prompt_test_author_mission,
  test_acceptance, test_acceptance_collect, test_acceptance_pycache,
  test_timeout_checkpoint, test_step_autocommit, test_checkpoint_zone_filter,
  test_checkpoint_external_step_artifacts, test_checkpoint_stray_acceptance_files,
  test_role_commit_by_pult, test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit,
  test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions,
  test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir, test_docs_dir_layout,
  test_pause_now, test_long_lived_step_end_to_end,
  test_test_author_long_lived_artifact, test_agent_prompt,
  test_branch_freshness_gate, test_long_lived_manifest, test_review_package,
  test_agent_failure, test_step_cost, test_analyst_role, test_multitarget,
  test_agent_log, test_runner_role_model,
  test_01m3y8570h9y57ytp3m7e1amhg_required_artifact,
  test_acceptance_tests_flow, test_auto_cycle — все зелёные.
- `git apply --check` приложения на чистом дереве — применяется (три файла).

## Влияние на систему

- Белый список команд роли расширен одной командой. Она пишет только
  временную выкладку `tasks/<id>/` рабочей копии кода и убирает её в
  `finally`; БД, журнал, ссылки, ветка, lease не трогаются (AC-4 сторожит).
  Отказ `_refuse_if_worktree` не ослаблен: роль зовёт `artel.py` главной
  копии (полный путь в миссии).
- `plank_in_code_copy`/`materialize_from_branch`: поведение прежнее (запись
  вынесена в `_write_plank` дословно); `run()`/`collect()` гейтов не
  тронуты — `run_plank` отдельная функция на том же раннере.
- Чекпоинты: для test_author/reviewer восстановление удалений делает то же,
  что откат вне мандата делал на аварийных путях, плюс штатный путь
  reviewer/analyst теперь восстанавливает удалённые вне `tasks/<id>/` файлы
  (до задачи не делал ничего). Правки и новые файлы роли на штатном пути не
  откатываются — только удаления. Для developer коммит пульта не меняется:
  удаление вне зон и раньше снималось со стейджа, теперь ещё и
  возвращается на диск. Гейт зон, гейт сохранности тестов, фильтр зон
  чекпоинта не тронуты.
- Ни один тест не ослаблен и не изменён; долгоживущие файлы задачи и планка
  не правились.
- Откат: revert merge-коммита задачи; приложение к `skills/` откатывается
  отдельно (`git apply -R`).

## Риски

- Переименование вне зон, назначение которого в зоне (`git mv
  tasks/H/x pkg/x`) у developer: `diff --cached --name-only` с детектором
  переименований называет только назначение — источник в `stray` не
  попадает и удаление уходит в коммит, как и до задачи. Массового удаления
  (случаи 03.10) это не касается.
- Задача без заявленных зон (старые SPEC) — у developer фильтра нет, удаления
  не восстанавливаются (тот же довод, что у `_stray_staged_paths`).
- `plank-run` и пульт не гоняют планку одновременно в одной рабочей копии:
  гейты пульта бегут между шагами роли, `plank-run` — внутри шага.
- Долгоживущие файлы `tests/` `plank-run` не гоняет (они в рабочей копии,
  `pytest tests/<файл>.py` напрямую) — так и записано в правилах.

## Приложение: правила ролей (skills/, защищённый путь)

Проверка: `git apply --check -v <файл>` на чистом дереве ветки задачи —
`Checking patch skills/coding-standards.md... skills/review-checklist.md...
skills/test-authoring.md...` без ошибок.

```diff
diff --git a/skills/coding-standards.md b/skills/coding-standards.md
index 3ad43c3a..cb52b893 100644
--- a/skills/coding-standards.md
+++ b/skills/coding-standards.md
@@ -114,6 +114,16 @@ PLAN вправе один раз, при первой сдаче, поднят
   планку), каждый вызов в переднем плане с таймаутом.
   Решение Оператора 05.09: восемь таймаутов шагов за сутки на ожидании
   полного набора.
+- Планку задачи гоняй только командой пульта `artel.py plank-run <id>
+  [файл]` (полный путь к `artel.py` пульта называет миссия шага): она
+  выкладывает зафиксированную планку в `tasks/<id>/acceptance_tests/`
+  рабочего каталога, гоняет её раннером и таймаутом пульта, печатает
+  итог и код выхода pytest и убирает выкладку — только `tasks/<id>/`.
+  Это единственный способ локального прогона планки: не копируй планку
+  в рабочий каталог руками и не удаляй каталоги рабочего каталога для
+  уборки — 03.10.2026 такая уборка (`shutil.rmtree("tasks")`) пять раз
+  удалила весь отслеживаемый каталог задач рабочей копии, а
+  незакоммиченное developer пульт коммитит за роль.
 
 ## Задача класса «рефакторинг» (правила T015)
 Класс задан словом «рефакторинг» в ТЗ/SPEC. Тогда:
diff --git a/skills/review-checklist.md b/skills/review-checklist.md
index cf9957bc..ef75baf2 100644
--- a/skills/review-checklist.md
+++ b/skills/review-checklist.md
@@ -216,6 +216,16 @@ HEAD», но этот sha — не всегда надёжный ориенти
 успеваешь полный набор — прогоняй по модулям и перечисли их в
 «Проверено исполнением».
 
+Планку задачи гоняй только командой пульта `artel.py plank-run <id>
+[файл]` (полный путь к `artel.py` пульта называет миссия шага): она
+выкладывает зафиксированную планку в рабочий каталог, гоняет её
+раннером и таймаутом пульта, печатает итог и код выхода pytest и
+убирает выкладку — только `tasks/<id>/`. Это единственный способ
+локального прогона планки: не копируй планку в рабочий каталог руками и
+не удаляй каталоги рабочего каталога для уборки — 03.10.2026 такая
+уборка (`shutil.rmtree("tasks")`) пять раз удалила весь отслеживаемый
+каталог задач рабочей копии.
+
 Полный набор `tests/` в шаге ревью не запускай: его гоняет CI на каждый
 пуш ветки, и его зелёный статус — условие гейтов verifying и merge. В
 шаге — планка задачи и тесты затронутых модулей; сверку «набор не
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index 69f91375..1216820d 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -345,9 +345,19 @@ T062, когда Оператор поднял потолок до 5 — main п
 её полей) — там расхождение с живым файлом и есть проверяемое свойство.
 
 ## Перед завершением
-`python3 -m pytest tasks/<id>/acceptance_tests -p no:cacheprovider -p
-timeout -o timeout=120` — тот же раннер и таймаут, которыми пульт
-принимает планку (`orchestrator/acceptance.py::_pytest_command`); все
+Прогон планки — только командой пульта `artel.py plank-run <id> [файл]`
+(полный путь к `artel.py` пульта называет миссия шага): в `tests_writing`
+она выкладывает твой черновик из каталога документов в
+`tasks/<id>/acceptance_tests/` рабочего каталога, гоняет его тем же
+раннером и таймаутом, которыми пульт принимает планку
+(`orchestrator/acceptance.py::_pytest_command`), печатает итог и код
+выхода pytest и убирает выкладку — только `tasks/<id>/`. Это единственный
+способ локального прогона планки: не копируй планку в рабочий каталог
+руками и не удаляй каталоги рабочего каталога для уборки — 03.10.2026
+такая уборка (`shutil.rmtree("tasks")`) пять раз удалила весь
+отслеживаемый каталог задач рабочей копии. Долгоживущие файлы `tests/`
+гоняй `python3 -m pytest tests/<файл>.py -p no:cacheprovider -p timeout
+-o timeout=120` из рабочего каталога. Все
 написанные тесты обязаны быть синтаксически рабочими (падать на
 отсутствующей пока реализации — нормально, падать на опечатке в самом
 тесте — нет), краснота каждого файла объяснена маркером (см. выше).
```

## Предложения системе

- `conftest.py` (сторож роли) пропускает pytest только по пути
  `tasks/<id>/acceptance_tests/…` рабочего каталога, а планка там с ADR-0021
  не лежит — поэтому роли и копировали её руками. После мержа `plank-run`
  это снимается, но сторож стоит проверить на путь каталога документов.
- Миссия этого же шага (до мержа задачи) велела `copytree` планки в рабочий
  каталог; прогон этой задачи сделан так же, уборка — только
  `tasks/01M41R4YAM4NGEQXW1FWH7T22M/`.
- `tests/test_review_package.py::test_developer_step_has_no_package` сверяет
  точный список git-вызовов шага developer: любая новая проверка чекпоинта
  упирается в правку утверждения этого теста. Сверка подмножества (нет
  `show` diff/stat) сторожила бы то же свойство без хрупкости.
