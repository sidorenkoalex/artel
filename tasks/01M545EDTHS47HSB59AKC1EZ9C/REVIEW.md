---
task: 01M545EDTHS47HSB59AKC1EZ9C
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: D2-2 — токен хостинга внешнего проекта и проверки doctor

## Фаза A — план
- Таблица покрытия PLAN.md полна: требования 1–9 разнесены по шагам 1–4; шаги — единицы размера MR (gitcmd / ci.gh / doctor / песочница / карта).
- Подход (механизм в `gitcmd.git` без смены сигнатуры, токен только окружением через `GIT_CONFIG_COUNT/KEY/VALUE` + `ARTEL_HOSTING_TOKEN`) не конфликтует с архитектурой: все git-вызовы пульта идут через `gitcmd.git`; `gitcmd.carpentry` (`orchestrator/gitcmd.py:339-371`) — только локальные плотницкие команды (вызовы в `artifact_branch.py`, `notes.py`, `snapshot.py`, `advance_gates/acceptance.py` — read-tree/hash-object/commit-tree/update-ref/show), прямые `subprocess` git в `acceptance.py:1783` и `plank_helper.py:71` — локальные. Обхода механизма нет.
- ANSWER-1 учтён: П-2 — `BaseBranchCheckTest.setUp` (`tests/test_doctor.py:639-649`), утверждения не тронуты; Ф-2 — `gitcmd`/`ci.gh` берут запись из `targets.load()`; Р-1 — `check_base_branch` даёт `skip` с текстом отказа (`misc_checks.py:104-106`), 5.4 — «недоступно»; Ф-3 — признак по пути только под `config.PROJECTS` (`gitcmd._project_of_path`).
- «Влияние на систему» соответствует diff: 10 файлов, всё в зонах SPEC (`config.py` — константа порога, названа требованием 5.1); защищённых путей (`skills/`, `templates/`, `.github/`, `gates.yaml`, `roles.yaml`) diff не касается. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `gitcmd._hosting_project` (`gitcmd.py:92-116`): подкоманды `fetch/push/pull/ls-remote`, проект по `-C` под `config.PROJECTS/<имя>/<…>` (артель и сам каталог проекта исключены, `len(parts) < 2`), второй признак — URL аргумента `push` независимо от `-C`. `hosting_env` ставит `credential.helper=` и помощник пульта, читающий пароль из `$ARTEL_HOSTING_TOKEN`; `.git/config` и `GIT_CONFIG_GLOBAL` не трогаются. `ci.gh(repo=)` и `check_base_branch` получают `GH_TOKEN`. |
| 2 | OK | Пустой слот — отказ с именем слота (`hosting_token`), без поля `token_slot` — `(None, None)`, прежняя авторизация. |
| 3 | OK | Тексты отказов значения не несут; токен только в окружении дочернего процесса, не в `os.environ` пульта; argv помощника — `get`. AC-5 (трасса `GIT_TRACE` помощника, все файлы корня, журналы, `role_env`) зелёный. |
| 4 | OK | Для артели `hosting_token` → `(None, None)`, `_project_of_path` исключает `artel`; `project_by_url` пропускает `DEFAULT_TARGET`. Окружение = `pult_env()`, argv тот же (AC-1). |
| 5 | OK | `orchestrator/doctor/project_checks.py`: 5.1 (возраст `FETCH_HEAD` до fetch, порог `config.PROJECT_CLONE_STALE_HOURS = 24`, нет файла — warn, fetch без смены рабочих копий), 5.2 (`push --dry-run` в `refs/artifacts/doctor-push-probe`), 5.3 (три формы `on:`), 5.4 (информационная, «недоступно» — skip), 5.5 (fail/warn/warn №24, значения не печатаются), 5.6 (маска через `project_profile.mask_matches` по `git ls-files`), 5.7 (`brief.project_skills_refusal`). |
| 6 | OK | Запись артели — семь строк `skip` «неприменимо». |
| 7 | OK | `hosting_token` проверяет `runner.in_role_environment()` до чтения слота, для записи с полем и без; 5.1/5.2/5.5 — `ROLE_SKIP`; 5.4 в роли — «недоступно» через отказ `gh_env`. |
| 8 | OK | `_push_closing_sha` не менялся, push по URL `origin` клона ловится вторым признаком; планка AC-11 зелёная. |
| 9 | OK | `tests/sandbox.py::isolate_keychain_and_role` в `TmpRootTest.setUp` и `RealGitSandbox.setUp`: `keychain.token` → `test-token-<слот>`, `ARTEL_ROLE` снят, `HOME` дома роли заменён. Существующие тесты, вызывающие настоящий `keychain.token` под песочницей, искал (`grep -rn "keychain\.token(" tests`) — таких нет, сужения данных под неизменными утверждениями нет; собственные подмены тестов (`patch.object(keychain, "token", …)`) применяются после `setUp` и перекрывают умолчание. |

