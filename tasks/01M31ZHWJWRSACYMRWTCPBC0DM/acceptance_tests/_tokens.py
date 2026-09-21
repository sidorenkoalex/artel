"""Общая обвязка планки задачи 01M31ZHWJWRSACYMRWTCPBC0DM (токены рядом с
долларами в `status`, RETRO и `report`).

Не тест: общий код нескольких файлов планки живёт только в модулях `_*.py`
рядом с тестами (skills/test-authoring.md). Здесь — песочница пульта с
задачами и журналом стоимости, разбор HTML отчёта на элементы и мелкие
предикаты «вид токенов показан числом», «прочерк», «голый ноль».

Песочница переходов FSM здесь не нужна и не заводится: предмет задачи —
ПОКАЗ уже учтённых чисел, а не переход состояния, поэтому берётся готовая
`tests.sandbox.TaskSeededTmpRootTest` (временные пути `config` + БД + одна
заведённая задача), а не собственная копия чего-либо из `tests/sandbox.py`.

Журнал шагов заполняется теми же вызовами, которыми его пишет пульт:
`spend.charge_step` кладёт «agent cost KNOWN» с разбивкой по видам,
`model=`/`provider=` и `actual_usd=`, а возвращённый ей хвост дословно
уходит в «agent run finished» — ровно так это делает
`orchestrator/runner.py::_account_step`. Фикстура не решает за
разработчика, какую из двух строк он прочтёт: обе несут одни и те же
числа.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, models, spend, store, yamlmini  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

TASK_ID = "01M31ZHWJWRSACYMRWTCPBC0DM"

#: Четыре общих вида цены — AC-3 называет их дословно (`input`, `output`,
#: `cache_write`, `cache_read`), а каталог держит тот же кортеж и в том же
#: порядке. Берём из каталога, а не литералом: вид токенов — крутилка
#: `orchestrator/models.py`, и фикстура, разошедшаяся с ней, молча потеряла
#: бы счётчик на `spend.by_price_kind`.
KINDS = tuple(models.PRICE_KINDS)

#: Две роли с полным учётом токенов.
DEV_ROLE = "developer"
REV_ROLE = "reviewer"
#: Роль, чьи шаги дошли до конца, но разбивки токенов не принесли вовсе
#: (цена от CLI есть, `tokens_by_type` пуст) — предмет AC-5.
MUTE_ROLE = "analyst"

#: Разбивка usage двух ролей. Числа мелкие, взаимно простые и попарно
#: различные — вместе с суммами по видам (34/42/48/56), суммами по ролям
#: (60/120) и суммой задачи (180) они образуют набор без единого
#: совпадения: любое «сложили не то с тем» меняет ЧИСЛО, а не только
#: подпись. Двузначность нарочна — число без разделителя разрядов
#: ищется в тексте одинаково при любом вкусе форматирования.
DEV_TOKENS = dict(zip(KINDS, (11, 13, 17, 19)))
REV_TOKENS = dict(zip(KINDS, (23, 29, 31, 37)))
TASK_TOKENS = {kind: DEV_TOKENS[kind] + REV_TOKENS[kind] for kind in KINDS}

DEV_TOTAL = sum(DEV_TOKENS.values())
REV_TOTAL = sum(REV_TOKENS.values())
TASK_TOTAL = sum(TASK_TOKENS.values())

DEV_USD = 1.25
REV_USD = 2.50
MUTE_USD = 0.75
#: Задача без единой записи токенов: деньги есть, разбивки нет.
SILENT_USD = 4.25

#: Модель и провайдер шагов каждой роли. Идентификаторов нет в каталоге
#: моделей — учёт уходит прежним путём факта CLI (`spend._cost_from_cli`
#: деградирует в «истину» на неизвестной модели), тариф не резолвится,
#: сверки курса и алерта расхождения в строке не появляется. Провайдеры
#: РАЗНЫЕ: роль, показанная с чужим провайдером, обязана быть отличима.
DEV_MODEL = "alfa-model-x"
DEV_PROVIDER = "alfa-cli"
REV_MODEL = "beta-model-y"
REV_PROVIDER = "beta-cli"

#: Колонки закрытой задачи, у которых `report` СЕГОДНЯ печатает прочерк на
#: `NULL` (`report._DASH`): фикстура заполняет их, чтобы прочерк в строке
#: отчёта означал ровно одно — «токенов нет», а не «диф не посчитан».
DIFF_BYTES = 7777
SPLIT_TEXT = "сигналов нет"

#: Прочерк: em-dash пульта (`report._DASH`) и en-dash — одно и то же
#: «данных нет» для читателя, различать их критерий не просит.
DASH_RE = re.compile(r"[—–]")

#: «Голый ноль» — ноль, не входящий в число вида `0/3`, `$0.00`, `T001`.
#: Именно он и есть запрещённый критериями 2/5/9 ноль вместо прочерка:
#: соседство с цифрой, точкой или косой чертой означает, что ноль —
#: часть уже существующей дроби/суммы/идентификатора, а не показанный
#: счётчик токенов.
BARE_ZERO_RE = re.compile(r"(?<![\d./])0(?![\d./])")


def shows_value(text: str, kind: str, value: int) -> bool:
    """Вид токенов назван в тексте рядом со СВОИМ числом.

    «Рядом» — без единой другой цифры между именем вида и числом (в любом
    порядке, не дальше 40 символов): так одинаково проходят `input=11`,
    `input: 11`, `<td>input</td><td>11</td>` и `11 input`, но не проходит
    `input=34 … 11`, где 11 принадлежит соседнему виду или другому
    разрезу.
    """
    name = re.escape(kind)
    forward = re.search(rf"{name}\D{{0,40}}{value}(?!\d)", text)
    backward = re.search(rf"(?<!\d){value}\D{{0,40}}{name}", text)
    return bool(forward or backward)


def missing_kinds(text: str, tokens: dict) -> list:
    """Виды разбивки, которых в тексте нет со своим числом."""
    return [kind for kind, value in tokens.items()
            if not shows_value(text, kind, value)]


def has_dash(text: str) -> bool:
    return bool(DASH_RE.search(text))


def bare_zeros(text: str) -> list:
    """Голые нули текста — то, чего в строке без записей токенов быть не
    должно (AC-2/AC-5/AC-9)."""
    return BARE_ZERO_RE.findall(text)


def zeroed_kinds(text: str, kinds=KINDS) -> list:
    """Виды разбивки, показанные нулём вместо прочерка."""
    return [kind for kind in kinds if shows_value(text, kind, 0)]


def agent_roles() -> list:
    """Роли-агенты карты исполнителей РЕАЛЬНОГО репозитория (`roles.yaml`).

    Читается файл, а не зашитый список: число ролей — крутилка Оператора,
    а от него зависит высота блока стоимости RETRO (AC-6). Песочница здесь
    ни при чём: `config.ROLES` в ней подменён временным путём, а вопрос
    «сколько ролей у пульта» задаётся настоящей карте.
    """
    text = (REPO_ROOT / "roles.yaml").read_text(encoding="utf-8")
    entries = yamlmini.mapping(text).get("roles") or {}
    return [name for name, entry in entries.items()
            if isinstance(entry, dict) and entry.get("executor") == "agent"]


# ------------------------------------------------------- разбор HTML отчёта

class _Elements(HTMLParser):
    """Текст КАЖДОГО элемента документа — не разметка, а то, что читатель
    видит внутри элемента (вложенные элементы входят в текст внешнего).

    Нужен ровно для одного вопроса критериев 7-9: стоят ли числа токенов
    в ТОЙ ЖЕ строке отчёта, что и доллары задачи/роли. Разметку `report`
    выбирает разработчик (строка таблицы, `div`, элемент списка), поэтому
    планка не знает ни классов, ни тегов — только вложенность.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list = []
        self.texts: list = []

    def handle_starttag(self, tag, attrs):
        self.stack.append([tag, []])

    def handle_data(self, data):
        if self.stack:
            self.stack[-1][1].append(data)

    def _close(self) -> None:
        _name, chunks = self.stack.pop()
        text = "".join(chunks)
        self.texts.append(text)
        if self.stack:
            self.stack[-1][1].append(text)

    def handle_endtag(self, tag):
        # Пустые теги (`<meta>`, `<br>`) закрывающего не имеют и остаются
        # в стеке — закрытие внешнего элемента сворачивает их заодно.
        while self.stack:
            name = self.stack[-1][0]
            self._close()
            if name == tag:
                break

    def finish(self) -> list:
        while self.stack:
            self._close()
        return self.texts


