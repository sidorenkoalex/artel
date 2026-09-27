"""Стенд планки 01M3HST4SGX0SPKAGNHVY7DWHM — общий для файлов
`test_ac*.py`: bare `origin` с трёхраздельным `docs/backlog.md`,
документом `docs/**` и файлом конфигурации Оператора, синхронный с
главной копией.

Тонкая надстройка над `tests/sandbox.py::RealGitSandbox` (импорт, не
копия — skills/test-authoring.md запрещает переписывать песочницу пульта
заново): здесь только фикстура документа, вызовы команд и опросы origin/
журнала, которых у общей песочницы нет.

Настоящий git и настоящий прогон `pytest` — сознательно, без моков
`gitcmd`/`acceptance`: предмет критериев AC-8..AC-15 — что именно
приезжает в `origin` и чем кончается прогон набора на дереве с
применённой правкой; планка не вправе фиксировать, какой функцией пульта
разработчик это сделает.
"""
import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, notes, store  # noqa: E402
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

# Документ `docs/**` и файл конфигурации Оператора — адресами из кода, не
# литералами: список допустимых путей `doc-commit` — крутилка Оператора
# (`notes.DOC_COMMIT_CONFIG_PATHS`), и планка не должна краснеть от её
# поворота.
DOC_REL = "docs/roadmap.md"
CONFIG_REL = notes.DOC_COMMIT_CONFIG_PATHS[0]

ROADMAP_TEXT = "# Роадмап\n\nСтарый раздел.\n"
CONFIG_TEXT = "# конфигурация Оператора\nкрутилка: один\n"

# Маркер правки конфигурации, от которого краснеет посеянный набор
# `CONDITIONAL_SUITE` ниже.
POISON = "ЯДОВИТАЯПРАВКА"
CONFIG_TEXT_POISONED = f"# конфигурация Оператора\nкрутилка: {POISON}\n"

# Шапки разделов — как на вершине origin/main (SPEC, «Материалы»):
# «Копилка» пятиколоночная, «Бэклог» шестиколоночная, «Очередь
# Оператора» трёхколоночная.
KOPILKA_HEADER = "| П | Дата | Наблюдение | Где | Состояние |"
KOPILKA_HEADER_WIDE = "| П | Дата | Наблюдение | Где | Состояние | Лишняя |"
KOPILKA_COLUMNS = len(KOPILKA_HEADER.strip("|").split("|"))

# Ячейка «Наблюдение» первой снимаемой строки длиннее 80 знаков: маркер
# ХВОСТОДИН стоит ЗА границей усечения записи журнала (требование 12 —
# каждая строка усечена до 80 знаков), СНЯТАЯОДИН — до неё, в обоих
# возможных видах строки (с обрамляющими чертами и без них).
DROPPED_LONG_CELL = "СНЯТАЯОДИН " + "х" * 70 + " ХВОСТОДИН"

SECTION_KOPILKA = f"""## Копилка

{KOPILKA_HEADER}
|---|---|---|---|---|
| 1 | 01.01 | СОСТОЯНИЕЕСТЬ наблюдение | orchestrator/x.py | прежнее состояние |
| 2 | 01.01 | СОСТОЯНИЕПУСТО наблюдение | orchestrator/y.py |  |
| 3 | 01.01 | СОСТОЯНИЕПРОЧЕРК наблюдение | orchestrator/z.py | — |
| 4 | 01.01 | ПРИОРИТЕТКЛЮЧ наблюдение | orchestrator/p.py | состояние |
| 4 | 01.01 | ПРИОРИТЕТВТОРОЙ наблюдение | orchestrator/q.py | состояние |
| 3 | 07.07 | {DROPPED_LONG_CELL} | orchestrator/d1.py | состояние |
| 4 | 07.07 | СНЯТАЯДВА наблюдение | orchestrator/d2.py | состояние |

"""

SECTION_BACKLOG = """## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта |
|---|---|---|---|---|---|
| 1 | Кандидат А | Суть А | $10 | orchestrator/a.py | сразу |

"""

SECTION_QUEUE = """## Очередь Оператора

| П | Действие | Условие |
|---|---|---|
| 1 | Действие А | сразу |
"""

BACKLOG_TITLE = "# Бэклог пульта\n\n"

