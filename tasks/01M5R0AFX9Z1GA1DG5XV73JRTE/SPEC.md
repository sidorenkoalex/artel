---
task: 01M5R0AFX9Z1GA1DG5XV73JRTE
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/, docs/codebase-map.md
budget_usd: 60
---

# SPEC: Сведение тестов, волна 3м-2 — тесты мьютекса по проекту и зависимостей мержа в файлы модулей pytest с доказательством мутациями

## Контекст
Строка бэклога «Периодическая консолидация тестов артели» (решение Оператора
23.10.2026). Основание — ADR-0027 п. 8 и ADR-0020 п. 8. Порядок волн (решение
Оператора 23.10.2026): note → outcome → merge → suite-run → остальные. Мандат
Оператора 23.10.2026: «Волна сведения тестов по note; после бери все
остальные модули в работу - даю мандат». Решение Оператора 24.10.2026
(«Бери»): одновременно идут до трёх волн. Модули волны —
`orchestrator/merge_lock.py`, `orchestrator/merge_queue.py`,
`orchestrator/merge_after.py`.

Волна 3м-1 (01M5QJTVJB1ZM8B6DDEFQBP6RX) смержена 24.10 (78a3013b): файлы
модулей `tests/test_merge_lock_module.py` и `tests/test_merge_queue.py` уже в
стиле pytest. Решения гейта SPEC волны 3м-1 действуют и здесь: признак «то же
утверждение», дубли, помощники в двух файлах, атрибуты классов.

Факты ТЗ сверены с origin/main 78a3013b. Аналитик повторно сверил с деревом
ветки (dad6165f) число строк, байтов, тестов, заявок и наборов `subTest`.
Между 78a3013b и dad6165f смержена 01M5QR5BSE: изменены только два
долгоживущих файла (`full_suite_lock`, `doctor_duration`) и
`docs/codebase-map.md`, `orchestrator/` не менялся. В работе 01M5QR7KGY
(`orchestrator/artifact_branch.py`); файлы волны с ней не пересекаются.

Файлы волны (у всех тестов есть заявки «Ловит мутацию»; тестов без заявки нет):
- `tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py` (далее
  «mutex_by_project») — долгоживущий файл задачи 01M57PM7NBFX34319TR0F9CB4F
  (в `done`):
  - 669 строк (37 876 байт), 17 тестов, 17 заявок;
  - константы модуля `OTHER_HOST` (:35, литерал тот же, что в обоих файлах
    модулей), `TS_FORMAT` (:36), `TAKEOVER_ACTION` (:37), `_ALPHABET` (:38),
    функция `refusal_pattern` (:41);
  - базовый класс `_ProjectMutexBase(TmpRootTest)` (:50), `setUp` :54;
  - классы `AcquireByProjectTest` (:160, 6 тестов), `ReleaseAndHeartbeatTest`
    (:308, 4), `StoreMergeLockTest` (:436, 1) проверяют `merge_lock`/`store`;
    `QueueByProjectTest` (:471, 4), `WaitTextsByProjectTest` (:590, 2) —
    `merge_queue`;
  - методы без утверждений: `token` :66, `new_project` :69, `new_task` :74,
    `session` :84, `foreign_pid` :87, `seed_lock` :91, `live_holder` :101,
    `lock_by_task` :105, `queue_task_ids` :109, `clear` :112, `enqueue` :117,
    `run_wait` :124 (вложенная `fake_sleep` :130), `actions` :145, `msg` :148,
    `project_pairs` :156;
  - с утверждениями: `assert_fresh` :151 (`assertLess` :154), `wait_texts` :592
    (`assertIsNotNone` :597; держит локальную `actions` и зовёт `self.actions`
    в одной функции :598);
  - `subTest` — 15 мест (:173, :200, :223, :248, :276, :294, :348, :386, :412,
    :447, :482, :506, :531, :569, :616), у всех общее состояние стенда;
    `test_ac17` утверждает и после цикла (:433);
  - замыкания: лямбды :352–357, вложенная `on_sleep` :540; ожидание — на
    подменённых `time.monotonic` и `patch_sleep` (:137–138);
  - утверждение до действия теста — `test_ac5` :326; `assertRegex` — :209,
    :633, :659.
- `tests/test_merge_after.py` (далее «merge_after») — 214 строк (10 102 байта),
  10 тестов, 10 заявок, не долгоживущий. `MARKER` (:15); `TaskIdFormTest` :18
  и `MigrationTest` :194 без песочницы; `MergeAfterDbSandbox(LightTransitionSandbox)`
  :35, `setUp` :37, методы `insert` :41, `set_deps` :48; `MigrationTest`
  глотает `sqlite3.Error` (:206–209).
