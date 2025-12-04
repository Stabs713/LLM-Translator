import re
import sys
from docx import Document
from tqdm import tqdm
from common import translate_chunk, chunk_text_by_sentences_safe


def mask_display_formulas(text):
    """Маскирует ТОЛЬКО формулы вида $$...$$ (display math)"""
    placeholders = []
    
    def repl(match):
        orig = match.group(0)
        # Убираем лишние пробелы внутри формулы
        cleaned = re.sub(r'\\\s*([a-zA-Z]+)\s*\{', r'\\\1{', orig)      # \ mathcal {L} → \mathcal{L}
        cleaned = re.sub(r'\s*([_{}=(),;:\.\+\-\*\/\^])\s*', r'\1', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        placeholders.append(cleaned)
        return f"__MATH_{len(placeholders)-1}__"
    
    # Только блочные формулы в $$...$$
    text = re.sub(r'\$\$(.+?)\$\$', repl, text, flags=re.DOTALL)
    
    return text, placeholders


def unmask_formulas(text, placeholders):
    for i in range(len(placeholders) - 1, -1, -1):
        text = text.replace(f"__MATH_{i}__", placeholders[i])
    return text


def translate_docx(input_path, output_path):
    try:
        doc = Document(input_path)
    except Exception as e:
        print(f"❌ Не удалось открыть .docx: {e}")
        sys.exit(1)

    for para in tqdm(doc.paragraphs, desc="Перевод .docx"):
        if not para.text.strip():
            continue

        # Собираем полный текст параграфа
        full_text = "".join(run.text for run in para.runs)
        if not full_text.strip():
            continue

        # Маскируем только $$...$$
        clean_text, formulas = mask_display_formulas(full_text)

        # Переводим
        chunks = chunk_text_by_sentences_safe(clean_text)
        translated = " ".join(
            translate_chunk(chunk) 
            for chunk in chunks if chunk.strip()
        )

        # Восстанавливаем формулы
        final_text = unmask_formulas(translated, formulas)

        # Заменяем параграф
        para.clear()
        para.add_run(final_text)

    doc.save(output_path)
    print(f"\n✅ Перевод завершён: {output_path}")