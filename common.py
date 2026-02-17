import os
import requests
from tqdm import tqdm
import re
import json

# Настройки
INPUT_DIR = "inputs"
OUTPUT_DIR = "outputs"

# URL локального сервера Ollama
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Защищённые макросы — НЕ переводить
PROTECTED_MACROS = {
    'documentclass', 'usepackage', 'RequirePackage',
    'label', 'ref', 'eqref', 'pageref', 'autoref',
    'cite', 'bibitem', 'bibliographystyle', 'bibliography', 'nocite',
    'includegraphics', 'input', 'include', 'subfile',
    'url', 'href', 'footnotemark', 'footnotetext',
    'hline', 'cline', 'multicolumn', 'multirow', 'cellcolor',
    'pagestyle', 'pagenumbering', 'thispagestyle',
    'newcommand', 'renewcommand', 'DeclareMathOperator',
    'index', 'gls', 'glsadd', 'printglossary',
    'begin', 'end', 'addbibresource',
    'usetikzlibrary', 'usepgflibrary',
    'hypersetup', 'def', 'let',
}

TRANSLATABLE_MACROS = {
    'section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph',
    'chapter', 'part', 'title', 'author', 'date', 'affil',
    'caption', 'shortcaption',
    'textbf', 'textit', 'emph', 'underline', 'texttt', 'textsf', 'textrm',
    'textsc', 'textsl', 'textsuperscript', 'textsubscript',
    'item', 'footnote',
    'abstract', 'keywords',
    'theorem', 'lemma', 'proposition', 'definition', 'corollary',
}

PROTECTED_ENVIRONMENTS = {
    'equation', 'equation*', 'align', 'align*', 'gather', 'gather*',
    'multline', 'multline*', 'eqnarray', 'eqnarray*', 'displaymath',
    'math', '$',
    'verbatim', 'lstlisting', 'minted', 'code', 'Verbatim',
    'tikzpicture', 'asy', 'pspicture',
}

TRANSLATABLE_ENVIRONMENTS = {
    'table', 'figure',
    'center', 'flushleft', 'flushright',
    'quote', 'quotation', 'verse',
    'itemize', 'enumerate', 'description',
    'tabular', 'tabularx', 'tabulary', 'longtable',
}

# Глобальная переменная для текущей модели
CURRENT_MODEL = None


def get_ollama_models():
    """Получает список установленных локальных моделей через Ollama API"""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [model['name'] for model in data.get('models', [])]
        else:
            print(f"⚠️ Ошибка подключения к Ollama: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"⚠️ Не удалось подключиться к Ollama ({OLLAMA_HOST}). Убедитесь, что сервис запущен.")
        print(f"   Детали: {str(e)}")
        return []


def set_current_model(model_name):
    global CURRENT_MODEL
    CURRENT_MODEL = model_name


def get_current_model():
    return CURRENT_MODEL


def select_translation_model():
    """Интерактивный выбор локальной модели"""
    print("\n" + "="*70)
    print("🤖 ВЫБОР ЛОКАЛЬНОЙ МОДЕЛИ (OLLAMA)")
    print("="*70)

    # Получаем доступные модели
    available_models = get_ollama_models()

    if not available_models:
        print("\n❌ Не найдено установленных моделей Ollama.")
        print("💡 Запусти команду в терминале: ollama pull qwen2.5:7b (или другую)")
        raise Exception("Нет доступных моделей.")

    print("\n✅ Доступные модели:")
    print("-" * 70)
    for i, model in enumerate(available_models, 1):
        print(f"  {i}. {model}")
    
    print("-" * 70)
    print(f"  {len(available_models) + 1}. Ввести имя модели вручную")

    while True:
        try:
            choice = input(f"\nВыберите вариант (1-{len(available_models) + 1}): ").strip()

            if not choice.isdigit():
                print("❌ Введите число.")
                continue

            choice_num = int(choice)

            # Выбор из списка
            if 1 <= choice_num <= len(available_models):
                selected_model = available_models[choice_num - 1]
                print(f"\n✅ Выбрана модель: {selected_model}")
                return selected_model

            # Ручной ввод
            elif choice_num == len(available_models) + 1:
                custom_model = input("\nВведите имя модели (например, qwen2.5:72b): ").strip()
                if custom_model:
                    print(f"\n🔍 Проверка наличия модели {custom_model}...")
                    # Быстрая проверка через запрос к конкретной модели (опционально)
                    # Или просто доверяем пользователю
                    print(f"✅ Выбрана модель: {custom_model}")
                    return custom_model
            else:
                print(f"❌ Выберите число от 1 до {len(available_models) + 1}.")

        except KeyboardInterrupt:
            print("\n\n❌ Отменено пользователем.")
            raise
        except Exception as e:
            print(f"❌ Ошибка: {e}")

    raise Exception("❌ Не удалось выбрать модель.")


def chunk_text_by_sentences_safe(text, max_tokens=1500):
    """Разбивает текст на чанки по предложениям (эвристически по длине)"""
    if not text.strip():
        return [text]

    # Простое разбиение по точкам с сохранением разделителей
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZА-Я\d(])', text.strip())
    if not sentences:
        return [text]

    chunks = []
    current_chunk = []
    current_len = 0

    for sent in sentences:
        # Грубая оценка токенов (1 токен ~ 4 символа для смешанного текста)
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
    """Переводит один чанк текста через локальную Ollama"""

    # Если текст состоит только из спецсимволов и плейсхолдеров, не переводим
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
5. НЕ добавляй комментарии, пояснения, не пиши "Вот перевод". Выдай ТОЛЬКО переведенный текст.

Текст для перевода:
{text}

Переведённый текст:"""

    payload = {
        "model": get_current_model(),
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.95,
            "num_predict": 4096  # Лимит на вывод
        }
    }

    for attempt in range(retries):
        try:
            response = requests.post(
                f"{OLLAMA_HOST}/api/chat", 
                json=payload, 
                timeout=120  # Локальная модель может думать дольше на больших чанках
            )
            
            if response.status_code == 200:
                result = response.json().get("message", {}).get("content", "").strip()
                if result:
                    return result
                else:
                    print(f"⚠️ Пустой ответ от модели (попытка {attempt+1}/{retries})")
            else:
                print(f"⚠️ Ошибка Ollama HTTP {response.status_code}: {response.text[:100]} (попытка {attempt+1}/{retries})")
                
        except Exception as e:
            print(f"⚠️ Ошибка соединения: {str(e)[:50]} (попытка {attempt+1}/{retries})")
        
        if attempt < retries - 1:
            import time
            time.sleep(2)
            
    return text  # Возвращаем оригинал если все попытки провалились


def get_files_list(directory):
    if not os.path.exists(directory):
        return []
    files = [f for f in os.listdir(directory) if f.lower().endswith(('.docx', '.tex', '.zip'))]
    return sorted(files)


def get_tex_files_list(directory):
    if not os.path.exists(directory):
        return []
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
        except KeyboardInterrupt:
            raise