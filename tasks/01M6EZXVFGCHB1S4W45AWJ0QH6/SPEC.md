---
task: 01M6EZXVFGCHB1S4W45AWJ0QH6
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/gitcmd.py, orchestrator/workspace.py, scripts/git-hooks/, orchestrator/doctor/git_hooks.py, tests/
merge_after: 01M6EZXVFGXC6WBDA9QJESAZRW
budget_usd: 40
---

# SPEC: GitLab Б2.3-2: хук pre-push в клоне, его строка doctor, клон подмодулей и сверки перед отправкой

## Контекст
Это часть 2 из 4 деления задачи 01M6EXF3TMNRKCZH8CS9BXXG1Z (GitLab Б2.3).
Основание — ADR-0029 п. 13 и решение R3-F1 (Б1.1) сессии при Операторе
26.10.

Единая точка отправки пульта — `_push_plan` в `orchestrator/gitcmd.py`.
Псевдоним в аргументах команды (`-c alias.*`, `!`-форма, `--config-env`)
прячет назначение отправки в значении, и перебором форм в `gitcmd` он не
закрывается. Его закрывает второй рубеж: постоянный `core.hooksPath` клона
на каталог хуков пульта и хук `pre-push` с правилами белого списка. К нему
добавляется строка `doctor`, которая сверяет хук, его файл политики и
`core.hooksPath`.

Что есть сейчас:
- у всех клонов `core.hooksPath` стоит на один каталог
  `<config.ROOT>/scripts/git-hooks` (`orchestrator/workspace.py:48-50`,
  `:68-75`);
- его `pre-push` — только защита `main`, и при `ARTEL_PULT_GIT=1` он
  пропускает всё (`scripts/git-hooks/pre-push:14-30`);
- вызовы отправки пульта `-c core.hooksPath` не задают;
- клон проекта идёт без токена слота: `clone` нет в
  `HOSTING_SUBCOMMANDS` (`orchestrator/gitcmd.py:41`, вызов —
  `orchestrator/workspace.py:112`), а клона подмодулей в коде нет вовсе.

Часть сверок белого списка уже есть в `_whitelist_refusal`, и задача их
сохраняет:
- окружение: `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`,
  `GIT_CONFIG_COUNT`, `GIT_CONFIG_PARAMETERS`,
  `GIT_CONFIG_KEY_*`/`GIT_CONFIG_VALUE_*` (`orchestrator/gitcmd.py:189-193`,
  `:660-664`);
- конфигурация: `remote.origin.pushurl`/`push`/`mirror`, локальный
  `push.pushOption` (`:719-723`);
- глобальные опции, кроме `-C`, перед `push` (`:653-657`).

## Термины
- **Проект `target-human`** — проект, запись которого даёт
  `targets.merged_by_project_people(entry)` = `True`.
- **Каталог хуков пульта проекта** — абсолютный путь. У проекта
  `target-human` это `<config.ROOT>/scripts/git-hooks/target-human`. У
  остальных проектов и у артели — прежний `<config.ROOT>/scripts/git-hooks`
  (`workspace.hooks_path()`).
- **Файл политики** — файл `artel-push-policy` в общем каталоге git клона
  (`git rev-parse --git-common-dir`, у клона это `<клон>/.git`). Тот же
  файл видят все рабочие копии задач клона. Форма — UTF-8, ровно четыре
  строки `ключ=значение` в таком порядке, каждая с `\n` в конце:
  `project=<имя проекта>`, `base=<base записи>`,
  `branch_template=<policy.branch_template записи или
  targets.DEFAULT_BRANCH_TEMPLATE>`, `artifacts_prefix=refs/artifacts/`.
  **Эталон файла политики** — это содержимое, собранное по текущей записи
  проекта.
- **Ветка по шаблону** — имя `<имя>` ссылки `refs/heads/<имя>`, которое
  совпадает с `branch_template`. Каждый `{id}`, `{slug}`, `{ref}` шаблона
  соответствует непустой подстроке, прочие символы — буквально.
- **Эталон хука** — содержимое `scripts/git-hooks/target-human/pre-push`
  в коммите `HEAD` главной копии пульта (`config.ROOT`), а не файл на
  диске.

