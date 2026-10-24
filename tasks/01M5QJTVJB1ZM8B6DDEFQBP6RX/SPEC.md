---
task: 01M5QJTVJB1ZM8B6DDEFQBP6RX
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/, docs/codebase-map.md
budget_usd: 60
---

# SPEC: Сведение тестов, волна 3м-1 — тесты замка и очереди мержа в файлы модулей pytest с доказательством мутациями

## Контекст
Строка бэклога «Периодическая консолидация тестов артели» (решение Оператора
23.10.2026). Основание — ADR-0027 п. 8 и ADR-0020 п. 8. Порядок волн (решение
Оператора 23.10.2026): note → outcome → merge → suite-run → остальные. Мандат
Оператора 23.10.2026: «Волна сведения тестов по note; после бери все
остальные модули в работу - даю мандат». Решение Оператора 24.10.2026
(«Бери»): одновременно идут до трёх волн, третья — из модуля merge.
Параллельно идут 2а-1б (01M5QAEPC6RF097YQ43T3Y56D9) и 2б-4
(01M5QG7KXQWJDEWRHAWZFQBXET); файлы волн не пересекаются. Модули волны —
`orchestrator/merge_lock.py` и `orchestrator/merge_queue.py`. Факты ТЗ
сверены с origin/main ec948ea4. Аналитик повторно сверил с деревом ветки
число строк, байтов, тестов и заявок, а также строки, названные ниже.

Файлы волны (не долгоживущие, в стиле unittest):
- `tests/test_merge_lock.py` (далее «замок»):
  - 384 строки (18 162 байта), 18 тестов, 7 заявок «Ловит мутацию» (все в
    `ProcessOwnershipTest`);
  - классы на `TmpRootTest`: `AcquireReleaseTest` (:24), `ProcessOwnershipTest`
    (:125), `RunWindowTest` (:276), `ConcurrentAcquireTest` (:335);
  - у `ConcurrentAcquireTest`: `THREADS = 8` (:344),
    `threading.Barrier(self.THREADS)` (:357), `.wait(timeout=5)`,
    `join(timeout=10)` (:374);
  - собственные `setUp` — :28, :135 (цикл `for tid, branch` :137), :283
    (по AST тело то же, что у :28, отличается только переносом строк), :346;
  - атрибуты классов `TASK = "T001"`, `HOLDER_TASK = "T999"`.
- `tests/test_merge_queue.py` (далее «очередь»):
  - 329 строк (15 606 байт), 19 тестов, 9 заявок;
  - базовый класс `_QueueTestBase(TmpRootTest)` (:25) с `TASK_A`, `TASK_B`,
    `TASK_C` и `setUp` :30; классы с :44 по :278;
  - `time.monotonic` и пауза подменяются в :178, :267, :314;
  - `test_free_mutex_registers_then_immediately_takes_the_window` (:280)
    настоящую паузу не подменяет. Если окно не берётся сразу, тест спит по
    90 с (`orchestrator/config.py:178`) до таймаута pytest-timeout 120 с.
- `tests/test_merge_lock_by_project.py` (далее «by_project»):
  - 159 строк (8 426 байт), 3 теста, 3 заявки;
  - константа модуля `OTHER_HOST` (:14), базовый класс `_Base(TmpRootTest)`
    (:17) с `setUp` :19, который задаёт `self.conn` и `self.counter`;
  - `LegacyTouchHeartbeatTest` (:54) проверяет `merge_lock`;
    `WaitForWindowOtherProjectQueueTest` (:83) и `WaitTextsAnyOrderTest` (:116)
    — `merge_queue`;
  - наборы `subTest` — :67, :95, :130, все с общим состоянием: счётчик
    `counter` стенда и `old` (:65), созданный до цикла;
  - подмена паузы `fake_sleep` падает строкой `raise AssertionError("задача P
    ушла в паузу очереди")` (:105).

Всего 40 тестов и 19 заявок; 21 тест заявки не имеет. Методов с утверждениями
у классов трёх файлов нет.

Методы без утверждений:
- `row` — :38, :143, :292, одинаковые;
- `seed` — :41 `(session_id, pid, hostname, heartbeat_ts, task_id)` и :146
  `(session_id, pid, hostname=None, heartbeat_ts=None)`, тела разные;
- `enqueue` (:39), `rows_by_pid` (:193);
- `new_task` (:27), `seed_lock` (:34), `locks` (:44), `clear` (:48).

