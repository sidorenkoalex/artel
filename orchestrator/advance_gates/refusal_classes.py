"""Классы отказов перехода из агентских состояний (SPEC
01M446WEVJXARR5CDED8RE9CCR, требование 1): единственный перечень, по
которому цикл `auto` решает, повторить шаг роли или остановиться.

Класс «чинит роль» — недостаток артефакта или кода роли текущего
состояния: `auto` запускает шаг этой роли с отказом в брифе. Класс «чинит
Оператор» — решение, мандат, бюджет, сбой окружения, git, push: `auto`
останавливается с первого отказа. Действие, которого здесь нет (в том
числе будущее), — «чинит Оператор»: неизвестный отказ не жжёт шаг роли.

Модуль намеренно без импортов пакета: его читают `auto.py`, `brief.py`
и `watch.py`, а `brief.py` не может импортировать `auto.py` обратно (цикл
`auto -> fsm -> review -> brief`) — поэтому раньше перечень «роль ещё не
закончила» жил тремя согласованными копиями литералов. Тексты действий
гейтов, объявленные константами в их модулях, повторены здесь литералами;
сверку держит `tests/test_refusal_classes.py`.
"""

ROLE_FIXES = "чинит роль"
OPERATOR_FIXES = "чинит Оператор"

GUARD_REFUSAL_ACTION = "переход отклонён guard'ом"
TREE_NOT_ON_BRANCH_REFUSAL_ACTION = "переход отклонён: дерево не на ветке задачи"
REWORK_REFUSAL_ACTION = "переход отклонён: замечания ревью не отработаны"
# ANSWER Оператора позже последнего шага developer (SPEC
# 01M4KAYMW2YRFB7G0442WFVSHA, требования 1, 5): «чинит роль», но НЕ подкласс
# «роль ещё не закончила» — тот же отказ после шага developer в этом визите
# значит новый ANSWER поверх отработанного, и решает Оператор, не второй шаг.
ANSWER_UNPROCESSED_REFUSAL_ACTION = ("переход отклонён: ANSWER Оператора не "
                                     "отработан developer")
# Аудит SPEC (SPEC 01M4MQAGRWMWR0GFDM9086P3TD, требования 12-13): вердикт
# прошлого визита или чужой роли — роль ещё не закончила; `spec_sha` вердикта
# не тот — чинит аудитор; SPEC сменился за визит — решает Оператор.
SPEC_AUDIT_NOT_FRESH_REFUSAL_ACTION = ("переход отклонён: вердикт аудита SPEC "
                                       "не свежий")
SPEC_AUDIT_SPEC_SHA_REFUSAL_ACTION = ("переход отклонён: spec_sha аудита не "
                                      "равен sha SPEC входа")
SPEC_AUDIT_SPEC_CHANGED_REFUSAL_ACTION = ("переход отклонён: SPEC сменился за "
                                          "визит аудита")

# Подкласс «роль ещё не закончила» класса «чинит роль»: шаг роли
# запускается, но в бриф эти отказы не попадают — роли нечего в них
# читать (`brief.advance_refusal_history`, SPEC 01M290PYPV5T2NFW1Y0HB8BD6E).
# Повтор-остановка «тот же отказ после шага роли — стоп» к ним тоже не
# применяется (решение Оператора, ANSWER-1 задачи 01M446WEVJXARR5CDED8RE9CCR):
# эти отказы значат «артефакта роли на ветке ещё нет», и роль законно
# дописывает его за два шага подряд — ревьювер или developer, получив тот же
# отказ после первого шага, встал бы на полпути. От кружения их держит
# порог холостых шагов `config.AUTO_STALL_STEPS_LIMIT`, как нежурналируемый
# «PLAN.md не ready».
ROLE_NOT_FINISHED_REFUSAL_ACTIONS = (REWORK_REFUSAL_ACTION,
                                     TREE_NOT_ON_BRANCH_REFUSAL_ACTION,
                                     SPEC_AUDIT_NOT_FRESH_REFUSAL_ACTION)

