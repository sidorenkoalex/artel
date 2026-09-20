"""Базовый интерфейс провайдера исполнителя роли (SPEC
01M2ZNTHSNFYSTF904P6SZTPYF, требование 1).

Один адрес на весь пульт для ответа «что нужно исполнителю роли»:
команда шага, окружение процесса, курируемый дом роли, предполётные
проверки, инструмент манифеста и вердикт совместимости модели с
установленным CLI. До этой задачи знание было размазано литералами по
`orchestrator/runner.py`, `orchestrator/stack.py`, `orchestrator/doctor/`
и `orchestrator/catalog.py`; запуск роли на другом CLI начинается с
того, чтобы собрать его сюда.

Модуль держится ЗАВЕДОМО 3.9-совместимым и на уровне модуля не
импортирует ничего, кроме стандартной библиотеки: `orchestrator/stack.py`
собирает `REQUIRED_TOOLS` обращением к реестру провайдеров, а сам
`stack.py` читается точкой входа `orchestrator/artel.py` ДО проверки
версии интерпретатора (SPEC 01M1SHK3MD4ZF9NYXSCT67J8AP, требование 2).
Отсюда же запрет на аннотации вида `X | None` в этом пакете: в 3.9 они
падают TypeError уже при объявлении функции.
"""
from collections import namedtuple

# Инструмент манифеста, объявленный самим провайдером: имя, минимальная
# версия кортежем и команда её проверки. `orchestrator/stack.py`
# переводит это в свою запись `ToolRequirement` — форму манифеста знает
# манифест, а значения знает провайдер.
CliTool = namedtuple("CliTool", "name minimum command")

# Курируемый дом роли: каталог референса в репозитории и имя, под
# которым он разворачивается в `.artel/home` (для `claude` — `claude` ->
# `.claude`, переименование при развёртывании, docs/reference/role-home.md).
HomeReference = namedtuple("HomeReference", "reference deployed_name")


class RoleExecutorProvider(object):
    """Интерфейс исполнителя роли. Реализация — на провайдера.

    Шесть методов требования 1 (`command`, `environment`,
    `home_reference`, `preflight`, `cli_tool`, `model_verdict`) —
    контракт, которым пользуется пульт. Ниже них — составные части
    предполёта: `preflight()` отдаёт ВЕСЬ набор проверок провайдера
    (его читает `doctor.all_checks` по каждой agent-роли), а пошаговый
    предполёт (`doctor.preflight_checks`) собирает из тех же частей
    свой порядок, перемежая их общими проверками пульта (диск, layout
    target'а, git-идентичность). Тела самих проверок живут в
    `orchestrator/doctor/preflight.py` — провайдер объявляет их состав и
    порядок, а не переписывает их заново.
    """

    #: Имя провайдера в реестре (`orchestrator/providers/__init__.py`).
    name = ""

    def command(self, model=None):
        """Argv шага роли. `model` — идентификатор модели роли либо
        `None` (дефолт CLI): аргумент, а не поле объекта, потому что
        модель у каждой роли своя, а провайдер один на пульт."""
        raise NotImplementedError

    def environment(self, role=None, task_id=None):
        """Провайдерская часть окружения процесса роли (дом, конфиг,
        секрет) — словарь ПОВЕРХ общего белого списка манифеста, который
        собирает `runner.role_env`. PATH, метки роли/задачи и
        git-идентичность остаются общими и сюда не входят."""
        raise NotImplementedError

    def home_reference(self):
        """`HomeReference` курируемого дома роли."""
        raise NotImplementedError

    def preflight(self, role):
        """Предполётные проверки провайдера списком `doctor.Check`: CLI
        найден, версия CLI, секрет роли, дом роли."""
        raise NotImplementedError

    def cli_tool(self):
        """`CliTool` — инструмент манифеста стека и его минимальная
        версия."""
        raise NotImplementedError

    def model_verdict(self, model):
        """Вердикт совместимости модели с УСТАНОВЛЕННЫМ CLI
        (`stack.ModelCliVerdict`): `ok`/`warn`/`fail`. Решение о том,
        нужно ли ради этого спрашивать версию CLI, принимает сам
        провайдер — модель вне его таблицы совместимости не стоит
        подпроцесса."""
        raise NotImplementedError

    # --- составные части preflight() -----------------------------------

    def check_cli_found(self):
        """Проверка «CLI найден» (блокирующая)."""
        raise NotImplementedError

    def check_cli_version(self):
        """Проверка «версия CLI» (предупреждение, не блок)."""
        raise NotImplementedError

    def check_token(self, role):
        """Проверка «секрет роли добыт» (блокирующая)."""
        raise NotImplementedError

    def check_home_reference(self):
        """Сверка развёрнутого дома роли с референсом провайдера."""
        raise NotImplementedError

    # --- прочее ---------------------------------------------------------

    def installed_cli_version(self):
        """Установленная версия CLI кортежем; `None` — не определилась."""
        raise NotImplementedError

    def live_smoke_command(self, prompt):
        """Argv минимального живого вызова CLI (`doctor.live_smoke`):
        тот же инструмент, что реально исполняет шаг, но без рабочей
        обвязки шага."""
        raise NotImplementedError
