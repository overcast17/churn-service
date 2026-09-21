# churn-service — предсказание оттока клиентов банка

Сервис на FastAPI отдаёт вероятность оттока клиента банка. Модель обучена в ноутбуке,
сохранена как joblib-бандл с паспортом, сервис логирует каждое предсказание в PostgreSQL,
разворачивается в Docker Compose и в Kubernetes.

Задача — **отток клиентов банка** (Kaggle, `Customer-Churn-Records.csv`, 10 000 строк).


## Три команды проверки

Выполняются из корня репозитория сверху вниз.

```bash
uv sync && uv run pytest
```

```bash
docker compose up -d --build
```

```bash
kind create cluster --name mlpro && docker build -t churn-service:1.0 . && kind load docker-image churn-service:1.0 --name mlpro && kubectl apply -f k8s/ && kubectl rollout status deploy/churn-service
```

Что делает каждая:

1. **Тесты.** `uv sync` поднимает окружение по `uv.lock` (Python 3.11 из `.python-version`),
   `pytest` прогоняет 9 тестов.
2. **Compose.** Собирает образ и поднимает сервис вместе с Postgres на `localhost:8000`.
3. **Kubernetes.** Создаёт кластер kind `mlpro`, собирает образ, загружает его в ноду,
   применяет манифесты и дожидается выката.

Нужны: `uv`, `docker` (запущенный Docker Desktop), `kind`, `kubectl`.

## Модель

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
| GET | `/docs` | Swagger UI, схема в `/openapi.js` |

### Запрос

Схема запрещает лишние поля (`extra="forbid"`) и проверяет границы значений —
неизвестная категория или отрицательный стаж вернут 422

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

Этот же пример лежит в `valid.json`.

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
Dockerfile         сборка на uv: слой зависимостей до слоя кода
compose.yaml       сервис + Postgres с healthcheck
```
## Отчёт

Скриншоты чекпоинтов и журнал проблем — в [REPORT.md](REPORT.md).
