import re
import sys
from docx import Document
from tqdm import tqdm
from common import translate_chunk, chunk_text_by_sentences_safe

REFERENCE_TITLES = {
    'references', 'reference',
    'bibliography', 'bibliographie',
    'литература', 'список литературы', 'источники'
}

def mask_display_formulas(text):
    placeholders = []
    
    def repl(match):
        orig = match.group(0)
        cleaned = re.sub(r'\\\s*([a-zA-Z]+)\s*\{', r'\\\1{', orig)
        cleaned = re.sub(r'\s*([_{}=(),;:\.\+\-\*\/\^])\s*', r'\1', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        placeholders.append(cleaned)
        return f"__MATH_{len(placeholders)-1}__"
    
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

    in_references = False

    for para in tqdm(doc.paragraphs, desc="Перевод .docx"):
        if not para.text.strip():
            continue

        para_text_clean = para.text.strip().lower()
        if para_text_clean in REFERENCE_TITLES:
            in_references = True
            continue

        if in_references:
            continue

        full_text = "".join(run.text for run in para.runs)
        if not full_text.strip():
            continue

        clean_text, formulas = mask_display_formulas(full_text)
        chunks = chunk_text_by_sentences_safe(clean_text)
        translated = " ".join(
            translate_chunk(chunk) 
            for chunk in chunks if chunk.strip()
        )
        final_text = unmask_formulas(translated, formulas)

        para.clear()
        para.add_run(final_text)

    doc.save(output_path)
    print(f"\n✅ Перевод завершён: {output_path}")