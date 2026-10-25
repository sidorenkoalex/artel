---
task: 01M5T18K1YFBYA7MM1BBRV869A
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Конвенции внешнего проекта в брифе — из файла пульта, сверка дрейфа

## Подход
Один новый модуль `orchestrator/conventions.py` держит всё, что касается
файла пульта `.artel/projects/<имя>/conventions.md`: путь через
`repo_context.projects_root()` (решение гейта 1), чтение (`read_file`:
`lstat` → «файла нет» / «не обычный файл», `os.open(O_NOFOLLOW)` + `fstat`,
UTF-8, текст ошибки ОС), разбор заголовка отметки на три вида требования 6
(`parse`: `plain` / `broken` / `stamped`, тело блока — `yamlmini.mapping`),
текст для брифа без заголовка (`brief_text`), команду
`conventions-stamp` (`cmd_conventions_stamp`) и сверку дрейфа (`drift`).
Бриф, `doctor` и команда отвечают на сломанный заголовок одной функцией
`parse` — согласованность AC-3 / AC-9 / AC-11 держится устройством, а не
тремя копиями проверки.

Бриф (`brief._project_conventions_parts`): блок `PROJECT_CONVENTIONS` и
`_read_project_conventions` удалены; первым куском идёт компонент
`conventions.md` (`_pult_conventions_part`) через `render` потребителя —
опись и предел размера те же, что были у файла конвенций, и считаются по
тексту без заголовка (требования 1, 2, 5). Файл не годится — строка
«конвенции проекта не разобраны: <причина> — .artel/projects/<имя>/
conventions.md» и запись журнала «бриф: конвенции проекта не разобраны»
(требование 4). За ним — `knowledge` с базы клона, как раньше; база
читается только при наличии `knowledge`; контекст не разрешён — пометка
«не прочитаны» всегда (требование 3, решение гейта 9). Пакет ревьювера
получает то же через прежний вызов `brief._project_conventions_parts` —
`review.py` не меняется.

Фильтр обвязки в `knowledge` (требование 11): список —
`repo_context.wrapper_paths(ctx)` (константа `config.AGENT_WRAPPER_MARKERS`
и поле `agent_wrapper` записи задачи 01M5T19041XE2KB6A52F0AT0NF), формула —
`config.is_protected_path`. Элемент-путь обвязки — строка «путь обвязки,
пропущен»; листинг каталога отсекает обвязку до предела
`KNOWLEDGE_DIR_MAX_FILES`; N — только `*.md`, которые каталог показал бы
(ANSWER-2 п.2).

`doctor`: подмодуль `orchestrator/doctor/project_conventions.py` по правилу
фасада (коллаборант `conventions` — импортом в `doctor/__init__.py`),
строка `project-conventions-<проект>` в цикле по записям `cli.all_checks`,
у артели строки нет. Сверка — `ls-tree` коммита `refs/heads/<base>`
(`reference_cache.branch_commit`), сетевых git-вызовов нет (решение гейта 4).

Отказы `conventions-stamp` — требование 7 и решение гейта ANSWER-2 п.1:
артель, неизвестный проект, клона нет / не репозиторий git
(`rev-parse --show-toplevel` ≠ путь клона — каталог внутри чужого
репозитория клоном не считается), нет `refs/heads/<base>`, файлы не
названы, пути нет в дереве / каталог / символьная ссылка / подмодуль,
`conventions.md` нет / не обычный файл / не UTF-8 / ошибка ОС, сломанный
заголовок. Запись — временный файл рядом и `os.replace` с правами
прежнего файла; через символьную ссылку не пишется (её отсекает `lstat`).
Дополнительно: заголовок, который не разбирается обратно тем же
`parse` без искажения (имя ветки или путь с символами, ломающими
`yamlmini`), — отказ, а не запись битого заголовка.

Бюджет SPEC ($60) не пересматривается.

## Шаги
1. `orchestrator/conventions.py` — чтение, разбор, отметка, сверка; команда
   `conventions-stamp` в `orchestrator/artel.py` (справка, таблица команд;
   вне белого списка ролей — пишет файл).
2. `orchestrator/brief.py` — компонент `conventions.md`, удаление блока
   `PROJECT_CONVENTIONS`, фильтр обвязки в `_knowledge_parts` /
   `_knowledge_dir_parts`; миссии analyst/developer в
   `orchestrator/role_prompt.py` («файл пульта conventions.md»).
