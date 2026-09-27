# Импорт: «Интеграция агентов Артели» (сессия ChatGPT, 22.09.2026)

Дата разговора: 22.09.2026, 23:07. Импортирован 26.09.2026 из ChatGPT
(разговор «Интеграция агентов Артели», проект artel). Тип: исследование,
не решение — это внешний брейншторм, решений Оператора по нему нет,
код не менялся.

Контекст: разбор плагина Brewcode (механизм `teams-setup`: анализ
репозитория, выделение доменов, создание доменных агентов в
`.claude/agents/`, их `upgrade` по накопленным трассам) и вопрос, как
перенести идею динамически конфигурируемых доменных архитекторов в
Артель: базовые роли в пульте, специфичные в `.artel`, или все
в `.artel`.

Что предложено (кратко):

1. Пульт хранит архетипы ролей (библиотека профессий), `.artel` —
   организационную структуру конкретного проекта: `.artel/domains/`
   описывают домены и политику участия, `.artel/agents/` — материализованные
   доменные архитекторы (`agent = archetype + domain + repo context +
   project rules`). Двух независимых наборов агентов не заводить.
2. Отдельный механизм «куратор агентов»: операции DISCOVER / CREATE /
   EVOLVE / REFACTOR (split, merge, retire) по топологии доменов и
   истории выполнения; со временем меняет и состав, и частоту участия.
3. Доменный архитектор подключается не по желанию менеджера, а по типу
   изменения: три уровня задач (L1 локальное, L2 внутри домена,
   L3 кросс-доменное), четыре точки входа (DISCOVER, DESIGN, REVIEW,
   ESCALATION), степени участия NONE / ADVISORY / REQUIRED / GATE.
4. Конвейер — не линейная цепочка ролей, а граф исполнения задачи, к
   узлам которого подключаются роли; замкнутый цикл «репозиторий →
   команда → выполнение → трасса → пересмотр команды и политик».

Ревью предложения (26.09.2026) — раздел «Ревью» в конце файла, после
транскрипта: сверка с кодом пульта, ADR и инвариантами, проверка
утверждений о Brewcode по файлам плагина 6.2.0, оценка реализуемости
и стоимости, список аномалий и практик, которые стоит взять.

Итог обсуждения (27.09.2026) — раздел «Итог обсуждения» в конце
файла: ответ на вопрос «можно ли интегрировать и в каком виде», анализ
пользы доменных агентов со стороны агента, раскладка в репозитории,
распределение между пультом и целевым проектом, подключение домена
и архитектора посреди шага конвейера.

Оговорки импорта: текст ответов ChatGPT перенесён дословно, включая
рисунки; ссылки-цитаты на документацию Brewcode из текста удалены
(в оригинале они стояли после абзацев про Brewcode). Терминология
источника (Manager, Architect, Router, Curator, `.artel/domains`)
не сверялась с текущим кодом пульта и `roles.yaml`; сопоставление —
отдельная работа.

---

## Оператор

проанализируй brewcode плагин и нашу систему агентов
интересна концепция динамического конфигурирования доменных архитекторов
как можно интегрировать в артель? чтобы при подключении их конфигурировать и пересматривать/создавать новых, можно ли иметь базавых в пульте а специфичных в .artel ? или всех в .artel ?

## ChatGPT

Да. Я бы **не переносил модель Brewcode 1:1**, а забрал из неё механизм «агентная команда как живой слой проекта» и встроил его в Артель.

В Brewcode это уже довольно хорошо оформлено: `teams-setup` анализирует репозиторий, выделяет домены, предлагает состав domain-specific агентов, создаёт их и потом умеет `upgrade` на основании накопленного `trace.jsonl`. При этом проектные агенты лежат непосредственно в `.claude/agents/`, а роутер предпочитает их generic/plugin-агентам.

#### Как бы я сделал в Артели

Я бы разделил **архетипы агентов** и **конкретных агентов проекта**:

```text
                   ARTEL CONTROL PLANE
                   ───────────────────
                  Agent Archetype Registry
                         │
        ┌────────────────┼────────────────┐
        │                │                │
 Backend Architect   Data Architect   DevOps Architect
        │                │                │
        └────────────────┼────────────────┘
                         │
                  Project bootstrap
                         │
                         ▼
              анализ конкретного repo
                         │
              Domain Discovery / Review
                         │
                         ▼
                    .artel/
              ┌──────────┴──────────┐
              │                     │
        agents/architects/      domains/
              │                     │
     pricing-architect.md      pricing.yaml
     rnd-architect.md          forecasting.yaml
     quality-architect.md      quality.yaml
```

То есть **в Пульте — не готовые доменные архитекторы проекта, а базовые архетипы**.

Например:

```text
Пульт
├── software-architect
├── backend-architect
├── data-architect
├── integration-architect
├── security-architect
└── devops-architect
```

А:

```text
.artel/agents/
├── pricing-architect
├── forecasting-architect
├── quality-architect
├── rnd-architect
└── commerce-architect
```

— уже конкретные архитекторы этого проекта.

Это, на мой взгляд, принципиально важное разделение.

#### Почему не держать всех в Пульте

Представим вашу платформу готовой еды.

`pricing-architect` должен знать не просто:

> Ты архитектор Python/backend.

А примерно:

```yaml
name: pricing-architect

extends:
  - backend-architect

owns:
  - pricing
  - cost-calculation

context:
  - src/pricing/**
  - src/cost/**
  - docs/domain/pricing/**
  - .artel/domains/pricing.yaml

responsibilities:
  - pricing model
  - cost calculation
  - price recalculation
  - pricing events
  - pricing API boundaries

dependencies:
  - forecasting
  - rnd
  - commerce
```

Такой агент **не универсален**. В другом проекте `pricing` может вообще отсутствовать.

Поэтому хранить его централизованно — неправильная абстракция.

---

### Но здесь я бы пошёл дальше Brewcode

Самая интересная часть — **не создание агентов при bootstrap, а их lifecycle**.

Brewcode уже движется именно в эту сторону: `teams-setup upgrade` оценивает здоровье агентов, условно деля их на Green/Yellow/Red; инструкции можно менять, а при неправильной базовой роли агент фактически пересоздаётся.

Для Артели я бы сделал отдельный механизм:

```text
Domain Architect Manager
```

или более общо:

```text
Agent Curator
```

Он работает примерно так:

```text
                   ┌───────────────┐
                   │ Agent Curator │
                   └───────┬───────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
          CODE          .artel/        HISTORY
       structure        config         traces
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                   Domain topology
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
           KEEP          UPDATE         CREATE
         architect      architect      architect
```

И вот это уже превращает систему из статического набора промптов в **самоконфигурирующуюся агентную организацию**.

#### Как выглядел бы цикл

При первом подключении проекта:

```text
artel init
      ↓
repo scanner
      ↓
domain discovery
      ↓
architecture map
      ↓
existing agent matching
      ↓
proposal
```

Например:

