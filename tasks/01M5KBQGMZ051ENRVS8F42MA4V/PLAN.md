---
task: 01M5KBQGMZ051ENRVS8F42MA4V
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: prune — промпты и каталоги suite-run по правилу хранения логов, удаление брошенного notes-work

## Подход
Все три вида — новые ветви одной команды `orchestrator/prune.py`, план и
исполнение по-прежнему считаются одним расчётом кандидатов в `cmd_prune`.

- **Промпты (тр. 1).** `_log_candidates` перебирает `config.LOGS.iterdir()`
  и берёт файлы с окончанием из `_LOG_SUFFIXES = (".log", ".prompt.txt")`;
  двойное правило (давность И вне `_kept_task_ids`) — прежнее. Строка отчёта
  — та же «лог <имя> …».
- **suite-run (тр. 2).** `_suite_run_candidates(conn)`: подкаталоги
  `suite_lock.directory()`, не ссылки, имя `idgen.is_task_id_form`, задача
  вне `_kept_task_ids`, не держатель `suite_lock.holder()`, самый свежий
  `lstat().st_mtime` среди файлов (`os.walk` без перехода по ссылкам;
  пустой — mtime каталога) старше порога, в `run.json` нет живого pid
  (`_run_pid_alive` — чтение как в `doctor/orphans._live_suite_run_in`).
  `lock.json`/`pending-journal/` отсекаются уже формой имени и тем, что
  `lock.json` — не каталог.
- **Упразднённые (тр. 3–4).** `ABOLISHED_DIRS = (".artel/notes-work",)`,
  `_abolished_candidates()` — существующие каталоги, не ссылки.
  `_unsaved_work_reason(path)`: нет `.git` → «не собственный репозиторий»;
  затем вопросы git через `gitcmd.in_repo` (только локальные):
  `rev-parse --show-toplevel` (не равен каталогу → «не собственный
  репозиторий», остальные вопросы не задаются — иначе они ушли бы к
  репозиторию пульта), `status --porcelain --ignored --untracked-files=all`,
  `rev-list -n 1 --branches --not --glob=refs/remotes/origin/*`,
  `stash list`, `rev-parse --symbolic-full-name HEAD`. Все вопросы
  задаются до разбора: сбой любого — «git не ответил: <stderr>» раньше
  признаков работы (порядок перечня SPEC); затем по порядку — правки
  (строки `status` не `??`/`!!`), неотслеживаемые/игнорируемые, коммиты вне
  origin, stash, HEAD не `refs/heads/…`. Выбраны вызовы, отвечающие нулём
  в штатных случаях (`symbolic-full-name` вместо `symbolic-ref -q`), чтобы
  ненулевой код означал только сбой. Число файлов считается после вопросов
  git (они вправе обновить `.git/index`).
- **Отчёт (тр. 5).** `_print_report` получил необязательные `suite_dirs`,
  `abolished` (пары каталог/число файлов) и `abolished_left` (каталог/
  причина); прежние строки и их порядок не тронуты, новые идут после логов.
  «нечего убирать» — только когда пусто всё, включая «оставлено».
  Удаление — `shutil.rmtree` (`_remove_dirs`), сбой печатается строкой
  «… не удалён: <ошибка>» и не прерывает остальное.
- **Документация (тр. 7–8).** `docs/retention.md`: дополнение раздела
  `.artel/logs/`, разделы «Каталоги упразднённых механизмов» и «Сессии
  ролей (`.artel/home/.claude/projects`)» (объём/рост — из строки
  `docs/backlog.md`). `orchestrator/artel.py`: только абзац модульной
  строки о `prune` и строка перечня модулей.

Оценка SPEC ($45) не меняется.

## Шаги
1. `orchestrator/prune.py` — отбор промптов, `suite-run`, упразднённых
   каталогов, проверка сохранности, отчёт и исполнение.
2. `docs/retention.md`, справка `orchestrator/artel.py`.
3. Тесты: долгоживущий `tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py`
   (не правился) зелёный; свой `tests/test_prune_abolished_rules.py` — на
   свойства вне долгоживущего файла: первая причина по порядку при
   нескольких, сбой git раньше признака работы, проверка без сетевых
   подкоманд git, нечитаемый/нецелый/неположительный pid `run.json` — не
   живой прогон, pid строкой цифр читается как целое. Каждый тест проверен
   временной мутацией из своей заявки — все пять покраснели, код
   восстановлен. Карта `docs/codebase-map.md` регенерирована.

Прогоны: `python3 -m pytest tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py
tests/test_prune.py tests/test_prune_abolished_rules.py tests/test_doc_commit.py`
— 62 passed; `artel.py plank-run 01M5KBQGMZ051ENRVS8F42MA4V` — 2 passed.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 2 |
| 8 | 2 |
| 9 | 3 |

## Влияние на систему
- Инвариант 16 не меняется: `cleanup.py` (`kill`/`done`) не тронут, логи и
  `suite-run` убирает только явный `prune --execute`.
- Хозяйство `suite-run`, нужное идущему прогону, защищено трижды: замок,
  живой pid `run.json`, давность по самому свежему файлу; `lock.json` и
  `pending-journal/` не отбираются формой имени.
- Пороги `LOG_RETENTION_DAYS`/`LOG_RETENTION_KEEP_TASKS` не менялись;
  прежние строки отчёта побайтно прежние, `tests/test_prune.py` зелёный без
  правки.
- Удаление `notes-work` консервативно: любой сбой или неоднозначность —
  «оставлено». Сетевых вызовов нет.
- Откат — revert merge-коммита задачи; данные, удалённые `--execute`, не
  восстанавливаются (поэтому dry-run по умолчанию сохранён).

## Риски
- `git status` в `notes-work` может обновить его `.git/index` при сухом
  прогоне — это служебный файл git, рабочее дерево не меняется.
- Каталог `suite-run` с именем-префиксом id (форма `is_task_id_form`
  допускает префикс) сверяется с `_kept_task_ids` по полному имени — такой
  каталог считается задачей вне БД; на практике каталоги `suite-run`
  называются полным id.

## Предложения системе
- Пульт отказывает в составных bash-командах (`cp … && python3 …`, `rm`)
  и в heredoc с `{"…"}` («expansion obfuscation»): временную мутацию для
  проверки сторожа пришлось писать файлом-сценарием. Не хватает команды
  пульта «mutation-check <файл теста> <замена>» с гарантированным откатом
  (skills/coding-standards.md, раздел «Тесты»).
