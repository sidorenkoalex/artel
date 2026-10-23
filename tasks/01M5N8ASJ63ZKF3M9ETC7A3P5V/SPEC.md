---
task: 01M5N8ASJ63ZKF3M9ETC7A3P5V
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/plank_layout.py, orchestrator/acceptance.py, orchestrator/suite_run.py, orchestrator/advance_gates/two_sided.py, orchestrator/advance_gates/outcome_integrity.py, orchestrator/advance_gates/tests_writing.py, orchestrator/plank_run.py, orchestrator/amend.py, orchestrator/pull.py, orchestrator/doctor/machine_load.py, docs/codebase-map.md, tests/
budget_usd: 30
---

# SPEC: CR-8, этап 1 — самодостаточная часть выкладки планки в `orchestrator/plank_layout.py`; публичные имена для закрытых имён `acceptance`, которые берут другие модули

## Контекст
Ревизия кода CR-2026-10-22-8 (`docs/audits/code-revision-2026-10-22.md`,
бэклог `docs/backlog.md:358`) нашла две вещи. Первая: в `orchestrator/acceptance.py`
живут и раннер внешнего проекта, и выкладка планки. Вторая: восемь модулей
берут закрытые имена `acceptance`. Оператор 23.10.2026 разделил находку на
два этапа. Этот этап делает три вещи. Он выносит самодостаточную часть
блока выкладки (`acceptance.py:1200–1494`) в отдельный модуль, прежние
имена при этом остаются реэкспортом. Он даёт публичные имена закрытым
именам, которые берёт код других модулей. И он закрывает пробел теста
задачи замера: сбой запуска потока чтения времени
(`acceptance._durations_reader`, ленивый импорт `suite_durations` вне
`try`, :2862). Блок раннеров (:37–948) этап не трогает. Тесты подменяют
его имена в глобалах `acceptance`, поэтому перенос требует перенацелить
подмены, а это мандат Оператора и этап 2.

Сверено с `origin/main` 84c784aa. Номера строк ниже взяты из ТЗ и
относятся к этой базе.

## Требования

1. Создаётся новый модуль `orchestrator/plank_layout.py`. В него переносится
   только самодостаточная часть блока выкладки, всё остальное остаётся на месте:
   - константы `PLANK_LAYOUT_DIR`, `PLANK_LAYOUT_EXCLUDE`,
     `LAYOUT_OUTSIDE_NOTE`, `PLANK_ABSENT_NOTE`, `NO_PLANK_LAYOUT`,
     `LAYOUT_NOT_NORMAL`, `LAYOUT_ID_NOT_LAST`, `LAYOUT_OUTSIDE_WORKDIR`,
     `LAYOUT_PARENT_NOT_HIDDEN`, `LAYOUT_PARENT_TRACKED`, `_LAYOUT_ID`;
   - функции `_inside`, `_layout_mode`, `_layout_root`, `_exclude_layout`,
     `_exclude_pattern`, `_drop_layout`, `_plank_layout`, `_uses_plank_layout`,
     `_layout_parent`, `_drop_component_layout`;
   - классы `_PlankPlan`, `_Laid`.

   Тексты отказов и поведение остаются побайтно прежними. Публичные имена
   без подчёркивания получают `exclude_layout`, `exclude_pattern`,
   `layout_mode`, `layout_root`, `drop_layout`, `plank_layout`,
   `uses_plank_layout`, `drop_component_layout`, `PlankPlan`, `Laid`.
   Остальные функции (`_inside`, `_layout_parent`) и `_LAYOUT_ID` остаются
   закрытыми. Константы без подчёркивания сохраняют свои имена.
   `plank_layout` не импортирует `acceptance`.
2. Несамодостаточная часть остаётся в `acceptance.py`: `_layout_ignore`,
   `_layout_check`, `_plank_plan`, `_component_layout`, `_laid_plank`. Она
   зовёт перенесённое через прежние имена модуля `acceptance`.
