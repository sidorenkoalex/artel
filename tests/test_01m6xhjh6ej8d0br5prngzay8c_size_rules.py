"""Правила метки размера (ADR-0032 п. 2): `test_lint.size_findings`, `test_lint.heavy_sandbox_names`, подполе профиля `size_marks` и подключение в `guard.long_lived_errors_from_files`.

Группа: долгоживущий
Красен до реализации: в `orchestrator/test_lint.py` нет `size_findings` и `heavy_sandbox_names`, у `guard.long_lived_errors_from_files` нет параметров `size_marks`/`sandbox_sources`, а `test_profile.size_marks` разбор профиля отвергает как «неизвестное подполе» — каждый тест падает на `AttributeError`/`TypeError` либо на тексте отказа.

Провалидировано временным стабом реализации (удалён, не закоммичен): все
методы файла зелёные; снятие разбора `AnnAssign` в стабе краснит случай
присваивания с аннотацией AC-5.

Все входы — исходники строками в памяти и запись проекта словарём
(`targets.check` в песочнице `tmp_root`, `config.TARGETS` во временном
каталоге): ни настоящего git, ни БД пульта, ни процессов. Имена классов
песочниц, тестов и файлов в части случаев — от `random`; зерно печатается и
входит в текст провала.
"""
import random
import re

import pytest

from orchestrator import targets, test_lint
from scripts import guard

pytestmark = pytest.mark.size("small")

HEAVY = ("RealGitSandbox", "InitializedTmpRootTest", "SchemaTmpRootTest",
         "SchemaSeededTmpRootTest", "TaskIdSchemaConnTmpRootTest",
         "TaskSeededTmpRootTest", "BudgetSeededTmpRootTest",
         "OriginRealGitSandbox", "SchemaConnTmpRootTest", "ConnRealGitSandbox",
         "SyncedOriginConnSandbox", "AutoOriginSandbox",
         "GitignoreCommittedRealGitSandbox", "ReportSandbox",
         "OutcomeGateSandbox")
LABEL = "tests/test_sample_size.py"
NO_MARK = "нет метки размера"
SEVERAL = "несколько меток размера"
SIZE_PREFIX = "размер —"
LETTERS = "abcdefghijklmnopqrstuvwxyz"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
MARKER = "# здесь"


def rng_and_seed():
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    return random.Random(seed), seed


def word(rng, size=7) -> str:
    return "".join(rng.choice(LETTERS) for _ in range(size))


def camel(rng) -> str:
    return word(rng, 6).capitalize() + word(rng, 5).capitalize()


def marked_line(source: str) -> int:
    """Номер строки с меткой `# здесь` в исходнике случая."""
    for number, line in enumerate(source.splitlines(), 1):
        if MARKER in line:
            return number
    raise LookupError("в исходнике случая нет строки с меткой")


def with_size(source: str, size: str) -> str:
    return source.replace("SIZE", size)


# --------------------------------------------------------------- AC-1

def test_ac1_missing_mark_reported_at_line_one():
    """Исходник без `pytestmark` с меткой размера — нарушение «нет метки размера» в строке 1.

    Сценарий: модуль с импортами и несколькими тестами со случайными
    именами, без какой-либо метки уровня модуля; ещё один — с меткой
    `pytestmark = pytest.mark.slow` (не размер). `size_findings` отдаёт
    пару (1, текст с «нет метки размера») для обоих.

    Ловит мутацию: отсутствие метки не проверяется (пустой список у
    файла без метки) либо нарушение ставится на строку первого теста, а
    не на строку 1; любая метка `pytestmark` принимается за метку размера.
    """
    rng, seed = rng_and_seed()
    for head in ("", "pytestmark = pytest.mark.slow\n\n"):
        names = [word(rng) for _ in range(rng.randint(1, 4))]
        body = "".join(f"\n\ndef test_{n}():\n    assert len('{n}') == {len(n)}\n"
                       for n in names)
        source = '"""Образец."""\nimport pytest\n\n' + head + body
        found = test_lint.size_findings(source, LABEL, frozenset(HEAVY))
        assert any(line == 1 and NO_MARK in text for line, text in found), (
            f"зерно: {seed}; нет пары (1, «{NO_MARK}»): {found}\n{source}")


# --------------------------------------------------------------- AC-2

SMALL_HEAVY_CASES = [
    (f"класс наследует {name}",
     f"import pytest\nfrom tests.sandbox import {name}\n\n"
     f"pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     f"class CaseTest({name}):  {MARKER}\n\n"
     f"    def test_case(self):\n        assert self is not None\n",
     name)
    for name in HEAVY
]

