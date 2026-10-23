---
task: 01M5KBQGMZ051ENRVS8F42MA4V
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: prune — промпты и каталоги suite-run по правилу хранения логов, удаление брошенного notes-work

## Фаза A — план
- Таблица покрытия полна: требования 1–9 → шаги 1–3.
- Шаги размера MR: код `prune.py`, документация, тесты. Не микрооперации.
- Подход в рамках архитектуры: новые ветви той же команды, один расчёт
  кандидатов для плана и исполнения, git через `gitcmd.in_repo`, файлы
  «только для чтения» из SPEC не тронуты (по diff --stat: только
  `docs/retention.md`, `orchestrator/artel.py`, `orchestrator/prune.py`,
  новый `tests/test_prune_abolished_rules.py` плюс карта).
- «Влияние на систему» совпадает с diff: `cleanup.py` не тронут, пороги не
  менялись, откат — revert; необратимость удаления закрыта dry-run по
  умолчанию.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_log_candidates` (`orchestrator/prune.py:67`): `iterdir()` + `endswith((".log", ".prompt.txt"))` + `is_file()`, двойное правило прежнее; `*.prompt.txt.bak`, `*-state.db` не отбираются (AC-1 планки). |
| 2 | OK | `_suite_run_candidates`: не ссылка, `is_task_id_form`, вне `_kept_task_ids`, не держатель `holder()`, давность по самому свежему файлу (`os.walk` без перехода по ссылкам; пустой — `lstat` каталога), `run.json`: `int(pid)`, `pid > 0`, `_pid_alive`. `lock.json` — не каталог, `pending-journal` — не форма id (алфавит ULID без `-`, длина ≤ 26). Каталоги `suite_run` называются полным id (`suite_run._task_dir`). |
| 3 | OK | `ABOLISHED_DIRS`, `_abolished_candidates` — `is_symlink()` раньше `is_dir()`. |
| 4 | OK | `_unsaved_work_reason`: нет `.git` / `--show-toplevel` ≠ каталог (по `resolve()`) → «не собственный репозиторий» сразу, без вопросов к репозиторию выше; все остальные вопросы задаются до разбора, сбой — «git не ответил: <stderr>» раньше признаков работы; затем правки → `??`/`!!` → `rev-list --branches --not --glob=refs/remotes/origin/*` → stash → HEAD `refs/heads/`. Сетевых подкоманд нет. Нерождённая ветка/нет origin-ссылок дают «git не ответил»/«коммиты вне origin» — консервативно. |
| 5 | OK | Новые строки после логов, прежние строки и порядок не тронуты; «нечего убирать» учитывает все виды и «оставлено»; `_remove_dirs` ловит `OSError`, печатает «… не удалён: …», остальное продолжается; логи удаляются раньше каталогов. |
| 6 | OK | `cleanup.py`, правила `*.log`, канарейки, alerts не менялись; `tests/test_prune.py` зелёный без правки. |
| 7 | OK | `docs/retention.md`: дополнение `.artel/logs/`, разделы «Каталоги упразднённых механизмов» и «Сессии ролей (`.artel/home/.claude/projects`)». |
| 8 | OK | `artel.py`: только абзац модульной строки и строка перечня модулей. |
| 9 | OK | Долгоживущий файл задачи не правился (вне diff), свой файл — свойства вне него; существующие тесты не изменены (diff `tests/` — только новый файл). |

## Замечания
Нет замечаний уровня blocker/major/minor.

Наблюдение без замечания: `is_task_id_form` допускает префикс id, поэтому
старый каталог `suite-run` с именем-префиксом считается задачей вне БД и
отбирается — это буква требования 2 («задача, которой нет в БД, — вне
множества»), PLAN называет риск в «Рисках»; `suite_run` создаёт каталоги
только полным id (`orchestrator/suite_run.py:119`), так что сценария
поломки в штатной работе нет.

Тесты `tests/test_prune_abolished_rules.py`: у каждого метода есть заявка
«Ловит мутацию: …» с наблюдаемым расхождением (строка отчёта / наличие
каталога / перечень вызовов git); повтора свойств долгоживущего файла нет
(порядок причин, приоритет сбоя git, локальность вызовов, нечитаемый pid,
pid строкой — в долгоживущем не проверяются).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний в итерации 1 не заведено, прошлых итераций нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m5kbqgmz051enrvs8f42ma4v_prune_retention.py tests/test_prune.py tests/test_prune_abolished_rules.py`
  — 34 passed, 31 subtests passed (57 с).
- `artel.py plank-run 01M5KBQGMZ051ENRVS8F42MA4V` — 2 passed, код выхода pytest 0.
- Временная мутация (сторож `test_first_reason_in_order_wins`): в
  `_unsaved_work_reason` проверка stash поставлена раньше сбоя и правок —
  `pytest tests/test_prune_abolished_rules.py -k first_reason` → 1 failed;
  код возвращён `git checkout -- orchestrator/prune.py`, `git status` чист.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` —
  расхождение только в строке `built_at_sha` (карта свежа по содержимому);
  регенерация откачена.
- Чтения сверх пакета: `idgen.is_task_id_form`, `suite_lock.holder`,
  `gitcmd.in_repo` (проверка формы имени и побочных эффектов чтения замка),
  `suite_run._task_dir` и `providers/codex.py:440` (кто пишет в каталог
  `suite-run` и как называет подкаталоги).
- CI коммита 1bf1a85b зелёный (16 проверок) — из пакета.

## Предложения системе
- Строки реестра нельзя завести под наблюдение уровня «не дефект»: любой
  minor в реестре блокирует гейт `approved` до следующей итерации, поэтому
  наблюдения уходят в свободный текст — стоит предусмотреть статус
  `info`, не блокирующий гейт (`advance_gates`/`fsm_advance.review`).
