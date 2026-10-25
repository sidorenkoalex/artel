---
task: 01M5T18K1YFBYA7MM1BBRV869A
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/brief.py, orchestrator/role_prompt.py, orchestrator/conventions.py, orchestrator/artel.py, orchestrator/doctor/project_conventions.py, orchestrator/doctor/cli.py, orchestrator/doctor/__init__.py, orchestrator/repo_context.py, docs/target-onboarding.md, tests/
merge_after: 01M5T19041XE2KB6A52F0AT0NF
budget_usd: 60
---

# SPEC: Конвенции внешнего проекта в брифе — из файла пульта, сверка дрейфа

## Контекст
Решение Оператора 25.10.2026 (бэклог П1, строки ee693e48 и 1f02aff4):
`CLAUDE.md`, `AGENTS.md` и прочие ИИ-настройки внешнего проекта пульт ролям
не передаёт. Сейчас `orchestrator/brief.py:45` `PROJECT_CONVENTIONS =
("CLAUDE.md", "AGENTS.md")` и `_read_project_conventions` (`:602`) кладут
текст обоих файлов корня базовой ветки клона в бриф каждой роли
(`_project_conventions_parts`, `:777`; потребители — бриф developer `:1252`,
spec_auditor `:1322`, analyst `:1623`, добавка test_author `:1661`, пакет
ревьювера `orchestrator/review.py:955`). Те же файлы приходят и через
`knowledge` компонента: элемент-файл `CLAUDE.md` (`brief.py:715–722`),
элемент-каталог `./` или `docs/` берёт все `*.md` под собой
(`brief.py:678–683`, `:738–741`). У feedback `AGENTS.md` начинается указанием
«первой командой запусти ./harness/task.sh» — роль пульта получила бы чужой
процесс. Вместо этого конвенции проекта разбирает сессия при Операторе в файл
`.artel/projects/<имя>/conventions.md` локального слоя пульта; бриф берёт
текст оттуда, а `doctor` сверяет, не изменились ли исходные файлы проекта с
момента разбора. Сверки дрейфа сейчас нет.

Решения гейта SPEC 25.10.2026: возврат 1 — фильтр обвязки в `knowledge` в
этой задаче (канал передан из задачи 01M5T19041XE2KB6A52F0AT0NF, её
ANSWER-2, ответы 1 и 5), поведение при сломанном заголовке, расширение зон
на `orchestrator/role_prompt.py` и требование 10, монолит, `budget_usd` 60;
возврат 2 — решения 1–11 и условия мандата У1–У4 файла
`tasks/01M5T18K1YFBYA7MM1BBRV869A/ANSWER-1.md`, внесённые ниже.

## Требования
Всё ниже касается только задач внешних проектов (target не равен
`config.DEFAULT_TARGET`); бриф, пакет и миссии ролей артели не меняются.

1. **Источник конвенций.** В брифе каждой роли задачи внешнего проекта (бриф
   analyst, developer, spec_auditor, добавка test_author, пакет ревьювера —
   там же, где сейчас блок `PROJECT_CONVENTIONS`) конвенции проекта — один
   компонент с текстом файла `repo_context.projects_root() / <имя проекта> /
   "conventions.md"` локального слоя пульта (путь — через
   `repo_context.projects_root()` с его охраной подменённого корня,
   `orchestrator/repo_context.py:61–72`, не прямым `config.PROJECTS`;
   решение гейта 1). Формат компонента — тот же, что сейчас у компонента
   файла конвенций (`brief._project_conventions_parts`, вызов `render`
   потребителя с подписью `<имя файла> (<где>)`), с заменой имени файла на
   `conventions.md` и места на `.artel/projects/<имя>/conventions.md`:
   подпись `conventions.md (.artel/projects/<имя>/conventions.md)`; опись
   (размер, sha256) — у тех же потребителей, что сейчас (решение гейта 8).
   `CLAUDE.md` и `AGENTS.md` корня проекта блоком конвенций в бриф не
   читаются ни с базовой ветки клона, ни из рабочей копии: ни их текста, ни
   пометок о них («файла нет», «не прочитаны») этот блок не несёт. Канал
   `knowledge` — требование 11.
2. **Заголовок скрыт.** Если `conventions.md` начинается заголовком отметки
   разбора (требование 6), в бриф идёт только текст после заголовка;
   строк заголовка (ветка, коммит, пути и blob исходных файлов) в брифе нет.
   Файл без заголовка идёт в бриф целиком. Файл со сломанным заголовком
   (требование 6) в бриф не идёт ни целиком, ни частью — требование 4.
3. **Документы `knowledge`** единственного компонента записи `components:`
   (SPEC 01M5ENWB2XHZFRNQ3Q3PZSAH2T) — как сейчас, следом за компонентом
   `conventions.md`, с базовой ветки клона, с фильтром обвязки требования 11.
   Повторы убираются между элементами `knowledge`, как сейчас; путь
   `conventions.md` с путями дерева проекта не сравнивается. Компонент
   `conventions.md` от состояния клона не зависит.
   - Контекст проекта разрешён (`repo_context.resolve` вернул контекст), а
     базовая ветка клона не читается: пометка «конвенции проекта не
     прочитаны: <причина> — <элементы knowledge>, <где>» и запись журнала
     `бриф: конвенции проекта не прочитаны` — только при наличии
     `knowledge`.
   - Контекст проекта не разрешён (`repo_context.resolve` вернул `None`,
     например записи проекта нет в `targets`): бриф несёт пометку
     «конвенции проекта не прочитаны: <причина> — <где>» (вид прежней
     пометки `PROJECT_CONVENTIONS_UNREAD_MARK`, без перечня элементов
     `knowledge`; причина — `repo_context.unresolved_reason`) и запись
     журнала `бриф: конвенции проекта не прочитаны` независимо от наличия
     `knowledge`; текст `conventions.md`, если файл читается, показывается
     всё равно; шаг не останавливается (решение гейта 9).