SMALL_OTHER_CASES = [
    ("локальный подкласс песочницы",
     "import pytest\nfrom tests.sandbox import RealGitSandbox\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     "class LocalBox(RealGitSandbox):\n    pass\n\n\n"
     f"class CaseTest(LocalBox):  {MARKER}\n\n"
     "    def test_case(self):\n        assert self is not None\n",
     ""),
    ("два уровня локальных подклассов",
     "import pytest\nfrom tests.sandbox import RealGitSandbox\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     "class LowerBox(RealGitSandbox):\n    pass\n\n\n"
     "class UpperBox(LowerBox):\n    pass\n\n\n"
     f"class CaseTest(UpperBox):  {MARKER}\n\n"
     "    def test_case(self):\n        assert self is not None\n",
     ""),
    ("импорт с псевдонимом as R",
     "import pytest\nfrom tests.sandbox import RealGitSandbox as R\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     f"class CaseTest(R):  {MARKER}\n\n"
     "    def test_case(self):\n        assert self is not None\n",
     ""),
    ("модуль с псевдонимом sb.RealGitSandbox",
     "import pytest\nimport tests.sandbox as sb\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     f"class CaseTest(sb.RealGitSandbox):  {MARKER}\n\n"
     "    def test_case(self):\n        assert self is not None\n",
     "RealGitSandbox"),
    *[(f"параметр {fx}",
       "import pytest\n\npytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
       f"def test_case({fx}):\n    assert {fx} is not None\n",
       fx)
      for fx in ("real_git", "origin_real_git", "initialized_tmp_root")],
    *[(f"параметр {fx} у фикстуры",
       "import pytest\n\npytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
       f"@pytest.fixture\ndef prepared({fx}):\n    return {fx}\n\n\n"
       "def test_case(prepared):\n    assert prepared is not None\n",
       fx)
      for fx in ("real_git", "origin_real_git", "initialized_tmp_root")],
    *[(f"usefixtures({fx}) модуля",
       "import pytest\n\npytestmark = [pytest.mark.size(\"SIZE\"), "
       f"pytest.mark.usefixtures(\"{fx}\")]\n\n\n"
       "def test_case():\n    assert True\n",
       fx)
      for fx in ("real_git", "origin_real_git", "initialized_tmp_root")],
    *[(f"usefixtures({fx}) теста",
       "import pytest\n\npytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
       f"@pytest.mark.usefixtures(\"{fx}\")\n"
       "def test_case():\n    assert True\n",
       fx)
      for fx in ("real_git", "origin_real_git", "initialized_tmp_root")],
    ("import subprocess",
     "import subprocess\n\nimport pytest\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     "def test_case():\n    assert subprocess is not None\n",
     "subprocess"),
    ("import subprocess as sp",
     "import subprocess as sp\n\nimport pytest\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     "def test_case():\n    assert sp is not None\n",
     "subprocess"),
    ("from subprocess import run",
     "from subprocess import run\n\nimport pytest\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     "def test_case():\n    assert run is not None\n",
     "subprocess"),
    ("import multiprocessing",
     "import multiprocessing\n\nimport pytest\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     "def test_case():\n    assert multiprocessing is not None\n",
     "multiprocessing"),
    ("import multiprocessing as mp",
     "import multiprocessing as mp\n\nimport pytest\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     "def test_case():\n    assert mp is not None\n",
     "multiprocessing"),
    ("from multiprocessing import Process",
     "from multiprocessing import Process\n\nimport pytest\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     "def test_case():\n    assert Process is not None\n",
     "multiprocessing"),
    *[(f"вызов {call}",
       "import os\n\nimport pytest\n\n"
       "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
       f"def test_case():\n    if os.environ.get('NEVER_SET_FLAG'):\n"
       f"        {call}({args})\n    assert True\n",
       needle)
      for call, args, needle in (
          ("os.system", "'true'", "os.system"),
          ("os.popen", "'true'", "os.popen"),
          ("os.fork", "", "os.fork"),
          ("os.spawnl", "os.P_WAIT, '/bin/true', 'true'", "os.spawn"),
          ("os.spawnv", "os.P_WAIT, '/bin/true', ['true']", "os.spawn"))],
]


@pytest.mark.parametrize("case, source, needle",
                         SMALL_HEAVY_CASES + SMALL_OTHER_CASES)
def test_ac2_small_resources_reported_medium_clean(case, source, needle):
    """Малый файл с песочницей настоящего git или БД пульта, с их фикстурой или с процессами — нарушение, называющее найденное; тот же исходник с `medium` — без нарушений.

    Сценарий: случай перечня AC-2 — класс наследует песочницу перечня
    (прямо, через один и два локальных подкласса, через псевдоним импорта
    класса или модуля), тест или фикстура берёт `real_git`/
    `origin_real_git`/`initialized_tmp_root` параметром или
    `usefixtures` модуля/теста, файл импортирует `subprocess`/
    `multiprocessing` любой формой или вызывает `os.system`/`os.popen`/
    `os.fork`/`os.spawn*`. При `small` нарушение есть; если у случая
    названо найденное имя — оно в тексте нарушения; если в исходнике
    отмечена строка класса — нарушение стоит на ней (класс наследует
    песочницу через цепочку или псевдоним). При `medium` список пуст.

    Ловит мутацию: из перечня выпал любой признак (имя песочницы, форма
    импорта, фикстура, `usefixtures` на одном из уровней, вызов `os.*`) —
    его случай без нарушения; локальный подкласс или псевдоним импорта не
    разворачивается до базы — класс случая без нарушения; правила малого
    файла применяются и к среднему — у `medium` нарушения.
    """
    heavy = frozenset(HEAVY)
    small = with_size(source, "small")
    found = test_lint.size_findings(small, LABEL, heavy)
    assert found, f"{case}: малый файл без нарушения:\n{small}"
    assert not any(NO_MARK in text for _l, text in found), (
        f"{case}: метка размера не распознана: {found}")
    if needle:
        assert any(needle in text for _l, text in found), (
            f"{case}: нарушение не называет «{needle}»: {found}")
    if MARKER in small:
        line = marked_line(small)
        assert any(number == line for number, _t in found), (
            f"{case}: нет нарушения в строке класса {line}: {found}")
    medium = with_size(source, "medium")
    assert test_lint.size_findings(medium, LABEL, heavy) == [], (
        f"{case}: средний файл с нарушениями:\n{medium}")


