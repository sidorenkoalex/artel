"""Реестр провайдеров исполнителя роли (SPEC
01M2ZNTHSNFYSTF904P6SZTPYF, требование 4).

Регистрация нового провайдера — запись в словарь `PROVIDERS`, не правка
ветвления в вызывающем коде. Имя провайдера роли читается из
`roles.yaml` (`orchestrator/roles.py::provider`); имени, которого нет в
реестре, соответствует именованный отказ `run`/`auto` до старта агента
и красная строка `doctor` — не тихий откат на провайдера по умолчанию.

На уровне модуля пакет тянет только стандартную библиотеку и себя же:
`orchestrator/stack.py` импортирует реестр, чтобы собрать
`REQUIRED_TOOLS`, а сам читается точкой входа до проверки версии
интерпретатора (см. докстринг `base.py`).
"""
from .base import (CliTool, EMPTY_EVENT, FailureSignature, HomeReference,
                   RoleExecutorProvider, RunResult, StreamEvent, ToolCall,
                   ToolResult)
from .claude import ClaudeProvider
from .codex import CodexProvider

#: Провайдер роли, у которой поле `provider:` в `roles.yaml` не задано.
DEFAULT_PROVIDER = "claude"

#: Реестр: имя провайдера -> реализация интерфейса `RoleExecutorProvider`.
#: Значения — готовые экземпляры: провайдер не несёт состояния шага, а
#: подмена его метода в тесте (`mock.patch.object(ClaudeProvider, ...)`)
#: видна всем держателям этого экземпляра.
#:
#: Запись в этом словаре НЕ делает инструмент провайдера обязательным
#: для пульта (SPEC 01M32NH6P053978AER66P0X4GN, требование 6): манифест
#: стека держит инструменты провайдеров, кроме провайдера по умолчанию,
#: необязательными и спрашивает их ровно тогда, когда ярус хотя бы одной
#: agent-роли разрешается в модель такого провайдера
#: (`orchestrator/stack.py::required_tools`). Пульт без Codex проходит
#: `doctor` и запускает роли на Claude как до регистрации.
PROVIDERS = {
    DEFAULT_PROVIDER: ClaudeProvider(),
    CodexProvider.name: CodexProvider(),
}


class UnknownProviderError(Exception):
    """Имя провайдера не зарегистрировано в `PROVIDERS`."""


def get(name):
    """Провайдер по имени. `UnknownProviderError` — имени нет в реестре."""
    try:
        return PROVIDERS[name]
    except KeyError:
        raise UnknownProviderError(
            f"провайдер {name} не зарегистрирован "
            f"(известны: {', '.join(sorted(PROVIDERS))})") from None


def default():
    """Провайдер по умолчанию — им идёт роль без поля `provider:`."""
    return get(DEFAULT_PROVIDER)


def or_default(provider=None):
    """`provider`, если он передан, иначе провайдер по умолчанию.

    Один адрес деградации для всех точек разбора вывода (SPEC
    01M31ZHSA6HMH40C2JTDPQJQNZ, требование 3): провайдера им передаёт
    шаг (`runner` — `for_role(role)`), но те же функции зовут и вне
    шага — живой смок `doctor`, разбор лога руками, тесты. Три копии
    тернарника по трём модулям разошлись бы на первой же правке
    умолчания.
    """
    return provider if provider is not None else default()


def name_for_role(role):
    """Имя провайдера роли из `roles.yaml`; `role is None` — провайдер
    по умолчанию (`runner.role_env()`/`doctor` зовут сборку окружения
    без роли). Карта исполнителей нечитаема или роль в ней не описана —
    тоже провайдер по умолчанию: нечитаемый `roles.yaml` останавливает
    шаг раньше и по своей, названной причине (`runner.
    _refuse_before_start` читает скилы и модель роли), а подменять её
    здесь трейсбеком из сборки окружения незачем — тот же приём
    защитной деградации, что у `runner._resolved_role_model`.
    """
    if role is None:
        return DEFAULT_PROVIDER
    from .. import roles
    try:
        return roles.provider(role)
    except roles.RolesError:
        return DEFAULT_PROVIDER


def for_role(role):
    """Провайдер роли. `UnknownProviderError` несёт имя провайдера И
    имя роли: отказ шага обязан называть, что именно чинить."""
    name = name_for_role(role)
    try:
        return get(name)
    except UnknownProviderError:
        raise UnknownProviderError(
            f"провайдер {name} роли {role} не зарегистрирован "
            f"(известны: {', '.join(sorted(PROVIDERS))})") from None


def role_providers(role_names):
    """[(роль, имя провайдера)] в порядке `role_names` — карта «кто на
    чём идёт» для вывода `doctor`. Имя не резолвится в объект: строка
    печатается и для незарегистрированного имени, иначе Оператор не
    увидел бы, что именно стоит у роли.

    Карта исполнителей читается БЕЗ защитной деградации
    `name_for_role`: `RolesError` уходит вызывающему (REVIEW.md итерации
    1, R1-F2). Деградация уместна на пути сборки окружения, где шаг и
    так остановится раньше по своей причине, но здесь предмет — сама
    карта: подставив `DEFAULT_PROVIDER` молча, диагностика утверждала бы
    прочитанным файл, которого не читала, и «прочитал, и там claude»
    стало бы неотличимо от «не смог прочитать».
    """
    from .. import roles
    return [(role, roles.provider(role)) for role in role_names]


def cli_tools():
    """{имя инструмента: `CliTool`} по всем зарегистрированным
    провайдерам — вход манифеста стека (`stack.REQUIRED_TOOLS`)."""
    return {provider.cli_tool().name: provider.cli_tool()
            for provider in PROVIDERS.values()}


def home_references():
    """`HomeReference` всех зарегистрированных провайдеров — вход
    развёртывания дома роли (`catalog._deploy_role_home_reference`)."""
    return [provider.home_reference() for provider in PROVIDERS.values()]
