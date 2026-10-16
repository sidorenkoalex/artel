---
task: 01M52CQB468758M2NAA15C15ZE
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/; в) пути-признаки (гейты): orchestrator/advance_gates/acceptance.py, orchestrator/advance_gates/test_integrity.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/two_sided.py, orchestrator/fsm_advance.py, orchestrator/fsm_autogate.py, orchestrator/fsm_merge_gate.py; г) budget_usd 50 ≥ 45; д) ТЗ ссылается на ADR: ADR-0023
spec_sha: 58e64feff39e4d3a60e652bc61901f90f3fab131
schema_version: 5
---

# SPEC-AUDIT: D0 — внешний доверенный проект без песочницы: профиль чужого стека и чистое окружение тестов

Повторный аудит после возврата SPEC Оператором с гейта (решение №1 от
16.10.2026, десять пунктов). Проверено, что решения внесены, и заново
сверены требования с кодом рабочего каталога.

## ТЗ и SPEC

Решения Оператора на гейте SPEC (№1) внесены все:
- п.1 — сухой сбор `tests_writing` в требовании 7, `fsm_advance.py` и
  `advance_gates/tests_writing.py` в зонах SPEC и D0-3;
- п.2 — `test_integrity.py` в зонах D0-3, приём профиля в `two_sided.run` —
  в D0-2;
- п.3 — `workdir`/`env` только при `pytest-own` (требование 1, AC-13); ключ
  `pult-pytest` неизменен (требование 8, AC-15);
- п.4 — `acceptance_suite` в D0-2 (п.1 части);
- п.5 — перевод целей делает место запуска (требование 4);
- п.6 — AC-2, AC-3, AC-4, AC-6 перечисляют восемь мест поимённо, AC-3
  проверяет уборку `HOME` и после таймаута;
- п.7 — AC-7 сверяет с профилем; есть отдельные AC-8…AC-12;
- п.8 — AC-1 и требование 9 охватывают оба пути команды;
- п.9 — строка матрицы о `-p timeout` есть;
- п.10 — факты `docs/backlog.md:186`, `config.py:587`,
  `acceptance.py:1343-1350` исправлены. Рамки частей указаны.

Требования ТЗ 1–8 и все пять критериев приёмки ТЗ в SPEC отражены. Сверх
ТЗ — только то, что прямо разрешил Оператор (зоны `fsm_advance.py`,
`tests_writing.py`, `test_integrity.py`; запрет `workdir`/`env` при
`pult-pytest`).

Расхождения с ТЗ: нет. Ниже — расхождения с кодом, которые требования
SPEC унаследовали.

## Факты против кода

Подтвердилось:
- `_pytest_command` — `orchestrator/acceptance.py:35-65`, `-p timeout -o
  timeout=…` — `:64-65`; `_pytest_env` — `:69-89` (копия `os.environ` +
  `PYTHONPYCACHEPREFIX`).
- Места запуска: `run` `:448`, `collect` `:556`, `run_repeat` `:665`,
  `run_plank` `:932` — `subprocess.run(timeout=…)` без своего сеанса;
  `_run_full_suite_now` с `observe` — `Popen(start_new_session=True)` и
  `_kill_group` `:1324-1339`; без `observe` — `subprocess.run` `:1343-1350`;
  `_run_full_suite_to_log` — `:1371-1390`; `two_sided._run_side` —
  `two_sided.py:227-235`.
- Полный набор: `root / "tests"` `:1172`, `-n … -p xdist` `:1175-1176`.
- Ключ: `suite_result_key` `:1609-1640`, gate-итог `:1740-1758`, base-итог
  `:1789-1793`; `suite_run.py:511`, `:524-525`, `:564-565`.
- `acceptance_suite` `:1807-1848` зовёт `full_suite` без `command`
  (`:1847-1848`); вызывающие — `fsm_autogate.py:326`, `fsm.py:1294`.
