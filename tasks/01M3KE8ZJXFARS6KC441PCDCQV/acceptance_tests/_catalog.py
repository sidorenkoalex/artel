"""Общий код планки 01M3KE8ZJXFARS6KC441PCDCQV: сверенная таблица
каталога моделей (требование 1 SPEC), снимок каталога ДО правки и чтение
каталога ВЕТКИ задачи.

Редакция 2 — по ANSWER-1.md, вопрос 1, вариант (а) (ADR-0012,
ограничитель (а): механический конфликт, спора о существе критериев нет).
Первая редакция собирала «каталог после применения приложения PLAN»:
`models.yaml` — защищённый путь (`config.PROTECTED_PATHS`), задача правила
его приложением к PLAN, и планка мерила AC-1..AC-3/AC-5 разницей «база
сравнения ветки -> результат применения приложения». Коммит Оператора
`ae3370c5` внёс тот же каталог в `main` ВПЕРЁД задачи, базой сравнения
ветки (`gitcmd.diff_base`) стал коммит, который сам несёт новый каталог,
и измерение разницей стало неисполнимо при любом содержимом ветки и PLAN.

Что поменялось редакцией 2 и что осталось:

- предмет AC-1..AC-4/AC-8/AC-9 — каталог ВЕТКИ (`models.yaml` рабочей
  копии), прочитанный тем же разбором пульта `models.load_catalog`,
  которым каталог читает сам оркестратор; ни текст приложения, ни
  содержимое базы сравнения больше не читаются;
- «прежние» значения, без которых AC-5 не отличает старую цену от новой,
  берутся снимком `PREVIOUS_PRICES`/`PREVIOUS_MIN_CLI` ниже — записью
  факта на день SPEC, а не чтением базы сравнения;
- `base_file()` остался и читает базу сравнения по-прежнему: его
  единственный потребитель — AC-7 (прежнее значение
  `config.CLI_VERSION_PIN`), а `orchestrator/config.py` коммит
  `ae3370c5` не трогал, там разница с базой измерима и сегодня.
"""
import atexit
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, gitcmd, models  # noqa: E402

TASK_ID = "01M3KE8ZJXFARS6KC441PCDCQV"

#: Путь каталога в дереве репозитория.
CATALOG_PATH = "models.yaml"

#: Дата прейскуранта всех правленых и добавленных записей (AC-2).
PRICE_DATE = "2026-09-28"

#: Три новые записи (AC-1): цены в порядке `models.PRICE_KINDS`
#: (вход / выход / запись в кэш / чтение из кэша), наименьшая версия
#: клиента и статус.
NEW_RECORDS = {
    "claude-opus-5-5": {
        "provider": "claude",
        "prices": (4.00, 20.00, 5.00, 0.20),
        "min_cli_version": "2.1.280",
        "status": "supported",
    },
    "gpt-6-sol": {
        "provider": "codex",
        "prices": (2.00, 10.00, 2.50, 0.20),
        "min_cli_version": "0.156.1",
        "status": "experimental",
    },
    "gpt-6-luna": {
        "provider": "codex",
        "prices": (0.10, 0.50, 0.125, 0.01),
        "min_cli_version": "0.157.0",
        "status": "experimental",
    },
}

#: Записи, у которых правится весь прейскурант (AC-2).
CORRECTED_PRICES = {
    "claude-fable-5-1": (10.00, 50.00, 12.50, 0.25),
    "claude-sonnet-5": (2.00, 10.00, 2.50, 0.20),
}

#: Записи раздела `codex`, у которых правится только цена записи в кэш
#: (AC-2): до правки она везде равнялась цене входа.
CORRECTED_CACHE_WRITE = {
    "gpt-6-astra": 12.50,
    "gpt-5.6-sol": 5.00,
    "gpt-5.6-terra": 2.50,
    "gpt-5.6-luna": 0.25,
}

#: Все записи, чья `price_date` обязана стать `2026-09-28` (AC-2):
#: добавленные, правленые и `claude-opus-5`, у которой меняется только она.
DATED_RECORDS = (tuple(NEW_RECORDS) + tuple(CORRECTED_PRICES)
                 + tuple(CORRECTED_CACHE_WRITE) + ("claude-opus-5",))