- `tests/test_merge_after_declared.py` (далее «declared») — 119 строк (6 315
  байт), 5 тестов, 5 заявок, не долгоживущий. `OTHER_TARGET` (:11);
  `DeclaredSandbox(LightTransitionSandbox)` :14, `setUp` :16 (тело равно телу
  `MergeAfterDbSandbox.setUp`), `insert` :20 (тело иное), метод `spec_text`
  :71 (`self` не читает); `subTest` :40; утверждение до действия теста — :87.
- `tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py` (далее
  «division») — долгоживущий файл задачи 01M4JC58GZFHZ4PZHW254P22M2 (в `done`):
  214 строк (11 638 байт), 3 теста, 3 заявки. `ZONE` (:29), `DIVIDED_PREFIX`
  (:31), `division_spec` (:34); класс
  `DivisionRewritesDependentsTest(LightTransitionSandbox)` :71 с атрибутом
  `TASK_TITLE` (:75), который читает `LightTransitionSandbox.setUp`
  (`tests/sandbox.py:2198`) и от которого деление строит заголовки подзадач;
  `setUp` :77; методы `new_task` :103, `msg` :107, `stored_deps` :125,
  `journal` :129; помощник с утверждениями подготовки `divide` :110 (:114,
  :119, :122); `test_ac3` глотает `SystemExit` (:202–205).
- `tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py` (далее
  «spec_gate_hint») — долгоживущий файл задачи 01M5FGHNB29QA254FM07QR55AB (в
  `done`): 278 строк (16 051 байт), 2 теста, 2 заявки. Константы `FIELD`,
  `MANDATE`, `LOSS_START`, `OLD_TAIL`, `ZONES`, `SPEC_TEXT` (:25–56), функции
  `spec_text(task_id, value)` (:59), `meta_of` (:64);
  `LossRefusalTextTest(InitializedTmpRootTest)` :68 (`setUp` :70, `task` :78);
  `DeclaredPathTest(LightTransitionSandbox)` :135 (`setUp` :137 с
  `self.addCleanup(env.stop)` :148; методы `note` :150, `run_cmd` :153,
  `live_task` :163, `refusal` :180, `no_code_tree` :185 — передаётся заменой в
  `mock.patch` :223; с утверждением подготовки `declared_task` :168 (:175));
  предпосылки в теле теста — :213; локальная `note` в `test_ac8` :121 и
  `test_ac9` :269; `subTest` :246; в `test_ac8` ветка «поле SPEC есть / нет»
  выбирается зерном.

Всего 37 тестов, 37 заявок; 1 494 строки, 81 982 байта. Из атрибутов классов
тесты читают через `self.` только `TASK_TITLE`. Ожидаемые тексты исключений не
проверяются; `assertRaises` нет. Прогон под `-p no:xdist` (78a3013b):
mutex_by_project — 17 тестов и 39 подслучаев за 1,0 с; spec_gate_hint —
0,43 с; остальные — доли секунды.

Файлы модулей волны 3м-1: `tests/test_merge_lock_module.py` — 546 строк
(25 801 байт), 19 тестов; `tests/test_merge_queue.py` — 523 строки (24 646
байт), 21 тест. Тела `clear` и `locks` модулей совпадают с телами `clear` и
`lock_by_task` `_ProjectMutexBase` (после замены `self.` параметром);
`new_task`, `seed_lock`, `enqueue` и фикстура `project_stand` — одноимённые с
иным телом. Тест очереди
`test_free_mutex_registers_then_immediately_takes_the_window` настоящую паузу
не подменяет: при мутации, после которой окно не берётся сразу, он спит по
90 с до таймаута pytest-timeout 120 с (`pyproject.toml:13`).

Связи вне волны: импортов из пяти файлов нет; путь ни одного из них не
упомянут строкой в `tests/`, `scripts/`, `orchestrator/`, `skills/`, `docs/`
(кроме `docs/codebase-map.md`); `tests/test_invariants.py` на них не
ссылается. Долгоживущие mutex_by_project, division, spec_gate_hint удаляются
по ветви ADR-0020 п. 8 «удаление без замены — решением Оператора»; перечень
сумм их задач после мержа не сверяется (ADR-0020 п. 6).

Общие фикстуры — `tests/fixtures.py` (`tmp_dir`, `tmp_root`,
`initialized_tmp_root`, `real_git`, `origin_real_git`, `light_transition`;
адаптер `_sandbox(cls)` исполняет уборку `addCleanup`). Подкласс песочницы
без тестовых методов в файле модуля стиля pytest — прецедент
`IdOutcomeGateSandbox` (`tests/test_outcome_gate_module.py:187`, фикстура
`_sandbox(IdOutcomeGateSandbox)` :578); смешением стилей guard считает только
класс с тестовыми методами (`scripts/guard.py:4557`). guard считает
утверждением `assert`, вызовы `assert…`/`fail` и `pytest.raises`/`pytest.warns`
(`scripts/guard.py:1530–1535`), текст сообщения отбрасывает.

