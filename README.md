# LLM-Translator + PDF Converter

Утилита для перевода научных статей и документов из форматов **LaTeX (.tex, .zip)** и **DOCX** на русский язык с помощью LLM через OpenRouter и последующей компиляции в **PDF** через Docker (TeX Live).

## Возможности

- Перевод отдельных `.tex` файлов и целых LaTeX‑проектов в `.zip`.
- Перевод `.docx` c сохранением OMML‑формул и математических выражений.
- Автоматическое добавление поддержки русского языка в преамбуле LaTeX.
- Коррекция типичных артефактов LLM в `.tex` и `.bib`.
- Компиляция в PDF через Docker (`texlive/texlive`, XeLaTeX / LuaLaTeX, поддержка MDPI).
- Два режима работы:
  - **CLI** (через аргументы командной строки).
  - **Интерактивное меню** (без аргументов).

## Установка

1. Создайте и активируйте виртуальное окружение (рекомендуется):

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

3. Установите и запустите **Docker Desktop**. Образ `texlive/texlive` будет подтянут автоматически при первой компиляции.

4. Создайте файл `.env` в корне проекта и добавьте ключ OpenRouter:

```bash
OPENROUTER_API_KEY=ваш_ключ
# опционально, если хотите переопределить endpoint
# OPENROUTER_API_URL=https://openrouter.ai/api/v1/chat/completions
```

## Структура проекта

- `main.py` — точка входа, CLI и интерактивное меню.
- `common.py` — общие настройки, работа с OpenRouter, выбор модели, разбиение текста на чанки и т.п.
- `translate_tex.py` — логика перевода LaTeX, работа с преамбулой, ZIP‑архивами и защитой формул.
- `translate_docx.py` — перевод DOCX с сохранением OMML‑формул.
- `pdf_converter.py` — компиляция `.tex`/`.zip` в PDF внутри Docker.
- `inputs/` — входные файлы (`.tex`, `.zip`, `.docx`).
- `outputs/` — результаты перевода.

## Запуск

### 1. Интерактивный режим

Просто запустите:

```bash
python main.py
```

Далее появится меню:

- `1` — перевести и (опционально) скомпилировать `.tex`, `.zip` или `.docx`.
- `2` — только скомпилировать `.tex` или `.zip` в PDF.
- `3` — выход.

Файлы берутся из папки `inputs`, результаты складываются в `outputs`.

### 2. CLI‑режим

#### Только компиляция

```bash
python main.py --mode compile --file path/to/file.tex
python main.py --mode compile --file path/to/archive.zip
```

#### Перевод (с опциональной компиляцией)

```bash
python main.py --mode translate --file path/to/file.tex --model anthropic/claude-3.5-haiku --compile
python main.py --mode translate --file path/to/file.docx --model openai/gpt-4o-mini
python main.py --mode translate --file path/to/project.zip --compile
```

- `--mode translate` — режим перевода.
- `--file` — путь к входному `.tex`, `.zip` или `.docx`. Если не указан, будет интерактивный выбор из папки `inputs`.
- `--model` — ID модели OpenRouter. Если не указан, модель выбирается интерактивно.
- `--compile` — автоматически скомпилировать `.tex`/`.zip` после перевода в PDF.

## Дополнительно

- Для ZIP‑проектов автоматически ищется главный `.tex` файл (с `\begin{document}`, приоритет у файлов ближе к корню).
- В `translate_docx` по умолчанию не переводится раздел литературы (после заголовков вроде `References` или `Литература`), чтобы не ломать библиографию. Это поведение можно изменить параметром `skip_references` внутри кода.
- Перед компиляцией `.bib` файлы автоматически чуть корректируются (пробелы в ключах, дубликаты), что повышает шанс успешной сборки.

## 🚀 Быстрый старт

### 1. Установка

```bash
# Клонируем репозиторий
git clone https://github.com/yourusername/llm-translator.git
cd llm-translator

# Создаем виртуальное окружение (опционально, но рекомендуется)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 2. Настройка .env

В корне проекта создайте файл `.env` со следующим содержимым:

```dotenv
OPENROUTER_API_KEY=ваш_ключ_OpenRouter_здесь
# Необязательно: можно переопределить URL, если используете прокси
# OPENROUTER_API_URL=https://openrouter.ai/api/v1/chat/completions
```

### 3. Папки для файлов

- входные файлы кладите в папку `inputs` (`.tex`, `.zip`, `.docx`);
- результаты перевода и готовые PDF будут появляться в папке `outputs`.

### 4. Запуск (интерактивный режим)

```bash
python main.py
```

Далее в консоли:
- выберите режим (перевод + компиляция или только компиляция),
- выберите модель перевода,
- выберите файл из списка.

### 5. Запуск (CLI‑режим без вопросов)

Вы можете управлять программой через параметры командной строки:

```bash
# Перевод файла с последующей компиляцией (если .tex или .zip)
python main.py --mode translate --file inputs/paper.tex --model openai/gpt-4o-mini --compile

# Только компиляция .tex в PDF
python main.py --mode compile --file inputs/paper.tex

# Только компиляция .zip в PDF
python main.py --mode compile --file inputs/archive.zip