## Требования
1. Пульт ставит клону проекта `target-human` `core.hooksPath` = каталог
   хуков пульта проекта (вне зон записи ролей) и пишет эталон файла
   политики в двух случаях:
   - при подготовке клона (`workspace.ensure_clone`);
   - в `doctor --fix`.

   Клоны прочих проектов и артели получают прежний
   `<config.ROOT>/scripts/git-hooks`. Правила держит именно файл
   `pre-push` каталога `target-human`: git вызывает в клоне только его.
2. В каталоге хуков `target-human` есть и `pre-commit` с поведением
   прежнего `scripts/git-hooks/pre-commit`: коммит на `main` без
   `ARTEL_PULT_GIT=1` получает отказ. Перевод клона на отдельный каталог
   не снимает с него прежнюю защиту `main`.
3. Хук `pre-push` каталога `target-human` разбирает каждую строку stdin
   git и сверяет её по файлу политики:
   - проходят обновление ветки по шаблону и обновление или удаление
     ссылки с префиксом `artifacts_prefix`;
   - отказ получают отправка в `refs/heads/<base>`, удаление любой
     `refs/heads/*`, отправка `refs/tags/*` и любой иной ссылки вне
     `refs/heads/*` и `artifacts_prefix`, отправка ветки не по шаблону.

   Отказ — ненулевой код и текст в stderr, где названы ссылка и причина.
   Хук держит только эти правила. Чего он не держит, перечислено в «Не
   входит».
4. Хук `pre-push` каталога `target-human` отказывает любой отправке с
   причиной, где назван путь файла политики, если:
   - файла политики нет;
   - он не читается;
   - в нём нет любого из четырёх ключей с непустым значением.

   В хуке по-прежнему только POSIX sh и git
   (`scripts/git-hooks/pre-push:10-11`).
5. Хук срабатывает при отправке из клона любой формой, которая запускает
   хуки, в том числе псевдонимом и коротким именем удалённого
   репозитория. Маркер `ARTEL_PULT_GIT=1` его правил не снимает.
6. Каждый вызов отправки пульта из клона проекта `target-human`, прошедший
   сверки, несёт `-c core.hooksPath=<каталог хуков пульта проекта>`.
   Опцию вставляет сама единая точка отправки (`gitcmd._push_plan`) после
   сверок, рядом с `PUSH_RESET_CONFIG` (`orchestrator/gitcmd.py:966-971`).
   Вызывающие её не передают: такую опцию от вызывающего по-прежнему
   отказывает `orchestrator/gitcmd.py:653-657`. Отправки проектов
   `operator` и артели этой опции не несут.
7. Защита `main` главной копии и клонов прочих проектов сохраняется без
   изменений: файлы `scripts/git-hooks/pre-push` и
   `scripts/git-hooks/pre-commit` и их поведение прежние.
8. Строка `doctor` с именем `clone-push-hook` выдаётся из
   `check_clone_hooks`, починка — из `_fix_project_clones`
   (`orchestrator/doctor/git_hooks.py`); обе уже подключены в
   `orchestrator/doctor/cli.py:203`, `:261`. Строка сверяет клоны всех
   проектов `target-human`, у которых клон есть:
   - контрольную сумму файла `pre-push` в каталоге, куда указывает
     действующий `core.hooksPath` клона, с эталоном хука;
   - контрольную сумму файла политики с эталоном файла политики;
   - значение `core.hooksPath` клона: не задано или не равно каталогу
     хуков пульта проекта — расхождение;
   - значение `core.hooksPath`, заданное в конфигурации любой рабочей
     копии задачи клона (`git worktree list`): задано и не равно каталогу
     хуков пульта проекта — расхождение.

   Любое расхождение даёт `fail`; detail называет проект, находку и
   найденное значение. Без расхождений — `ok`. Нет ни одного клона проекта
   `target-human` — строки нет. `doctor --fix` возвращает к эталону файл
   хука (из `HEAD`) и файл политики, а `core.hooksPath` клона — к каталогу
   хуков пульта проекта.