Гейт ёмкости диффа — 262 144 байта; оценка задачи — около 175 КБ. `mutation-run`
(с 24.10): `--workers <n>`, `--wait-lock <минуты>` (сумма с `--wait` — не больше
9 минут), `--copy-table`; предел части — 1500 с на контроль и все патчи. Шаг
роли — 2700 с. Мандат выдаётся командой `answer`.

## Требования

1. Мутации «до», патчи.
   - Для каждой из 37 заявок — патч к коду `orchestrator/` в
     `tasks/<id>/mutation-<nnn>.diff`, номера подряд с 001. Патч реализует
     ровно мутацию заявки.
   - У заявки с несколькими альтернативами («либо …») — по патчу на каждую,
     если они не одинаковы по смыслу. Одинаковые по смыслу заявки — одна
     мутация со списком тестов.
   - У каждой мутации в PLAN — её заявка и что меняет патч.
   - Тест без заявки, если сверка его найдёт, получает заявку «Ловит
     мутацию» — правдоподобную мутацию проверяемого им кода, которую он ловит.
2. Таблица «до».
   - Команда — `mutation-run <id> --ref base --tests
     tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py,tests/test_merge_after.py,tests/test_merge_after_declared.py,tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py,tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py
     --copy-table --wait-lock 4`, частями `--patches` не больше 25 патчей.
   - Отчёт части — повторными `mutation-run <id> --wait 5` до итоговой
     строки.
   - Вывод части — в PLAN, раздел «Мутации до», дословно, с шапкой и всеми
     строками, до старта следующей части.
   - Патчи, после которых окно мержа может не взяться или цикл
     `wait_for_window` может не кончиться, — отдельными частями, не больше 8
     патчей в каждой.
   - Часть, оборванная пределом: её патчи переписываются и раскладываются по
     частям, тем же набором её не прогоняют.
3. Строка падения. У каждой мутации в PLAN для таблиц «до» и «после» — строка
   падения из лога прогона патча (файл:строка упавшего утверждения).
4. Не доказательство — мутация, «убитая» одним из способов (такой патч
   переписывается так, чтобы падало утверждение теста):
   - ошибкой сбора, импорта, setup или фикстуры;
   - исключением без падения утверждения;
   - только утверждением подготовки: `divide` (division :114, :119, :122),
     `declared_task` (spec_gate_hint :175), `wait_texts` (mutex_by_project
     :597), предпосылки spec_gate_hint :213, declared :87, mutex_by_project
     :326;
   - по таймауту pytest-timeout (`Timeout` в логе).
5. Детерминированность и находки.
   - Убийство мутации обязано быть детерминированным при любом зерне.
     Мутация, которую тест убивает только на части зёрен (ветки `test_ac8`
     «поле есть» и «два и более потерянных id», непустой `kept` в `test_ac9`,
     позиция родителя и случайные числа division, перемешивание `test_ac5`),
     не годится — переписывается.
   - Для тестов со случайными входами (mutex_by_project, division,
     spec_gate_hint, ULID из `idgen`) у каждой мутации в PLAN — одна фраза,
     почему её убийство не зависит от зерна.
   - Если для теста нет мутации, убиваемой при любом зерне, — находка в PLAN;
     тест не удаляется, зерно не фиксируется.
   - Расхождение «убита / не убита» между «до», «после» и повтором — заявка
     переписывается; повторы до убийства запрещены.
   - Мутация, не убитая никем, — находка в PLAN.
   - Исходы «итог неизвестен», «патч не применяется», «патч трогает тесты»,
     «не прогнана» — патч переписывается и прогоняется заново.
6. Красный контроль.
   - Первый красный контроль — повтор тем же вызовом в следующем шаге.
   - Повторно красный — повтор с `--workers 4`.
   - Красный и тогда — `escalate` с логом контроля; тесты и пределы не
     трогаются.
   - Ожидание замка — только `--wait-lock`; циклы и сценарии ожидания
     запрещены.
7. Временные файлы в рабочей копии не создаются. Допустимы: файл первого
   уровня каталога документов задачи с расширением не `.md` и именем не
   `test_*`/`mutation-*`; файл в `$TMPDIR`, созданный командой `python3`;
   копии `mutation-run-<n>.tsv` команды. К концу каждого шага `git status
   --porcelain` называет только: новый `tests/test_merge_after_module.py`,
   изменённые `tests/test_merge_lock_module.py` и `tests/test_merge_queue.py`,
   удаление пяти файлов волны и `docs/codebase-map.md` (только вывод
   генератора).
