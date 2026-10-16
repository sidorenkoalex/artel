---
task: 01M52CQB468758M2NAA15C15ZE
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/acceptance.py, orchestrator/targets.py, orchestrator/project_profile.py, orchestrator/advance_gates/two_sided.py, orchestrator/advance_gates/acceptance.py, orchestrator/fsm_merge_gate.py, orchestrator/suite_run.py, orchestrator/plank_run.py, orchestrator/pull.py, orchestrator/amend.py, orchestrator/notes.py, orchestrator/fsm.py, orchestrator/fsm_autogate.py, orchestrator/fsm_advance.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/test_integrity.py, tests/
budget_usd: 50
---

# SPEC: D0 — внешний доверенный проект без песочницы: профиль чужого стека и чистое окружение тестов

## Контекст
ADR-0023, «Поправка 16.10.2026 (вторая)»: песочница (D1а, SPEC
01M51YKZNES22DZQY13D3QKF89) отложена, внешний доверенный проект (sled)
исполняет тесты на хосте, как артель. Сегодня пульт чужой стек гонять не
умеет: `_pytest_command` (`orchestrator/acceptance.py:35-65`) всегда ставит
интерпретатор venv пульта и `-p timeout -o timeout=…` (`:64-65`), полный
набор берёт `<корень>/tests` и дописывает `-n … -p xdist`; у sled тесты в
`backend/tests`, запуск `uv run pytest`, плагинов `pytest-timeout`/
`pytest-xdist` нет. `_pytest_env` (`acceptance.py:69-89`) отдаёт тестам
копию всего окружения пульта, включая токены. Точечные прогоны
(`acceptance.run`, `collect`, `run_repeat`, `run_plank`) идут через
`subprocess.run(timeout=…)` и на таймауте снимают только прямого потомка —
дочерний python `uv run` остался бы жить. То же сегодня у пути
`_run_full_suite_now` без `observe` (`acceptance.py:1343-1350`):
`subprocess.run` без собственного сеанса, группу процессов он не снимает;
группу снимают только путь с `observe` (`:1323-1341`) и
`_run_full_suite_to_log` (`:1371-1391`). Автогейт приёмки и `approve` на
acceptance зовут полный набор через `acceptance.acceptance_suite`
(`acceptance.py:1807-1848`) без команды профиля (`docs/backlog.md:186`).

## Требования

1. `test_profile` (`orchestrator/targets.py`, `PROFILE_FIELDS`) получает три
   необязательных подполя; профиль без них остаётся правильным и ведёт себя
   как сейчас:
   - `runner`: `pult-pytest` (по умолчанию, сегодняшнее поведение) |
     `pytest-own`; иное значение — отказ проверки;
   - `workdir`: каталог прогона относительно корня репозитория;
     `targets.check` отказывает абсолютному пути и пути с сегментом `..`;
   - `env`: блочное отображение строк (новый вид подполя `mapping`;
     `orchestrator/yamlmini.py` не меняется); `targets.check` отказывает
     имени из точного перечня секретов — `secret_env_names()` провайдеров,
     `GITHUB_TOKEN`, `GH_TOKEN`, — сверка по точному имени.
   `workdir` и `env` допустимы только при `runner: pytest-own`:
   `targets.check` отказывает профилю, несущему `workdir` или `env` при
   `runner: pult-pytest`, в том числе при `runner` по умолчанию (поле не
   задано). Подполя доходят до потребителей полями `project_profile.Profile`
   (`orchestrator/project_profile.py`). Поле `sandbox` не вводится.
2. В момент прогона `realpath` каталога `workdir` обязан лежать внутри
   дерева прогона; иначе прогон не запускается, а место запуска возвращает
   именованный отказ (текст называет `workdir` и причину).
