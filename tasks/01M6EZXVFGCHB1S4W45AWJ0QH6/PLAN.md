---
task: 01M6EZXVFGCHB1S4W45AWJ0QH6
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab Б2.3-2: хук pre-push в клоне, его строка doctor, клон подмодулей и сверки перед отправкой

## Подход
Второй рубеж белого списка — отдельный каталог хуков пульта
`scripts/git-hooks/target-human/` (`pre-push` с правилами по файлу
политики и `pre-commit` с прежней защитой `main`), постоянный
`core.hooksPath` клона на него и `-c core.hooksPath` в каждой отправке
пульта. Прежние `scripts/git-hooks/pre-push`/`pre-commit` не тронуты.

Ключевые решения:
- Хук — POSIX sh без внешних программ, кроме `git rev-parse
  --git-common-dir`. Шаблон ветки превращается в образец `case`:
  `{id}`/`{slug}`/`{ref}` → `?*` (непустая подстрока), символы образца
  (`*?[]\`) шаблона экранируются — буквально. Проверено на `/bin/sh` и
  `/bin/bash` macOS.
- Каталог хуков проекта — одна функция `gitcmd.project_hooks_path(entry)`
  (признак — `targets.merged_by_project_people`, литералов `merge_gate` вне
  `targets.py` нет); `workspace.project_hooks_path(target)` — обёртка по
  имени проекта. `workspace.hooks_path()` прежний.
- Файл политики пишет `workspace.write_push_policy` в
  `git rev-parse --git-common-dir` клона; эталон —
  `workspace.push_policy_text` (четыре строки по записи).
- Хост записи для помощника учётных данных — переменная окружения
  `ARTEL_HOSTING_HOST` рядом с `ARTEL_HOSTING_TOKEN` (помощник читает
  `host=` запроса со stdin и сверяет); форма `credential.<url>.helper`
  отвергнута — она меняла бы число записей `GIT_CONFIG_*`, которое
  фиксирует `tests/test_hosting_token_units.py::HostingEnvTest::test_appends_after_existing_git_config_entries`.
  Хост: с портом, без учётной части; путь и `file://` — пустой
  (ANSWER-1 п. 2).
- Клон: `clone` добавлен в `HOSTING_SUBCOMMANDS`; проект `git clone`
  узнаётся по адресу в argv (каталог клона ещё не в области проекта) и
  только у записи со `token_slot` — у записей без слота и у артели
  авторизация прежняя (и в процессе роли отказа нет, как прежде).
  Подмодули — `git submodule update --init --recursive` через
  `gitcmd.in_repo` (хостинговый вызов проекта), только у внешних
  проектов со `token_slot` и при наличии `.gitmodules` (ANSWER-1 п. 3);
  сбой — каталог клона убирается, причина названа.
- Сверки `_whitelist_refusal` (требование 12) дополнены
  `GIT_SSH_COMMAND`/`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` и
  `_config_redirect_refusal`: `remote.origin.url` = `url` записи
  (`url_key`), `url.*.insteadOf`/`pushInsteadOf`/`core.sshCommand` в
  действующей конфигурации (все слои, включая `config.worktree` и
  глобальный — ANSWER-1 п. 4), `core.hooksPath` задан и не абсолютный
  каталог хуков пульта проекта.
- Строка `clone-push-hook` — в `check_clone_hooks` для клонов проектов
  `target-human` (они исключены из `clone-hooks`, та осталась `warn` для
  прочих). Эталон хуков — `git show HEAD:<путь>` главной копии; `config.ROOT`
  не репозиторий или файла в `HEAD` нет — `skip` (ANSWER-1 п. 5).
  `core.hooksPath` рабочих копий — из `config.worktree` каждой рабочей
  копии `git worktree list`.
- Стенды MR-тестов приведены к согласованию по ANSWER-1 п. 1: адрес
  записи стенда = путь bare-`origin` клона; утверждения не менялись.

Оценка SPEC ($40) не пересматривается.

## Шаги
1. `scripts/git-hooks/target-human/pre-push`, `pre-commit` (исполняемые).
2. `orchestrator/gitcmd.py`: `url_host`, помощник со сверкой `host`,
   `hosting_env(..., host)`, `clone` и `submodule update` — хостинговые
   вызовы (`_clone_project`), `project_hooks_path`, `same_dir`, новые
   сверки окружения и конфигурации, `-c core.hooksPath` в `_push_plan`.
3. `orchestrator/workspace.py`: `project_hooks_path`, `is_target_human`,
   `set_clone_hooks(clone, target)`, `push_policy_text`/`push_policy_path`/
   `write_push_policy`, `_clone_submodules`; `ensure_clone` ставит
   каталог проекта, пишет политику, клонирует подмодули.
4. `orchestrator/doctor/git_hooks.py`: строка `clone-push-hook`
   (`_check_push_hook_clones`) и починка `_fix_push_hook_clone` из
   `_fix_project_clones`.
5. Стенды `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py` и
   `tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py`: `url:` записи —
   путь `config.PROJECTS/<имя>/origin.git` (шаблон `ENTRY` и его
   `format`), утверждения те же.
6. Юнит-тесты `tests/test_push_hook_units.py`; карта
   `python3 scripts/codebase_map.py`.
7. (Итерация 2, REVIEW R1-F1.) Долгоживущие сторожа в `tests/`:
   `tests/test_push_hook_stand.py` — стенд `real_git` (каталог
   `scripts/git-hooks` закоммичен в `config.ROOT`, клоны — `ensure_clone`,
   шпион отправки): `-c core.hooksPath` в отправке `target-human` и её
   отсутствие у `operator`; строка `clone-push-hook` (изменённый хук, хук
   без бита исполнения, изменённый/удалённый файл политики, чужой/прежний/
   снятый `core.hooksPath`, `config.worktree`, `--fix` → `ok`, `skip` без
   хука в `HEAD`, нет строки без клонов, исключение из `clone-hooks`);
   сверки `GIT_SSH_COMMAND`/`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM`,
   `remote.origin.url`, `insteadOf`, `core.sshCommand`; `ensure_clone` и
   `pre-commit` `target-human`; клон и подмодули с токеном слота, без
   слота — без токена. В `tests/test_push_hook_units.py` — отказ хука на
   теги/`refs/notes` при исправной политике и при отсутствующем или
   нечитаемом файле политики.

8. (Итерация 3, возврат из merge_gate.) `orchestrator/gitcmd.py`:
   - `remote.origin.url` читается `--get-all` по всем слоям; отказ, если
     значений не ровно одно или оно не адрес записи (`git push origin`
     шлёт на каждое значение);
   - `_strict_config`: код `git config` 1 — «ключа нет», иной сбой или
     `OSError` — `_ConfigUnread`, отказ «конфигурация клона не прочитана».
     Так читаются все сверки конфигурации `_whitelist_refusal`
     (`pushurl`/`push`/`mirror`, `push.pushOption`, `remote.origin.url`,
     `insteadOf`/`sshCommand`, `core.hooksPath`) и псевдоним клона под
     белым списком. `_raw_config` остаётся только у `_destination_project`
     (адрес `origin` артели) — вне белого списка;
   - `GIT_SSH` добавлен в `GIT_TRANSPORT_ENV_NAMES` — отказ, как у
     `GIT_SSH_COMMAND`;
   - `_push_policy_refusal` (после сверок белого списка, только
     `target-human`): пульт перезаписывает файл политики эталоном по
     записи, читает его обратно и сверяет. Не записан или не читается
     (нет прав, на месте файла каталог, общий каталог git не получен) —
     отказ до git с путём файла. Эталон и путь (`push_policy_text`,
     `push_policy_path`, `PUSH_POLICY_NAME`) перенесены в `gitcmd`,
     `workspace` их делегирует.

   Толкование «отсутствия» файла. Пульт пишет эталон перед каждой
   отправкой, поэтому отсутствующий файл создаётся, и отправка идёт. Отказ
   дают случаи, когда файл после записи не получить. Строгое чтение
   («файла нет — отказ до записи») проверено и отвергнуто: оно краснит
   десятки тестов, которые SPEC требует оставить зелёными без правки.
   Их стенды заводят клоны `target-human` без `ensure_clone`:
   `tests/test_gitcmd_push_point.py`, MR-стенды
   `test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery`/`test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync`
   («push артефактной ветки FAILED … artel-push-policy нет»). Кроме того,
   так отказ «нет файла» снимал бы и решение «перезапись перед каждой
   отправкой».

   Тесты (`tests/test_push_hook_stand.py`, 10 новых): `GIT_SSH`; второе
   значение `remote.origin.url` в локальном слое и в `~/.gitconfig`; сбой
   `git config` на `--get-regexp`/`core.hooksPath`/`remote.origin.pushurl`;
   изменённый и удалённый файл политики после отправки равен эталону;
   нечитаемый файл и каталог на месте файла дают отказ до git с путём.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 3, 4, 7 |
| 2 | 1, 7 |
| 3 | 1, 7 |
| 4 | 1, 7, 8 |
| 5 | 1, 2 |
| 6 | 2, 7 |
| 7 | 1 (прежние файлы не тронуты) |
| 8 | 4, 7 |
| 9 | 4, 7 |
| 10 | 2, 3, 7 |
| 11 | 2 |
| 12 | 2, 5, 7, 8 |
| 13 | 2, 3, 4 (только `targets.merged_by_project_people`/`push_whitelisted`) |
| 14 | 2, 3, 4 |

Проверка: `plank-run` — 68 passed. Затронутые модули: `test_gitcmd_push_point`,
`test_git_hooks`, `test_hosting_token_units`, `test_01m42pencs26d0656x8fr7dfa7_project_area`,
`test_01m545edths47hsb59akc1ez9c_project_token`, MR-стенды (83 passed после
шага 5; до него 69 красных — именно сверка `remote.origin.url`), ещё 30
файлов вокруг клонов/`target-human`/doctor (329 passed), `test_invariants` и
`test_doctor*` (253 passed). Новые тесты проверены временной мутацией —
каждый из 11 случаев красный.
Итерация 2: `tests/test_push_hook_stand.py` + `tests/test_push_hook_units.py`
— 32 passed; вместе с `test_git_hooks`, `test_hosting_token_units`,
`test_gitcmd_push_point` — 98 passed; `test_invariants` — 88 passed;
`plank-run` — 68 passed. 20 временных мутаций (вставка `-c` в
`_push_plan`, перечень переменных окружения, сверка `remote.origin.url`,
`PUSH_REDIRECT_CONFIG`, разбор `clone`, `_clone_submodules`, запись
политики и каталог хуков в `ensure_clone`, сумма/бит/политика/
`core.hooksPath`/`config.worktree` в строке doctor, исключение из
`clone-hooks`, `skip`, бит в `--fix`, правило ссылок и отсутствие файла
политики в `pre-push`, `pre-commit`) — все красные, код возвращён. Мутация
«`clone` убран из `HOSTING_SUBCOMMANDS`» выжила законно: `clone`
разбирается раньше этой проверки (`gitcmd.py:131-132`), её сторожит
мутация самого разбора.
Итерация 3: `tests/test_push_hook_stand.py` — 30 passed. Вместе с
`test_push_hook_units`, `test_gitcmd_push_point`, `test_git_hooks`,
`test_hosting_token_units`, `test_fail_closed_on_read_failure` и
`test_invariants` — 216 passed. MR-стенды, awaiting-, project_area,
multitarget, ac9, gitlab_doctor_lines, coldstart вместе с файлами выше —
378 passed. `plank-run` — 68 passed. Четыре временные мутации, по одной на
пункт возврата: `--get` вместо `--get-all`, сбой `git config` → пусто, без
`GIT_SSH`, без перезаписи политики. Все 10 новых тестов красные, код
возвращён.

## Влияние на систему
- Защита `main` главной копии и клонов прочих проектов — прежние файлы и
  поведение (AC-6 зелёный, `tests/test_git_hooks.py` зелёный).
- Существующие клоны `target-human` (до этой задачи) без файла политики:
  их отправки хук отказывает до `doctor --fix` (требование 4 — так и
  задумано); `doctor` покажет `clone-push-hook` `fail`. Открытие
  `gitlab`/`target-human` — часть 4 деления, живых клонов таких проектов
  сейчас нет.
- Сверки только добавлены, ни одна прежняя не ослаблена; отправки
  `operator` и артели не меняются (нет `-c core.hooksPath`, сверки белого
  списка их не касаются).
- `hosting_env` получил необязательный `host` (по умолчанию пустой —
  пароль только запросу без хоста, строже прежнего); единственный
  вызывающий — `gitcmd.git`.
- Правка двух чужих долгоживущих тестов — только адрес записи стенда
  (ANSWER-1 п. 1), утверждения не тронуты. Если рубеж неослабления
  отметит их, перечень мест: шаблон `ENTRY` (строка `url:`) и вызовы
  `ENTRY.format(...)` в `Stand.record` обоих файлов и в
  функции `write` внутри
  `tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py::test_ac17_bad_interval_refuses_record_naming_field` — мандат
  по ANSWER-1 п. 1.
- Откат — revert merge-коммита задачи.

## Риски
- Сверка действующей конфигурации читает и `~/.gitconfig` Оператора
  (ANSWER-1 п. 4): `url.*.insteadOf` в глобальном слое машины откажет
  отправкам проектов под белым списком — намеренно.
- Помощник учётных данных сравнивает `host` побайтно (регистр важен).
- Итерация 3: второе значение `remote.origin.url` в `~/.gitconfig`
  Оператора (`[remote "origin"]` в глобальном слое) откажет всем отправкам
  `target-human` — намеренно (решение при возврате).
- Отправка пульта пишет файл в `.git` клона (побочный эффект единой точки
  отправки). Подмену политики между отправками по-прежнему ловит строка
  `doctor`.

## Предложения системе
- Нет команды пульта для прогона одного хука с заданным stdin — тесты хука
  пишут свою обвязку (`tests/test_push_hook_units.py`); класс «хук git
  проверяется настоящим push» дорог.
- `scripts/guard.py::network_address_errors_from_files` (инвариант 35)
  принимает учётную часть адреса за хост: `https://u:p@localhost/…`
  отказывается как внешний адрес. В `tests/test_push_hook_units.py` такой
  адрес собран из частей (хост — `127.0.0.1`), с комментарием.