Вложенные `fake_sleep`, `fake_monotonic`, `worker` остаются вложенными.
Тексты исключений проверяются формой `assertIn(<текст>, str(ctx.exception))`
(замок :317, :319; очередь :319); `assertRaisesRegex` нет. Строки
`sys.path.insert` — замок :17, очередь :18.

Один прогон трёх файлов без параллельных процессов pytest занимает около 5 с.
Суммы по файлам — 2,6 / 1,9 / 0,2 с, самый долгий тест — 0,3 с.

Связи вне волны:
- Импортов из трёх файлов нет.
- Путь `tests/test_merge_queue.py` проверяет долгоживущий
  `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py:257–259`: `assertIn` в
  списке просмотренных файлов, его строит `scan_tests_tree` (:104–116).
  Поэтому файл очереди не удаляется, а переписывается на месте.
- Описания модулей `tests/test_merge_gate_ci_wait.py:8` и
  `tests/test_release.py:8` упоминают `tests/test_merge_lock.py` и остаются
  как есть.

Общие фикстуры — `tests/fixtures.py`: `tmp_dir`, `tmp_root`,
`initialized_tmp_root`, `real_git`, `origin_real_git`, `light_transition`.
Адаптер `_sandbox(cls)` (:42) сам исполняет уборку `addCleanup`. Фикстура
`tmp_root` (:65) отдаёт экземпляр `TmpRootTest` после `setUp()`.
`_alive_foreign_pid(testcase)` (`tests/sandbox.py:1042`) регистрирует уборку
через `testcase.addCleanup`. Тесты берут БД через `store.db()` по подменённым
путям `config`. guard считает утверждением `assert`, вызовы `assert…`/`fail`
и `pytest.raises`/`pytest.warns` (`scripts/guard.py:1530–1535`); текст
сообщения нормализатор отбрасывает.

Гейт ёмкости диффа — 262 144 байта; оценка диффа задачи — около 100 КБ.
`mutation-run` (с 24.10) принимает:
- `--workers <n>`;
- `--wait-lock <минуты>` (сумма с `--wait` — не больше 9 минут);
- `--copy-table`.

Предел части — 1500 с на контроль и все патчи. Параллельно идут прогоны двух
других волн.

Шаг роли — 2700 с. Пульт сам коммитит рабочую копию разработчика в пределах
зон. Роль на Claude пишет в каталог документов задачи и в `$TMPDIR` командой
`python3`. Мандат выдаётся командой `answer`.

## Требования

1. Мутации «до», патчи. Заявку «Ловит мутацию» получает каждый из 21 теста
   без заявки. Заявка называет правдоподобную мутацию кода
   `orchestrator/merge_lock.py`, `orchestrator/merge_queue.py` или
   `orchestrator/store.py`, которую тест ловит. Для каждой из 19 существующих
   и 21 новой заявки — патч к коду `orchestrator/` в
   `tasks/<id>/mutation-<nnn>.diff`, номера подряд с 001. Патч реализует ровно
   мутацию заявки. Одинаковые по смыслу заявки — одна мутация со списком
   тестов.
2. Таблица «до». Команда — `mutation-run <id> --ref base --tests
   tests/test_merge_lock.py,tests/test_merge_queue.py,tests/test_merge_lock_by_project.py
   --copy-table --wait-lock 4`, частями `--patches` не больше 25 патчей.
   - Отчёт части получают повторными `mutation-run <id> --wait 5` до итоговой
     строки.
   - Вывод части переносится в PLAN, раздел «Мутации до», дословно, с шапкой и
     всеми строками, до старта следующей части.
   - Патчи, после которых окно может не взяться, идут отдельной частью не
     больше 8 патчей.
   - Часть, оборванная пределом: её патчи переписываются и раскладываются по
     частям. Тем же набором её не прогоняют.
3. Строка падения. У каждой мутации в PLAN для таблиц «до» и «после» —
   строка падения из лога прогона патча (файл:строка). Строка `raise
   AssertionError` в подмене паузы (by_project :105) считается строкой
   падения.
4. Не доказательство — мутация, «убитая» одним из способов:
   - ошибкой сбора, импорта или setup;
   - исключением без падения утверждения;
   - только утверждением подготовки;
   - по таймауту pytest-timeout (`Timeout` в логе).

   Такой патч переписывается. Мутации пути взятия окна и цикла
   `wait_for_window` выбираются так, чтобы тест падал утверждением, а не
   зависал.
