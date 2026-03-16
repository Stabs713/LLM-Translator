# common.py
import os
import re
from typing import List, Optional

import requests
from dotenv import load_dotenv
from tqdm import tqdm

# Настройки
INPUT_DIR = "inputs"
OUTPUT_DIR = "outputs"

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

# Глобальные переменные и конфигурация API
OPENROUTER_API_URL: Optional[str] = None
OPENROUTER_API_KEY: Optional[str] = None
CURRENT_MODEL: Optional[str] = None

# Рекомендуемые платные модели (дешёвые и качественные для перевода)
PAID_MODELS = [
    {
        "id": "anthropic/claude-3.5-haiku",
        "name": "Claude 3.5 Haiku",
        "price": "$0.80 / 1M tokens",
        "quality": "⭐⭐⭐⭐⭐",
        "description": "Быстрая, точная, идеальна для перевода"
    },
    {
        "id": "google/gemini-flash-1.5",
        "name": "Gemini 1.5 Flash",
        "price": "$0.075 / 1M tokens",
        "quality": "⭐⭐⭐⭐",
        "description": "Очень дешёвая, хорошее качество"
    },
    {
        "id": "openai/gpt-4o-mini",
        "name": "GPT-4o Mini",
        "price": "$0.15 / 1M tokens",
        "quality": "⭐⭐⭐⭐⭐",
        "description": "Отличный баланс цены и качества"
    },
    {
        "id": "anthropic/claude-3-haiku",
        "name": "Claude 3 Haiku",
        "price": "$0.25 / 1M tokens",
        "quality": "⭐⭐⭐⭐",
        "description": "Быстрая и дешёвая"
    },
]

# Список бесплатных моделей (для автоперебора)
FREE_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-flash-1.5:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "meta-llama/llama-3.2-90b-vision-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "liquid/lfm-40b:free",
    "microsoft/phi-3-medium-128k-instruct:free",
]


def load_env_vars() -> None:
    """
    Загружает переменные окружения из .env.
    Требуется как минимум OPENROUTER_API_KEY.
    OPENROUTER_API_URL можно переопределить, по умолчанию используется официальный эндпоинт OpenRouter.
    """
    global OPENROUTER_API_KEY, OPENROUTER_API_URL

    load_dotenv()
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")

    if not OPENROUTER_API_KEY:
        raise ValueError("❌ OPENROUTER_API_KEY не найден в .env. Добавьте его.")


def set_current_model(model_name: str) -> None:
    global CURRENT_MODEL
    CURRENT_MODEL = model_name


def get_current_model() -> Optional[str]:
    return CURRENT_MODEL