#: Прейскурант каталога ДО правки — снимок коммита, предшествующего
#: внесению каталога в main (`ae3370c5^`, голова `main` на день SPEC).
#: Литерал, а не чтение базы сравнения (редакция 1 брала его именно
#: оттуда): базой сравнения ветки стал уже правленый каталог, и «прежнее»
#: значение из git больше не достаётся. Снимок прошлого во времени не
#: меняется — это запись факта, а не утверждение о состоянии системы на
#: сегодня (skills/test-authoring.md, «Запрещено утверждать состояние
#: системы на сегодня», — запрет как раз про второе).
PREVIOUS_PRICES = {
    "claude-sonnet-5": (3.00, 15.00, 3.75, 0.30),
    "claude-opus-5": (5.00, 25.00, 6.25, 0.50),
    "claude-fable-5-1": (5.00, 25.00, 6.25, 0.50),
    "gpt-6-astra": (10.00, 50.00, 10.00, 1.00),
    "gpt-5.6-sol": (4.00, 20.00, 4.00, 0.40),
    "gpt-5.6-terra": (2.00, 12.00, 2.00, 0.20),
    "gpt-5.6-luna": (0.20, 1.20, 0.20, 0.02),
    "gpt-5.5": (5.00, 30.00, 5.00, 0.50),
}

#: Наименьшие версии клиента ДО правки — тот же снимок (AC-5, вторая
#: половина). Таблица требования 1 минимумов существующих записей не
#: двигает, поэтому сегодня список расхождений пуст; проверка сторожит
#: именно тот случай, когда минимум всё-таки поедет.
PREVIOUS_MIN_CLI = {
    "claude-sonnet-5": "1.0.0",
    "claude-opus-5": "1.0.0",
    "claude-fable-5-1": "2.1.251",
    "gpt-6-astra": "0.155.1",
    "gpt-5.6-sol": "0.155.1",
    "gpt-5.6-terra": "0.155.1",
    "gpt-5.6-luna": "0.155.1",
    "gpt-5.5": "0.155.1",
}

#: Снимаемая модель (AC-3).
WITHDRAWN_MODEL = "gpt-5.5"

#: Новый состав каталога по разделам (требование 3, AC-4).
NEW_COMPOSITION = {
    "claude": ["claude-fable-5-1", "claude-opus-5", "claude-opus-5-5",
               "claude-sonnet-5"],
    "codex": ["gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-6-astra",
              "gpt-6-luna", "gpt-6-sol"],
}

#: Пометка «цены не сверены» у записи `claude-fable-5-1` (AC-2).
UNVERIFIED_PRICE_MARK = "ЦЕНЫ НЕ СВЕРЕНЫ"

_MISSING = object()
_branch_catalog = _MISSING


class CatalogUnavailable(AssertionError):
    """Каталог ветки не прочитать: файла нет либо он не разбирается
    `models.load_catalog`. `AssertionError` — чтобы такой исход был
    ОТКАЗОМ теста, а не тихим пропуском критерия."""


class BranchCatalog:
    """Каталог `models.yaml` рабочей копии ветки задачи.

    `text` — текст файла, `catalog` — он же разобранный
    `models.load_catalog`, `dir` — временный каталог для производных
    фикстур (AC-4 подставляет модулю набора каталог с переименованной и
    с лишней моделью, и класть их рядом с боевым файлом нельзя).
    """

    def __init__(self, path: Path, tmp: Path):
        self.path = path
        self.dir = tmp
        self.text = path.read_text(encoding="utf-8")
        self.catalog = models.load_catalog(path)


def branch() -> str:
    """Имя ветки рабочего каталога планки. Берётся у git рабочей копии, а
    не `gitcmd.current_branch()`: тот ходит в `config.ROOT`, который у
    прогона пультом равен главной копии, а планка живёт в worktree
    задачи."""
    res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                         cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        raise CatalogUnavailable(
            f"git не ответил на имя ветки рабочей копии: {res.stderr.strip()}")
    return res.stdout.strip()