# Действия класса «чинит Оператор», отделённые от прежнего действия того
# же гейта (требование 5): прежний текст остаётся за причиной роли.
BRANCH_UNREAD_REFUSAL_ACTION = "переход отклонён: ветка документов не прочитана"
MUTATION_CLAIM_GIT_REFUSAL_ACTION = ("переход отклонён: гейт заявки мутации — "
                                     "git не ответил")
ACCEPTANCE_CODE_COPY_REFUSAL_ACTION = ("переход отклонён: рабочая копия задачи "
                                       "не готова к приёмке")
LONG_LIVED_GIT_REFUSAL_ACTION = ("переход отклонён: долгоживущие файлы tests/ — "
                                 "git не ответил")

# Честный `FAIL_TO_PASS` на выходе из `tests_writing` и тесты критериев на
# ветке (SPEC 01M5AQH8M2DKBV30NBY86J34A7, требование 11): находки чинит
# test_author, отсутствие теста критерия на ветке — developer, правку SPEC
# после гейта — тот, кто правил; список «провал проверки», подготовку
# прогона и опору SPEC — Оператор.
FAIL_TO_PASS_REFUSAL_ACTION = "переход отклонён: честный FAIL_TO_PASS"
BRANCH_CRITERION_REFUSAL_ACTION = ("переход отклонён: приёмочные тесты — тест "
                                   "критерия не в отчёте")
SPEC_CHANGED_AFTER_GATE_REFUSAL_ACTION = ("переход отклонён: SPEC изменён после "
                                          "гейта SPEC")
NO_FAILURE_ERRORS_REFUSAL_ACTION = ("переход отклонён: честный FAIL_TO_PASS — "
                                    "список «провал проверки» не задан")
FAIL_TO_PASS_PREPARE_REFUSAL_ACTION = ("переход отклонён: честный FAIL_TO_PASS — "
                                       "отказ подготовки")
SPEC_ANCHOR_REFUSAL_ACTION = ("переход отклонён: честный FAIL_TO_PASS — опора "
                              "SPEC не найдена")

# Гейт неослабления по исходам (SPEC 01M5CJVB5B5V55PQQVR2QRHWZN, требование
# 6): только «сломан правкой» чинит developer; нестабильность, исчезновение,
# пропуски и подготовка прогона — решение или окружение Оператора.
OUTCOME_INTEGRITY_REFUSAL_ACTION = "переход отклонён: гейт неослабления по исходам"
OUTCOME_BROKEN_REFUSAL_ACTION = ("переход отклонён: гейт неослабления по "
                                 "исходам — сломан правкой")
OUTCOME_PREPARE_REFUSAL_ACTION = ("переход отклонён: гейт неослабления по "
                                  "исходам — подготовка")
# Тот же гейт на гейте мержа (SPEC 01M5DDTVZEA40ZB9BHEH4YDEE7, требование 4):
# находка без мандата — эскалация, решение Оператора.
OUTCOME_MERGE_REFUSAL_ACTION = "merge отклонён: гейт неослабления по исходам"
OUTCOME_MERGE_PREPARE_ACTION = f"{OUTCOME_MERGE_REFUSAL_ACTION} — подготовка"

