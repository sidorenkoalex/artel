---
task: 01M6JJ4J4NBV2Y1Q4XHE3C3FVT
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/direct_git.py, tests/test_01m3vfyp4rxby0bg8d3a0b18hd_pult_commit.py, tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py, tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py, tests/test_01m6jj4j4nbv2y1q4xhe3c3fvt_*.py, tests/test_codex_login_shell_path.py, tests/test_multitarget.py, tests/test_providers.py; в) пути-признаки (песочница ролей): docs/reference/role-home/claude/settings.json, orchestrator/providers/claude.py, orchestrator/providers/codex.py, orchestrator/runner.py; в) защищённые пути: knowledge/; г) budget_usd 90 ≥ 45."
spec_sha: 70e98e8c616b7229780f4457b7182fc323691cc1
schema_version: 5
---

# SPEC-AUDIT: Граница git для ролей — отказ git clean и git в репозитории пульта, команда удаления файла задачи

## ТЗ и SPEC
ANSWER-n.md в каталоге документов нет; решений Оператора на гейте SPEC в брифе нет. Сверка ТЗ ↔ SPEC по пунктам:

- ТЗ пп. 1–5, 7–9 перенесены в SPEC требования 1–5, 7–9 без потерь; имя команды удаления выбрано SPEC (`task-rm <id> <путь>…`, SPEC «Требования» п. 4) — ТЗ п. 4 это право даёт.
- **Отклонение А1.** ТЗ п. 6: «потеря ускорения `tests/direct_git.py` (если есть) — замер в SPEC». SPEC требование 6 переносит замер в PLAN.md разработчика («разработчик записывает в PLAN.md замер времени…»). Замер, который ТЗ требовал как вход решения на гейте SPEC, оказывается после гейта. По коду потеря при обёртке на PATH не условная, а наверняка: `prefer_direct_git` ничего не делает, если `which git` ≠ `/usr/bin/git` (`tests/direct_git.py:56-58`), а обёртка стоит раньше `/usr/bin`; вдобавок каждая обёртка на Python добавляет старт интерпретатора к каждому вызову git (тесты пульта зовут git «сотнями раз на тест», `tests/direct_git.py:4-7`). Решение Оператора: принять перенос замера в PLAN либо потребовать оценку в SPEC.
- ТЗ «Существующие тесты: правка не ожидается… эскалация с перечнем» — в SPEC «Не входит», последний пункт; совпадает.
- В SPEC нет требований, которых нет в ТЗ.

## Факты против кода
Подтвердилось:
- `config.PROJECTS = ROOT / ".artel" / "projects"` — `orchestrator/config.py:57`; `config.ROOT` — `config.py:11`.
- `artifact_branch.docs_dir` = `docs_root(target)/"tasks"/task_id` — `orchestrator/artifact_branch.py:800-802`.
- `ALLOWED_TOOLS = "Bash(git:*),Bash(python3:*)"` — `orchestrator/providers/claude.py:45`; внешний проект — `external_allowed_tools`, def на `:114`, строка `Bash(git:*),Bash(python3 {artel_py}:*)` на `:122`; `--add-dir` — `:194`.
- `SANDBOX_MODE = "workspace-write"` — `orchestrator/providers/codex.py:136`; `--add-dir` каталога документов и каталога `suite-run` — `codex.py:437-443`.
- `_role_path_dirs` — `orchestrator/runner.py:1017`, `role_env` — `runner.py:1093`; PATH = `[venv_bin] + _role_path_dirs(...)` — `runner.py:1178`; `ARTEL_ROLE`/`ARTEL_TASK` — `runner.py:1179-1182`.
- `_ROLE_ALLOWED_COMMANDS` — `orchestrator/artel.py:2562-2565`, комментарий над ним — `artel.py:2538-2561`; список закрыт по умолчанию (`_role_allowed_command`, `artel.py:2576-2592`).
- `PULT_MARKER_ENV = "ARTEL_PULT_GIT"` — `orchestrator/gitcmd.py:25`.
- `GIT_CEILING_DIRECTORIES` — `orchestrator/plank_helper.py:66-67`.
- `mutation_run._reset` — `clean -ffdx` во временной копии, `orchestrator/mutation_run.py:467`.
- Автокоммит удалений документов — `checkpoint._commit_step_artifacts_to_branch`, `orchestrator/checkpoint.py:1393-1428` (`remove=removed`, `:1424-1425`).
- Тесты порядка PATH: `tests/test_providers.py:260` (только `[0]` = venv/bin), `tests/test_multitarget.py:941` (только `[0]`), `tests/test_codex_login_shell_path.py:199-201` (равенство PATH Claude и Codex и `[0]`), `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py:575-591` (`git --version` по PATH роли = `/usr/bin/git --version`, каталоги объявленных инструментов в PATH). Обёртка вторым элементом с ними совместима — ТЗ п. 6 и SPEC требование 6 согласованы с кодом.
- Раздел `docs/stack.md:517` «Паритет безопасности роли: запрет у Claude → чем закрыт у Codex» существует.

