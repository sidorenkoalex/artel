"""Раздел отчёта `report` о расходе шагов test_author за окно `OPERATOR_WINDOW_DAYS`: стоимость, токены, вызовы инструментов по видам, прогоны pytest и их время, вызовы Write, файлы и строки отдельно для `tests/` и `acceptance_tests/`, «н/д» для обрезанного пути, пропавшего файла и провайдера не Claude; ни одного вызова git (AC-12).

Группа: долгоживущий

Красен до реализации: в отчёте нет раздела о шагах test_author — заголовка со словами «test_author» (или «автор тестов») нет, проверка находит пустой раздел.

Песочница — `tests.sandbox.SchemaTmpRootTest` (пути `config` во временном
каталоге, схема БД), отчёт — публичный `report.cmd_report`, его файл
`.artel/report.html` читается целиком. Журнал шагов пишется
`store.journal` в той форме, в какой его пишет пульт: «agent run started»
(`лог: <путь>`), «agent cost KNOWN» (`model=`, `provider=`, токены по
видам), «прогон pytest» (итоговая строка pytest «N passed in X.XXs»),
«agent run finished» (`стоимость $X, токенов N`). Лог шага —
`config.LOGS/<задача>-test_author-<N>.log` в форме рендера провайдера:
строка вызова инструмента `· <Инструмент> <аргумент>`, аргумент обрезан до
100 символов. Файлы, которые пишет Write, лежат в коротком временном
каталоге, чтобы их путь в строке лога не обрезался.

Раздел отчёта — от заголовка (`<h1>`…`<h6>`), в тексте которого есть
«test_author» либо «автор… тест…», до следующего заголовка того же или
более высокого уровня. Числа проверяются как отдельно стоящие числа текста
раздела (без тегов); все числа фикстуры попарно различны, поэтому каждое
число указывает на свою величину. Все числа и пути — из `random`; зерно
печатается и входит в текст каждого провала.

Валидация стабом: временный стаб раздела (заголовок «Шаги test_author»,
строка на шаг: стоимость, токены, вызовы по видам, прогоны pytest, Write/
файлы/строки по группам, «н/д» по обрезке, пропавшему файлу и провайдеру)
— все три теста зелёные; мутация стаба «`tests/` по подстроке „tests/“»
краснит первый тест на числах Write, файлов и строк. Стаб удалён.
"""
import html
import random
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import agent_log, config, report, spend, store
from tests.sandbox import SchemaTmpRootTest

TOOL_ARGUMENT_LIMIT = 100
HEADING = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.S | re.I)
TITLE = re.compile(r"test_author|автор\w*\s+тест", re.I)


def word(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                   for _ in range(length))