# Таблица «Перечень отказов» SPEC: действие журнала -> класс.
REFUSAL_CLASSES = {
    GUARD_REFUSAL_ACTION: ROLE_FIXES,
    TREE_NOT_ON_BRANCH_REFUSAL_ACTION: ROLE_FIXES,
    REWORK_REFUSAL_ACTION: ROLE_FIXES,
    ANSWER_UNPROCESSED_REFUSAL_ACTION: ROLE_FIXES,
    SPEC_AUDIT_NOT_FRESH_REFUSAL_ACTION: ROLE_FIXES,
    SPEC_AUDIT_SPEC_SHA_REFUSAL_ACTION: ROLE_FIXES,
    "переход отклонён: защищённый путь": ROLE_FIXES,
    "переход отклонён: гейт зон — мандат есть, раздел PLAN не оформлен": ROLE_FIXES,
    "переход отклонён: приложение PLAN неприменимо": ROLE_FIXES,
    "переход отклонён: гейт заявки мутации": ROLE_FIXES,
    "переход отклонён: приёмочные тесты": ROLE_FIXES,
    "переход отклонён": ROLE_FIXES,
    "переход отклонён: код сменился после вердикта": ROLE_FIXES,
    "переход отклонён: реестр замечаний": ROLE_FIXES,
    "переход отклонён: трассируемость AC": ROLE_FIXES,
    "переход отклонён: посторонние файлы планки": ROLE_FIXES,
    "переход отклонён: группы приёмочных тестов": ROLE_FIXES,
    "переход отклонён: долгоживущие файлы tests/": ROLE_FIXES,
    "переход отклонён: планка читает артефакты с диска": ROLE_FIXES,
    "переход отклонён: планка не собирается": ROLE_FIXES,
    FAIL_TO_PASS_REFUSAL_ACTION: ROLE_FIXES,
    BRANCH_CRITERION_REFUSAL_ACTION: ROLE_FIXES,
    SPEC_CHANGED_AFTER_GATE_REFUSAL_ACTION: ROLE_FIXES,
    OUTCOME_BROKEN_REFUSAL_ACTION: ROLE_FIXES,

    BRANCH_UNREAD_REFUSAL_ACTION: OPERATOR_FIXES,
    NO_FAILURE_ERRORS_REFUSAL_ACTION: OPERATOR_FIXES,
    FAIL_TO_PASS_PREPARE_REFUSAL_ACTION: OPERATOR_FIXES,
    SPEC_ANCHOR_REFUSAL_ACTION: OPERATOR_FIXES,
    MUTATION_CLAIM_GIT_REFUSAL_ACTION: OPERATOR_FIXES,
    ACCEPTANCE_CODE_COPY_REFUSAL_ACTION: OPERATOR_FIXES,
    LONG_LIVED_GIT_REFUSAL_ACTION: OPERATOR_FIXES,
    OUTCOME_INTEGRITY_REFUSAL_ACTION: OPERATOR_FIXES,
    OUTCOME_PREPARE_REFUSAL_ACTION: OPERATOR_FIXES,
    OUTCOME_MERGE_REFUSAL_ACTION: OPERATOR_FIXES,
    OUTCOME_MERGE_PREPARE_ACTION: OPERATOR_FIXES,
    SPEC_AUDIT_SPEC_CHANGED_REFUSAL_ACTION: OPERATOR_FIXES,
    "переход отклонён: результат шага не закоммичен": OPERATOR_FIXES,
    "переход отклонён: рабочая копия артефактов грязная": OPERATOR_FIXES,
    "переход отклонён: лок приёмочных тестов": OPERATOR_FIXES,
    "переход отклонён: перечень долгоживущих тестов": OPERATOR_FIXES,
    "переход отклонён: посторонние файлы в worktree": OPERATOR_FIXES,
    "переход отклонён: планка не найдена в источнике": OPERATOR_FIXES,
    "переход отклонён: перечень долгоживущих файлов не прочитан": OPERATOR_FIXES,
    "переход отклонён: гейт ёмкости diff": OPERATOR_FIXES,
    "переход отклонён: гейт зон": OPERATOR_FIXES,
    "переход отклонён: гейт приложений PLAN": OPERATOR_FIXES,
    "переход отклонён: гейт неослабления тестов": OPERATOR_FIXES,
    "переход отклонён: голова не в origin": OPERATOR_FIXES,
    "переход отклонён: рабочая копия задачи не заведена": OPERATOR_FIXES,
    # `project_profile.REFUSAL_ACTION`: чинится targets.yaml (SPEC
    # 01M45FJVGQT1K0P8HDEXZX6HS7, требования 4-5).
    "переход отклонён: профиль тестов проекта": OPERATOR_FIXES,
    ("переход отклонён: фиксация не обновлена: голова ссылки документов "
     "не прочитана"): OPERATOR_FIXES,
}


def refusal_class(action: str) -> str:
    """Класс отказа по действию журнала; действия нет в перечне —
    «чинит Оператор» (требование 1)."""
    return REFUSAL_CLASSES.get(action, OPERATOR_FIXES)
