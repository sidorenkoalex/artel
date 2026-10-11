---
task: 01M4P4ZP37WV81410YTZHKQC8D
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: предпроверка выхода из tests_writing для роли (`artel.py preflight <id>`)

## Подход

Новый модуль `orchestrator/preflight.py` с командой `cmd_preflight(arg)`;
переход (`orchestrator/fsm.py`, `orchestrator/fsm_advance.py`,
`orchestrator/advance_gates/*`) не трогается — только читается.

- **Входы.** Черновик планки — `.py` файлы `acceptance_tests/` каталога
  документов (`artifact_branch.docs_dir`), отобранные перечнем
  `INPUT_FILTERS = (guard.is_extraneous_acceptance_test_file,)` — тот же
  фильтр, что у автокоммита; вложенные файлы и `_pult.py` отбрасываются.
  `SPEC.md` — с диска каталога документов. Долгоживущие файлы — обход
  `<рабочая копия>/<profile.long_lived_dir>` на диске с отбором
  `profile.is_long_lived`: незакоммиченные и неотслеживаемые видны, git не
  зовётся. Рабочей копии нет (`workspace.path(id, target)` без `ensure`) —
  одна строка «рабочей копии кода … нет — долгоживущих файлов нет».
- **Проверки** (требование 3) — ядра ветко-корректного пути перехода:
  профиль (`project_profile.decide`), трассируемость
  (`guard.scan_ac_content` по всем `.py` планки + по текстам долгоживущих,
  `guard.traceability_errors_from_content`), маркер
  (`guard.redness_marker_errors_from_files` по `test_*.py`), образец id
  (`guard.id_format_sample_errors` по всем `.py`), долгоживущие файлы
  (строка группы через `guard.plank_file_group` с текстом ошибки гейта, затем
  `guard.long_lived_errors_from_files`), строка группы
  (`guard.acceptance_test_files` по каталогу документов с тем же фильтром
  входа → `group_line_errors_from_files` + `long_lived_plank_errors` +
  `long_lived_errors_from_files`, состав и порядок
  `_tests_writing_test_groups_gate`). `network_addresses` —
  `repo_context.is_artel(target)`.
- **Метки** — формы перехода: `tasks/<id>/acceptance_tests/<файл>` для
  трассируемости/маркера/образца, `acceptance_tests/<файл>` (метка
  `guard.acceptance_test_files`) для строки группы, путь от корня рабочей
  копии для долгоживущих.
- **Вывод.** По каждой проверке заголовок «<проверка>: пройдена|отказ», под
  отказом — строки ошибок с отступом в два пробела; отказ не останавливает
  остальные проверки. Отказ профиля — `decision.refusal` и
  `project_profile.refusal_hint(id)` отдельными строками; долгоживущие и
  строка группы тогда — «не проверяется предпроверкой: профиль тестов
  проекта не разрешён»; `decide().skip` — «…: у проекта нет профиля тестов»,
  без `journal_skip`. В конце — перечень `NOT_CHECKED` (10 пунктов
  требования 6), строка на пункт; пункт «чтение со ссылки документов и путь
  с диска» называет `guard.scan_acceptance_tests`,
  `guard.acceptance_traceability_errors`, `guard.scan_redness_markers`,
  `guard.scan_id_format_samples` — так множество функций guard модуля без
  фильтров входа равно множеству трёх тел перехода (сторож требования 12).
- **БД** — `sqlite3.connect("<uri>?mode=ro", uri=True)` с
  `row_factory=sqlite3.Row`; строка задачи — `store.get_task` на этом
  соединении, его `SystemExit` перехватывается: то же сообщение, что у
  `show`, но код 2. Файла БД нет — код 2, файл не создаётся. Не
  `tests_writing` — код 2.
- **CLI.** `artel.py`: строка таблицы диспетчера `preflight`, имя в
  `_ROLE_ALLOWED_COMMANDS`, строка в справке модулей.
- **Скил** — приложение PLAN к `skills/test-authoring.md` (защищённый путь),
  абзац в «Перед завершением».

`budget_usd` SPEC (45) не переоцениваю.

## Шаги

1. `orchestrator/preflight.py`, подключение в `orchestrator/artel.py`,
   регенерация `docs/codebase-map.md`, юнит-тесты `tests/test_preflight.py`;
   приложение к `skills/test-authoring.md` (ниже). Сделано в этом шаге.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (команда, заголовки, все отказы) | 1 — `cmd_preflight`, `_report` |
| 2 (входы, перечень фильтров входа) | 1 — `INPUT_FILTERS`, `_plank_py_files`, `_long_lived_files` |
| 3 (ядра проверок, `is_artel`) | 1 — `_traceability`, `_long_lived`, `_groups` |
| 4 (тексты и метки ошибок) | 1 — `_plank_label`, метки `acceptance_test_files`, путь от корня копии |
| 5 (профиль: refusal/skip) | 1 — ветки `decision.refusal`/`profile is None` |
| 6 (перечень «не проверяется») | 1 — `NOT_CHECKED` |
| 7 (только чтение) | 1 — нет lease/журнала/git-записи/`ensure`/выкладки |
| 8 (коды выхода 0/1/2, сообщения как у `show`) | 1 — `_task_row`, проверка состояния |
| 9 (БД `mode=ro`) | 1 — `_open_db_readonly` |
| 10 (`_ROLE_ALLOWED_COMMANDS`) | 1 — `orchestrator/artel.py` |
| 11 (приложение к скилу) | 1 — раздел «Приложение» ниже |
| 12 (сторож) | долгоживущий файл задачи `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py` (не правился); модуль устроен под его сверку |