BACKLOG_TEXT = BACKLOG_TITLE + SECTION_KOPILKA + SECTION_BACKLOG + SECTION_QUEUE

# Посеянный в дерево прогона набор `tests/`: красен РОВНО тогда, когда
# правка конфигурации уже применена к дереву (требование 13 — прогон идёт
# «на дереве с УЖЕ применённой правкой»). Путь читается от собственного
# файла, а не от cwd: `pytest` пульта зовётся с cwd рабочего репозитория,
# и якорь на cwd прошёл бы и при прогоне не на том дереве.
CONDITIONAL_SUITE = f'''"""Посеянный набор стенда планки: красен ровно
тогда, когда правка конфигурации применена к дереву прогона."""
from pathlib import Path

TREE_ROOT = Path(__file__).resolve().parents[1]


def test_seed_config_has_no_poison():
    text = (TREE_ROOT / "{CONFIG_REL}").read_text(encoding="utf-8")
    assert "{POISON}" not in text, "правка применена — набор красный"
'''

# Посеянный набор, красный при любом содержимом дерева — им проверяется,
# что путь `docs/**` прогона не заводит вовсе (требование 16).
FAILING_SUITE = '''"""Посеянный набор стенда планки: красен всегда."""


def test_seed_always_red():
    assert False, "набор красный намеренно"
'''

SEEDED_SUITE_REL = "tests/test_seed.py"