4. **Файла нет или не читается.** Нет `conventions.md`, это не обычный файл
   (каталог, символьная ссылка и т.п.), текст не в UTF-8, чтение отвечает
   ошибкой ОС (`OSError`) или заголовок сломан (требование 6) — бриф
   собирается без конвенций проекта и на месте компонента несёт строку
   «конвенции проекта не разобраны: <причина> — <путь>», где путь —
   относительный `.artel/projects/<имя>/conventions.md`, как в подписи
   компонента (решение гейта 11), а причина различает случаи («файла нет»,
   «не обычный файл», «текст не в UTF-8», текст ошибки ОС — не «файла нет»,
   «заголовок отметки не читается»; решение гейта 10); в журнал задачи —
   запись действия «бриф: конвенции проекта не разобраны» с той же
   причиной. Сборка брифа и старт шага роли этим не останавливаются.
5. **Предел размера** текста `conventions.md` — только у потребителей, у
   которых он есть сейчас, и тот же, что сейчас у файла конвенций: бриф
   developer и spec_auditor (`_manifest_component`, `orchestrator/brief.py:481`)
   и пакет ревьювера (`review.artifact_part`, `orchestrator/review.py:190`) —
   пропуск компонента сверх `config.CONTEXT_FILE_MAX_BYTES` с прежней
   пометкой пропуска. У брифа analyst и добавки test_author
   (`_journal_component`, `orchestrator/brief.py:444–459`) предела нет и
   не появляется. Размер считается по тексту без заголовка — по тому, что
   идёт в бриф.
6. **Формат заголовка отметки разбора** — блок в начале файла, тело
   которого между строками `---` разбирает `orchestrator/yamlmini.py::mapping`
   (плоский `frontmatter` вложенное `sources` не разбирает); sha и id blob —
   в двойных кавычках, чтобы шестнадцатеричная строка из одних цифр не
   разобралась числом:
   ```
   ---
   conventions_stamp: 1
   base_branch: <базовая ветка записи проекта>
   base_sha: "<40-символьный sha коммита базы на момент отметки>"
   sources:
     <путь файла в репозитории проекта>: "<40-символьный id blob git на base_sha>"
     ...
   ---
   ```
   Заголовок — блок от первой строки `---` до следующей строки `---`
   включительно. Три вида файла:
   - **без заголовка** — первая строка не `---`, либо блок между строками
     `---` разобран и ключа `conventions_stamp` в нём нет;
   - **сломанный заголовок** — первая строка `---`, а закрывающей строки
     `---` нет; либо `yamlmini.mapping` отвечает на тело блока ошибкой
     `YamlError`; либо `conventions_stamp` есть, но `base_branch` пуст или
     не строка, `base_sha` не 40 шестнадцатеричных символов или `sources` —
     не непустое отображение «путь → 40 шестнадцатеричных символов» (в том
     числе `sources` — список или элемент без blob; решение гейта 2);
   - **с заголовком** — всё прочее с `conventions_stamp`.
7. **Команда отметки** `python3 orchestrator/artel.py conventions-stamp
   <проект> <файл>…` (модуль `orchestrator/conventions.py`): читает коммит
   `refs/heads/<base>` клона проекта без обращения к сети — не `HEAD` клона
   и не его рабочее дерево; сетевых git-вызовов (`fetch`, `ls-remote`,
   `push`) не делает (решение гейта 4); для каждого названного файла — id
   его blob на этом коммите, и пишет заголовок требования 6 в начало
   `conventions.md` (`sources` — ровно названные файлы), заменяя прежний
   заголовок, если он был. Текст под заголовком остаётся побайтно прежним.
   Отказ с ненулевым кодом выхода и причиной в выводе, без изменения файла:
   проект `config.DEFAULT_TARGET` или неизвестный; клон не читается (пути
   клона нет или это не репозиторий git); базовая ветка не читается (нет
   `refs/heads/<base>`); файлы не названы; названного пути нет в дереве
   коммита или это не обычный файл (каталог, символьная ссылка, подмодуль);
   `conventions.md` нет или он не читается (случаи требования 4); заголовок
   `conventions.md` сломан (требование 6, в том числе сломанные `sources` и
   `base_branch`).
