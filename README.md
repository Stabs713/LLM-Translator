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