8. Свод mutex_by_project.
   - Тесты `AcquireByProjectTest`, `ReleaseAndHeartbeatTest`,
     `StoreMergeLockTest` — функциями в конец `tests/test_merge_lock_module.py`;
     `QueueByProjectTest`, `WaitTextsByProjectTest` — в конец
     `tests/test_merge_queue.py`. Разделы — комментарием с именем бывшего
     класса и файла.
   - Стенд — фикстура `project_mutex_stand(tmp_root)` с телом
     `_ProjectMutexBase.setUp` в каждом из двух файлов; тела одинаковы.
   - Помощники `_ProjectMutexBase` и `refusal_pattern`, константы `TS_FORMAT`,
     `TAKEOVER_ACTION`, `_ALPHABET` — в каждом файле те, что нужны его тестам,
     с одинаковыми телами и литералами. Импорт между файлами модулей запрещён.
     `OTHER_HOST` не переопределяется.
   - Помощники, чьё тело после замены `self.` параметром равно телу функции
     модуля, не переносятся — тест зовёт функцию модуля: `lock_by_task` →
     `locks`, `clear` → `clear`.
   - Одноимённые с иным телом и совпадающие с локальной переменной
     вызывающей функции получают префикс `project_mutex_` в обоих файлах:
     `project_mutex_new_task`, `project_mutex_seed_lock`,
     `project_mutex_enqueue`, `project_mutex_actions`.
   - Импортируются только недостающие имена (замок: `random`, `re`,
     `datetime`, `timezone`; очередь: `os`, `random`, `re`); `unittest`,
     `TmpRootTest` и `if __name__ == "__main__"` не переносятся.
   - Существующие 40 тестов обоих файлов, их фикстуры и функции не меняются;
     докстринги обоих модулей дополняются абзацем о волне 3м-2.
9. Свод четырёх файлов merge_after — в новый `tests/test_merge_after_module.py`
   в стиле pytest.
   - Докстринг модуля называет четыре прежних файла и их SPEC
     (01M44EP0D47F498TEE08MNGBYT, 01M45D29BQJE8FJYJA4JQWSYFZ,
     01M4JC58GZFHZ4PZHW254P22M2, 01M5FGHNB29QA254FM07QR55AB); строки «Группа:»
     и «Красен до реализации» не переносятся.
   - Стенды: `merge_after_stand(light_transition)` — одно тело `setUp`
     `MergeAfterDbSandbox` и `DeclaredSandbox`; `loss_stand(initialized_tmp_root)`;
     `declared_path_stand(light_transition)` (тело дословно,
     `self.addCleanup(env.stop)` → вызов стенда).
   - Для деления — подкласс `DivisionSandbox(LightTransitionSandbox)` только с
     `TASK_TITLE` прежним литералом, фикстура `division_sandbox()` с телом
     `yield from _sandbox(DivisionSandbox)` и фикстура
     `division_stand(division_sandbox)` с телом `setUp`
     `DivisionRewritesDependentsTest`. `_sandbox` импортируется из
     `tests.fixtures`, как в `tests/test_outcome_gate_module.py:65`.
   - `TaskIdFormTest` и `MigrationTest` — без фикстуры.
   - Одноимённые помощники с разным телом — с префиксом бывшего класса:
     `merge_after_db_insert`, `declared_insert`,
     `spec_gate_declared_refusal_spec_text` (метод; функция `spec_text`
     бывшего spec_gate_hint сохраняет имя); `note` бывшего `DeclaredPathTest`
     — `declared_path_note`; локальная `note` переименовывается и в
     `test_ac8` :121, и в `test_ac9` :269.
   - Тела `msg` (division) и `note` (`DeclaredPathTest`) совпадают, но не
     объединяются — это функции разных стендов.
   - `no_code_tree` — функция модуля без параметра стенда.
   - Константы и функции модулей прежних файлов — дословно.
   - Не переносятся: `unittest`, `InitializedTmpRootTest`, неиспользуемые
     импорты, `if __name__ == "__main__"`.
10. Фикстуры (требования 8–9). Тело фикстуры — тело `setUp` дословно без
    `super().setUp()`, `self.` заменено параметром, в конце `return
    <параметр>`. Фикстура только готовит окружение, утверждений в ней нет.
    Имена фикстур не совпадают с фикстурами `tests/fixtures.py` и файла
    модуля.
11. Помощники (требования 8–9). Методы классов — функции модуля: первый
    параметр — стенд, тело дословно, `self.` заменено именем параметра,
    вызовы перенесённых помощников — вызовы функций. Помощники с
    утверждениями (`assert_fresh`, `wait_texts`, `divide`, `declared_task`) —
    так же, тест зовёт их голым именем. Методы и атрибуты песочницы тест зовёт
    через стенд. Перечень «метод → функция», переименований и совпадений тел —
    в PLAN.