8. **Дрейф в `doctor`.** Новая проверка `project-conventions`
   (`orchestrator/doctor/project_conventions.py`, вызов — в цикле по
   проектам `orchestrator/doctor/cli.py`) — по строке на каждый внешний
   проект записи `targets`. Сверка — по коммиту `refs/heads/<base>` клона, не
   по `HEAD` и не по рабочему дереву:
   - заголовок есть и blob каждого файла `sources` на текущем коммите
     `refs/heads/<base>` клона совпадает с записанным — `ok`;
   - blob хоть одного файла отличается или файла в дереве нет — `warn`
     «конвенции проекта изменились с последнего разбора: <файлы>» с
     перечнем всех таких файлов;
   - `conventions.md` есть, заголовка нет — `warn` «нет отметки разбора»
     с путём файла и командой требования 7;
   - заголовок сломан (в том числе сломанные `sources` и `base_branch`) —
     `warn` «заголовок отметки не читается» с путём файла;
   - `conventions.md` нет — `warn` с путём файла и подсказкой шага разбора
     (ссылка на `docs/target-onboarding.md`);
   - `conventions.md` не читается (не обычный файл, в том числе символьная
     ссылка, — «не обычный файл»; не UTF-8; ошибка ОС), клон не читается
     или базовая ветка не читается — `warn` с причиной; проверка не падает
     исключением.
   Проверка `conventions.md` не меняет и сетевых git-вызовов (`fetch`,
   `ls-remote`, `push`) не делает (решение гейта 4); у
   `config.DEFAULT_TARGET` строки нет.
9. **Порядок подключения** — новый документ `docs/target-onboarding.md`:
   шаг разбора ИИ-настроек проекта как текста; что выбирается (стек,
   архитектура и слои, стиль кода, команды тестов и линтеров, миграции,
   именование); что отбрасывается (команды запуска обвязки, правила
   commit/push, роли, ревью, хуки, MCP, разрешения); куда пишется итог
   (`.artel/projects/<имя>/conventions.md`, смотрит Оператор); как ставится
   отметка (команда требования 7); что делать при предупреждении дрейфа
   (`doctor`, требование 8). Только описание порядка, без данных конкретных
   проектов.
10. **Миссии ролей** (следствие требования 1): строки миссий analyst и
    developer задачи внешнего проекта (`orchestrator/role_prompt.py:53`,
    `:121`) не называют «CLAUDE.md и AGENTS.md его базовой ветки» источником
    конвенций; они называют конвенции проекта из файла пульта. Фраза
    «конвенции проекта» в миссии developer сохраняется.
11. **Обвязка проекта не идёт в бриф через `knowledge`.** Список обвязки —
    действующий список обвязки проекта задачи 01M5T19041XE2KB6A52F0AT0NF
    (её требование 4: константа `config.AGENT_WRAPPER_MARKERS` —
    `CLAUDE.md` и `AGENTS.md` на любой глубине, каталог обвязки агента на
    любой глубине, `.mcp.json`, — затем элементы `policy.agent_wrapper`
    записи); покрытие пути — формулой `config.is_protected_path` с этим
    списком (с записью `**/<каталог>/` той же задачи). Значения списка здесь
    не повторяются литералом — читаются из константы и записи.
    - Элемент `knowledge` (файл или каталог), путь которого после
      нормализации (`./CLAUDE.md` → `CLAUDE.md`) покрыт списком, не
      читается и не показывается; на его месте — строка «документы
      knowledge: <элемент> — путь обвязки, пропущен» (решение гейта 5).
      Такой путь в «показанные» не заносится.
    - Листинг элемента-каталога (в том числе `./`, `docs/`, `frontend/`)
      пропускает покрытые списком файлы до отбора по
      `KNOWLEDGE_DIR_MAX_FILES`: их текст не читается и не показывается,
      в нумерацию «документ k из n» и в предел они не входят. N — число
      файлов, пропущенных фильтром обвязки в одном этом элементе-каталоге
      (решение гейта 5); у каждого элемента, где N > 0, — своя строка
      «документы knowledge: каталог <элемент> — пропущено файлов обвязки:
      N»; имён пропущенных файлов вне границы недоверенных данных нет
      (требование 7 SPEC 01M5ENWB2XHZFRNQ3Q3PZSAH2T).

## Критерии приёмки
Песочница — учебный внешний проект (клон в области проектов песочницы)
с `CLAUDE.md` «ПРАВИЛО-ПРОЕКТА» и `AGENTS.md` «ПРАВИЛО-АГЕНТА» в базовой
ветке и в рабочей копии и с `conventions.md` «КОНВЕНЦИЯ-ПУЛЬТА» под
заголовком отметки в области проектов песочницы
(`repo_context.projects_root() / <проект>`). «Пять точек» ниже — бриф
analyst, developer, spec_auditor, добавка test_author и пакет ревьювера.

AC-1. Во всех пяти точках задачи песочного проекта есть «КОНВЕНЦИЯ-ПУЛЬТА»
одним компонентом с подписью `conventions.md
(.artel/projects/<проект>/conventions.md)`; у developer, spec_auditor и в
пакете ревьювера компонент несёт опись (размер, sha256), у analyst и
test_author — без описи; нет ни «ПРАВИЛО-ПРОЕКТА», ни «ПРАВИЛО-АГЕНТА», ни
значений `base_sha` и blob из заголовка, ни строки `conventions_stamp`; у
записи с `knowledge` компонента (элемент — нейтральный файл вне обвязки)
текст элемента `knowledge` стоит после «КОНВЕНЦИЯ-ПУЛЬТА» (требования 1–3).

AC-2. Отдельно для каждого случая: `conventions.md` нет; `conventions.md` —
каталог; `conventions.md` — символьная ссылка (решение гейта 3); текст не в
UTF-8; чтение `conventions.md` отвечает `OSError` (сбой внедрён подменой
чтения файла, решение гейта 10) — во всех пяти точках бриф собирается без
исключения, несёт строку «конвенции проекта не разобраны: <причина> —
.artel/projects/<проект>/conventions.md» с причиной своего случая («файла
нет», «не обычный файл» для каталога и символьной ссылки, «текст не в
UTF-8», текст ошибки ОС — не «файла нет»), не несёт «ПРАВИЛО-ПРОЕКТА»; в
журнале задачи — запись «бриф: конвенции проекта не разобраны» с той же
причиной; шаг роли стартует (`run` не отказывает по этой причине)
(требование 4).

