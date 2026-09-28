"""Общий код планки 01M3KE8ZJXFARS6KC441PCDCQV: сверенная таблица
каталога моделей (требование 1 SPEC) и сборка ТОГО каталога, который
получится у пульта после применения приложения PLAN.

Каталог `models.yaml` — защищённый путь (`config.PROTECTED_PATHS`):
задача не правит его веткой, а прикладывает unified-дифф к PLAN.md
(SPEC, «Не входит»). Поэтому дерево ветки задачи о новых записях ничего
не знает, и предмет критериев AC-1..AC-3 живёт не на диске рабочей
копии, а в приложении: планка достаёт PLAN.md из АРТЕФАКТНОЙ ветки
(`gitcmd.show`, как это делает сам пульт), разбирает приложения тем же
разбором, что гейт применимости (`scripts/guard.py::plan_appendices`),
кладёт файлы базы сравнения во временный каталог и применяет к ним
дифф — ровно тем же `git apply`, что `orchestrator/advance_gates/
plan_appendix.py::git_apply` отдаёт git'у на выходе `in_dev`.

База сравнения — `gitcmd.diff_base` (точка расхождения с `origin/main`,
не с локальной веткой: локальная `main` главной копии равна пину пульта
и отстаёт от origin). Приложение, УЖЕ лежащее в базе (штатный путь после
мержа: коммит приложений ложится в main), распознаётся обратным
`git apply --reverse --check` и не считается дефектом — файл базы уже
несёт правку.
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
from scripts import guard  # noqa: E402

TASK_ID = "01M3KE8ZJXFARS6KC441PCDCQV"

#: Путь каталога в дереве репозитория — он же путь внутри приложения.
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
_applied = _MISSING


class AppendixUnavailable(AssertionError):
    """Каталог «после приложения» не собрать: PLAN.md ещё нет, приложения
    в нём нет, дифф не применяется или git не ответил. `AssertionError` —
    чтобы такой исход был ОТКАЗОМ теста, а не тихим пропуском критерия."""


class Applied:
    """Каталог, полученный применением приложений PLAN к базе сравнения.

    `text` — текст `models.yaml` после применения, `catalog` — он же
    разобранный `models.load_catalog`, `base_catalog` — каталог базы
    сравнения (до правки; нужен AC-5, чтобы отличить ПРЕЖНЮЮ цену от
    новой без литералов в самой планке), `paths` — пути, названные
    приложениями PLAN.
    """

    def __init__(self, tmp: Path, base_text: str, paths: tuple):
        self.dir = tmp
        self.path = tmp / CATALOG_PATH
        self.text = self.path.read_text(encoding="utf-8")
        self.base_text = base_text
        self.paths = paths
        self.catalog = models.load_catalog(self.path)
        base_path = tmp / "models.base.yaml"
        base_path.write_text(base_text, encoding="utf-8")
        self.base_catalog = models.load_catalog(base_path)


def branch() -> str:
    """Имя ветки рабочего каталога планки. Берётся у git рабочей копии, а
    не `gitcmd.current_branch()`: тот ходит в `config.ROOT`, который у
    прогона пультом равен главной копии, а планка живёт в worktree
    задачи."""
    res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                         cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        raise AppendixUnavailable(
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
        raise AppendixUnavailable(
            f"PLAN.md задачи не прочитан из артефактной ветки "
            f"{artifact_branch.branch_name(TASK_ID)}: {reason}")
    return text


def _base_sha() -> str:
    base = gitcmd.diff_base(branch(), repo=REPO_ROOT)
    if base is None:
        raise AppendixUnavailable(
            "git не ответил на базу сравнения ветки задачи "
            "(gitcmd.diff_base) — применить приложение не к чему")
    return base


def _apply(tmp: Path, appendix) -> None:
    """`git apply` одного приложения во временном каталоге. Уже
    применённое приложение (база сравнения его несёт — штатный путь после
    мержа) распознаётся обратной проверкой и дефектом не считается."""
    patch = tmp / "appendix.diff"
    patch.write_text(appendix.diff, encoding="utf-8")
    res = subprocess.run(["git", "apply", str(patch)], cwd=tmp,
                         capture_output=True, text=True)
    if res.returncode == 0:
        return
    back = subprocess.run(["git", "apply", "--reverse", "--check", str(patch)],
                          cwd=tmp, capture_output=True, text=True)
    if back.returncode == 0:
        return
    raise AppendixUnavailable(
        f"приложение PLAN {', '.join(appendix.paths)} не применяется к базе "
        f"сравнения ни прямо, ни обратно: {res.stderr.strip()[:300]}")


def _build() -> Applied:
    text = plan_text()
    appendices, errors = guard.plan_appendices(text)
    if errors:
        raise AppendixUnavailable(
            f"приложения PLAN не разобраны: {'; '.join(errors)}")
    if not appendices:
        raise AppendixUnavailable(
            "в PLAN.md нет ни одного раздела «## Приложение» с блоком "
            "```diff — каталог models.yaml правится только приложением "
            "(SPEC, «Не входит»)")
    paths = tuple(path for appendix in appendices for path in appendix.paths)
    if CATALOG_PATH not in paths:
        raise AppendixUnavailable(
            f"приложения PLAN называют пути {', '.join(paths)} — среди них "
            f"нет {CATALOG_PATH}")

    base = _base_sha()
    base_text, reason = gitcmd.show(base, CATALOG_PATH)
    if base_text is None:
        raise AppendixUnavailable(
            f"{CATALOG_PATH} не прочитан из базы сравнения {base}: {reason}")

    tmp = Path(tempfile.mkdtemp(prefix="artel-plank-catalog-"))
    atexit.register(shutil.rmtree, tmp, True)
    # Файлы базы — во временный каталог: git apply сверяет патч с ДЕРЕВОМ,
    # и приложение к любому другому защищённому пути тоже обязано лечь,
    # иначе порядок применения разойдётся с тем, что делает пульт.
    for rel in dict.fromkeys(paths):
        file_text, _ = gitcmd.show(base, rel)
        if file_text is None:
            continue
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(file_text, encoding="utf-8")
    for appendix in appendices:
        _apply(tmp, appendix)
    return Applied(tmp, base_text, paths)


def applied() -> Applied:
    """Каталог после приложения — одной сборкой на процесс: девять файлов
    планки спрашивают его по разу, а разбор PLAN и `git apply` стоят
    дороже, чем сам ассерт."""
    global _applied
    if _applied is _MISSING:
        try:
            _applied = _build()
        except AppendixUnavailable as exc:
            _applied = exc
    if isinstance(_applied, AppendixUnavailable):
        raise _applied
    return _applied


def record(test, model_id: str):
    """Запись `model_id` каталога после приложения; отсутствие записи —
    отказ теста с внятным текстом, а не `KeyError`."""
    catalog = applied().catalog
    if model_id not in catalog.models:
        test.fail(f"в каталоге после приложения PLAN нет записи {model_id} "
                  f"(есть: {', '.join(sorted(catalog.models))})")
    return catalog.models[model_id]


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
    Нужен там, где критерий говорит о ПРЕЖНЕМ значении (AC-5, AC-7): брать
    его литералом в планку значило бы зашить сегодняшнее состояние."""
    text, reason = gitcmd.show(_base_sha(), rel)
    if text is None:
        raise AppendixUnavailable(f"{rel} не прочитан из базы сравнения: "
                                  f"{reason}")
    return text