12. Утверждения и проверяемые свойства не меняются.
    - Ожидания дословно, форма — `assert …` (ADR-0027). Соответствие:
      `assertEqual(a, b)` ↔ `assert a == b`, `assertIsNone(x)` ↔ `assert x is
      None`, `assertIsNotNone(x)` ↔ `assert x is not None`, `assertIn(a, b)` ↔
      `assert a in b`, `assertNotIn(a, b)` ↔ `assert a not in b`,
      `assertTrue(x)` ↔ `assert x`, `assertFalse(x)` ↔ `assert not x`,
      `assertLess(a, b)` ↔ `assert a < b`, `assertGreaterEqual(a, b)` ↔
      `assert a >= b`, `assertRegex(t, p)` ↔ `assert re.search(p, t)`.
    - Текст `msg=`/позиционного сообщения — вторым операндом `assert`.
    - Литерал остаётся литералом, константа — константой; равенство значений
      доводом не считается.
    - Все 17 наборов `subTest` — прежним циклом. Ярлык — суффиксом `+ "; " +
      f"<ключ>={<значение>!r}, …"` с ключами и значениями прежнего `subTest` в
      тексте сообщения каждого утверждения подслучая. У утверждения подслучая
      без сообщения (declared :41) сообщением становится сам ярлык
      `f"tz={tz!r}"`.
    - Помощнику с утверждениями внутри подслучая суффикс доходит через
      аргумент сообщения (`assert_fresh(…, ctx + …)`); `wait_texts` получает
      последний необязательный параметр `case: str = ""`, сообщение её тела —
      `… + case`, иных отличий тела нет.
    - Глотание `sqlite3.Error` и `SystemExit`, подмены часов и паузы,
      замыкания — дословно.
13. Дубли.
    - Дубль удаляется, только если: (а) каждую его мутацию по таблице «до»
      убивает и другой сохраняемый тест того же прежнего файла (не тест волны
      3м-1); (б) каждый литерал и вид каждого утверждения удаляемого теста
      есть в сохраняемом; (в) ни одна мутация набора не убивается только
      удаляемым тестом.
    - Тест, получивший заявку в этой задаче, не удаляется; тест, чью мутацию
      не убил никто, не удаляется. Удалённые дубли — в PLAN.
    - Сверка с тестами волны 3м-1 на дубли не ведётся.
    - У каждой функции-теста — «Ловит мутацию:».
14. Таблица «после».
    - Команда — `mutation-run <id> --ref worktree --tests
      tests/test_merge_lock_module.py,tests/test_merge_queue.py,tests/test_merge_after_module.py
      --copy-table --wait-lock 4`, теми же диапазонами `--patches` и тем же
      `--workers`, что «до». Вывод — в PLAN, раздел «Мутации после», дословно.
    - Перед каждой частью — пустой вывод `git status --porcelain --
      orchestrator/`.
    - `Timeout` тестов волны 3м-1
      (`test_free_mutex_registers_then_immediately_takes_the_window`,
      `test_texts_name_own_project_holder_in_every_insertion_order`) в таблице
      «после» не повод переписывать патч, если перенесённая функция падает
      утверждением. Мутации выбираются так, чтобы перенесённый тест падал
      утверждением, а не зависал.
15. Соответствие «до» и «после».
    - Мутацию, убитую «до» тестом T, «после» убивает функция, в которую
      перенесён T, тем же утверждением (соответствие требования 12).
      Соответствие «до → после» с файлом:строкой — в PLAN.
    - Дерево `orchestrator/` ревизий обеих шапок совпадает; sha256 каждого
      патча совпадает.
    - При подтяжке main с изменением `orchestrator/` (ожидается после мержа
      01M5QR7KGY) таблица «до» прогоняется заново.
16. Прогоны и замеры. Под ролью адресно прогоняются только три файла
    модулей. Время «до» и «после» — по контрольным прогонам `mutation-run`.
    Число тестов и строк до и после — в PLAN (ожидается: замок 30, очередь 27,
    merge_after 20 тестов).
17. Удаление и мандат.
    - Пять файлов волны удаляются. Мандат — `answer` только на эти пять путей.
    - Не разрешены: удаление утверждения без переноса, ослабление сравнения,
      `skip`/`xfail`, подъём пределов.
    - `tests/test_merge_lock_module.py` и `tests/test_merge_queue.py` мандатом
      не покрыты: в них только добавление; правка их 40 тестов, фикстур и
      функций запрещена. Находка гейта неослабления по этим двум файлам —
      `escalate`; мандат на них не выдаётся и не расширяется.