AC-3. `conventions.md` со сломанным заголовком — отдельно: первая строка
`---` без закрывающей строки `---`; тело блока, на котором
`yamlmini.mapping` отвечает `YamlError`; `conventions_stamp` с `base_sha`
не из 40 шестнадцатеричных символов; `sources` — список, не отображение;
элемент `sources` без blob; `base_branch` пуст; `base_branch` не строка
(решение гейта 2) — во всех пяти точках бриф собирается, несёт строку
«конвенции проекта не разобраны: заголовок отметки не читается —
.artel/projects/<проект>/conventions.md», не несёт ни строк заголовка, ни
текста под ним; в журнале — запись «бриф: конвенции проекта не разобраны»
с этой причиной (требования 2, 4, 6).

AC-4. `conventions.md`, текст которого под заголовком крупнее
`config.CONTEXT_FILE_MAX_BYTES`, в брифе developer пропущен с той же
пометкой пропуска по размеру, что получал бы сейчас файл конвенций того
же размера. `conventions.md`, текст которого под заголовком не крупнее
предела, а вместе с заголовком — крупнее, в брифе developer показан
целиком, без пометки пропуска (требование 5).

AC-5. Запись песочного проекта с `policy.agent_wrapper: [harness/]` и
компонентом `knowledge: [CLAUDE.md, ./AGENTS.md, ./, docs/arch.md]`; в
базе — `CLAUDE.md`, `AGENTS.md`, `docs/AGENTS.md`, `sub/CLAUDE.md`,
`.claude/rules/r.md`, `harness/h.md`, `docs/arch.md`, `guide.md`, у каждого
свой уникальный текст, других `*.md` в базе нет (решение гейта 7). Во
всех пяти точках: тексты `docs/arch.md` и `guide.md` есть, текстов
остальных шести файлов нет; строки «документы knowledge: CLAUDE.md — путь
обвязки, пропущен» и то же для `./AGENTS.md` есть; строка «документы
knowledge: каталог ./ — пропущено файлов обвязки: 6» есть; нумерация
кусков каталога `./` — «из 2» (требование 11).

AC-6. Бриф analyst, developer, spec_auditor, добавка test_author и пакет
ревьювера задачи артели (`config.DEFAULT_TARGET`) побайтно равны эталону,
снятому с текущего кода main при том же `run_id` (требование «бриф ролей
артели не меняется»).

AC-7. Миссии analyst и developer задачи песочного проекта не содержат
«CLAUDE.md и AGENTS.md»; миссия developer содержит «конвенции проекта»;
строки «CLAUDE.md и AGENTS.md его базовой ветки» в тексте
`orchestrator/role_prompt.py` нет (решение гейта 6; требование 10).

AC-8. В клоне песочницы `HEAD` стоит на другой ветке, где `AGENTS.md` и
`CLAUDE.md` другие, чем на `refs/heads/<base>`, а рабочее дерево клона
несёт незакоммиченную правку `AGENTS.md`. `conventions-stamp <проект>
AGENTS.md CLAUDE.md`: в начале `conventions.md` заголовок требования 6 с
`base_branch` записи, `base_sha`, равным `git rev-parse refs/heads/<base>`
клона, и blob каждого файла, равным `git rev-parse <base_sha>:<файл>` (не
blob `HEAD` и не `git hash-object` файла рабочего дерева); текст под
заголовком побайтно равен прежнему телу файла. После нового коммита в базу
повторная команда заменяет заголовок на новый `base_sha`, тело то же; файл
без заголовка получает заголовок, тело то же (требования 6, 7).

AC-9. `conventions-stamp` отказывает с ненулевым кодом и причиной, не
меняя `conventions.md` (побайтно), для: проекта `config.DEFAULT_TARGET`;
неизвестного проекта; клона, путь которого не существует; клона без
`refs/heads/<base>`; вызова без файлов; файла, которого нет в дереве
коммита базы; пути, который в дереве коммита базы — каталог;
отсутствующего `conventions.md`; `conventions.md` со сломанным заголовком —
отдельно: первая строка `---` без закрывающей; `sources` — список;
элемент `sources` без blob; `base_branch` пуст; `base_branch` не строка
(решение гейта 2; требование 7).

AC-10. Клон песочницы в состоянии AC-8 (`HEAD` на другой ветке, правка
рабочего дерева). После `conventions-stamp <проект> AGENTS.md CLAUDE.md`
строка `project-conventions` проекта в `doctor` — `ok`; новый коммит в
ветку `HEAD` (не базу), меняющий `AGENTS.md`, и новая правка `AGENTS.md`
в рабочем дереве — по-прежнему `ok`; новый коммит в базовую ветку
песочницы, меняющий `AGENTS.md`, — `warn` с «конвенции проекта изменились
с последнего разбора» и `AGENTS.md`; вместо этого коммит в базу, меняющий
другой файл (не из `sources`), — `ok`; коммит в базу, удаляющий
`CLAUDE.md`, — `warn` с `CLAUDE.md`. `conventions.md` после каждого
прогона `doctor` побайтно прежний (требование 8).

