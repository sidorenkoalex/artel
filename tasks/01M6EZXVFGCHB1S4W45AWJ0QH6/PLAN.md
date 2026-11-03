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

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 3, 4 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1, 2 |
| 6 | 2 |
| 7 | 1 (прежние файлы не тронуты) |
| 8 | 4 |
| 9 | 4 |
| 10 | 2, 3 |
| 11 | 2 |
| 12 | 2, 5 |
| 13 | 2, 3, 4 (только `targets.merged_by_project_people`/`push_whitelisted`) |
| 14 | 2, 3, 4 |

Проверка: `plank-run` — 68 passed. Затронутые модули: `test_gitcmd_push_point`,
`test_git_hooks`, `test_hosting_token_units`, `test_01m42pencs26d0656x8fr7dfa7_project_area`,
`test_01m545edths47hsb59akc1ez9c_project_token`, MR-стенды (83 passed после
шага 5; до него 69 красных — именно сверка `remote.origin.url`), ещё 30
файлов вокруг клонов/`target-human`/doctor (329 passed), `test_invariants` и
`test_doctor*` (253 passed). Новые тесты проверены временной мутацией —
каждый из 11 случаев красный.

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

## Предложения системе
- Нет команды пульта для прогона одного хука с заданным stdin — тесты хука
  пишут свою обвязку (`tests/test_push_hook_units.py`); класс «хук git
  проверяется настоящим push» дорог.
- `scripts/guard.py::network_address_errors_from_files` (инвариант 35)
  принимает учётную часть адреса за хост: `https://u:p@localhost/…`
  отказывается как внешний адрес. В `tests/test_push_hook_units.py` такой
  адрес собран из частей (хост — `127.0.0.1`), с комментарием.