- Вызывающие: `fsm_merge_gate.py:962-967`, `plank_run.py:187`,
  `amend.py:545,549,715,718`, `pull.py:664-666`, `fsm_advance.py:594-596`,
  `tests_writing.py:557-563`, `test_integrity.py:1429,1527`,
  `notes.py:1040`. Других вызовов мест запуска в `orchestrator/` и
  `scripts/` нет (grep `acceptance\.(run|collect|run_repeat|run_plank|full_suite|run_full_suite|acceptance_suite)\(`, `_pytest_command`, `two_sided.run(`).
- `preflight.py` и `dry_run.py` pytest не запускают (`subprocess` и
  `acceptance` не импортируют) — утверждение требования 7 верно.
- `PROFILE_FIELDS` — `targets.py:41-50`, неизвестное подполе — отказ
  `:269-272`; вид `dir` уже отказывает `/`, `..`, пустым сегментам
  `:299-303`. `Profile` — `project_profile.py:63-85`.
- `runner.foreign_secret_env_names` — `runner.py:914`; `secret_env_names` у
  провайдеров — `providers/claude.py:213`, `providers/codex.py:500`.
- `command: [python3, -m, pytest]` — `targets.yaml:46`.
- `config.ACCEPTANCE_TIMEOUT_SEC` `:188`, `TWO_SIDED_PYTEST_TIMEOUT_SEC`
  `:207`, `FULL_SUITE_TIMEOUT_SEC` `:219`, `SPLIT_SIGNAL_BUDGET_USD = 60`
  `:587`; строка бэклога — `docs/backlog.md:186`.

Не подтвердилось / не учтено:
- **Ф1. id упавших `suite-run --failed` не отсчитаны от корня
  репозитория.** Требование 4 (и п.3 D0-2, AC-5) велит «прочие переданные
  вызывающим цели (например, id упавших тестов `suite-run --failed`)
  переводить от корня репозитория к `workdir`». Но перечень упавших
  `suite_run._read_failed` (`suite_run.py:217`) пишется из разбора вывода
  pytest — `acceptance.failed_entries` (`acceptance.py:1452-1465`), блок
  «short test summary info»: эти id pytest печатает относительно своего
  rootdir, а при `cwd = workdir` rootdir лежит в `workdir` или ниже, не в
  корне репозитория. Перевод «от корня к `workdir`» превратит
  `tests/test_x.py::t` (уже от `workdir`) в `../tests/test_x.py::t` —
  повтор упавших у sled сломается, а тест AC-5 на выдуманной цели «от
  корня» останется зелёным.
- **Ф2. Проверка наличия `<корень>/tests` в `run_full_suite`.**
  `acceptance.py:1172-1174` возвращает `FULL_SUITE_NO_TESTS_NOTE`, если нет
  `root/"tests"`, до сборки argv. Требование 4 меняет цель на
  `long_lived_dir`, но не говорит, что и эта проверка при `pytest-own`
  идёт по `long_lived_dir` под `workdir`. У sled `<корень>/tests` нет
  (ТЗ, «Факты») — полный набор вернёт «tests/ нет в worktree».
- **Ф3. `amend-tests` без `long_lived` идёт из `config.ROOT`.**
  `amend.py:715` и `:718` зовут `collect(tdir)`/`run(tdir)` без `cwd`, то
  есть `cwd = config.ROOT` (`acceptance.py:439`, `:550`) — корень пульта,
  не рабочая копия задачи. AC-9 требует `cwd` = `workdir` для
  `amend-tests`, а требование 7 разрешает в `amend.py` только передачу
  профиля. Либо AC-9 по этому пути невыполним, либо разработчик меняет
  `cwd` вызова — правку, которую SPEC не называет.
- **Ф4. Два места запуска не имеют параметра `command`.**
  `run_plank(targets, cwd)` (`acceptance.py:923`) и `_run_side(tree, nodes,
  plugin_dir, report, timeout)` (`two_sided.py:222`) команды не принимают,
  `_run_full_suite_now`/`_to_log` получают готовый argv. Требование 9 и
  AC-1 («по обоим путям команды … зафиксированы ДО правки», критерий D0-1
  «фиксирующие тесты … по обоим путям команды зелёные на текущем коде»)
  для `run_plank` и `_run_side` на пути `command=[python3, -m, pytest]`
  на текущем коде не определены. Формулировка «принимают профиль тем же
  каналом, что сегодня `command`» (D0-2, п.1; требование 7) для них же
  канала не имеет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да, кроме Ф4 | случайно включённый чистый env/новый сеанс/иной argv у артели; смена `cwd` по умолчанию. Для `run_plank`/`_run_side` на пути `command=[python3,-m,pytest]` фиксация до правки невозможна (Ф4) |