5. Детерминированность и находки.
   - Мутация, которую проверяет `ConcurrentAcquireTest`, обязана убиваться
     детерминированно.
   - Если «до», «после» и повтор расходятся в исходе «убита / не убита»,
     заявка переписывается. Повторять прогон до убийства запрещено.
   - Мутация, не убитая никем, — находка в PLAN.
   - Исходы «итог неизвестен», «патч не применяется», «патч трогает тесты»,
     «не прогнана» — патч переписывается и прогоняется заново.
6. Красный контроль.
   - Первый красный контроль — повтор тем же вызовом в следующем шаге.
   - Повторно красный — повтор с `--workers 4`.
   - Красный и тогда — `escalate` с логом контроля; тесты и пределы не
     трогаются.

   Ожидание замка — только `--wait-lock`; циклы и сценарии ожидания
   запрещены.
7. Временные файлы в рабочей копии не создаются. Допустимы:
   - файл первого уровня каталога документов задачи с расширением не `.md` и
     именем не `test_*`/`mutation-*`;
   - файл в `$TMPDIR`, созданный командой `python3`;
   - копии `mutation-run-<n>.tsv` команды.

   К концу каждого шага `git status --porcelain` называет только:
   - новый `tests/test_merge_lock_module.py`;
   - изменённый `tests/test_merge_queue.py`;
   - удаление `tests/test_merge_lock.py` и `tests/test_merge_lock_by_project.py`;
   - `docs/codebase-map.md` (только вывод генератора).
8. Свод по файлам, в стиле pytest:
   - тесты замка и класса `LegacyTouchHeartbeatTest` → в новый
     `tests/test_merge_lock_module.py`;
   - тесты прежнего `tests/test_merge_queue.py`,
     `WaitForWindowOtherProjectQueueTest` и `WaitTextsAnyOrderTest` → в
     `tests/test_merge_queue.py`, переписанный на месте.
9. Стенды.
   - Песочница — фикстура `tmp_root` из `tests/fixtures.py`.
   - `setUp` каждого класса, а также `_QueueTestBase` и `_Base`, становится
     собственной фикстурой файла поверх `tmp_root` без утверждений. Тело —
     дословно, без `super().setUp()`, `self.` заменено параметром.
   - Одинаковые тела — одна фикстура.
   - Общая часть `_Base` — своя фикстура в каждом из двух файлов, тела
     одинаковые.
   - Имена фикстур не совпадают с фикстурами `tests/fixtures.py`.
   - Атрибуты классов (`TASK`, `HOLDER_TASK`, `THREADS`, `TASK_A`, `TASK_B`,
     `TASK_C`) — константы модуля с теми же именами и литералами. `OTHER_HOST`
     — константа модуля с тем же литералом.
   - `_alive_foreign_pid` получает стенд; уборку `addCleanup` исполняет
     `_sandbox`.
10. Методы классов без утверждений (`row`, `seed`, `enqueue`, `rows_by_pid`,
    `new_task`, `seed_lock`, `locks`, `clear`) становятся функциями модуля:
    - первый параметр — стенд, тело дословно, `self.` заменено именем
      параметра;
    - вызовы перенесённых помощников — вызовы функций;
    - одинаковые по телу — одна функция;
    - одноимённые с разным телом (`seed`) — с префиксом бывшего класса:
      `acquire_release_seed`, `process_ownership_seed`;
    - перечень — в PLAN.
11. Утверждения и проверяемые свойства не меняются.
    - Ожидания дословно, форма — `assert …` (ADR-0027).
    - Литерал остаётся литералом, константа — константой; равенство значений
      доводом не считается.
    - Голый `assertRaises(E)` → `pytest.raises(E)`.
    - `assertIn(<текст>, str(ctx.exception))` → `assert <текст> in
      str(excinfo.value)` после блока; `match=` не используется.
    - Текст `msg=` — `pytest.fail(<текст>)` последней строкой блока либо
      вторым операндом `assert`.
    - Наборы `subTest` :67, :95, :130 — прежним циклом; ярлык подслучая — в
      тексте сообщения каждого утверждения подслучая.
    - `raise AssertionError` в подмене паузы, потоки, барьеры и пределы
      ожидания `ConcurrentAcquireTest` — дословно.
    - Не переносятся: `unittest`, `sys.path.insert` (замок :17, очередь :18),
      неиспользуемые импорты, `if __name__ == "__main__"`.
