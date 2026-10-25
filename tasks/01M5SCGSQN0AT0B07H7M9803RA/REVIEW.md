---
task: 01M5SCGSQN0AT0B07H7M9803RA
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Записи внешних проектов — в локальный слой вне репозитория артели

## Фаза A: план
- Таблица покрытия полна: требования 1–14 → шаги 1–8; требование 12 честно закрыто тем, что канарейку не трогали (слой вычисляется от `config.TARGETS`).
- Шаги по размеру — единицы MR (модуль на шаг), не микрооперации.
- Шаг 8 (правка `tests/sandbox.py::RealGitSandbox.setUp`) выходит за «Не входит» SPEC, но авторизован ANSWER-3 п. 1 (вариант (б) вместо (а) ANSWER-2). Строка ANSWER-2 в `ProjectAreaSandbox.setUp` снята по ANSWER-3 п. 2: файла `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py` нет в diff --stat, он равен базе.
- «Влияние на систему» сходится с diff, с одной оговоркой: в пункте «Канарейка и `tests/sandbox.py` не тронуты» про `tests/sandbox.py` написано не то — файл тронут по ANSWER-3. Это неточность формулировки PLAN (шаг 8 её сам и описывает), на код она не влияет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `config.TARGETS_LOCAL_REL` — строка, `targets.local_path()` — `config.TARGETS.parent / …` в момент вызова; новых атрибутов `Path` нет |
| 2 | OK | `merge_local` + `_check_local_sections`: проверяются неизвестный раздел или поле, поле не в своём разделе, `PATH` в `description.env`, отсутствие раздела, плоская запись, чужой компонент, `sandbox`, запись `artel`; в текстах есть путь слоя, запись и поле |
| 3 | OK | `_flatten`/`_with_env`: `<cache>` подставляется только в начале значения `env` описания; `machine.path` без своего раннера даёт отказ с `machine.path` до `check()` (для профиля и единственного компонента; для нескольких компонентов `check()` раннер не требует, отказа там и не нужно) |
| 4 | OK | `_check_local_values` проходит `description`/`policy` на любой глубине, `machine` не проверяет |
| 5 | OK | `load()` = `dict(repo).update(local)`: место ключа сохраняется по репозиторию, новые записи идут следом; репозиторный слой проверяется целиком; при отсутствии файла выдача прежняя; тексты отказов общие (`_read_section`); `core_reference` выбирает слой по требованию |
| 6 | OK | `target()` дописывает хвост про локальный слой; начало текста прежнее |
| 7 | OK | `check(name, entry, source=None)`, по умолчанию текст прежний (AC-5 байт в байт) |
| 8 | OK | `targets_local_layer_check` вызывается только в `else` годного `load()` |
| 9 | OK | `local_layer_digest` — последнее поле со значением `None`; сумма сверяется и при молчании `git status` (ANSWER-1 п. 4); при совпадении суммы лишних процессов нет (AC-14 проверяет `spy.call_count == 1`) |
| 10 | OK | порядок такой: отказы, раскладка, собственная запись текста, разбор, сведение, сверка поле в поле (тип и порядок компонентов тоже), атомарная запись; команды нет в `_ROLE_ALLOWED_COMMANDS` |
| 11 | OK | `LIVE_FILES` и `LIVE_FILE_CONFIG_ATTRS` дополнены |
| 12 | OK | `orchestrator/canary.py` не тронут |
| 13 | OK | после регенерации `scripts/codebase_map.py` карта отличается только строкой `built_at_sha` |
| 14 | OK | `tests/test_acceptance_suite_profile.py`: импорт и первый контекст `sandbox.declared_without_profile("sled")`; утверждения не тронуты (мандат ANSWER-1) |

Неослабление `tests/`: в diff `tests/` два файла. `tests/test_acceptance_suite_profile.py` — только импорт и контекст изоляции, утверждения не менялись. `tests/sandbox.py` — только путь `config.TARGETS` у `RealGitSandbox` (`.artel/targets.yaml` → `.artel/repo-targets.yaml`) и комментарий; посев и данные песочницы не сужены. Обе правки укладываются в мандаты ANSWER-1 и ANSWER-3.