Тесты: долгоживущий файл задачи покрывает AC-1…AC-10, AC-12…AC-16; AC-11 — планка `Группа: разовый` с обоснованием (закрытое имя `_push_closing_sha`), её долгоживущее свойство (push по URL проекта из чужого источника — с токеном) держит AC-13 в `tests/`. `tests/test_hosting_token_units.py` — три метода с заявками «Ловит мутацию», наблюдаемыми (затёртый `KEY_0`, побайтное сравнение адресов, поиск подстроки `pull_request`) и не повторяющими долгоживущий файл. `tests/test_doctor.py` — добавлен только `setUp` (ANSWER-1, П-2), утверждения не изменены и не удалены; других изменений в `tests/` вне песочницы нет.

Наблюдения без требования исправить (вкус, сценарий поломки за рамками SPEC, поэтому не заведены замечаниями):
- `orchestrator/gitcmd.py:84-89` (`_declared_targets`): битый `targets.yaml` → `{}` → хостинговая операция внешнего проекта идёт без токена и без отказа требования 7 даже в процессе роли. PLAN это заявляет («прежнее поведение»); на практике при битом `targets.yaml` пульт не работает целиком, а у роли нет учётных данных Оператора. Если захочется закрыть fail-closed — отказ для `-C` под `config.PROJECTS/<не артель>/…` при `TargetsError`.
- `orchestrator/doctor/project_checks.py:104-128` (`declares_pull_request`): потоковое отображение `on: {pull_request: …}` и многострочный потоковый список не распознаются (warn вместо ok). SPEC требует три формы, и все три распознаются.

## Замечания

Нет (0 blocker, 0 major).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m545edths47hsb59akc1ez9c_project_token.py tests/test_hosting_token_units.py "tests/test_doctor.py::BaseBranchCheckTest"` — 26 passed, 94 subtests passed (29.6 с).
- `python3 orchestrator/artel.py plank-run 01M545EDTHS47HSB59AKC1EZ9C` (пульта) — `test_ac11_push_closing_sha.py` 1 passed, код выхода pytest 0.
- Временная мутация в памяти процесса (файл не правился, `git status` чист): `gitcmd.HOSTING_SUBCOMMANDS = ('fetch','push','pull')` → `HostingTokenTest.test_ac12_local_commands_skip_slot_remote_ones_use_it` красный, 3 failures (subTest `ls-remote` и др.). Заявка AC-12 исполнима.
- Свежесть карты: `scripts/codebase_map.render` в памяти против `docs/codebase-map.md` без строк `built_at_sha:` — совпадает («fresh»).
- `grep` по `orchestrator/` на прямые `subprocess` git-вызовы и вызовы `gitcmd.carpentry` — хостинговых вне `gitcmd.git` нет (кроме `git clone` в `workspace.py:111`, вне зоны по SPEC «Не входит»).
- CI коммита 97b13809 — зелёный (16 проверок), из пакета.

## Предложения системе
- Токен в окружении хостингового git-вызова (`ARTEL_HOSTING_TOKEN`, `GIT_CONFIG_*`) виден любому хуку и `core.*Command` клона. Сегодня это закрывает запрет ADR-0023 на запись роли в `config`/`hooks` общего клона (`docs/adr/0023-role-step-sandbox.md:837`). Стоит держать связь явной: ослабление этого запрета открывает утечку токена.
- Сделать `scripts/codebase_map.py --check` (сравнение без записи файла): ревьюверу сейчас приходится импортировать `render` вручную, чтобы проверить свежесть, не меняя рабочее дерево.
