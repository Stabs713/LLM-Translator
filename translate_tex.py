import os
import zipfile
import sys
from tqdm import tqdm

# Импорты для LaTeX
try:
    from pylatexenc.latexwalker import (
        LatexWalker,
        LatexMacroNode,
        LatexCharsNode,
        LatexGroupNode,
        LatexEnvironmentNode
    )
except ImportError:
    LatexWalker = None

from common import (
    PROTECTED_MACROS,
    TRANSLATABLE_MACROS,
    PROTECTED_ENVIRONMENTS,
    TRANSLATABLE_ENVIRONMENTS,
    translate_chunk
)

# Глобальные списки для сбора текста
translatable_texts = []
text_spans = []

def translate_latex_text(latex_content, max_tokens=1200):
    global translatable_texts, text_spans
    if LatexWalker is None:
        print("❌ Установите pylatexenc: pip install pylatexenc")
        sys.exit(1)

    translatable_texts = []
    text_spans = []

    walker = LatexWalker(latex_content)
    nodelist, _, _ = walker.get_latex_nodes(pos=0)

    def collect_text(node, inside_math=False, inside_protected=False):
        if isinstance(node, LatexCharsNode):
            text = node.chars
            if text.strip() and not inside_math and not inside_protected:
                start_pos = node.pos
                end_pos = start_pos + len(text)
                translatable_texts.append(text)
                text_spans.append((start_pos, end_pos))
        elif isinstance(node, LatexMacroNode):
            macro_name = node.macroname or ""
            is_protected = macro_name in PROTECTED_MACROS
            if not is_protected and macro_name in TRANSLATABLE_MACROS:
                if node.nodeargd:
                    for arg in node.nodeargd.argnlist:
                        if arg is not None:
                            collect_text(arg, inside_math=inside_math, inside_protected=inside_protected)
        elif isinstance(node, LatexEnvironmentNode):
            env_name = node.envname or ""
            math_env = env_name in {'equation', 'align', 'gather', 'displaymath', 'math'}
            # Явно обрабатываем транслируемые окружения
            if env_name in TRANSLATABLE_ENVIRONMENTS and not math_env:
                for child in node.nodelist:
                    collect_text(child, inside_math=math_env, inside_protected=False)
            # Обычные окружения — если не защищены
            elif env_name not in PROTECTED_ENVIRONMENTS and not math_env:
                for child in node.nodelist:
                    collect_text(child, inside_math=math_env, inside_protected=False)
        elif isinstance(node, LatexGroupNode):
            for child in node.nodelist:
                collect_text(child, inside_math=inside_math, inside_protected=inside_protected)

    for node in nodelist:
        collect_text(node)

    # Переводим текст БЕЗ чанкования (чтобы не ломать короткие фразы в таблицах)
    translated_texts = []
    for text in tqdm(translatable_texts, desc="Перевод LaTeX"):
        # Передаём целиком — без chunk_text_by_paragraphs
        translated = translate_chunk(text)
        translated_texts.append(translated)

    # Заменяем в исходной строке
    result = list(latex_content)
    for i in range(len(text_spans) - 1, -1, -1):
        start, end = text_spans[i]
        result[start:end] = translated_texts[i]

    return ''.join(result)

# --- Извлечение из ZIP ---
def extract_tex_from_zip(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        tex_files = [f for f in zip_ref.namelist() if f.lower().endswith('.tex')]
        if not tex_files:
            raise ValueError("В архиве нет .tex файлов.")
        tex_file = tex_files[0]
        content = zip_ref.read(tex_file).decode('utf-8')
        return os.path.basename(tex_file), content

# --- Добавление поддержки русского ---
def add_russian_preamble(latex_content):
    if r"\documentclass" not in latex_content:
        return latex_content

    lines = []
    for line in latex_content.splitlines():
        if r"\usepackage[" in line and "babel" in line:
            continue
        elif r"\usepackage{babel}" in line:
            continue
        else:
            lines.append(line)

    content_without_babel = "\n".join(lines)

    new_preamble = [
        "% Поддержка русского языка (автоматически добавлено)",
        r"\usepackage{fontspec}",
        r"\usepackage[russian]{babel}",
        r"\usepackage{amsmath}",
        r"\setmainfont{DejaVu Serif}",
        r"\setsansfont{DejaVu Sans}",
        r"\setmonofont{DejaVu Sans Mono}",
        ""
    ]

    if r"\documentclass" in content_without_babel:
        lines = content_without_babel.splitlines()
        new_lines = []
        inserted = False
        for line in lines:
            if r"\documentclass" in line and not inserted:
                new_lines.append(line)
                new_lines.extend(new_preamble)
                inserted = True
            else:
                new_lines.append(line)
        return "\n".join(new_lines)
    else:
        return "\n".join(new_preamble) + "\n" + content_without_babel