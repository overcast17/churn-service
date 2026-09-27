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

**Конфиг.** Контейнер стартует и падает сам, в логах трейсбек — значит, окружение на месте, а сломано то,
что читает приложение.

**Секрет.** Сломал `secretKeyRef` у Postgres, а не `secretRef` сервиса, поэтому упал шаг «база».
Логов нет, потому что контейнер не создавался, — причина видна только в events.

**Ресурсы.** Под не назначен на узел (NODE пустой), в events `FailedScheduling`. Поднимать пришлось и
`limits`: при `requests > limits` манифест не проходит валидацию.

## Семь вопросов

**1.** Build шёл **71 с** в [первом прогоне](https://github.com/overcast17/churn-service/actions/runs/36317676278)
и **33 с** во [втором](https://github.com/overcast17/churn-service/actions/runs/36320723071). Из кэша взят слой
`uv sync --no-install-project` — установка зависимостей. Он зависит только от `pyproject.toml` и `uv.lock`,
которые не менялись; изменился `src/`, и пересобралось всё начиная с `COPY src/`.

**2.** `kubectl apply` создаёт Deployment с образом из манифеста `churn-service:1.0`, которого в kind нет, —
это и есть поды в ImagePullBackOff. Следом `kubectl set image` ставит образ из GHCR, и `rollout status` ждёт
уже новую ревизию. Старые поды удаляются, так что прогон зелёный.

**3.** GitHub Secret `DB_PASSWORD` → `${{ secrets.DB_PASSWORD }}` в env шага → `kubectl create secret` →
Secret `churn-secrets` в кластере → `envFrom: secretRef` в поде. В `configmap.yaml` нельзя: репозиторий
публичный, и пароль навсегда остался бы в истории git.

**4.** Build пойдёт параллельно с тестами. Коммит ломает логирование 422, тест красный, но образ уже в GHCR,
и deploy выкатывает его в кластер — сломанная версия работает, хотя тесты её не пропустили.

**5.** Строка `if: github.ref == 'refs/heads/main'` у build; deploy пропускается следом через `needs: build`.
Так в реестр попадают только образы из main после ревью, а PR получает быструю проверку тестами.

**6.** Реплики — это два пода сервиса (`replicas: 2`). Оба при старте вызывают `CREATE TABLE IF NOT EXISTS`,
и на пустой базе один из них может упасть с `duplicate key ... pg_type_typname_nsp_index`: `IF NOT EXISTS`
от гонки не защищает. Лок ставит их в очередь, второй видит уже готовую таблицу.

**7.** `Pending` → `CreateContainerConfigError` → `CrashLoopBackOff`. Pending — scheduler не нашёл узел
с такой памятью. CreateContainerConfigError — под на узле, но kubelet не может собрать env из секрета.
CrashLoopBackOff — контейнер запустился, упало само приложение.

## Замечания по домашке 1

| Замечание | Коммит |
|---|---|
| 422 не логируются в `status_code` | [7e52269](https://github.com/overcast17/churn-service/commit/7e52269), тест [9e1ca93](https://github.com/overcast17/churn-service/commit/9e1ca93) |
| ноутбук сохраняет модель не в `artifact/` | [3ae97c2](https://github.com/overcast17/churn-service/commit/3ae97c2) |
| нет `.dockerignore` | [84de75c](https://github.com/overcast17/churn-service/commit/84de75c) |
| тест про батч без батча | [ade050b](https://github.com/overcast17/churn-service/commit/ade050b) |
| `uv:latest`, подпись «три пода» | не исправлено |

## Журнал проблем

(что не завелось с первого раза: текст ошибки → как починили)

### CI

1. `docker create ... --health-intreval 5s --health-timeoust 3s` → exit code 125 на *Initialize containers*. Опечатки в health-флагах Postgres, `POSTGRES_DB:churn` без пробела, `DATABASE_URL` без `postgresql://`. → [bd264a3](https://github.com/overcast17/churn-service/commit/bd264a3).
2. `Unable to resolve action docker/login-acrion` → build упал на *Set up job*. PR слит раньше, чем запушено исправление. → [ab4371d](https://github.com/overcast17/churn-service/commit/ab4371d) через PR #2.
3. Интеграционный тест зелёный, но на деле пропускался: в CI не было `DATABASE_URL`, срабатывал `skipif`. → Postgres в `services:` job tests.
4. Коммит починки `99ebc87` без своего прогона: запушен одним push вместе со следующим, а GitHub запускает workflow только для последнего.

### Локально

5. `KeyError: 'Contract'` — интеграционный тест скопирован с семинара с чужим датасетом. → Проверка по `geography`.
6. `NotNullViolation: null value in column "score"` после снятия `NOT NULL`: `CREATE TABLE IF NOT EXISTS` не меняет существующую таблицу. → `DROP TABLE predictions`.

Общая проблема — опечатки в YAML и именах. Самые неприятные не падали сразу: YAML принял `KEY:value`
без пробела, pytest молча пропустил тест, `IF NOT EXISTS` молча оставил старую схему.