def _get_openrouter_headers() -> dict:
    """Возвращает стандартные заголовки для запросов к OpenRouter."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com/llm-translator",
        "X-Title": "LLM Translator",
    }


def openrouter_request(payload: dict, timeout: int = 120) -> Optional[requests.Response]:
    """
    Унифицированный HTTP‑запрос к OpenRouter.

    Возвращает объект Response при успехе или None при ошибке/исключении.
    """
    if not OPENROUTER_API_KEY or not OPENROUTER_API_URL:
        return None

    try:
        response = requests.post(
            OPENROUTER_API_URL,
            json=payload,
            headers=_get_openrouter_headers(),
            timeout=timeout,
        )
        return response
    except Exception:
        return None


def test_model_connection(model_name: str, silent: bool = False) -> bool:
    """Проверяет подключение к модели"""
    if not silent:
        print(f"🔌 Проверка модели: {model_name}...", end=" ")

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "test"}],
        "max_tokens": 10
    }
    try:
        response = openrouter_request(payload, timeout=15)
        if response and response.status_code == 200:
            if not silent:
                print("✅")
            return True
        elif response is not None:
            if not silent:
                print(f"❌ (HTTP {response.status_code})")
            return False
    except Exception as e:
        if not silent:
            print(f"❌ ({str(e)[:50]})")
        return False


def auto_select_free_model() -> Optional[str]:
    """Автоматически находит первую доступную бесплатную модель"""
    print("\n🔍 Автоматический поиск бесплатных моделей...")
    print("-" * 70)

    for model in FREE_MODELS:
        if test_model_connection(model):
            print(f"\n✅ Найдена рабочая модель: {model}")
            return model

    return None


def select_translation_model() -> str:
    """Интерактивный выбор модели с возможностью автоперебора"""
    print("\n" + "="*70)
    print("🤖 ВЫБОР МОДЕЛИ ДЛЯ ПЕРЕВОДА")
    print("="*70)

    print("\n💰 РЕКОМЕНДУЕМЫЕ ПЛАТНЫЕ МОДЕЛИ (лучшее качество):")
    print("-" * 70)
    for i, model in enumerate(PAID_MODELS, 1):
        print(f"{i}. {model['name']}")
        print(f"   ID: {model['id']}")
        print(f"   Цена: {model['price']}")
        print(f"   Качество: {model['quality']}")
        print(f"   {model['description']}")
        print()

    print("\n🆓 БЕСПЛАТНЫЕ ОПЦИИ:")
    print("-" * 70)
    print(f"{len(PAID_MODELS) + 1}. Автоматически найти бесплатную модель")
    print(f"{len(PAID_MODELS) + 2}. Ввести ID модели вручную")

    while True:
        try:
            choice = input(f"\nВыберите вариант (1-{len(PAID_MODELS) + 2}): ").strip()

            if not choice.isdigit():
                print("❌ Введите число.")
                continue

            choice_num = int(choice)

            # Выбор платной модели
            if 1 <= choice_num <= len(PAID_MODELS):
                selected_model = PAID_MODELS[choice_num - 1]["id"]
                print(f"\n🔍 Проверка {PAID_MODELS[choice_num - 1]['name']}...")

                if test_model_connection(selected_model):
                    print(f"✅ Выбрана модель: {selected_model}")
                    return selected_model
                else:
                    print("\n⚠️ Не удалось подключиться к этой модели.")
                    retry = input("Попробовать другую модель? (y/n): ").strip().lower()
                    if retry != 'y':
                        break

            # Автопоиск бесплатной модели
            elif choice_num == len(PAID_MODELS) + 1:
                model = auto_select_free_model()
                if model:
                    return model
                else:
                    print("\n⚠️ Не найдено доступных бесплатных моделей.")
                    retry = input("Попробовать другой вариант? (y/n): ").strip().lower()
                    if retry != 'y':
                        break

            # Ручной ввод
            elif choice_num == len(PAID_MODELS) + 2:
                custom_model = input("\nВведите ID модели (например, anthropic/claude-3.5-haiku): ").strip()
                if custom_model:
                    if test_model_connection(custom_model):
                        print(f"✅ Выбрана модель: {custom_model}")
                        return custom_model
                    else:
                        print("\n⚠️ Не удалось подключиться к указанной модели.")
                        retry = input("Попробовать снова? (y/n): ").strip().lower()
                        if retry != 'y':
                            break
            else:
                print(f"❌ Выберите число от 1 до {len(PAID_MODELS) + 2}.")

        except KeyboardInterrupt:
            print("\n\n❌ Отменено пользователем.")
            raise
        except Exception as e:
            print(f"❌ Ошибка: {e}")

    raise Exception("❌ Не удалось выбрать модель для перевода.")


def chunk_text_by_sentences_safe(text: str, max_tokens: int = 1500) -> List[str]:
    """Разбивает текст на чанки по предложениям"""
    if not text.strip():
        return [text]

    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZА-Я\d(])', text.strip())
    if not sentences:
        return [text]

    chunks = []
    current_chunk = []
    current_len = 0

    for sent in sentences:
        # Кириллица кодируется ~2 байта/символ, токен ≈ 3-4 символа → делим на 3
        tokens = len(sent.encode('utf-8')) // 12

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


def translate_chunk(text: str, retries: int = 3) -> str:
    """Переводит один чанк текста через OpenRouter"""

    if re.fullmatch(r'(__PROTECTED_\d+__|\s|[\\{}\[\]_^&$])+', text):
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

    payload = {
        "model": get_current_model(),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000,
        "temperature": 0.2,
        "top_p": 0.95
    }

    for attempt in range(retries):
        try:
            response = openrouter_request(payload, timeout=120)
            if response and response.status_code == 200:
                result = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if result:
                    return result
            elif response is not None and response.status_code == 429:
                print(f"⚠️ Rate limit (попытка {attempt+1}/{retries})")
                import time
                time.sleep(3)
            elif response is not None:
                print(f"⚠️ HTTP {response.status_code} (попытка {attempt+1}/{retries})")
        except Exception as e:
            print(f"⚠️ Ошибка: {str(e)[:50]} (попытка {attempt+1}/{retries})")
            pass
        if attempt < retries - 1:
            import time
            time.sleep(2)
    print("⚠️ Не удалось получить перевод от модели, возвращаю исходный текст чанка без изменений.")
    return text


def find_main_tex_in_dir(root_dir: str) -> str:
    """
    Находит главный .tex файл в распакованном проекте.

    Логика:
    - собираем все .tex файлы с информацией о глубине вложенности;
    - сортируем так, чтобы сначала шли файлы ближе к корню;
    - среди них ищем первый, где встречается '\\begin{document}';
      если не нашли — берём самый "поверхностный" .tex.

    Возвращает путь к .tex относительно root_dir с прямыми слешами.
    Бросает ValueError, если .tex файлов нет.
    """
    all_tex = []
    for root, _, files in os.walk(root_dir):
        for fname in files:
            if not fname.lower().endswith(".tex"):
                continue
            full_path = os.path.join(root, fname)
            depth = len(os.path.relpath(full_path, root_dir).split(os.sep))
            all_tex.append((full_path, depth))

    if not all_tex:
        raise ValueError("В архиве нет .tex файлов.")

    all_tex.sort(key=lambda x: x[1])

    main_tex_path = None
    for full_path, _ in all_tex:
        try:
            with open(full_path, "r", encoding="utf-8") as fp:
                if r"\begin{document}" in fp.read():
                    main_tex_path = full_path
                    break
        except Exception:
            continue

    if main_tex_path is None:
        main_tex_path = all_tex[0][0]

    rel_path = os.path.relpath(main_tex_path, root_dir).replace(os.sep, "/")
    return rel_path


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