12. Дубли.
    - Дубль удаляется только если выполнены оба условия:
      - (а) каждую его мутацию по таблице «до» убивает и другой сохраняемый
        тест;
      - (б) каждый литерал и вид каждого утверждения удаляемого теста есть в
        сохраняемом.
    - Удалённые дубли — в PLAN.
    - Тест, чью мутацию не убил никто, не удаляется: его заявка переписывается
      на мутацию, которую он убивает, либо он становится находкой в PLAN.
    - У каждой функции-теста — «Ловит мутацию:».
13. Таблица «после». Команда — `mutation-run <id> --ref worktree --tests
    tests/test_merge_lock_module.py,tests/test_merge_queue.py --copy-table
    --wait-lock 4`, теми же диапазонами `--patches` и тем же `--workers`, что
    «до». Вывод — в PLAN, раздел «Мутации после», дословно. Перед каждой
    частью — пустой вывод `git status --porcelain -- orchestrator/`.
14. Соответствие «до» и «после».
    - Мутацию, убитую «до» тестом T, «после» убивает функция, в которую
      перенесён T, тем же утверждением. «То же» значит ту же нормальную форму
      guard, а для `raise AssertionError` — тот же текст строки. Соответствие
      — в PLAN.
    - Дерево `orchestrator/` ревизий обеих шапок совпадает; sha256 каждого
      патча совпадает.
    - При подтяжке main с изменением `orchestrator/` таблица «до» прогоняется
      заново.
15. Прогоны и замеры. Под ролью адресно прогоняются только два файла модулей
    (`tests/test_merge_lock_module.py`, `tests/test_merge_queue.py`). Время
    «до» и «после» берётся по контрольным прогонам `mutation-run`. В PLAN —
    число тестов и строк до и после.
16. Удаление и мандат.
    - `tests/test_merge_lock.py` и `tests/test_merge_lock_by_project.py`
      удаляются, `tests/test_merge_queue.py` переписывается.
    - Мандат — `answer` на эти три пути.
    - Не разрешены: удаление утверждения без переноса, ослабление сравнения,
      `skip`/`xfail`, подъём пределов.
17. Ограничение зон по смыслу. Не меняются:
    - `tests/fixtures.py`, `tests/sandbox.py`, `tests/test_invariants.py`;
    - `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`,
      `tests/test_merge_gate_ci_wait.py`, `tests/test_release.py`;
    - файлы волн 2а-1б и 2б-4: `tests/test_outcome_gate_module.py`,
      `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`,
      `tests/test_report_outcome_module.py`,
      `tests/test_component_report_gates.py`;
    - код `orchestrator/`.

    `docs/codebase-map.md` — только вывод генератора.
18. Независимая проверка — сессией при Операторе до approve на merge_gate:
    повтор `mutation-run` и сравнение утверждений по AST.

## Критерии приёмки

AC-1. Патчи и заявки.
- В каталоге документов задачи первым уровнем лежат патчи
  `mutation-<nnn>.diff`, номера подряд с 001 без пропусков; каждый патч меняет
  только файлы под `orchestrator/`.
- У каждого из 40 исходных тестов есть заявка «Ловит мутацию»: 19 прежних и 21
  новая, каждая новая называет мутацию кода `orchestrator/merge_lock.py`,
  `orchestrator/merge_queue.py` или `orchestrator/store.py`.
- В PLAN каждая заявка сопоставлена патчу. Одинаковые по смыслу заявки
  сведены в одну мутацию со списком тестов.

AC-2. Раздел «Мутации до» в PLAN.
- В нём выводы частей `mutation-run <id> --ref base --tests
  tests/test_merge_lock.py,tests/test_merge_queue.py,tests/test_merge_lock_by_project.py
  --copy-table --wait-lock 4`, перенесённые дословно, с шапкой и всеми
  строками.
- Каждая часть — не больше 25 патчей; часть с патчами, после которых окно может
  не взяться, — не больше 8.
- В таблицах есть каждый патч набора.

AC-3. У каждой мутации в PLAN для таблиц «до» и «после» приведена строка
падения из лога прогона патча (файл:строка). Для подмены паузы by_project это
строка `raise AssertionError` (:105).

AC-4. Засчитывание мутаций.
- Ни одна мутация не засчитана доказательством, если её «убили» только:
  ошибка сбора, импорта или setup; исключение без падения утверждения;
  утверждение подготовки; таймаут pytest-timeout (`Timeout` в логе).
