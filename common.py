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
    # Базовые команды документа
    'documentclass', 'usepackage', 'RequirePackage',

    # Метки и ссылки
    'label', 'ref', 'eqref', 'pageref', 'autoref',

    # Библиография
    'cite', 'bibitem', 'bibliographystyle', 'bibliography', 'nocite',

    # Графика и файлы
    'includegraphics', 'input', 'include', 'subfile',

    # Гиперссылки
    'url', 'href', 'footnotemark', 'footnotetext',

    # Таблицы и матрицы
    'hline', 'cline', 'multicolumn', 'multirow', 'cellcolor',

    # Оформление
    'pagestyle', 'pagenumbering', 'thispagestyle',

    # Математика (команды, а не содержимое)
    'newcommand', 'renewcommand', 'DeclareMathOperator',

    # Индекс и глоссарии
    'index', 'gls', 'glsadd', 'printglossary',

    # Прочие технические
    'begin', 'end',
    'addbibresource',
    'usetikzlibrary', 'usepgflibrary',
    'hypersetup',
    'def', 'let',
}

# Макросы, чьи аргументы МОЖНО переводить
TRANSLATABLE_MACROS = {
    # Структура документа
    'section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph',
    'chapter', 'part', 'title', 'author', 'date', 'affil',

    # Оформление текста
    'caption', 'shortcaption',
    'textbf', 'textit', 'emph', 'underline', 'texttt', 'textsf', 'textrm',
    'textsc', 'textsl', 'textsuperscript', 'textsubscript',

    # Списки и абзацы
    'item', 'footnote',

    # Абстракт и блоки
    'abstract', 'keywords',

    # Теоремы и определения
    'theorem', 'lemma', 'proposition', 'definition', 'corollary',
}

# Защищённые окружения (НЕ переводим содержимое)
PROTECTED_ENVIRONMENTS = {
    # Математика
    'equation', 'equation*', 'align', 'align*', 'gather', 'gather*',
    'multline', 'multline*', 'eqnarray', 'eqnarray*', 'displaymath',
    'math', '$',

    # Код и verbatim
    'verbatim', 'lstlisting', 'minted', 'code', 'Verbatim',

    # Прочие технические
    'tikzpicture', 'asy', 'pspicture',
}

# Транслируемые окружения (переводим содержимое)
TRANSLATABLE_ENVIRONMENTS = {
    'table', 'figure',
    'center', 'flushleft', 'flushright',
    'quote', 'quotation', 'verse',
    'itemize', 'enumerate', 'description',
    'tabular', 'tabularx', 'tabulary', 'longtable',
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


def chunk_text_by_sentences_safe(text, max_tokens=1500):
    """Разбивает текст на чанки по предложениям с улучшенным regex"""
    if not text.strip():
        return [text]

    # Улучшенный regex: учитывает цифры и скобки в начале предложения
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZА-Я\d(])', text.strip())
    if not sentences:
        return [text]

    chunks = []
    current_chunk = []
    current_len = 0

    for sent in sentences:
        tokens = len(sent) // 4

        if not current_chunk:
            current_chunk = [sent]
            current_len = tokens
        elif current_len + tokens <= max_tokens:
            current_chunk.append(sent)
            current_len += tokens
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sent]
            current_len = tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def translate_chunk(text, retries=3):
    """Переводит один чанк текста с улучшенным промптом"""

    # Если текст состоит только из LaTeX команд и placeholder'ов, не переводим
    if re.fullmatch(r'[\s\\{}\[\]_^&$__PROTECTED_\d+__]+', text):
        return text

    prompt = f"""Переведи весь английский текст на русский. КРИТИЧЕСКИ ВАЖНО:

1. Переводи АБСОЛЮТНО ВСЁ что является текстом (слова, заголовки, подписи, содержимое таблиц)
2. НЕ ТРОГАЙ:
   - Математические формулы и символы: $...$, $$...$$, \\[...\\], dXt, µ, σ, Wt и т.д.
   - LaTeX команды: \\section, \\caption, \\textbf, \\begin, \\end
   - Структуру таблиц: &, \\\\, \\hline
   - Маркеры __PROTECTED_N__
3. Переводи содержимое внутри фигурных скобок: \\section{{Introduction}} → \\section{{Введение}}
4. Переводи содержимое таблиц: Parameter → Параметр, Value → Значение
5. НЕ добавляй комментарии, пояснения, не пиши "Вот перевод"

Текст для перевода:
{text}

Переведённый текст:"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PROXY_API_KEY}"
    }

    payload = {
        "model": get_current_model(),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 3000,
        "temperature": 0.2,
        "top_p": 0.95
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
    """Проверяет подключение к модели"""
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
    """Получает список файлов для перевода"""
    files = [f for f in os.listdir(directory) if f.lower().endswith(('.docx', '.tex', '.zip'))]
    return sorted(files)


def get_tex_files_list(directory):
    """Получает список .tex файлов"""
    files = [f for f in os.listdir(directory) if f.lower().endswith('.tex')]
    return sorted(files)


def select_file_by_number(total_count):
    """Выбор файла по номеру"""
    while True:
        try:
            choice = int(input(f"\nВыберите номер файла (1-{total_count}): ").strip())
            if 1 <= choice <= total_count:
                return choice
            else:
                print(f"❌ Номер должен быть от 1 до {total_count}.")
        except ValueError:
            print("❌ Введите число.")


def select_translation_model():
    """Выбор модели перевода"""
    model_names = ["gpt-4o", "gpt-4o-mini"]
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