Долгоживущие тесты задачи (4 файла, `Группа: долгоживущий`) проверяют свойства кода, а не факты задачи. Заявки «Ловит мутацию» называют наблюдаемое расхождение; две из них проверены временной мутацией (ниже). Повторов долгоживущих тестов в `tests/` разработчик не добавлял. Ветвлений под литералы фикстур в коде нет.

## Замечания
Blocker и major нет. Ниже наблюдения уровня minor, на вердикт они не влияют и в реестр не заносятся:

- minor — `orchestrator/projects.py` (`_strings`) — повторяет `orchestrator/targets.py::_strings` один в один. Можно звать `targets._strings`, как уже зовутся `targets.cache_dir`/`CACHE_MARK`.
- minor — `orchestrator/targets.py`, `_check_local_values`, условие `field.rsplit(".", 1)[0] in envs` — env-ключ с точкой (`A.B: <cache>/x`) даст ложный отказ «`<cache>` допустим только в начале значения env». Ключи env с точкой на практике редки. Надёжнее сверять префикс `f"{env_field}."` по каждому полю из `envs`.
- minor — `orchestrator/targets.py::core_reference` — для внешнего проекта при локальном слое с пустым `targets:` молча берётся репозиторный слой, а `load()` тот же файл отвергает («раздел 'targets:' пуст»). Это расхождение строгости двух читателей; требование 5 его допускает («проверяется только запись `name`»).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: blocker/major не найдено; minor-наблюдения выше в реестр не заносятся.

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M5SCGSQN0AT0B07H7M9803RA` — отказ «планки нет: в refs/artifacts/… нет test_*.py», pytest не запускался. Все свойства задачи лежат в долгоживущих файлах `tests/`.
- `python3 -m pytest -q -p no:cacheprovider` по четырём долгоживущим файлам `tests/test_01m5scgsqn0at0b07h7m9803ra_{doctor_layer,local_layer,targets_migrate,watch_layer}.py` и `tests/test_acceptance_suite_profile.py` — 67 passed, 6 subtests passed.
- Временная мутация `checkpoint.watch_main_copy`: `layer_changed = False`. `doctor_layer` + `watch_layer` — 3 failed (все три случая `test_ac14_layer_change_raises_watch_alert`), 8 passed. Код возвращён (`git checkout`, `git status` чист).
- Временная мутация `targets._check_local_values`: проверка абсолютных путей отключена (`for section in ()`). `-k ac6` — 6 failed, 1 passed (прошёл как раз `test_ac6_machine_absolute_values_accepted`). Код возвращён.
- `python3 scripts/codebase_map.py` и `git diff` карты — меняется только строка `built_at_sha`, карта свежая. Файл возвращён.
- Если запустить `tests/test_01m5scgsqn0at0b07h7m9803ra_watch_layer.py` отдельно, он падает на сборке: циклический импорт `orchestrator.checkpoint` → `fixation`. Это не дефект задачи: `import orchestrator.checkpoint` с чистого интерпретатора падает так же на коде базы 8fcc989d (выгружен `git archive` во временный каталог). В общем прогоне и в CI файл зелёный.

## Предложения системе
- `orchestrator/checkpoint.py`: `import orchestrator.checkpoint` с чистого интерпретатора падает циклом через `fixation` (на main тоже). Любой тестовый файл, который первым импортирует `checkpoint`, нельзя прогнать в одиночку, а временная мутация «по файлу» из review-checklist даёт ложный результат «ошибка сборки». Стоит завести инвариант «каждый модуль `orchestrator/` импортируется отдельно».
- review-checklist, «Реестр замечаний»: правило «каждое замечание — строка реестра» плохо сходится с «0 blocker/major → approved» и гейтом «все записи accepted». Для minor на первой итерации не сказано, заносить ли их в реестр (если занести, они заблокируют собственный approve).