3. `runner: pytest-own`: argv — команда профиля как есть, без подстановки
   интерпретатора пульта, без `-p timeout`/`-o timeout=…` и без
   `-n …`/`-p xdist`; пульт по-прежнему дописывает свои аргументы гейтов
   (`--collect-only -q`, `--junitxml`, `-o junit_logging=system-out`,
   `-p no:cacheprovider`) и аргументы, которые сегодня дописывает конкретное
   место запуска. Рабочий каталог прогона — `workdir` (без него — корень
   дерева прогона).
4. При `pytest-own` все пути профиля (`long_lived_dir`, долгоживущие пути,
   `workdir`) отсчитываются от корня репозитория; пульт переводит их в пути,
   верные из `workdir`. Перевод делает место запуска
   (`orchestrator/acceptance.py`, `two_sided.py`): цель полного набора —
   `long_lived_dir`, а не `<корень>/tests` (в том числе когда вызывающий
   передаёт целью полного набора `tests`, как `suite_run.py:525,565`);
   прочие переданные вызывающим цели (например, id упавших тестов
   `suite-run --failed`) переводятся от корня репозитория к `workdir`.
   Логика `orchestrator/suite_run.py` не меняется.
5. Окружение тестов при `pytest-own` состоит только из: `PATH` пульта;
   временного `HOME` (новый каталог на каждый прогон, удаляется после
   прогона, в том числе по таймауту и исключению); `TMPDIR`; `LANG`/`LC_ALL`
   при наличии у пульта; служебных переменных, которые сегодня ставит место
   запуска (`PYTHONPYCACHEPREFIX`, `PYTHONUNBUFFERED`, переменные плагина и
   отчёта двустороннего прогона); `test_profile.env`. Остальное окружение
   пульта, в том числе токены и переменные провайдеров, не передаётся. При
   `pult-pytest` окружение прежнее.
6. Таймаут при `pytest-own`: каждое из восьми мест запуска —
   `acceptance.run`, `acceptance.collect`, `acceptance.run_repeat`,
   `acceptance.run_plank`, `_run_full_suite_now` с `observe`,
   `_run_full_suite_now` без `observe`, `_run_full_suite_to_log`,
   `two_sided._run_side` — запускает прогон в собственном сеансе и по
   таймауту и на любом исключении снимает всю группу процессов — как сегодня
   полный набор (`acceptance.py:1324-1337`, `:1373-1391`). Для точечных
   прогонов и пути `_run_full_suite_now` без `observe` это новое поведение:
   сегодня они группу не снимают. При `pult-pytest` поведение прежнее.
7. Один источник команды профиля: следующие вызывающие получают одни и те же
   `command`, `runner`, `workdir`, `env` профиля проекта задачи — через тот
   же канал, которым сегодня передаётся `command` (`Profile` вместо списка):
   - автогейт приёмки (`fsm_autogate.py`) и `approve` на acceptance
     (`fsm.py`) — через `acceptance.acceptance_suite`
     (`acceptance.py:1807-1848`), которая берёт профиль проекта задачи сама;
   - гейт мержа (`fsm_merge_gate.py:962-967`), `suite-run`
     (`suite_run.py`), `plank-run` (`plank_run.py:187`), `amend-tests`
     (`amend.py:545-549`, `:715-718`), прогоны `pull` (`pull.py:664-666`);
   - сухой сбор выхода `tests_writing` (`fsm_advance.py:594-596`,
     `advance_gates/tests_writing.py:557-563`);
   - двусторонний прогон: вызывающие `two_sided.run`
     (`advance_gates/test_integrity.py:1429`, `:1527`) передают профиль,
     `two_sided.run` его принимает.
   `preflight` (`orchestrator/preflight.py`) и `acceptance-dry-run`
   (`orchestrator/dry_run.py`) pytest не запускают — их модули вне зон и не
   правятся; если разработчик найдёт в них запуск прогона, это эскалация.
   Для прогонов без задачи (в том числе `notes.py:1040`) и для артели —
   сегодняшнее поведение. В вызывающих модулях меняется только передача
   профиля вместо команды, без изменения логики гейтов.
