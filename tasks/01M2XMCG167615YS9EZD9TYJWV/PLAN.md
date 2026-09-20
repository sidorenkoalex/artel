---
task: 01M2XMCG167615YS9EZD9TYJWV
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Команда doc-commit: документы и конфигурация Оператора коммитятся от origin/main механикой note

## Подход

Команда `doc-commit` живёт в том же модуле, что и `note`
(`orchestrator/notes.py`), и переиспользует его механику не копией, а
общими функциями: `_ensure_work_repo`, `_fetch_and_build`,
`_commit_and_push`, `_run` (повторы non-fast-forward, окно тишины,
удержание), `_attempt`/`_flush_pending`. Новый вид удержанной записи —
тот же JSON в `.artel/notes-pending/` с полем `kind: "doc-commit"` и
полями `path`/`content`/`message`: запись самодостаточна, `--flush`
воспроизводит коммит от актуального `origin/main` без обращения к
исходному `--from`-файлу (тот может уже не существовать).

Ключевые решения:

- **Ветвление по `kind` — в двух точках, не по всему модулю.**
  `_fetch_and_build` после fetch/checkout для `doc-commit` зовёт
  `_build_doc_commit` (сверка базы + сравнение с origin), для прочих
  видов — прежний `_read_backlog` + `_build_for` (не тронуты).
  `_commit_and_push` пишет по `_target_rel(request)` (`docs/backlog.md`
  для note, `request["path"]` для doc-commit), сообщение коммита —
  `_commit_message` с новой веткой `doc-commit`. Журнал пульта для
  `doc-commit` не пишется (требование 7), для `note` — как прежде
  (требование 9: `tests/test_notes.py` не правятся).
- **Сверка базы (требование 5) — валидация внутри `_fetch_and_build`,
  ДО решения об окне тишины и удержании**, тем же местом, что отказы
  валидации `note`: сравниваются blob-sha `FETCH_HEAD:<путь>` рабочего
  репозитория и `HEAD:<путь>` главной копии (`git rev-parse --verify`),
  не декодированный текст — точная сверка без вопросов кодировки.
  Оба отсутствуют — новый файл, допустим. Отдельный отказ «содержимое
  уже совпадает с origin»: иначе `git commit` ничего не находит,
  три повтора проваливаются и запись зависает в pending без причины.
- **Рубеж окружения роли — первым действием `cmd_doc_commit`**, до
  разбора аргументов и до любого git (AC-9), тем же
  `runner.in_role_environment()`, что `answer`/`zones-extend`.
  Порядок отказов дальше: путь → `--message` → `--from` (чтение и
  декодирование UTF-8) → только затем `_run`. Все отказы — `sys.exit`
  до fetch: коммита и удержанной записи не появляется (AC-2/AC-3/AC-8).
- **Допустимые пути** (`_doc_commit_path_refusal`): нормализация
  `PurePosixPath` (отказ абсолютным, `..`, пустым, каталогу `docs/`),
  затем `docs/**` кроме `docs/backlog.md` (отдельный текст «для него
  `note`») либо ровно один из `DOC_COMMIT_CONFIG_PATHS =
  ("roles.yaml", "gates.yaml", "targets.yaml")`. Остальное — «код и
  артефакты меняются задачами, не doc-commit».
- **Содержимое** читается и пишется байтами (`read_bytes().decode`,
  `write_bytes`), не `read_text`/`write_text`: универсальные переводы
  строк не должны менять файл между `--from` и origin.
- **Вывод**: `_run` возвращает sha (для `note` результат по-прежнему
  игнорируется), `cmd_doc_commit` печатает путь и sha коммита в
  origin (требование 7). Тексты удержания/финального отказа
  параметризованы видом записи: у `note` — буквально прежние (их
  сверяет `test_ac3_hold_message_prefix_and_suffix`).
- `doc-commit --flush` без пути = безусловный `_flush_pending()` (оба
  вида, требование 8), с путём — флаш и затем сама запись, зеркально
  `note`. Оппортунистический допуш вне окна — тоже как у `note`.

Расхождения с оценкой SPEC нет: правятся ровно два модуля и один новый
тестовый файл; `budget_usd` не переоценивается.

## Шаги

1. `orchestrator/notes.py`: константы `DOC_COMMIT_KIND`,
   `DOC_COMMIT_CONFIG_PATHS`, `DOC_COMMIT_FOREIGN_REFUSAL`,
   `DOC_COMMIT_BASE_REFUSAL`; `_doc_commit_path_refusal`,
   `_doc_commit_prefix`, `_blob_sha`, `_build_doc_commit`,
   `_target_rel`, `_write_doc`; ветки `doc-commit` в `_fetch_and_build`,
   `_commit_and_push`, `_commit_message`; тексты удержания/отказа в
   `_run` по виду записи и возврат sha; `_parse_doc_commit_args`,
   `_read_source_file`, `cmd_doc_commit`. Докстринг модуля — абзац про
   `doc-commit`.
2. `orchestrator/artel.py`: запись `"doc-commit"` в таблице
   диспетчера, строка в справке команд и в описании модуля `notes`.