```text
Detected domains:

Commerce
Forecasting
Quality
Pricing / Cost
RnD
Shared Platform

Suggested architects:

+ commerce-architect
+ forecasting-architect
+ quality-architect
+ pricing-architect
+ rnd-architect

Use existing:
= platform-architect

Create 5 agents?
```

Это очень близко к `teams-setup install` Brewcode: там сначала запускается анализ code structure / stack / domain boundaries, затем предлагаются варианты команды и только после подтверждения создаются агенты.

Но Артель может сделать это **на уровне своей модели**, а не Claude-specific `.claude/agents`.

---

### Где должен жить source of truth

Я бы сделал именно так:

```text
Пульт                     Репозиторий
─────────────────         ───────────────────────

Agent Archetypes          .artel/
                          ├── agents/
backend-architect ───────►│   ├── pricing.md
data-architect ──────────►│   ├── forecasting.md
devops-architect ────────►│   └── quality.md
                          │
                          ├── domains/
                          │   ├── pricing.yaml
                          │   └── forecasting.yaml
                          │
                          └── agent-team.yaml
```

**Source of truth конкретной команды — `.artel`.**

Пульт предоставляет:

- archetypes;
- шаблоны;
- capabilities;
- правила;
- schema;
- версии;
- механизм генерации/upgrade.

`.artel` предоставляет:

- конкретные роли;
- ownership;
- границы доменов;
- project-specific instructions;
- зависимости;
- routing;
- overrides.

То есть по смыслу:

```text
agent = archetype + project domain + repo context + project rules
```

Например:

```text
pricing-architect
    =
backend-architect@2.1
    +
pricing domain
    +
repository topology
    +
.artel rules
```

#### И я бы НЕ делал двух независимых наборов агентов

То есть вариант:

```text
Пульт:
backend-architect
pricing-architect

.artel:
pricing-architect
```

быстро приведёт к проблеме precedence.

Вместо этого Пульт содержит **definition/template**, а `.artel` — **instance**:

```yaml
# .artel/agents/pricing-architect.yaml

kind: DomainArchitect

extends:
  control-plane://architects/backend@2

domain: pricing

owns:
  - src/pricing/**
  - src/cost/**

collaborates_with:
  - commerce-architect
  - forecasting-architect

instructions:
  - preserve pricing invariants
  - evaluate impact on cost calculation
  - review pricing schema changes
```

---

### Самое интересное — динамический пересмотр

Я бы добавил:

```bash
artel agents review
```

Он не просто спрашивает «нормальные ли у нас промпты», а повторно строит **domain topology**.

Например, было:

```text
pricing-architect
        │
        ├── pricing
        └── cost
```

Через полгода cost calculation вырос:

```text
cost/
├── ingredients
├── production
├── logistics
├── labor
└── writeoffs
```

Curator обнаруживает:

> `pricing-architect` имеет слишком широкую область ответственности.

И предлагает:

```text
SPLIT

pricing-architect
        │
        ├──────────────┐
        ▼              ▼
pricing-architect   cost-architect
```

И наоборот:

```text
quality-architect
food-safety-architect
```

могут почти всегда работать над одними файлами/задачами.

Тогда:

```text
MERGE candidate:
quality-architect + food-safety-architect
```

Получается уже настоящий **agent organization refactoring**.

---

### А ещё лучше — не привязывать это только к `architect`

Я бы ввёл понятие:

```text
Domain Cell
```

Например:

```text
Pricing
│
├── pricing-architect
├── pricing-developer
├── pricing-reviewer
└── pricing-tester
```

Но при этом физически необязательно создавать четыре markdown-файла сразу.

Domain descriptor:

```yaml
# .artel/domains/pricing.yaml

domain: pricing

ownership:
  - src/pricing/**
  - src/cost/**

architect:
  agent: pricing-architect

execution:
  developer: backend-developer

review:
  - pricing-architect
  - backend-reviewer

testing:
  agent: backend-tester
```

И это как раз хорошо ложится на нашу прежнюю модель **manager → architect → developer → tester/reviewer**, но добавляет поверх неё вертикальное измерение — **домен**.

Получается матрица:

|  | Pricing | Forecasting | Quality |
|---|---|---|---|
| Architect | специфичный | специфичный | специфичный |
| Developer | общий | общий/ML | общий |
| Tester | общий | общий | общий |
| Reviewer | общий + architect | общий + architect | общий + architect |

И **не надо плодить 20 агентов**, как это довольно легко происходит в Brewcode Maximum team, где предусмотрено 15–20 domain agents.

---

### Поэтому для Артели я бы выбрал гибрид

**Пульт = библиотека профессий. `.artel` = организационная структура конкретного проекта.**

Причём динамическими в первую очередь сделать именно **domain architects**, потому что архитектурная роль сильнее всего зависит от bounded context проекта.

Я бы заложил четыре операции:

```text
DISCOVER
найти новые/изменившиеся домены

CREATE
создать domain architect из archetype

EVOLVE
обновить ownership/context/instructions существующего

REFACTOR
split / merge / retire архитекторов
```

И lifecycle:

```text
               ┌──────────────┐
               │  ARTEL PULT  │
               │  Archetypes  │
               └──────┬───────┘
                      │ instantiate
                      ▼
┌──────────┐    ┌──────────────┐
│   Repo   │───►│Domain Scanner│
└──────────┘    └──────┬───────┘
                       ▼
                Domain Topology
                       │
                       ▼
                 Agent Curator
                  /    |    \
                 /     |     \
             create  evolve  retire
                \      |      /
                 ▼     ▼     ▼
                    .artel
                       │
                Agent Registry
                       │
                       ▼
                    Router
                       │
             ┌─────────┼─────────┐
             ▼         ▼         ▼
          Manager   Architect  Developer
```

И тут есть ещё одна полезная идея из Brewcode: их router перехватывает generic spawn, когда видит, что задача явно принадлежит project/domain agent.  В Артели это стоит сделать **нативной частью router**, а не hook'ом конкретного Claude Code.

Например задача:

> Изменить алгоритм расчёта себестоимости блюда.

Router:

```text
semantic task classification
        ↓
domain = pricing/cost
        ↓
.artel/domains/cost.yaml
        ↓
owner = cost-architect
        ↓
manager → cost-architect → backend-developer
```

#### Итоговая модель

Я бы **не выбирал «базовые в Пульте или все в `.artel`» как взаимоисключающие варианты**.

Правильнее:

**Пульт**
→ `architect archetypes`

**`.artel/domains`**
→ описание реальных доменов проекта

**`.artel/agents`**
→ материализованные project-specific architects

**Artel Curator**
→ обнаруживает необходимость `create/update/split/merge/retire`

**Artel Router**
→ выбирает нужного архитектора по domain ownership.

Это, на мой взгляд, может стать одной из сильных концепций Артели: **не пользователь вручную проектирует «зоопарк агентов», а Артель строит и со временем рефакторит агентную организацию под архитектуру конкретной кодовой базы**. Brewcode уже подтверждает жизнеспособность отдельных частей этой идеи (`teams-setup`, health/upgrade, project agents, router), но у нас можно поднять это на уровень выше — от управления файлами агентов к управлению **моделью доменов и ролей**.

