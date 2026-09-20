---
task: 01M2XMCG167615YS9EZD9TYJWV
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Команда doc-commit: документы и конфигурация Оператора коммитятся от origin/main механикой note

Ревью HEAD `cd5b944e` (код — коммит `ed3b7854`, поверх него подтяжка main).
SPEC.md и PLAN.md в ревью-пакет не вошли («не показан … в дереве — файл
не найден»), хотя на диске рабочего каталога оба материализованы —
прочитаны инструментом чтения по адресу `tasks/<id>/SPEC.md`,
`tasks/<id>/PLAN.md`, `tasks/<id>/TZ.md` (без них ни гейт плана, ни
таблицу соответствия не заполнить).

## Фаза A: гейт плана

1. **Покрытие SPEC полно.** Таблица «Покрытие требований» PLAN несёт все
   10 требований, каждое адресовано шагом и (где применимо) тестом;
   AC-1..AC-9 сопоставлены тестам `tests/test_doc_commit.py` и планке
   `acceptance_tests/`.
2. **Шаги — проверяемые единицы.** Четыре шага (notes.py, artel.py,
   тесты, карта) — размер одного MR; SPEC обосновал монолит (общий
   формат pending без команды и команда без формата — оба промежуточных
   состояния теряют или не разбирают удержанные записи), PLAN его не
   оспаривает. Согласен: резать нечего.
3. **Подход не конфликтует с архитектурой.** Ветвление по `kind` ровно
   в трёх точках (`_fetch_and_build`, `_commit_and_push`,
   `_commit_message`), остальная механика `note` переиспользуется, не
   копируется; рубеж `runner.in_role_environment()` — тот же, что у
   `answer`/`zones-extend`. Секция «Влияние на систему» соответствует
   фактическому diff: 4 файла (`orchestrator/notes.py`,
   `orchestrator/artel.py`, `tests/test_doc_commit.py`,
   `docs/codebase-map.md`), защищённые пути не тронуты, гейты/guard'ы не
   ослаблены, путь отката описан (revert одного merge-коммита, повисшие
   записи `doc-commit` в pending не теряются, `doctor` их покажет).

Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (команда, механика note, --flush) | OK | `cmd_doc_commit` → `_run` → общий цикл `_fetch_and_build`/`_commit_and_push` с `MAX_PUSH_ATTEMPTS`, удержание `_hold_pending` при сетевом отказе и окне; `doc-commit --flush` и `note --flush` зовут один `_flush_pending`. Тесты `DocCommitPushTest`, `SilenceWindowAndFlushTest`. |
| 2 (главная копия не трогается) | OK | Вся запись — в `.artel/notes-work`; в `config.ROOT` только `git rev-parse --verify` (чтение). Снимок HEAD/ветка/`status --porcelain` до и после сверяет `test_content_lands_in_origin_output_names_sha_main_copy_untouched`. |
| 3 (допустимые пути, именованный отказ) | OK | `_doc_commit_path_refusal`: нормализация `PurePosixPath`, отказ абсолютным/`..`/пустым/голому `docs`; `docs/**` кроме `BACKLOG_REL`; ровно `DOC_COMMIT_CONFIG_PATHS`. Текст отказа — буквально из SPEC (`DOC_COMMIT_FOREIGN_REFUSAL`). `PathRefusalTest`, `DocCommitRefusalTest`. |
| 4 (отказ из окружения роли) | OK | Первая строка `cmd_doc_commit`, до argparse и до `_ensure_work_repo` (тест проверяет, что `.artel/notes-work` не заведён). Прочитан `orchestrator/runner.py:696-705`: маркеры HOME/CLAUDE_CONFIG_DIR — тест `test_role_environment_markers_from_env_are_honoured` ставит именно их. |
| 5 (сверка базы, новый файл допустим) | OK | `_build_doc_commit`: blob-sha `FETCH_HEAD:<путь>` в рабочем репо против `HEAD:<путь>` в `config.ROOT`; оба `None` — новый файл. Текст отказа — буквально из SPEC (`DOC_COMMIT_BASE_REFUSAL`). `PinBaseCheckTest` покрывает расхождение, новый файл, файл, появившийся в origin после пина. |
| 6 (сообщение коммита, --message обязателен) | OK | `_commit_message` ветка `doc-commit`: `docs:`/`config:` по `_doc_commit_prefix`, без усечения; пустой/пробельный `--message` — отказ до `_run`. `CommitMessageTest`, `test_config_path_gets_config_prefix_docs_path_gets_docs_prefix`, `test_missing_message_refused_without_commit_or_hold`. |
| 7 (без журнала, вывод sha) | OK | `store.journal` в `_commit_and_push` обёрнут `if not is_doc_commit`; прочитан `orchestrator/store.py:572-574` — `journal` пишет в таблицу `steps`, её и считает `test_no_journal_row_for_doc_commit`, заявка мутации правдива. `_run` возвращает sha, `cmd_doc_commit` печатает `<путь> закоммичен в origin/<main>: <sha>`. |
| 8 (общий pending, поле kind, flush обоих видов) | OK | Один `_pending_dir()`, JSON с `kind: doc-commit`; `_flush_pending` → `_attempt` → `_fetch_and_build` ветвится по `kind`. `test_note_flush_sends_both_kinds`, `test_doc_commit_flush_sends_both_kinds`, `test_flush_does_not_need_source_file_anymore`. |
| 9 (совместимость note) | OK | Diff `tests/test_notes.py` пуст; прогнан без правок — зелёный. Тексты удержания/отказа `note` параметризованы, но буквально прежние (`test_note_hold_texts_unchanged`). |
| 10 (тесты в tests/) | OK | `tests/test_doc_commit.py`, 28 тестов, у каждого заявка «Ловит мутацию» (проверено разбором AST — пропусков нет). Заявки сверены с кодом выборочно и по ключевым: журнал (`steps`), маркеры role_env, оппортунистический флаш под окном, CRLF байт-в-байт — мутации правдоподобны, тесты их ловят. |

