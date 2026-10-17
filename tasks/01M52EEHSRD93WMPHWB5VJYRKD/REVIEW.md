---
task: 01M52EEHSRD93WMPHWB5VJYRKD
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: D0-3: один источник профиля у вызывающих прогон

## Фаза A — план
- Таблица покрытия полна: каждая точка требования 1 (гейт мержа, рубеж `in_dev` с повторами, `suite_run` с ключом базы, `plank_run`, обе точки `amend`, `pull`, сухой сбор `tests_writing`, оба вызывающих `two_sided.run`) — шаг 1; требования 2 и 5 — честно «без правки», требования 3 и 4 — ветки `None`/список.
- Один шаг на однородную правку в 9 файлах приемлем: правка механическая, размер MR — 144+/31−.
- Подход не конфликтует с архитектурой: источник профиля один (`acceptance._own` / `acceptance._task_own_profile` части 2), второго не заводится. Обращение к закрытым именам из чужих модулей названо в «Рисках» и «Предложениях системе». Это обосновано: правка `acceptance.py` по SPEC «Не входит».
- «Влияние на систему» сходится с diff: вне зоны SPEC файлов нет, `acceptance.py`/`two_sided.py`/`notes.py`/`preflight`/`dry_run` не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 — гейт мержа | OK | `fsm_merge_gate.py:820-823`: `_full_suite_command` отдаёт `acceptance._own(profile) or list(profile.command)`. Обе ветви `fresh` берут его одинаково (AC-3 зелёный в обеих subTest) |
| 1 — рубеж `in_dev` и повторы с зерном | OK | `advance_gates/acceptance.py:393-396`: тот же `command` идёт в `_seed_repeats_escalate` (аннотация снята под Profile). AC-12 проверяет и прогон, и `LONG_LIVED_SEED_REPEATS` повторов |
| 1 — `suite-run` и ключ итога | OK | `_profile_command` при `runner: pytest-own` строит `Profile.from_values`. Тот же объект уходит в `run_full_suite` ветки и базы и в `suite_result_key(…, base=True)` у `_base` (`suite_run.py:523`). Ключ `_own_suite_result_key` у профиля сверен по `acceptance.py:1829-1890`. `--failed` у own идёт каналом `test_ids`: `run_full_suite` не переводит id `::` к `workdir`, а pytest печатает их уже из `workdir` (`acceptance._own_target`) |
| 1 — `plank-run` | OK | `plank_run.py:187-192`, `run_plank(..., profile=own)` только при не-`None` |
| 1 — `amend-tests` | OK | `_collect_and_run`: `command=own`. `_amend_plank_only`: `cwd=wt_path` + `command=own` только у own. `tdir = wt_path/"tasks"/id` абсолютный (`amend.py:699`), так что смена `cwd` путь планки не ломает |
| 1 — `pull` | OK | `pull.py:663-671`, обе ветви |
| 1 — сухой сбор `tests_writing` | OK | `fsm_advance.py:595` (приоритет `(A or B) if … else None` верный). `_tests_writing_dry_collect_gate` не сворачивает Profile в список |
| 1 — двусторонний прогон | OK | `_own_profile` → `_observe` → `_observe_methods` → `two_sided.run(profile=…)`, и в вызове гейта `:1542`. У `pult-pytest` форма вызова прежняя |
| 2 | OK | Без правки, через `acceptance_suite` (часть 2). AC-1/AC-2 зелёные |
| 3 | OK | Порядок узлов, отказы и журнал гейтов не менялись. В `suite_run` поменялись только канал команды и выбор `targets`/`test_ids` |
| 4 | OK | `notes.py` не тронут (AC-11 зелёный). У артели и `pult-pytest` вызовы прежней формы (AC-10 — обе вариации, 16 мест каждая) |
| 5 | OK | `preflight.py` и `dry_run.py` не тронуты |

## Замечания
Нет.

## Реестр замечаний
| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

Целостность: утверждения существующих тестов не изменены, удалений нет. Diff `tests/` — только импорт и новый класс `FailedIdsByProfileTest`. Его заявка «Ловит мутацию» наблюдаема и подтверждена временной мутацией (ниже). Новый тест не дублирует долгоживущий файл задачи: тот проверяет `suite-run` полным прогоном без `--failed`, а новый — канал `test_ids` в режиме `--failed`. Долгоживущий файл несёт `Группа: долгоживущий` и проверяет свойства кода, не факты задачи. Защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) не тронуты.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_suite_run.py`: 17 passed, 6 subtests passed.
- Временная мутация `orchestrator/suite_run.py`: строка `targets, test_ids = (), targets` заменена на `pass`. `pytest tests/test_suite_run.py -k FailedIds`: SUBFAILED на подслучае Profile (`test_ids` = None вместо id), 1 failed. Код возвращён, `git status` чистый.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`: 26 passed, 44 subtests passed за 89.65 с.
- Временная мутация `orchestrator/amend.py::_amend_plank_only`: из kwargs убран `cwd=wt_path`. `pytest … -k ac6`: SUBFAILED `long_lived=False`. Код возвращён, `git status` чистый.
- `artel.py plank-run 01M52EEHSRD93WMPHWB5VJYRKD`: отказ «в источнике нет файлов test_*.py». Планка задачи — только долгоживущий файл `tests/` (перечень лока), его прогон выше.
- `python3 scripts/codebase_map.py` → `git diff -- docs/codebase-map.md`: расхождение только в `built_at_sha`, карта свежа. Изменение откачено `git checkout`.
- CI коммита a8f7e5cf зелёный (16 проверок, по пакету).

## Предложения системе
- `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`: 89.8 с при пороге 60 с. Тяжёлую часть составляют AC-10 (2 × 16 мест в настоящем git). Класс «связочный тест на все места × все профили» стоит в test-authoring делить на файлы или классы по месту — иначе порог превышается по построению.
- `orchestrator/plank_run.py:189-192`, `advance_gates/test_integrity.py:1437-1441`, `:1542-1546`: двойная форма вызова `f(…, profile=own) if own is not None else f(…)` нужна только ради неизменной формы вызова для `mock.assert_called_with` в старых тестах. При дефолте `profile=None` по поведению она равна одному вызову. Раз шаблон повторяется, стоит решить на уровне конвенции, допустимо ли менять форму вызова при неизменном поведении.
- `orchestrator/acceptance.py`: `_own`/`_task_own_profile` теперь используют 7 модулей — поддерживаю предложение PLAN сделать их публичными.