def elements(html: str) -> list:
    parser = _Elements()
    parser.feed(html)
    return parser.finish()


def rows(html: str, marker: str, *forbidden: str) -> list:
    """Элементы отчёта, несущие `marker` и знак доллара и НЕ несущие ни
    одного из `forbidden`.

    `forbidden` — маркеры соседей по разрезу (идентификатор другой задачи,
    имя другой роли): без них под определение попадает и `<body>` целиком,
    в котором рядом оказывается вообще всё. Так «строка разреза» остаётся
    строкой, а не документом.
    """
    return [text for text in elements(html)
            if marker in text and "$" in text
            and not any(other in text for other in forbidden)]


# ------------------------------------------------------------- песочница

class TokensSandbox(TaskSeededTmpRootTest):
    """Временный пульт с двумя задачами: `self.TASK` — с записями токенов,
    `self.SILENT` — без них. Обе в `done`, обе с заполненными `diff_bytes`/
    `split_assessment` (см. `DIFF_BYTES`).
    """

    TASK = "T001"
    SILENT = "T002"

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.update_task(self.conn, self.TASK, state="done",
                          diff_bytes=DIFF_BYTES, split_assessment=SPLIT_TEXT)
        store.insert_task(self.conn, self.SILENT, "Задача без токенов",
                          "done", "task/t002-bez-tokenov",
                          config.DEFAULT_TARGET, 25.0)
        store.update_task(self.conn, self.SILENT, diff_bytes=DIFF_BYTES,
                          split_assessment=SPLIT_TEXT)

    def charge(self, task_id: str, role: str, usd: float, tokens: dict = None,
               *, model: str = None, provider: str = None,
               attempt: int = 1) -> None:
        """Завершённый шаг роли — теми же двумя записями журнала, какими его
        пишет `orchestrator/runner.py`: «agent cost KNOWN» (её кладёт сам
        `spend.charge_step`) и «agent run finished» с возвращённым хвостом.
        `tokens is None` — итог запуска без разбивки: цена есть, видов нет.
        """
        numbered = f"попытка {attempt}/1"
        if model is not None:
            numbered += f", model={model}, provider={provider}"
        cost = {"usd": usd,
                "tokens": sum(tokens.values()) if tokens else None,
                "tokens_by_type": dict(tokens) if tokens else None}
        spent = spend.charge_step(self.conn, task_id, role, cost, numbered)
        store.journal(self.conn, task_id, role, "agent run finished",
                      f"rc=0, {numbered}{spent}, окружение: планка {TASK_ID}")

    def charge_two_roles(self, task_id: str = None) -> None:
        """Два шага с разбивкой по видам — `developer` и `reviewer`."""
        task_id = task_id or self.TASK
        self.charge(task_id, DEV_ROLE, DEV_USD, DEV_TOKENS,
                    model=DEV_MODEL, provider=DEV_PROVIDER)
        self.charge(task_id, REV_ROLE, REV_USD, REV_TOKENS,
                    model=REV_MODEL, provider=REV_PROVIDER, attempt=2)

    def charge_without_tokens(self, task_id: str, role: str,
                              usd: float) -> None:
        """Шаг, чей итог запуска пришёл без разбивки usage. `model=`/
        `provider=` к такой строке не приписываются — `runner.
        _account_step` дополняет `numbered` этими полями ровно тогда,
        когда разбивка есть, и подсунуть их здесь значило бы дать
        разработчику данные, которых у него на этом пути не будет."""
        self.charge(task_id, role, usd, None)
