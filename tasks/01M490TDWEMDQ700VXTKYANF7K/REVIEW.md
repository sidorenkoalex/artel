---
task: 01M490TDWEMDQ700VXTKYANF7K
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: guard --all принимает паспорт задачи артели без frontmatter

## Соответствие SPEC

Фаза A (план): таблица покрытия PLAN полна (требования 1–3); шаг один, по
размеру MR (узкая правка одного файла + карта); подход — признак по имени и
уровню (`is_task_passport`), не по содержимому, с конвенциями не
конфликтует. Отклонение от буквы SPEC (`acceptance_tests/PASSPORT.md`
теперь посторонний файл планки, а до правки шёл в `check` и получал «нет
frontmatter», т.к. `.+\.md` его пускал) прямо требуется AC-4 и описано в
PLAN как ужесточение — принимаю.

Фаза B:

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `scripts/guard.py` `main` (`--all`): паспорт первого уровня убран из списка для `check`; белый список `TASK_ROOT_ALLOWED_MD` и `scan_extraneous_task_root_files` не тронуты — `JOURNAL.md` и `wip/PASSPORT.md` остаются посторонними (AC-2, AC-5); соседний `SPEC.md` проверяется (AC-3); `is_extraneous_acceptance_test_file` называет `acceptance_tests/PASSPORT.md` посторонним (AC-4). |
| 2 | OK | одиночный режим: `is_task_passport(f)` → печать `<путь>: паспорт задачи, не артефакт роли — пропущен`, `check`/`spec_path_errors`/`plan_appendix_errors` не зовутся, код 0 (AC-6); `acceptance_tests/PASSPORT.md` не паспорт — `check` и «нет frontmatter» (AC-7). Признак `path.parent.parent.name == "tasks"` работает и для абсолютных путей; `Path("PASSPORT.md")` и `./PASSPORT.md` паспортом не считаются. |
| 3 | OK | долгоживущий `tests/test_01m490tdwemdq700vxtkyanf7k_passport_guard.py`, 7 методов, у каждого «Ловит мутацию», группа «долгоживущий» — это свойства кода, не факт задачи. Заявки проверены временными мутациями (см. ниже) — каждая заявленная мутация красит свой тест. Повторов в `tests/` разработчик не дописал (SPEC это и требует). |

Системная целостность: существующие тесты не изменены (diff `tests/` пуст,
кроме долгоживущего файла задачи вне diff пакета); гейты и лимиты не
ослаблены — пропуск узок (имя + уровень), прочие проверки на месте; вне зоны
задачи файлов нет (`scripts/guard.py`, `docs/codebase-map.md`); карта
регенерирована (+`is_task_passport`, +секция долгоживущего теста), по
содержимому совпадает с кодом. Откат — revert.

Наблюдение без последствий для мержа (замечанием не заводится): PLAN,
«Риски» и «Предложения системе», утверждает, что
`orchestrator/checkpoint.py::_is_stray_acceptance_test_file` держит
независимую копию регулярки планки и «копии разошлись». Это неверно —
checkpoint с SPEC 01M290PVYG2VJK6442H5BAX9MA делегирует
`guard.is_extraneous_acceptance_test_file` (`orchestrator/checkpoint.py:24-49`,
прочитан ради проверки этого пункта PLAN). Следствие обратное заявленному:
расхождения нет, а автокоммит тоже начнёт считать
`acceptance_tests/PASSPORT.md` посторонним файлом планки — согласованно с
guard и с AC-4, поэтому вреда нет; но в «Влиянии на систему» этот эффект не
назван.

## Замечания

Нет замечаний уровня blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tests/test_01m490tdwemdq700vxtkyanf7k_passport_guard.py tests/test_guard_extraneous_acceptance_files.py tests/test_guard_task_root_subdirectory.py tests/test_checkpoint_stray_acceptance_files.py tests/test_guard_schema.py -q -p no:cacheprovider` — 83 passed, 41 subtests passed.
- `python3 scripts/guard.py --all` на рабочей копии — `GUARD: ок (1502 файлов)`.
- `artel.py plank-run 01M490TDWEMDQ700VXTKYANF7K` — отказ «планки нет: … нет файлов test_*.py»: вся планка задачи — долгоживущий файл в `tests/` (ADR-0020), он прогнан выше.
- Временные мутации `scripts/guard.py` (по одной, код возвращён, `git status` чист), прогон только долгоживущего файла:
  - убрана ветка `PASSPORT.md` в `is_extraneous_acceptance_test_file` → красный `test_ac4` (1 failed);
  - убран пропуск паспорта и в `--all`, и в цикле → красные `test_ac1`, `test_ac3`, `test_ac6`;
  - признак только по имени (без `parent.parent.name == "tasks"`) → красный `test_ac7`;
  - пропуск только в `--all` (без ветки в цикле) → красный `test_ac6`;
  - убран лишь фильтр `--all` (цикл всё равно пропускает паспорт) → 7 passed: фильтр поведенчески избыточен для кода выхода, он только убирает строку-пометку и паспорт из счётчика в выводе `--all`; заявки тестов на это не претендуют, это не дефект.
- CI коммита 831046b1 — зелёный (16 проверок, из пакета).

## Предложения системе

- PLAN этой задачи сослался на «независимую копию» белого списка планки в `orchestrator/checkpoint.py`, которой нет с SPEC 01M290PVYG2VJK6442H5BAX9MA — утверждения «Риски»/«Влияние на систему» о соседних модулях стоит подтверждать `grep` вызова, а не памятью (skills/plan-authoring, класс «устаревшее знание о коде»).
