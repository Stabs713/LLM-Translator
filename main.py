import os
import sys

from common import (
    INPUT_DIR,
    OUTPUT_DIR,
    test_model_connection,
    load_env_vars,
    get_files_list,
    get_tex_files_list,
    select_file_by_number,
    select_main_action,
    select_translation_model
)
from translate_tex import translate_latex_text, extract_tex_from_zip, add_russian_preamble
from translate_docx import translate_docx
from pdf_converter import compile_tex_to_pdf_via_docker

def main():
    print(" LLM-Translator: перевод .tex / .docx / .zip")
    print("-" * 70)
    print("Поддерживаемые форматы: .docx, .tex, .zip")

    load_env_vars()

    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    action = select_main_action()

    if action == "translate":
        # Выбор модели
        model_name = select_translation_model()
        
        # Проверка подключения к выбранной модели
        if not test_model_connection(model_name):
            print("❌ Не удалось подключиться к модели. Проверьте ключ и URL.")
            sys.exit(1)

        available = get_files_list(INPUT_DIR)
        if not available:
            print(f"📁 Положите .docx, .tex или .zip в папку '{INPUT_DIR}'")
            sys.exit(1)
        print(f"\n📁 Доступные файлы для перевода:")

    elif action == "compile":
        available = get_tex_files_list(INPUT_DIR)
        if not available:
            print(f"📁 В папке '{INPUT_DIR}' нет .tex файлов для компиляции.")
            sys.exit(1)
        print(f"\n📁 Доступные .tex файлы для компиляции:")
        model_name = None  # не используется

    for i, filename in enumerate(available, 1):
        print(f"  {i}. {filename}")

    file_index = select_file_by_number(len(available))
    filename = available[file_index - 1]
    input_path = os.path.join(INPUT_DIR, filename)
    base, ext = os.path.splitext(filename)
    ext = ext.lower()

    try:
        if action == "translate":
            # Передаём выбранную модель в функции перевода
            from common import set_current_model
            set_current_model(model_name)

            if ext == '.zip':
                print("\n📦 Извлечение .tex из архива...")
                tex_name, tex_content = extract_tex_from_zip(input_path)
                base = os.path.splitext(tex_name)[0]
                output_tex = os.path.join(OUTPUT_DIR, f"{base}_translated.tex")
                translated = translate_latex_text(tex_content)
                translated = add_russian_preamble(translated)
                with open(output_tex, 'w', encoding='utf-8') as f:
                    f.write(translated)
                print(f"\n✅ Перевод .tex завершён! Результат: {output_tex}")
                if input("Скомпилировать в PDF? (y/n): ").strip().lower() == 'y':
                    compile_tex_to_pdf_via_docker(output_tex)

            elif ext == '.tex':
                with open(input_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                output_tex = os.path.join(OUTPUT_DIR, f"{base}_translated.tex")
                translated = translate_latex_text(content)
                translated = add_russian_preamble(translated)
                with open(output_tex, 'w', encoding='utf-8') as f:
                    f.write(translated)
                print(f"\n✅ Перевод .tex завершён! Результат: {output_tex}")
                if input("Скомпилировать в PDF? (y/n): ").strip().lower() == 'y':
                    compile_tex_to_pdf_via_docker(output_tex)

            elif ext == '.docx':
                output_docx = os.path.join(OUTPUT_DIR, f"{base}_translated.docx")
                translate_docx(input_path, output_docx)

        elif action == "compile":
            if ext != '.tex':
                print("❌ Только .tex файлы можно компилировать.")
                sys.exit(1)
            print(f"\n📦 Компиляция файла: {filename}")
            compile_tex_to_pdf_via_docker(input_path)

    except KeyboardInterrupt:
        print("\n\n❌ Отменено пользователем.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()