| AC-2 | да | передача `dict(os.environ)` при `pytest-own`; потеря `test_profile.env`; утечка маркера/токена в одном из восьми мест |
| AC-3 | да | общий `HOME` пульта; временный `HOME` не убран на ветке таймаута |
| AC-4 | да | оставленный `-p timeout`/`-o timeout`/`-n`/`-p xdist`; подстановка venv-интерпретатора вместо `python3` профиля; `cwd` = корень вместо `workdir` |
| AC-5 | частично | цель `<корень>/tests` вместо `long_lived_dir` ловит. Не ловит Ф2 (если в учебном проекте есть приманка `<корень>/tests`, проверка `:1172` её найдёт и пропустит) и закрепляет неверный перевод id `--failed` (Ф1) |
| AC-6 | да | `subprocess.run` без `start_new_session`/`killpg` у точечных мест и у `_run_full_suite_now` без `observe` |
| AC-7 | да | `acceptance_suite` без профиля задачи; гейт мержа без профиля при `command is None` |
| AC-8 | да | `plank_run.py:187` без профиля |
| AC-9 | да, но см. Ф3 | `amend.py:545/549/715/718` без профиля; по пути `:715-718` `cwd` не определён SPEC |
| AC-10 | да | `pull.py:664-666` без профиля |
| AC-11 | да | `test_integrity.py:1429/1527` не передают профиль; `_run_side` без него |
| AC-12 | да | `fsm_advance.py:594-596`/`tests_writing.py:557-563` передают только `command` |
| AC-13 | да | пропуск сверки имени секрета; `workdir` абсолютный/`..`; `runner` вне двух значений; `workdir`/`env` при `pult-pytest` по умолчанию |
| AC-14 | да | проверка только синтаксиса без `realpath` в момент прогона |
| AC-15 | да | ключ без `runner`/`workdir`/`env`; изменённый байт ключа `pult-pytest` |

## Зоны

Зоны SPEC = зоны ТЗ + `fsm_advance.py`, `advance_gates/tests_writing.py`,
`advance_gates/test_integrity.py` по решению Оператора №1 пп.1–2. Других
вызывающих мест запуска вне зон grep не нашёл. Защищённых путей
(`config.PROTECTED_PATHS`) требования не трогают; `targets.yaml` и
`docs/backlog.md` — только чтение. Деление: D0-1 (`targets.py`,
`project_profile.py`, `tests/`), D0-2 (`acceptance.py`, `two_sided.py`,
`tests/`), D0-3 (остальные) — зоны частей вместе дают зоны SPEC, не
пересекаются, кроме `tests/`. Песочница ролей не расширяется.

Если Ф3 решается сменой `cwd` в `amend.py:715-718`, это правка логики
вызова, а не только передача профиля — нужна явная строка в SPEC.

## Матрица неослабления

Строки SPEC проверены: `-p timeout` (заменитель — предел места запуска и
снятие группы, AC-6; принято Оператором), `-n -p xdist`, окружение. Не
хватает строк для свойств, которые задача тоже трогает:

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| цель полного набора при `pytest-own` — `long_lived_dir` | «нет набора — не зелёно»: `run_full_suite` отказывает при отсутствии `root/"tests"` (`acceptance.py:1172-1174`, `FULL_SUITE_NO_TESTS`) | не задано SPEC (Ф2): проверка либо ложно отказывает sled, либо смотрит не тот каталог | не покрыто | нужно требование: при `pytest-own` проверка по `long_lived_dir` под `workdir`, отсутствие — `FULL_SUITE_NO_TESTS` |
| ключ повторного использования итога при `pytest-own` | итог засчитывается только для той же команды (`acceptance.py:1609-1640`) | да | AC-15 | строки в матрице нет — желательно добавить |
| классификация «таймаут теста (pytest-timeout)» двустороннего прогона | `two_sided.py:204-205` читает `record["timeout"]` от плагина `pytest-timeout` | при `pytest-own` — нет, остаётся только таймаут стороны (`two_sided.py:236-237`) | AC-6 (группа процессов) | вытекает из строки `-p timeout`, явно не названо |