AC-11. `doctor` для внешнего проекта: `conventions.md` без заголовка —
`warn` с «нет отметки разбора»; со сломанным заголовком — отдельно для
случаев AC-3 (в том числе `sources` — список, элемент без blob,
`base_branch` пуст и не строка; решение гейта 2) — `warn` с «заголовок
отметки не читается»; без `conventions.md` — `warn` со ссылкой на
`docs/target-onboarding.md`; `conventions.md` — каталог, и отдельно —
символьная ссылка (решение гейта 3), и отдельно — текст не в UTF-8 —
`warn` с причиной своего случая; путь клона не существует — `warn` с
причиной; `refs/heads/<base>` в клоне нет — `warn` с причиной; ни в одном
случае `doctor` не падает исключением. Для `config.DEFAULT_TARGET` строки
`project-conventions` нет (требование 8).

AC-12. `docs/target-onboarding.md` существует и содержит: шаг разбора
ИИ-настроек проекта как текста; каждое из выбираемых и каждое из
отбрасываемых требования 9; путь `.artel/projects/<имя>/conventions.md`;
команду `conventions-stamp`; действие при предупреждении дрейфа `doctor`
(требование 9).

AC-13. При запрещённых сетевых git-вызовах (`fetch`, `ls-remote`, `push`) и
сокетах — по образцу `NoNetworkTest` пакета ревьювера — `conventions-stamp
<проект> AGENTS.md CLAUDE.md` пишет заголовок AC-8, а проверка
`project-conventions` в `doctor` даёт `ok` и `warn` сценариев AC-10; ни
одного сетевого git-вызова и ни одного сокета за прогон не открыто
(решение гейта 4; требования 7, 8).

AC-14. Запись песочного проекта убрана из `targets.yaml` (контекст проекта
не разрешается), `conventions.md` в области проекта читается: во всех
пяти точках бриф собирается, несёт строку «конвенции проекта не прочитаны:
<причина> — <где>» с непустой причиной и текст «КОНВЕНЦИЯ-ПУЛЬТА»; в
журнале задачи у каждой роли — запись «бриф: конвенции проекта не
прочитаны»; шаг роли стартует (решение гейта 9; требование 3).

## Затрагиваемые существующие тесты
Требования 1, 3, 4 и 11 противоречат долгоживущим тестам, закрепляющим
чтение `CLAUDE.md`/`AGENTS.md` базы проекта в бриф — блоком конвенций и
через `knowledge`. Раздел «Меняемое поведение» неприменим: правка меняет
фикстуры, источник и эталоны-константы модуля, а не скалярный литерал
утверждения. Мандат Оператора дан строкой `ANSWER-1.md` («Ослабление тестов
разрешено» на три файла ниже) и действует ровно в объёме этого раздела с
условиями У1–У4 и столбцом «Решение» матрицы; удаление утверждений, `skip`,
ослабление вида утверждения (`assertEqual` → `assertIn`, порог `>= 2` →
`>= 1`) не разрешены. Метод вне перечня краснеет — эскалация, не правка.
Разработчик подтверждает перечень прогоном и сообщает в PLAN о каждом
расхождении.

Помощники `ExternalBriefSandbox.prepare`, `fail_claude_reads`,
`assert_reason_journaled`, `unread_reasons` (файл external_brief) и
`ExternalReviewSandbox.prepare`
(`tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py:118` — кладёт
`conventions.md` пульта и запись `components:` с элементом `knowledge` для
У1) правятся только в объёме перечисленных методов;
`assert_reason_journaled` и `unread_reasons` получают параметр «какая
пометка» («не прочитаны» / «не разобраны»).

`tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`:
- `ProjectConventionsInBriefTest` (:335) — `test_ac2_…`, `test_ac3_…`,
  `test_ac4_…`, `test_ac5_…`: фикстура кладёт уникальный текст в
  `conventions.md` пульта вместо `CLAUDE.md` базы; ДОБАВЛЯЕТСЯ утверждение
  «текста `CLAUDE.md` базы нет»; прежние утверждения («текст есть, карты и
  `CLAUDE.md` пульта нет») не меняются и не удаляются (У3).
- `BothConventionFilesTest::test_ac6_both_files_from_base_branch_as_separate_components`
  (:398) — свойства «у developer и spec_auditor компонент конвенций — с
  описью (размер, sha256), у analyst и test_author — без описи; подпись
  называет файл» переезжают на компонент `conventions.md` и проверяются
  утверждениями того же вида; добавляется «текстов `CLAUDE.md`/`AGENTS.md`
  базы и рабочей копии в брифе нет» (У4).
- `AbsentFileMarkTest::test_ac7_…` (:479), `test_ac8_…` (:493) — пометка
  «конвенции проекта не разобраны: файла нет —
  .artel/projects/<проект>/conventions.md» у каждой роли, вид утверждений
  прежний.
- `UnreadConventionsTest::test_ac9_…` (:538, `drop_project_entry`) —
  контекст проекта не разрешён: утверждения о пометке «не прочитаны» с
  причиной и о записи журнала сохраняются (требование 3, решение гейта 9,
  AC-14).
- `UnreadConventionsTest::test_ac10_…` (:554) — сбой ОС при чтении
  `conventions.md` внедряется подменой чтения файла (`mock.patch` на
  функцию чтения в `brief`/`conventions`, бросающую `OSError`), не
  `fail_claude_reads` (тот подменяет только вызовы git); ожидание «не
  разобраны: <текст ошибки ОС>», не «файла нет», и запись журнала (решение
  гейта 10). Случаи «не UTF-8» и «не обычный файл» — отдельными
  критериями AC-2.
