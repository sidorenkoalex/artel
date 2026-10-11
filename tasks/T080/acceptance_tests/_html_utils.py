"""Общие вспомогательные функции приёмочных тестов T080: поиск и разбор
статических HTML-файлов макета без внешних зависимостей (только stdlib —
`bs4`/lxml в окружении нет и AC-2 запрещает макету зависеть от чего-либо
кроме HTML/CSS, так что тестовому харнесу их требовать тоже не стоит).
"""
import re
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parents[1]  # tasks/T080/
ACCEPTANCE_DIR = Path(__file__).resolve().parent

# Канонические состояния FSM задачи — источник истины orchestrator/fsm.py
# (переходы store.set_state) и orchestrator/config.py (STATE_ROLE ∪
# AUTO_STOP, комментарий config.py:196 «ключи покрывают все состояния FSM
# вне STATE_ROLE»). НЕ включает `paused` — это булево поле tasks.paused
# (store.py:35), не состояние FSM (orchestrator/pause.py:53-55).
CANONICAL_FSM_STATES = frozenset({
    "spec_writing", "spec_gate", "tests_writing", "in_dev", "review",
    "acceptance", "merge_gate", "escalated", "done", "killed",
})

TASK_ID_RE = re.compile(r"\bT\d{2,4}\b")


def html_files():
    """Все *.html/*.htm файлы макета в tasks/T080/, кроме самих тестов."""
    files = []
    for ext in ("*.html", "*.htm"):
        for p in TASK_DIR.rglob(ext):
            if ACCEPTANCE_DIR == p.parent or ACCEPTANCE_DIR in p.parents:
                continue
            files.append(p)
    return sorted(files)


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent", "parts")

    def __init__(self, tag, attrs, parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []  # только дочерние _Node, для обхода дерева
        self.parent = parent
        # Дочерние узлы И текстовые куски вперемешку, В ПОРЯДКЕ документа
        # (важно: текст между <div>1/3</div> и <div>lease</div> — это
        # пробел/перевод строки, принадлежащий родителю МЕЖДУ детьми, а не
        # «весь свой текст сначала, потом все дети» — иначе при склейке
        # full_text «1/3» и «lease» слипаются в одно слово без пробела).
        self.parts = []


_VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "area", "base",
              "col", "embed", "source", "track", "wbr"}


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", {})
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs, parent=self._stack[-1])
        self._stack[-1].children.append(node)
        self._stack[-1].parts.append(node)
        if tag not in _VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = _Node(tag, attrs, parent=self._stack[-1])
        self._stack[-1].children.append(node)
        self._stack[-1].parts.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        self._stack[-1].parts.append(data)


def parse(html_text):
    builder = _TreeBuilder()
    builder.feed(html_text)
    return builder.root


def own_text(node):
    """Текст, лежащий непосредственно в узле (не в потомках)."""
    return "".join(p for p in node.parts if isinstance(p, str)).strip()


def full_text(node):
    """Текст узла вместе со всеми потомками, в порядке документа —
    соседние блочные элементы остаются разделены (сохраняем разделяющий
    их текст/перевод строки исходника), а не склеиваются в одно слово."""
    rendered = [p if isinstance(p, str) else full_text(p) for p in node.parts]
    return "".join(rendered)


def walk(node):
    yield node
    for c in node.children:
        yield from walk(c)


def normalize(s):
    """«In Dev» -> «in_dev», «Spec Gate» -> «spec_gate» — сравнение
    человекочитаемой подписи колонки/поля с каноническим именем состояния
    без учёта регистра/пробелов/дефисов."""
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")


def node_state_label(node, canonical=CANONICAL_FSM_STATES):
    """Каноническое состояние, которым подписан ИМЕННО этот узел (по
    собственному тексту, без учёта потомков), либо None."""
    label = normalize(own_text(node))
    return label if label in canonical else None


def find_fsm_board(root, canonical=CANONICAL_FSM_STATES, min_columns=4):
    """Ищет группу «колонок»: общий предок, у которого не менее
    `min_columns` РАЗНЫХ прямых веток (детей) содержат подпись
    канонического состояния FSM — сколь угодно глубоко вложенную (подпись
    может лежать в заголовке внутри колонки, не обязательно в самом узле
    колонки). Возвращает найденный набор состояний либо None.

    Такая проверка отличает настоящий канбан (несколько параллельных
    колонок с разными состояниями под одним контейнером) от случайного
    упоминания имени состояния в прозе карточки/лога."""
    labeled = [(node, node_state_label(node, canonical))
               for node in walk(root)]
    labeled = [(n, lbl) for n, lbl in labeled if lbl is not None]
    if len(labeled) < min_columns:
        return None

    def ancestors(n):
        chain = []
        cur = n
        while cur is not None:
            chain.append(cur)
            cur = cur.parent
        chain.reverse()
        return chain

    # ancestor_id -> {branch_child_id -> {labels}}
    branches_by_ancestor = defaultdict(lambda: defaultdict(set))
    for node, label in labeled:
        chain = ancestors(node)
        for depth in range(len(chain) - 1):
            anc, branch_child = chain[depth], chain[depth + 1]
            branches_by_ancestor[id(anc)][id(branch_child)].add(label)

    for branches in branches_by_ancestor.values():
        distinct_labels = set()
        for lbls in branches.values():
            distinct_labels |= lbls
        if len(branches) >= min_columns and len(distinct_labels) >= min_columns:
            return distinct_labels
    return None


def smallest_matching(root, predicate):
    """Узел с наименьшим по длине текстом (включая потомков), для
    которого predicate(full_text(node)) истинен — «самый сфокусированный»
    блок документа, отвечающий условию. None, если такого нет."""
    best, best_len = None, None
    for node in walk(root):
        text = full_text(node)
        if predicate(text):
            length = len(text)
            if best_len is None or length < best_len:
                best, best_len = node, length
    return best


def looks_like_button(node, label_re):
    if node.tag not in ("button", "a", "input", "div", "span"):
        return False
    role = (node.attrs.get("role") or "").lower()
    cls = (node.attrs.get("class") or "").lower()
    is_button_ish = (
        node.tag in ("button", "input")
        or role == "button"
        or "btn" in cls.split()
        or "button" in cls.split()
        or (node.tag == "a" and node.attrs.get("href"))
    )
    if not is_button_ish:
        return False
    haystacks = [own_text(node)]
    for key in ("value", "aria-label", "title"):
        v = node.attrs.get(key)
        if v:
            haystacks.append(v)
    return any(label_re.search(h) for h in haystacks)
