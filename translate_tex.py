import os
import zipfile
import sys
from tqdm import tqdm
import re

from common import translate_chunk


def translate_latex_text(latex_content, max_chunk_size=2000):
    """
    Полный перевод LaTeX с сохранением структуры документа
    """

    # Шаг 1: Разделяем на преамбулу, begin/end document и тело
    begin_doc = r'\begin{document}'
    end_doc = r'\end{document}'

    if begin_doc not in latex_content:
        # Нет структуры документа - переводим всё как есть
        return translate_body(latex_content, max_chunk_size)

    # Разделяем
    parts = latex_content.split(begin_doc, 1)
    preamble = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    if end_doc in rest:
        body_parts = rest.split(end_doc, 1)
        body = body_parts[0]
        postamble = end_doc + body_parts[1] if len(body_parts) > 1 else end_doc
    else:
        body = rest
        postamble = ""

    # Шаг 2: Обрабатываем преамбулу - переводим \title и \author
    translated_preamble = translate_preamble(preamble)

    # Шаг 3: Переводим тело документа
    translated_body = translate_body(body, max_chunk_size)

    # Шаг 4: Собираем документ обратно
    return translated_preamble + begin_doc + translated_body + postamble


def translate_preamble(preamble):
    """Переводит только \title{} в преамбуле, автора оставляет"""
    result = preamble

    # Переводим \title{...}
    def translate_title(match):
        title_text = match.group(1)
        # Защищаем математику
        protected = []
        def protect(m):
            protected.append(m.group(0))
            return f"__P{len(protected)-1}__"
        title_text = re.sub(r'\$[^$]+\$', protect, title_text)

        # Переводим
        translated = translate_chunk(title_text)

        # Восстанавливаем
        for i in range(len(protected)-1, -1, -1):
            translated = translated.replace(f"__P{i}__", protected[i])

        return f"\\title{{{translated}}}"

    result = re.sub(r'\\title\{([^}]+)\}', translate_title, result)

    # Автора НЕ переводим (обычно имена собственные)

    return result


def translate_body(body, max_chunk_size=2000):
    """Переводит тело документа с защитой математики и технических команд"""

    protected_blocks = []

    def protect_block(match):
        protected_blocks.append(match.group(0))
        return f"__PROTECTED_{len(protected_blocks)-1}__"

    text = body

    # Защищаем математику
    # Display math
    text = re.sub(r'\\\[.*?\\\]', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{equation\*?\}.*?\\end\{equation\*?\}', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{align\*?\}.*?\\end\{align\*?\}', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{gather\*?\}.*?\\end\{gather\*?\}', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{multline\*?\}.*?\\end\{multline\*?\}', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\$\$.*?\$\$', protect_block, text, flags=re.DOTALL)

    # Inline math
    text = re.sub(r'\$[^$]+\$', protect_block, text)
    text = re.sub(r'\\\(.*?\\\)', protect_block, text, flags=re.DOTALL)

    # Технические окружения
    for env in ['verbatim', 'lstlisting', 'minted', 'code', 'tikzpicture', 'asy']:
        pattern = rf'\\begin\{{{env}\*?\}}.*?\\end\{{{env}\*?\}}'
        text = re.sub(pattern, protect_block, text, flags=re.DOTALL)

    # Технические команды (сами команды, не аргументы)
    text = re.sub(r'(\\label\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\ref\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\eqref\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\cite(?:\[[^\]]*\])?\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\url\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\href\{[^}]*\}\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\includegraphics(?:\[[^\]]*\])?\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\bibliographystyle\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\bibliography\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\addbibresource\{[^}]*\})', protect_block, text)

    # Разбиваем на параграфы
    paragraphs = re.split(r'(\n\s*\n)', text)

    translated_parts = []

    for para in tqdm(paragraphs, desc="Перевод"):
        if not para.strip():
            translated_parts.append(para)
            continue

        # Если только защищённые блоки - не переводим
        if re.fullmatch(r'[\s__PROTECTED_\d+__]+', para):
            translated_parts.append(para)
            continue

        # Проверяем, есть ли что переводить
        temp = para
        for i in range(len(protected_blocks)):
            temp = temp.replace(f"__PROTECTED_{i}__", "")

        # Если после удаления защищённого осталось только пробелы/LaTeX команды
        if not re.search(r'[a-zA-Z]{2,}', temp):
            translated_parts.append(para)
            continue

        # Переводим
        if len(para) > max_chunk_size:
            # Разбиваем на предложения
            sentences = re.split(r'(?<=[.!?])\s+', para)
            chunks = []
            current = []
            current_len = 0

            for sent in sentences:
                if current_len + len(sent) > max_chunk_size and current:
                    chunks.append(' '.join(current))
                    current = [sent]
                    current_len = len(sent)
                else:
                    current.append(sent)
                    current_len += len(sent)

            if current:
                chunks.append(' '.join(current))

            translated = ' '.join(translate_chunk(chunk) for chunk in chunks if chunk.strip())
        else:
            translated = translate_chunk(para)

        translated_parts.append(translated)

    result = ''.join(translated_parts)

    # Восстанавливаем защищённые блоки
    for i in range(len(protected_blocks) - 1, -1, -1):
        result = result.replace(f"__PROTECTED_{i}__", protected_blocks[i])

    return result


def restore_bibliography_commands(original_content, translated_content):
    """Восстанавливает библиографические команды из оригинала"""
    orig_style = re.search(r'\\bibliographystyle\{([^}]+)\}', original_content)
    if orig_style:
        style_name = orig_style.group(1)
        translated_content = re.sub(
            r'\\bibliographystyle\{[^}]*\}',
            f'\\\\bibliographystyle{{{style_name}}}',
            translated_content,
            count=1
        )

    orig_bib = re.search(r'\\bibliography\{([^}]+)\}', original_content)
    if orig_bib:
        bib_name = orig_bib.group(1)
        translated_content = re.sub(
            r'\\bibliography\{[^}]*\}',
            f'\\\\bibliography{{{bib_name}}}',
            translated_content,
            count=1
        )

    return translated_content


def process_zip_for_translation(zip_path, output_dir):
    """Обрабатывает ZIP-архив с LaTeX файлами"""
    import tempfile

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
            print(f"\n📄 Перевод файла: {os.path.basename(tex_path)}")
            with open(tex_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            content_with_preamble = add_russian_preamble(original_content)
            translated = translate_latex_text(content_with_preamble)
            translated = restore_bibliography_commands(original_content, translated)

            # Восстанавливаем \documentclass из оригинала
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
    """Добавляет поддержку русского языка в преамбулу"""
    if r"\documentclass" not in latex_content:
        return latex_content

    # Удаляем старые babel команды
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