3. `acceptance.py` сохраняет все прежние имена перенесённой части
   реэкспортом того же объекта (`_exclude_layout = plank_layout.exclude_layout`,
   константы — тем же объектом). Поэтому продолжают работать
   `acceptance.PLANK_LAYOUT_DIR`, `acceptance.PLANK_LAYOUT_EXCLUDE`,
   `acceptance.LAYOUT_OUTSIDE_NOTE`, `acceptance._exclude_layout` и все
   остальные прежние имена из списка требования 1. Вызовы внутри
   `acceptance.py` (`run`, `collect`, `drop_from_code_copy`, `run_plank`,
   `_component_target`, `_report_argv`, `run_full_suite`, `_link_deps`) идут
   через прежние имена модуля `acceptance`.
4. В `acceptance.py` объявляется публичное имя для каждого закрытого имени
   `acceptance`, которое берёт код других модулей. Публичное имя ссылается
   на тот же объект (`reported = _reported`), закрытое имя остаётся.
   Таких закрытых имён тринадцать: `_reported`, `_own`, `_full_suite_outcome`,
   `_own_cwd`, `_own_target`, `_place_command`, `_place_env`,
   `_run_in_session`, `_report_run`, `_report_suite_result_key`,
   `_task_own_profile`, `_component_name`, `_process_snapshot`.
   Вызывающие модули переходят на публичное имя:
   - `suite_run.py`;
   - `advance_gates/two_sided.py`;
   - `advance_gates/outcome_integrity.py`;
   - `advance_gates/tests_writing.py`;
   - `plank_run.py`;
   - `amend.py`;
   - `pull.py`;
   - `doctor/machine_load.py` (через пакет — `doctor.acceptance`).

   Исключение — `_last_full_suite_metrics`. Это изменяемая переменная модуля:
   `acceptance` переприсваивает её через `global`, её пишут
   `suite_run.py:678` и тест. Публичного имени-копии она не получает,
   обращения к ней остаются прежними.
5. Разработчик повторяет на базе ветки поиск подмен тестами имён из
   списка требования 4, во всех формах:
   - `mock.patch.object(<…>.acceptance, …)`;
   - `mock.patch("orchestrator.acceptance.…")`;
   - присваивание;
   - `monkeypatch.setattr`.

   Результат поиска разработчик прикладывает к PLAN. Если подмена имени из
   списка найдена, это имя добавляется в исключения: вызывающий модуль
   остаётся на закрытом имени, путь вызова не меняется.
6. Не меняются:
   - логика вердикта `full_suite`, `run_full_suite` и
     `_report_suite_result_key` (кроме объявления публичного имени);
   - блок раннеров `acceptance.py:37–948` — ни место, ни имена;
   - argv и окружение прогонов;
   - ключ кэша итога.
7. В `acceptance._durations_reader` ленивый импорт `suite_durations`
   переносится внутрь `try`. Если запуск потока чтения времени сбоит,
   исключение наружу не выходит, а прогон идёт как без потока.