## Влияние на систему

- Переход, гейты, guard, лок планки, зоны — не меняются: модуль только
  читает и вызывает публичные ядра guard. Новая команда в белом списке ролей
  — только чтение (`mode=ro`, без `store.db()`), состояния пульта не меняет;
  этого держит долгоживущий сторож задачи (заглушки на `store.journal`,
  git commit/push, `workspace.ensure`, выкладку планки; побайтная сверка
  файла БД; файл БД 0444).
- Расхождение предпроверки с переходом в будущем (новый вызов guard в
  телах перехода) ловит двусторонний сторож требования 12.
- Ни один тест, гейт, лимит не ослаблен; существующие тестовые методы не
  менялись.
- Откат — revert merge-коммита задачи; приложение к скилу Оператор не
  применяет / откатывает отдельно.

Проверено исполнением:
- `python3 -m pytest tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py
  tests/test_preflight.py` — 24 passed, 28 subtests passed.
- `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`,
  `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`,
  `tests/test_codebase_map.py`, `tests/test_invariants.py` — 130 passed.
- `artel.py suite-run 01M4P4ZP37WV81410YTZHKQC8D` №1 (полный набор,
  без приложений PLAN — PLAN ещё не в ссылке): «зелёный прогон», упало 0
  (сводка напечатала «прошло: 1» — счётчик сводки, не число тестов: по
  логу ветки выполнено больше 5000).
- Мутации своих тестов: `_task_row` через `store.db()` — краснеют
  `NoDatabaseTest` и AC-8 долгоживущего файла; непрочитанный SPEC.md как
  пустой текст — краснеет `MissingSpecTest`.
- Планка `plank-run` до записи PLAN: единственный тест
  (`test_ac8_skill_appendix.py`) красный по своему маркеру — PLAN.md ещё
  не в ссылке документов; приложение ниже проверено `git apply --check` на
  чистом дереве (см. «Риски»).

## Риски

- Приложение к `skills/test-authoring.md` снято `git diff` с временной
  правки чистого дерева (правка тут же откатена `git checkout`), проверено
  `git apply --check` на чистом дереве ветки — применяется.
- Предпроверка не видит проверок перечня `NOT_CHECKED` (дифф кодовой ветки,
  сухой сбор и т.д.): «пройдено» предпроверки не гарантирует прохода
  перехода — это сказано в выводе построчно.

## Приложение: правка skills/test-authoring.md

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
index fa6b2950..e43a9bbf 100644
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -413,6 +413,18 @@ T062, когда Оператор поднял потолок до 5 — main п
 Коммитить каталог в ветку задачи не нужно — автокоммит оркестратора сам
 перенесёт его в артефактную ветку (SPEC 01M1NKTF173WV5CPDZ1C3WW69K).
 
+Перед сдачей шага запусти предпроверку выхода из `tests_writing`:
+`artel.py preflight <id>` (полный путь к `artel.py` пульта называет
+миссия шага). Она судит по твоему черновику — планке каталога
+документов и долгоживущим файлам рабочей копии кода, в том числе
+незакоммиченным, — теми же проверками guard, что переход: трассируемость
+AC, маркер красноты, образец id задачи, строка группы, долгоживущие
+файлы. По каждой печатает «пройдена» или «отказ» со строками ошибок
+перехода; код выхода 1 — есть отказ: почини черновик до сдачи шага.
+Остальные проверки выхода она называет строками «не проверяется
+предпроверкой (проверит переход)». Команда только читает: журнал,
+ветки и рабочие копии не меняет (SPEC 01M4P4ZP37WV81410YTZHKQC8D).
+
 Прогоны — только в переднем плане с таймаутом (параметр `timeout`
 команды, до 10 минут), по одному файлу планки. Команда,
 которую клиент увёл в фон, результата шагу не даёт: не жди её и не
```

## Предложения системе

- `skills/coding-standards.md` велит прогонять `git apply --check
  <файл-с-диффом>`, но запись вне рабочего каталога и каталога документов
  шагу закрыта, а временный файл в рабочем каталоге пульт закоммитит:
  нужна команда пульта «проверить приложения PLAN на чистом дереве» (у
  планки задачи такой помощник есть — `_pult.apply_check`).
- `orchestrator/suite_run.py`: отчёт зелёного полного прогона напечатал
  «прошло: 1, упало: 0» при >5000 выполненных тестах по логу — счётчик
  сводки вводит в заблуждение (аномалия 11.10, прогон №1 этой задачи).
