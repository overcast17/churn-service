# Отчёт: CI/CD для churn-service

## Чекпоинты

| Пункт | Ссылка |
|---|---|
| 2.1 Зелёный прогон, три job | [run 36328656414](https://github.com/overcast17/churn-service/actions/runs/36328656414) |
| 2.1 Пакет, тег = sha | [ghcr.io/overcast17/churn-service](https://github.com/overcast17/churn-service/pkgs/container/churn-service), тег `e0f93a4d8e895600de6212cd52479d31b78aabf1` |
| 2.2 PR: красный → зелёный | [PR #4](https://github.com/overcast17/churn-service/pull/4): [красный](https://github.com/overcast17/churn-service/actions/runs/36328459466) → [зелёный](https://github.com/overcast17/churn-service/actions/runs/36328612116) |
| 2.3 Конфиг | [красный](https://github.com/overcast17/churn-service/actions/runs/36330701210) → [зелёный](https://github.com/overcast17/churn-service/actions/runs/36331350584) |
| 2.3 Секрет | [красный](https://github.com/overcast17/churn-service/actions/runs/36331760908) → [зелёный](https://github.com/overcast17/churn-service/actions/runs/36332317609) |
| 2.3 Ресурсы | [красный](https://github.com/overcast17/churn-service/actions/runs/36332800667) → [зелёный](https://github.com/overcast17/churn-service/actions/runs/36333181277) |

### 1. Пайплайн для своего сервиса

**Интеграционный тест** — [tests/test_integration.py](../tests/test_integration.py): после валидного запроса
в `predictions` есть строка с `status_code = 200`, после запроса с `tenure: -1` — строка с `422` и `score = NULL`.
Для второго случая в сервис добавлен обработчик `RequestValidationError`.

**ConfigMap** — `MODEL_PATH` и `LOG_LEVEL` приходят через `envFrom`, `/health` возвращает их значения.

**Smoke** — запрос с моими фичами и проверка смысла ответа:

```bash
curl --fail -s -X POST localhost:8080/v1/predict -H "Content-Type: application/json" -d @valid.json \
  | python3 -c "import json,sys; r=json.load(sys.stdin); assert 0 <= r['score'] <= 1, r"
```

### 2. Процесс: ветка и pull request

Красный прогон в PR #4 — не специально сломанный тест, а линтер: `E501 Line too long (152 > 150)`.
Починен следующим коммитом, после зелёной проверки PR слит.

### 3. Три красных прогона

| Поломка | Job / шаг | Статус пода | Что в диагностике |
|---|---|---|---|
| `MODEL_PATH: artifact/tralalal.joblib` | deploy / сервис | `CrashLoopBackOff` | трейсбек `FileNotFoundError` в логах |
| `secretKeyRef: {name: tun-tun-tun}` | deploy / база | `CreateContainerConfigError` | логов нет, в events `secret "tun-tun-tun" not found` |
| `memory: 10000000000000000000000000000000Mi` | deploy / сервис | `Pending` | логов нет, в events `Insufficient memory` |

**Конфиг.** Контейнер стартует и падает сам, значит, окружение на месте, а сломано то, что читает приложение.

**Секрет.** Сломал `secretKeyRef` у Postgres, а не `secretRef` сервиса, поэтому упал шаг «база».

**Ресурсы.** Под не назначен на узел (NODE пустой), в events `FailedScheduling`. Поднимать пришлось и
`limits`: при `requests > limits` манифест не проходит валидацию.

## Вопросы

**1.** Build шёл **71 с** в [первом прогоне](https://github.com/overcast17/churn-service/actions/runs/36317676278)
и **33 с** во [втором](https://github.com/overcast17/churn-service/actions/runs/36320723071). Полагаю, что в 1 прогоне устанавливались зависимости и окружение, а в дальнейших нет: `uv sync --frozen --no-dev --no-install-project`.

**2.** `kubectl apply` создаёт Deployment с образом из манифеста `churn-service:1.0`, которого в kind нет, это и есть  
поды в ImagePullBackOff. Следом `kubectl set image` ставит образ из GHCR, а старые поды удаляются.

**3.** Создаём секрет `DB_PASSWORD` в настройках GitHub -> в job deploy он попадает в переменную шага через `${{ secrets.DB_PASSWORD }}` (в логах скрыт как `***`) -> `kubectl create secret` кладёт его в Secret `churn-secrets` в кластере -> Deployment через `envFrom: secretRef` превращает его в переменные окружения пода. В configmap нельзя, так как репозиторий публичный и пароль остался бы в истории git.

**4.** Мы параллельно запускаем tests и build, и может пройти на кластер то, что не работает, так как тест не проверил бы build.

**5.** Строка `if: github.ref == 'refs/heads/main'` у build, а для deploy пропускается через `needs: build`.
PR получает быструю проверку, потому что прогонять каждый раз build и deploy на PR было бы затратно по времени. 

**6.** 2 реплики — это 2 пода сервиса (`replicas: 2`), а не реплики базы. При старте оба вызывают `init()` с `CREATE TABLE IF NOT EXISTS`, и на пустой базе оба могут решить, что таблицы нет. `IF NOT EXISTS` от такой гонки не защищает: второй под падает с ошибкой `duplicate key` и уходит в перезапуск. Лок ставит их в очередь: второй под ждёт, пока первый создаст таблицу, и видит её уже готовой.

**7.**

1. Pending
2. CreateContainerConfigError
3. CrashLoopBackOff

Pending: scheduler не нашёл узел с такой памятью. CreateContainerConfigError: под на узле, но kubelet не может собрать env из секрета.
CrashLoopBackOff: контейнер запустился, упало само приложение.

## Журнал проблем

(что не завелось с первого раза: текст ошибки → как починили)

### CI

1. `docker create ... --health-intreval 5s --health-timeoust 3s` → exit code 125 на *Initialize containers*. Опечатки в health-флагах Postgres, `POSTGRES_DB:churn` без пробела, `DATABASE_URL` без `postgresql://`. → [bd264a3](https://github.com/overcast17/churn-service/commit/bd264a3).
2. `Unable to resolve action docker/login-acrion` → build упал на *Set up job*. PR слит раньше, чем запушено исправление. → [ab4371d](https://github.com/overcast17/churn-service/commit/ab4371d) через PR #2.

Общая проблема — опечатки в YAML и именах. Самые неприятные не падали сразу: YAML принял `KEY:value`
без пробела, pytest молча пропустил тест, `IF NOT EXISTS` молча оставил старую схему.