8. Ключ повторного использования итога полного набора (gate- и base-итог,
   `acceptance.py:1609-1640`, `:1740-1758`, `:1790-1792`;
   `suite_run.py:511,533`) при `pytest-own` учитывает `runner`, `workdir`
   и `env`; при `pult-pytest` ключ не меняется ни на байт.
9. До правки мест запуска тестами зафиксированы argv, `cwd` и окружение
   каждого из восьми мест запуска требования 6 для артели — по обоим путям
   команды артели: `command=None` (команда пульта) и
   `command=[python3, -m, pytest]` (профиль артели, `targets.yaml:46`);
   после правки они неизменны.
10. Тесты детерминированы, без сети и без `uv`: учебный проект во временном
    каталоге с `runner: pytest-own` и командой, которая запускает pytest
    интерпретатором тестов через обёртку-скрипт, порождающий дочерний
    процесс.

## Критерии приёмки

AC-1. У артели (профиль без `runner`/`workdir`/`env`) argv, `cwd` и
окружение каждого из восьми мест запуска (`acceptance.run`,
`acceptance.collect`, `acceptance.run_repeat`, `acceptance.run_plank`,
`_run_full_suite_now` с `observe`, `_run_full_suite_now` без `observe`,
`_run_full_suite_to_log`, `two_sided._run_side`) совпадают со значениями,
зафиксированными до правки, — и при `command=None`, и при
`command=[python3, -m, pytest]` (`targets.yaml:46`).

AC-2. Учебный проект с `pytest-own`: в каждом из восьми мест запуска,
названных в AC-1, тест, читающий `os.environ`, не видит ни одной переменной
окружения пульта вне перечня требования 5 (в том числе подставленной в
окружение пульта переменной-маркера и токенов), а переменные
`test_profile.env` видит.

AC-3. Учебный проект с `pytest-own`: в каждом из восьми мест запуска,
названных в AC-1, `HOME` в тесте — временный каталог, отличный от `HOME`
пульта, и после возврата из места запуска его нет на диске — как после
обычного завершения, так и после таймаута.

AC-4. Учебный проект с `pytest-own`: в каждом из восьми мест запуска,
названных в AC-1, argv прогона — команда профиля без интерпретатора пульта,
без `-p timeout`, без `-o timeout=…`, без `-n` и без `-p xdist`, с
аргументами гейтов этого места запуска, а рабочий каталог — `workdir`.

AC-5. Учебный проект с `pytest-own` и `workdir`: полный набор собирается из
`long_lived_dir` (путь от корня репозитория, переведённый в путь из
`workdir`), а не из `<корень>/tests`, в том числе когда вызывающий передаёт
целью `tests`; переданная вызывающим цель-путь от корня репозитория
доходит до pytest переведённой в путь из `workdir`.

AC-6. По таймауту прогона учебного проекта с `pytest-own` (обёртка
порождает дочерний процесс) в каждом из восьми мест запуска, названных в
AC-1, дочерний процесс обёртки после возврата из места запуска не остаётся
жить.

AC-7. Автогейт приёмки, `approve` на acceptance, гейт мержа и `suite-run`
задачи учебного проекта запускают полный набор с argv, `cwd` и окружением,
которые требуют требования 3–5 для его профиля `pytest-own`: команда
профиля, `cwd` — `workdir`, окружение — только перечень требования 5 с
`test_profile.env`.

AC-8. `plank-run` задачи учебного проекта запускает планку с argv, `cwd` и
окружением по профилю `pytest-own` (требования 3–5).

AC-9. `amend-tests` задачи учебного проекта запускает прогоны с argv, `cwd`
и окружением по профилю `pytest-own` (требования 3–5).

AC-10. Прогоны `pull` задачи учебного проекта идут с argv, `cwd` и
окружением по профилю `pytest-own` (требования 3–5).