def test_ac2_heavy_names_include_roots_and_subclasses_only():
    """`heavy_sandbox_names` по исходникам-образцам отдаёт корень и его подклассы — через примесь и второго уровня — и не отдаёт постороннего класса.

    Сценарий: исходник `tests/sandbox.py` в памяти — `TmpRootTest`,
    корень `RealGitSandbox(TmpRootTest)`, примесь со случайным именем,
    подкласс `<имя>(<примесь>, RealGitSandbox)`, подкласс второго уровня
    `<имя>(<подкласс>)` и посторонний `<имя>(TmpRootTest)`; второй
    исходник `tests/<имя>_sandbox.py` — корень `SchemaTmpRootTest` и его
    подкласс. Порядок классов в файле и имена — от зерна.

    Ловит мутацию: перечень — только корни (подклассы не добавляются);
    база через примесь не просматривается (берётся только первая база);
    цепочка не замыкается на второй уровень; в перечень попадает
    любой подкласс `TmpRootTest` или примесь.
    """
    rng, seed = rng_and_seed()
    mixin, sub, deep, stray, schema_sub = (camel(rng) for _ in range(5))
    sources = {
        "tests/sandbox.py":
            "import unittest\n\n\n"
            "class TmpRootTest(unittest.TestCase):\n    pass\n\n\n"
            "class RealGitSandbox(TmpRootTest):\n    pass\n\n\n"
            f"class {mixin}:\n    pass\n\n\n"
            f"class {sub}({mixin}, RealGitSandbox):\n    pass\n\n\n"
            f"class {deep}({sub}):\n    pass\n\n\n"
            f"class {stray}(TmpRootTest):\n    pass\n",
        f"tests/{word(rng, 5)}_sandbox.py":
            "from tests.sandbox import TmpRootTest\n\n\n"
            "class SchemaTmpRootTest(TmpRootTest):\n    pass\n\n\n"
            f"class {schema_sub}(SchemaTmpRootTest):\n    pass\n",
    }
    found = test_lint.heavy_sandbox_names(sources)
    assert isinstance(found, frozenset), f"зерно: {seed}; не frozenset: {found!r}"
    for name in ("RealGitSandbox", sub, deep, "SchemaTmpRootTest", schema_sub):
        assert name in found, f"зерно: {seed}; нет {name}: {sorted(found)}"
    for name in ("TmpRootTest", mixin, stray):
        assert name not in found, f"зерно: {seed}; лишний {name}: {sorted(found)}"


def test_ac2_heavy_names_cross_file_chain_independent_of_order():
    """Подкласс в одном исходнике, его база — в другом, исходник наследника раньше исходника базы: перечень несёт и базу, и подкласс.

    Сценарий: словарь исходников, первым — `tests/<a>_sandbox.py` с
    `class <наследник>(<база>)` (база импортирована из второго файла),
    вторым — `tests/<b>_sandbox.py` с `class <база>(RealGitSandbox)`,
    последним — `tests/sandbox.py` с корнем `RealGitSandbox`. Тот же
    словарь в обратном порядке даёт тот же перечень.

    Ловит мутацию: файлы обходятся один раз по порядку словаря — база
    ещё не известна, когда разбирается наследник, и он выпадает;
    перечень зависит от порядка словаря.
    """
    rng, seed = rng_and_seed()
    base, child = camel(rng), camel(rng)
    first, second = word(rng, 5), word(rng, 6)
    child_rel = f"tests/{first}_sandbox.py"
    base_rel = f"tests/{second}_sandbox.py"
    root_rel = "tests/sandbox.py"
    child_src = (f"from tests.{second}_sandbox import {base}\n\n\n"
                 f"class {child}({base}):\n    pass\n")
    base_src = ("from tests.sandbox import RealGitSandbox\n\n\n"
                f"class {base}(RealGitSandbox):\n    pass\n")
    root_src = ("import unittest\n\n\n"
                "class RealGitSandbox(unittest.TestCase):\n    pass\n")
    forward = test_lint.heavy_sandbox_names({child_rel: child_src,
                                             base_rel: base_src,
                                             root_rel: root_src})
    backward = test_lint.heavy_sandbox_names({root_rel: root_src,
                                              base_rel: base_src,
                                              child_rel: child_src})
    for name in (base, child):
        assert name in forward, f"зерно: {seed}; нет {name}: {sorted(forward)}"
    assert forward == backward, (
        f"зерно: {seed}; перечень зависит от порядка: {sorted(forward)} "
        f"против {sorted(backward)}")