8. Новые тесты кладутся только новыми файлами в `tests/`. У каждого теста
   есть строка «Ловит мутацию:». Стиль — по действующим скилам (ADR-0027
   ещё не исполнен). Нужны тесты:
   - (а) прежние имена `acceptance` перенесённой части — тот же объект, что
     имена `plank_layout` (перебор по списку требования 1);
   - (б) `plank_layout` не импортирует `acceptance` (разбор `ast`);
   - (в) публичные имена требования 4 — тот же объект, что закрытые;
   - (г) ни один модуль `orchestrator/` и `scripts/` не обращается к
     закрытому имени модуля `orchestrator.acceptance`, кроме константы
     исключений `{"_last_full_suite_metrics"}` (плюс имена, добавленные по
     требованию 5). Модуль узнаётся разбором импортов, формы:
     - абсолютный импорт: `from orchestrator import acceptance`,
       `import orchestrator.acceptance`;
     - относительный импорт, разрешающийся в `orchestrator.acceptance`:
       `from . import acceptance` в `orchestrator/*.py`,
       `from .. import acceptance` в подпакетах `orchestrator/advance_gates/`,
       `orchestrator/doctor/`. Тест строит разрешение относительного
       импорта по пути файла;
     - обращение через пакет `doctor.acceptance`.

     `advance_gates.acceptance` (`from .acceptance import …` внутри
     `advance_gates`) — другой модуль и не считается. Тест ловит
     мутацию «вызывающий модуль оставлен на закрытом имени»;
   - (д) требование 7, два сценария. Условие запуска потока: раннер пульта
     (`profile is None`) и прогон с логом (`run_full_suite(..., log=…)`).
     Тест сначала убеждается, что без сбоя файл времени при этом условии
     появляется (иначе сценарий холостой).
     - Сбой запуска потока: подмена `suite_durations.Reader.start` (или
       конструктора `Reader`) бросает `RuntimeError`. «Ловит мутацию:» —
       убран перехват исключения при запуске потока.
     - Сбой импорта `suite_durations`: на время прогона
       одновременно `sys.modules["orchestrator.suite_durations"] = None`
       и снят атрибут `suite_durations` у пакета `orchestrator`
       (`mock.patch.dict(orchestrator.__dict__)` с удалением ключа либо
       `monkeypatch.delattr(orchestrator, "suite_durations",
       raising=False)`), после прогона оба восстанавливаются. Подмена
       атрибута значением `None` не допускается. Перед прогоном тест
       убеждается, что `from orchestrator import suite_durations` в этих
       условиях бросает `ImportError` (иначе сценарий холостой). «Ловит
       мутацию:» — импорт снова вне `try`.

     В обоих сценариях: тот же итог (код возврата и разобранная сводка),
     те же строки результатов тестов (`PASSED/FAILED <id>`) без
     длительностей, в логе нет строк трассировки исключения потока, файла
     времени нет, исключение наружу не выходит.
9. Карта кода `docs/codebase-map.md` перегенерируется.
10. Существующие тесты не правятся. Адресно разработчик прогоняет:
    - все файлы `tests/` с подменой атрибутов `orchestrator.acceptance`
      (список — в PLAN);
    - три файла с обращениями к блоку выкладки:
      `tests/test_acceptance_plank_exclude_lock.py`,
      `tests/test_acceptance_plank_layout_refusal.py`,
      `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py`;
    - `tests/test_task_component_places.py`;
    - `tests/test_01m4jd36…_amend_pult.py` и `tests/test_01m5edw6…_file_level.py`
      (полные имена — по поиску).
11. Ограничение зон по смыслу:
    - в модулях кроме `acceptance.py` и `plank_layout.py` — только замена
      обращения к закрытому имени `acceptance` на публичное (требование 4);
    - в `acceptance.py` — только перенос самодостаточной части выкладки с
      реэкспортом, объявление публичных имён и требование 7;
    - в `tests/` — только новые файлы.

## Критерии приёмки

AC-1. Модуль `orchestrator/plank_layout.py` существует. Он определяет
публичные имена `exclude_layout`, `exclude_pattern`, `layout_mode`,
`layout_root`, `drop_layout`, `plank_layout`, `uses_plank_layout`,
`drop_component_layout`, `PlankPlan`, `Laid` и константы `PLANK_LAYOUT_DIR`,
`PLANK_LAYOUT_EXCLUDE`, `LAYOUT_OUTSIDE_NOTE`, `PLANK_ABSENT_NOTE`,
`NO_PLANK_LAYOUT`, `LAYOUT_NOT_NORMAL`, `LAYOUT_ID_NOT_LAST`,
`LAYOUT_OUTSIDE_WORKDIR`, `LAYOUT_PARENT_NOT_HIDDEN`,
`LAYOUT_PARENT_TRACKED`. Закрытые `_inside`, `_layout_parent` и
`_LAYOUT_ID` определены в нём же и не имеют публичных двойников.

AC-2. `orchestrator/plank_layout.py` не импортирует модуль
`orchestrator.acceptance` ни в одной форме: разбор `ast` не находит
импорта `acceptance`, в том числе ленивого внутри функций.