- `PultMapUntouchedTest` (:579), `ExternalMissionsTest` (:642) — только
  фикстура (`conventions.md` вместо `CLAUDE.md`), утверждения не трогаются
  (У3).

`tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`:
- `ProjectConventionsInPackageTest::test_ac1_…` (:195) — проверяет один
  компонент `conventions.md` вместо цикла по двум файлам, утверждения на
  компонент («внутри границ», «заголовок с размером и sha256») — того же
  вида; `test_ac2_…` (:212) — источник `conventions.md`, свойства те же.
- `ConventionMarksInPackageTest::test_ac3_…` (:258) — пометка «не
  разобраны: файла нет»; `test_ac4_…` (:278, удалённая база) — элемент
  `knowledge` в фикстуре, пометка «не прочитаны» с причиной сохраняется
  (У1); `test_ac5_…` (:300, не UTF-8) — то же для `conventions.md`, пометка
  с причиной тем же видом.
- `NoNetworkTest::test_ac8_package_builds_without_network` (:528) —
  фикстура сохраняет элемент `knowledge`, читаемый из базы клона, и тест
  ДОБАВЛЯЕТ утверждение «текст элемента `knowledge` есть в пакете»;
  утверждения запрета сетевых git-вызовов и сокетов не меняются (У1).

`tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py`:
- фикстура `KnowledgeSandbox.prepare` (:245) кладёт `conventions.md` пульта:
  без него строка «… не разобраны: файла нет …» содержит `ABSENT_MARK` и
  краснеют утверждения «пометок нет» (`CyrillicNamesTest::test_ac7_…`,
  :940; утверждения не трогаются).
- константы `ETALON_JOURNAL`/`ETALON_MANIFEST`/`ETALON_REVIEW`/`ETALONS`
  (:114–160) и методы на них: `ElementFileTest::test_ac1_…` (:456),
  `EtalonTest::test_ac9_…` (оба, :1020, :1033), `OldOutputKeptTest::test_ac10_…`
  (:1070, :1083, :1094, :1103, :1115) — новые эталоны записываются в тесте
  явным текстом (литералами), не вычисляются из кода пульта; побайтное
  сравнение сохраняется; формат компонента — требование 1 (решение гейта
  8). Дифф эталонов: исчезают только куски `CLAUDE.md`/`AGENTS.md` и их
  пометки, появляется ровно компонент `conventions.md` в формате
  требования 1, прочие байты эталона не меняются — ревью сверяет
  построчно (У2). `OldOutputKeptTest::test_ac10_artel_brief_has_no_knowledge`
  (:1127) не меняется.
- `RepeatsAndMarksTest::test_ac6_shown_paths_not_repeated` (:767) —
  `CLAUDE.md` в фикстуре и в элементах заменяется нейтральным файлом корня
  (`./<имя>.md`, `<имя>.md`); утверждения «текст нейтрального файла и
  `docs/<a>.md` — по одному разу», «кусок каталога — только `docs/<b>.md`,
  документ 1 из 1», «второго заголовка `knowledge` у файла корня нет»
  сохраняются тем же видом.
- `RepeatsAndMarksTest::test_ac6_size_skip_in_render_counts_as_shown`
  (:794) — крупный нейтральный файл корня, `knowledge: [<имя>.md,
  ./<имя>.md]`; `assertEqual(len(headers), 1)` сохраняется.
- `RepeatsAndMarksTest::test_ac6_marked_paths_not_counted_as_shown`
  (:815) — по два элемента `knowledge` на один путь: `[<нет>.md,
  ./<нет>.md, <не-UTF-8>.md, ./<не-UTF-8>.md]` (нейтральные пути вне
  обвязки); порог `>= 2` и вид `assertGreaterEqual` не меняются.
- `UnreadBaseTest::test_ac8_unread_base_single_mark_lists_knowledge`
  (:980) — перечень пометки теряет `PROJECT_CONVENTIONS` (механизм
  удаляется): проверяются оба элемента `knowledge`; «ровно одна строка «не
  прочитаны»» и «кусков `knowledge` нет» сохраняются тем же видом.
- `ConsumersTest::test_ac11_reviewer_package_knowledge_after_conventions_in_order`
  (:1200) — порядок «`conventions.md`, элемент, каталог»; `order ==
  sorted(order)` сохраняется. `test_ac11_knowledge_in_four_role_briefs`
  (:1184) — только фикстура, если краснеет; утверждения не меняются.

Не меняются (ожидаемо зелёные; краснеют — эскалация):
`tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py` (песочница —
`KnowledgeSandbox`, элемент `frontend-guide.md` вне обвязки), прочие методы
трёх файлов выше.

