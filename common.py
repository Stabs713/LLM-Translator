import os
import requests
from tqdm import tqdm
from dotenv import load_dotenv
import re

# Настройки
INPUT_DIR = "inputs"
OUTPUT_DIR = "outputs"

# Защищённые макросы — НЕ переводить
PROTECTED_MACROS = {
    'cite', 'ref', 'label', 'eqref', 'footnote', 'url', 'href', 'includegraphics',
    'input', 'include', 'usepackage', 'documentclass', 'bibitem', 'index',
    'begin', 'end', 'hline', 'cline', 'multicolumn', 'multirow'
}

# Макросы, чьи аргументы МОЖНО переводить
TRANSLATABLE_MACROS = {
    'section', 'subsection', 'subsubsection', 'chapter', 'part',
    'caption', 'title', 'author', 'date', 'abstract',
    'textbf', 'textit', 'emph', 'underline', 'item', 'texttt'
}

# Защищённые окружения (НЕ переводим)
PROTECTED_ENVIRONMENTS = {
    'equation', 'align', 'gather', 'multline', 'eqnarray',
    'verbatim', 'lstlisting', 'code', 'minted', 'displaymath', 'math',
    'figure'
}

# Транслируемые окружения (переводим содержимое)
TRANSLATABLE_ENVIRONMENTS = {
    'tabular',
    'table',
    'itemize',
    'enumerate'
}

# Глобальные переменные
PROXY_API_URL = None
PROXY_API_KEY = None
CURRENT_MODEL = "gpt-4o"

def load_env_vars():
    global PROXY_API_URL, PROXY_API_KEY
    load_dotenv()
    PROXY_API_URL = os.getenv("PROXY_API_URL", "https://api.proxyapi.ru/openai/v1/chat/completions")
    PROXY_API_KEY = os.getenv("PROXY_API_KEY")
    if not PROXY_API_KEY:
        raise ValueError("❌ PROXY_API_KEY не найден в .env. Добавьте его.")

def set_current_model(model_name):
    global CURRENT_MODEL
    CURRENT_MODEL = model_name

def get_current_model():
    return CURRENT_MODEL

def chunk_text_by_sentences_safe(text, max_tokens=1200):
    """
    Разбивает текст на чанки, но НИКОГДА не обрывает предложение.
    Если предложение не помещается в текущий чанк — оно идёт в следующий.
    """
    if not text.strip():
        return [text]

    # Разделяем на предложения (с учётом . ! ? и возможных сокращений)
    sentences = re.split(r'(?<=[.!?])\s+(?=[А-ЯA-Z])', text.strip())
    if not sentences:
        return [text]

    chunks = []
    current_chunk = []
    current_len = 0

    for sent in sentences:
        tokens = len(sent) // 4  # грубая оценка

        # Если текущий чанк пуст — берём предложение даже если оно длинное
        if not current_chunk:
            current_chunk = [sent]
            current_len = tokens
        # Если предложение помещается — добавляем
        elif current_len + tokens <= max_tokens:
            current_chunk.append(sent)
            current_len += tokens
        # Если НЕ помещается — закрываем чанк БЕЗ этого предложения
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sent]  # начинаем новый чанк с этого предложения
            current_len = tokens

    # Добавляем последний чанк
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def translate_chunk(text, retries=3):
    prompt = f"""Переведи ТОЛЬКО текст с английского на русский. Сохрани:
- все формулы, команды LaTeX (\\section, \\texttt, \\url, \\begin{{...}}, и т.д.) без изменений,
- исходную структуру и пунктуацию.
НЕ ДОБАВЛЯЙ ничего от себя: никаких комментариев, пояснений или фраз вроде "Вы не предоставили текст".

Текст:
{text}"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PROXY_API_KEY}"
    }
    
    payload = {
        "model": get_current_model(),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
        "temperature": 0.1,
        "top_p": 0.9
    }

    for attempt in range(retries):
        try:
            response = requests.post(PROXY_API_URL, json=payload, headers=headers, timeout=120)
            if response.status_code == 200:
                result = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if result:
                    return result
        except Exception as e:
            print(f"⚠️ Ошибка запроса (попытка {attempt+1}/{retries}): {e}")
            pass
        if attempt < retries - 1:
            import time
            time.sleep(1)
    return text

def test_model_connection(model_name):
    print(f"🌐 Проверка подключения к модели: {model_name}")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PROXY_API_KEY}"
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5
    }
    try:
        response = requests.post(PROXY_API_URL, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"✅ Подключение к модели {model_name} успешно!")
            return True
        else:
            print(f"❌ Ошибка HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Не удалось подключиться: {e}")
        return False

def get_files_list(directory):
    files = [f for f in os.listdir(directory) if f.lower().endswith(('.docx', '.tex', '.zip'))]
    return sorted(files)

def get_tex_files_list(directory):
    files = [f for f in os.listdir(directory) if f.lower().endswith('.tex')]
    return sorted(files)

def select_file_by_number(total_count):
    while True:
        try:
            choice = int(input(f"\nВыберите номер файла (1-{total_count}): ").strip())
            if 1 <= choice <= total_count:
                return choice
            else:
                print(f"❌ Номер должен быть от 1 до {total_count}.")
        except ValueError:
            print("❌ Введите число.")

def select_main_action():
    print("\nЧто вы хотите сделать?")
    print("1. Перевести файл (.docx, .tex, .zip)")
    print("2. Скомпилировать .tex в PDF")
    while True:
        try:
            choice = int(input("Выберите действие (1 или 2): ").strip())
            if choice == 1:
                return "translate"
            elif choice == 2:
                return "compile"
            else:
                print("❌ Введите 1 или 2.")
        except ValueError:
            print("❌ Введите число.")

def select_translation_model():
    model_names = ["gpt-4o", "gpt-4.1"]
    print("\nДоступные модели для перевода:")
    for i, name in enumerate(model_names, 1):
        print(f"  {i}. {name}")
    while True:
        try:
            choice = int(input(f"\nВыберите модель (1-{len(model_names)}): ").strip())
            if 1 <= choice <= len(model_names):
                selected = model_names[choice - 1]
                print(f"✅ Выбрана модель: {selected}")
                return selected
            else:
                print(f"❌ Номер должен быть от 1 до {len(model_names)}.")
        except ValueError:
            print("❌ Введите число.")