# --------------------------------------------------------------- AC-3

def test_ac3_small_with_light_fixtures_clean():
    """Малый файл с фикстурами `tmp_root`, `tmp_dir` и импортом `FakeProc` — без нарушений.

    Сценарий: модуль с `pytestmark = pytest.mark.size("small")`,
    `from tests.sandbox import FakeProc`, тестами с параметрами
    `tmp_root` и `tmp_dir` и фикстурой, берущей `tmp_dir`; перечень
    `heavy` — полный литерал AC-2. `size_findings` — пустой список.

    Ловит мутацию: признак фикстуры сверяется подстрокой (`tmp_root`
    принят за `initialized_tmp_root`); любой импорт из `tests.sandbox`
    считается тяжёлой песочницей; любой параметр-фикстура — нарушение.
    """
    source = ("import pytest\nfrom tests.sandbox import FakeProc\n\n"
              "pytestmark = pytest.mark.size(\"small\")\n\n\n"
              "@pytest.fixture\ndef folder(tmp_dir):\n    return tmp_dir.tdir\n\n\n"
              "def test_root(tmp_root):\n    assert tmp_root.root is not None\n\n\n"
              "def test_dir(tmp_dir, folder):\n    assert FakeProc is not None\n")
    assert test_lint.size_findings(source, LABEL, frozenset(HEAVY)) == []


# --------------------------------------------------------------- AC-4

MEDIUM_CASES = [
    *[(f"{call} с artel.py",
       "import subprocess\nimport sys\n\nimport pytest\n\n"
       "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
       f"def test_case():\n    {call}([sys.executable, \"orchestrator/artel.py\", "
       "\"status\"])\n")
      for call in ("subprocess.run", "subprocess.Popen", "subprocess.call",
                   "subprocess.check_call", "subprocess.check_output")],
    *[(f"{call} с pytest",
       "import subprocess\nimport sys\n\nimport pytest\n\n"
       "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
       f"def test_case(tmp_path):\n    {call}([sys.executable, \"-m\", \"pytest\", "
       "str(tmp_path)])\n")
      for call in ("subprocess.run", "subprocess.Popen", "subprocess.call",
                   "subprocess.check_call", "subprocess.check_output")],
    ("путь artel.py выражением",
     "import subprocess\nimport sys\nfrom pathlib import Path\n\nimport pytest\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n"
     "ROOT = Path(__file__).resolve().parent.parent\n\n\n"
     "def test_case():\n"
     "    subprocess.run([sys.executable, str(ROOT / \"orchestrator\" / "
     "\"artel.py\")])\n"),
    ("константа модуля ARTEL",
     "import subprocess\nimport sys\nfrom pathlib import Path\n\nimport pytest\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n"
     "ROOT = Path(__file__).resolve().parent.parent\n"
     "ARTEL = str(ROOT / \"artel.py\")\n\n\n"
     "def test_case():\n    subprocess.run([sys.executable, ARTEL])\n"),
    ("имя в теле функции с artel.py",
     "import subprocess\nimport sys\n\nimport pytest\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     "def test_case():\n"
     "    command = [sys.executable, \"orchestrator/artel.py\", \"status\"]\n"
     "    subprocess.run(command)\n"),
    ("имя в теле функции с pytest",
     "import subprocess\nimport sys\n\nimport pytest\n\n"
     "pytestmark = pytest.mark.size(\"SIZE\")\n\n\n"
     "def test_case(tmp_path):\n"
     "    command = [sys.executable, \"-m\", \"pytest\", str(tmp_path)]\n"
     "    subprocess.run(command)\n"),
]


@pytest.mark.parametrize("case, source", MEDIUM_CASES)
def test_ac4_medium_child_artel_or_pytest_reported_large_clean(case, source):
    """Средний файл, запускающий `artel.py` или pytest дочерним процессом, — нарушение; тот же исходник с `large` — без нарушений.

    Сценарий: случай перечня AC-4 — каждая из пяти функций `subprocess`
    с литералом `"orchestrator/artel.py"` и с литералом `"pytest"` в
    аргументах, путь `artel.py` выражением от `ROOT`, константа модуля
    `ARTEL` и имя, присвоенное в теле той же функции. При `medium`
    нарушение есть; при `large` список пуст.

    Ловит мутацию: из перечня выпала функция `subprocess`; литерал ищется
    только среди прямых элементов списка аргументов, а не во всём
    выражении (`ast.walk`) — путь выражением не ловится; имя модуля или
    тела функции не разворачивается до присвоенного выражения; литерал
    `artel.py` сверяется равенством, а не окончанием; правило среднего
    файла применяется к большому.
    """
    medium = with_size(source, "medium")
    found = test_lint.size_findings(medium, LABEL, frozenset(HEAVY))
    assert found, f"{case}: средний файл без нарушения:\n{medium}"
    assert not any(NO_MARK in text for _l, text in found), (
        f"{case}: метка размера не распознана: {found}")
    large = with_size(source, "large")
    assert test_lint.size_findings(large, LABEL, frozenset(HEAVY)) == [], (
        f"{case}: большой файл с нарушениями:\n{large}")