- Ни одна мутация с исходом «итог неизвестен», «патч не применяется», «патч
  трогает тесты» или «не прогнана» не засчитана ни убитой, ни выжившей.
- Мутации, которые «до» не убил никто, перечислены в PLAN находками.

AC-5. Мутации, которые проверяет `ConcurrentAcquireTest`, убиты в «до» и
«после» одинаково. Ни у одной мутации исход «убита / не убита» в «до», «после»
и повторе не расходится.

AC-6. Рабочая копия к концу шага. `git status --porcelain` называет только:
новый `tests/test_merge_lock_module.py`, изменённый `tests/test_merge_queue.py`,
удаление `tests/test_merge_lock.py` и `tests/test_merge_lock_by_project.py` и
`docs/codebase-map.md`. Файлы первого уровня каталога документов задачи с
расширением не `.md`, кроме патчей `mutation-<nnn>.diff` и копий
`mutation-run-<n>.tsv`, не называются `test_*` и `mutation-*`.

AC-7. Файлов на ветке:
- Файлов `tests/test_merge_lock.py` и `tests/test_merge_lock_by_project.py` на
  ветке нет.
- `tests/test_merge_lock_module.py` несёт тесты замка и
  `LegacyTouchHeartbeatTest`.
- `tests/test_merge_queue.py` несёт тесты прежнего файла очереди,
  `WaitForWindowOtherProjectQueueTest` и `WaitTextsAnyOrderTest`.

AC-8. В двух файлах модулей нет тестовых классов, `subTest`, импорта
`unittest`, `sys.path.insert`, блока `if __name__ == "__main__"` и
неиспользуемых импортов.

AC-9. Фикстуры.
- Фикстуры файлов построены поверх `tmp_root` и не содержат утверждений.
- Тело каждой фикстуры равно телу исходного `setUp` (`_QueueTestBase`, `_Base`
  — тоже) без `super().setUp()`, с заменой `self.` параметром.
- Одинаковые тела сведены в одну фикстуру в пределах файла. Фикстура общей
  части `_Base` есть в каждом из двух файлов, тела одинаковые.
- Имена фикстур не совпадают с фикстурами `tests/fixtures.py`.

AC-10. Константы и стенд.
- `TASK`, `HOLDER_TASK`, `THREADS`, `TASK_A`, `TASK_B`, `TASK_C`, `OTHER_HOST` —
  константы модуля с прежними именами и литералами.
- `_alive_foreign_pid` вызывается со стендом.

AC-11. Помощники.
- Методы `row`, `seed`, `enqueue`, `rows_by_pid`, `new_task`, `seed_lock`,
  `locks`, `clear` — функции модуля: первый параметр — стенд, тело дословно с
  заменой `self.` именем параметра, вызовы перенесённых помощников — вызовы
  функций.
- Одинаковые по телу сведены в одну функцию; два `seed` названы
  `acquire_release_seed` и `process_ownership_seed`. Перечень есть в PLAN.
- `fake_sleep`, `fake_monotonic`, `worker` остаются вложенными.

AC-12. Ожидания перенесённых тестов совпадают с исходными дословно в форме
`assert …`.
- Литерал остался литералом, константа — константой; ни одно сравнение не
  ослаблено.
- На месте голого `assertRaises(E)` — `pytest.raises(E)`.
- На месте `assertIn(<текст>, str(ctx.exception))` — `assert <текст> in
  str(excinfo.value)` после блока; `match=` нигде не используется.
- Текст `msg=` — `pytest.fail(<текст>)` последней строкой блока либо второй
  операнд `assert`.

AC-13. Циклы, паузы, потоки.
- Наборы `subTest` :67, :95, :130 — прежним циклом в одной функции; ярлык
  подслучая есть в тексте сообщения каждого утверждения подслучая.
- `raise AssertionError("задача P ушла в паузу очереди")` в подмене паузы, а
  также потоки, `threading.Barrier`, `wait(timeout=5)`, `join(timeout=10)` и
  `THREADS = 8` перенесены дословно.

AC-14. Дубли.
- У каждой функции-теста есть строка «Ловит мутацию:».
- Каждый исходный тест, не перенесённый в модуль, перечислен в PLAN удалённым
  дублем с его мутациями, и для него выполнены условия (а) и (б) требования 12.
- Тест, чью мутацию не убил никто, не удалён.

