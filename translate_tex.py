import os
import zipfile
import sys
from tqdm import tqdm
import re

try:
    from pylatexenc.latexwalker import (
        LatexWalker,
        LatexMacroNode,
        LatexCharsNode,
        LatexGroupNode,
        LatexEnvironmentNode,
        LatexSpecialsNode
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
            new_inside_protected = inside_protected or is_protected
            if node.nodeargd:
                for arg in node.nodeargd.argnlist:
                    if arg is not None:
                        collect_text(arg, inside_math=inside_math, inside_protected=new_inside_protected)
        elif isinstance(node, LatexEnvironmentNode):
            env_name = node.envname or ""
            math_env = env_name in {'equation', 'align', 'gather', 'displaymath', 'math'}
            is_protected_env = env_name in PROTECTED_ENVIRONMENTS
            new_inside_protected = inside_protected or is_protected_env
            for child in node.nodelist:
                collect_text(child, inside_math=math_env, inside_protected=new_inside_protected)
        elif isinstance(node, LatexGroupNode):
            for child in node.nodelist:
                collect_text(child, inside_math=inside_math, inside_protected=inside_protected)
        elif isinstance(node, LatexSpecialsNode):
            pass

    for node in nodelist:
        collect_text(node)

    translated_texts = []
    for text in tqdm(translatable_texts, desc="Перевод LaTeX"):
        translated = translate_chunk(text)
        translated_texts.append(translated)

    result = list(latex_content)
    for i in range(len(text_spans) - 1, -1, -1):
        start, end = text_spans[i]
        del result[start:end]
        for j, char in enumerate(translated_texts[i]):
            result.insert(start + j, char)

    return ''.join(result)

def restore_bibliography_commands(original_content, translated_content):
    orig_style = re.search(r'\\bibliographystyle\{([^}]+)\}', original_content)
    if orig_style:
        style_name = orig_style.group(1)
        translated_content = re.sub(
            r'\\bibliographystyle\{[^}]*\}',
            lambda m: f'\\bibliographystyle{{{style_name}}}',
            translated_content
        )

    orig_bib = re.search(r'\\bibliography\{([^}]+)\}', original_content)
    if orig_bib:
        bib_name = orig_bib.group(1)
        translated_content = re.sub(
            r'\\bibliography\{[^}]*\}',
            lambda m: f'\\bibliography{{{bib_name}}}',
            translated_content
        )

    return translated_content

def process_zip_for_translation(zip_path, output_dir):
    import tempfile
    import zipfile
    import os

    with tempfile.TemporaryDirectory() as tmp_extract_dir:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_extract_dir)

        tex_files = []
        main_tex = None
        for root, _, files in os.walk(tmp_extract_dir):
            for f in files:
                if f.lower().endswith('.tex'):
                    full_path = os.path.join(root, f)
                    tex_files.append(full_path)
                    if main_tex is None:
                        try:
                            with open(full_path, 'r', encoding='utf-8') as fp:
                                content = fp.read()
                                if r'\begin{document}' in content:
                                    main_tex = full_path
                        except:
                            pass

        if not tex_files:
            raise ValueError("В архиве нет .tex файлов.")

        if main_tex is None:
            main_tex = tex_files[0]
            print("⚠️ Не найден \\begin{document}. Используем первый .tex как главный.")

        for tex_path in tex_files:
            with open(tex_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            content_with_preamble = add_russian_preamble(original_content)
            translated = translate_latex_text(content_with_preamble)
            translated = restore_bibliography_commands(original_content, translated)
            docclass_match = re.search(r'\\documentclass(?:\[[^\]]*\])?\{[^\}]+\}', original_content)
            if docclass_match:
                orig_docclass = docclass_match.group(0)
                translated = re.sub(
                    r'\\documentclass(?:\[[^\]]*\])?\{[^\}]+\}',
                    lambda m: orig_docclass,
                    translated,
                    count=1
                )
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(translated)

        base_name = os.path.splitext(os.path.basename(zip_path))[0]
        output_zip = os.path.join(output_dir, f"{base_name}_translated.zip")
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            for root, _, files in os.walk(tmp_extract_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arc_path = os.path.relpath(full_path, tmp_extract_dir)
                    new_zip.write(full_path, arc_path)

        main_tex_rel = os.path.relpath(main_tex, tmp_extract_dir)
        return output_zip, main_tex_rel

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