Корректность за пределами таблицы, что проверял отдельно:
- Повтор non-fast-forward для `doc-commit`: после неудачного push
  локальный коммит остаётся в `notes-work`, дерево чистое, следующая
  итерация `checkout -B main FETCH_HEAD` сбрасывает его; если
  промежуточный чужой коммит тронул тот же файл — сверка базы отказывает
  `sys.exit` (не удерживает) — это правильно: запись сделана поверх
  устаревшей версии.
- Отказ «содержимое уже совпадает» стоит после сверки базы и до
  commit — иначе три провала `git commit` повисли бы записью в pending;
  внутри `_flush_pending` такой `SystemExit` перехватывается и запись
  остаётся висеть (как устаревшая заметка `note`) — задокументировано в
  «Рисках» PLAN.
- Импорт `runner` на верхнем уровне `notes.py`: цикла нет (карта:
  `runner` не импортирует `notes`; `doctor` берёт `notes` через
  `doctor.notes`), импорт пакета при прогоне тестов чист.
- Безопасность: секретов нет; `--from` — любой путь на диске по
  замыслу SPEC (Оператор, не роль — рубеж AC-9); push сразу в
  `origin/main` для `roles.yaml`/`gates.yaml`/`targets.yaml` мимо ревью —
  решение Оператора 19.09, зафиксировано ТЗ/SPEC; `PROTECTED_PATHS` не
  правится.
- Системная целостность: удалённых/изменённых `assert` в `tests/` — 0
  (diff `tests/` — только новый файл); `skills/`, `templates/`,
  `gates.yaml`, `roles.yaml`, `.github/` — не тронуты; пометок
  `AC-n: manual|skip` в планке нет.

## Замечания

- minor — `orchestrator/notes.py:337-352` (`_doc_commit_path_refusal`)
  и `:411-417` (`_write_doc`) — путь, который в репозитории является
  КАТАЛОГОМ (`doc-commit docs/adr --from x`), проходит проверку пути
  (`docs/<что-то>`), проходит сверку базы (tree-sha каталога совпадает в
  origin и пине) и падает в `_write_doc` необработанным
  `IsADirectoryError`; путь с файлом-родителем
  (`docs/roadmap.md/x.md`) — `FileExistsError` из `mkdir(parents=True)`.
  Воспроизведено зондом на стенде `DocCommitSandbox`: traceback, origin
  не сдвинут, удержанной записи нет — ущерба нет, но вместо
  именованного отказа Оператор видит стек. Предложение (не для этой
  задачи): в `_build_doc_commit` после сверки базы — `if target.is_dir()
  → sys.exit("<путь>: это каталог, укажи файл")`, а `mkdir`/`write_bytes`
  в `_write_doc` обернуть в `except OSError → sys.exit`. Класс один —
  оба места перечислены.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/notes.py:337-352, :411-417 | Путь-каталог (`docs/adr`) или путь с файлом-родителем (`docs/roadmap.md/x.md`) даёт необработанный `IsADirectoryError`/`FileExistsError` вместо именованного отказа | Traceback вместо отказа; origin и pending не затронуты (проверено зондом) — ущерба нет | minor, правки в рамках задачи не требует: ни одно требование SPEC не называет этот случай, ущерба нет. Закрыто ревьювером на месте как наблюдение для будущей правки (см. «Замечания»); статус `accepted` — чтобы гейт `review -> verifying` не отклонил `approved` |