Не подтвердилось:
- **Отклонение Б1 (мелкое).** SPEC «Материалы»: «разбор аргументов git с раскрытием псевдонимов — `orchestrator/gitcmd.py:258-276` (`_push_plan`)». На `gitcmd.py:258-276` лежат константы `GIT_GLOBALS_WITH_VALUE` и `GIT_BUILTINS`; сам `_push_plan` — `gitcmd.py:1123`. Неточность пришла из ТЗ (факт 4); разработчику нужны оба места.
- Мелочь: `docs/stack.md:530-535` перечисляет белый список команд роли без `plank-run`/`suite-run`/`mutation-run`/`preflight`/`knowledge`/`guard` (уже устарел на main) и утверждает, что под признаком роли отказывают все команды, меняющие состояние репозитория. `task-rm` удаляет файлы — требование 8 (правка этого раздела) обязано снять это противоречие; SPEC это прямо не называет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да, с пробелом | потолок не ставится вовсе / ставится без разрешения пути (`/tmp`→`/private/tmp`) — git из каталога документов находит ROOT. **Не ловит** (Отклонение В1): потолок = `config.PROJECTS` вместо `config.ROOT` — все четыре cwd AC-1 лежат под `PROJECTS`, тест зелёный, а git из `.artel/logs`, `.artel/home`, `.artel/canary` по-прежнему доходит до ROOT (SPEC требование 1 называет `logs/`, но AC его не проверяет). Частично ловит AC-14 только если временный подкаталог doctor лежит вне `PROJECTS`; SPEC требование 7 этого не требует |
| AC-2 | да, с пробелом | разбор `-C`/`--git-dir`/`GIT_DIR`/`-c core.worktree` выкинут; своя рабочая копия ошибочно отклоняется. **Не ловит** (Отклонение В2): выкинутый разбор `--work-tree` и `GIT_WORK_TREE` — формы требования 2, которых нет ни в одном AC |
| AC-3 | да | обёртка пропускает `clean` в своей рабочей копии (отказ только в ROOT); строка отказа без `task-rm` |
| AC-4 | да, с пробелом | раскрытие псевдонимов из `-c`/`.git/config`/`GIT_CONFIG_PARAMETERS` выкинуто. **Не ловит** (Отклонение В2): `--config-env`, `GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n`, `!`-псевдоним из `.git/config`, `core.pager`, `core.fsmonitor` — формы требования 3 без критерия |
| AC-5 | да | отказ `clean` по признаку «любой репозиторий», а не «внутри ROOT» |
| AC-6 | да | воспроизведение инцидента; ловит отсутствие и потолка, и отказа `clean` |
| AC-7 | да | `task-rm` не удаляет / удаляет не тот путь |
| AC-8 | да | частичное удаление до проверки всего набора; пропуск проверки ветки артефактов, `../`, ссылок, `.git` |
| AC-9 | да | `<id>` не сверяется с `ARTEL_TASK`; Оператору отказ |
| AC-10 | да, с пробелом | `task-rm` не внесена в белый список. **Не ловит** (Отклонение В3): «миссия роли» не названа — упоминание в одной заметке (например, только `_reviewer_checks_note`, `orchestrator/role_prompt.py:336`) проходит AC-10, а миссия test_author — роли инцидента — команды не называет. В `role_prompt.py` нет единого перечня команд: они разнесены по `docs_dir_note` (`:503`), `suite_run_note` (`:426`), `_reviewer_checks_note` (`:336`), `_plank_run_point` (`:311`) |
| AC-11 | да | диспетчер не снимает механизм — `mutation-run` (`clean -ffdx`) отказывает; `ARTEL_PULT_GIT=1` трактуется как освобождение |
| AC-12 | да | обёртка трогает репозитории вне ROOT; обёртка ломает `-C <tmp>` |
| AC-13 | да | каталог обёртки не второй / после каталога git; `--version` обёртки свой |
| AC-14 | да, с пробелом | граница снята — `fail`; временный каталог не удалён. **Не ловит** (Отклонение В4): строка doctor, проверяющая только границу и пропускающая половину «`git clean` в репозитории пульта отклоняется», — подмена в AC-14 касается только границы |
| AC-15 | да | строка `deny` не добавлена / JSON сломан |