9. Строка `clone-hooks` сверяет, как сейчас, клоны проектов, которые не
   `target-human`, и для них остаётся `warn`
   (`orchestrator/doctor/git_hooks.py:148-172`). Клоны `target-human`
   сверяет строка `clone-push-hook`.
10. При подготовке клона проекта с полем `token_slot` клон проекта
    (`git clone`) и клон его подмодулей (`--recurse-submodules` либо
    `git submodule update --init --recursive` — форму выбирает
    разработчик) идут токеном слота `token_slot` записи. Механизм тот же,
    что у `fetch`/`push`: `gitcmd.hosting_token`/`hosting_env`, токен в
    `HOSTING_TOKEN_ENV`, помощник учётных данных пульта. У записи без
    `token_slot` и у артели авторизация клона прежняя.
11. Перед отправкой проекта под белым списком (`targets.push_whitelisted`)
    `gitcmd` сверяет до вызова git:
    - `remote.origin.url` клона совпадает с адресом записи (`url_key`);
    - в действующей конфигурации вызова, включая конфигурацию рабочей
      копии, нет `url.*.insteadOf`, `url.*.pushInsteadOf` и
      `core.sshCommand`;
    - в действующей конфигурации нет `core.hooksPath`, заданного и не
      равного каталогу хуков пульта проекта. Не заданный `core.hooksPath`
      отправке не отказывает: отправка пульта всё равно несёт свой `-c`
      (требование 6), а снятый ролью путь ловит строка `doctor`
      (требование 8);
    - в окружении вызова нет `GIT_SSH_COMMAND`, `GIT_CONFIG_GLOBAL`,
      `GIT_CONFIG_SYSTEM`;
    - прежние отказы сохраняются: `GIT_DIR`, `GIT_WORK_TREE`,
      `GIT_COMMON_DIR`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_PARAMETERS`,
      `GIT_CONFIG_KEY_*`/`GIT_CONFIG_VALUE_*` в окружении,
      `remote.origin.pushurl`/`push`/`mirror` и локальный
      `push.pushOption` в конфигурации.

    Нарушение — отказ отправки до вызова git, причина называет находку
    (имя переменной или ключа конфигурации).
12. Признак проекта определяют только помощники `targets.py`
    (`push_whitelisted`, `merged_by_project_people`). Сравнивать значение
    `forge`/`merge_gate` с литералом вне `targets.py` и добавлять новые
    исключения `EXEMPT` сторожа ac9
    (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:416-421`)
    запрещено.
13. У артели и проектов `github` + `operator` поведение и существующие
    тесты прежние.

## Критерии приёмки
Песочницы — вымышленные проекты с локальным `origin`. Клон проекта
`target-human` заводит пульт (`workspace.ensure_clone`), если в критерии
не сказано иное. Каталог хуков `target-human` в песочнице берётся из
проверяемого дерева.

AC-1. Клон проекта `target-human`, заведённый `workspace.ensure_clone`,
несёт `core.hooksPath` = абсолютный
`<config.ROOT>/scripts/git-hooks/target-human`. В его общем каталоге git
лежит `artel-push-policy`, побайтно равный эталону файла политики
(четыре строки `project=`, `base=`, `branch_template=`,
`artifacts_prefix=refs/artifacts/` по записи). Ручной коммит на `main`
этого клона без `ARTEL_PULT_GIT` отказывается хуком `pre-commit`.

AC-2. В клоне проекта `target-human` хук `pre-push` отказывает каждой из
отправок: в `base`, тега, удаления ветки, ветки не по шаблону. Код
ненулевой, ссылка на `origin` не изменилась.

AC-3. Те же отправки, что в AC-2, отказываются хуком и в каждой из форм:
через `git -c alias.p=push`, через `!`-псевдоним, через короткое имя
удалённого репозитория, при `ARTEL_PULT_GIT=1` в окружении.

AC-4. В клоне проекта `target-human` отправка ветки по шаблону проекта и
отправка ссылки `refs/artifacts/<id>` проходят хук: ссылки появились на
`origin`.

AC-5. В клоне проекта `target-human` при каждом из состояний файла
политики любая отправка, в том числе ветки по шаблону, отказывается
хуком с причиной, где назван путь файла. Состояния: файла нет; он не
читается; в нём нет ключа `branch_template`.