AC-11. Двусторонний прогон задачи учебного проекта, вызванный из
`advance_gates/test_integrity.py`, идёт с argv, `cwd` и окружением по
профилю `pytest-own` (требования 3–5).

AC-12. Сухой сбор на выходе `tests_writing` задачи учебного проекта идёт с
argv, `cwd` и окружением по профилю `pytest-own` (требования 3–5).

AC-13. `targets.check` отказывает: `test_profile.env` с именем секрета
(`GITHUB_TOKEN`, `GH_TOKEN`, имя из `secret_env_names()` провайдера);
`workdir` с сегментом `..` или абсолютным путём; `runner` вне
`pult-pytest`/`pytest-own`; `workdir` или `env` при `runner: pult-pytest` и
при `runner`, не заданном в профиле. Профиль без новых подполей проходит
проверку.

AC-14. `workdir`, чей `realpath` в момент прогона выходит за дерево прогона
(например, символическая ссылка наружу), даёт именованный отказ, и прогон
не запускается.

AC-15. Итог полного набора при `pytest-own`, полученный с другим `runner`,
`workdir` или `env`, не засчитывается повторно; ключ итога при
`pult-pytest` совпадает с ключом до правки байт в байт.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `-p timeout` / `-o timeout=…` снимаются при `runner: pytest-own` | предел времени одного теста `stack.PER_TEST_TIMEOUT_SEC` (`orchestrator/acceptance.py:64-65`) | при `pytest-own` — нет (у чужого стека плагина нет); при `pult-pytest` — остаётся | замена: предел прогона места запуска (`config.ACCEPTANCE_TIMEOUT_SEC`, `config.py:188`; `TWO_SIDED_PYTEST_TIMEOUT_SEC`, `:207`; предел полного набора `FULL_SUITE_TIMEOUT_SEC`, `:219`, или профиля) и снятие всей группы процессов — AC-6; `pult-pytest` — AC-1 | принято Оператором 16.10.2026 осознанно |
| `-n … -p xdist` снимаются при `runner: pytest-own` | параллельный полный набор пульта (`acceptance.py`, полный набор) | при `pytest-own` — нет; при `pult-pytest` — остаётся | `pult-pytest` — AC-1; при `pytest-own` свойство не гарантирующее, а ускоряющее | по ТЗ, требование 2 |
| Окружение тестов при `pytest-own` | копия окружения пульта (`acceptance.py:69-89`) | при `pult-pytest` — остаётся прежним | AC-1; при `pytest-own` — сужение, AC-2, AC-3 | по ТЗ, требование 3 |

## Оценка объёма и деление

Сработавший сигнал: число файлов зоны — 17 (порог ≥ 5). Сигнал по бюджету
не срабатывает: `budget_usd` 50 ниже порога `config.SPLIT_SIGNAL_BUDGET_USD`
= 60 (`orchestrator/config.py:587`). По калибровке
(`config.BUDGET_CALIBRATION_TABLE`) задача «8 и более файлов» — ~$85 либо
деление; рамка ТЗ — $50.

