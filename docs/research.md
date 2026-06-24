# Avalone — исследования по миру

> Результаты первого раунда исследований для проработки идеи метавселенной Avalone.
> Дата: 2026-06-24.
> Источники: открытые веб-источники, публичные репозитории, отраслевые отчёты.

## Цель

Понять, какие аналоги, стандарты и архитектурные паттерны существуют в мире для:
- цифровых экосистем / super apps, покрывающих повседневную жизнь;
- HR / gig economy платформ (особенно в Южной Корее);
- социально-экономических графов (люди — организации — возможности — репутация);
- identity и reputation systems;
- моделей данных и протоколов взаимодействия.

---

## 1. Цифровые экосистемы и super apps

### WeChat (Tencent, Китай)

WeChat — ключевой пример super app, в который встроена значительная часть цифровой жизни: коммуникации, платежи, мини-программы, официальные аккаунты брендов, видео, рабочие процессы (WeCom).

**Что важно для Avalone:**
- Единый аккаунт + профиль + социальный граф + платежи = основа для множества вертикалей.
- Mini Programs показывают, как сторонние сервисы могут жить внутри экосистемы без необходимости скачивать отдельные приложения.
- Official Accounts — модель взаимодействия организаций с пользователями внутри одной платформы.
- WeChat Pay обработал более 4 трлн RMB в 2023 году; Mini Programs — 2.7 трлн RMB транзакций.
- Платформа не является единым 3D-миром, но по сути является метавселенной поверх реального мира: связи, платежи, услуги, работа, образование, госуслуги.

**Урок для Avalone:** метавселенная не обязана быть 3D. Достаточно единого цифрового слоя с аккаунтом, социальным графом, репутацией и платёжной инфраструктурой.

### LinkedIn, Upwork, Airbnb и другие западные платформы

Каждая из платформ покрывает узкий сегмент:
- LinkedIn — профессиональный профиль и репутация.
- Upwork — фриланс и проектная работа.
- Airbnb — жильё и краткосрочная аренда.
- JobKorea / Albamon — работа и подработка в Корее.

**Проблема:** у пользователя одна жизнь, а данные разбросаны по десяткам сервисов. У каждого сервиса свой профиль, своя репутация, свои отзывы.

**Урок для Avalone:** возможность построить единый профиль и единую репутацию, которые работают во всех ветках (работа, жильё, образование, туризм).

---

## 2. HR и gig economy в Южной Корее

### JobKorea и Albamon

- JobKorea и Albamon принадлежат Worksphere (ранее JobKorea).
- В 2025 году совокупное количество откликов на вакансии превысило 95 млн.
- Albamon — лидер среди платформ для подработки (арбайт): около 10 млн MAU, более 55% рынка.
- JobKorea внедряет AI-рекомендации: AI Recommendation 2.0/3.0, AI career advisor, персонализированные инсайты.
- Albamon запустил AI-бота AlbamuMulbot и функции Direct-to-Work.

**Что важно для Avalone:**
- Рынок огромный и уже конкурентный. Просто клонировать JobKorea/Albamon нет смысла.
- Дифференциация возможна через:
  - вертикальную интеграцию (работа + развозка + образование + документы);
  - социальный граф и репутацию среди мигрантов;
  - операционную систему для самущилей, а не только маркетплейс вакансий.

### Самущили и арбайт

- Самущиль (dispatch agency) и арбайт (part-time/temporary work) — специфичная для Кореи форма трудоустройства.
- Существующие платформы не покрывают операционную координацию: кто на какой машине, кто остался на заводе, кто уехал, переработки.
- Эта боль и есть первая точка входа для Avalone.

---

## 3. Графовые модели и репутация

### Twitter / X recommendation algorithm

Публичный репозиторий twitter/the-algorithm показывает, как построена рекомендательная система на основе графа:
- **TwHIN** — dense knowledge graph embeddings для пользователей и постов.
- **real-graph** — модель предсказания вероятности взаимодействия между пользователями.
- **tweepcred** — PageRank для расчёта репутации пользователя.
- **SimClusters** — community detection и sparse embeddings.
- **graph-feature-service** — графовые фичи для пар пользователей.

**Урок для Avalone:** репутация и matching могут быть выражены через графовые модели. Для Avalone это может быть граф: человек — организация — возможность — сделка — отзыв.

### Village Link

GitHub-проект, нацеленный на построение "деревень" — локальных сообществ с акцентом на:
- identity и authentication;
- reputation;
- social connections и connection weights;
- нормы сообщества;
- non-zero-sum transactional opportunities через поиск и репутацию в социальном графе.

**Урок для Avalone:** connection weights (веса связей) — важная концепция. Не все связи равны: близкие друзья, надёжные коллеги, проверенные работодатели имеют больший вес.

### Trust Over IP (ToIP) stack

