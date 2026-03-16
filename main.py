# main.py
import os
import sys
import argparse

from common import (
    INPUT_DIR,
    OUTPUT_DIR,
    test_model_connection,
    load_env_vars,
    get_files_list,
    select_file_by_number,
    select_translation_model,
    find_main_tex_in_dir,
)
from translate_tex import (
    translate_latex_text,
    add_russian_preamble,
    process_zip_for_translation,
    restore_bibliography_commands,
)
from translate_docx import translate_docx
from pdf_converter import compile_tex_to_pdf_via_docker, compile_zip_to_pdf_via_docker

def show_main_menu():
    """Показывает главное меню"""
    print("\n" + "="*70)
    print("🌐 LLM-Translator: перевод и компиляция LaTeX/DOCX")
    print("="*70)
    print("\nВыберите режим работы:")
    print("  1. Перевести и скомпилировать (.tex, .zip, .docx)")
    print("  2. Только скомпилировать в PDF (.tex, .zip)")
    print("  3. Выход")
    print("-" * 70)

def compile_only_mode():
    """Режим только компиляции без перевода"""
    print("\n📦 РЕЖИМ КОМПИЛЯЦИИ (без перевода)")
    print("-" * 70)
    
    available = [f for f in get_files_list(INPUT_DIR) if f.lower().endswith(('.tex', '.zip'))]
    if not available:
        print(f"📁 Положите .tex или .zip файлы в папку '{INPUT_DIR}'")
        return
    
    print(f"\n📁 Доступные файлы для компиляции:")
    for i, filename in enumerate(available, 1):
        print(f"  {i}. {filename}")
    
    file_index = select_file_by_number(len(available))
    filename = available[file_index - 1]
    input_path = os.path.join(INPUT_DIR, filename)
    ext = os.path.splitext(filename)[1].lower()
    
    try:
        if ext == '.zip':
            # Для ZIP нужно найти главный .tex файл
            import zipfile
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(input_path, "r") as zip_ref:
                    zip_ref.extractall(tmpdir)

                try:
                    main_tex_name = find_main_tex_in_dir(tmpdir)
                except ValueError as e:
                    print(f"❌ {e}")
                    return

            print(f"📄 Главный файл: {main_tex_name}")
            print("🐳 Компиляция ZIP в PDF...")
            compile_zip_to_pdf_via_docker(input_path, main_tex_name)
        
        elif ext == '.tex':
            print("🐳 Компиляция .tex в PDF...")
            compile_tex_to_pdf_via_docker(input_path)
    
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
        import traceback
        traceback.print_exc()

def _translate_file(input_path: str, model_name: str, auto_compile: bool = False) -> None:
    """
    Внутренняя функция перевода одного файла.
    Работает и для интерактивного, и для CLI‑режима.
    """
    from common import set_current_model
    set_current_model(model_name)

    filename = os.path.basename(input_path)
    base, ext = os.path.splitext(filename)
    ext = ext.lower()

    try:
        if ext == '.zip':
            print("\n📦 Обработка архива...")
            output_zip, main_tex_name = process_zip_for_translation(input_path, OUTPUT_DIR)
            print(f"✅ Перевод завершён! Архив: {output_zip}")

            if auto_compile:
                print("🐳 Компиляция в PDF...")
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

            if auto_compile:
                print("🐳 Компиляция в PDF...")
                compile_tex_to_pdf_via_docker(output_tex)

        elif ext == '.docx':
            output_docx = os.path.join(OUTPUT_DIR, f"{base}_translated.docx")
            translate_docx(input_path, output_docx)
            print(f"\n✅ Перевод .docx завершён! Результат: {output_docx}")

        else:
            print("❌ Неподдерживаемое расширение файла для перевода.")

    except KeyboardInterrupt:
        print("\n\n❌ Отменено пользователем.")
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
        import traceback
        traceback.print_exc()


def translate_mode() -> None:
    """Интерактивный режим перевода с компиляцией"""
    print("\n🌐 РЕЖИМ ПЕРЕВОДА")
    print("-" * 70)

    # Выбор модели
    model_name = select_translation_model()

    # Проверка подключения к выбранной модели
    if not test_model_connection(model_name):
        print("❌ Не удалось подключиться к модели. Проверьте ключ и URL.")
        return

    available = get_files_list(INPUT_DIR)
    if not available:
        print(f"📁 Положите .docx, .tex или .zip в папку '{INPUT_DIR}'")
        return

    print(f"\n📁 Доступные файлы для перевода:")
    for i, filename in enumerate(available, 1):
        print(f"  {i}. {filename}")

    file_index = select_file_by_number(len(available))
    filename = available[file_index - 1]
    input_path = os.path.join(INPUT_DIR, filename)

    # Спрашиваем, компилировать ли PDF после перевода (для tex/zip)
    compile_choice = input("\n🐳 Скомпилировать в PDF после перевода? (y/n): ").strip().lower()
    auto_compile = compile_choice == 'y'

    _translate_file(input_path, model_name, auto_compile=auto_compile)