18. Ограничение зон по смыслу. Не меняются: `tests/fixtures.py`,
    `tests/sandbox.py`, `tests/test_invariants.py`,
    `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`, долгоживущие
    `tests/test_01m44ep0d47f498tee08mngbyt_*.py` и
    `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`,
    `tests/test_fsm_map_regen.py`, файлы задач 01M5QR5BSE и 01M5QR7KGY, код
    `orchestrator/`. `docs/codebase-map.md` — только вывод генератора.
19. Независимая проверка (повтор `mutation-run` на зафиксированном наборе
    патчей, сравнение утверждений по AST) — сессией при Операторе до approve
    на merge_gate.

## Критерии приёмки

AC-1. Патчи и заявки.
- В каталоге документов задачи первым уровнем лежат патчи
  `mutation-<nnn>.diff`, номера подряд с 001 без пропусков; каждый патч меняет
  только файлы под `orchestrator/`.
- Каждая из 37 заявок сопоставлена в PLAN патчу (у заявки с неодинаковыми по
  смыслу альтернативами — патчу на каждую альтернативу), у каждой мутации
  названо, что меняет патч. Одинаковые по смыслу заявки сведены в одну мутацию
  со списком тестов.

AC-2. Раздел «Мутации до» в PLAN.
- В нём выводы частей `mutation-run <id> --ref base --tests <пять файлов
  волны> --copy-table --wait-lock 4`, перенесённые дословно, с шапкой и всеми
  строками.
- Каждая часть — не больше 25 патчей; часть с патчами, после которых окно
  может не взяться или `wait_for_window` может не кончиться, — не больше 8.
- В таблицах есть каждый патч набора.

AC-3. У каждой мутации в PLAN для таблиц «до» и «после» приведена строка
падения из лога прогона патча (файл:строка упавшего утверждения).

AC-4. Засчитывание мутаций.
- Ни одна мутация не засчитана доказательством, если её «убили» только:
  ошибка сбора, импорта, setup или фикстуры; исключение без падения
  утверждения; утверждение подготовки (division :114, :119, :122;
  spec_gate_hint :175, :213; mutex_by_project :597, :326; declared :87);
  таймаут pytest-timeout (`Timeout` в логе).
- Ни одна мутация с исходом «итог неизвестен», «патч не применяется», «патч
  трогает тесты» или «не прогнана» не засчитана ни убитой, ни выжившей.
- Мутации, которые «до» не убил никто, перечислены в PLAN находками.

AC-5. Детерминированность.
- Ни у одной мутации исход «убита / не убита» в «до», «после» и повторе не
  расходится.
- У каждой мутации тестов mutex_by_project, division, spec_gate_hint и
  тестов с ULID из `idgen` в PLAN есть фраза, почему её убийство не зависит
  от зерна; ни одна засчитанная мутация не убивается только веткой, зависящей
  от зерна (ветки `test_ac8` «поле есть» и «два и более потерянных id»,
  непустой `kept` в `test_ac9`, позиция родителя division, перемешивание
  `test_ac5`).
- Зерно ни в одном тесте не зафиксировано.

AC-6. Рабочая копия к концу шага. `git status --porcelain` называет только:
новый `tests/test_merge_after_module.py`, изменённые
`tests/test_merge_lock_module.py` и `tests/test_merge_queue.py`, удаление пяти
файлов волны и `docs/codebase-map.md`. Файлы первого уровня каталога
документов задачи с расширением не `.md`, кроме патчей `mutation-<nnn>.diff` и
копий `mutation-run-<n>.tsv`, не называются `test_*` и `mutation-*`.

AC-7. Файлы на ветке.
- Пяти файлов волны на ветке нет.
- В конце `tests/test_merge_lock_module.py` — тесты `AcquireByProjectTest`,
  `ReleaseAndHeartbeatTest`, `StoreMergeLockTest`; в конце
  `tests/test_merge_queue.py` — тесты `QueueByProjectTest`,
  `WaitTextsByProjectTest`; разделы отмечены комментарием с именем бывшего
  класса и файла.
- `tests/test_merge_after_module.py` несёт тесты merge_after, declared,
  division и spec_gate_hint; его докстринг называет четыре прежних файла и
  SPEC 01M44EP0D47F498TEE08MNGBYT, 01M45D29BQJE8FJYJA4JQWSYFZ,
  01M4JC58GZFHZ4PZHW254P22M2, 01M5FGHNB29QA254FM07QR55AB и не содержит строк
  «Группа:» и «Красен до реализации».
- Докстринги `tests/test_merge_lock_module.py` и `tests/test_merge_queue.py`
  дополнены абзацем о волне 3м-2.

