---
task: 01M4JMMH70NWJG72G422BFY1KC
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Регенерация карты кодовой базы под интерпретатором пульта, не голым `python3`

## Фаза A — план
- Покрытие: таблица PLAN покрывает требования 1–4 (AC-1…AC-6) единственным
  шагом; для задачи такого объёма (≈110 строк кода, три однотипные замены +
  журнал в одном модуле) один шаг размера MR — адекватно, SPEC сам обосновал
  монолит.
- Подход не конфликтует с архитектурой: `sys.executable` уже применяется тем
  же приёмом в `fsm_merge_gate.py`, `canary.py`, `suite_run.py`; помощник не
  заведён в `stack.py` (путь только для чтения по SPEC «Не входит») — верно.
- Перечень исключений требования 3 назван явно (пуст), совпадает с
  `ALLOWED = frozenset()` сторожа.
- «Влияние на систему» соответствует diff: `brief.py`, `fsm_postmerge.py`,
  `pull.py`, новый тест, регенерированная карта; эскалация не тронута.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `pull.py:368`, `fsm_postmerge.py:95`, `brief.py:285` — `[sys.executable, "scripts/codebase_map.py"]`; `import sys` есть во всех трёх модулях (в `pull.py`/`fsm_postmerge.py` добавлен, в `brief.py` уже был, стр. 18). AC-1/2/3 зелёные. |
| 2 | OK | `_journal_step_failure` (шаг, код или «нет», хвост `strip()[-500:]`) + `_git_step_ok`; покрыты `add` слитого документа, запись слитого (OSError), `checkout --theirs`, регенерация (OSError и ненулевой код), `add` карты, `commit`. Запись делается внутри `_auto_resolve_conflict`, т. е. до `merge --abort`/`set_state` в `_handle_merge_failure`; текст эскалации не меняется (AC-4/AC-5 сверяют его неизменность). Действие `авторазрешение конфликта подтяжки: шаг отказал` не задевает читателей журнала: `auto._pull_conflict_marker_streak` (`auto.py:737-741`) и `fsm.ROLE_STEP_REQUIRED_MARKERS` сравнивают действие на равенство с `PULL_CONFLICT_ROLE_STEP_MARKER`, сбрасывают счёт только по `state -> …` (проверено чтением `auto.py:724-742` и `git grep PULL_CONFLICT`). Штатные отказы политики («не-документ», «аддитивность не доказана») не журналируются — это не отказ шага, решение изложено в PLAN и согласуется с «Не входит» SPEC (поведение эскалации не меняется). |
| 3 | OK | `git grep -n '"python3"' -- orchestrator scripts` — остались только `acceptance.py:37/61`, `runner.py:897`, `stack.py:277/648/653`: комментарий, сравнение, выбор каталога, кортеж имён инструментов, пути venv — не дочерние вызовы. Сторож AC-6 зелёный. |
| 4 | OK | Существующие тесты `tests/` не изменены (diff `tests/` — только новый файл `test_pull_autoresolve_step_journal.py`); раздел «Меняемое поведение» не нужен. |

## Замечания

Блокирующих и major-замечаний нет. Тест разработчика
`tests/test_pull_autoresolve_step_journal.py` повтором долгоживущих не
является: он закрывает шаг `commit`, которого долгоживущие тесты задачи не
касаются; заявка «Ловит мутацию» исполнима и проверена временной мутацией
(см. ниже). Наблюдение без severity, вне реестра: `git commit` при отказе
часто пишет причину в stdout, не в stderr, — тогда хвост в записи будет
«пусто»; SPEC требует именно stderr, так что это не дефект.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q` (Python 3.13.12) по файлам:
  `tests/test_01m4jmmh70nwjg72g422bfy1kc_bare_python3_guard.py`,
  `…_brief_map_interpreter.py`, `…_postmerge_map_interpreter.py`,
  `…_pull_map_interpreter.py`, `tests/test_pull_autoresolve_step_journal.py`,
  `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_fsm_map_regen.py`,
  `tests/test_brief.py`, `tests/test_runner_pre_step_pull.py`,
  `tests/test_fsm_merge_conflict_note.py` — 61 passed, 2 subtests passed.
- Временная мутация «голый `"python3"`» во всех трёх регенерациях
  (`pull.py:368`, `brief.py:285`, `fsm_postmerge.py:95`): красные
  test_ac6 (сторож), test_ac3 (brief), test_ac2 (postmerge), test_ac1 (pull);
  AC-4/AC-5 зелёные, как и должны. Код возвращён `git checkout -- orchestrator/`.
- Временная мутация «отказ `commit` молча `False`» (прежний
  `gitcmd.in_repo` + `return False` в `_auto_resolve_conflict`):
  `tests/test_pull_autoresolve_step_journal.py` красный. Код возвращён.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`:
  расходится только строка `built_at_sha` — карта свежая; рабочая копия
  возвращена (`git status --short` пуст).
- `artel.py plank-run 01M4JMMH70NWJG72G422BFY1KC` — отказ «планки нет: в
  refs/artifacts/… нет файлов test_*.py»: вся планка задачи — долгоживущие
  файлы в `tests/`, их прогон выше.
- Статус CI коммита 8e74cdb9 по пакету — зелёный (16 проверок).

## Предложения системе
- `artel.py plank-run` у задачи, вся планка которой — долгоживущие
  `tests/test_<id>_*.py`, отвечает отказом «планки нет»; скил
  review-checklist велит гонять планку только этой командой. Стоило бы,
  чтобы plank-run в таком случае прогонял долгоживущие файлы из перечня лока.
