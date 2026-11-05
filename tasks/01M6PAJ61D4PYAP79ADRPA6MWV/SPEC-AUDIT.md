---
task: 01M6PAJ61D4PYAP79ADRPA6MWV
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/test_01m5n8asj63zkf3m9etc7a3p5v_plank_layout_names.py; в) пути-признаки (гейты): orchestrator/advance_gates/acceptance.py, orchestrator/advance_gates/outcome_integrity.py, orchestrator/advance_gates/test_integrity.py, orchestrator/advance_gates/two_sided.py; г) budget_usd 60 ≥ 45; д) ТЗ ссылается на ADR: ADR-0023.
spec_sha: 79b39475f2bea9f1a14cd85abce22ea798c1724d
schema_version: 5
---

# SPEC-AUDIT: Ядро раннера compose

Это пятый визит аудита. Прошлый вердикт (SPEC 49608e20) назвал два
отклонения:
- канал id задачи не доходит до трёх мест вызова вне зон;
- объём «только передачи» в `outcome_integrity.py` (`_rerun`).

Оператор снял оба решениями пятого круга 1–2 (решение гейта №4). SPEC
вносит их с пометкой «решение пятого круга N». Новая находка вытекает из
решения пятого круга 1: у `run_plank` параметр `task_id` уже есть, но
означает он другое.

## ТЗ и SPEC

Решения пятого круга внесены так:
- **1 (канал id до всех мест).**
  - Требование 3: SPEC.md:133-150 — `run_repeat` получает параметр
    `task_id`, `advance_gates/acceptance.py:174`, `suite_run.py:607`,
    `:680`, `plank_run.py:267-269`.
  - Зоны во frontmatter (SPEC.md:7) дополнены тремя файлами. В «Не
    входит» (SPEC.md:426-440) их правка ограничена передачей `task_id`.
  - AC-9 (SPEC.md:370) называет повтор с зерном, `suite-run` и
    `plank-run` долгоживущего файла.
- **2 (`_rerun`).** Требование 3: SPEC.md:146-148. «Не входит» —
  SPEC.md:428-433. AC-9 — «перепрогон стороны через `_rerun`».

Решения кругов 1–4 и ТЗ остаются в силе без противоречий. Перенос
требований 1–13 и AC-1…AC-17 из родителя прошлые визиты сверили, других
изменений нет. Требований сверх ТЗ и решений гейта нет.

Расширение зон файлами, которые ТЗ называет «только чтение»
(`suite_run.py`), дают решения Оператора 3.1 и 4.1–4.2. Это не
расхождение с ТЗ.

## Факты против кода

Рабочий каталог — 54fe44ebb. Якоря решения пятого круга подтверждены:
- `advance_gates/acceptance.py:174` —
  `acceptance.run_repeat(seeded, run_cwd, command=command)` внутри
  `_seed_repeats_escalate` (:153);
- `acceptance.py:1731-1732` — `run_repeat(files, cwd, command=None)`,
  параметра id нет. Ветка отчёта — `_report_run` на :1749;
- `suite_run.py:607` (копия базы) и `:680` (дерево прогона) —
  `acceptance.run_full_suite(..., command=command, ...)` без id;
  `run_full_suite` :2338 — параметра id нет, ветка отчёта
  `_run_full_suite_reported` → `_report_run` :2518;
- `plank_run.py:267-269` — `run_plank([target_arg], code_dir,
  profile=own)` без `task_id`;
- `outcome_integrity.py:430` — `_rerun(profile, trees, red, history, …)`
  без id; вызовы :757 и :972; `report_run` :445 и :736;
- `report_run = _report_run` (`acceptance.py:3706`): параметр узла сразу
  доступен и публичному имени.

**Не подтвердилось по смыслу: «у `run_plank` параметр `task_id` уже
есть»** (SPEC.md:144-145). Параметр есть (`acceptance.py:2042-2043`), но
означает «цели лежат в планке задачи `tasks/<id>/acceptance_tests`»
(докстринг `acceptance.py:2056-2061`: «Не передан — цели как есть
(долгоживущий файл, раннер пульта)»). С `task_id` `run_plank` строит план
выкладки (`:2068-2069`) и входит в `_laid_plank` (:2072). У профиля с
`long_lived_dir` под `workdir` (`plank_layout.layout_mode`,
`plank_layout.py:41-47`) это `plank_layout.plank_layout`
(`plank_layout.py:107-134`). Он делает `shutil.copytree(tests_dir, …)`
каталога `<code_dir>/tasks/<id>/acceptance_tests`. На пути долгоживущего
файла этого каталога в рабочей копии нет («`tasks/<id>/` рабочей копии
этот прогон не трогает», `plank_run.py:262-263`).

Проверено опытом во временном каталоге: `shutil.copytree` отсутствующего
каталога бросает `FileNotFoundError`. Значит, передача `task_id` в этот
вызов «как есть»:
- у `pytest-own` роняет `plank-run` долгоживущего файла исключением.
  Существующий тест
  `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py::…test_ac5_long_lived_path_runs_by_own_profile`
  (:362; профиль `pytest-own`, `long_lived_dir` под `workdir`, :151-158)
  при безусловной передаче покраснеет;