AC-8. В трёх файлах модулей нет тестовых классов, `subTest`, импорта
`unittest`, `TmpRootTest`, `InitializedTmpRootTest`, блока `if __name__ ==
"__main__"` и неиспользуемых импортов; между файлами модулей нет импорта.
Единственный класс нового модуля — `DivisionSandbox(LightTransitionSandbox)`
без тестовых методов, только с `TASK_TITLE` прежним литералом.

AC-9. Стенды.
- В `tests/test_merge_lock_module.py` и `tests/test_merge_queue.py` есть
  фикстура `project_mutex_stand(tmp_root)` с одинаковыми телами.
- В `tests/test_merge_after_module.py` есть фикстуры
  `merge_after_stand(light_transition)`, `loss_stand(initialized_tmp_root)`,
  `declared_path_stand(light_transition)`, `division_sandbox()` с телом
  `yield from _sandbox(DivisionSandbox)` и `division_stand(division_sandbox)`;
  `_sandbox` импортирован из `tests.fixtures`. Тесты `TaskIdFormTest` и
  `MigrationTest` фикстур стенда не берут.
- Тело каждой фикстуры стенда — тело исходного `setUp` дословно без
  `super().setUp()`, `self.` заменено параметром, в конце `return
  <параметр>`; в `declared_path_stand` `self.addCleanup(env.stop)` заменено
  вызовом стенда. Утверждений в фикстурах нет; имена фикстур не совпадают с
  фикстурами `tests/fixtures.py` и своего файла модуля.

AC-10. Помощники и константы.
- Методы классов перенесены функциями модуля: первый параметр — стенд, тело
  дословно с заменой `self.` именем параметра, вызовы перенесённых помощников
  — вызовы функций; помощники с утверждениями (`assert_fresh`, `wait_texts`,
  `divide`, `declared_task`) тест зовёт голым именем; методы и атрибуты
  песочницы — через стенд.
- `lock_by_task` и `clear` `_ProjectMutexBase` не перенесены — тесты зовут
  `locks` и `clear` модуля.
- Имена: `project_mutex_new_task`, `project_mutex_seed_lock`,
  `project_mutex_enqueue`, `project_mutex_actions` (в обоих файлах, где
  нужны); `merge_after_db_insert`, `declared_insert`,
  `spec_gate_declared_refusal_spec_text`, `spec_text` (прежняя функция
  spec_gate_hint), `declared_path_note`; локальная `note` в `test_ac8` и
  `test_ac9` переименована; `msg` division и `declared_path_note` — отдельные
  функции; `no_code_tree` — функция без параметра стенда.
- Помощники `_ProjectMutexBase`, `refusal_pattern`, константы `TS_FORMAT`,
  `TAKEOVER_ACTION`, `_ALPHABET` — в каждом из двух файлов те, что нужны его
  тестам, с одинаковыми телами и литералами; `OTHER_HOST` не переопределён.
  Константы и функции модулей четырёх файлов merge_after перенесены дословно.
- В двух файлах 3м-1 добавлены только недостающие импорты (замок: `random`,
  `re`, `datetime`, `timezone`; очередь: `os`, `random`, `re`).
- Перечень «метод → функция», переименований и совпадений тел есть в PLAN.

AC-11. Ожидания перенесённых тестов совпадают с исходными дословно в форме
`assert …` по соответствию требования 12; текст сообщения — второй операнд
`assert`; литерал остался литералом, константа — константой; ни одно
сравнение не ослаблено.

AC-12. Циклы, подслучаи, глотание.
- Все 17 наборов `subTest` — прежним циклом; ярлык суффиксом `+ "; " +
  f"<ключ>={<значение>!r}, …"` с ключами и значениями прежнего `subTest` есть
  в тексте сообщения каждого утверждения подслучая; у утверждения declared
  :41 сообщение — `f"tz={tz!r}"`.
- Помощник с утверждениями внутри подслучая получает суффикс через аргумент
  сообщения; `wait_texts` отличается от исходной только последним параметром
  `case: str = ""` и `… + case` в сообщении.
- Глотание `sqlite3.Error` и `SystemExit`, подмены часов и паузы, замыкания
  перенесены дословно.

AC-13. Существующие 40 тестов `tests/test_merge_lock_module.py` и
`tests/test_merge_queue.py`, их фикстуры и функции не изменены: дифф этих
файлов против базы — только добавления (абзац докстринга, импорты, новые
фикстуры, функции и тесты).

AC-14. Дубли.
- У каждой функции-теста есть строка «Ловит мутацию:».
- Каждый исходный тест, не перенесённый в модуль, перечислен в PLAN
  удалённым дублем с его мутациями, и для него выполнены условия (а), (б) и (в)
  требования 13; другой убивающий тест — того же прежнего файла.