# --------------------------------------------------------------- AC-5

RECOGNIZED_FORMS = [
    ("список с другой меткой",
     "import pytest\n\npytestmark = [pytest.mark.size(\"small\"), "
     "pytest.mark.slow]\n\n\ndef test_case():\n    assert True\n"),
    ("псевдоним модуля pytest",
     "import pytest as pt\n\npytestmark = pt.mark.size(\"small\")\n\n\n"
     "def test_case():\n    assert pt is not None\n"),
    ("присваивание с аннотацией",
     "import pytest\n\npytestmark: list = [pytest.mark.size(\"small\")]\n\n\n"
     "def test_case():\n    assert True\n"),
]


@pytest.mark.parametrize("case, source", RECOGNIZED_FORMS)
def test_ac5_mark_forms_recognized(case, source):
    """Метка размера в списке `pytestmark`, через псевдоним `pytest` и в присваивании с аннотацией распознана — нарушений нет.

    Сценарий: малый файл без ресурсов, метка — одной из трёх форм AC-5.
    `size_findings` — пустой список (в том числе нет «нет метки
    размера»).

    Ловит мутацию: `pytestmark` разбирается только одиночной меткой (не
    списком); имя модуля pytest берётся буквально `pytest`, без
    псевдонимов; `ast.AnnAssign` не считается присваиванием `pytestmark`.
    """
    assert test_lint.size_findings(source, LABEL, frozenset(HEAVY)) == [], case


BAD_MARKS = [
    ("имя вне перечня",
     "import pytest\n\npytestmark = pytest.mark.size(\"huge\")\n\n\n"
     "def test_case():\n    assert True\n",
     ("huge",)),
    ("не строковый литерал",
     "import pytest\n\nSIZE_NAME = \"small\"\n"
     "pytestmark = pytest.mark.size(SIZE_NAME)\n\n\n"
     "def test_case():\n    assert True\n",
     ("SIZE_NAME",)),
    ("две метки модуля",
     "import pytest\n\npytestmark = [pytest.mark.size(\"small\"), "
     "pytest.mark.size(\"medium\")]\n\n\ndef test_case():\n    assert True\n",
     (SEVERAL, "small", "medium")),
    ("метка модуля и метка теста",
     "import pytest\n\npytestmark = pytest.mark.size(\"small\")\n\n\n"
     "@pytest.mark.size(\"large\")\ndef test_case():\n    assert True\n",
     (SEVERAL, "small", "large")),
]


@pytest.mark.parametrize("case, source, needles", BAD_MARKS)
def test_ac5_bad_marks_reported_with_values(case, source, needles):
    """Метка с именем вне перечня, не литералом или не одна — нарушение с найденными значениями.

    Сценарий: `size("huge")`, `size(SIZE_NAME)`, две метки размера
    уровня модуля, метка модуля плюс метка теста. В тексте одного из
    нарушений — каждое ожидаемое значение (для двух меток — «несколько
    меток размера» и оба найденных имени).

    Ловит мутацию: имя метки не сверяется с перечнем; не литерал
    принимается или падает исключением; берётся первая метка размера, а
    вторая (в том же списке или у теста) не видна; текст нарушения не
    называет найденное значение.
    """
    found = test_lint.size_findings(source, LABEL, frozenset(HEAVY))
    assert any(all(needle in text for needle in needles)
               for _l, text in found), (
        f"{case}: нет нарушения с {needles}: {found}")


# --------------------------------------------------------------- AC-7

def long_lived_text(name: str, mark: str | None, param: str = "") -> str:
    """Долгоживущий файл без прочих нарушений: строка группы, заявка мутации."""
    lines = ['"""Образец долгоживущего файла ' + name + ".", "",
             "Группа: " + guard.GROUP_LONG_LIVED, '"""', "import random", "",
             "import pytest", ""]
    if mark is not None:
        lines += [f"pytestmark = pytest.mark.size(\"{mark}\")", ""]
    lines += ["", f"def test_ac1_{name}({param}):",
              f'    """Образец {name}.', "",
              "    Ловит " + "мутацию: сумма перестаёт совпадать.", '    """',
              "    seed = random.randrange(1 << 30)",
              '    assert seed + 1 == 1 + seed, f"зерно: {seed}"', ""]
    return "\n".join(lines)


def size_errors(errors: list) -> list:
    return [e for e in errors if SIZE_PREFIX in e]