AC-6. В главной копии и в клоне проекта `github` + `operator` хук ведёт
себя как прежде. Клон несёт прежний `<config.ROOT>/scripts/git-hooks`.
Отправка в `main` без `ARTEL_PULT_GIT=1` отказывается, с маркером
проходит. Строка `clone-hooks` по такому клону с неверным
`core.hooksPath` — `warn`, как прежде.

AC-7. `gitcmd` отказывает отправке проекта `target-human` до вызова git
(шпион не видит `push`), причина называет находку. Находки в
конфигурации:
- `remote.origin.url` не равен адресу записи;
- `url.<x>.insteadOf`;
- `url.<x>.pushInsteadOf`;
- `core.sshCommand`;
- `core.hooksPath`, заданный и не равный каталогу хуков пульта проекта;
- `remote.origin.pushurl`, `remote.origin.push`, `remote.origin.mirror`;
- локальный `push.pushOption`.

При снятом `core.hooksPath` клона и без иных находок отправка доходит до
git.

AC-8. `gitcmd` отказывает отправке проекта `target-human` до вызова git
(шпион не видит `push`), причина называет имя переменной, при каждой из
переменных окружения вызова: `GIT_DIR`, `GIT_WORK_TREE`,
`GIT_SSH_COMMAND`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`,
`GIT_COMMON_DIR`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_PARAMETERS`,
`GIT_CONFIG_KEY_0`.

AC-9. `gitcmd` отказывает отправке до вызова git (шпион не видит `push`)
при `!`-псевдониме в аргументах команды с `-c core.hooksPath=` в теле,
вызванном в клоне проекта `target-human`.

AC-10. Отправка пульта из клона проекта `target-human`, прошедшая сверки,
несёт в argv git пару `-c core.hooksPath=<config.ROOT>/scripts/git-hooks/target-human`.
Вызывающий её не передаёт. Отправка проекта `github` + `operator` такой
пары не несёт.

AC-11. `doctor` по клону проекта `target-human`: файл `pre-push`
каталога хуков, изменённый против эталона из `HEAD` главной копии, даёт
строку `clone-push-hook` со статусом `fail`. После `doctor --fix` файл
равен эталону, строка — `ok`.

AC-12. `doctor` по клону проекта `target-human`: файл политики, изменённый
против эталона по записи или удалённый, даёт строку `clone-push-hook` со
статусом `fail`. После `doctor --fix` файл равен эталону, строка — `ok`.

AC-13. `doctor` по клону проекта `target-human`: `core.hooksPath` клона
по очереди чужой абсолютный путь, прежний `<config.ROOT>/scripts/git-hooks`
и снятый — каждый даёт строку `clone-push-hook` со статусом `fail`. После
`doctor --fix` `core.hooksPath` равен
`<config.ROOT>/scripts/git-hooks/target-human`, строка — `ok`.

AC-14. Постоянный `core.hooksPath` с чужим значением в конфигурации
рабочей копии задачи клона проекта `target-human` (как это сделала бы
роль; `extensions.worktreeConfig` + `git config --worktree`) даёт строку
`clone-push-hook` со статусом `fail`, и в detail стоит это значение.
Отправка пульта из этой рабочей копии отказывается до вызова git (шпион
не видит `push`).

AC-15. Подготовка клона проекта с `token_slot`, у которого `origin`
содержит подмодуль, проверяется подменённым git с поддельной связкой
ключей. Подменённый git видит токен слота (`HOSTING_TOKEN_ENV`, помощник
пульта) и в вызове клона проекта, и в вызове клона подмодуля. Подготовка
клона проекта без подмодулей и без `token_slot` идёт без токена, как
прежде.

## Оценка объёма и деление
Сработали три сигнала:
- число критериев приёмки ≥ 10 (15);
- `budget_usd` ≥ $30 ($40 — рамка Оператора в ТЗ);
- зон задачи 5.

Материал к решению «монолит» (решение — за Оператором на гейте SPEC).
Задача уже сама — часть 2 деления 01M6EXF3TMNRKCZH8CS9BXXG1Z, нарезанная
по зонам родителя. Её механика атомарна, части держат друг друга:
- Каталог хуков `target-human` без файла политики, который пишет пульт,
  отказывает любой отправке (требование 4) и останавливает работу с
  проектом.
