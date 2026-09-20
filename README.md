# churn-service — предсказание оттока клиентов банка

Сервис на FastAPI отдаёт вероятность оттока клиента банка. Модель обучена в ноутбуке,
сохранена как joblib-бандл с паспортом, сервис логирует каждое предсказание в PostgreSQL,
разворачивается в Docker Compose и в Kubernetes.

Задача — **отток клиентов банка** (Kaggle, `Customer-Churn-Records.csv`, 10 000 строк).
Это не телеком-датасет семинара: другие признаки, своя схема запроса и свой паспорт модели.

## Три команды проверки

Выполняются из корня репозитория сверху вниз.

```bash
uv sync && uv run pytest
```

```bash
bash scripts/compose_up.sh
```

```bash
bash scripts/kind_up.sh
```

Что делает каждая:

1. **Тесты.** `uv sync` поднимает окружение по `uv.lock` (Python 3.11 из `.python-version`),
   `pytest` прогоняет 9 тестов.
2. **Compose.** Собирает образ, поднимает сервис и Postgres, дожидается готовности,
   делает предсказание и показывает строку в таблице логов.
3. **Kubernetes.** Создаёт кластер kind (если его нет), собирает образ, загружает его в ноду,
   применяет манифесты, дожидается выката и получает предсказание через port-forward.

Нужны: `uv`, `docker` (запущенный Docker Desktop), `kind`, `kubectl`.

## Модель

| | |
|---|---|
| Алгоритм | LogisticRegression в `Pipeline` с препроцессингом |
| Версия | 1.0.0 |
| Порог | 0.1973 — максимальный порог при recall ≥ 0.7 на OOF-предсказаниях train |
| ROC-AUC | 0.7784 |
| PR-AUC | 0.4865 |
| Precision / Recall / F1 | 0.3794 / 0.7402 / 0.5017 |

Порог выбран в пользу recall: для удержания клиентов дороже пропустить уходящего,
чем лишний раз побеспокоить лояльного.

Обучение: [`notebooks/bank_churn.ipynb`](notebooks/bank_churn.ipynb).
Артефакт: `artifact/model.joblib` — словарь с ключами `pipeline` и `metadata`.
Паспорт модели продублирован в [`artifact/metadata.json`](artifact/metadata.json):
версия, список признаков в нужном порядке, порог, метрики, версии библиотек.

## API

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Процесс жив, отдаёт версию модели (liveness-проба) |
| GET | `/ready` | Модель загружена; 503, пока это не так (readiness-проба) |
| POST | `/v1/predict` | Предсказание по одному клиенту |
| GET | `/docs` | Swagger UI, схема в `/openapi.json` |

### Запрос

Схема запрещает лишние поля (`extra="forbid"`) и проверяет границы значений —
неизвестная категория или отрицательный стаж вернут 422, а не молча доедут до модели.

```json
{
  "credit_score": 619,
  "geography": "France",
  "gender": "Female",
  "age": 42,
  "tenure": 2,
  "balance": 0.0,
  "num_of_products": 1,
  "has_cr_card": 1,
  "is_active_member": 1,
  "estimated_salary": 101348.88,
  "satisfaction_score": 2,
  "card_type": "DIAMOND",
  "point_earned": 464
}
```

Этот же пример лежит в `valid.json` — им пользуются скрипты проверки.

### Ответ

```json
{
  "score": 0.1370243611816741,
  "churn": false,
  "model_version": "1.0.0",
  "request_id": "7f43ebf4-82fb-439b-8a3f-774ea40df3ee",
  "latency_ms": 66.59
}
```

`churn` — результат сравнения `score` с порогом из паспорта модели.

## Логи предсказаний

Каждый успешный запрос к `/v1/predict` пишется строкой в таблицу `predictions`:

| Колонка | Тип | Что хранит |
|---|---|---|
| `request_id` | uuid | Идентификатор запроса, он же в ответе |
| `ts` | timestamptz | Время |
| `model_version` | text | Версия модели |
| `features` | jsonb | Признаки как пришли |
| `score` | double precision | Предсказание |
| `latency_ms` | real | Время обработки |
| `status_code` | int | Код ответа |

Запись идёт в фоновой задаче — ответ клиенту не ждёт базу.
Без `DATABASE_URL` сервис работает штатно и просто не логирует.

## Конфигурация

Читается из переменных окружения (`pydantic-settings`), при отсутствии берутся значения по умолчанию.

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `MODEL_PATH` | `artifact/model.joblib` | Путь к артефакту |
| `DATABASE_URL` | не задан | Строка подключения к PostgreSQL |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

В Compose переменные заданы в `compose.yaml`, там же поднимается Postgres — логирование
предсказаний проверяется именно там. В Kubernetes `DATABASE_URL` не задан: сервис работает
и отдаёт предсказания, просто не пишет их в базу.

## Структура

```
artifact/          model.joblib + metadata.json
data/              исходный датасет
notebooks/         обучение модели
src/churn/
  config.py        настройки
  db.py            DDL и запись предсказаний
  service/app.py   FastAPI: схемы, lifespan, эндпоинты
tests/             9 тестов: контракт, smoke, детерминизм
k8s/               deployment.yaml, service.yaml
scripts/           compose_up.sh, kind_up.sh
Dockerfile         сборка на uv: слой зависимостей до слоя кода
compose.yaml       сервис + Postgres с healthcheck
```

## Ручные команды

Локальный запуск без контейнеров:

```bash
uv run uvicorn churn.service.app:app --port 8000
```

Посмотреть логи предсказаний в Compose:

```bash
docker compose exec -T db psql -U postgres -d churn -c "SELECT * FROM predictions;"
```

Обновить образ в кластере после правок кода:

```bash
docker build -t churn-service:1.0 . && kind load docker-image churn-service:1.0 --name mlpro && kubectl rollout restart deployment/churn-service
```

Остановить всё:

```bash
docker compose down && kind delete cluster --name mlpro
```

## Отчёт

Скриншоты чекпоинтов и журнал проблем — в [REPORT.md](REPORT.md).