def task_id(rng) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def test_ac7_locked_without_mark_exempt_with_mark_checked():
    """Залоченный текст без метки освобождает файл от правил размера; залоченный текст с `size("small")` — нет: добавленный `real_git` или снятая метка дают отказ.

    Сценарий: `guard.long_lived_errors_from_files(files, <id>,
    network_addresses=True, lint_base={метка: залоченный текст},
    size_marks=True, sandbox_sources={})`. (а) залоченный без метки, новый
    без метки (тест переименован) — строк «размер —» нет; (б) залоченный
    с `size("small")`, новый добавил параметр `real_git` — строка
    «размер —» с меткой файла и `real_git`; (в) залоченный с
    `size("small")`, новый снял метку — строка с «нет метки размера».

    Ловит мутацию: залоченный файл с меткой тоже пропускается (наличие
    базы освобождает файл целиком); освобождение не смотрит в базу —
    файл (а) получает «нет метки размера»; метку ищут в новом тексте
    вместо залоченного — (в) пропускается.
    """
    rng, seed = rng_and_seed()
    tid = task_id(rng)
    label = f"tests/test_{tid.lower()}_{word(rng, 5)}.py"
    first, second = word(rng), word(rng)
    cases = [
        ("без метки — без метки", long_lived_text(first, None),
         long_lived_text(second, None), None),
        ("small — добавлен real_git", long_lived_text(first, "small"),
         long_lived_text(first, "small", "real_git"), "real_git"),
        ("small — метка снята", long_lived_text(first, "small"),
         long_lived_text(first, None), NO_MARK),
    ]
    for case, locked, new, needle in cases:
        errors = guard.long_lived_errors_from_files(
            [(label, new)], tid, network_addresses=True,
            lint_base={label: locked}, size_marks=True, sandbox_sources={})
        found = size_errors(errors)
        context = f"зерно: {seed}; {case}: {errors}"
        if needle is None:
            assert found == [], context
        else:
            assert any(label in e and needle in e for e in found), context


# --------------------------------------------------------------- AC-8

def test_ac8_bad_size_marks_value_named(tmp_root):
    """`test_profile.size_marks: other` — отказ разбора, называющий подполе, найденное значение и ожидаемое `required`, без «неизвестное подполе».

    Сценарий: запись проекта со всеми обязательными полями и профилем
    тестов; `targets.check` с `size_marks: other` — `TargetsError` с
    `test_profile.size_marks`, `other`, `required` и без «неизвестное
    подполе»; та же запись с `size_marks: required` и без подполя —
    проходит.

    Ловит мутацию: подполе не внесено в известные (отказ «неизвестное
    подполе»); значение не проверяется (`other` проходит); подполе стало
    обязательным (запись без него получает отказ); текст отказа не
    называет найденное значение или ожидаемое.
    """
    name = "sizeproj"
    entry = {"forge": "github", "url": f"file:///nonexistent/{name}",
             "base": "main", "token_slot": f"{name}-token", "no_paths": [],
             "project_skills": [], "merge_gate": "operator"}
    profile = {"command": ["python3", "-m", "pytest"],
               "long_lived_dir": "tests",
               "long_lived_name": "test_<id>_<name>.py",
               "weakening_scope": ["tests/**/*.py"],
               "mutation_claim_scope": ["tests/test_*.py"]}
    targets.check(name, dict(entry, test_profile=dict(profile)))
    targets.check(name, dict(entry, test_profile=dict(profile,
                                                      size_marks="required")))
    with pytest.raises(targets.TargetsError) as caught:
        targets.check(name, dict(entry, test_profile=dict(profile,
                                                          size_marks="other")))
    text = str(caught.value)
    assert "test_profile.size_marks" in text, text
    assert re.search(r"\bother\b", text), text
    assert "required" in text, text
    assert "неизвестное подполе" not in text, text


# --------------------------------------------------------------- AC-9

def test_ac9_rule_off_without_size_marks():
    """Мутация «правило размера применяется без `size_marks`» — красная: без параметра у файла без метки строк «размер —» нет, с `size_marks=True` — есть.

    Сценарий: новый долгоживущий файл без метки и без прочих нарушений;
    `long_lived_errors_from_files` без `size_marks` и с `size_marks=False`
    — без строк «размер —»; с `size_marks=True` — строка с меткой файла и
    «нет метки размера».

    Ловит мутацию: правила размера исполняются безусловно (умолчание
    `size_marks=True` или флаг не читается) — около 125 существующих
    тестов, строящих образцы без метки, получили бы отказ; либо флаг
    `True` не включает правила — отказа нет.
    """
    rng, seed = rng_and_seed()
    tid = task_id(rng)
    label = f"tests/test_{tid.lower()}_{word(rng, 5)}.py"
    files = [(label, long_lived_text(word(rng), None))]
    off = guard.long_lived_errors_from_files(files, tid)
    off_explicit = guard.long_lived_errors_from_files(files, tid,
                                                      size_marks=False)
    on = guard.long_lived_errors_from_files(files, tid, size_marks=True,
                                            sandbox_sources={})
    assert size_errors(off) == [], f"зерно: {seed}; {off}"
    assert size_errors(off_explicit) == [], f"зерно: {seed}; {off_explicit}"
    assert any(label in e and NO_MARK in e for e in size_errors(on)), (
        f"зерно: {seed}; {on}")


