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

Создайте файл .env на основе примера:
PROXY_API_KEY=ваш_ключ_здесь
# PROXY_API_URL=https://api.proxyapi.ru/openai/v1/chat/completions  # По умолчанию
