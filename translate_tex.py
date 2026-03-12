# translate_tex.py
import os
import zipfile
import sys
from tqdm import tqdm
import re

from common import translate_chunk

# Файлы, которые НЕ нужно переводить
EXCLUDE_FILES = {
    'journalnames.tex',
    'mdpi.cls',
    'Definitions.tex',
    'reference.bib',
    'bibliography.bib',
}

# Расширения файлов, которые НЕ переводим
EXCLUDE_EXTENSIONS = {
    '.bib',  # Библиография
    '.bst',  # Стили библиографии
    '.cls',  # Классы документов
    '.sty',  # Пакеты стилей
}

def should_translate_file(filename):
    """Проверяет, нужно ли переводить файл"""
    basename = os.path.basename(filename).lower()
    
    if basename in {name.lower() for name in EXCLUDE_FILES}:
        return False
    
    _, ext = os.path.splitext(basename)
    if ext.lower() in EXCLUDE_EXTENSIONS:
        return False
    
    return True

def sanitize_tex_file(file_path):
    """
    Принудительно исправляет распространенные ошибки LLM в .tex файлах:
    1. Удаляет невидимые управляющие символы (ASCII 0-31), кроме табуляции и переноса строки.
    2. Эта функция теперь只做 очистку от мусора (^^H). 
       Восстановление библиографии вынесено в отдельный этап для надежности.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️ Не удалось прочитать файл для очистки: {e}")
        return

    original_content = content
    
    # 1. Удаляем все управляющие символы (кроме \n, \t, \r)
    # Символ ^^H имеет код 8. Мы удаляем всё, что < 32, кроме 9, 10, 13.
    cleaned_chars = []
    removed_count = 0
    for char in content:
        code = ord(char)
        if code >= 32 or code in (9, 10, 13):
            cleaned_chars.append(char)
        else:
            removed_count += 1
    
    content = "".join(cleaned_chars)
    if removed_count > 0:
        print(f"  🧹 Удалено {removed_count} недопустимых управляющих символов.")

    # Записываем обратно, только если были изменения по символам
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ Файл {os.path.basename(file_path)} очищен от управляющих символов.")

def fix_lualatex_compatibility(content):
    """Добавляет фиксы для совместимости с LuaLaTeX (для MDPI)"""
    if '\\documentclass' not in content:
        return content
    
    if 'LuaLaTeX Compatibility Fix' in content:
        return content
    
    match = re.search(r'(\\documentclass(?:\[[^\]]*\])?\{[^}]+\})', content)
    if match:
        pos = match.end()
        
        fix = """
% === LuaLaTeX Compatibility Fix (Auto-inserted) ===
\\RequirePackage{iftex}
\\ifluatex
  \\protected\\def\\pdffilesize#1{%
    \\directlua{
      local file = io.open("#1", "rb")
      if file then
        local size = file:seek("end")
        file:close()
        tex.write(size)
      else
        tex.write(0)
      end
    }%
  }
  \\let\\pdfpagewidth\\pagewidth
  \\let\\pdfpageheight\\pageheight