- Тест, чью мутацию не убил никто, и тест, получивший заявку в этой задаче,
  не удалены.

AC-15. Раздел «Мутации после» в PLAN.
- В нём выводы `mutation-run <id> --ref worktree --tests
  tests/test_merge_lock_module.py,tests/test_merge_queue.py,tests/test_merge_after_module.py
  --copy-table --wait-lock 4` теми же диапазонами `--patches` и тем же
  `--workers`, что «до», перенесённые дословно.
- Перед каждой частью — пустой вывод `git status --porcelain -- orchestrator/`.

AC-16. Соответствие «до» и «после».
- Каждая мутация, убитая «до» тестом T, «после» убита функцией, в которую
  перенесён T, тем же утверждением по соответствию требования 12;
  соответствие с файлом:строкой приведено в PLAN.
- Дерево `orchestrator/` ревизий обеих шапок совпадает; sha256 каждого патча
  совпадает.
- В PLAN названы число тестов (замок, очередь, merge_after), число строк и
  время по контрольным прогонам `mutation-run` до и после свода.

AC-17. Дифф ветки против базы — только: новый
`tests/test_merge_after_module.py`, добавления в
`tests/test_merge_lock_module.py` и `tests/test_merge_queue.py`, удаление пяти
файлов волны и `docs/codebase-map.md`, равный выводу `python3
scripts/codebase_map.py` на дереве ветки. Файлы требования 18 и всё под
`orchestrator/` не изменены. В трёх файлах модулей нет новых `skip`/`xfail`,
пределы не выше исходных.

## Оценка объёма и деление

Сработавшие сигналы:
- `budget_usd` ≥ $30 — ставка $60 из ТЗ («Бюджет: $60»);
- число критериев приёмки ≥ 10 — их 17;
- прогноз диффа выше половины потолка гейта ёмкости. Прогноз диффа: 175 КиБ
  (оценка ТЗ: удаление 82 КБ плюс добавление около 90 КБ; потолок — 256 КиБ).

Обоснование монолита (материал для решения Оператора на гейте SPEC).
Оператор уже нарезал семейство merge по волнам и вынес из этой семь
долгоживущих файлов `merge_after` (волна 3м-2б), чтобы дифф уложился в гейт
ёмкости. Внутри задачи части связаны:
- Тесты mutex_by_project расходятся по двум файлам модулей (замок и
  очередь); долгоживущий файл удаляется только когда перенесены все 17
  тестов.
- Четыре файла merge_after сводятся в один новый модуль; доказательство
  «до/после» ведётся одним набором патчей при неизменном `orchestrator/` и
  одной таблицей «после» по трём файлам модулей. Мандат — один `answer` на
  пять путей.
- Перенос без удаления исходных файлов оставляет полные дубли; удаление без
  переноса теряет покрытие.

Возможный разрез (mutex_by_project отдельно от четырёх файлов merge_after) —
решение Оператора; ТЗ ставит их одной волной с общим набором патчей.

## Не входит

- Семь долгоживущих файлов `merge_after`
  (`tests/test_01m44ep0d47f498tee08mngbyt_{answer,guard,merge_gate,plan,spec_gate,status_show}_merge_after.py`,
  `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`) —
  отдельная волна 3м-2б.
- `tests/test_fsm_map_regen.py` — волна семейства `fsm_postmerge`.
- Сверка на дубли с тестами волны 3м-1.
- Правка общих фикстур и песочниц (`tests/fixtures.py`, `tests/sandbox.py`).
- Изменение кода пульта `orchestrator/`; мутации — только во временной копии
  `mutation-run`.
- Независимая проверка (требование 19) — её делает сессия при Операторе, не
  роль.
- Полный зелёный набор `tests/` и CI ветки — их держит пульт.

## Материалы

- SPEC волны 3м-1: `refs/artifacts/01M5QJTVJB1ZM8B6DDEFQBP6RX`,
  `tasks/01M5QJTVJB1ZM8B6DDEFQBP6RX/SPEC.md`.
- ADR-0027 п. 8, ADR-0020 пп. 6, 8; `docs/backlog.md` — строка 23.10.
- Прецедент подкласса песочницы в модуле pytest:
  `tests/test_outcome_gate_module.py:187`, :578.

Только чтение: docs/, scripts/, skills/, orchestrator/ (весь код пульта;
мутации — только во временной копии `mutation-run`), tests/fixtures.py,
tests/sandbox.py, scripts/guard.py, tests/test_invariants.py,
tests/test_outcome_gate_module.py, conftest.py, pyproject.toml, targets.yaml,
skills/test-authoring.md, docs/adr/0027-pytest-style-tests.md,
docs/adr/0020-long-lived-acceptance-tests-in-tests.md.