### Матрица неослабления (мандат ANSWER-1, прошла независимую проверку)

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py — `ProjectConventionsInBriefTest` | блок конвенций проекта есть в брифе каждой роли, карты и `CLAUDE.md` пульта нет — tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:335 | остаётся, источник — `conventions.md`; добавляется «текста `CLAUDE.md` базы нет» | tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:335 | ок при условии: У3 — прежние утверждения не меняются, только добавляются |
| tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py — `BothConventionFilesTest` | компонент конвенций у каждой роли: опись (размер, sha256) у developer и spec_auditor, без описи у analyst и test_author, подпись называет файл — tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:398 | остаётся, переезжает на компонент `conventions.md` (правило 2); два отдельных файла базы уходят вместе с механизмом | tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:398 | ок при условии: У4 — утверждения описи и подписи тем же видом, плюс «текстов `CLAUDE.md`/`AGENTS.md` нет» |
| tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py — `UnreadConventionsTest::test_ac9`, сценарий «контекст проекта не разрешён» | запись проекта не загружается — пометка «не прочитаны» и журнал — tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:538 | остаётся: пометка «конвенции проекта не прочитаны: <причина> — <где>» и журнал (решение гейта 9) | tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:538 | ок при условии: решение 9 исполнено; утверждения о пометке и журнале не удаляются |
| tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py — `UnreadConventionsTest::test_ac10` | сбой чтения ОС — пометка с причиной, не «файла нет» — tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:554 | остаётся для `conventions.md` (решение гейта 10) | tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:554 | ок при условии: решение 10 исполнено, AC-2 дополнен |
| tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py — `ConventionMarksInPackageTest::test_ac4`, `test_ac5` | удалённая база — пометка «не прочитаны»; не UTF-8 — пометка с причиной — tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py:278 | остаётся: `test_ac4` — с элементом `knowledge` (У1), `test_ac5` — для `conventions.md` | tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py:278 | ок при условии: У1; пометки с причиной тем же видом |
| tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py — `AbsentFileMarkTest` | отсутствие файла конвенций помечено у каждой роли, не молчит — tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:479 | остаётся: пометка «не разобраны: файла нет — <путь>» | tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:479 | ок при условии: пометка у каждой роли, вид утверждений прежний |
| tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py — `UnreadConventionsTest` | сбой чтения — пометка с причиной и запись журнала, не «файла нет», шаг не падает — tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:538 | остаётся для базы (через `knowledge`) и для `conventions.md` (:554) | tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:538 | ок при условии: оба случая сохранены, причина различается |
| tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py — `PultMapUntouchedTest`, `ExternalMissionsTest` | карта пульта не в брифе; миссии внешнего проекта — tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:579 | остаётся, утверждения не меняются | tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:579 | ок при условии: У3 — только фикстура |
| tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py — `ProjectConventionsInPackageTest`, `ConventionMarksInPackageTest` | конвенции в пакете ревьювера внутри границ с описью (размер, sha256); пометки «файла нет»/«не прочитаны» — tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py:195 | остаётся, источник — `conventions.md` | tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py:195 | ок при условии: границы, опись и пометки тем же видом |
| tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py — `NoNetworkTest::test_ac8_package_builds_without_network` | сборка пакета ревьювера без сетевых git-вызовов и сокетов — tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py:528 | остаётся, если сборка по-прежнему читает базу клона | tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py:528 | ок при условии: У1 — элемент `knowledge` в фикстуре, запрет сети не меняется |
| tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py — эталоны и методы на них | побайтный эталон прежнего вывода и порядок `knowledge` после конвенций — tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:456 | остаётся, эталон новый, явным текстом, формат компонента — решение гейта 8 | tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:456 | ок при условии: У2 — литералы, побайтное сравнение, построчная сверка диффа эталонов на ревью |
| tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py — `RepeatsAndMarksTest::test_ac6_shown_paths_not_repeated` | повтор пути между элементами убран, `./<путь>` сведён к пути, каталог не повторяет файл — tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:767 | остаётся на нейтральном файле корня; `CLAUDE.md` в `knowledge` теперь закрыт фильтром обвязки | tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:767 | ок при условии: те же три утверждения тем же видом |
| tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py — `RepeatsAndMarksTest::test_ac6_size_skip_in_render_counts_as_shown` | пропуск по размеру считается показанным, второго куска нет — tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:794 | остаётся между двумя элементами на один крупный путь | tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:794 | ок при условии: `assertEqual(len(headers), 1)` сохранён |
| tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py — `RepeatsAndMarksTest::test_ac6_marked_paths_not_counted_as_shown` | помеченный путь не считается показанным, не меньше двух пометок — tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:815 | остаётся: две пометки от двух элементов на один путь | tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:815 | ок при условии: порог `>= 2` и `assertGreaterEqual` не меняются |
| tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py — `UnreadBaseTest::test_ac8_unread_base_single_mark_lists_knowledge` | нечитаемая база — ровно одна пометка со всеми элементами, кусков нет — tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:980 | остаётся для элементов `knowledge`; файлы `PROJECT_CONVENTIONS` уходят из перечня вместе с механизмом | tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:980 | ок при условии: «ровно одна строка» и «оба элемента в ней» сохранены |
| tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py — `ConsumersTest` | порядок заголовков: конвенции раньше `knowledge` — tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:1200 | остаётся: `conventions.md`, затем элементы | tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:1200 | ок при условии: `order == sorted(order)` сохранено |
| tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py — фикстура `KnowledgeSandbox.prepare` | «пометок нет» в брифе без сбоев — tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:940 | остаётся, фикстура кладёт `conventions.md` | tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:940 | ок при условии: только фикстура, утверждения без правки |
| tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py — `ConsumersTest::test_ac11_knowledge_in_four_role_briefs` | `knowledge` есть в брифе четырёх ролей — tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:1184 | остаётся, утверждения не меняются | tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:1184 | ок при условии: только фикстура, если краснеет |

## Оценка объёма и деление
Сработавшие сигналы: файлов зоны 9 (порог 5); критериев приёмки 14
(порог 10); `budget_usd` ≥ $30.

