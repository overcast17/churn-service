# Отчёт: churn-service от артефакта до кластера

Домашнее задание 1, ML PRO. Сервис предсказания оттока клиентов банка:
модель → FastAPI → тесты → Docker → Compose с Postgres → Kubernetes в kind.

## Чекпоинты

### 1. Тесты

```bash
uv run pytest
```

9 тестов: контракт (лишнее поле, пропущенное поле, неверный тип, неизвестная категория,
значение вне границ — все дают 422), smoke (код 200, скор в диапазоне [0, 1],
типы полей ответа), детерминизм (один вход дважды даёт один скор).

![Вывод uv run pytest: 9 passed](images/tests.png)

### 2. Логи предсказаний в Postgres

```bash
docker compose up -d --build
curl -X POST http://localhost:8000/v1/predict -H "Content-Type: application/json" -d "@valid.json"
docker compose exec -T db psql -U postgres -d churn -c "SELECT request_id, score, latency_ms, status_code, ts FROM predictions;"
```

`request_id` в строке таблицы совпадает с тем, что вернул сервис, `status_code` = 200.

![SELECT из таблицы predictions](images/select.png)

### 3. Поды в кластере

```bash
kubectl get pods
```

Две реплики сервиса.

![kubectl get pods: три пода Running](images/pods.png)

### 4. Предсказание через port-forward

```bash
kubectl port-forward svc/churn-service 8080:80
curl -X POST http://localhost:8080/v1/predict -H "Content-Type: application/json" -d "@valid.json"
```

Три порта на пути запроса: 8080 на машине, 80 у Service, 8000 в контейнере.

![Ответ модели через port-forward](images/predict.png)

### 5. k9s

![k9s, вид :pods](images/k9s.png)

## Журнал проблем

(что не завелось с первого раза: текст ошибки → как починили)

### Сервис

1. Поля схемы `Features` были голыми `int` и `str`: запрос с `tenure: -1` или `geography: "Атлантида"` → статус 200 и правдоподобный скор. Неизвестную категорию `OneHotEncoder(handle_unknown="ignore")` молча превращал в нулевой вектор. → Границы через `Field(ge/le)`, допустимые категории через `Literal[...]`, на каждый случай добавлен тест с ожиданием 422.
2. Опечатка `geografy` в схеме при `geography` в паспорте модели: сервис не падал, `reindex(columns=meta["features"])` ставил `NaN`, `SimpleImputer(strategy="most_frequent")` подставлял самую частую страну — все клиенты становились французами. → Исправлено имя поля. Правило: имена в схеме запроса обязаны совпадать со списком `features` из паспорта, расхождение проявляется молча.

Общая проблема — опечатки: в именах полей схемы, в ключевых словах DDL, в именах колонок таблицы.
Самые неприятные из них не роняли сервис: он отвечал 200, а ошибка всплывала только в данных или в логах.