- у `compose` даёт тот же путь, если `compose` идёт через `_own`
  (SPEC.md:81-83 этого и требует: «`compose` проходит те же … ветки, что
  `pytest-own`: … `acceptance._own`»; `workdir` обязателен).

Существующие тесты на прочие изменённые сигнатуры не ломаются:
- подмены `acceptance.run_full_suite` в `tests/` — `MagicMock`
  (`side_effect`, `return_value`, `wraps`) и лямбда
  `lambda root: …` (`tests/test_fsm_merge_gate_remote_branch_cleanup.py:190-191`);
- лямбду зовёт `fsm_merge_gate` через `full_suite`, а не `suite_run`.
  Тесты `suite_run` читают у вызова только `kwargs["limit"]`
  (`tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py:141-142`);
- прямые вызовы `run_repeat` в тестах
  (`tests/test_01m52eedeyv14658x8vfnhcw8k_launch_places.py:292`) идут
  без `task_id`, необязательный параметр их не задевает.

Вне зон без id остаётся `mutation_run.py:516` (`run_full_suite`). Для
`compose` это отказ запуска, но мутационный прогон в контейнере назван
в «Не входит» (SPEC.md:422). Это не отклонение.

Опытом не проверено (программы `docker` на машине шага нет): форма вывода
`config --format json`. SPEC сам помечает её «опытом не проверено», на
правила решений она не влияет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация | Тест до кода |
|---|---|---|---|
| AC-1 | да | `compose` не в `PROFILE_RUNNERS`; умолчание `command` не подставлено; `machine.path` отказан | красный (`TargetsError`), безопасен |
| AC-2 | да | снятая обязательность поля; две пары `compose_mount` приняты; `env` плоской записи принят | красный, безопасен |
| AC-3 | да | нет `--project-directory`/`-w`/`--rm`; отчёт вне монтирования; итог по коду выхода | красный: `docker` не зовётся |
| AC-4 | да | `ports` не сняты; `default` без `internal`; нет метки; шаблон не перезаписан | красный |
| AC-5 | да | снято правило сокета или обхода; пропущен `tcp://`; принят ошибочный `config` | красный; зависание — `exec sleep` при малом пределе |
| AC-6 | да | префикс без `_`; `name:` тома не проверен | красный |
| AC-7 | да | путь не переведён; путь вне монтирования прошёл | красный |
| AC-8 | да | нет `down` на одном из исходов; нет `kill`; `up` не ограничен остатком; `run` при остатке ≤ 0; запись не в `store.journal`; `context inspect` без предела | красный; зависания ограничены подменёнными константами |
| AC-9 | да | постоянный id прогона; имя без id; id не передан в `run_repeat`/`run_full_suite`/`run_plank`/`_rerun` (отказ места вместо прогона). Ловит и падение `plank-run` долгоживущего файла `compose` (вердикт, п. 1) | красный (`TypeError` на `task_id` либо отказ) |
| AC-10 | да | `_own_profile` не расширен → `-p <плагин>`, `PYTHONPATH` | красный |
| AC-11 | да | `os.environ` целиком; `PATH` вызывающего | красный |
| AC-12 | да | откат на `~/.docker` пульта; фон без `ARTEL_ROLE` не распознан | красный |
| AC-13 | да | удалён весь `.artel-report`; нет `info/exclude`; неверный порядок проверок | красный, git — песочница |
| AC-14 | да | слагаемое не добавлено | красный |
| AC-15 | да | поле или константа перекрытия не в ключе | красный |
| AC-16 | да | поля `compose_*` в ключе безусловно; `task_id` меняет argv прежних профилей. Безусловная передача `task_id` в `run_plank` долгоживущего файла у `pytest-own` ловится прежним тестом (см. «Факты»), не самим AC-16 | зелёный с рождения (страж) |
| AC-17 | да | нет пропуска при `CI`; проба без предела 10 с | пропуск |

Опасных форм нет: `docker` подменён, процессы ограничены, git идёт в
песочнице.

## Зоны

- Требования 1–13 укладываются в зоны SPEC (SPEC.md:7). Правка
  `run_plank` (новый смысл канала id долгоживущего файла, вердикт п. 1)
  лежит в `acceptance.py` — в зонах.
- Ограничение «в этих четырёх файлах — только передача id»
  (SPEC.md:149) выполнимо: в `plank_run.py:267` достаточно передать
  `task_id=task_id`, если `run_plank` различит два смысла.
- Защищённые пути не затронуты: `config.py` вне `PROTECTED_PATHS`.
  Песочница ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `workdir`/`env` только при `pytest-own` | `targets.py:1096-1103`, `:1258-1265`; `tests/test_01m52eedeyv14658x8vfnhcw8k_profile_runner.py:187-205` | да | AC-1, AC-2 | ок |