Решение гейта SPEC 25.10.2026 (возврат 1, п. 5) — монолит, `budget_usd` 60.
Материал к решению: требования 1–6 и 11 (бриф) и 6–8 (команда, `doctor`)
опираются на один формат заголовка требования 6 и одну трактовку его трёх
видов, в том числе сломанного (бриф, `doctor` и команда отвечают на него
согласованно — AC-3, AC-9, AC-11); раздельная поставка отдала бы бриф с
трактовкой заголовка, которую не проверяет ни одна сверка, а мандат на
правку тестов привязан к этой задаче. По калибровке
(`BUDGET_CALIBRATION_TABLE`) класс «8 и более файлов» — ~$85; `budget_usd` 60
— по решению гейта, ниже калибровки. Возврат 2 добавил критерии AC-13,
AC-14 и случаи в AC-2, AC-3, AC-9, AC-11 без новых файлов кода, кроме
чтения `repo_context.projects_root()`.

## Обоснование зависимостей мержа
- `01M5T19041XE2KB6A52F0AT0NF` («ИИ-настройки внешнего проекта — полем
  записи, вне рабочей копии роли»): ТЗ — «Порядок мержа: после задачи …,
  если зоны пересекаются по `orchestrator/doctor/`». Строка ТЗ не формата
  «Порядок:», заявленным значением не стала. Основания: (1) зоны
  пересекаются — эта задача регистрирует новую проверку в
  `orchestrator/doctor/__init__.py` и `orchestrator/doctor/cli.py`, та
  задача меняет те же файлы (её SPEC, `zones:`); (2) требование 11 читает
  список обвязки из её константы `config.AGENT_WRAPPER_MARKERS` и поля
  `policy.agent_wrapper` и сверяет путь её формулой `**/<каталог>/` в
  `config.is_protected_path` — до её мержа этого кода в main нет. Решение
  гейта SPEC 25.10 (п. 1): `merge_after` на неё сохраняется для всей задачи.

## Не входит
- Сам разбор ИИ-настроек конкретных проектов и файлы `conventions.md`
  sled/feedback — делает сессия при Операторе.
- Исключение обвязки из рабочей копии роли, `no_paths` и отказ загрузки
  записи по `knowledge` — задача 01M5T19041XE2KB6A52F0AT0NF; константа
  `config.AGENT_WRAPPER_MARKERS`, поле `agent_wrapper` и формула
  `**/<каталог>/` — её, здесь только читаются.
- MCP ролей.
- Автоматическое изменение `conventions.md` (ни бриф, ни `doctor` его не
  пишут; пишет только команда отметки и только заголовок).
- Правка `orchestrator/targets.py`, `orchestrator/reference_cache.py`,
  `orchestrator/workspace.py`, `orchestrator/config.py`,
  `docs/adr/0003-target-projects.md` — только чтение по ТЗ.
- Правка `orchestrator/repo_context.py`: в зонах по решению гейта 1 только
  ради чтения `repo_context.projects_root()`, сам файл не меняется.
- Правка `orchestrator/review.py` (пакет ревьювера получает новый блок
  через `brief._project_conventions_parts` со своим `render`) и
  `orchestrator/yamlmini.py` (заголовок разбирается имеющимся разбором) —
  только чтение.
- Правка существующих тестов сверх раздела «Затрагиваемые существующие
  тесты» и сверх мандата `ANSWER-1.md`.
- Полный зелёный набор `tests/` и зелёный CI ветки — их держит пульт.
- Пути обвязки проекта и пульта: `.claude/`, `.claude/rules/r.md`,
  `.mcp.json`, `CLAUDE.md`, `AGENTS.md` (корень и любая глубина) — данные
  песочницы тестов и предмет фильтра требования 11, не зоны задачи;
  каталог `.claude/` пульта и его курируемый слой роли эта задача не
  трогает.
- Пути песочного и подключаемых проектов в требованиях и критериях
  (`./`, `./AGENTS.md`, `./CLAUDE.md`, `docs/`, `docs/AGENTS.md`,
  `frontend/`, `sub/`, `sub/CLAUDE.md`, `harness/`, `harness/h.md`,
  `docs/arch.md`, `guide.md`) — элементы `knowledge` и данные тестов, не
  зоны задачи.

## Материалы
- ТЗ: `tasks/01M5T18K1YFBYA7MM1BBRV869A/TZ.md`; бэклог П1 — `docs/backlog.md:370`.
- `tasks/01M5T18K1YFBYA7MM1BBRV869A/ANSWER-1.md` — мандат на три файла
  тестов, условия У1–У4, решения гейта 1–11, матрица неослабления.
- SPEC-AUDIT итераций 1–2 (О1–О3, П1–П4, М1, М2, Н1, Ф1) и причины
  возврата гейта SPEC 25.10.2026.
- SPEC 01M5634E094QF7JX8HD3KSG4KN (блок конвенций), 01M56G7SB1PSR277BN4CHJBCQC
  (пакет ревьювера), 01M5ENWB2XHZFRNQ3Q3PZSAH2T (`knowledge`);
  SPEC и ANSWER-2 задачи 01M5T19041XE2KB6A52F0AT0NF (список обвязки,
  требования 1–4; передача канала `knowledge`, ответы 1 и 5).
- Разбор `base` клона без сети — `orchestrator/reference_cache.py::branch_commit`
  (как в `_read_project_conventions`).
