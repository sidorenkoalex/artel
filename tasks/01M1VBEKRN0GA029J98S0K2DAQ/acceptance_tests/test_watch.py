"""Приёмочные тесты 01M1VBEKRN0GA029J98S0K2DAQ — команда `watch`: дозор
событий журнала для сессии Оператора (AC-1..AC-14, SPEC.md).

Красен до реализации: `orchestrator/watch.py` ещё не существует — импорт
модуля обёрнут в `try/except ImportError` (иначе весь файл не собрался бы
единой ошибкой загрузки, и трассируемость AC потеряла бы имена методов),
`watch` остаётся `None`. Тесты AC-2..AC-8, AC-10..AC-13 запускают
`watch.cmd_watch` в фоновом потоке — обращение к `None.cmd_watch` кидает
`AttributeError`, который `_wait_until` ловит и превращает в быстрый и
явный `self.fail(...)` (не ждёт полный таймаут вслепую). AC-1 зовёт
`watch.cmd_watch` напрямую — тот же `AttributeError` рвёт
`assertRaises(SystemExit)` и репортится как ERROR. AC-9 падает по другой,
самостоятельной причине: `docs/operator-session.md`, п.4 которого ещё не
переписан на `artel.py watch --mine`.

## Допущения интерфейса, которые вводит этот файл

Ничего из перечисленного не описано SPEC буквально — SPEC описывает
только CLI-контур (`artel.py watch --tasks/--mine/--all ...`), не
внутреннюю точку входа, которую ещё не выбрал разработчик. Тесты бьют
по единственной публичной функции модуля `watch`, тем же приёмом, что
уже применялся для лимитера параллельных задач (tasks/T060) — через
наблюдаемое поведение, а не воображаемую внутреннюю структуру:

- `orchestrator.watch.cmd_watch(argv: list[str]) -> None` — единственная
  точка входа модуля, разбирает СЫРОЙ список аргументов после `watch`
  сама (монолит по решению Оператора 06.09, SPEC «Оценка объёма» —
  «резать нечего»). Ошибка использования — `sys.exit(...)`; успешное
  завершение — обычный `return`. Другой сигнатуры (например,
  предварительно распарсенных kwargs, как у `canary.cmd_canary(k=N)`)
  этот файл не предполагает — она подошла бы командам с одним-двумя
  флагами, а не шести флагам с зависимостями между ними.
- `--interval` принимает дробные секунды (`float`) — SPEC фиксирует
  только единицу измерения и дефолт (30), не тип парсинга; без дробного
  интервала эти тесты ждали бы реальные десятки секунд на каждую
  проверку. Тесты передают `--interval` часто ЦЕЛЫМ (`"1"`), что валидно
  и для `int()`, и для `float()` — искобычно как раз этого выбора
  реализации тесты не боятся; расчёт на дробную секунду был бы более
  быстрым, но менее надёжным (не проверяется отдельно).
- Цикл опроса реализован через `time.sleep(interval)` между итерациями —
  тесты НЕ патчат `time.sleep` (общий процессный объект, патч задел бы и
  собственный таймер тестов), а просто дают команде реальное время
  через `--interval` и терпеливый `_wait_until`/`join(timeout=...)`.

Валидация стабом (решение Оператора 03.09, обязательно перед сдачей):
временная корректная реализация `orchestrator/watch.py` прогонялась
поверх этого файла — все тесты дали `OK`; стаб удалён без коммита.
"""
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, session, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

try:
    from orchestrator import watch  # noqa: E402
except ImportError:
    watch = None


# Те же 4 состояния, что несёт флаг «ЖДЁТ ОПЕРАТОРА» в `catalog.cmd_status`
# (SPEC AC-3, «gates» — подмножество «transitions»).
GATE_STATES = ("spec_gate", "acceptance", "merge_gate", "escalated")


def _exit_status(code) -> int:
    """Код возврата процесса, который дал бы `sys.exit(code)` — воспроизводит
    поведение самого Python (`None` -> 0, `int` -> он сам по модулю 256,
    любой другой объект, включая строку сообщения, -> 1), а не сравнение
    „в лоб” с `0` (строковое сообщение об ошибке не равно `int 0`, но и не
    обязано буквально совпадать по типу — важен именно код ПРОЦЕССА)."""
    if code is None:
        return 0
    if isinstance(code, int):
        return code % 256
    return 1