ToIP — архитектурный стек для цифрового доверия:
- Layer 1: Trust Support (DIDs, registries, identifiers).
- Layer 2: Trust Spanning (Trusted Communication Protocol, user agents, data vaults, KMS).
- Layer 3: Data Exchange (verifiable credentials).
- Layer 4: Ecosystem Governance.

**Урок для Avalone:** identity, reputation и trust можно проектировать слоями, а не смешивать в одну кучу.

---

## 4. Identity и reputation systems

### Decentralized Identifiers (DIDs) и Verifiable Credentials (VCs)

- **W3C DID Core** — стандарт децентрализованных идентификаторов.
- **W3C Verifiable Credentials Data Model** — стандарт криптографически верифицируемых утверждений.
- **DID methods:** did:key, did:web, did:ion, did:ebsi, KERI, did:dht (Block).
- **Протоколы:** DIDComm, OpenID4VCI, OpenID4VP, Presentation Exchange.
- **Организации:** W3C, DIF (Decentralized Identity Foundation), OpenID Foundation.

**Слои VC-стека:**
1. Data Model (JSON-LD / JWT)
2. Identity (DID)
3. Credential Issuance
4. Proof (Linked Data Proofs, JWT, BBS+ / ZKP)
5. Revocation (Status Lists)
6. Presentation (Verifiable Presentations)
7. Transport (DIDComm, HTTPS, OIDC)
8. Verification
9. Governance (Trust Frameworks)
10. Storage / Wallet

**Урок для Avalone:**
- Для начала можно использовать централизованные идентификаторы (did:web, внутренние ID), но архитектура должна позволять в будущем перейти на VC/DID.
- Репутация и навыки могут быть оформлены как Verifiable Credentials.
- Документы (визы, разрешения, сертификаты) — естественный кандидат для VC.

### Soulbound Tokens (SBT) и non-transferable reputation

- SBT — невзаимозаменяемые токены, привязанные к аккаунту, не передаваемые.
- Используются для репутации, достижений, членства в сообществах.

**Урок для Avalone:** некоторые аспекты репутации должны быть non-transferable: например, отзывы, история работы, подтверждённые навыки.

### Proof of Personhood / Sybil resistance

- Проблема: как отличить реального человека от фейковых аккаунтов.
- Решения: биометрия (Worldcoin), социальные графы, VC от доверенных issuer'ов, телефонная верификация.

**Урок для Avalone:** для платформы, где репутация — ключевой актив, Sybil resistance критичен. Начать можно с телефонной верификации + VC от работодателей/самущилей.

---

## 5. Метавселенные: тренды

- Метавселенная не обязательно 3D или игровая.
- Ключевые тренды: decentralized virtual economies, AI-аватары, виртуальные рабочие места, социальные метавселенные, образование, виртуальная недвижимость.
- Успешные "метавселенные" — это чаще всего социальные платформы, маркетплейсы, super apps.

**Урок для Avalone:** Avalone может позиционироваться как "социально-экономическая метавселенная" без необходимости строить 3D-мир.

---

## 6. Выводы и импликации для Avalone

### Что подтверждается

1. **Super app / цифровой слой** — рабочая модель. WeChat доказывает, что один аккаунт может покрывать коммуникации, платежи, работу, услуги, образование.
2. **HR/gig рынок Кореи огромен** — 95 млн откликов в год, 10 млн MAU у Albamon. Есть место для нишевого решения, если оно решает реальную операционную боль.
3. **Граф + репутация** — технически осуществимо. Twitter, Village Link, ToIP дают паттерны.
4. **Identity standards зрелеют** — W3C DID/VC, OID4VC, DIF. Можно начать просто и усложнять по мере роста.

### Что меняет подход

1. **Не конкурировать с JobKorea напрямую.** Конкурировать нужно на уровне операционной системы для самущилей и социального графа мигрантов.
2. **Репутация — главный актив с самого начала.** Даже в MVP должны закладываться механизмы отзывов, истории и доверия.
3. **Модель данных должна быть расширяемой.** Сегодня работа, завтра образование, послезавтра туризм — без переписывания ядра.
4. **Sybil resistance важен.** Фейковые профили разрушат репутационную систему.

### Архитектурные гипотезы

1. **Ядро:** единый профиль, identity, репутация, социальный граф, платежи, сообщения.
2. **Ветки:** работа, образование, туризм, медицина, жильё, транспорт, сообщества — как Mini Programs внутри Avalone.
3. **Data model:** граф сущностей Человек — Организация — Место — Событие — Возможность — Навык — Документ — Транспорт — Сообщество — Репутация.
4. **Identity:** начать с phone-verified + internal IDs, roadmap — VC/DID.
5. **Reputation:** reviews + history + skills endorsements + connection weights, частично non-transferable.

---

## 7. Направления для следующих исследований

