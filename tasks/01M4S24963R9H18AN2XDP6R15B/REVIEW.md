---
task: 01M4S24963R9H18AN2XDP6R15B
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Справочник ядра — генератор, настройка проекта, кэш (К-3а)

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–9 → шаги 1–5; шаг 6 (утечка
  флагов `auto._stop_requested`/`_zone_wait_sleeping` между тестами) —
  вне требований SPEC, обоснован красным CI и задевает только `setUp`
  двух тестовых классов, без изменения проверок.
- Шаги — единицы размера MR. Подход (генератор только на stdlib + `ast`,
  поле `targets` тем же приёмом, что `test_profile`, кэш в
  `knowledge/derived/`) с архитектурой не конфликтует; обоснование места
  кэша одной строкой в PLAN есть (требование 5).
- «Влияние на систему» = diff: config (6 констант), targets (поле +
  `core_reference`), два новых модуля, тесты, карта. Защищённые пути,
  гейты, `gitcmd.py` не тронуты. Откат описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `scripts/core_reference.py`: импорты только stdlib (проверено тестом AC-1 по `ast`), разбор только `ast.parse`/`tokenize`; `build` с параметрами `min_uses`, `generator_sha256`; обход `sorted(sources)`; CLI — `git ls-files -z` с отсевом ссылок, без git — `os.walk` с отсевом `.`-каталогов, `__pycache__`, `node_modules`, `venv`; вывод в stdout. |
| 2 | OK | Подсчёт по множеству файлов (`_users`, свой файл исключён); последнее определение (`definitions.pop` + вставка); сигнатура из фрагментов исходника; пример — три ступени по `sorted(files)` и (строка, столбец), длина ≤ 80, только `lineno == end_lineno`; константы только из `constants_module`, `_cut` 400/160, предложение по `[.:;](?=\s)`; очистка Cc `_clean` на тело, шапку и тексты сбоев; шапка несёт все поля. |
| 3 | OK | `_check_reference`/`_reference_module_error` покрывают все случаи AC-9; `core_reference(name)` разбирает файл один раз и зовёт `check` только для записи `name`. |
| 4 | OK | `ls-tree -r -l -z` потоком через `Popen` с пределом вывода и таймером остатка срока; отбор `blob` 100644/100755 `.py`; пределы до `cat-file`; один `cat-file --batch` по уникальным blob с `timeout=remaining`; разбор по длине, `missing` — пропуск; срок проверяется после `cat-file` и в разборе (`DeadlineExceeded`); форма sha — до git. |
| 5 | OK | `projects_root()/<проект>/knowledge/derived/core-reference.md`; `mkstemp` в том же каталоге + `os.replace`; одно чтение с `O_NOFOLLOW|O_NONBLOCK`, `fstat` (не обычный файл/крупнее 4×MAX_BLOB — испорчен); годность — `reference_sha` (настройка, генератор, sha256 тела) + сверка `built_at_sha`; `GENERATOR_SHA256` от `core_reference.__file__` при импорте. |
| 6 | OK | Порядок `NO_AREA` → настройка → кэш → sha; исходы `off`/`fresh`/`cached`/`unverified`/`absent` по SPEC; журнал «справочник ядра: построен» с sha, байтами, записями, длительностью, поводом; внешний `except Exception`. |
| 7 | OK | Алерт `incident` по проекту, источник от `reason`; тексты-константы без sha/времени/размеров (подробности — в `note` и журнал «сбой»); кэш не записан — `fresh` из памяти. |
| 8 | OK | Четыре долгоживущих файла + `tests/test_core_reference.py` (свойства вне SPEC, с заявками «Ловит мутацию»); песочница `ConnRealGitSandbox`, внешние проекты с другим деревом; сторож AC-14 по рабочему дереву. Повтора долгоживущих свойств в `tests/test_core_reference.py` нет. |
| 9 | OK | `docs/codebase-map.md` по содержимому совпадает с генерацией по коду ветки (сверка без строки `built_at_sha`, см. ниже). |

## Замечания
Нет замечаний уровня blocker/major/minor, требующих итерации.

Наблюдения без замечания (вкус, на усмотрение К-3б — в реестр не заношу):
- `orchestrator/reference_cache.py` (`_build`, вызов `store.journal(… BUILT_ACTION …)`) не завёрнут в `suppress`, в отличие от `_absent`/`_alert`: сбой записи журнала после удачной сборки уйдёт во внешний `except` и превратит готовый текст в `absent` «внутренний сбой». Контракт «не бросает» соблюдён; сценарий — только отказ БД.
- `ALERT_SOURCES.get(reason, …brief)` молча принимает неизвестный `reason` как `brief`; SPEC допускает только два значения, вызывающего кода пока нет.
- `_usage` считает `x.<стем>.<имя>` (через `_tail`) обращением к модулю — например `self.store.journal` засчитается `store.journal`; SPEC формулирует правило как «обращение `<модуль>.<имя>`», так что это допустимое прочтение, но порог может завышаться на объектах-полях с именем модуля.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved — все 9 требований и 15 критериев реализованы так, как требует SPEC.
Тесты сверены с заявками, существующие тесты не ослаблены: в `tests/` diff
содержит только добавленные строки (`git diff 8bf731c8...HEAD --stat --
tests/` — одни insertions; два `setUp` возвращают модульные флаги и ни
одного утверждения не меняют).

## Проверено исполнением
- `python3 -m pytest tests/test_01m4s24963r9h18an2xdp6r15b_generator.py tests/test_01m4s24963r9h18an2xdp6r15b_cli.py tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py tests/test_01m4s24963r9h18an2xdp6r15b_cache.py tests/test_core_reference.py -p no:cacheprovider -q` — 57 passed, 135 subtests passed (15.8 с).
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4S24963R9H18AN2XDP6R15B` — 2 passed, код выхода pytest 0.
- `python3 -m pytest tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py tests/test_auto_cycle.py -p no:cacheprovider -q` (файлы шага 6) — 71 passed, 53 subtests passed.
- Свежесть карты без записи на диск: `scripts.codebase_map.build_modules` + `render` в памяти, сравнение с `docs/codebase-map.md` без строк `built_at_sha:` — совпадает («fresh»).
- `git grep "from scripts import" -- orchestrator/` — импорт `from scripts import core_reference` в `reference_cache.py` повторяет принятую конвенцию (`from scripts import guard` в десяти модулях пульта).
- `git diff 8bf731c8...HEAD --stat -- tests/` — только добавления, удалённых или изменённых утверждений нет.

## Предложения системе
- Форма REVIEW.md требует заносить в реестр каждое замечание, включая minor, а гейт `review -> verifying` не пропускает `approved`, пока хоть одна запись реестра не `accepted`. Из-за этого замечание уровня «вкус» либо отправляет задачу на лишнюю итерацию, либо уходит в свободный текст без реестра. Стоит разрешить в skills/review-checklist.md статус `accepted` для minor, заведённых при аппруве, или отдельный раздел «наблюдения» вне реестра.