def cells(line: str) -> list:
    """Ячейки строки таблицы — собственным разбором планки, не
    `notes._row_cells`: проверять нормализацию инструментом самой
    реализации значило бы не проверять её вовсе."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def today_stamps() -> set:
    """Текущая дата пульта в форме «ДД.ММ» — местная И UTC: требование 7
    часовой пояс не фиксирует, а прогон около полуночи не должен красить
    залоченную планку."""
    return {date.today().strftime("%d.%m"),
            datetime.now(timezone.utc).strftime("%d.%m")}


def draft_with_extra_row() -> str:
    """Корректная заготовка: те же три раздела и те же шапки, в «Копилке»
    на одну строку больше."""
    extra = ("| 1 | 27.09 | ЗАГОТОВКАПРИМЕНЕНА наблюдение | "
             "orchestrator/n.py | новое |")
    lines = BACKLOG_TEXT.split("\n")
    lines.insert(lines.index(KOPILKA_HEADER) + 2, extra)
    return "\n".join(lines)


def draft_without_dropped_rows() -> str:
    """Корректная заготовка, потерявшая обе строки-маркера СНЯТАЯ* —
    предмет перечня удалённых строк в журнале (требование 12)."""
    return "\n".join(line for line in BACKLOG_TEXT.split("\n")
                     if "СНЯТАЯ" not in line)


def draft_without_backlog_section() -> str:
    """Заготовка без раздела «Бэклог» целиком (заголовок и таблица)."""
    return BACKLOG_TITLE + SECTION_KOPILKA + SECTION_QUEUE


def draft_with_widened_kopilka_header() -> str:
    """Заготовка, у которой шапка «Копилки» несёт лишнюю колонку — число
    колонок разошлось с текущим origin."""
    return BACKLOG_TEXT.replace(KOPILKA_HEADER, KOPILKA_HEADER_WIDE)


class NoteSandbox(RealGitSandbox):
    """Главная копия с `docs/backlog.md` (три раздела), `docs/roadmap.md`
    и файлом конфигурации Оператора, синхронная с bare `origin`: сверка
    базы проходит, окно тишины закрыто (БД пуста, ни держателя
    merge-мьютекса, ни задач), `tests/` в дереве НЕТ — его сеет сам тест
    (`seed_suite`)."""

    def setUp(self):
        super().setUp()
        self.origin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", self.origin)
        self.git("remote", "add", "origin", self.origin)
        for rel, text in ((notes.BACKLOG_REL, BACKLOG_TEXT),
                          (DOC_REL, ROADMAP_TEXT),
                          (CONFIG_REL, CONFIG_TEXT)):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "документы")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.source_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.source_dir, ignore_errors=True)

    # --- файлы-источники -------------------------------------------------

    def source_file(self, text: str, name: str = "draft.md") -> Path:
        path = Path(self.source_dir) / name
        path.write_text(text, encoding="utf-8")
        return path

    # --- вызовы команд ---------------------------------------------------

    def note(self, *argv: str) -> str:
        return capture(notes.cmd_note, list(argv))

    def doc_commit(self, *argv: str) -> str:
        return capture(notes.cmd_doc_commit, list(argv))

    def apply_draft(self, text: str, message: str) -> str:
        return self.note("--apply",
                         str(self.source_file(text, "draft-backlog.md")),
                         "--message", message)

    def refusal(self, fn, *argv: str) -> str:
        """Текст отказа команды (`SystemExit`). Вывод в stdout подавлен —
        отказ может печатать по дороге, и это не предмет проверки."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit) as ctx:
            fn(list(argv))
        return str(ctx.exception)

    def assert_named_refusal(self, message: str, *keywords: str) -> None:
        """Отказ именованный: текст непустой, это не код выхода argparse
        («2» — команда даже не разобрала аргументы, а не отказала по
        существу) и несёт хотя бы одно слово из тех, которыми критерий
        называет причину. Точную формулировку планка не фиксирует —
        выбирает её разработчик."""
        self.assertTrue(message.strip(), "отказ без текста")
        self.assertNotEqual(
            message.strip(), "2",
            f"argparse не разобрал аргументы вместо отказа по существу: "
            f"{message}")
        lowered = message.lower()
        self.assertTrue(
            any(word.lower() in lowered for word in keywords),
            f"текст отказа не называет причину (ни одного из {keywords}): "
            f"{message}")

    # --- опрос origin ----------------------------------------------------

    def origin_run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", self.origin, *args],
                              capture_output=True, text=True)

    def origin_head(self) -> str:
        res = self.origin_run("rev-parse", config.MAIN_BRANCH)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_commit_count(self) -> int:
        res = self.origin_run("rev-list", "--count", config.MAIN_BRANCH)
        return int(res.stdout.strip()) if res.returncode == 0 else -1

    def origin_show(self, rel: str) -> str:
        res = self.origin_run("show", f"{config.MAIN_BRANCH}:{rel}")
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout

    def origin_message(self) -> str:
        res = self.origin_run("log", "-1", "--format=%B", config.MAIN_BRANCH)
        return res.stdout

    def origin_backlog(self) -> str:
        return self.origin_show(notes.BACKLOG_REL)

    def backlog_rows(self, key: str) -> list:
        return [line for line in self.origin_backlog().split("\n")
                if key in line]

    def backlog_row(self, key: str) -> str:
        rows = self.backlog_rows(key)
        self.assertEqual(len(rows), 1, f"по ключу «{key}»: {rows}")
        return rows[0]

    def main_copy_snapshot(self) -> tuple:
        return (self.git("rev-parse", "HEAD").strip(),
                self.git("rev-parse", "--abbrev-ref", "HEAD").strip(),
                self.git("status", "--porcelain"))

    def push_foreign_backlog_change(self, text: str) -> None:
        """Чужая правка `docs/backlog.md`, уехавшая в origin ПОЗЖЕ базы
        главной копии (тот же приём, что `tests/test_doc_commit.py::
        PinBaseCheckTest._push_foreign_change_past_the_pin`)."""
        (self.root / notes.BACKLOG_REL).write_text(text, encoding="utf-8")
        self.git("commit", "-a", "-q", "-m", "чужая правка бэклога")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("reset", "-q", "--hard", "HEAD~1")

    # --- журнал и окно тишины --------------------------------------------

    def journal_text(self) -> str:
        rows = store.db().execute(
            "SELECT actor, action, detail FROM steps ORDER BY id").fetchall()
        return "\n".join(" ".join(str(col) for col in row) for row in rows)

    def open_silence_window(self, task_id: str = "T-WIN") -> None:
        store.insert_task(store.db(), task_id, "окно тишины",
                          config.NOTE_SILENCE_WINDOW_STATES[0],
                          f"task/{task_id}", config.DEFAULT_TARGET, 10.0)

    # --- посев набора tests/ в дерево прогона ----------------------------

    def seed_suite(self, body: str) -> None:
        """Набор `tests/` в главной копии и в origin — дерево рабочего
        репозитория `note`/`doc-commit` чекаутится из origin, и прогон
        полного набора видит именно этот файл."""
        path = self.root / SEEDED_SUITE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "набор tests/")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