def test_ac9_requirement_subclasses_recognized():
    """Мутация «подкласс песочницы из требования 2 не распознан» — красная: подклассы корней через примесь и цепочку в перечне и дают нарушение малого файла.

    Сценарий: исходники в памяти той же формы, что песочницы пульта:
    примесь `_ConnSetupMixin`, корни `RealGitSandbox`, `SchemaTmpRootTest`
    и подклассы `ConnRealGitSandbox(_ConnSetupMixin, RealGitSandbox)`,
    `SchemaConnTmpRootTest(_ConnSetupMixin, SchemaTmpRootTest)`,
    `OriginRealGitSandbox(RealGitSandbox)`,
    `AutoOriginSandbox(OriginRealGitSandbox)`, `OutcomeGateSandbox` во
    втором файле и `ReportSandbox` в третьем. Каждый подкласс — в
    `heavy_sandbox_names`, и малый файл, наследующий его, даёт нарушение
    с его именем.

    Ловит мутацию: перечень — жёсткий список корней без обхода
    подклассов; примесь первой базой обрывает обход; подклассы второго
    уровня и других файлов не входят.
    """
    sources = {
        "tests/sandbox.py":
            "import unittest\n\n\n"
            "class TmpRootTest(unittest.TestCase):\n    pass\n\n\n"
            "class _ConnSetupMixin:\n    pass\n\n\n"
            "class SchemaTmpRootTest(TmpRootTest):\n    pass\n\n\n"
            "class SchemaConnTmpRootTest(_ConnSetupMixin, SchemaTmpRootTest):\n"
            "    pass\n\n\n"
            "class RealGitSandbox(TmpRootTest):\n    pass\n\n\n"
            "class ConnRealGitSandbox(_ConnSetupMixin, RealGitSandbox):\n"
            "    pass\n\n\n"
            "class OriginRealGitSandbox(RealGitSandbox):\n    pass\n\n\n"
            "class AutoOriginSandbox(OriginRealGitSandbox):\n    pass\n",
        "tests/outcome_gate_sandbox.py":
            "from tests.sandbox import RealGitSandbox\n\n\n"
            "class OutcomeGateSandbox(RealGitSandbox):\n    pass\n",
        "tests/report_outcome_sandbox.py":
            "from tests.outcome_gate_sandbox import OutcomeGateSandbox\n\n\n"
            "class ReportSandbox(OutcomeGateSandbox):\n    pass\n",
    }
    heavy = test_lint.heavy_sandbox_names(sources)
    for name in ("SchemaConnTmpRootTest", "ConnRealGitSandbox",
                 "OriginRealGitSandbox", "AutoOriginSandbox",
                 "OutcomeGateSandbox", "ReportSandbox"):
        assert name in heavy, f"нет {name}: {sorted(heavy)}"
        source = (f"import pytest\nfrom tests.sandbox import {name}\n\n"
                  "pytestmark = pytest.mark.size(\"small\")\n\n\n"
                  f"class CaseTest({name}):\n\n"
                  "    def test_case(self):\n        assert self is not None\n")
        found = test_lint.size_findings(source, LABEL, heavy)
        assert any(name in text for _l, text in found), f"{name}: {found}"
    assert "_ConnSetupMixin" not in heavy, sorted(heavy)
    assert "TmpRootTest" not in heavy, sorted(heavy)


def test_ac9_pytestmark_list_recognized():
    """Мутация «`pytestmark` списком не распознан» — красная: метка размера в списке `pytestmark` признаётся, у пустого списка — «нет метки размера».

    Сценарий: малый файл, у которого `pytestmark` — список со случайным
    порядком метки размера среди других меток (`slow`, `filterwarnings`),
    — без нарушений; `pytestmark = []` и список без метки размера — «нет
    метки размера».

    Ловит мутацию: разбор берёт только значение-вызов, список пропускает;
    берётся первый элемент списка — метка размера не первой не видна;
    любой непустой список принимается за метку.
    """
    rng, seed = rng_and_seed()
    others = ["pytest.mark.slow", "pytest.mark.filterwarnings(\"ignore\")"]
    items = others + ["pytest.mark.size(\"small\")"]
    rng.shuffle(items)
    template = ("import pytest\n\npytestmark = [{items}]\n\n\n"
                "def test_case():\n    assert True\n")
    good = template.format(items=", ".join(items))
    assert test_lint.size_findings(good, LABEL, frozenset(HEAVY)) == [], (
        f"зерно: {seed}\n{good}")
    for items_text in ("", ", ".join(others)):
        bad = template.format(items=items_text)
        found = test_lint.size_findings(bad, LABEL, frozenset(HEAVY))
        assert any(NO_MARK in text for _l, text in found), (
            f"зерно: {seed}; {found}\n{bad}")