class _Stream:
    """Потокобезопасный приёмник stdout фонового потока `watch`: пишет в
    список чанков без всякой внутренней буферизации (значение видно сразу
    же после `write`), но ОТДЕЛЬНО считает вызовы `flush()` — только этот
    счётчик способен отличить «пишет и сразу же flush()ит» от «пишет без
    flush» (AC-2): при in-memory приёмнике вроде этого текст виден в
    `getvalue()` в любом случае, будь то `print(x)` или `print(x,
    flush=True)` — разница ловится исключительно счётчиком."""

    def __init__(self):
        self._chunks = []
        self._lock = threading.Lock()
        self.flush_calls = 0

    def write(self, s):
        with self._lock:
            self._chunks.append(s)

    def flush(self):
        with self._lock:
            self.flush_calls += 1

    def getvalue(self) -> str:
        with self._lock:
            return "".join(self._chunks)


class _WatchTestCase(TmpRootTest):
    """Общая песочница: схема БД без `cmd_init` (та же лёгкая заготовка,
    что `RealGitSandbox.setUp` — `create_schema` идемпотентна) — `watch`
    не трогает git и роли, поднимать их песочнице незачем."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self._stream = None
        self._thread = None
        self._watch_outcome = None

    def _insert_task(self, task_id: str, state: str = "in_dev",
                     target: str = None) -> None:
        store.insert_task(
            store.db(), task_id, f"Задача {task_id}", state,
            f"task/{task_id.lower()}", target or config.DEFAULT_TARGET, 25.0)

    def _set_state(self, task_id: str, new_state: str, expected: str) -> None:
        store.set_state(store.db(), task_id, new_state, "operator",
                        expected_state=expected)

    def _start(self, argv: list) -> threading.Thread:
        self._stream = _Stream()
        self._watch_outcome = {}
        thread = threading.Thread(target=self._worker, args=(argv,),
                                  daemon=True)
        self._thread = thread
        # Регистрируется РАНЬШЕ снятия патчей `config` (те регистрирует
        # `TmpRootTest.setUp` раньше по времени — cleanup идёт LIFO, так
        # что этот запустится ПЕРВЫМ): без него упавшая на середине
        # `_wait_until`/assert проверка оставляет цикл `watch` живым в
        # фоне навсегда (у него нет отмены снаружи) — следующий тест
        # переподменяет `config.DB` на СВОЙ временный путь, и осиротевший
        # поток начинает опрашивать чужую (следующую) песочницу, унаследовав
        # атрибут `config.DB` по имени, а не по значению на момент старта.
        self.addCleanup(self._force_stop)
        thread.start()
        return thread

    def _force_stop(self) -> None:
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        try:
            conn = store.db()
            conn.execute("UPDATE tasks SET state='killed'")
            conn.commit()
        except Exception:  # noqa: BLE001 — best-effort, тест уже упал
            pass
        thread.join(timeout=3.0)

    def _worker(self, argv: list) -> None:
        old_stdout = sys.stdout
        sys.stdout = self._stream
        try:
            watch.cmd_watch(argv)
            self._watch_outcome["exit_code"] = 0
        except SystemExit as exc:
            self._watch_outcome["exit_code"] = _exit_status(exc.code)
        except BaseException as exc:  # noqa: BLE001 — диагностика падения потока
            self._watch_outcome["exception"] = exc
        finally:
            sys.stdout = old_stdout

    def _settle(self, seconds: float = 0.3) -> None:
        """Пауза после `_start`, ДО первой мутации БД тестом: баз��вый
        снимок `watch` (id последнего известного `steps`/состояние задачи)
        снимается в фоновом потоке асинхронно относительно `thread.start()`
        — без паузы возможна гонка, где тестовая правка успевает попасть
        в БД РАНЬШЕ этого снимка, и тогда `watch` примет её за
        «историческую» (уже учтённую базой), а не за новую: событие
        молча не появится в потоке, тест упадёт таймаутом `_wait_until`
        по причине, не имеющей отношения к проверяемому свойству."""
        time.sleep(seconds)

    def _wait_until(self, predicate, timeout: float = 6.0,
                    interval: float = 0.02) -> None:
        gate = threading.Event()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # Быстрый отказ, если фоновый поток УЖЕ упал (например,
            # `orchestrator.watch` ещё не существует — `watch is None`,
            # `watch.cmd_watch` кидает `AttributeError` немедленно): без
            # этой проверки тест ждал бы полный `timeout`, прежде чем
            # честно сказать, что дело не в условии, а в упавшем потоке.
            if self._watch_outcome and "exception" in self._watch_outcome:
                exc = self._watch_outcome["exception"]
                self.fail(f"поток watch упал: {exc!r}")
            if predicate():
                return
            gate.wait(interval)
        self.fail(
            "условие не выполнено за отведённое время; вывод потока:\n"
            + (self._stream.getvalue() if self._stream else "<нет>"))

    def _join(self, timeout: float = 8.0) -> None:
        self._thread.join(timeout=timeout)
        self.assertFalse(self._thread.is_alive(),
                         "watch не завершился за отведённое время")
        if "exception" in self._watch_outcome:
            raise self._watch_outcome["exception"]


class SelectorUsageTest(TmpRootTest):
    """НЕ наследует `_WatchTestCase`: тот заводит схему БД (`store.
    create_schema(store.db())`) уже в своём `setUp` — файл БД появился бы
    на диске ДО начала теста и `assertFalse(config.DB.exists())` был бы
    неверным по конструкции, а не по факту обращения `cmd_watch`."""

    def test_ac1_selector_flags_are_validated_before_any_db_access(self):
        """Ни один селектор, либо более одного сразу — отказ использования
        ДО обращения к БД.

        Разыгрывает три вызова `cmd_watch`: без `--tasks`/`--mine`/`--all`,
        с `--tasks`+`--mine`, и со всеми тремя разом — каждый обязан
        завершиться `SystemExit` с ненулевым кодом процесса и не создать
        файл БД (`config.DB` патчен на путь, ещё не существующий на диске —
        `store.db()` создаёт его каталог первым же обращением).
        Ловит мутацию: разбор селекторов сперва зовёт `store.db()` (чтобы,
        скажем, проверить существование задачи), а уже потом требование
        «ровно один селектор» — файл БД появится на диске ДО отказа, и
        `assertFalse(config.DB.exists())` покраснеет.
        """
        self.assertFalse(config.DB.exists())

        with self.assertRaises(SystemExit) as cm:
            watch.cmd_watch(["--interval", "1"])
        self.assertNotEqual(_exit_status(cm.exception.code), 0)
        self.assertFalse(config.DB.exists(),
                         "watch обратился к БД без единого селектора")

        with self.assertRaises(SystemExit) as cm2:
            watch.cmd_watch(["--tasks", "T001", "--mine", "--interval", "1"])
        self.assertNotEqual(_exit_status(cm2.exception.code), 0)
        self.assertFalse(config.DB.exists(),
                         "watch обратился к БД при двух селекторах")

        with self.assertRaises(SystemExit) as cm3:
            watch.cmd_watch(["--tasks", "T001", "--mine", "--all"])
        self.assertNotEqual(_exit_status(cm3.exception.code), 0)
        self.assertFalse(config.DB.exists(),
                         "watch обратился к БД при трёх селекторах")


class StreamFormatTest(_WatchTestCase):

    def test_ac2_prints_only_new_steps_with_flush_and_log_schema(self):
        """Поток печатает НОВЫЕ строки `steps` схемой `log` (ts, задача,
        actor, action, `| detail`) с flush на каждой строке; исторические
        записи (до старта `watch`) не печатаются.

        Ловит мутацию: реализация читает `task_steps` целиком при каждой
        итерации без отсечения по стартовому id — историческая строка
        `историческая-метка-строки` попадёт в вывод, и
        `assertNotIn` на неё покраснеет.
        """
        conn = store.db()
        self._insert_task("T001")
        store.journal(conn, "T001", "operator", "историческое событие",
                     "историческая-метка-строки")

        self._start(["--tasks", "T001", "--interval", "1"])
        self._settle()

        store.journal(conn, "T001", "runner", "agent run started",
                     "новая-метка-детали")
        row = store.task_steps(conn, "T001")[-1]
        self.assertEqual(row["detail"], "новая-метка-детали")

        def _line_matches():
            for line in self._stream.getvalue().splitlines():
                if not all(part in line for part in
                          (row["ts"], "T001", row["actor"], row["action"],
                           f"| {row['detail']}")):
                    continue
                positions = [line.index(row["ts"]), line.index("T001"),
                            line.index(row["actor"]), line.index(row["action"]),
                            line.index(f"| {row['detail']}")]
                if positions == sorted(positions):
                    return True
            return False

        self._wait_until(_line_matches)
        self.assertNotIn("историческая-метка-строки", self._stream.getvalue())

        lines_printed = self._stream.getvalue().count("\n")
        self.assertGreaterEqual(self._stream.flush_calls, lines_printed,
                                "watch не делает flush на каждую напечатанную строку")

        self._set_state("T001", "done", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class DefaultEventClassesTest(_WatchTestCase):

    def test_ac3_default_classes_cover_four_kinds_and_dedupe_overlap(self):
        """Без `--events` активны РОВНО `transitions,refusals,gates,steps`;
        запись, подпадающая под два класса разом (`state -> spec_gate`),
        печатается один раз, `бюджет`/нерелевантные записи не печатаются.

        Ловит мутацию: дефолт заужен до одних `transitions` (тогда
        `refusals`/`steps`-маркеры не появятся) либо расширен до «всё
        подряд» (тогда `бюджет`-маркер появится) — оба случая ловят
        соответствующие `assertIn`/`assertNotIn`; дедуп ловит
        `assertEqual(..., 1)` по счётчику вхождений.
        """
        conn = store.db()
        self._insert_task("T002")

        self._start(["--tasks", "T002", "--interval", "1"])
        self._settle()

        store.journal(conn, "T002", "fsm", "state -> tests_writing",
                     "маркер-transitions-only")
        store.journal(conn, "T002", "fsm", "state -> spec_gate",
                     "маркер-gate-and-transition")
        store.journal(conn, "T002", "fsm", f"{store.REFUSAL_ACTION_PREFIX}: причина",
                     "маркер-refusal")
        store.journal(conn, "T002", "runner", "agent run started",
                     "маркер-steps")
        store.journal(conn, "T002", "budget", "бюджет: превышен потолок",
                     "маркер-budget-excluded")
        store.journal(conn, "T002", "operator", "нечто нерелевантное",
                     "маркер-noise-excluded")

        self._wait_until(
            lambda: "маркер-steps" in self._stream.getvalue())

        out = self._stream.getvalue()
        self.assertIn("маркер-transitions-only", out)
        self.assertIn("маркер-gate-and-transition", out)
        self.assertIn("маркер-refusal", out)
        self.assertIn("маркер-steps", out)
        self.assertNotIn("маркер-budget-excluded", out)
        self.assertNotIn("маркер-noise-excluded", out)
        self.assertEqual(out.count("маркер-gate-and-transition"), 1,
                         "запись 'state -> spec_gate' напечатана не ровно один раз")

        self._set_state("T002", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)

    def test_ac3_alerts_class_matches_only_target_equal_to_selected_task_id(self):
        """`--events alerts` печатает только строки `alerts`, чей `target`
        буквально совпадает с id ВЫБРАННОЙ задачи; запись с `target` —
        именем проекта, `NULL`, либо id НЕвыбранной задачи — не печатается.

        Ловит мутацию: фильтр по `target` заменён фильтром по `kind` или
        снят вовсе — сообщения B/C/D (не адресованные выбранной задаче)
        окажутся в потоке, и `assertNotIn` на них покраснеет.
        """
        conn = store.db()
        self._insert_task("T003")
        self._insert_task("T004")

        self._start(["--tasks", "T003", "--events", "alerts", "--interval", "1"])
        self._settle()

        # Алерты заводятся ПОСЛЕ старта `watch` — «Не входит» SPEC.md прямо
        # исключает историческую выдачу; заведи их до `_start`, и тест
        # проверял бы не фильтр по `target` (предмет AC-3), а совсем другое
        # свойство — попадание в поток исторических записей, которое здесь
        # не предмет проверки.
        store.insert_alert(conn, "T003", "incident", "doctor",
                          "алерт-А-должен-появиться")
        store.insert_alert(conn, config.DEFAULT_TARGET, "incident", "doctor",
                          "алерт-Б-target-имя-проекта")
        store.insert_alert(conn, None, "threshold", "canary",
                          "алерт-В-target-null")
        store.insert_alert(conn, "T004", "incident", "doctor",
                          "алерт-Г-чужая-задача")

        self._wait_until(
            lambda: "алерт-А-должен-появиться" in self._stream.getvalue())

        out = self._stream.getvalue()
        self.assertNotIn("алерт-Б-target-имя-проекта", out)
        self.assertNotIn("алерт-В-target-null", out)
        self.assertNotIn("алерт-Г-чужая-задача", out)

        self._set_state("T003", "done", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class MineSelectorTest(_WatchTestCase):

    def test_ac4_mine_matches_latest_lease_session_or_created_fallback(self):
        """`--mine` берёт задачи по session_id ПОСЛЕДНЕЙ записи `actor=lease`
        («lease взят»/«lease перехвачен»); при отсутствии такой записи —
        по session_id записи `created`.

        Заводит 4 задачи: A — совпадающий lease, B — несовпадающий lease,
        C — без lease, совпадающий `created`, D — без lease, несовпадающий
        `created`. Только шаги A и C обязаны попасть в поток.

        Ловит мутацию: сравнение берёт ПЕРВУЮ запись lease вместо
        последней (перехват lease меняет владельца) — тогда задача A с
        начальным чужим lease и последующим «своим» перехватом ошибочно
        осталась бы вне выборки, шаг A не появился бы в потоке.
        """
        conn = store.db()
        caller = "sess-caller-mine"
        for task_id in ("A001", "B001", "C001", "D001"):
            self._insert_task(task_id)

        # A: чужой lease, затем перехват нашей сессией — берётся ПОСЛЕДНЯЯ запись.
        store.journal(conn, "A001", "lease", "lease взят", "",
                     session_id="sess-someone-else")
        store.journal(conn, "A001", "lease", "lease перехвачен", "причина",
                     session_id=caller)
        # B: lease чужой сессии, без перехвата.
        store.journal(conn, "B001", "lease", "lease взят", "",
                     session_id="sess-other")
        # C: lease никогда не брался — фолбэк на "created".
        store.journal(conn, "C001", "operator", "created", "",
                     session_id=caller)
        # D: тот же фолбэк, но чужая сессия.
        store.journal(conn, "D001", "operator", "created", "",
                     session_id="sess-other")

        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": caller}):
            self.assertEqual(session.resolve_session_id(None), caller)
            self._start(["--mine", "--interval", "1"])
            self._settle()

            store.journal(conn, "A001", "runner", "agent run started",
                         "маркер-A-моя")
            store.journal(conn, "B001", "runner", "agent run started",
                         "маркер-B-чужая")
            store.journal(conn, "C001", "runner", "agent run started",
                         "маркер-C-моя-фолбэк")
            store.journal(conn, "D001", "runner", "agent run started",
                         "маркер-D-чужая-фолбэк")

            self._wait_until(
                lambda: "маркер-A-моя" in self._stream.getvalue()
                and "маркер-C-моя-фолбэк" in self._stream.getvalue())

            out = self._stream.getvalue()
            self.assertNotIn("маркер-B-чужая", out)
            self.assertNotIn("маркер-D-чужая-фолбэк", out)

            self._set_state("A001", "done", "in_dev")
            self._set_state("C001", "done", "in_dev")
            self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class AllSelectorTest(_WatchTestCase):

    def test_ac5_all_excludes_terminal_tasks_from_the_initial_selection(self):
        """`--all` не включает в выборку задачу, уже находящуюся в
        `done`/`killed` на момент опроса — её события не должны попасть в
        поток, даже если только она и «мешала» бы `--until` (здесь
        `--all` обязан выбрать РОВНО одну задачу — вторая уже терминальна).

        Ловит мутацию: `--all` перестаёт исключать `done`/`killed`
        (например, фильтр `state NOT IN (...)` заменён на «все задачи») —
        тогда выборка включит обе задачи, `--until` откажет как «более
        одной задачи», и тест упадёт уже на этом расхождении (мы не
        получим SystemExit).
        """
        conn = store.db()
        self._insert_task("X001", state="in_dev")
        self._insert_task("Y001", state="done")

        self._start(["--all", "--until", "done", "--interval", "1"])
        self._settle()

        store.journal(conn, "X001", "runner", "agent run started",
                     "маркер-X-в-потоке")
        store.journal(conn, "Y001", "runner", "agent run started",
                     "маркер-Y-исключена")

        self._wait_until(
            lambda: "маркер-X-в-потоке" in self._stream.getvalue())
        self.assertNotIn("маркер-Y-исключена", self._stream.getvalue())

        self._set_state("X001", "done", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class UntilTerminationTest(_WatchTestCase):

    def test_ac6_until_requires_single_task_and_exhausts_without_until(self):
        """`--until` с более чем одной задачей в выборке — отказ
        использования ДО начала опроса; без `--until` цикл завершается,
        только когда ВСЕ выбранные задачи оказались в {done, killed}, не
        раньше.

        Ловит мутацию: проверка «ровно одна задача» для `--until` снята
        (тогда двухзадачный вызов не бросит `SystemExit` — тест упадёт на
        `assertRaises`); либо цикл завершается по ПЕРВОЙ, а не по ВСЕМ
        терминальным задачам (тогда поток завершится сразу после перевода
        только T005 в `done`, T006 ещё нет — `assertTrue(thread.is_alive())`
        после этого шага упадёт).
        """
        self._insert_task("T005")
        self._insert_task("T006")
        with self.assertRaises(SystemExit) as cm:
            watch.cmd_watch(["--tasks", "T005,T006", "--until", "done"])
        self.assertNotEqual(_exit_status(cm.exception.code), 0)

        self._start(["--tasks", "T005,T006", "--interval", "1"])
        time.sleep(0.3)
        self.assertTrue(self._thread.is_alive(),
                        "watch завершился раньше времени — задачи ещё не терминальны")

        self._set_state("T005", "done", "in_dev")
        time.sleep(0.3)
        self.assertTrue(
            self._thread.is_alive(),
            "watch завершился после ОДНОЙ терминальной задачи из двух выбранных")

        self._set_state("T006", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class StateChangeMarkerTest(_WatchTestCase):

    def test_ac7_state_change_prints_state_line_regardless_of_events_filter(self):
        """Смена `tasks.state` печатает отдельную строку `STATE=<state>`
        НЕЗАВИСИМО от выбранных `--events` — даже когда `transitions`/
        `gates` не входят в набор классов.

        Ловит мутацию: печать `STATE=` привязана к попаданию записи
        перехода под активные `--events` (то есть сведена к обычной
        `transitions`-строке) — при `--events refusals` строка `STATE=
        review` не появится вовсе, `assertIn` покраснеет.
        """
        self._insert_task("T007")

        self._start(["--tasks", "T007", "--events", "refusals", "--interval", "1"])
        self._settle()

        self._set_state("T007", "review", "in_dev")

        self._wait_until(
            lambda: any(ln.strip() == "STATE=review"
                       for ln in self._stream.getvalue().splitlines()))
        self.assertNotIn("state -> review", self._stream.getvalue())

        self._set_state("T007", "done", "review")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class NonMutatingReadTest(_WatchTestCase):

    def test_ac8_no_alerts_mutation_no_lease_no_extra_state_change(self):
        """За время работы `watch` не создаёт и не изменяет строки
        `alerts`, не заводит запись `leases`, не меняет `tasks.state` сам
        (единственная строка `state -> done` в журнале — та, что записал
        тест, не вторая от `watch`).

        Ловит мутацию: `watch` открывает lease на выбранной задаче, чтобы
        «застолбить» чтение (реалистичная, хоть и ошибочная, оптимизация)
        — `store.lease_row` перестанет быть `None` после прогона.
        """
        conn = store.db()
        self._insert_task("T008")
        store.insert_alert(conn, "T008", "incident", "doctor", "предсуществующий")
        alerts_before = conn.execute("SELECT COUNT(*) AS c FROM alerts").fetchone()["c"]

        self._start(["--tasks", "T008", "--interval", "1"])
        time.sleep(1.2)
        self._set_state("T008", "done", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)

        conn = store.db()
        alerts_after = conn.execute("SELECT COUNT(*) AS c FROM alerts").fetchone()["c"]
        self.assertEqual(alerts_before, alerts_after,
                         "число строк alerts изменилось за время работы watch")
        row = conn.execute(
            "SELECT ack_ts FROM alerts WHERE message='предсуществующий'").fetchone()
        self.assertIsNone(row["ack_ts"], "watch подтвердил чужой алерт")
        self.assertIsNone(store.lease_row(conn, "T008"), "watch взял lease")
        state_transitions = [r for r in store.task_steps(conn, "T008")
                            if r["action"] == "state -> done"]
        self.assertEqual(len(state_transitions), 1,
                         "watch записал лишний переход state -> done")


class EventFilterMutationTest(_WatchTestCase):

    def test_ac10_events_refusals_excludes_steps_class(self):
        """`--events refusals` печатает записи «переход отклонён…» и НЕ
        печатает `agent run started` — тест на мутацию фильтра из SPEC
        (AC-10): снятие фильтра красит тест зелёным сразу для ОБОИХ
        маркеров разом, что и делает его чувствительным именно к фильтру.

        Ловит мутацию: `--events` игнорируется реализацией (печатается
        всё подряд) — `agent-run-маркер` окажется в выводе, и
        `assertNotIn` покраснеет.
        """
        conn = store.db()
        self._insert_task("T009")

        self._start(["--tasks", "T009", "--events", "refusals", "--interval", "1"])
        self._settle()

        store.journal(conn, "T009", "fsm",
                     f"{store.REFUSAL_ACTION_PREFIX}: причина отказа",
                     "refusal-маркер")
        store.journal(conn, "T009", "runner", "agent run started",
                     "agent-run-маркер")

        self._wait_until(lambda: "refusal-маркер" in self._stream.getvalue())
        self.assertNotIn("agent-run-маркер", self._stream.getvalue())

        self._set_state("T009", "killed", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class DynamicAllSelectionTest(_WatchTestCase):

    def test_ac11_task_created_after_start_appears_without_restart(self):
        """Задача, заведённая ПОСЛЕ старта `watch --all`, появляется в
        потоке на следующей итерации без перезапуска команды.

        Ловит мутацию: выборка `--all`/`--mine` считается ОДИН РАЗ на
        старте и кэшируется (частая, но неверная оптимизация) — шаг новой
        задачи Z002, заведённой после старта, никогда не появится в
        выводе, и `_wait_until` упадёт таймаутом.
        """
        conn = store.db()
        self._insert_task("Z001", state="in_dev")

        self._start(["--all", "--interval", "1"])
        self._settle()

        self._insert_task("Z002", state="in_dev")
        # Пауза ДО записи шага: даёт `watch` хотя бы одну итерацию, чтобы
        # обнаружить Z002 динамическим пересчётом выборки и завести ей
        # собственный базовый снимок (0 известных шагов) — без паузы шаг
        # рискует лечь в БД РАНЬШЕ первого обнаружения Z002, и тогда он
        # будет учтён этим самым базовым снимком как «уже исторический»,
        # что проверяло бы не свойство AC-11, а гонку таймингов теста.
        time.sleep(1.5)
        store.journal(conn, "Z002", "runner", "agent run started",
                     "маркер-новая-задача-Z002")

        self._wait_until(
            lambda: "маркер-новая-задача-Z002" in self._stream.getvalue())

        self._set_state("Z001", "done", "in_dev")
        self._set_state("Z002", "done", "in_dev")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class UntilBlockingBehaviorTest(_WatchTestCase):

    def test_ac12_until_exits_zero_exactly_when_state_is_reached(self):
        """`watch --tasks <id> --until <state>` не завершается, пока
        состояние не достигнуто, и завершается кодом 0 сразу после того,
        как оно достигнуто — не раньше и не позже.

        Ловит мутацию: условие сравнивается «состояние НЕ РАВНО
        начальному» вместо «состояние РАВНО целевому» — тогда переход
        `in_dev -> review` (промежуточный, не целевой `done`) уже
        завершил бы цикл, и `assertTrue(thread.is_alive())` после него
        упадёт.
        """
        self._insert_task("T010", state="in_dev")

        self._start(["--tasks", "T010", "--until", "done", "--interval", "1"])
        time.sleep(0.3)
        self.assertTrue(self._thread.is_alive(), "завершился до старта опроса")

        self._set_state("T010", "review", "in_dev")
        time.sleep(0.5)
        self.assertTrue(self._thread.is_alive(),
                        "завершился на промежуточном состоянии, не на целевом")

        self._set_state("T010", "done", "review")
        self._join()
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)


class NoJournalOrLeaseFootprintTest(_WatchTestCase):

    def test_ac13_steps_and_leases_row_counts_unchanged_by_a_watch_run(self):
        """Число строк `steps` и `leases` до и после прогона `watch`
        совпадает — команда сама не журналирует ничего.

        Задача выбрана уже терминальной (`done`) — `watch` обязан
        завершиться немедленно первой же проверкой, не сделав ни одной
        записи от своего имени.

        Ловит мутацию: `watch` пишет запись «watch старт» в `steps` при
        запуске — счётчик строк `steps` после прогона окажется на 1
        больше, `assertEqual` покраснеет.
        """
        conn = store.db()
        self._insert_task("T011", state="done")
        steps_before = conn.execute("SELECT COUNT(*) AS c FROM steps").fetchone()["c"]
        leases_before = conn.execute("SELECT COUNT(*) AS c FROM leases").fetchone()["c"]

        self._start(["--tasks", "T011", "--interval", "1"])
        self._join(timeout=5.0)
        self.assertEqual(self._watch_outcome.get("exit_code"), 0)

        conn = store.db()
        steps_after = conn.execute("SELECT COUNT(*) AS c FROM steps").fetchone()["c"]
        leases_after = conn.execute("SELECT COUNT(*) AS c FROM leases").fetchone()["c"]
        self.assertEqual(steps_before, steps_after)
        self.assertEqual(leases_before, leases_after)


class OperatorSessionDocTest(unittest.TestCase):

    def test_ac9_operator_session_doc_recommends_watch_mine(self):
        """`docs/operator-session.md`, «Возобновление сессии», п. 4
        «Поставить дозор» — переписан на `artel.py watch --mine` как
        актуальный способ; прежние сценарии сессии как актуальный способ
        не упоминаются.

        Ловит мутацию: правка коснулась другого раздела/пункта, а п. 4
        остался прежним текстом («фоновый наблюдатель» без команды) —
        `assertIn("artel.py watch --mine", ...)` покраснеет.
        """
        text = (REPO_ROOT / "docs" / "operator-session.md").read_text(
            encoding="utf-8")
        self.assertIn("## Возобновление сессии", text)
        section = text.split("## Возобновление сессии", 1)[1]
        section = section.split("\n## ", 1)[0]
        self.assertIn("artel.py watch --mine", section,
                     "п.4 «Поставить дозор» не называет команду watch --mine")
        self.assertNotIn("watch_tasks.py", section,
                        "прежний сценарий всё ещё упомянут как актуальный способ")
        self.assertNotIn("watch_spec_gate.py", section,
                        "прежний сценарий всё ещё упомянут как актуальный способ")


# AC-14: skip — «существующие тесты CLI (tests/test_cli*.py, tests/
# test_artel*.py, если есть) и tests/test_store*.py остаются зелёными без
# правки ассертов» проверяется штатным прогоном УЖЕ СУЩЕСТВУЮЩЕГО набора
# (его гоняет CI, скил test-authoring прямо запрещает гонять полный
# tests/ из шага этой роли) — детерминированный тест здесь дал бы не
# новое свойство, а копию чужого прогона поверх кода, которого эта роль
# не пишет и не видит целиком; критерий — регрессионная гарантия для
# ревью/CI, не для новой планки приёмки.