- Политика без каталога и `-c core.hooksPath` ничего не защищает.
- Сверка «иного `core.hooksPath`» без отдельного каталога сверяет
  каталог, который правил `target-human` не держит.
- У строки `doctor` без хука и политики нет эталона.

Отделимы лишь клон подмодулей слотом токена (требование 10, AC-15) и
новые сверки окружения и конфигурации (часть AC-7, AC-8). Их вынос даёт
подзадачу на 1–2 критерия, а цена отдельного прогона конвейера больше
экономии.

## Не входит
- Прочие строки `doctor` проекта и `forge-probe` — часть 3 деления.
- Открытие `gitlab`/`target-human` — часть 4 деления.
- Запрет отправки роли из оболочки формами, выключающими хуки в самом
  вызове (`--no-verify`, `-c core.hooksPath=…`). Хук их не держит (модель
  угроз ТЗ). В вызовах пульта их закрывают сверки требования 11 и уже
  существующий отказ псевдонима в аргументах (`gitcmd.py:887-901`).
- Удержание хуком постоянного `core.hooksPath`, который роль задала в
  конфигурации клона или рабочей копии. Его обнаруживает строка `doctor`
  (требование 8), а отправку пульта отказывает сверка требования 11.
- Правила `gitcmd`, которых хук не держит (хук знает только файл
  политики, ни БД, ни журнала у него нет):
  - ветка живой задачи из БД: хук пропустит ветку по шаблону мёртвой или
    несуществующей задачи (`gitcmd.py:698-700`);
  - запрет `+`-refspec и перезаписи (`:683-684`);
  - сверка sha аренды с журналом (`:709-718`);
  - опции `-o` и адрес назначения.

  В вызовах пульта эти правила по-прежнему держит `gitcmd`.
- Починка `doctor --fix` для `core.hooksPath` в конфигурации рабочей
  копии задачи (AC-14 требует только `fail`). Обновление файла политики
  при смене записи проекта — только через `doctor --fix`, отдельного
  механизма нет.
- Изменение защиты `main` главной копии и клонов прочих проектов.

## Материалы
- `tasks/01M6EZXVFGCHB1S4W45AWJ0QH6/TZ.md`; ADR-0029 п. 13; решение R3-F1
  (Б1.1); `tasks/01M6EZXVFGCHB1S4W45AWJ0QH6/SPEC-AUDIT.md` (итерация 1,
  Д-1…Д-7).
- `orchestrator/gitcmd.py`:
  - `:41` — `HOSTING_SUBCOMMANDS`;
  - `:125-165` — `hosting_token`, `hosting_env`;
  - `:185-193` — `PUSH_RESET_CONFIG`, имена переменных окружения;
  - `:645-724` — `_whitelist_refusal`;
  - `:887-901` — отказ псевдонима в аргументах;
  - `:966-971` — вставка `PUSH_RESET_CONFIG`.
- `orchestrator/workspace.py`:
  - `:48-50` — `hooks_path`;
  - `:68-75` — `set_clone_hooks`;
  - `:95-123` — `ensure_clone`.
- `orchestrator/doctor/git_hooks.py:148-192` — `check_clone_hooks`,
  `_fix_project_clones`; подключение — `orchestrator/doctor/cli.py:203`,
  `:261`.
- `scripts/git-hooks/pre-push:10-30`, `scripts/git-hooks/pre-commit`.
- `orchestrator/targets.py:364-365` (`DEFAULT_BRANCH_TEMPLATE`,
  `BRANCH_PLACEHOLDERS`), `:558-570` (`push_whitelisted`,
  `merged_by_project_people`); `orchestrator/catalog.py:627-639`
  (`branch_template`, `branch_name`).
- Существующие тесты, которые должны остаться зелёными без правки:
  - `tests/test_gitcmd_push_point.py` — клон `target-human` без
    `core.hooksPath`, шпион отправку не исполняет;
  - `tests/test_git_hooks.py`;
  - `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:800-885`.