3. `orchestrator/doctor/project_conventions.py`, регистрация в
   `orchestrator/doctor/__init__.py` и `orchestrator/doctor/cli.py`.
4. `docs/target-onboarding.md` — порядок разбора, отметки, действия при
   дрейфе.
5. Тесты: правка трёх файлов по мандату ANSWER-1/ANSWER-2 (ниже), свой
   `tests/test_conventions.py`; регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 1, 2 |
| 3 | 2 |
| 4 | 1, 2 |
| 5 | 2 |
| 6 | 1 |
| 7 | 1 |
| 8 | 1, 3 |
| 9 | 4 |
| 10 | 2 |
| 11 | 2 |

Проверено прогоном: долгоживущие файлы задачи
`tests/test_01m5t18k1yfbya7mm1bbrv869a_conventions_brief.py` (18) и
`…_conventions_stamp.py` (34) — зелёные; планка `plank-run` — 24 passed
(AC-6 артели побайтно, AC-12); `tests/test_conventions.py` — 10 passed,
сторожа проверены временными мутациями (каждая красит свой тест);
соседние наборы (`role_missions`, `role_refusal`, `doctor`,
`doctor_components`, `doctor_layer`, `wrapper_doctor`, `help_registry`,
`importers`, `external_missions`, `codebase_map`, `role_outputs`) —
201 passed.

## Затрагиваемые существующие тесты — отчёт по мандату
Прогон до правки тестов подтвердил перечень SPEC: красными были ровно
методы, названные в разделе «Затрагиваемые существующие тесты» (плюс
`CyrillicNamesTest::test_ac7_…` и `RepeatsAndMarksTest::test_ac6_size_skip_…`,
названные там же); `tests/test_01m5jgsaanr1nzyqd4fcsve48y_role_outputs.py`
и прочие методы трёх файлов — зелёные без правки. Методы не удалялись и
не переименовывались.

- `external_brief`: фикстура `prepare` кладёт `conventions.md` пульта
  (параметры `pult_text`, `with_pult`, `knowledge`); `ProjectConventionsInBriefTest`
  — прежние утверждения на текст `conventions.md`, ДОБАВЛЕНО «текста
  `CLAUDE.md` базы нет» (У3); `BothConventionFilesTest` — опись/подпись
  на компоненте `conventions.md` тем же видом, «текстов `CLAUDE.md`/
  `AGENTS.md` базы и других версий нет» (У4), замена `assertNotEqual`
  на «строка заголовка ровно одна» (`assertEqual(…, 1)`) и
  `header == эта строка` (У6); `AbsentFileMarkTest` — пометка «не
  разобраны: файла нет — <путь>»; `UnreadConventionsTest::run_scenario` —
  элемент `knowledge` из базы и `conventions.md` (У5), перебор четырёх
  сценариев прежний; `test_ac10` — сбой ОС подменой `os.open` для пути
  файла, ожидание «не разобраны: <текст ошибки>», не «файла нет», журнал;
  помощник `assert_reason_journaled` получил параметр пометки.
  `PultMapUntouchedTest`, `ExternalMissionsTest` — без правки (фикстура
  уже кладёт файл пульта).
- `review_conventions`: `ExternalReviewSandbox.prepare` кладёт
  `conventions.md` и умеет компонент с `knowledge` (У1); `test_ac1` —
  один компонент `conventions.md` (границы, опись) + «текстов
  `CLAUDE.md`/`AGENTS.md` нет»; `test_ac2` — источник `conventions.md`,
  утверждения те же; `test_ac3` — «не разобраны: файла нет»; `test_ac4` —
  элемент `knowledge`, пометка «не прочитаны» с причиной; `test_ac5` —
  `conventions.md` не UTF-8, пометка «не разобраны» с причиной о файле;
  `NoNetworkTest` — ДОБАВЛЕНО «текст элемента `knowledge` есть в пакете»,
  запрет сети без изменений. `unread_reasons` получил параметр пометки.