AC-3. Каждое прежнее имя перенесённой части в `orchestrator.acceptance`
является тем же объектом, что соответствующее имя `plank_layout`
(`acceptance._exclude_layout is plank_layout.exclude_layout`,
`acceptance.PLANK_LAYOUT_DIR is plank_layout.PLANK_LAYOUT_DIR` и так далее
по всему списку требования 1). Тексты отказов-констант побайтно совпадают
с текстами на 84c784aa.

AC-4. Несамодостаточная часть выкладки остаётся в `acceptance.py`:
`_layout_ignore`, `_layout_check`, `_plank_plan`, `_component_layout` и
`_laid_plank` определены в модуле `orchestrator.acceptance`, и у каждого
из этих пяти объектов `__module__ == "orchestrator.acceptance"`. Имена блока
раннеров `acceptance.py:37–948` также остаются определёнными в
`orchestrator.acceptance`.

AC-5. Для каждого закрытого имени требования 4, кроме
`_last_full_suite_metrics` и имён, добавленных в исключения по требованию 5,
в `orchestrator.acceptance` есть публичное имя без подчёркивания.
Публичное имя ссылается на тот же объект, что закрытое, а закрытое имя
по-прежнему существует. Публичного имени `last_full_suite_metrics` в
модуле нет.

AC-6. Ни один модуль `orchestrator/` и `scripts/` не обращается к закрытому
имени модуля `orchestrator.acceptance`, кроме имён из константы исключений
`{"_last_full_suite_metrics"}` и исключений требования 5. Под модулем
`orchestrator.acceptance` здесь понимаются формы, распознанные разбором
импортов: абсолютный импорт (`from orchestrator import acceptance`,
`import orchestrator.acceptance`); относительный импорт, разрешающийся в
`orchestrator.acceptance` (`from . import acceptance` в
`orchestrator/*.py`, `from .. import acceptance` в подпакетах
`orchestrator/advance_gates/`, `orchestrator/doctor/`), — разрешение
относительного импорта тест строит по пути файла; обращение через пакет
`doctor.acceptance`. `advance_gates.acceptance` (`from .acceptance import …`
внутри `advance_gates`) — другой модуль, обращения к нему не считаются.

AC-7. Прогон маленького проекта песочницы раннером пульта
(`profile is None`) с логом (`run_full_suite(..., log=…)`) проверяется в
двух сценариях сбоя. Сначала тест убеждается, что без сбоя при этом
условии файл времени появляется. Сценарий 1: подмена
`suite_durations.Reader.start` (или конструктора `Reader`) бросает
`RuntimeError`. Сценарий 2: на время прогона
одновременно `sys.modules["orchestrator.suite_durations"] = None` и
удаление атрибута `suite_durations` у пакета `orchestrator`
(`mock.patch.dict(orchestrator.__dict__)` с удалением ключа либо
`monkeypatch.delattr(orchestrator, "suite_durations", raising=False)`),
с восстановлением обоих после прогона (сбой импорта `suite_durations`);
подмена атрибута значением `None` не допускается. Перед прогоном тест
убеждается, что `from orchestrator import suite_durations` в этих
условиях бросает `ImportError`; «Ловит мутацию: импорт снова вне try».
В каждом
сценарии прогон по сравнению с прогоном без сбоя даёт тот же итог (код
возврата и разобранная сводка) и те же строки результатов тестов
(`PASSED/FAILED <id>`) без длительностей; в логе нет строк трассировки
исключения потока; файл времени не создаётся; исключение из прогона
наружу не выходит.

AC-8. PLAN задачи содержит две вещи:
- результат повторного поиска подмен тестами имён из списка требования 4
  на базе ветки, во всех четырёх формах требования 5;
- список файлов `tests/` с подменой атрибутов `orchestrator.acceptance`,
  прогнанных адресно по требованию 10.

## Оценка объёма и деление

Сработал сигнал: число файлов зоны ≥ 5
(`SPLIT_SIGNAL_ZONE_FILES`). Зона: 10 модулей `orchestrator/`, карта и
`tests/`.