def test_ac9_locked_with_mark_not_skipped():
    """Мутация «залоченный файл с меткой пропускается» — красная: залоченный текст со случайным размером и новый текст без метки — отказ «нет метки размера».

    Сценарий: `lint_base` несёт файл с `size("<размер>")` (размер — от
    зерна); новый текст того же файла — без метки.
    `long_lived_errors_from_files(..., size_marks=True)` — строка
    «размер —» с меткой файла и «нет метки размера».

    Ловит мутацию: любой файл, присутствующий в `lint_base`, освобождается
    от правил размера целиком.
    """
    rng, seed = rng_and_seed()
    tid = task_id(rng)
    label = f"tests/test_{tid.lower()}_{word(rng, 5)}.py"
    name = word(rng)
    locked = long_lived_text(name, rng.choice(("small", "medium", "large")))
    errors = guard.long_lived_errors_from_files(
        [(label, long_lived_text(name, None))], tid,
        lint_base={label: locked}, size_marks=True, sandbox_sources={})
    assert any(label in e and NO_MARK in e for e in size_errors(errors)), (
        f"зерно: {seed}; {errors}")


def test_ac9_guard_builds_list_from_sandbox_sources():
    """Мутация «guard передаёт пустой перечень при непустом дереве» — красная: подкласс песочницы, известный только из `sandbox_sources`, даёт нарушение малого файла.

    Сценарий: `sandbox_sources` — исходник `tests/sandbox.py` с
    `RealGitSandbox` и подклассом со случайным именем; малый долгоживущий
    файл наследует этот подкласс. `long_lived_errors_from_files(...,
    size_marks=True, sandbox_sources=...)` — строка «размер —» с меткой
    файла и именем подкласса; тот же файл при `sandbox_sources={}` —
    без строк «размер —».

    Ловит мутацию: guard не строит перечень из `sandbox_sources` (передаёт
    в `size_findings` пустой или жёсткий перечень корней) — подкласс со
    случайным именем не распознан.
    """
    rng, seed = rng_and_seed()
    tid = task_id(rng)
    label = f"tests/test_{tid.lower()}_{word(rng, 5)}.py"
    sub = camel(rng)
    sources = {"tests/sandbox.py":
               "import unittest\n\n\n"
               "class TmpRootTest(unittest.TestCase):\n    pass\n\n\n"
               "class RealGitSandbox(TmpRootTest):\n    pass\n\n\n"
               f"class {sub}(RealGitSandbox):\n    pass\n"}
    name = word(rng)
    text = "\n".join([
        '"""Образец долгоживущего файла ' + name + ".", "",
        "Группа: " + guard.GROUP_LONG_LIVED, '"""', "import pytest", "",
        f"from tests.sandbox import {sub}", "",
        "pytestmark = pytest.mark.size(\"small\")", "", "",
        f"class CaseTest({sub}):", "",
        f"    def test_ac1_{name}(self):",
        f'        """Образец {name}.', "",
        "        Ловит " + "мутацию: сумма перестаёт совпадать.", '        """',
        "        assert self is not None", ""])
    with_tree = guard.long_lived_errors_from_files(
        [(label, text)], tid, size_marks=True, sandbox_sources=sources)
    assert any(label in e and sub in e for e in size_errors(with_tree)), (
        f"зерно: {seed}; {with_tree}")
    empty = guard.long_lived_errors_from_files(
        [(label, text)], tid, size_marks=True, sandbox_sources={})
    assert size_errors(empty) == [], f"зерно: {seed}; {empty}"


def test_ac9_cross_file_chain_closed():
    """Мутация «цепочка подклассов между файлами не замкнута» — красная: наследник из файла, идущего в словаре раньше файла базы, в перечне и даёт нарушение.

    Сценарий: три исходника — `tests/sandbox.py` с корнем, файл
    наследника второго уровня и файл его базы; порядок словаря —
    случайная перестановка (зерно). Наследник второго уровня — в
    `heavy_sandbox_names`, и малый файл, наследующий его, даёт нарушение.

    Ловит мутацию: обход файлов однократный по порядку словаря — при
    перестановке «наследник раньше базы» наследник выпадает.
    """
    rng, seed = rng_and_seed()
    base, child = camel(rng), camel(rng)
    base_mod, child_mod = word(rng, 5), word(rng, 6)
    items = [
        ("tests/sandbox.py", "import unittest\n\n\n"
         "class RealGitSandbox(unittest.TestCase):\n    pass\n"),
        (f"tests/{base_mod}_sandbox.py",
         "from tests.sandbox import RealGitSandbox\n\n\n"
         f"class {base}(RealGitSandbox):\n    pass\n"),
        (f"tests/{child_mod}_sandbox.py",
         f"from tests.{base_mod}_sandbox import {base}\n\n\n"
         f"class {child}({base}):\n    pass\n"),
    ]
    orders = [list(reversed(items)), list(items)]
    shuffled = list(items)
    rng.shuffle(shuffled)
    orders.append(shuffled)
    for order in orders:
        heavy = test_lint.heavy_sandbox_names(dict(order))
        context = f"зерно: {seed}; порядок {[p for p, _s in order]}"
        assert child in heavy and base in heavy, f"{context}: {sorted(heavy)}"
        source = (f"import pytest\nfrom tests.{child_mod}_sandbox import "
                  f"{child}\n\npytestmark = pytest.mark.size(\"small\")\n\n\n"
                  f"class CaseTest({child}):\n\n"
                  "    def test_case(self):\n        assert self is not None\n")
        found = test_lint.size_findings(source, LABEL, heavy)
        assert any(child in text for _l, text in found), f"{context}: {found}"