## Оператор

хорошо, давай еще рассмотрим участие уже сформированных агентов в конвеере - какие этапы, связи. когда кто может подключаться

## ChatGPT

Да. Если принять предыдущую модель — **доменные архитекторы уже сформированы в `.artel`**, — то я бы не делал их просто «консультантами, которых Manager иногда вызывает». Они должны стать частью маршрутизации pipeline.

У Brewcode есть полезная основа: Manager сначала строит полный task graph, назначает подходящих агентов и передаёт каждому ограниченный контекст; отдельно architecture-first режим требует проектирования до написания кода.  В Артели это можно сделать более системно: **доменный архитектор подключается не по желанию Manager, а по типу изменения и ownership домена.**

### 1. Я бы видел pipeline так

```text
                        USER TASK
                            │
                            ▼
                    ┌───────────────┐
                    │    MANAGER    │
                    │ orchestration │
                    └───────┬───────┘
                            │
                    ① CLASSIFICATION
                            │
                            ▼
                    ┌───────────────┐
                    │ DOMAIN ROUTER │
                    └───────┬───────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
           Pricing      Forecasting      Platform
              │             │              │
              ▼             ▼              ▼
          Architect     Architect      Architect
              └─────────────┼──────────────┘
                            │
                     ② ARCHITECTURE
                            │
                            ▼
                       TASK GRAPH
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
             Backend       Data       DevOps
            Developer    Developer    Developer
                │           │           │
                └───────────┼───────────┘
                            │
                       ③ EXECUTION
                            │
                            ▼
                     ④ VERIFICATION
                    /       │        \
                   /        │         \
              Tester    Reviewer   Architect
                   \        │         /
                    └───────┼────────┘
                            ▼
                       ⑤ INTEGRATE
                            │
                            ▼
                         Manager
```

Но важный момент: **Architect не обязан участвовать во всех задачах.**

Иначе получим дорогой и медленный конвейер.

---

### 2. Три уровня задачи

Router после первичного анализа определяет `change level`.

#### L1 — локальное изменение

Например:

> Добавить поле `description` в response DTO.

```text
Manager
   ↓
Developer
   ↓
Tests
   ↓
Reviewer
```

Архитектор вообще не нужен.

---

#### L2 — изменение внутри домена

Например:

> Добавить новый способ расчёта скидки.

```text
Manager
   ↓
Domain Router
   ↓
pricing-architect
   │
   └── design constraints
          ↓
      Developer
          ↓
       Tester
          ↓
      Reviewer
          ↓
pricing-architect ← optional verification
          ↓
       Manager
```

Здесь архитектор нужен **до реализации**, потому что изменение затрагивает бизнес-инварианты.

---

#### L3 — cross-domain / architectural

Например:

> Пересчитывать себестоимость после изменения прогноза спроса.

Уже:

```text
             Manager
                │
                ▼
         Change Analyzer
                │
        ┌───────┴────────┐
        ▼                ▼
 Forecasting         Cost/Pricing
 Architect            Architect
        │                │
        └───────┬────────┘
                ▼
        Architecture synthesis
                │
                ▼
            Task Graph
         /       |       \
        ▼        ▼        ▼
 Forecast BE   Cost BE   Event/Infra
        │        │        │
        └────────┼────────┘
                 ▼
              Tests
                 ▼
          Cross-domain review
                 │
        ┌────────┴─────────┐
        ▼                  ▼
 Forecast Architect   Cost Architect
        └────────┬─────────┘
                 ▼
              Manager
```

Вот здесь доменные архитекторы становятся особенно полезны.

---

### 3. Я бы дал архитектору четыре точки входа

Не просто:

```text
architect → developer
```

А:

```text
             ┌── DISCOVER
             │
             ├── DESIGN
Architect ───┤
             ├── REVIEW
             │
             └── ESCALATION
```

#### ① DISCOVER

До построения task graph.

Архитектор отвечает:

> Что эта задача означает для моего домена?

Например `pricing-architect` возвращает:

```yaml
domain: pricing

affected:
  - CostCalculation
  - PriceRecalculation

invariants:
  - published price cannot mutate retroactively
  - recalculation must be idempotent

dependencies:
  - forecasting

risk: medium

architecture_required: true
```

Manager получает это **до декомпозиции**.

Это важно: архитектор помогает Manager понять, **какие вообще задачи надо создать**.

---

### 4. DESIGN — архитектор проектирует, но не реализует

Здесь я бы провёл довольно жёсткую границу.

```text
Architect owns:
─────────────────────────
domain boundaries
contracts
invariants
data ownership
integration decisions
interfaces
events
migration strategy

Developer owns:
─────────────────────────
implementation
code
unit tests
local refactoring
technical details
```

То есть архитектор выдаёт не код, а `Architecture Decision / Implementation Contract`.

Например:

```yaml
decision:
  producer: forecasting
  event: DemandForecastUpdated

consumer:
  domain: cost
  handler: RecalculateCost

delivery:
  semantics: at-least-once

requirements:
  idempotency: required

data:
  pass:
    - product_id
    - forecast_version

  do_not_pass:
    - calculated_cost
```

И дальше Developer работает **внутри этих ограничений**.

Это снижает шанс, что каждый разработчик начнёт самостоятельно переизобретать архитектуру.

---

### 5. Самое интересное — несколько архитекторов

Я бы не делал:

```text
Manager
 ↓
Architect A
 ↓
Architect B
 ↓
Developer
```

Это плохо масштабируется.

Лучше fan-out/fan-in:

```text
                  Manager
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Pricing   Forecasting   Platform
      Architect   Architect   Architect
          │          │          │
          └──────────┼──────────┘
                     ▼
             Architecture Merge
                     │
                     ▼
                 Task Graph
```

Каждый отвечает **только за свой bounded context**.

Например:

**Forecasting architect**

> После публикации ForecastVersion создаём immutable event.

**Pricing architect**

> Мне достаточно `product_id + forecast_version`; стоимость внутри события передавать нельзя.

**Platform architect**

> Используем существующий Kafka topic, новый transport abstraction не создаём.

После этого Manager/специальный `Architecture Synthesizer` собирает решение.

---

### 6. Я бы даже не создавал отдельного Synthesizer сначала

На первом этапе это вполне может делать Manager.

```text
Architect A ─┐
Architect B ─┼──► Manager ──► consolidated design
Architect C ─┘
```

Если потом увидим, что архитектурные конфликты занимают много контекста:

```text
Architects
    ↓
Architecture Coordinator
    ↓
Manager
```

То есть **не плодить агента заранее**.

---

### 7. REVIEW — архитектор возвращается после реализации

Вот это я считаю особенно важным.

Обычный reviewer проверяет:

```text
correctness
quality
tests
conventions
security
```

Domain architect проверяет другое:

```text
architecture compliance
domain invariants
boundary violations
contract compliance
unwanted coupling
```