## Зоны
- Зоны SPEC (`zones:` frontmatter) совпадают с зонами ТЗ; тестовая зона сужена до `tests/test_01m6jj4j4nbv2y1q4xhe3c3fvt_*.py` — равна по смыслу «долгоживущие файлы задачи».
- Защищённые пути (`config.PROTECTED_PATHS`, `orchestrator/config.py:786-792`) зонами не задеты: `docs/reference/role-home/claude/settings.json` не защищён; `skills/` и `conftest.py` явно вне зон. `knowledge/` (сигнал глубины) встречается в SPEC требование 1 лишь как пример каталога под `<ROOT>/.artel`, в который не пишут, — не зона.
- Песочница ролей: расширение явное и предусмотрено ТЗ — новая команда, меняющая файлы, в белом списке роли (`artel.py:2562`), строка `deny` в курируемом HOME, окружение роли (`runner.role_env`). Молчаливого расширения нет. Для Codex `task-rm` работает внутри уже открытых каталогов (`codex.py:437-443`) — новых `--add-dir` не требуется.
- `orchestrator/doctor/__init__.py` в зонах — нужен, если проверка регистрируется через пакет (`orchestrator/doctor/cli.py:133-138` зовёт `doctor.isolation_smoke`/`doctor.provider_isolation_smokes`).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| PATH роли (`runner.role_env`, `runner.py:1178`) | `[0]` = `.artel/venv/bin` — `tests/test_providers.py:260`, `tests/test_multitarget.py:941`, `tests/test_codex_login_shell_path.py:200-201` | да (обёртка — `[1]`) | те же тесты + AC-13 | остаётся |
| PATH Claude = PATH Codex | `tests/test_codex_login_shell_path.py:199` | да (требование 5 — механизм одинаков) | тот же тест | остаётся |
| `git --version` по PATH роли = настоящий git | `tests/test_01m5kjne39phv9eawjchk7qdfs_direct_git.py:580-581` | да | тот же тест + AC-13 | остаётся |
| Ускорение git в тестах (`tests/direct_git.py:42-77`) | `prefer_direct_git` при `which git == /usr/bin/git` | нет под окружением роли с обёрткой (`tests/direct_git.py:56-58`) | не покрыто, требования-замены нет — только замер в PLAN (SPEC требование 6) | вопрос Оператору (Отклонение А1) |
| Белый список команд роли «только чтение» (`artel.py:2538-2565`; `docs/stack.md:530-535`) | закрыт по умолчанию — `artel._role_allowed_command`, `tests/test_canary_run_task.py:175`, `tests/test_epic_supervisor_units.py:66-68` | сужается по смыслу: `task-rm` пишет; так требует ТЗ п. 4 | AC-7–AC-10 | остаётся, расширение санкционировано ТЗ |
| Курируемый `deny` Claude (`docs/reference/role-home/claude/settings.json`) | правила `deny` | усиливается (новая строка) | AC-15 | остаётся |

Раздела «Меняемое поведение» в SPEC нет — правка существующих утверждений не заявлена, это согласуется с ТЗ.