\\fi
% === End Fix ===
"""
        content = content[:pos] + fix + content[pos:]
    
    return content

def translate_latex_text(latex_content, max_chunk_size=2000):
    """
    Полный перевод LaTeX с сохранением структуры документа
    """
    begin_doc = r'\begin{document}'
    end_doc = r'\end{document}'

    if begin_doc not in latex_content:
        return translate_body(latex_content, max_chunk_size)

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

    # БАГ #18: translate_preamble() была определена, но не вызывалась
    translated_preamble = translate_preamble(preamble)
    translated_body = translate_body(body, max_chunk_size)

    return translated_preamble + begin_doc + translated_body + postamble

def translate_preamble(preamble):
    """
    Переводит \\title{}, \\affil{}, \\begin{abstract}...\\end{abstract} в преамбуле.
    Авторов (\\author{}) оставляет без изменений.
    """
    result = preamble

    def _protect_and_translate(text):
        protected = []
        def protect(m):
            protected.append(m.group(0))
            return f"__P{len(protected)-1}__"
        text = re.sub(r'\$[^$]+\$', protect, text)
        translated = translate_chunk(text)
        for i in range(len(protected)-1, -1, -1):
            translated = translated.replace(f"__P{i}__", protected[i])
        return translated

    # 1. Переводим \title{...}
    def translate_title(match):
        return f"\\title{{{_protect_and_translate(match.group(1))}}}"
    result = re.sub(r'\\title\{([^}]+)\}', translate_title, result)

    # 2. Переводим \affil[X]{...} — аффилиация (не трогаем email)
    def translate_affil(match):
        prefix, text = match.group(1), match.group(2)
        if '@' in text or text.strip().startswith('http'):
            return match.group(0)
        return f"\\affil{prefix}{{{_protect_and_translate(text)}}}"
    result = re.sub(r'\\affil(\[[^\]]*\])\{([^}]+)\}', translate_affil, result)

    # 3. Переводим \begin{abstract}...\end{abstract}
    def translate_abstract(match):
        body = match.group(1)
        protected = []
        def protect(m):
            protected.append(m.group(0))
            return f"__AP{len(protected)-1}__"
        body = re.sub(r'\\cite(?:\[[^\]]*\])?\{[^}]*\}', protect, body)
        body = re.sub(r'\\ref\{[^}]*\}', protect, body)
        body = re.sub(r'\$[^$]+\$', protect, body)

        paragraphs = re.split(r'(\n\s*\n)', body)
        translated_parts = []
        for p in paragraphs:
            if not p.strip() or not re.search(r'[a-zA-Z]{3,}', p):
                translated_parts.append(p)
            else:
                translated_parts.append(translate_chunk(p))
        translated_body = ''.join(translated_parts)

        for i in range(len(protected)-1, -1, -1):
            translated_body = translated_body.replace(f"__AP{i}__", protected[i])
        return f"\\begin{{abstract}}{translated_body}\\end{{abstract}}"

    result = re.sub(
        r'\\begin\{abstract\}(.*?)\\end\{abstract\}',
        translate_abstract, result, flags=re.DOTALL
    )

    return result

def translate_body(body, max_chunk_size=2000):
    """Переводит тело документа с защитой математики и технических команд"""

    protected_blocks = []

    def protect_block(match):
        protected_blocks.append(match.group(0))
        return f"__PROTECTED_{len(protected_blocks)-1}__"

    text = body

    # Защита математики
    text = re.sub(r'\\\[.*?\\\]', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{equation\*?\}.*?\\end\{equation\*?\}', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{align\*?\}.*?\\end\{align\*?\}', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{gather\*?\}.*?\\end\{gather\*?\}', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{multline\*?\}.*?\\end\{multline\*?\}', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\$\$.*?\$\$', protect_block, text, flags=re.DOTALL)
    text = re.sub(r'\$[^$]+\$', protect_block, text)
    text = re.sub(r'\\\(.*?\\\)', protect_block, text, flags=re.DOTALL)

    # Технические окружения
    for env in ['verbatim', 'lstlisting', 'minted', 'code', 'tikzpicture', 'asy']:
        pattern = rf'\\begin\{{{env}\*?\}}.*?\\end\{{{env}\*?\}}'
        text = re.sub(pattern, protect_block, text, flags=re.DOTALL)

    # Защита путей и ссылок
    text = re.sub(r'(\\input\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\include\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\label\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\ref\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\eqref\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\cite(?:\[[^\]]*\])?\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\url\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\href\{[^}]*\}\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\includegraphics(?:\[[^\]]*\])?\{[^}]*\})', protect_block, text)
    
    # Защита библиографии
    text = re.sub(r'(\\bibliographystyle\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\bibliography\{[^}]*\})', protect_block, text)
    text = re.sub(r'(\\addbibresource\{[^}]*\})', protect_block, text)

    paragraphs = re.split(r'(\n\s*\n)', text)
    translated_parts = []

    for para in tqdm(paragraphs, desc="Перевод"):
        if not para.strip():
            translated_parts.append(para)
            continue

        if re.fullmatch(r'[\s__PROTECTED_\d+__]+', para):
            translated_parts.append(para)
            continue

        temp = para
        for i in range(len(protected_blocks)):
            temp = temp.replace(f"__PROTECTED_{i}__", "")

        if not re.search(r'[a-zA-Z]{2,}', temp):
            translated_parts.append(para)
            continue

        if len(para) > max_chunk_size:
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

    for i in range(len(protected_blocks) - 1, -1, -1):
        result = result.replace(f"__PROTECTED_{i}__", protected_blocks[i])

    return result

def restore_bibliography_commands(original_content, translated_content):
    """
    ЖЕСТКОЕ восстановление команд библиографии.
    Мы полностью игнорируем то, что написано в translated_content,
    и берем имена файлов напрямую из original_content.
    """
    # 1. Восстанавливаем \bibliographystyle{...}
    orig_style = re.search(r'\\bibliographystyle\{([^}]+)\}', original_content)
    if orig_style:
        style_name = orig_style.group(1)
        # Полностью заменяем любую строку, содержащую bibliographystyle, на новую
        # Используем multiline флаг, чтобы захватить команду, даже если она одна в строке
        translated_content = re.sub(
            r'^.*bibliographystyle.*$',
            f'\\bibliographystyle{{{style_name}}}',
            translated_content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        # Если команда была не одна в строке (редко), пробуем еще раз более локально
        if f'\\bibliographystyle{{{style_name}}}' not in translated_content:
             translated_content = re.sub(
                r'\\?bibliographystyle\{[^}]*\}',
                f'\\bibliographystyle{{{style_name}}}',
                translated_content,
                flags=re.IGNORECASE
            )

    # 2. Восстанавливаем \bibliography{...}
    orig_bib = re.search(r'\\bibliography\{([^}]+)\}', original_content)
    if orig_bib:
        bib_name = orig_bib.group(1)
        # Полностью заменяем строку
        translated_content = re.sub(
            r'^.*bibliography.*$',
            f'\\bibliography{{{bib_name}}}',
            translated_content,
            flags=re.MULTILINE | re.IGNORECASE
        )
        # Дублирующая проверка для надежности
        if f'\\bibliography{{{bib_name}}}' not in translated_content:
            translated_content = re.sub(
                r'\\?bibliography\{[^}]*\}',
                f'\\bibliography{{{bib_name}}}',
                translated_content,
                flags=re.IGNORECASE
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
        is_mdpi = False
        
        for root, _, files in os.walk(tmp_extract_dir):
            for f in files:
                if f.lower().endswith('.tex'):
                    full_path = os.path.join(root, f)
                    
                    if not should_translate_file(f):
                        print(f"⏭️  Пропуск файла (технический): {f}")
                        continue
                    
                    tex_files.append(full_path)
                    if main_tex is None:
                        try:
                            with open(full_path, 'r', encoding='utf-8') as fp:
                                content = fp.read()
                                if r'\begin{document}' in content:
                                    main_tex = full_path
                                    if 'mdpi' in content.lower() and '\\documentclass' in content:
                                        is_mdpi = True
                        except:
                            pass

        if not tex_files:
            all_tex = []
            for root, _, files in os.walk(tmp_extract_dir):
                for f in files:
                    if f.lower().endswith('.tex'):
                        all_tex.append(os.path.join(root, f))
            
            if not all_tex:
                raise ValueError("В архиве нет .tex файлов.")
            else:
                print("⚠️  Все .tex файлы были исключены (технические файлы).")
                for tf in all_tex:
                    try:
                        with open(tf, 'r', encoding='utf-8') as fp:
                            if r'\begin{document}' in fp.read():
                                main_tex = tf
                                break
                    except:
                        pass
                
                if not main_tex:
                    main_tex = all_tex[0]

        if main_tex is None and tex_files:
            main_tex = tex_files[0]
            print("⚠️ Не найден \\begin{document}. Используем первый .tex как главный.")

        for tex_path in tex_files:
            print(f"\n📄 Перевод файла: {os.path.basename(tex_path)}")
            with open(tex_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            # Добавляем поддержку русского языка
            content_with_preamble = add_russian_preamble(original_content)
            
            translated = translate_latex_text(content_with_preamble)
            
            # ВОССТАНАВЛИВАЕМ БИБЛИОГРАФИЮ ДО записи файла
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
            
            if is_mdpi and tex_path == main_tex:
                translated = fix_lualatex_compatibility(translated)
                print("  ✓ Применён фикс совместимости LuaLaTeX для MDPI")

            # Записываем переведенный контент
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(translated)
            
            # Очищаем файл от мусора LLM (символы ^^H и т.д.)
            # Важно: это делается ПОСЛЕ записи, чтобы убрать мусор, но ДО компиляции
            sanitize_tex_file(tex_path)

        base_name = os.path.splitext(os.path.basename(zip_path))[0]
        output_zip = os.path.join(output_dir, f"{base_name}_translated.zip")

        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as new_zip:
            for root, _, files in os.walk(tmp_extract_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arc_path = os.path.relpath(full_path, tmp_extract_dir)
                    new_zip.write(full_path, arc_path)

        main_tex_rel = os.path.relpath(main_tex, tmp_extract_dir)
        main_tex_rel = main_tex_rel.replace("\\", "/")  # Docker требует прямых слешей
        return output_zip, main_tex_rel

def add_russian_preamble(latex_content):
    """
    Добавляет поддержку русского языка, адаптируясь под движок (XeLaTeX/LuaLaTeX).
    Удаляет старые конфликты babel/fontenc.
    """
    if r"\documentclass" not in latex_content:
        return latex_content

    lines = latex_content.splitlines()
    new_lines = []
    
    # 1. Очищаем преамбулу от старых пакетов, вызывающих конфликты
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(r"\usepackage") and ("babel" in stripped or "fontenc" in stripped or "inputenc" in stripped):
            continue 
        elif stripped.startswith(r"\DeclareUnicodeCharacter"):
            continue 
        else:
            new_lines.append(line)

    content_clean = "\n".join(new_lines)

    # 2. Определяем, нужен ли режим MDPI (LuaLaTeX)
    is_mdpi = "mdpi" in content_clean.lower() and r"\documentclass" in content_clean

    # 3. Формируем новый блок поддержки языка
    if is_mdpi:
        russian_support = [
            "% --- Поддержка русского языка (LuaLaTeX/Polyglossia) ---",
            r"\usepackage{fontspec}",
            r"\usepackage{polyglossia}",
            r"\setmainlanguage{russian}",
            r"\setotherlanguage{english}",
            r"\newfontfamily\cyrillicfont{DejaVu Serif}[Script=Cyrillic]",
            r"\newfontfamily\cyrillicfontsf{DejaVu Sans}[Script=Cyrillic]",
            r"\newfontfamily\cyrillicfonttt{DejaVu Sans Mono}[Script=Cyrillic]",
            r"\defaultfontfeatures{Ligatures=TeX,Scale=MatchLowercase}",
            r"\setmainfont{DejaVu Serif}",
            "% -------------------------------------------------------"
        ]
    else:
        russian_support = [
            "% --- Поддержка русского языка (XeLaTeX/Babel) ---",
            r"\usepackage{fontspec}",
            r"\usepackage[russian, english]{babel}",
            r"\setmainfont{DejaVu Serif}",
            r"\setsansfont{DejaVu Sans}",
            r"\setmonofont{DejaVu Sans Mono}",
            "% -------------------------------------------------"
        ]

    # 4. Вставляем блок сразу после \documentclass
    final_lines = []
    inserted = False
    for line in content_clean.splitlines():
        final_lines.append(line)
        if r"\documentclass" in line and not inserted:
            final_lines.extend(russian_support)
            inserted = True
    
    if not inserted:
        final_lines = russian_support + final_lines

    return "\n".join(final_lines)