def plan_text() -> str:
    """Текст PLAN.md — ИЗ артефактной ветки задачи (ADR-0016), тем же
    примитивом, которым его читает пульт. Диск рабочей копии источником
    не служит: в среде прогона гейта из `tasks/<id>/` материализован один
    `acceptance_tests/`."""
    text, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                               f"tasks/{TASK_ID}/PLAN.md")
    if text is None:
        raise CatalogUnavailable(
            f"PLAN.md задачи не прочитан из артефактной ветки "
            f"{artifact_branch.branch_name(TASK_ID)}: {reason}")
    return text


def _base_sha() -> str:
    base = gitcmd.diff_base(branch(), repo=REPO_ROOT)
    if base is None:
        raise CatalogUnavailable(
            "git не ответил на базу сравнения ветки задачи "
            "(gitcmd.diff_base) — прежнее значение читать неоткуда")
    return base


def _build() -> BranchCatalog:
    path = REPO_ROOT / CATALOG_PATH
    if not path.is_file():
        raise CatalogUnavailable(
            f"{CATALOG_PATH} в рабочей копии {REPO_ROOT} не найден — "
            f"предмета критериев нет")
    tmp = Path(tempfile.mkdtemp(prefix="artel-plank-catalog-"))
    atexit.register(shutil.rmtree, tmp, True)
    try:
        return BranchCatalog(path, tmp)
    except models.ModelsError as exc:
        raise CatalogUnavailable(
            f"{CATALOG_PATH} ветки не разобран пультом: {exc}") from exc


def catalog() -> BranchCatalog:
    """Каталог ветки — одной сборкой на процесс: девять файлов планки
    спрашивают его по разу, а разбор стоит дороже, чем сам ассерт."""
    global _branch_catalog
    if _branch_catalog is _MISSING:
        try:
            _branch_catalog = _build()
        except CatalogUnavailable as exc:
            _branch_catalog = exc
    if isinstance(_branch_catalog, CatalogUnavailable):
        raise _branch_catalog
    return _branch_catalog


def record(test, model_id: str):
    """Запись `model_id` каталога ветки; отсутствие записи — отказ теста с
    внятным текстом, а не `KeyError`."""
    catalog_of_branch = catalog().catalog
    if model_id not in catalog_of_branch.models:
        test.fail(f"в каталоге ветки нет записи {model_id} "
                  f"(есть: {', '.join(sorted(catalog_of_branch.models))})")
    return catalog_of_branch.models[model_id]


def assert_prices(test, model_id: str, expected) -> None:
    """Четыре цены записи — по видам `models.PRICE_KINDS`, каждая своим
    ассертом: расхождение обязано назвать ВИД токена, иначе Оператор
    сверяет кортежи глазами."""
    entry = record(test, model_id)
    for kind, want, got in zip(models.PRICE_KINDS, expected, entry.list_price):
        with test.subTest(model=model_id, kind=kind):
            test.assertAlmostEqual(
                want, got, places=6,
                msg=f"{model_id}: цена {kind} — {got}, сверенная {want}")


def tests_sources() -> list:
    """[(путь относительно корня, текст)] — все модули `tests/` рабочей
    копии. Предмет AC-3/AC-5/AC-6/AC-7 — исходники набора, они живут в
    ветке задачи и читаются с диска законно (артефакты задачи — нет)."""
    out = []
    for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
        out.append((path.relative_to(REPO_ROOT).as_posix(),
                    path.read_text(encoding="utf-8")))
    return out


def base_file(rel: str) -> str:
    """Текст файла `rel` в базе сравнения ветки — «как было до задачи».
    Нужен там, где критерий говорит о ПРЕЖНЕМ значении и разница с базой
    измерима: единственный такой путь после `ae3370c5` —
    `orchestrator/config.py` (AC-7), его тот коммит не трогал. Для
    каталога прежние значения берутся снимком `PREVIOUS_*` выше."""
    text, reason = gitcmd.show(_base_sha(), rel)
    if text is None:
        raise CatalogUnavailable(f"{rel} не прочитан из базы сравнения: "
                                 f"{reason}")
    return text