## Пути обхода гейтов
1. **Отклонение Е1 — doctor сам воспроизводит инцидент.** SPEC требование 7: строка doctor проверяет, «что `git clean` в репозитории пульта отклоняется», без требования к неразрушительной форме. Буквально выполненная проверка вида `git clean -fX` в `config.ROOT` при сломанном механизме (как раз тот случай, ради которого строка заведена) удалит игнорируемые файлы пульта — `.artel/models.yaml`, `.artel/home/.claude` и прочее из инцидента. Требование должно назвать неразрушительную форму (`git clean -n`/`--dry-run`) или временный репозиторий-дублёр. То же для тестов AC-14, если они гоняются против настоящего ROOT, а не песочницы.
2. **Е2 — снятие механизма диспетчером переходит на код роли.** По SPEC требование 5 механизм убирается из окружения процесса `artel.py` «и дочерних»: `suite-run`/`plank-run`/`mutation-run` запускают тесты и планку, написанные ролью, уже без механизма требований 2–3 (остаётся только потолок требования 1). Тест роли с `subprocess.run(["git", "-C", <ROOT>, "clean", …])` при прогоне через `plank-run` проверку минует. По модели угрозы (ошибочная команда) — наблюдение, не блокер; полезно упомянуть в `docs/stack.md` в таблице паритета.
3. **Е3 — двусмысленность форм требования 3.** «`-c`, `--config-env`, … задающие псевдоним, `core.worktree`, `core.pager` или `core.fsmonitor`» читается двумя способами: (а) отказ любой команды git в репозитории внутри ROOT, если такой ключ задан (тогда `git -c core.pager=cat log` в своей рабочей копии — отказ); (б) отказ только тогда, когда вызов приводит к `clean`. Не сказано и про `core.pager`/`core.fsmonitor`, записанные в `.git/config` рабочей копии (`!`-псевдоним оттуда назван явно). Вложенный `git clean`, который запускают pager/fsmonitor/`!`-псевдоним, всё равно идёт через PATH и попадает в обёртку, так что разрушительный путь закрыт при любом прочтении; но объём отказа разработчик выберет сам. Формулировка пришла из ТЗ п. 3 — решение Оператора на гейте.
4. **Е4 — `xcrun git`.** Каталог git роли — `/usr/bin` (на macOS), там же `xcrun`; `xcrun git clean …` обходит обёртку на PATH без абсолютного пути. По модели угрозы это ближе к «абсолютному пути к git» (вне задачи), но в «Не входит» стоит назвать явно.

## Вердикт
`concerns` — SPEC работоспособен, отклонения решаемы Оператором на гейте:

1. **А1** — замер потери ускорения `tests/direct_git.py` перенесён из SPEC в PLAN.md против ТЗ п. 6 (SPEC требование 6); потеря при обёртке на PATH наверняка (`tests/direct_git.py:56-58`).
2. **Е1** — требование 7 не требует неразрушительной формы проверки `git clean` в `config.ROOT`: при сломанном механизме doctor сам повторит инцидент.
3. **В1** — AC-1 не ловит потолок на `config.PROJECTS` вместо `config.ROOT`: нет cwd вне `PROJECTS` (например, `.artel/logs`), хотя требование 1 называет `logs/`.
4. **В2** — формы требований 2–3 без критерия: `--work-tree`, `GIT_WORK_TREE`, `--config-env`, `GIT_CONFIG_COUNT/KEY_n/VALUE_n`, `!`-псевдоним из `.git/config`, `core.pager`, `core.fsmonitor` (SPEC AC-2, AC-4).
5. **В4** — AC-14 не ловит строку doctor без половины «отказ `git clean`».
6. **В3** — AC-10 не называет, миссии каких ролей должны упоминать `task-rm`; в `orchestrator/role_prompt.py` нет единого перечня команд (`:311`, `:336`, `:426`, `:503`).
7. **Е3** — двусмысленный объём отказа для `core.pager`/`core.fsmonitor` (SPEC требование 3; из ТЗ п. 3).
8. **Б1** (мелкое) — `_push_plan` на `orchestrator/gitcmd.py:1123`, не на `:258-276`; `docs/stack.md:530-535` про «только читающие команды роли» требование 8 должно поправить явно.
9. Наблюдения без требования правки: Е2 (код роли под `plank-run`/`suite-run` без механизма), Е4 (`xcrun git`).
