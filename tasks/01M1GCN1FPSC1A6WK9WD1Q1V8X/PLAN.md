---
task: 01M1GCN1FPSC1A6WK9WD1Q1V8X
type: plan
author_role: developer
status: ready
schema_version: 3
---

# PLAN: Лимиты пакетов контекста и гейт ёмкости диффа ревью

## Подход

Новый модуль `orchestrator/context_package.py` несёт всю дисциплину
размера как чистые функции без побочных эффектов — общий слой для
`brief.developer_brief` и `review.review_package`:

- `render_component(label, text)` — заголовок компонента: путь, размер,
  sha256 (AC-1), либо путь, размер, причина пропуска, когда компонент
  крупнее `config.CONTEXT_FILE_MAX_BYTES` (AC-2/AC-3).
- `split_into_parts(text)` — деление текста на части по границам строк,
  каждая не крупнее `config.CONTEXT_PART_MAX_BYTES` (AC-5); жадное
  накопление строк, строка крупнее потолка целиком открывает свою часть
  (доказано юнит-тестом на строке 300 КБ).
- `discipline(text)` — итоговая сборка: под потолком части — текст как
  есть, крупнее — пронумерованные части с sha256 каждой (AC-6/AC-9),
  инструкция «прочитать все части по порядку» (AC-7), без потери хвоста
  (AC-10). Части, которые несёт манифест (для AC-6), — чистые срезы
  исходного текста; заголовки «--- ЧАСТЬ N/M ---» в возвращаемом тексте —
  только разметка для роли, не часть самих частей, поэтому конкатенация
  срезов побайтово равна целому независимо от разметки.

`review.py`: `artifact_part`/`artifact_text` получают ту же дисциплину
компонента (AC-1/AC-2) через `context_package.render_component`-подобную
логику (встроена в `artifact_part`, т.к. там уже есть источник-note
WORKTREE_NOTE, который нужно сохранить в заголовке). `truncate_diff` и
`truncate_package` удалены целиком — единственная точка усечения
заменена одним вызовом `context_package.discipline` над уже собранным
телом пакета (diff включён в это тело как обычная часть, поэтому
деление diff'а — частный случай деления всего пакета, а не отдельная
дисциплина, что закрывает и AC-8/AC-9 без специального кода для diff).

`brief.py`: новая `_manifest_component` — та же роль, что старая
`_journal_component` (журналирует sha256 шагом), но рендерит компонент
через `context_package.render_component`. `_journal_component` и её
потребители (analyst/test_author через `_answer_component`/
`_questions_component`) не трогаются — SPEC «Не входит» явно исключает
опись для analyst/test_author, а `_answer_component` получила необязательный
параметр `render`, чтобы developer мог передать `_manifest_component`, не
дублируя логику поиска последнего ANSWER-n.md. `developer_brief` в конце
прогоняет собранный документ через `context_package.discipline`.

Алерт AC-21/AC-22 — отдельная функция `_handle_map_size_alert`,
вызывается только для `docs/codebase-map.md` внутри `developer_brief`
(не общая часть `context_package`, т.к. только карта — «всегда
включаемый» компонент; SPEC явно ограничивает алерт этим одним
компонентом). Паттерн открытия/авто-закрытия — тот же, что
`doctor._auto_ack_gone` (T035/T088), но реализован локально в brief.py:
`doctor.py` импортирует `runner.py`, который импортирует `brief.py` —
импорт `doctor` из `brief.py` дал бы цикл.

Гейт ёмкости (AC-12..AC-16) — новая функция `fsm_advance.
_capacity_gate_refuses`, вызывается в `fsm_advance.in_dev` между сверкой
свежести ветки (`fsm._pull_main_or_escalate`) и финальным
`store.set_state(..., "review", ...)`: тот же расчёт, что «полный»
`diff_type` ревью-пакета — `review.git_diff_part(config.MAIN_BRANCH,
t["branch"])` без флагов. Модуль `review` импортирован в `fsm_advance.py`
через `from .review import git_diff_part as _review_git_diff_part`, не
`from . import review` — этот же модуль уже определяет функцию `review`
(обработчик состояния `review`), и `from . import review` тут же
переопределился бы этой функцией, пряча модуль (поймано юнит-тестом до
коммита — `AttributeError: 'function' object has no attribute
'git_diff_part'`).

## Шаги

1. `orchestrator/config.py` — три именованные константы:
   `CONTEXT_FILE_MAX_BYTES = 131_072`, `CONTEXT_PART_MAX_BYTES = 65_536`,
   `REVIEW_SNAPSHOT_DIFF_MAX_BYTES = 262_144`; удаление
   `REVIEW_DIFF_MAX_LINES`/`REVIEW_PACKAGE_MAX_BYTES` (заменяемая
   дисциплина).