AC-15. Раздел «Мутации после» в PLAN.
- В нём выводы `mutation-run <id> --ref worktree --tests
  tests/test_merge_lock_module.py,tests/test_merge_queue.py --copy-table
  --wait-lock 4` теми же диапазонами `--patches` и тем же `--workers`, что
  «до», перенесённые дословно.
- Перед каждой частью — пустой вывод `git status --porcelain -- orchestrator/`.

AC-16. Соответствие «до» и «после».
- Каждая мутация, убитая «до» тестом T, «после» убита функцией, в которую
  перенесён T, тем же утверждением: та же нормальная форма guard, для `raise
  AssertionError` — тот же текст строки. Соответствие приведено в PLAN.
- Шапки «до» и «после» согласованы: дерево `orchestrator/` их ревизий
  совпадает, sha256 каждого патча совпадает.
- В PLAN названы число тестов, число строк и время по контрольным прогонам
  `mutation-run` до и после свода.

AC-17. Дифф ветки против базы — только: новый
`tests/test_merge_lock_module.py`, правка `tests/test_merge_queue.py`,
удаление `tests/test_merge_lock.py` и `tests/test_merge_lock_by_project.py` и
`docs/codebase-map.md`, равный выводу `python3 scripts/codebase_map.py` на
дереве ветки. Файлы требования 17 и всё под `orchestrator/` не изменены. В
двух файлах модулей нет `skip`/`xfail`, пределы не выше исходных.

## Оценка объёма и деление

Сработавшие сигналы:
- `budget_usd` ≥ $30 — ставка $60 из ТЗ («Бюджет: $60»);
- число критериев приёмки ≥ 10 — их 17.

Обоснование монолита (материал для решения Оператора на гейте SPEC).
Оператор уже нарезал семейство merge по волнам (3м-1…3м-5); 3м-1 — замок и
очередь одного механизма merge-окна. Прогноз диффа около 100 КБ — меньше
половины гейта ёмкости. Внутри задачи части неделимы:
- Тесты by_project расходятся по обоим целевым файлам
  (`LegacyTouchHeartbeatTest` — в модуль замка, два класса — в модуль
  очереди). Файл by_project удаляется только когда перенесены все три теста.
- Перенос без удаления исходных файлов оставляет полные дубли. Удаление без
  переноса теряет покрытие.
- Доказательство сравнивает убийства «до» на трёх исходных файлах с
  убийствами «после» на двух модулях одним набором патчей при неизменном
  `orchestrator/`. Мандат — один `answer` на три пути.

Зона — `tests/` (два файла удаляются, один новый, один переписан) плюс
регенерация карты; резать по смыслу нечего.

## Не входит

- Долгоживущий `tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py`.
- Прочие файлы семейства merge (`merge_after`, `fsm_postmerge`, `pull`,
  `pull_main`, `fsm_merge_gate`) — волны 3м-2…3м-5.
- Правка общих фикстур и песочниц (`tests/fixtures.py`, `tests/sandbox.py`).
- Правка описаний модулей `tests/test_merge_gate_ci_wait.py:8`,
  `tests/test_release.py:8` и долгоживущего
  `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`.
- Изменение кода пульта `orchestrator/`; мутации — только во временной копии
  `mutation-run`.
- Независимая проверка (требование 18) — её делает сессия при Операторе, не
  роль.

## Материалы

- SPEC волны 2б-4: `refs/artifacts/01M5QG7KXQWJDEWRHAWZFQBXET`,
  `tasks/01M5QG7KXQWJDEWRHAWZFQBXET/SPEC.md`.
- ADR-0027 п. 8, ADR-0020 п. 8; `docs/backlog.md` — строка 23.10.

Только чтение: orchestrator/ (весь код пульта; мутации — только во временной
копии `mutation-run`), orchestrator/merge_lock.py, orchestrator/merge_queue.py,
orchestrator/store.py, orchestrator/config.py, orchestrator/stack.py,
orchestrator/advance_gates/mandate.py,
orchestrator/advance_gates/test_integrity.py,
orchestrator/advance_gates/capacity.py, orchestrator/mutation_run.py,
orchestrator/checkpoint.py, tests/fixtures.py, tests/sandbox.py,
scripts/guard.py, scripts/codebase_map.py, tests/test_invariants.py,
tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py, conftest.py,
pyproject.toml, targets.yaml, skills/test-authoring.md,
docs/adr/0027-pytest-style-tests.md,
docs/adr/0020-long-lived-acceptance-tests-in-tests.md.