То есть:

```text
                     IMPLEMENTATION
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          Reviewer       Tester     Domain Architect
              │            │            │
              ▼            ▼            ▼
         code quality    behavior     architecture
              └────────────┼────────────┘
                           ▼
                        Manager
```

Это **не три одинаковых code review**.

У каждого своя ось.

У Brewcode уже используется идея независимого параллельного review несколькими агентами с последующим объединением результатов; Artel может применить аналогичный fan-out не просто для поиска багов, а для разных типов контроля.

---

### 8. ESCALATION — Developer сам может вызвать архитектора

Это тоже обязательно.

Pipeline не должен быть строго сверху вниз.

Допустим Developer обнаружил:

> Чтобы сделать задачу, надо нарушить заявленный контракт.

Он не должен сам принимать решение.

```text
Developer
    │
    │ architecture conflict
    ▼
Domain Architect
    │
    ├── clarify
    ├── change design
    └── escalate cross-domain
```

Например:

```text
Developer
   ↓
pricing-architect
   ↓
"это затрагивает forecasting"
   ↓
Manager
   ↓
pricing-architect + forecasting-architect
   ↓
updated decision
   ↓
Developer
```

То есть появляется **обратная связь**, а не waterfall.

---

### 9. Тогда полный pipeline Artel получается таким

```text
USER
 │
 ▼
MANAGER
 │
 ├── Understand request
 │
 ▼
CHANGE ANALYSIS
 │
 ├── affected domains
 ├── complexity
 ├── architectural impact
 └── risk
 │
 ▼
DOMAIN ROUTER
 │
 ├─────────────┬──────────────┐
 ▼             ▼              ▼
Architect A  Architect B   Architect N
 │             │              │
 └─────────────┼──────────────┘
               ▼
      ARCHITECTURE DECISION
               │
               ▼
           TASK GRAPH
               │
       ┌───────┼────────┐
       ▼       ▼        ▼
      Dev     Dev      Dev
       │       │        │
       │    ◄──┴──► Architect
       │        escalation
       │
       ▼
        IMPLEMENTATION
               │
       ┌───────┼─────────┐
       ▼       ▼         ▼
     Tester  Reviewer  Architect
       │       │         │
       └───────┼─────────┘
               ▼
          FIX / RETRY
               │
               ▼
            MANAGER
               │
               ▼
           INTEGRATION
```

---

### 10. А теперь связать это с `.artel`

Вот здесь предыдущая концепция начинает реально работать.

```yaml
# .artel/domains/pricing.yaml

domain: pricing

architect:
  agent: pricing-architect

ownership:
  - src/pricing/**
  - src/cost/**

triggers:

  design:
    - schema_change
    - business_rule_change
    - public_contract_change
    - integration_change

  review:
    - cross_domain_change
    - invariant_change
    - architecture_change

  escalation:
    always: true
```

А для какого-нибудь простого домена:

```yaml
domain: notifications

architect:
  agent: notifications-architect

triggers:
  design:
    - architecture_change

  review:
    - architecture_change
```

Получается **не просто список агентов, а политика их участия**.

---

### 11. Более того — Curator может менять эти политики

И тут соединяются две наши идеи.

Допустим Artel видит:

```text
pricing-architect

last 30 tasks:
────────────────────────
invoked:             27
useful decisions:    24
architecture fixes:   8
```

→ архитектор явно полезен.

А:

```text
notification-architect

last 30 tasks:
────────────────────────
invoked:             19
useful decisions:     1
architecture fixes:   0
```

Curator может предложить:

```text
BEFORE

notifications:
    architect.design: domain_change


AFTER

notifications:
    architect.design: architecture_change
```

То есть динамически оптимизируется **не только состав команды, но и частота участия агентов**.

Это уже интереснее Brewcode.

---

### 12. Я бы ещё разделил обязательное и консультативное участие

Например:

```text
NONE
не вызываем

ADVISORY
можно вызвать

REQUIRED
pipeline не идёт дальше без ответа

GATE
архитектор должен approve результат
```

Тогда задача может иметь execution plan:

```yaml
architecture:

  pricing:
    pre_design: REQUIRED
    implementation: ADVISORY
    post_review: GATE

  platform:
    pre_design: ADVISORY
    implementation: NONE
    post_review: NONE
```

Это очень мощная штука.

Потому что вместо:

> «Запусти pricing-architect»

Manager получает **машиночитаемую политику orchestration**.

---

### 13. И здесь я бы немного изменил нашу первоначальную модель

Раньше условно:

```text
Manager
   ↓
Architect
   ↓
Developer
   ↓
Tester
   ↓
Reviewer
```

Я бы теперь **отказался от этой линейности**.

Правильнее:

```text
                   MANAGER
                      │
                Task / Change
                      │
                      ▼
                 TASK GRAPH
                      │
         ┌────────────┼────────────┐
         │            │            │
    Architect     Developer      Tester
         ▲            │            │
         │            ▼            │
         └──────── Reviewer ◄───────┘
```

Агенты — **не этапы pipeline**.

Агенты — **роли, подключаемые к узлам task graph**.

Это принципиальное различие.

Например одна задача:

```text
Change pricing formula

ARCHITECT → DEV → TEST → ARCHITECT REVIEW
```

Другая:

```text
Fix typo

DEV → TEST
```

Третья:

```text
Kafka migration

Platform Architect ─┐
                    ├→ DEVOPS → TEST
Pricing Architect ──┘
```

Четвёртая:

```text
Refactor repository class

DEV → REVIEW
```

То есть **pipeline динамически собирается под конкретный change**.

---

### Я бы именно это сделал центральной моделью Artel

Не:

> «У нас есть Manager → Architect → Developer → Reviewer».

А:

> **Artel строит execution graph задачи и динамически назначает сформированных агентов на точки принятия решений, исполнения и контроля.**

Причём `.artel` отвечает сразу на два вопроса:

```text
WHO EXISTS?
────────────────
pricing-architect
forecasting-architect
platform-architect
backend-developer
tester
reviewer


WHEN TO USE?
────────────────
pricing change → pricing architect
cross-domain → all affected architects
local implementation → developer
behavior verification → tester
code quality → reviewer
architecture compliance → architect
```

А Curator, о котором говорили выше, со временем меняет и **WHO**, и **WHEN**.

И вот тогда получается красивая общая архитектура:

```text
                    ┌──────────────────┐
                    │      ПУЛЬТ       │
                    │ Agent Archetypes │
                    └────────┬─────────┘
                             │
                             ▼
REPO ───────────────►  ARTEL CURATOR
                             │
                       creates/evolves
                             ▼
                       .artel/agents
                             │
                             ▼
USER ──► MANAGER ──► CHANGE ANALYZER
                             │
                             ▼
                       DOMAIN ROUTER
                             │
                             ▼
                      EXECUTION GRAPH
                    /      / | \       \
                   ▼      ▼  ▼  ▼       ▼
                 Arch    Dev Test Review Arch
                   \      \  |  /       /
                    └───────┬──────────┘
                            ▼
                         RESULT
                            │
                            ▼
                         TRACE
                            │
                            ▼
                     ARTEL CURATOR
                            │
                      evolve agents
                       + policies
```