## Вердикт
approved

## Проверено исполнением

Рабочий каталог `.artel/worktrees/01M2XMCG167615YS9EZD9TYJWV`, HEAD
`cd5b944e`, CI коммита зелёный (7 проверок, по пакету).

- `python3 -m pytest tests/test_doc_commit.py tests/test_notes.py
  tests/test_artel_role_restricted_commands.py -p no:cacheprovider -q`
  — 75 passed (29.8 s); `tests/test_notes.py` без правок — требование 9.
- `python3 -m pytest tasks/01M2XMCG167615YS9EZD9TYJWV/acceptance_tests/
  -p no:cacheprovider -q` — 13 passed (9.2 s), AC-1..AC-9.
- `python3 scripts/guard.py tasks/<id>/PLAN.md tasks/<id>/SPEC.md` —
  `GUARD: ок (2 файлов)`.
- Разбор AST `tests/test_doc_commit.py`: функций `test_*` без строки
  «Ловит мутацию» в докстринге — `[]`.
- `python3 scripts/codebase_map.py` — диф свёлся только к строке
  `built_at_sha` (сверено `git diff -- docs/codebase-map.md | grep -v
  built_at_sha` → пусто), карта по содержимому свежая; перегенерация
  отменена `git checkout -- docs/codebase-map.md`.
- `git diff 712b7cfa...HEAD --stat -- tests/ skills/ templates/
  gates.yaml roles.yaml .github/` — только `tests/test_doc_commit.py`
  (+600); удалённых строк `assert` в `tests/` — 0.
- `grep -rn "AC-[0-9]*: *(manual|skip)" tasks/<id>/acceptance_tests/`
  — пусто.
- Зонд (временный `unittest` на `DocCommitSandbox`, удалён после
  прогона): `doc-commit docs/adr` при существующем `docs/adr/0001.md` в
  origin → `IsADirectoryError`, origin не сдвинут, `pending_notes()`
  пуст; `doc-commit docs/roadmap.md/x.md` → `FileExistsError`, pending
  пуст — основание R1-F1.
- Прочитаны точечно: `orchestrator/notes.py` целиком (в т.ч. не
  вошедшие в diff `_attempt`, `_flush_pending`, `_hold_pending`,
  `_silence_window_reason`, `_ensure_work_repo`) — для проверки
  требования 8 и повторов; `orchestrator/runner.py:696-705`
  (`in_role_environment`) — заявка теста про маркеры;
  `orchestrator/store.py:572-574` (`journal` → таблица `steps`) —
  заявка теста про журнал; `orchestrator/doctor/misc_checks.py:35-45`
  — совет `note --flush` остаётся верным для обоих видов;
  `scripts/guard.py:915-1044` — форма реестра.

## Предложения системе

- Ревью-пакет этой задачи не нашёл `tasks/<id>/SPEC.md` и
  `tasks/<id>/PLAN.md` («в ветке — не существует; в дереве — файл не
  найден»), хотя в рабочем каталоге шага оба материализованы. Сборщик
  пакета (`orchestrator/review.py` / `context_package.py`), похоже,
  ищет их в дереве не там, где их кладёт материализация артефактной
  ветки; ревьювер без них работать не может и вынужден читать с диска
  — стоит сверить путь «в дереве» сборщика с `role_cwd` шага.
- PLAN уже отметил: SPEC требование 7 «журнал не пишет (как `note`)» —
  фактически `note` журнал пишет. Реализовано буквально для
  `doc-commit`; формулировку про `note` стоит поправить в docs.