3. `tests/test_doc_commit.py`: стенд `DocCommitSandbox(RealGitSandbox)`
   с bare origin (docs/backlog.md, docs/roadmap.md, roles.yaml) и
   тесты AC-1..AC-9 плюс чистые тесты `_doc_commit_path_refusal`,
   `_commit_message`, `_target_rel`, и углы: CRLF байт-в-байт, отказ
   «содержимое уже совпадает», путь, появившийся в origin после пина,
   флаш без исходного `--from`-файла, дисциплина оппортунистического
   флаша под окном.
4. `python3 scripts/codebase_map.py` тем же коммитом (правка `*.py`).

Сделано одним коммитом `ed3b7854` в ветке задачи. Прогоны (передний
план, `-p no:cacheprovider -p timeout -o timeout=120`):

| Набор | Итог |
|---|---|
| `tasks/01M2XMCG167615YS9EZD9TYJWV/acceptance_tests/` | 13 passed |
| `tests/test_notes.py` + `tests/test_artel_role_restricted_commands.py` | 47 passed (без правок) |
| `tests/test_doc_commit.py` | 28 passed |
| `tests/test_doctor.py` + `tests/test_codebase_map.py` | 155 passed |

`scripts/guard.py` по PLAN.md/SPEC.md — ок; заявка мутации есть у всех
тестов нового файла (`guard.test_functions_without_mutation_claim` → []).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (команда, механика note, --flush) | 1, 2 |
| 2 (главная копия не трогается) | 1 (вся работа — в `.artel/notes-work`), тест AC-1 в 3 |
| 3 (допустимые пути, именованный отказ) | 1 (`_doc_commit_path_refusal`), 3 |
| 4 (отказ из окружения роли) | 1 (`cmd_doc_commit`, первая строка), 3 |
| 5 (сверка базы, новый файл допустим) | 1 (`_build_doc_commit`), 3 |
| 6 (сообщение коммита, --message обязателен) | 1 (`_commit_message`, `cmd_doc_commit`), 3 |
| 7 (без журнала, вывод sha) | 1 (`_commit_and_push`, `cmd_doc_commit`), 3 |
| 8 (общий pending, поле kind, flush обоих видов) | 1 (`_flush_pending` через `_fetch_and_build`), 3 |
| 9 (совместимость note) | 1 (ветвление по kind, тексты note прежние), прогон `tests/test_notes.py` |
| 10 (тесты) | 3 |

## Влияние на систему

- Затрагивается только `orchestrator/notes.py` и таблица диспетчера
  `artel.py`. Поведение `note` (пути, сообщения, журнал, формат
  pending) не меняется: новые ветки кода включаются только при
  `kind == "doc-commit"`; `tests/test_notes.py` остаются как есть и
  прогоняются.
- `doctor.check_pending_notes` (`orchestrator/doctor/misc_checks.py`)
  считает записи через `notes.pending_notes()` — увидит и удержанные
  doc-commit, совет «note --flush» остаётся верным (флаш отправляет оба
  вида). Модуль не правится (вне зон).
- Гейты/guard/лимиты не ослабляются. Новый рубеж (окружение роли)
  добавляется, не снимается. `PROTECTED_PATHS` не трогается:
  `doc-commit` даёт Оператору канал в `roles.yaml`/`gates.yaml`/
  `targets.yaml` мимо главной копии, но это и есть решение Оператора
  19.09 (ТЗ); роли к команде доступа не имеют (AC-9).
- Сеть: только `fetch`/`push` в `origin` из рабочего репозитория
  `.artel/notes-work`, как у `note`. В тестах — bare origin на диске.
- Откат: revert одного merge-коммита; удержанные записи `doc-commit` в
  `.artel/notes-pending/` после отката перестанут разбираться флашем
  (`_build_for` упадёт на неизвестном `kind` → `SystemExit` перехвачен,
  файл остаётся висеть) — не теряются, `doctor` их покажет.

## Риски

- `runner` импортируется в `notes.py` на верхнем уровне (для
  `notes.runner.in_role_environment`, патчится тестами как у `answer`).
  Цикла нет: `runner` не импортирует `notes` и `doctor`; проверено
  импортом пакета при прогоне тестов.
- Сверка базы отказывает и в случае «файл есть в HEAD, удалён в
  origin» и в обратном «файла нет в HEAD, появился в origin» (blob-sha
  различаются) — оба трактуются как «изменился в origin после пина»,
  сначала `pin-update`. Сознательно: удаление и чужой новый файл —
  тоже чужая правка (второй случай покрыт тестом).
- Сверка базы читает HEAD главной копии одним `git rev-parse` в
  `config.ROOT` — только чтение, требование 2 не нарушается (снимок
  HEAD/ветки/`git status` до и после сверяется тестом).
- Удержанная запись `doc-commit` при флаше после сдвига origin по тому
  же файлу отказывает сверкой базы и остаётся висеть (как устаревшая
  заметка `note`) — Оператор делает `pin-update` и повторяет флаш.

## Предложения системе

- SPEC требование 7 говорит «журнал пульта команда не пишет (как
  `note`)», но `note` журнал пишет (`_commit_and_push`, «заметка: …»).
  Реализовано буквально для `doc-commit` (без журнала), `note` не
  тронут; стоит уточнить формулировку в будущих ТЗ про `note`.