То есть замыкается цикл:

**репозиторий → формирование команды → выполнение → накопление опыта → пересмотр команды и правил её подключения → следующее выполнение.**

Вот это я бы уже рассматривал как **ядро agent orchestration Артели**, а не отдельную фичу «доменные архитекторы».

---

# Ревью предложения (26.09.2026)

Тип: ревью ассистентской сессии при Операторе, решений нет. Метод:
три параллельные разведки по коду и документам (`roles.yaml`,
`orchestrator/fsm*.py`, `runner.py`, `brief.py`, `targets.py`,
`projects.py`, `advance_gates/zones.py`, `config.py`, ADR-0003/0005,
`docs/design.md` §2, §4, §10–12, `docs/invariants.md`,
`docs/triggers.md`, `docs/research/2026-09-04-external-target-readiness.md`)
и по файлам плагина Brewcode 6.2.0 в `~/.claude/plugins/cache/`;
стоимость ролей — подсчёт по 156 RETRO в `docs/retro/`.

## 1. Фактическая база, от которой считано ревью

Пульт сегодня:

- Четыре LLM-роли (`analyst`, `test_author`, `developer`, `reviewer`) в
  плоском `roles.yaml` (защищённый путь); поля роли — исполнитель, слот
  токена, список скилов, ярус модели. Архетипов, наследования, зон и
  прав на уровне роли нет; инструменты у всех ролей одинаковые.
