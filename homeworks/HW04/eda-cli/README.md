## S04 – eda_cli: HTTP-сервис качества датасетов (FastAPI)

Расширенная версия проекта `eda-cli` из Семинара 03.

К существующему CLI-приложению для EDA добавлен **HTTP-сервис на FastAPI**
для оценки качества датасетов на основе эвристик.

Используется в рамках Семинара 04 курса «Инженерия ИИ».

---

## Связь с S03

Проект в S04 основан на том же пакете `eda_cli`, что и в S03:

- сохраняется структура `src/eda_cli/` и CLI-команда `eda-cli`;
- используются эвристики качества из HW03;
- добавлен модуль `api.py` с FastAPI-приложением;
- в зависимости добавлены `fastapi` и `uvicorn[standard]`.

Цель S04 – показать, как поверх уже реализованного EDA-ядра поднять HTTP-сервис.

---

## Требования

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) установлен в систему
- HTTP-клиент или браузер (для Swagger UI `/docs`)

---

## Инициализация проекта

В корне проекта (каталог `S04/eda-cli`):

```bash
uv sync
```

Команда:

- создаёт виртуальное окружение `.venv`;
- устанавливает зависимости из `pyproject.toml`;
- устанавливает сам проект `eda-cli` в окружение.

---

## Запуск CLI (как в S03)

CLI остаётся доступным и в S04.

### Краткий обзор

```bash
uv run eda-cli overview data/example.csv
```

Параметры:

- `--sep` — разделитель (по умолчанию `,`);
- `--encoding` — кодировка (по умолчанию `utf-8`).

### Полный EDA-отчёт

```bash
uv run eda-cli report data/example.csv --out-dir reports
```

В результате в каталоге `reports/` появятся:

- `report.md` — основной отчёт в Markdown;
- `summary.csv` — таблица по колонкам;
- `missing.csv` — пропуски по колонкам;
- `correlation.csv` — корреляционная матрица;
- `top_categories/*.csv` — top-k категорий по строковым признакам;
- `hist_*.png` — гистограммы числовых колонок;
- `missing_matrix.png` — визуализация пропусков;
- `correlation_heatmap.png` — тепловая карта корреляций.

---

## Запуск HTTP-сервиса

HTTP-сервис реализован в модуле `eda_cli.api` на FastAPI.

### Запуск Uvicorn

```bash
uv run uvicorn eda_cli.api:app --reload --port 8000
```

После запуска сервис доступен по адресу:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

---

## Эндпоинты сервиса

### 1. `GET /health`

Простейший health-check сервиса.

```http
GET /health
```

Пример ответа:

```json
{
  "status": "ok",
  "service": "dataset-quality"
}
```

---

### 2. `POST /quality-from-csv`

Эндпоинт принимает CSV-файл и:

- читает его в `pandas.DataFrame`;
- вызывает:
  - `summarize_dataset`,
  - `missing_table`,
  - `compute_quality_flags`;
- возвращает агрегированную оценку качества и флаги.

```http
POST /quality-from-csv
Content-Type: multipart/form-data
file: <CSV-файл>
```

---

### 3. `POST /quality-flags-from-csv` (новый эндпоинт)

Эндпоинт принимает CSV-файл и **возвращает полный набор булевых эвристик качества**,
включая новые эвристики, добавленные в HW03.

```http
POST /quality-flags-from-csv
Content-Type: multipart/form-data
file: <CSV-файл>
```

#### Используемые эвристики качества

Эндпоинт возвращает флаги, вычисленные в `compute_quality_flags`, включая:

- `too_few_rows` — слишком мало строк;
- `too_many_columns` — слишком много колонок;
- `too_many_missing` — слишком высокая доля пропусков;
- `has_constant_columns` — наличие константных признаков;
- `has_high_cardinality_categoricals` — категориальные признаки с высокой кардинальностью.

#### Пример ответа

```json
{
  "flags": {
    "too_few_rows": true,
    "too_many_columns": false,
    "too_many_missing": false,
    "has_constant_columns": true,
    "has_high_cardinality_categoricals": true
  }
}
```

#### Пример вызова через `curl`

```bash
curl -X POST "http://127.0.0.1:8000/quality-flags-from-csv" \
  -F "file=@data/example.csv"
```

---

## Структура проекта (упрощённо)

```text
S04/
  eda-cli/
    pyproject.toml
    README.md
    src/
      eda_cli/
        core.py      # EDA-логика и эвристики качества
        viz.py       # визуализации
        cli.py       # CLI (overview / report)
        api.py       # HTTP-сервис (FastAPI)
    tests/
      test_core.py  # тесты EDA-ядра
    data/
      example.csv
```

---

## Тесты

Запуск тестов:

```bash
uv run pytest -q
```