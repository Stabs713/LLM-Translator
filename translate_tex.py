# translate_tex.py
import os
import re
import zipfile
import tempfile
import shutil
import subprocess
from tqdm import tqdm
from common import (
    translate_chunk,
    chunk_text_by_sentences_safe,
    OUTPUT_DIR
)

# === Безопасный перевод таблиц ===

def translate_tabular_content(content):
    if not content.strip():
        return content
    lines = content.split('\\\\')
    translated_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            translated_lines.append("")
            continue
        if stripped.startswith(r'\hline') or stripped.startswith(r'\cline'):
            translated_lines.append(line)
            continue
        cells = line.split('&')
        translated_cells = []
        for cell in cells:
            cell = cell.strip()
            if not cell:
                translated_cells.append("")
                continue
            if (cell.startswith(r'\multicolumn') or
                cell.startswith(r'\multirow') or
                cell.startswith(r'\cline') or
                cell.startswith(r'\hline')):
                translated_cells.append(cell)
                continue
            translated_cells.append(translate_chunk(cell))
        translated_lines.append(" & ".join(translated_cells))
    return " \\\\ \n".join(translated_lines)

# === Основная функция перевода ===

def translate_latex_text(latex_content):
    # === Шаг 1: Перевод аргументов макросов, которые ДОЛЖНЫ переводиться ===
    TRANSLATABLE_MACROS = ['section', 'subsection', 'subsubsection', 'caption', 'title', 'author', 'abstract']
    for macro in TRANSLATABLE_MACROS:
        def repl(m):
            inner = m.group(1)
            translated = translate_chunk(inner)
            return f"\\{macro}{{{translated}}}"
        latex_content = re.sub(rf'\\{macro}\{{(.*?)\}}', repl, latex_content, flags=re.DOTALL)

    # === Шаг 2: Маскировка всего, что НЕЛЬЗЯ переводить ===
    placeholders = []
    def store_and_mask(match):
        placeholders.append(match.group(0))
        return f"__PH_{len(placeholders)-1}__"

    # Критически важные команды
    latex_content = re.sub(r'\\documentclass(\[[^\]]*\])?\{[^}]*\}', store_and_mask, latex_content)
    latex_content = re.sub(r'\\(usepackage|bibliographystyle|RequirePackage)(\[[^\]]*\])?\{[^}]*\}', store_and_mask, latex_content)

    # Защищённые окружения
    PROTECTED_ENVS = [
        'equation', 'align', 'gather', 'multline', 'eqnarray',
        'verbatim', 'lstlisting', 'minted', 'displaymath', 'math',
        'code', 'algorithm', 'algorithmic', 'figure'
    ]
    for env in PROTECTED_ENVS:
        latex_content = re.sub(rf'\\begin{{{env}}}.*?\\end{{{env}}}', store_and_mask, latex_content, flags=re.DOTALL)

    # Формулы
    latex_content = re.sub(r'\$\$(.*?)\$\$', store_and_mask, latex_content, flags=re.DOTALL)
    latex_content = re.sub(r'\$(.*?)\$', store_and_mask, latex_content, flags=re.DOTALL)
    latex_content = re.sub(r'\\\((.*?)\\\)', store_and_mask, latex_content, flags=re.DOTALL)
    latex_content = re.sub(r'\\\[', store_and_mask, latex_content)
    latex_content = re.sub(r'\\\]', store_and_mask, latex_content)

    # Комментарии и опции
    latex_content = re.sub(r'(?<!\\)%.*', store_and_mask, latex_content)
    latex_content = re.sub(r'\[[^\]]*\]', store_and_mask, latex_content)

    # Все остальные команды
    latex_content = re.sub(r'\\([a-zA-Z]+)(\{[^{}]*\})?', store_and_mask, latex_content)

    # === Шаг 3: Обработка tabular отдельно (не маскируем целиком!) ===
    def replace_tabular(match):
        full = match.group(0)
        m = re.search(r'\\begin\{tabular\}(\{[^}]*\})(.*?)\\end\{tabular\}', full, re.DOTALL)
        if m:
            spec = m.group(1)
            body = m.group(2)
            return f"\\begin{{tabular}}{spec}{translate_tabular_content(body)}\\end{{tabular}}"
        return full
    latex_content = re.sub(r'\\begin\{tabular\}\{[^}]*\}.*?\\end\{tabular\}', replace_tabular, latex_content, flags=re.DOTALL)

    # === Шаг 4: Перевод оставшегося текста с прогресс-баром ===
    chunks = chunk_text_by_sentences_safe(latex_content, max_tokens=1200)
    translated_chunks = []
    for chunk in tqdm(chunks, desc="Перевод LaTeX"):
        if chunk.strip():
            translated_chunks.append(translate_chunk(chunk))
        else:
            translated_chunks.append(chunk)
    translated = "".join(translated_chunks)

    # === Шаг 5: Восстановление ===
    for i in range(len(placeholders) - 1, -1, -1):
        translated = translated.replace(f"__PH_{i}__", placeholders[i])

    return translated