- Линейный конечный автомат `spec_writing → spec_gate → tests_writing →
  in_dev → verifying → review → acceptance → merge_gate`; роль на шаг
  задаёт таблица `STATE_ROLE`; ветвления — только пропуск
  `tests_writing`, деление задачи на подзадачи («## Деление» в SPEC)
  и возвраты с лимитами. Параллельных ролей внутри задачи нет
  (design §10: «не параллелить исполнителей внутри задачи»).
- Зоны — свойство задачи, не роли: их объявляет analyst во frontmatter
  SPEC, гейт зон проверяет дифф на `in_dev → verifying`, для внешнего
  target этот гейт сейчас пропускается.
- Эскалация любой роли адресована только Оператору (`answer`), канала
  «роль → роль» нет; единственный канал между ролями — артефакты.
- `.artel/` — рабочий каталог самого пульта вне git (БД, логи,
  worktree, `projects/<target>/…`), а не каталог в целевом
  репозитории. Проектный слой целевого по ADR-0003 — `knowledge/`
  под управлением пульта; `project_skills` и `no_paths` из
  `targets.yaml` объявлены, но кодом не читаются (ТЗ-4 не заведено);
  внешний target пока даже не клонируется (ТЗ-2 не заведено).
- Содержимое целевого репозитория — недоверенные данные: бриф
  оборачивает его маркерами границы, обвязка целевого (`CLAUDE.md`,
  `.claude/`) не наследуется (ADR-0003 п.14).
- Стоимость по 156 RETRO (сумма шагов роли за задачу): analyst медиана
  $1.63, test_author $8.27, developer $11.70, reviewer $4.51; задача
  целиком — медиана $27.7, 80-й перцентиль $46.6, максимум $141.
  Потолок задачи по умолчанию $50, потолок ролей $100 (ADR-0014).

Brewcode 6.2.0 (проверено по файлам плагина):

- `teams-setup` есть; домены выделяет не эвристика, а 3–5 агентов
  Explore, затем модель предлагает варианты через вопрос пользователю;
  агенты создаются в `.claude/agents/` со строгим шаблоном (шесть
  разделов, до 800 токенов), общий контракт — в `.claude/teams/<team>/team.md`.
- `trace.jsonl` пишут сами агенты добровольным вызовом сценария
  (хука нет); записи — `took/refused/completed/failed/issue/insight`.
  `upgrade` классифицирует агентов по доле успеха (Healthy / Needs
  tuning / Underperforming / Inactive; «Green/Yellow/Red» — только в README).
  Токены, время и качество результата не измеряются.
- Роутер — экспериментальный хук PreToolUse на вызов Agent: он не
  подменяет агента, а отклоняет запуск generic-агента с подсказкой
  имени эксперта; работает только в основном цикле, при ошибке
  пропускает вызов. Владение путями (`Owned surfaces`) —
  декларация в тексте агента, принудительной проверки нет.
- Размеры команд: Minimal 5, Balanced 10–12, Maximum 15–20; варианта
  «Standard» нет.

## 2. Оценка по частям предложения

### 2.1. Архетипы в пульте, экземпляры в `.artel` проекта

Реализуемо и полезно в части идеи, ошибочно в части адреса.

- Хорошая практика: разделение «определение (архетип, версия) —
  экземпляр (домен + владение + инструкции)», запрет двух независимых
  наборов ролей. Это совпадает с ADR-0003 3з: кастомизация проекта
  только аддитивная, «проект не может ослабить роль». Формула
  «экземпляр = архетип + домен + контекст репозитория + правила»
  ложится на уже существующие механизмы: архетип = роль `roles.yaml`
  с набором скилов и ярусом; проектная часть = `project_skills`
  (объявлено, не читается) и карта целевого (ADR-0003 п.12,
  не построена).
- Аномалия (главная): в тексте `.artel/` — каталог внутри целевого
  репозитория, «source of truth команды». В пульте `.artel/` — его
  собственный рабочий каталог; целевой репозиторий по ADR-0003 п.1
  и п.14 и по CLAUDE.md — данные, не инструкции. Экземпляр агента,
  лежащий в целевом репозитории и определяющий, кто и с какими
  инструкциями запускается, — это инструкция из недоверенного
  источника. Правильный адрес — `projects/<target>/knowledge/`
  пульта, запись только через гейт Оператора.
- Реализуемость: `roles.yaml` защищён и статичен; динамические
  экземпляры означают, что состав ролей частично становится данными
  (БД или `knowledge/`) и `roles.py` должен склеивать два слоя.
  Умеренная работа, но её предусловия — ТЗ-2 (клон целевого, зоны на
  внешнем target) и ТЗ-4 (чтение проектного слоя). До них доменные
  архитекторы целевого проекта физически не на что опереть.

### 2.2. Куратор агентов (DISCOVER / CREATE / EVOLVE / REFACTOR)

Реализуемо как отчёт с предложениями, не как автоматика.

- Хорошая практика: «куратор предлагает, Оператор решает» — это ровно
  политика реестра триггеров (`docs/triggers.md`) и защищённых путей.
  Куратор ролей — расширение уже сделанного контура К2 (T093:
  дистилляция RETRO и копилки в MR правок скилов) и скила
  `code-revision`, а не новый компонент.
- Аномалия: метрика «useful decisions» неизмерима. В Brewcode она
  самооценка агента в добровольной трассе; в пульте есть данные
  лучше (журнал шагов со стоимостью, вердикты REVIEW, число
  итераций, эскалации), но и они шумные: разброс стоимости задачи
  $27–141, значит для вывода «архитектор домена полезен» нужны
  десятки задач на домен. При текущем потоке это месяцы.
- Автоматический split/merge архитекторов по «слишком широкому
  владению» — умозрителен, данных под него нет; это территория
  policy-движка, который проект сознательно отложил (триггер №4).
- Дисциплина триггеров: design §12 вводит роль архитектора по
  условию «крупные задачи разваливаются на этапе PLAN (лимит
  итераций из-за плохой декомпозиции)». Предложение это условие не
  проверяет. Первый шаг — проверить его по данным, а не строить
  куратора.

### 2.3. Точки входа архитектора, уровни L1–L3, политика участия

Самая ценная часть, но требует перевода на модель пульта.

- Хорошая практика: архитектор участвует не везде; уровень изменения
  решает состав шагов; политика участия NONE / ADVISORY / REQUIRED /
  GATE — машиночитаемые данные. По форме это то же, что `gates.yaml`
  (политика на переход) — расширение существующего файла, а не
  новый механизм.
- Аномалия: «Router классифицирует изменение» — LLM-решение внутри
  оркестратора, что противоречит инварианту 1 («оркестратор не
  думает») и инварианту 25 (решения только по зафиксированным
  артефактам). Перевод: уровень L считается кодом как функция от
  `zones` SPEC и описания доменов (число затронутых доменов:
  0 → L1, 1 → L2, ≥2 → L3). Семантические триггеры вроде
  `business_rule_change` требуют классификации моделью; допустимы
  только путевые триггеры плюс флаг, который analyst явно ставит
  во frontmatter SPEC и проверяет guard.
- GATE «архитектор должен одобрить результат» — новый тип гейта
  «вердикт агента», аналог инварианта 13 (свежий вердикт
  ревьювера). Реализуемо как вторая ось ревью. Дешевле сначала
  сделать её доменным чек-листом внутри существующего шага
  ревьювера (роадмап уже держит «доменные чек-листы ревью» по
  триггеру второго target с другим стеком), чем отдельной ролью.
- ESCALATION «developer сам вызывает архитектора» противоречит
  текущему правилу «адресат эскалации — Оператор» и «канал — только
  артефакт». Переводится в состояние FSM `arch_consult` с числовым
  лимитом (инварианты 3–4): PLAN со статусом escalate и адресатом
  «архитектор» → шаг архитектора → ANSWER-артефакт → возврат в in_dev.
  Это единственная часть, у которой есть измеримая выгода: снятие с
  Оператора части эскалаций (волна T044–T053 — 15 эскалаций на 10
  задач). Сколько из них были архитектурными, а не о требованиях —
  неизвестно; проверяется по QUESTIONS/ANSWER без кода.

### 2.4. Веер архитекторов и граф исполнения вместо конвейера

Отклонить в предложенном виде.

- Противоречит design §10 (данные Anthropic: мультиагентность ≈ 15×
  токенов, плохо для связного кодинга; последовательный конвейер —
  оптимум), design §11 (LangGraph рассмотрен и отклонён в пользу
  тонкого FSM) и инварианту 36 (порядок состояний зафиксирован).
- Потребность не показана: для кросс-доменных изменений в пульте
  уже есть «Деление» на 2–4 подзадачи с собственными зонами и
  замки зон между параллельными задачами. Это и есть L3 в текущей
  модели — последовательно и с учётом стоимости.
- Веер архитекторов на этапе проектирования не так опасен, как веер
  разработчиков (только чтение, артефакт на выходе), но начинать
  нужно с одного архитектора-владельца домена; архитекторы смежных
  доменов — рецензенты его артефакта, не параллельные авторы.
- Аномалия: «на первом этапе синтез делает Manager» — в пульте нет
  LLM-менеджера. Brewcode — интерактивный шаблон одной сессии
  (основная сессия = менеджер, порождает субагентов); пульт —
  пакетный автомат с эфемерными ролями и гейтами Оператора.
  Всё, что в тексте делает Manager, в пульте делят analyst
  (артефакт SPEC) и код FSM.

### 2.5. Роутер, перехватывающий запуск generic-агента

К пульту не применимо: динамического порождения агентов нет, роль на
шаг фиксирована таблицей. «Роутер» пульта — чистая функция «зоны SPEC
× владение доменов → экземпляр архитектора». Тривиально и
детерминированно, без хука и без LLM-судьи.

## 3. Эффективность

- Добавочная стоимость на задаче L2/L3: шаг DISCOVER/DESIGN (чтение и
  короткий артефакт) сопоставим с analyst, $2–5; ось GATE — с
  reviewer, около $4.5. Итого +$5–10 на задачу при медиане $27.7,
  то есть +20–35 % на задачах, где архитектор включён; на L1 — ноль.
- Окупается только если снижает возвраты из ревью, отказы приёмки
  или эскалации Оператору. По ранним задачам фазы A повторных
  итераций ревью не было; главный кандидат на экономию — время
  Оператора на эскалациях, а не токены.
- Куратор по трассам при потоке задач пульта статистически не
  обоснован; в Brewcode он держится на самооценке агентов.
- Предложение вовсе не упоминает бюджеты: у задачи жёсткий потолок
  (инварианты 8–10), калибровочная таблица ADR-0014 потребует строки
  для класса «с архитектором».

## 4. Сводка аномалий

1. `.artel/` в тексте — каталог целевого репозитория; в пульте — свой
   рабочий каталог. Экземпляры ролей в целевом репозитории нарушают
   границу доверия (ADR-0003 п.1, п.14; CLAUDE.md).
2. Manager как LLM-роль против инварианта 1 (оркестратор — код).
3. Граф исполнения вместо FSM против design §10–11 и инварианта 36.
4. Эскалация роль → роль против правила «адресат — Оператор» и
   «канал — артефакт»; решается новым состоянием с лимитом.
5. Метрика полезности неизмерима; трассы Brewcode — самоотчёт.
6. Семантические триггеры участия требуют LLM-классификации.
7. Не учтены существующие механизмы: «Деление», зоны, `gates.yaml`,
   контур К2, скил ревизии, калибровка бюджета.
8. Не учтены бюджеты и потолки.
9. Неточности о Brewcode: роутер не подменяет, а отклоняет и
   подсказывает; владение путями не проверяется; пороги
   Green/Yellow/Red — из README, в скиле иные названия; размера
   «Standard» нет.
10. Не проверено условие триггера design §12 для роли архитектора.

## 5. Практики, которые стоит взять

- Разделение «определение с версией — экземпляр»; один набор ролей,
  проектный слой только аддитивный.
- Политика участия роли как данные, продолжение `gates.yaml`.
- Архитектор выдаёт контракт (инварианты домена, что передавать и
  что не передавать), а не код; его потребители — developer и
  reviewer. Ложится на секцию «Влияние на систему» PLAN (инвариант 17).
- Три оси проверки: качество кода (reviewer), поведение (планка
  приёмки), соответствие архитектуре — третья ось и есть добавка.
- Матрица «специфичен только архитектор, остальные роли общие» —
  защита от разрастания состава.
- Не заводить синтезатора и куратора заранее; система предлагает,
  Оператор решает.

## 6. Рекомендация

- Сейчас, без кода: разобрать прошлые эскалации (QUESTIONS/ANSWER)
  по типу — требования, архитектура, механика пульта. Если
  архитектурных заметная доля, у роли архитектора есть основание по
  триггеру design §12; иначе тема ждёт.
- После ТЗ-2 и ТЗ-4 (фаза B): описание доменов целевого в
  `projects/<target>/knowledge/domains.yaml` (пути владения, экземпляр
  архитектора, политика участия), читаемое пультом; уровень L —
  функция кода от `zones` SPEC; необязательное состояние
  `arch_design` между `spec_gate` и `tests_writing` для L2/L3 с
  артефактом-контрактом; архитектурная ось — доменным чек-листом
  ревьювера.
- По триггеру: состояние консультации developer → архитектор с
  лимитом; раздел куратора в `report`/`doctor` с предложениями по
  составу и политике, применение — Оператором через ADR.
- Не делать в предложенном виде: граф исполнения вместо FSM,
  параллельный веер архитекторов, самопереписывание экземпляров
  агентов, источник истины в целевом репозитории.

---

# Итог обсуждения (27.09.2026)

Тип: вывод ассистентской сессии при Операторе по итогам ревью и
вопросов Оператора 26–27.09. Решений Оператора нет; раздел фиксирует
предлагаемую форму, чтобы из неё можно было писать ТЗ.

## 1. Ответ на исходный вопрос

Архетипы на уровне пульта и доменные архитекторы на уровне
подключённого проекта интегрировать можно, в следующем виде.

- Архетип — обычная роль `architect` в `roles.yaml` пульта с общим
  скилом архитектора. Отдельного реестра архетипов, версий и
  наследования не нужно: скилы версионируются вместе с репозиторием
  пульта.
- Доменный архитектор проекта — не отдельный агент-файл, а сочетание:
  роль `architect` пульта, пакет знаний домена из проектного слоя и
  пути владения. Второго набора ролей не возникает.
- Участие определяет код: зоны SPEC пересекаются с путями доменов.
  Домен не задет — обычная цепочка. Домен с обязательным
  проектированием — необязательный шаг архитектора между гейтом SPEC
  и написанием тестов, на выходе короткий артефакт-контракт для
  разработчика и ревьювера. Домен с проверкой на выходе — ревьювер
  получает пакет домена дополнительным чек-листом.
- Предусловия: ТЗ-2 (клон целевого проекта, гейт зон на внешнем
  проекте) и ТЗ-4 (чтение проектного слоя `knowledge/`). До них
  форма остаётся на бумаге.
- Оценка добавочной стоимости: $5–10 на задачу там, где домен
  требует архитектора; на остальных задачах ноль.
- Не делать: описание архитекторов в самом целевом репозитории,
  параллельный запуск нескольких архитекторов, граф исполнения вместо
  конвейера, право куратора самому переписывать агентов.

## 2. Анализ со стороны агента, без учёта процессов Оператора

Вывод: постоянные доменные агенты как отдельные исполнители не нужны;
нужны доменные пакеты знаний, которые подгружаются в обычного агента
по затронутым файлам. Выигрыш даёт точный контекст, а не
специализация исполнителя.

Основание: агент состоит из модели и содержимого её окна. Модель у
всех одна, поэтому доменный агент отличается от общего только
загруженным контекстом. Название роли в промпте качества почти не
добавляет.

Где узкий охват полезен:

- Знание, которого нет в коде: инварианты, причины решений, запреты,
  известные ловушки. Агент живёт один запуск и каждый раз изучает код
  заново; это знание из кода не выводится.
- Экономия на разведке: заметная доля токенов исполнителя уходит на
  поиск нужных мест до первой правки.
- Короткий контекст: качество рассуждений падает с ростом окна.

Цена разделения на отдельных агентов:

- Ошибки на стыках: узкий агент не видит потребителей своих
  интерфейсов, а изменения часто пересекают границы.
- Потери при передаче: каждая передача между агентами сжимает
  информацию; рассуждение, приведшее к решению, остаётся у автора.
- Устаревание: описание домена является кэшем; устаревший кэш даёт
  уверенно неверную навигацию.
- Ошибка выбора домена: неверно выбранный специалист хуже общего
  агента.

Порог окупаемости: пока агент с картой находит нужное за несколько
чтений, деление на домены даёт только издержки. Оно окупается, когда
неявных правил много или код домена не помещается в рабочее окно.

Организация работы:

- Единица хранения — пакет домена, не агент. Один исполнитель может
  загрузить два пакета для задачи на стыке, что снимает проблему
  границ без координации между агентами.
- Границы доменов — по связности: файлы, которые по истории коммитов
  меняются вместе. Доменов порядка пяти–десяти.
- Иерархия в два уровня: выбор пакетов делает код по путям; один
  исполнитель с пакетами проектирует и реализует в одном контексте;
  независимый проверяющий со свежим контекстом и теми же пакетами
  сверяет результат с инвариантами. Проверить соблюдение правила
  надёжнее, чем породить код с его учётом.
- Отдельный проектировщик оправдан, только когда задача не помещается
  в один контекст: он делит её на части с явными контрактами и
  непересекающимися файлами.
- Параллельность допустима для чтения и проверки, не для записи в
  связанный код.
- Пакет обновляет агент, закончивший задачу: неожиданность, которой не
  было в пакете, становится предложением правки.

Измерение: на одинаковых задачах с пакетом и без него сравнить токены
до первой правки, число возвратов от проверяющего и дефекты на стыках
доменов. Первые две величины не падают — пакет пересказывает код.
Растёт третья — границы проведены не там.

## 3. Состав пакета домена

Предел размера — одна-две тысячи токенов. Форма жёсткая:

```markdown
# pricing

## Инварианты
- Опубликованная цена не меняется задним числом. Тест: invariants_test.py::test_published_immutable
- Пересчёт идемпотентен. Тест: invariants_test.py::test_recalc_idempotent

## Граница
Отдаёт: событие PriceChanged, функция get_price(product_id, date).
Потребляют: commerce, reports.
Принимает: ForecastUpdated из forecasting.

## Ловушки
- Округление только в money.py, иначе расходятся итоги.

## Точки входа
- src/pricing/service.py: пересчёт
- src/pricing/money.py: арифметика

## Проверка
pytest src/pricing -q
```

В пакет не кладутся структура каталогов и общие советы: первое
выводится из кода, второе не помогает. Всё, что выразимо тестом или
типом, хранится тестом; строка инварианта без ссылки на тест означает
«проверяет только читающий», таких строк должно быть мало.

## 4. Раскладка: пульт, проектный слой, целевой проект

В целевом проекте каталога `.artel/` нет. `.artel/` — рабочий каталог
пульта.

| Где | Что лежит | Почему там |
|---|---|---|
| Репозиторий пульта | Роль `architect` в `roles.yaml`; общий скил архитектора в `skills/`; шаблон пакета домена в `templates/`; код выбора доменов по путям, проверки свежести, предела размера, подмешивания пакета в бриф | Общее для всех проектов; защищённые пути, меняет только Оператор |
| Проектный слой пульта `.artel/projects/<проект>/knowledge/` | Индекс `domains.yaml` (пути доменов, команды проверки, политика участия архитектора, коммит свежести); пакеты `domains/<домен>.md`; контракты стыков `seams/` | Индекс определяет, что запускается и какие команды исполняются, поэтому не может приходить из недоверенного источника; каталог уже создаётся `target-init` как локальный git-репозиторий |
| Репозиторий целевого проекта | Только код и тесты инвариантов домена | Тесты являются кодом проекта и попадают туда обычным MR задачи |

```text
пульт/
├── roles.yaml                       # роль architect
├── skills/architecture-contract.md  # общий скил архитектора
├── templates/DOMAIN.md              # форма пакета
└── .artel/                          # вне git пульта
    └── projects/sled/
        └── knowledge/               # локальный git, ведёт пульт
            ├── domains.yaml
            ├── domains/
            │   ├── pricing.md
            │   └── forecasting.md
            └── seams/
                └── pricing--forecasting.md

sled/                                # целевой репозиторий
└── src/pricing/
    ├── invariants_test.py           # инварианты тестами
    └── ...
```

Индекс проектного слоя:

```yaml
domains:
  pricing:
    paths: [src/pricing/**, src/cost/**]
    pack: domains/pricing.md
    verify: pytest src/pricing -q
    design: required        # none | advisory | required
    review: gate            # none | advisory | gate
    built_at: 4f2a9c1       # коммит целевого, на котором пакет сверен с кодом
  notifications:
    paths: [src/notifications/**]
    pack: domains/notifications.md
    verify: pytest src/notifications -q
    design: none
    review: none
    built_at: 9b07e3d
seams:
  - between: [pricing, forecasting]
    pack: seams/pricing--forecasting.md
```

Правила:

- Каждый путь принадлежит одному домену; пути в индексе не
  пересекаются; непокрытый код относится к домену `shared`.
- Один файл на домен, без вложенных пакетов. Домен, которому нужен
  второй уровень, делится на два.
- Контракт стыка хранится отдельно и подгружается, когда задача
  задевает оба домена.
- Свежесть считает код: если с коммита `built_at` в путях домена
  изменилось больше заданной доли строк, пакет помечается устаревшим
  и роль получает его с предупреждением.
- Предел размера пакета проверяется механически.

Порядок при запуске шага:

1. Код берёт зоны задачи и по индексу находит домены.
2. В бриф роли кладутся пакеты найденных доменов и их стыков.
3. После правок запускаются команды `verify` затронутых доменов.
4. Ревьювер получает те же пакеты и дифф.
5. Предложение правки пакета роль оформляет в своём артефакте;
   применяет пульт после гейта.

Кто пишет в проектный слой: первичное наполнение — разовая задача при
подключении проекта (агент изучает клон, предлагает домены и пакеты,
Оператор принимает); далее — только через гейт.

Отличие от общей схемы «пакет рядом с кодом»: для подключённого
проекта она не подходит, потому что содержимое целевого репозитория
пульт считает данными, а не инструкциями, и по ADR-0003 не публикует
свои материалы в целевой проект, кроме веток задач и MR. Связь пакета
с кодом держится на коммите свежести в индексе. Для самого пульта как
цели слои совпадают физически: пакеты можно класть рядом с кодом в
`orchestrator/`, индекс — в корень репозитория под защищённые пути.

## 5. Домен или архитектор понадобился посреди шага

Роль не может вызвать архитектора внутри своего шага: один шаг равен
одному запуску агента, роли общаются только через артефакты.
Потребность закрывается одним из трёх способов.

1. Нужно знание домена. Роль читает пакет сама, шаг не
   останавливается. В бриф каждой роли кладётся краткий перечень всех
   доменов проекта с путями; пакеты доступны на чтение.
2. Нужно править файлы чужого домена. Это существующая механика
   расширения зон. Добавляется одно: после расширения код заново
   пересекает зоны с индексом доменов, новый домен попадает в бриф
   следующего шага, включается его политика участия.
3. Нужно решение архитектора (например, задача требует нарушить
   контракт домена). Роль завершает шаг артефактом со статусом
   эскалации и адресатом «архитектор домена X». Автомат переходит в
   отдельное состояние консультации и запускает роль `architect` с
   пакетом домена, вопросом и артефактами задачи. Архитектор пишет
   ответ в том же формате, что ответ Оператора. Задача возвращается
   в состояние, из которого пришла.

Доступность по шагам:

| Шаг | Чтение пакетов | Консультация архитектора | Примечание |
|---|---|---|---|
| Написание SPEC, analyst | да | нет | По пакетам analyst точнее задаёт зоны; вопросы шага касаются требований и идут Оператору |
| Проектирование, architect | да, плюс пакеты стыков | нет | Это сам архитектор; изменение контракта стыка он эскалирует Оператору |
| Написание тестов, test_author | да | да | Повод: критерий приёмки противоречит инварианту домена |
| Разработка, developer | да | да | Основной источник обращений; здесь же расширение зон |
| Проверка CI | не применимо | нет | Роли нет; код запускает команды проверки всех доменов, задетых фактическим диффом |
| Ревью, reviewer | да, по фактическому диффу | да | Обычно ревьювер возвращает задачу со ссылкой на инвариант; консультация — когда доменный вопрос он рассудить не может |
| Гейты: SPEC, приёмка, мерж | не применимо | нет | Решает Оператор или автогейт |

Правила консультации:

- Адресата называет роль, проверяет код: домен существует в индексе
  и задет зонами задачи либо граничит с ними. Иначе вопрос уходит
  Оператору.
- Числовой лимит: счётчик консультаций общий на задачу (например,
  две); после лимита — Оператор. Требование инвариантов 3 и 4.
- Стоимость шага списывается с бюджета задачи; по порядку величины
  как шаг analyst, $1–3.
- Архитектор вправе переадресовать вопрос Оператору, если он вне его
  полномочий.
- Архитектор на консультации не меняет инварианты пакета, не меняет
  контракт стыка двух доменов и не поднимает бюджет. Это остаётся
  Оператору.

Домен обнаружился посреди задачи: если после расширения зон задет
домен с обязательным проектированием, а разработка уже идёт, полный
шаг проектирования заново не запускается. Выполняется консультация
по этому домену, её ответ служит дополнением к контракту.

Открытое решение: может ли архитектор сам разрешать расширение зон
внутри путей своего домена. Это снимает часть эскалаций с Оператора,
но сейчас такое разрешение — право Оператора; делегирование требует
отдельного решения.
