---
task: 01M4RZB9287PXZ4Y7ZJG7HDR6Y
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Короткий путь файла в строке лога шага роли (`wt:` / `docs:`)

## Подход
Одна общая функция `base.short_log_path(value)` в
`orchestrator/providers/base.py`; оба провайдера зовут её через модуль
(`from . import base` → `base.short_log_path(…)`), поэтому подмена
атрибута модуля действует на обоих (AC-8).

- Строка: только абсолютная, без `config.CANARY_POOL_DIRNAME` в значении
  (свойство детектора `doctor/canary_pool.py:73-83`); разбор по сегментам
  `split("/")` — `.artel` ищется сегментом, не подстрокой. Первый якорь
  слева, давший непустой хвост: `.artel/worktrees/<id>/X` → `wt:X`,
  `.artel/projects/<п>/worktrees/<id>/X` → `wt:X`,
  `.artel/projects/<п>/tasks/<id>/X` → `docs:X`. Вложенная раскладка даёт
  одну замену `wt:tasks/<id>/X`, потому что берётся первый (левый) якорь.
  Пустой хвост, пустой `<id>`/`<проект>`, `logs/`, `state.db`, `repo/` —
  без изменений. `config` импортируется внутри функции (`from .. import
  config`), на уровне модуля — только стандартная библиотека (AC-10).
- Перечень (`changes` Codex): копия, где у словарей со строковым `path`
  он сокращён; прочие элементы — как есть; вход не мутируется. Любое
  иное значение отдаётся как есть (AC-9).
- Claude: `_render_block` берёт `(ключ, значение)` новой
  `_tool_argument_entry` (её зовёт и прежняя `_tool_argument`, поведение
  `ToolCall.argument` не меняется) и сокращает только при ключе
  `file_path` — `command`/`pattern` не трогаются, даже если сами путь
  (AC-4). Сокращение — до среза до `TOOL_ARGUMENT_LIMIT`.
- Codex: `_log_argument(item)` — тот же обход `ITEM_ARGUMENT_KEYS`, что
  `_argument`, но при ключе из `PATH_ARGUMENT_KEYS = ("path", "changes")`
  значение проходит `base.short_log_path` до `_text_of`. `_argument` и
  `ToolCall.argument` не меняются (AC-5, AC-6).
- `report`: в `WRITE_GROUPS` слева от сегмента допустимо `[/:]`; путь,
  начинающийся с `wt:`/`docs:` (`SHORT_PATH_PREFIXES` из констант
  `base`), даёт «н/д» строк — не читается относительно рабочего каталога
  отчёта (AC-12).
- Комментарии: `claude.py` над пределом — заморозка снята задачей в части
  пути файла; `codex.py` — символ и предел у каждого провайдера, путь
  файла — общий `base.short_log_path`; `base.py` (о `log_text`) — общая
  только короткая форма пути (AC-11).

Оценка бюджета SPEC ($45) не пересматривается.

## Шаги
1. `base.short_log_path` + вызовы в `claude._render_block` и
   `codex._tool_call_event`, правка комментариев о формате строки;
   `report.WRITE_GROUPS` и «н/д» для короткой формы; пересборка
   `docs/codebase-map.md` (`python3 scripts/codebase_map.py`). Сделано,
   коммит `8e89a58f`.

Проверено:
- `python3 -m pytest tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py
  tests/test_providers.py tests/test_providers_codex.py tests/test_report.py
  tests/test_agent_log.py
  tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py
  tests/test_01m446x1b7fb8jdmyfp5apwtve_watch_progress.py
  tests/test_doctor_canary_pool.py` — 249 passed, 1 failed:
  `test_ac7_limit_symbol_and_flattening_kept`, на предусловии фикстуры
  (см. «Эскалация»), а не на проверке кода.
- `artel.py plank-run 01M4RZB9287PXZ4Y7ZJG7HDR6Y` — 3 passed, код выхода 0.
- `artel.py suite-run 01M4RZB9287PXZ4Y7ZJG7HDR6Y` №1 — зелёный: прошло
  5149, упало 0, пропущено 2. `test_ac7_…` в нём попал на удачное зерно:
  это лотерея, а не стабильность (см. «Эскалация»).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | долгоживущий файл `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py` (test_author); свойств вне него не осталось |
| 7 | 1 |

## Влияние на систему
- Меняется только `log_text` отметки вызова для пути файла.
  `ToolCall.argument` (ключ метрики трения), результаты вызовов, учёт
  токенов, поток событий, `TOOL_ARGUMENT_LIMIT` = 100 и символ строки
  прежние (AC-6, AC-7).
- Детектор утечки пула канарейки: значение с `.artel-canary` не
  сокращается, подстрока остаётся в логе; `tests/test_doctor_canary_pool.py`
  зелёный.
- `report`: на логах старой формы числа блока test_author прежние —
  регулярные выражения только расширены на «:», а «н/д» добавлено лишь
  для префиксов `wt:`/`docs:`, которых в старых логах нет.
- Гейты, лимиты, права ролей и существующие тесты не тронуты.
- Откат — revert коммита `8e89a58f`.

## Риски
- Старые логи остаются в длинной форме; читатели, разбирающие строку
  вызова (`report`), понимают обе формы.

## Предложения системе
- Класс «предусловие случайной фикстуры, выполненное лишь с некоторой
  вероятностью» (`assertGreater(len(tail), LIMIT)` на случайной длине) в
  долгоживущем файле прошёл валидацию стабом test_author, потому что стаб
  прогнали, видимо, на удачном зерне. Стоит ловить в шаге test_author
  повтором долгоживущего файла с N разными зёрнами
  (`skills/test-authoring.md`).

## Эскалация

**Вопросы** (по блокирующести):

1. Долгоживущий тест
   `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py::ShortLogPathTest::test_ac7_limit_symbol_and_flattening_kept`
   нестабилен из-за своей фикстуры, а не из-за кода. Строки 461-462:
   `tail = self.paths.tail(parts=self.rng.randint(14, 20))`, затем
   `self.assertGreater(len(tail), LIMIT)`. При 14 сегментах по 3-9 символов
   средняя длина хвоста ≈ 100, поэтому предусловие часто ложно. Замер:
   12 запусков подряд дали 11 провалов `AssertionError: 95 not greater than
   100` (и подобные) и 1 проход. Моделирование генератора по 2000 зёрнам —
   ≈68% провалов. Когда предусловие выполнено, тест зелёный на коде ветки.
   Гейт полного набора и CI будут краснеть в большинстве прогонов. Сам
   файл я не правлю: он залочен перечнем сумм.
   - Вариант А (дефолт): правка теста командой `amend-tests` — строить
     хвост, пока он не длиннее предела, например после строки 461
     `while len(tail) <= LIMIT: tail = self.paths.seg() + "/" + tail`.
     Заявка «Ловит мутацию:» и проверки метода не меняются, исчезает
     только вероятностный провал фикстуры.
   - Вариант Б: поднять нижнюю границу числа сегментов (например,
     `randint(20, 26)`: минимум 20·3+19+3 = 82 — тоже не гарантия, хуже А).
   - Дефолт при молчании: А.

**Контекст**: реализация закончена и закоммичена (`8e89a58f`); планка —
3 passed; остальные 249 тестов затронутых модулей и прочие методы
долгоживущего файла зелёные. Провал воспроизводится:
`python3 -m pytest tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py -k ac7 -p no:cacheprovider -q`
(в выводе печатается `зерно: N`).

**Блокирует**: стабильно зелёный полный набор `tests/` и CI ветки, а
значит выход из `in_dev` в `verifying` без лотереи по зерну.