- `knowledge_brief`: `KnowledgeSandbox.prepare` кладёт `conventions.md`
  (`ETALON_CLAUDE` у эталонных сценариев); `ETALON_JOURNAL`/
  `ETALON_MANIFEST`/`ETALON_REVIEW` переписаны литералами: из прежних
  исчезли кусок `CLAUDE.md` и пометка `AGENTS.md`, появился ровно
  компонент `conventions.md (.artel/projects/uchebnyetalon/conventions.md)`
  — размер 122 байт и sha256 те же (тот же текст); побайтное сравнение
  прежнее (У2). `test_ac6_shown_paths_not_repeated`,
  `test_ac6_marked_paths_not_counted_as_shown` — нейтральные пути вместо
  `CLAUDE.md`/`AGENTS.md`, порог `>= 2` прежний; `UnreadBaseTest` —
  перечень без `PROJECT_CONVENTIONS`; `ConsumersTest` — порядок
  «`conventions.md`, элемент, каталог».

Расхождения с буквой мандата (сообщаю по требованию SPEC; ревью — на
решение, правку вернуть не трудно):
1. `RepeatsAndMarksTest::test_ac6_shown_paths_not_repeated` — третье
   утверждение было `assertFalse(lines_with("CLAUDE.md (knowledge
   компонента"))`: у прежней фикстуры файл корня показывал блок конвенций,
   и куска `knowledge` у него не было вовсе. С нейтральным файлом корня
   его показывает сам `knowledge`, поэтому «второго заголовка нет»
   выражено `assertEqual(len(lines_with("### <файл> (knowledge
   компонента")), 1)` — строже прежнего, не слабее, но вид другой.
2. `RepeatsAndMarksTest::test_ac6_size_skip_in_render_counts_as_shown` —
   `assertEqual(len(headers), 1)` сохранён; второе утверждение
   `assertNotIn("knowledge компонента", headers[0])` при новой фикстуре
   (оба элемента — `knowledge`) невыполнимо по построению и заменено
   `assertIn("пропущен", headers[0])` — единственный заголовок и есть
   пропуск по размеру, вторым куском файл не выведен.

## Влияние на систему
- Задачи артели не меняются: развилка `is_artel_task` прежняя, AC-6
  планки сверяет пять точек артели побайтно с кодом базы.
- Роли внешнего проекта больше не получают `CLAUDE.md`/`AGENTS.md` проекта
  ни блоком конвенций, ни через `knowledge` — это и есть цель SPEC; до
  разбора проекта в `conventions.md` бриф несёт пометку «не разобраны:
  файла нет», шаг не останавливается.
- Гейты, лимиты, инварианты не трогаются; предел размера компонента —
  тот же `config.CONTEXT_FILE_MAX_BYTES` у тех же потребителей.
  `doctor` получает только `warn`-строки — `DOCTOR: ок`/код выхода не
  меняются (`fail` проверка не выдаёт).
- Новая команда `conventions-stamp` пишет файл локального слоя — вне белого
  списка ролей (`_ROLE_ALLOWED_COMMANDS` не тронут), процесс роли получит
  прежний отказ.
- Откат — revert merge-коммита: модуль, подмодуль `doctor` и документ
  удаляются, бриф возвращается к блоку `PROJECT_CONVENTIONS`; файлы
  `conventions.md` в `.artel/projects/` никто, кроме команды отметки, не
  пишет — откат их не трогает.
- `merge_after` 01M5T19041XE2KB6A52F0AT0NF уже в main (её код —
  `targets.wrapper_paths`, `repo_context.wrapper_paths` — используется).

## Риски
- Проект с `knowledge`, называющим корневые `CLAUDE.md`/`AGENTS.md`
  (их загрузка записи пропускает, `targets.KNOWLEDGE_WRAPPER_ALLOWED`),
  теперь получает в брифе строку «путь обвязки, пропущен» вместо текста —
  по требованию 11; Оператору стоит перенести нужное в `conventions.md`.
- Отметка ставится по локальной ссылке базы клона: отставший клон даст
  отметку по старой базе. Документ называет это явно.

## Предложения системе
- Шелл роли без `ls`/`cat` и с лимитом длины команды: длинные heredoc
  отказывают («Parser aborted»), правку больших файлов приходится дробить
  на десятки Edit — стоит упомянуть в скиле разработчика.
- Мандат «утверждения тем же видом» плохо переносит смену фикстуры, при
  которой прежнее утверждение становится невыполнимым по построению
  (п. 2 расхождений): матрице неослабления полезна графа «утверждение
  невыполнимо при новой фикстуре — чем заменено».