def run_compile_cli(args: argparse.Namespace) -> None:
    """Обработка CLI‑режима compile."""
    if not args.file:
        # Без --file используем интерактивный режим компиляции
        compile_only_mode()
        return

    filename = os.path.basename(args.file)
    input_path = args.file
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".tex", ".zip"):
        print("❌ Для режима compile поддерживаются только .tex и .zip.")
        sys.exit(1)

    try:
        if ext == ".tex":
            print("🐳 Компиляция .tex в PDF...")
            if not compile_tex_to_pdf_via_docker(input_path):
                sys.exit(1)
        else:
            print("🐳 Компиляция ZIP в PDF...")
            # Нам нужно знать main_tex_name; используем ту же логику, что и в интерактивном режиме
            import zipfile
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(input_path, "r") as zip_ref:
                    zip_ref.extractall(tmpdir)

                try:
                    main_tex_name = find_main_tex_in_dir(tmpdir)
                except ValueError as e:
                    print(f"❌ {e}")
                    sys.exit(1)

            print(f"📄 Главный файл: {main_tex_name}")
            if not compile_zip_to_pdf_via_docker(input_path, main_tex_name):
                sys.exit(1)
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def run_translate_cli(args: argparse.Namespace) -> None:
    """Обработка CLI‑режима translate."""
    # Выбор модели
    if args.model:
        model_name = args.model
        if not test_model_connection(model_name):
            print("❌ Не удалось подключиться к модели. Проверьте ключ и URL.")
            sys.exit(1)
    else:
        model_name = select_translation_model()
        if not test_model_connection(model_name):
            print("❌ Не удалось подключиться к модели. Проверьте ключ и URL.")
            sys.exit(1)

    # Выбор файла
    if args.file:
        input_path = args.file
    else:
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

    _translate_file(input_path, model_name, auto_compile=args.compile)


def run_interactive_menu() -> None:
    """Интерактивное меню, используемое при отсутствии CLI‑аргументов."""
    while True:
        show_main_menu()

        try:
            choice = input("Выберите режим (1-3): ").strip()

            if choice == '1':
                translate_mode()
            elif choice == '2':
                compile_only_mode()
            elif choice == '3':
                print("\n👋 До свидания!")
                sys.exit(0)
            else:
                print("❌ Выберите 1, 2 или 3")
                continue

            # Спрашиваем, продолжить ли работу
            again = input("\n🔄 Выполнить ещё одну операцию? (y/n): ").strip().lower()
            if again != 'y':
                print("\n👋 До свидания!")
                break

        except KeyboardInterrupt:
            print("\n\n❌ Отменено пользователем.")
            sys.exit(1)
        except Exception as e:
            print(f"\n💥 Ошибка: {e}")
            import traceback
            traceback.print_exc()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM-Translator: перевод и компиляция LaTeX/DOCX"
    )
    parser.add_argument(
        "--mode",
        choices=["translate", "compile"],
        help="Режим работы: translate (перевод) или compile (только компиляция)",
    )
    parser.add_argument(
        "--file",
        help="Путь к входному файлу (.tex, .zip, .docx). Если не указан — будет интерактивный выбор из папки inputs.",
    )
    parser.add_argument(
        "--model",
        help="ID модели для перевода (например, anthropic/claude-3.5-haiku). Если не указан — будет интерактивный выбор.",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Автоматически скомпилировать в PDF после перевода (для .tex/.zip).",
    )

    args = parser.parse_args()

    try:
        load_env_vars()
    except ValueError as e:
        print(f"⚠️ {e}")
        print("ℹ️  Режим компиляции доступен без API ключа.")

    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Неинтерактивный CLI‑режим
    if args.mode == "compile":
        run_compile_cli(args)
        return
    if args.mode == "translate":
        run_translate_cli(args)
        return

    # Старый интерактивный режим (без аргументов)
    run_interactive_menu()

if __name__ == "__main__":
    main()