1. **Детальный анализ сценария арбайт + развозка.** Поминутное описание дня самущиля и работника.
2. **Технический стек для графовых БД.** Neo4j, Dgraph, PostgreSQL + pg_graphql, RDF/SPARQL.
3. **Мигрантские сообщества в Корее.** Как они коммуницируют сейчас (KakaoTalk, Telegram, Facebook, word-of-mouth).
4. **Монетизация платформ.** Транзакционные комиссии, подписки для организаций, реклама, данные.
5. **Регуляторика.** Fintech, персональные данные, трудовое законодательство Кореи.
6. **Прототипирование MVP.** Форма для самущиля, карта заводов, чат/уведомления, базовая развозка.

---

## 8. UI / навигация портала

### Ключевые принципы

- **Thumb-zone first:** основные действия — в нижней трети экрана. Bottom navigation работает на 30-40% быстрее drawer-навигации для частых переключений.
- **Progressive disclosure:** сначала показывать главное, детали — по тапу.
- **Кратчайший путь:** от старта до цели — минимум тапов.
- **Не больше 4-5 первичных пунктов:** иначе когнитивная перегрузка.

### Паттерны

- **Bottom navigation + contextual cards** — стандарт для mobile-first приложений.
- **Bento grid** — сетка карточек для визуального обзора всех веток.
- **Command palette / поиск** — кратчайший путь для опытных пользователей.
- **Horizontal hierarchy** — движение вбок вместо углубления вниз.
- **FAB (Floating Action Button)** — главное действие в текущем контексте.

### Визуальные тренды 2025

- Glassmorphism, layered depth, spatial UI.
- Micro-animations как навигационная подсказка.
- Adaptive theming (утро/вечер, контекст).
- Empty states с teaser для coming-soon разделов.

## 9. Технологический стек

### Frontend

- **SvelteKit** — рекомендуется для MVP из-за производительности и малого размера bundle.
- **React / Next.js** — альтернатива с большей экосистемой.
- **PWA** — must have для мобильных пользователей без необходимости публиковаться в App Store.

### Backend

- **Python FastAPI** — async, быстрый, AI-ready, уже используется в Counta.
- **Node.js / NestJS** — альтернатива для full-stack JavaScript и real-time.

### Database

- **PostgreSQL** — надёжный выбор для старта.
- **Neo4j** — для глубоких графовых запросов при масштабировании.
- **Apache AGE / pg_graphql** — граф поверх PostgreSQL.

### Real-time

- **WebSockets** — для статусов машин и смен.
- **SSE** — для односторонних push-уведомлений.
- **Firebase / Supabase Realtime** — готовое BaaS-решение.

### Maps

- **Kakao Maps API** — лучшее покрытие Кореи.
- **Naver Maps API** — альтернатива.
- **OpenStreetMap + Leaflet** — бесплатный fallback.

### Auth

- **Firebase Auth** — phone + OAuth, быстрый старт.
- **DID / VC** — roadmap для будущего.

### Payments

- **Stripe** — международный, простой.
- **Toss Payments / KakaoPay** — для Кореи при масштабировании.

---

## Источники

- WeChat ecosystem overview: https://mediascope.group/wechat-ecosystem-an-overview-of-chinas-digital-super-app/
- JobKorea / Albamon annual applications: https://www.digitaltoday.co.kr/en/view/4353/jobkorea-albamon-annual-job-applications-top-95-million
- Albamon Z design: https://competition.adesignaward.com/ada-winner-design.php?ID=156820
- Twitter / X algorithm: https://github.com/twitter/the-algorithm
- Village Link: https://github.com/Inky-Tech-Pty-Ltd/Links
- ToIP ontology (PDF): https://utheme.univ-tlse3.fr/files/original/a279d4dbaee14b7ee7fee77a3a48772ab38c7cc6.pdf
- Decentralized Identity Applications study: https://arxiv.org/html/2503.15964
- Microsoft Entra Verified ID standards: https://learn.microsoft.com/ar-sa/entra/verified-id/verifiable-credentials-standards
- GS1 VC and DIDs landscape: https://ref.gs1.org/docs/2025/VCs-and-DIDs-tech-landscape
- Top Metaverse Trends: https://webcomsystem.net/blog/top-10-metaverse-avatar-development-trends-to-in-2024-2025/
- Mobile Navigation Hierarchy Law: https://uxuiprinciples.com/en/principles/mobile-navigation-hierarchy
- Material Design Navigation Patterns: https://m1.material.io/patterns/navigation.html
- Top Mobile App UI Patterns 2025: https://www.witstechnologies.co.ke/blog/top-10-mobile-app-ui-patterns-dominating-2025/
- Mobile App UI Design Guide 2025: https://www.thedroidsonroids.com/blog/mobile-app-ui-design-guide
- Best Tech Stack for SaaS 2026: https://enqcode.com/blog/best-tech-stack-for-building-scalable-saas-apps-in-2026
- Best Tech Stacks for Mobile App Development 2026: https://www.8ration.com/blogs/best-technology-stacks-for-mobile-app-development/
- Top PWA Frameworks 2026: https://www.testmuai.com/blog/progressive-web-app-frameworks/