Предлагается **нарезка на 3 части** по границам зон (ниже, «## Деление»):

1. **Профиль: подполя и фиксация argv** — `targets.py`, `project_profile.py`,
   `tests/`. Механика, на которую опираются остальные: поля `Profile` и
   проверка `targets.check`, плюс тесты-фиксация argv/`cwd`/окружения
   восьми мест запуска артели по обоим путям команды (требование 9 требует
   их ДО правки мест запуска). Самостоятельно мержима: новые подполя
   необязательны, никто их ещё не читает, поведение артели не меняется,
   фиксирующие тесты зелёные на текущем коде.
2. **Раннер `pytest-own` в местах запуска** — `acceptance.py`,
   `advance_gates/two_sided.py`, `tests/`. Требования 2–6, 8, 10 на уровне
   мест запуска, перевод целей полного набора, приём профиля
   `two_sided.run`, профиль задачи в `acceptance.acceptance_suite`.
   Самостоятельно мержима: вызывающие вне `acceptance.py` ещё передают
   только `command`, у артели путь `pult-pytest` прежний — фиксация части 1
   держит его неизменность.
3. **Один источник профиля у вызывающих** — `advance_gates/acceptance.py`,
   `fsm_merge_gate.py`, `suite_run.py`, `plank_run.py`, `pull.py`,
   `amend.py`, `notes.py`, `fsm.py`, `fsm_autogate.py`, `fsm_advance.py`,
   `advance_gates/tests_writing.py`, `advance_gates/test_integrity.py`,
   `tests/`. Требование 7 и AC-7–AC-12: передача профиля вместо команды без
   изменения логики гейтов. Мержима последней: опирается на приём профиля
   частью 2.

Рамки частей ($25 / $45 / $40) взяты по калибровке на объём каждой части;
планка не ниже $25 на задачу, поэтому их сумма ($110) выше рамки ТЗ $50.
Альтернатива — монолит: атомарности нет (каждая часть оставляет систему
рабочей), монолиту по калибровке нужен потолок ~$85 при рамке $50. Решение
и рамки частей — за Оператором на гейте SPEC.

## Деление

### D0-1: профиль test_profile — подполя runner, workdir, env и фиксация мест запуска

Зоны: orchestrator/targets.py, orchestrator/project_profile.py, tests/
Порядок: первая, без зависимостей
Рамка: $25

Основание — ADR-0023, вторая поправка 16.10.2026; часть 1 из 3 задачи
D0 (внешний доверенный проект без песочницы).

1. `test_profile` (`orchestrator/targets.py`) получает необязательные
   подполя; профиль без них остаётся правильным и ведёт себя как сейчас:
   `runner`: `pult-pytest` (по умолчанию) | `pytest-own`, иное — отказ;
   `workdir` — каталог прогона относительно корня репозитория,
   `targets.check` отказывает абсолютному пути и пути с `..`; `env` —
   блочное отображение строк (новый вид подполя `mapping`; `yamlmini` не
   меняется), `targets.check` отказывает имени из точного перечня секретов
   (`secret_env_names()` провайдеров, `GITHUB_TOKEN`, `GH_TOKEN`), сверка
   по точному имени. `workdir` и `env` допустимы только при
   `runner: pytest-own`: `targets.check` отказывает им при `pult-pytest`, в
   том числе при `runner` по умолчанию. Поле `sandbox` не вводится.
2. Подполя доходят до потребителей полями `project_profile.Profile`
   (`orchestrator/project_profile.py`); потребителей в этой части не
   меняем.
3. Тестами зафиксировать argv, `cwd` и окружение каждого из восьми мест
   запуска для артели (`acceptance.run`, `collect`, `run_repeat`,
   `run_plank`, `_run_full_suite_now` с `observe` и без, 
   `_run_full_suite_to_log`, `two_sided._run_side`) на текущем коде — по
   обоим путям команды: `command=None` и `command=[python3, -m, pytest]`
   (`targets.yaml:46`).

Критерии приёмки: `targets.check` отказывает `env` с именем секрета,
`workdir` с `..` или абсолютным путём, неизвестному `runner`, `workdir` или
`env` при `pult-pytest` и при `runner` по умолчанию; профиль без новых
подполей проходит и даёт `Profile` с `runner` = `pult-pytest`; фиксирующие
тесты мест запуска по обоим путям команды зелёные на текущем коде. Не
входит: правка `orchestrator/acceptance.py`, `two_sided.py` и вызывающих
модулей; запись sled в `targets.yaml` (только чтение).

### D0-2: раннер pytest-own в местах запуска — команда, workdir, чистое окружение, группа процессов

Зоны: orchestrator/acceptance.py, orchestrator/advance_gates/two_sided.py, tests/
Порядок: после части 1
Рамка: $45

Основание — ADR-0023, вторая поправка 16.10.2026; часть 2 из 3 задачи
D0. Опирается на поля `Profile` `runner`/`workdir`/`env` части 1.

1. Места запуска (`acceptance.run`, `collect`, `run_repeat`, `run_plank`,
   `_run_full_suite_now` с `observe` и без, `_run_full_suite_to_log`,
   `two_sided._run_side`) принимают профиль тем же каналом, что сегодня
   `command`; `two_sided.run` принимает профиль от вызывающего.
   `acceptance.acceptance_suite` (`acceptance.py:1807-1848`) берёт профиль
   проекта задачи сама и передаёт его полному набору.
2. `runner: pytest-own`: команда профиля как есть, без интерпретатора
   пульта, `-p timeout`/`-o timeout=…` и `-n/-p xdist`; пульт дописывает
   аргументы гейтов (`--collect-only -q`, `--junitxml`,
   `-o junit_logging=system-out`, `-p no:cacheprovider`) и аргументы
   конкретного места запуска. Рабочий каталог — `workdir`; в момент прогона
   `realpath` обязан остаться внутри дерева прогона, иначе именованный
   отказ, прогон не запускается.
3. Пути профиля (`long_lived_dir`, долгоживущие пути, `workdir`)
   отсчитываются от корня репозитория и переводятся местом запуска в пути,
   верные из `workdir`: цель полного набора — `long_lived_dir`, а не
   `<корень>/tests` (в том числе когда вызывающий передаёт целью `tests`,
   как `suite_run.py:525,565`); прочие переданные вызывающим цели
   переводятся от корня репозитория к `workdir`.
4. Окружение при `pytest-own` — только `PATH` пульта, временный `HOME`
   (новый на прогон, удаляется после, в том числе по таймауту и
   исключению), `TMPDIR`, `LANG`/`LC_ALL` при наличии, служебные переменные
   места запуска (`PYTHONPYCACHEPREFIX`, `PYTHONUNBUFFERED`, переменные
   плагина и отчёта двустороннего прогона) и `test_profile.env`.
5. Таймаут при `pytest-own`: каждое из восьми мест запуска — в собственном
   сеансе, по таймауту и на любом исключении снимает всю группу процессов
   (как сегодня `acceptance.py:1324-1337`, `:1373-1391`); точечные прогоны
   и путь `_run_full_suite_now` без `observe` (`:1343-1350`) сегодня группу
   не снимают. Снятие `-p timeout` у `pytest-own` принято Оператором
   16.10.2026 осознанно: замена — предел прогона и снятие группы процессов.
6. Ключ повторного использования итога полного набора (gate- и base-итог,
   `acceptance.py:1609-1640`, `:1740-1758`, `:1790-1792`) при `pytest-own`
   учитывает `runner`, `workdir`, `env`; при `pult-pytest` не меняется ни
   на байт.
7. Тесты детерминированы, без сети и без `uv`: учебный проект во временном
   каталоге с `runner: pytest-own` и командой-обёрткой, порождающей
   дочерний процесс.

Критерии приёмки: у артели argv, `cwd` и окружение восьми мест запуска не
изменились (фиксация части 1 зелёная по обоим путям команды); в каждом из
восьми мест запуска тест учебного проекта не видит переменных пульта вне
перечня п.4 и видит `test_profile.env`, `HOME` — временный каталог, после
прогона и после таймаута удалён; argv — команда профиля без интерпретатора
пульта, `-p timeout`, `-n`, `-p xdist`, `cwd` — `workdir`; полный набор
собирается из `long_lived_dir` под `workdir`; по таймауту в каждом месте
запуска дочерний процесс обёртки не остаётся жить; `workdir` со ссылкой
наружу — именованный отказ без прогона; итог полного набора с другим
`runner`, `workdir` или `env` не засчитывается, ключ `pult-pytest` прежний.
Не входит: вызывающие вне `acceptance.py` и `two_sided.py` (часть 3),
логика `suite_run.py`, песочница.

### D0-3: один источник профиля у вызывающих прогон

Зоны: orchestrator/advance_gates/acceptance.py, orchestrator/fsm_merge_gate.py, orchestrator/suite_run.py, orchestrator/plank_run.py, orchestrator/pull.py, orchestrator/amend.py, orchestrator/notes.py, orchestrator/fsm.py, orchestrator/fsm_autogate.py, orchestrator/fsm_advance.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/test_integrity.py, tests/
Порядок: после части 2
Рамка: $40

Основание — ADR-0023, вторая поправка 16.10.2026; часть 3 из 3 задачи
D0. Опирается на приём профиля местами запуска (часть 2).

1. Вызывающие вне `acceptance.py` передают профиль проекта задачи
   (`command`, `runner`, `workdir`, `env`) тем же каналом, которым сегодня
   передаётся `command` (`Profile` вместо списка): гейт мержа
   (`fsm_merge_gate.py:962-967`), `suite-run` (`suite_run.py`, в том числе
   ключ итога `:511`, `:533`), `plank-run` (`plank_run.py:187`),
   `amend-tests` (`amend.py:545-549`, `:715-718`), прогоны `pull`
   (`pull.py:664-666`), сухой сбор `tests_writing` (`fsm_advance.py:594-596`,
   `advance_gates/tests_writing.py:557-563`), вызывающие двустороннего
   прогона (`advance_gates/test_integrity.py:1429`, `:1527`). Автогейт
   приёмки и `approve` на acceptance получают профиль через
   `acceptance.acceptance_suite` (часть 2).
2. Только передача профиля: логика гейтов и логика `suite_run.py` не
   меняются. Для прогонов без задачи (в том числе `notes.py:1040`) и для
   артели — сегодняшнее поведение. `preflight` и `acceptance-dry-run`
   pytest не запускают и не правятся.

Критерии приёмки: автогейт приёмки, `approve` на acceptance, гейт мержа и
`suite-run` запускают полный набор учебного проекта с argv, `cwd` и
окружением по профилю `pytest-own`; то же отдельно для `plank-run`,
`amend-tests`, прогонов `pull`, двустороннего прогона и сухого сбора
`tests_writing`; у артели argv, `cwd` и окружение мест запуска не
изменились. Не входит: правка `orchestrator/acceptance.py` и
`two_sided.py`; запись sled в `targets.yaml`.

## Не входит

- Поле `sandbox` и любая песочница (D1а, SPEC 01M51YKZNES22DZQY13D3QKF89).
- Запись sled в `targets.yaml` и меры круга 1 (D2); `targets.yaml` и
  `docs/backlog.md` — только чтение.
- Отдельный исполнитель команды `install` — зависимости ставит команда
  профиля.
- Стенд с базами данных (D1б).
- Codex на внешних проектах.
- Правка `orchestrator/yamlmini.py`, `orchestrator/preflight.py`,
  `orchestrator/dry_run.py` и любых модулей вне зон; правка вне зон —
  эскалация.
- Изменение логики гейтов в вызывающих модулях и логики
  `orchestrator/suite_run.py` — только передача профиля.

## Материалы

- `tasks/01M52CQB468758M2NAA15C15ZE/TZ.md`.
- ADR-0023, `docs/adr/0023-role-step-sandbox.md`, вторая поправка 16.10.2026.
- `orchestrator/acceptance.py:35-89` (`_pytest_command`, `_pytest_env`);
  места запуска `:447`, `:555`, `:664`, `:931`, `:1323`, `:1344`, `:1371`;
  `acceptance_suite` `:1807-1848`; `orchestrator/advance_gates/two_sided.py:227-235`.
- `orchestrator/runner.py:914` (`foreign_secret_env_names`) — образец
  сбора имён секретов провайдеров.
- `SPEC-AUDIT.md` этой задачи (вердикт concerns) и решение Оператора
  16.10.2026 на гейте SPEC по десяти замечаниям.
