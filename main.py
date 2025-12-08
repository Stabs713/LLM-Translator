import os
import sys

from common import (
    INPUT_DIR,
    OUTPUT_DIR,
    test_model_connection,
    load_env_vars,
    get_files_list,
    select_file_by_number,
    select_translation_model
)
from translate_tex import translate_latex_text, add_russian_preamble, process_zip_for_translation, restore_bibliography_commands
from translate_docx import translate_docx
from pdf_converter import compile_tex_to_pdf_via_docker, compile_zip_to_pdf_via_docker


def main():
    print("🌐 LLM-Translator: перевод .tex / .docx / .zip")
    print("-" * 70)
    print("Поддерживаемые форматы: .docx, .tex, .zip")

    load_env_vars()

    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

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
    for i, filename in enumerate(available, 1):
        print(f"  {i}. {filename}")

    file_index = select_file_by_number(len(available))
    filename = available[file_index - 1]
    input_path = os.path.join(INPUT_DIR, filename)
    base, ext = os.path.splitext(filename)
    ext = ext.lower()

    try:
        from common import set_current_model
        set_current_model(model_name)

        if ext == '.zip':
            print("\n📦 Обработка архива...")
            output_zip, main_tex_name = process_zip_for_translation(input_path, OUTPUT_DIR)
            print(f"✅ Перевод завершён! Архив: {output_zip}")
            print("\n🐳 Автоматическая компиляция в PDF...")
            compile_zip_to_pdf_via_docker(output_zip, main_tex_name)

        elif ext == '.tex':
            with open(input_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            output_tex = os.path.join(OUTPUT_DIR, f"{base}_translated.tex")
            content_with_preamble = add_russian_preamble(original_content)
            translated = translate_latex_text(content_with_preamble)
            translated = restore_bibliography_commands(original_content, translated)

            # Восстанавливаем \documentclass из оригинала
            import re
            docclass_match = re.search(r'\\documentclass(?:\[[^\]]*\])?\{[^\}]+\}', original_content)
            if docclass_match:
                orig_docclass = docclass_match.group(0)
                translated = re.sub(
                    r'\\documentclass(?:\[[^\]]*\])?\{[^\}]+\}',
                    lambda m: orig_docclass,
                    translated,
                    count=1
                )
            with open(output_tex, 'w', encoding='utf-8') as f:
                f.write(translated)
            print(f"\n✅ Перевод .tex завершён! Результат: {output_tex}")
            print("\n🐳 Автоматическая компиляция в PDF...")
            compile_tex_to_pdf_via_docker(output_tex)

        elif ext == '.docx':
            output_docx = os.path.join(OUTPUT_DIR, f"{base}_translated.docx")
            translate_docx(input_path, output_docx)

    except KeyboardInterrupt:
        print("\n\n❌ Отменено пользователем.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