# === Остальные функции (без изменений) ===

def get_all_tex_files_in_zip(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        return [f for f in zip_ref.namelist() if f.lower().endswith('.tex')]

def select_tex_files_for_translation(tex_files_list):
    print(f"\n📌 Найдено {len(tex_files_list)} .tex файлов:")
    for i, f in enumerate(tex_files_list, 1):
        print(f"  {i}. {f}")
    print("\nКакие файлы перевести?")
    print("1. Только один файл")
    print("2. Несколько файлов")
    print("3. Все файлы")
    while True:
        try:
            choice = int(input("Выберите действие (1/2/3): ").strip())
            if choice == 1:
                idx = int(input("Введите номер файла: ")) - 1
                if 0 <= idx < len(tex_files_list):
                    return [tex_files_list[idx]]
                else:
                    print("❌ Неверный номер.")
            elif choice == 2:
                indices = input("Введите номера файлов через пробел: ").strip().split()
                selected = []
                for s in indices:
                    try:
                        idx = int(s) - 1
                        if 0 <= idx < len(tex_files_list):
                            selected.append(tex_files_list[idx])
                        else:
                            print(f"⚠️ Номер {s} вне диапазона.")
                    except ValueError:
                        print(f"⚠️ «{s}» — не число.")
                if selected:
                    return selected
                else:
                    print("❌ Не выбрано ни одного файла.")
            elif choice == 3:
                return tex_files_list[:]
            else:
                print("❌ Выберите 1, 2 или 3.")
        except ValueError:
            print("❌ Введите число.")

def repack_zip_with_translated_tex(original_zip_path, translated_files, output_zip_path):
    with zipfile.ZipFile(original_zip_path, 'r') as zip_in:
        with zipfile.ZipFile(output_zip_path, 'w') as zip_out:
            for item in zip_in.infolist():
                if item.filename in translated_files:
                    zip_out.writestr(item, translated_files[item.filename].encode('utf-8'))
                else:
                    zip_out.writestr(item, zip_in.read(item.filename))

def find_main_tex_in_dir(directory):
    for root, _, files in os.walk(directory):
        for f in files:
            if f.lower().endswith('.tex'):
                path = os.path.join(root, f)
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        if r'\documentclass' in file.read():
                            return os.path.relpath(path, directory)
                except:
                    continue
    return None

def compile_zip_to_pdf(zip_path, output_pdf_path=None):
    if not output_pdf_path:
        base = os.path.splitext(os.path.basename(zip_path))[0]
        output_pdf_path = os.path.join(OUTPUT_DIR, f"{base}_translated.pdf")

    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("ℹ️  Docker не запущен. Запустите Docker Desktop.")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)

        main_tex = find_main_tex_in_dir(tmpdir)
        if not main_tex:
            print("⚠️ Не найден файл с \\documentclass.")
            return None

        print(f"📄 Компиляция: {main_tex}")
        main_tex_posix = main_tex.replace("\\", "/")

        try:
            result = subprocess.run([
                "docker", "run", "--rm",
                "-v", f"{tmpdir}:/work",
                "-w", "/work",
                "texlive/texlive",
                "latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", main_tex_posix
            ], capture_output=False, text=True, timeout=180)

            if result.returncode == 0:
                generated_pdf = os.path.join(tmpdir, os.path.splitext(main_tex)[0] + ".pdf")
                if os.path.exists(generated_pdf):
                    shutil.copy(generated_pdf, output_pdf_path)
                    print(f"✅ PDF создан: {output_pdf_path}")
                    return output_pdf_path
        except Exception as e:
            print(f"💥 Ошибка: {e}")
    return None

def add_russian_preamble(latex_content):
    if r"\documentclass" not in latex_content:
        return latex_content

    lines = [line for line in latex_content.splitlines()
             if not (r"\usepackage[" in line and "babel" in line) and r"\usepackage{babel}" not in line]

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

    result_lines = []
    inserted = False
    for line in lines:
        result_lines.append(line)
        if r"\documentclass" in line and not inserted:
            result_lines.extend(new_preamble)
            inserted = True

    return "\n".join(result_lines)