def text_of(chunk: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", chunk)).split())


def author_section(page: str) -> str:
    """Текст раздела test_author (см. докстринг модуля); пусто — нет."""
    headings = list(HEADING.finditer(page))
    for index, match in enumerate(headings):
        if not TITLE.search(text_of(match.group(2))):
            continue
        level = int(match.group(1))
        end = len(page)
        for later in headings[index + 1:]:
            if int(later.group(1)) <= level:
                end = later.start()
                break
        return text_of(page[match.start():end])
    return ""


def standalone(section: str, value) -> bool:
    return re.search(rf"(?<![\d.,]){re.escape(str(value))}(?!\d)",
                     section) is not None


def tool_line(name: str, arg: str) -> str:
    return f"· {name} {arg[:TOOL_ARGUMENT_LIMIT]}\n"


class AuthorReportSandbox(SchemaTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        base = "/tmp" if Path("/tmp").is_dir() else None
        self.short = Path(tempfile.mkdtemp(prefix="a", dir=base)).resolve()
        self.addCleanup(shutil.rmtree, self.short, ignore_errors=True)

    def note(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def numbers(self) -> dict:
        """Попарно различные числа фикстуры."""
        while True:
            r, b, e = self.rng.sample(range(11, 20), 3)
            wt, wa = self.rng.sample((21, 23, 25, 27, 29), 2)
            ft, fa = self.rng.sample(range(2, 6), 2)
            p = self.rng.randrange(6, 10)
            durations = [self.rng.randrange(50, 80) for _ in range(p)]
            lines_t = [self.rng.randrange(20, 50) for _ in range(ft)]
            lines_a = [self.rng.randrange(20, 50) for _ in range(fa)]
            tokens_in = self.rng.randrange(300, 500)
            tokens_out = self.rng.randrange(500, 600)
            values = {"r": r, "b": b, "e": e, "wt": wt, "wa": wa,
                      "w": wt + wa, "ft": ft, "fa": fa, "p": p,
                      "s": sum(durations), "lt": sum(lines_t),
                      "la": sum(lines_a), "n": tokens_in + tokens_out,
                      "wt1": wt + 1, "wa1": wa + 1,
                      "tokens_in": tokens_in, "tokens_out": tokens_out}
            if len(set(values.values())) == len(values) and \
                    not set(durations) & set(values.values()):
                values.update(durations=durations, lines_t=lines_t,
                              lines_a=lines_a,
                              cost=round(self.rng.uniform(1.01, 4.99), 2))
                return values

    def files(self, folder: str, counts: list) -> list:
        """Файлы с заданным числом строк под `self.short/<folder>`."""
        paths = []
        for count in counts:
            path = self.short / folder / f"test_{word(self.rng, 4)}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(f"x_{i} = {i}\n" for i in range(count)),
                            encoding="utf-8")
            self.assertLess(len(str(path)), TOOL_ARGUMENT_LIMIT, self.note(
                f"путь фикстуры длиннее предела обрезки: {path}"))
            paths.append(str(path))
        return paths

    def writes(self, paths: list, total: int) -> list:
        """`total` строк Write по `paths`, каждый путь хотя бы раз."""
        chosen = list(paths) + [self.rng.choice(paths)
                                for _ in range(total - len(paths))]
        return [tool_line("Write", p) for p in chosen]

    def seed_step(self, task: str, v: dict, provider: str = "claude",
                  extra_lines: tuple = ()) -> None:
        """Задача и шаг test_author: журнал и лог шага."""
        conn = store.db()
        store.insert_task(conn, task, f"Задача {task}", "in_dev",
                          f"task/{task.lower()}", config.DEFAULT_TARGET, 25.0)
        tests_paths = self.files("tests", v["lines_t"])
        plank_paths = self.files("plank/acceptance_tests", v["lines_a"])
        lines = (["Начинаю шаг.\n"]
                 + [tool_line("Read", f"/x/{word(self.rng)}.md") for _ in range(v["r"])]
                 + [tool_line("Bash", "python3 -m pytest -q") for _ in range(v["b"])]
                 + [tool_line("Edit", f"/x/{word(self.rng)}.py") for _ in range(v["e"])]
                 + self.writes(tests_paths, v["wt"])
                 + self.writes(plank_paths, v["wa"])
                 + list(extra_lines))
        self.rng.shuffle(lines)
        config.LOGS.mkdir(parents=True, exist_ok=True)
        log = config.LOGS / f"{task}-test_author-1.log"
        log.write_text("".join(lines), encoding="utf-8")
        attempt = f"попытка 1/{config.AGENT_ATTEMPTS}"
        store.journal(conn, task, "test_author", "agent run started",
                      f"{attempt}, model=fx-model, роль test_author, источник "
                      f"модели: фикстура, лог: {log}, промпт: {log}.prompt, "
                      f"окружение: фикстура")
        for duration in v["durations"]:
            store.journal(conn, task, "test_author", agent_log.PYTEST_RUN_ACTION,
                          f"{self.rng.randrange(1, 9)} passed in {duration}.00s")
        store.journal(conn, task, "test_author", spend.KNOWN_COST_JOURNAL_ACTION,
                      f"{attempt}, model=fx-model, provider={provider}: "
                      f"input={v['tokens_in']}, output={v['tokens_out']}, "
                      f"cache_write=0, cache_read=0, actual_usd={v['cost']}")
        store.journal(conn, task, "test_author", "agent run finished",
                      f"rc=0, {attempt}, стоимость ${v['cost']:.4f}, "
                      f"токенов {v['n']}, окружение: фикстура")

    def section(self) -> str:
        self.capture(report.cmd_report)
        page = (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")
        return author_section(page)


class AuthorReportTest(AuthorReportSandbox):

    def test_ac12_author_section_counts_cost_tools_pytest_and_writes(self):
        """Раздел test_author: стоимость, токены, вызовы по видам, прогоны pytest и их время, Write/файлы/строки отдельно для `tests/` и `acceptance_tests/`; шаг вне окна не учтён; git не вызывается.

        Сценарий: шаг test_author в окне — лог с вызовами Read/Bash/Edit и
        Write по файлам `…/tests/` и `…/acceptance_tests/` (часть путей
        повторяется), прогоны pytest в журнале, стоимость и токены. Шаг
        test_author другой задачи старше окна `OPERATOR_WINDOW_DAYS` — со
        своей стоимостью. В разделе есть: стоимость и токены шага, число
        вызовов каждого вида (и имя вида), число прогонов pytest и их
        суммарное время, число Write, число различных файлов и сумма их
        строк по `tests/` и по `acceptance_tests/`; стоимости шага вне окна
        нет. Ни одного запуска git — ни через `subprocess.Popen`, ни через
        `gitcmd`.

        Ловит мутацию: строка `…/acceptance_tests/…` отнесена к `tests/` по
        подстроке «tests/» — числа Write по `tests/` и `acceptance_tests/`
        не те; файлы считаются по строкам Write, а не по различным путям;
        строки файла не читаются с диска; время прогонов не суммируется;
        окно не применяется — стоимость старого шага в разделе; число
        строк считается через `git show`/`git log` — есть запуск git.
        """
        v = self.numbers()
        task = f"T{self.rng.randrange(10 ** 5, 10 ** 6)}"
        self.seed_step(task, v)
        old_task = f"T{self.rng.randrange(10 ** 6, 10 ** 7)}"
        old = self.numbers()
        old["cost"] = round(v["cost"] + 5.0 + self.rng.randrange(1, 90) / 100, 2)
        self.seed_step(old_task, old)
        stale = (datetime.now(timezone.utc)
                 - timedelta(days=report.OPERATOR_WINDOW_DAYS + 5)).isoformat()
        conn = store.db()
        conn.execute("UPDATE steps SET ts=? WHERE task_id=?", (stale, old_task))
        conn.commit()

        launched = []
        real = subprocess.Popen

        def spy(args, *rest, **kwargs):
            launched.append([str(a) for a in args] if isinstance(args, (list, tuple))
                            else [str(args)])
            return real(args, *rest, **kwargs)

        git_before = len(self.git_spy.calls)
        with mock.patch.object(subprocess, "Popen", spy):
            section = self.section()
        context = self.note(f"числа: {v}\nраздел:\n{section}")
        self.assertTrue(section, context)
        self.assertIn(f"{v['cost']:.2f}", section, context)
        self.assertNotIn(f"{old['cost']:.2f}", section, context)
        for kind in ("Read", "Bash", "Edit", "Write"):
            self.assertIn(kind, section, context)
        for key in ("n", "r", "b", "e", "w", "p", "s", "wt", "wa", "ft", "fa",
                    "lt", "la"):
            with self.subTest(key=key):
                self.assertTrue(standalone(section, v[key]),
                                self.note(f"нет числа {key}={v[key]}\n{context}"))
        gits = [argv for argv in launched
                if argv and argv[0].rsplit("/", 1)[-1] == "git"]
        self.assertEqual(gits, [], context)
        self.assertEqual(self.git_spy.calls[git_before:], [], context)

    def test_ac12_truncated_or_missing_path_counts_write_and_reports_na(self):
        """Строка Write с путём, обрезанным на 100 символах до `…/acceptance`, и строка с путём пропавшего файла: вызов Write засчитан, файлы и строки — «н/д».

        Сценарий: к логу шага добавлены `· Write <путь>`, чей видимый
        аргумент — ровно 100 символов и кончается на `/acceptance`, и
        `· Write <…/tests/test_<x>.py>`, которого нет на диске. В разделе:
        число Write по `acceptance_tests/` на единицу больше числа строк с
        полным путём, по `tests/` — тоже на единицу больше; «н/д» есть.

        Ловит мутацию: обрезанная строка без полного сегмента
        `acceptance_tests/` не засчитана в Write `acceptance_tests/`;
        пропавший файл считается файлом в 0 строк (или строка с ним
        отброшена) — «н/д» нет, Write по `tests/` не те.
        """
        v = self.numbers()
        prefix = str(self.short / "d")
        filler = TOOL_ARGUMENT_LIMIT - len(prefix) - len("/acceptance")
        self.assertGreater(filler, 0, self.note(f"короткий каталог длинен: {prefix}"))
        visible = prefix + "d" * filler + "/acceptance"
        self.assertEqual(len(visible), TOOL_ARGUMENT_LIMIT, self.note(visible))
        missing = str(self.short / "tests" / f"test_gone_{word(self.rng)}.py")
        extra = (tool_line("Write", visible + f"_tests/test_{word(self.rng)}.py"),
                 tool_line("Write", missing))
        self.seed_step(f"T{self.rng.randrange(10 ** 5, 10 ** 6)}", v,
                       extra_lines=extra)
        section = self.section()
        context = self.note(f"числа: {v}\nраздел:\n{section}")
        self.assertTrue(section, context)
        self.assertIn("н/д", section, context)
        self.assertTrue(standalone(section, v["wa1"]), context)
        self.assertTrue(standalone(section, v["wt1"]), context)

    def test_ac12_non_claude_provider_writes_are_na(self):
        """Шаг test_author с провайдером не Claude: число Write, файлов и строк — «н/д», не числа из лога.

        Сценарий: шаг, записанный с `provider=codex`, с тем же видом лога,
        что у шага Claude (Write по существующим файлам `tests/` и
        `acceptance_tests/`). В разделе есть «н/д», а сумм строк файлов
        `tests/` и `acceptance_tests/` нет.

        Ловит мутацию: провайдер шага не учитывается — строки лога
        разбираются как у Claude, в разделе появляются суммы строк файлов
        вместо «н/д».
        """
        v = self.numbers()
        self.seed_step(f"T{self.rng.randrange(10 ** 5, 10 ** 6)}", v,
                       provider="codex")
        section = self.section()
        context = self.note(f"числа: {v}\nраздел:\n{section}")
        self.assertTrue(section, context)
        self.assertIn("н/д", section, context)
        self.assertFalse(standalone(section, v["lt"]), context)
        self.assertFalse(standalone(section, v["la"]), context)