| `machine.path` только при `pytest-own` | `targets.py:755-773` | да; у `compose` — только `PATH` вызова `docker` | AC-1, AC-11 | ок |
| обязательность `command` | `targets.py:1087-1092` | да для прочих раннеров | AC-2 | ок |
| запрет повторов и `layers` | `targets.py:1194-1222`, `:1237-1239` | да | AC-2 | ок |
| ключ итога с отчётом | `acceptance.py:3069-3096`; `tests/test_report_argv_rerun_ban.py:98-130` | да | AC-15, AC-16 | ок |
| сигнатуры `_report_run`/`report_run`, `run_repeat`, `run_full_suite`, `_rerun` (новый `task_id`) | `tests/test_01m5n8asj63zkf3m9etc7a3p5v_plank_layout_names.py:331-373`; подмены — `MagicMock`/лямбды без `suite_run` | да | прежние тесты; AC-9, AC-16 | ок |
| `plank-run` долгоживущего файла без выкладки планки | `acceptance.py:2056-2073`; `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py:362` | да, если `task_id` для имени проекта не включает выкладку; при передаче через нынешний параметр — нет (`FileNotFoundError`) | прежний тест; AC-9 | вердикт, п. 1 |
| повтор долгоживущих файлов с зерном | `advance_gates/acceptance.py:153-180`; `tests/test_acceptance_seed_repeat.py:82-116` | да | AC-9 | ок |
| чистое окружение прогона | `acceptance.py:189-211` | да, строже | AC-11, AC-12 | ок |
| двусторонний прогон по профилю | `test_integrity.py:1679`, `:1784`; `two_sided.py:340-359` | да | AC-10 | ок |
| граница гейта исходов | `advance_gates/acceptance.py:213-218` | да | AC-10 | ок |
| сокет Docker не передаётся (ADR-0023) | нового кода нет | да | AC-5 | ок |
| стенд «всегда снимается» | нового кода нет | да; свидетельство — `store.journal` | AC-8 | ок |
| предел времени места | `config.ACCEPTANCE_TIMEOUT_SEC`, пределы компонентов | да; соотношение задано | AC-8, AC-14 | ок |

Раздела «Меняемое поведение» нет (SPEC.md:441-442). Поиск в `tests/`
это подтверждает при условии, что `plank_run` не меняет прогон
долгоживущего файла `pytest-own` (вердикт, п. 1).

## Пути обхода гейтов

1. **Канал id из имени `cwd`.** Решение 3.1 требует явного аргумента, и
   теперь он доходит до всех мест. Если `run_plank` не различит смыслы
   `task_id`, исполнитель может для `compose` на пути долгоживущего файла
   вывести id из имени `code_dir` (рабочая копия названа по id задачи)
   вместо передачи. На рабочей копии AC-9 пройдёт, буква «явный
   аргумент» будет нарушена. Закрывается пунктом 1 вердикта.
2. Иных путей не найдено: AC-9 перечисляет каждое место, и отказ
   «`compose` без `task_id`» на любом из них тест AC-9 ловит.

## Вердикт

**concerns.** Оба отклонения прошлого визита сняты решениями пятого
круга 1–2. Утверждения решения №4 о коде верны:
`advance_gates/acceptance.py:174`; `suite_run.py:607`, `:680`;
`plank_run.py:267-269`; `acceptance.py:1731`; `outcome_integrity.py:430`,
`:757`, `:972`. Существующие тесты от новых необязательных параметров
`run_repeat`, `run_full_suite`, `_rerun` и `report_run` не ломаются.

Отклонения:

1. **У `run_plank` параметр `task_id` значит «цели в планке задачи», а
   не «id для имени проекта».** SPEC.md:143-145 ведёт канал id
   долгоживущего файла через «уже имеющийся» параметр `task_id`. По коду
   (`acceptance.py:2056-2073`, `plank_layout.py:107-134`) этот параметр
   включает выкладку планки `tasks/<id>/acceptance_tests`. На пути
   долгоживущего файла этого каталога нет, и `shutil.copytree` бросает
   `FileNotFoundError` (проверено опытом). Следствия:
   - безусловная передача в `plank_run.py:267` ломает прежний тест
     `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py:362`
     (`pytest-own`, `long_lived_dir` под `workdir`) и требование 11;
   - передача только для `compose` роняет тем же путём сам `plank-run`
     долгоживущего файла `compose` (через `_own`, SPEC.md:81-83), и AC-9
     покраснеет.

   Решается в зоне `acceptance.py`, но SPEC этого не говорит. Варианты
   для Оператора:
   - а) (дефолт) `run_plank` получает отдельный необязательный параметр
     для id имени проекта (или признак долгоживущего файла), не
     включающий выкладку; `plank_run.py:267` передаёт его — по-прежнему
     только передача id;
   - б) `task_id` в `run_plank` для `compose` на пути долгоживущего
     файла не включает выкладку (смысл параметра меняется только у
     `compose`), и это записано в SPEC;
   - в) явно сказать в SPEC, что `plank_run.py:267` передаёт `task_id`
     только при профиле `compose`, а выкладку у `compose` без планки
     `run_plank` пропускает.