Эта задача уже нарезана: Оператор 23.10.2026 разделил находку CR-8 на два
этапа, и этот этап — первый. Ниже — материал Оператору для решения о
монолите внутри этапа. Само решение утверждает Оператор на гейте SPEC.

Большинство файлов зоны — восемь вызывающих модулей. В каждом правка
однострочная: замена закрытого имени на публичное.

Эти правки связаны с тестом AC-6. Он требует, чтобы все вызывающие модули
разом не обращались к закрытым именам. Значит, правки модулей и
объявление публичных имён в `acceptance.py` мержатся вместе. Если
вынести модуль-вызыватель в отдельную подзадачу, тест AC-6 в первой
части будет красным либо потребует временного списка исключений.

Перенос выкладки (`plank_layout.py`) и пробел теста замера можно отделить
по зонам. Но оба трогают тот же `acceptance.py`, а резать эту зону
поперёк по правилу деления нельзя.

Прогноз диффа невелик: перенос около 300 строк и однострочные замены.

## Не входит

- Этап 2: перенос блока раннеров (`pytest-own`, компонент с отчётом,
  установка зависимостей, `acceptance.py:37–948`) и несамодостаточной части
  выкладки (`_layout_ignore`, `_layout_check`, `_plank_plan`,
  `_component_layout`, `_laid_plank`). Он требует перенацелить подмены
  атрибутов `acceptance` в существующих тестах — это мандат Оператора и
  отдельная задача.
- Изменение поведения приёмки, гейтов, выкладки, вердикта `full_suite`,
  argv и окружения прогонов, ключа кэша итога.
- Публичное имя для `_last_full_suite_metrics` и переименование закрытых
  имён внутри `acceptance.py`.
- Правка существующих тестов `tests/`, `tests/test_invariants.py` и
  `tests/sandbox.py`.
- Правка комментариев в модулях вне зон. Это касается и
  `orchestrator/models.py`, `orchestrator/fsm_autogate.py`,
  `orchestrator/plank_helper.py`, `orchestrator/project_profile.py`: в них
  закрытые имена `acceptance` встречаются только в комментариях.
- Правка модулей только для чтения: `orchestrator/suite_durations.py`,
  `orchestrator/advance_gates/acceptance.py`, `orchestrator/doctor/__init__.py`,
  `scripts/guard.py`, `orchestrator/gitcmd.py`, `orchestrator/config.py`,
  `docs/backlog.md`, `docs/audits/code-revision-2026-10-22.md`.
- Правка `orchestrator/` и `scripts/` вне перечня зон: там только чтение —
  поиск обращений для требований 4 и 8(г).
- Перенос импорта `suite_durations` наверх модуля `acceptance`. Он
  невозможен из-за цикла `suite_durations.py:16` → `suite_run` →
  `acceptance` (`suite_run.py:53`).
- Зелёный полный набор `tests/` и зелёный CI ветки, включая джоб свежести
  карты кода (требования 9–10). Их держит пульт.

## Материалы

- `tasks/01M5N8ASJ63ZKF3M9ETC7A3P5V/TZ.md`, раздел «Факты» — номера строк и
  перечни обращений на 84c784aa.
- `docs/audits/code-revision-2026-10-22.md`, находка CR-2026-10-22-8.
- `docs/backlog.md:358`; строка бэклога 23.10 «Тест задачи замера
  (01M5MJFSYW): сбой запуска потока чтения времени не меняет прогон».
- Решения Оператора на гейте SPEC 24.10.2026 (круг 1, по `SPEC-AUDIT.md`,
  вердикт concerns): приняты все пять предложений аудита — формы импорта
  в 8(г)/AC-6, второй сценарий и условие запуска потока в 8(д)/AC-7,
  сравнение прогонов без длительностей в AC-7, проверка `__module__` в AC-4.
- Решение Оператора на гейте SPEC 24.10.2026 (круг 2, по `SPEC-AUDIT.md`,
  вердикт concerns): в сценарии 2 AC-7 вместе с
  `sys.modules[...] = None` снимается атрибут пакета `orchestrator`
  (не подменяется `None`), тест проверяет `ImportError` перед прогоном.