## Пути обхода гейтов

- **О1 (Ф1).** Буквальное исполнение требования 4 для id `--failed` даёт
  зелёный AC-5 на синтетической цели «от корня» и сломанный повтор упавших
  на реальном проекте с `workdir`.
- **О2 (Ф2).** Учебный проект AC-5 с приманкой `<корень>/tests` (чтобы
  доказать, что она не собирается) проходит проверку `:1172` — тест
  зелёный, а sled без `<корень>/tests` получит «tests/ нет в worktree» на
  автогейте, гейте мержа и `suite-run`.
- **О3.** `PYTHONPATH` двустороннего прогона (`two_sided.py:230-231`)
  склеивается из каталога плагина и `PYTHONPATH` пульта. Требование 5
  разрешает «переменные плагина» — разработчик вправе оставить хвост
  `PYTHONPATH` пульта, и AC-2 его не поймает, если маркер не кладётся в
  `PYTHONPATH`. Нужно уточнение: при `pytest-own` `PYTHONPATH` = только
  каталог плагина (плюс `test_profile.env`, если там задан).
- **О4 (наблюдение, не отклонение — так велит ТЗ).** Свежий `HOME` на
  каждый прогон лишает `uv run` кэша (`~/.cache/uv`): в scratch-деревьях
  гейта мержа, двустороннего прогона и `suite-run` без `.venv` зависимости
  будут скачиваться заново каждый прогон. Обходится `UV_CACHE_DIR` в
  `test_profile.env` — уместно учесть в D2.

## Вердикт

**concerns.** Решения Оператора №1 внесены полностью. Расхождений с ТЗ
нет. Отклонения, которые решаются на гейте правкой формулировок:

1. Ф1/О1 — требование 4, п.3 D0-2 и AC-5: id упавших `suite-run --failed`
   отсчитаны от rootdir pytest, а не от корня репозитория
   (`acceptance.py:1452-1465`, `suite_run.py:217`, `:550`, `:570`). Перевод
   «от корня к `workdir`» их ломает. Предложение: id из вывода pytest
   передавать без перевода, переводить только пути, которые пульт
   получает от корня репозитория (долгоживущие файлы, планка, цели
   `plank-run`).
2. Ф2/О2 — требование 4: не сказано, что проверка `root/"tests"`
   (`acceptance.py:1172-1174`) при `pytest-own` идёт по `long_lived_dir`
   под `workdir`; строки матрицы для `FULL_SUITE_NO_TESTS` нет.
3. Ф3 — требование 7 и AC-9: `amend.py:715-718` запускает прогон из
   `config.ROOT` (`cwd` не передан); «только передача профиля» не даёт
   выполнить AC-9 (`cwd` = `workdir`). Нужно решение: разрешить в
   `amend.py` передачу `cwd` рабочей копии для внешнего проекта либо
   вывести этот путь из AC-9.
4. Ф4 — требование 9, AC-1, критерий D0-1: у `run_plank`
   (`acceptance.py:923`) и `two_sided._run_side` (`two_sided.py:222`) нет
   параметра `command`; фиксация «по пути `command=[python3,-m,pytest]` до
   правки» для них не определена. Предложение: для них фиксируется один
   путь (сегодняшний), второй добавляется в D0-2 вместе с приёмом
   профиля.
5. О3 — требование 5: состав `PYTHONPATH` двустороннего прогона при
   `pytest-own` (`two_sided.py:230-231`) не задан.
6. Матрица: нет строк о ключе повторного использования
   (`acceptance.py:1609-1640`) и о классификации таймаута теста
   двустороннего прогона (`two_sided.py:204-205`) — желательно, не
   блокирует.