2. Новый `orchestrator/context_package.py` — `sha256_of`,
   `render_component`, `split_into_parts`, `discipline`.
3. `orchestrator/review.py` — `artifact_part` несёт опись/пропуск
   компонента; `truncate_diff`/`truncate_package` удалены;
   `review_package` собирает тело и один раз прогоняет его через
   `context_package.discipline`; `package_note` меняет «усечён» на
   «поделён на N частей».
4. `orchestrator/brief.py` — `_manifest_component`, `_handle_map_size_alert`
   (AC-21/AC-22), `_answer_component(..., render=...)`,
   `developer_brief` использует всё это и завершает сборку `discipline`.
5. `orchestrator/fsm_advance.py` — `_capacity_gate_refuses` + вызов в
   `in_dev` перед переходом в `review`.
6. `skills/coding-standards.md`, `skills/review-checklist.md` — раздел
   протокола описи (части по порядку / не перечитывать включённое /
   читать исключённое адресно), мандат ТЗ требование 7.
7. Тесты: `tests/test_review_package.py` — удалены тесты старого
   усечения, добавлены тесты `context_package`/`render_component` и
   дисциплины частей на самом пакете; `package_note`/`note_of` без
   `truncated`/`over_bytes`. Приёмочные тесты задачи (AC-1..AC-22) —
   были залочены test_author, код подгонялся под них без правки текста
   тестов.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (опись) | 2, 3, 4 |
| 2 (константы) | 1 |
| 3 (дисциплина частей) | 2, 3, 4 |
| 4 (diff той же дисциплиной, замена усечения) | 2, 3 |
| 5 (гейт ёмкости) | 1, 5 |
| 6 (инкрементальный diff — без изменений точки отсчёта) | 3 (не тронуто) |
| 7 (протокол в скилах) | 6 |
| 8 (тесты) | 7 |
| 9 (алерт на пропуск карты) | 4 |

## Влияние на систему

Затронуты: `orchestrator/config.py` (константы — удаление двух старых,
добавление трёх новых), `orchestrator/review.py` (замена усечения),
`orchestrator/brief.py` (новые функции + правка `developer_brief`),
`orchestrator/fsm_advance.py` (новый гейт в `in_dev`), новый
`orchestrator/context_package.py`, `skills/coding-standards.md` и
`skills/review-checklist.md` (мандат ТЗ требование 7). `role_prompt.py`
не тронут — инструкция «читать части по порядку» встроена прямо в текст
пакета/брифа (AC-7 проверяется на самом `review.review_package`, не на
`role_prompt`), формулировка миссии роли не меняется.

Существующий состав включаемых компонентов не изменён (AC-18):
`developer_brief` по-прежнему несёт SPEC/карту/конвенции/ANSWER,
`review_package` — задачу/SPEC/PLAN/прошлый REVIEW/форму/стат-список/
diff — только заголовки компонентов обзавелись размером/sha256 или
причиной пропуска. Инкрементальный diff (T029) не тронут: точка отсчёта
(`prev_sha` vs `config.MAIN_BRANCH`) выбирается тем же кодом, что и до
этой задачи, дисциплина частей применяется уже ПОСЛЕ выбора diff.

Гейт ёмкости — новый обязательный шаг на `in_dev -> review`, не
затрагивает уже пройденные переходы других задач (в БД нет обратного
хода). Не эскалирует и не действует автоматически (AC-14) — задача
остаётся в `in_dev`, решение (разделить задачу или поднять потолок,
только Оператор через ADR-0002) явно оставлено человеку.

Ни один существующий тест/гейт/лимит/guard не ослаблен: `truncate_diff`/
`truncate_package` и их тесты удалены не для смягчения проверки, а
потому что сама проверяемая дисциплина (молчаливое усечение с потерей
хвоста) заменена требованием 4 SPEC — их место заняли более строгие
тесты (никакая строка не теряется, конкатенация частей точна). Полный
прогон `tests/` (1216 тестов) и приёмочные тесты задачи (36 тестов,
AC-1..AC-22) зелёные.

Откат: правки локальны к перечисленным пяти файлам плюс новый модуль —
`git revert` коммитов этой задачи возвращает прежнее поведение
(усечение вместо частей, отсутствие гейта ёмкости) без остаточных
миграций (константы БД/схемы не менялись).

## Риски

- Потолок части (65536 байт) меньше `docs/codebase-map.md` (75 340 байт
  на 02.09.2026) — КАЖДЫЙ бриф разработчика в проде теперь делится на
  части; это заложено в SPEC («Материалы») как ожидаемое поведение, а не
  побочный эффект, но стоит иметь в виду при следующем пересмотре
  потолка.

## Предложения системе
