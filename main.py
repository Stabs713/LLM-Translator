# main.py
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
                with zipfile.ZipFile(input_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)
                
                # Собираем все .tex файлы с глубиной вложенности
                all_tex = []
                for root, _, files in os.walk(tmpdir):
                    for f in files:
                        if f.lower().endswith('.tex'):
                            full_path = os.path.join(root, f)
                            depth = len(os.path.relpath(full_path, tmpdir).split(os.sep))
                            all_tex.append((full_path, depth))
                
                if not all_tex:
                    print("❌ В архиве нет .tex файлов.")
                    return
                
                # Сортируем по глубине — сначала файлы ближе к корню
                all_tex.sort(key=lambda x: x[1])
                
                # Ищем главный: \begin{document}, приоритет — ближе к корню
                main_tex = None
                for full_path, _ in all_tex:
                    try:
                        with open(full_path, 'r', encoding='utf-8') as fp:
                            if r'\begin{document}' in fp.read():
                                main_tex = full_path
                                break
                    except:
                        pass
                
                if main_tex is None:
                    print("⚠️ Не найден \\begin{document}. Используем ближайший к корню .tex файл.")
                    main_tex = all_tex[0][0]
                
                main_tex_name = os.path.relpath(main_tex, tmpdir).replace('\\', '/')
            
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

def translate_mode():
    """Режим перевода с компиляцией"""
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
    base, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    try:
        from common import set_current_model
        set_current_model(model_name)
        
        if ext == '.zip':
            print("\n📦 Обработка архива...")
            output_zip, main_tex_name = process_zip_for_translation(input_path, OUTPUT_DIR)
            print(f"✅ Перевод завершён! Архив: {output_zip}")
            
            # Спрашиваем, компилировать ли
            compile_choice = input("\n🐳 Скомпилировать в PDF? (y/n): ").strip().lower()
            if compile_choice == 'y':
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
            
            # Спрашиваем, компилировать ли
            compile_choice = input("\n🐳 Скомпилировать в PDF? (y/n): ").strip().lower()
            if compile_choice == 'y':
                print("🐳 Компиляция в PDF...")
                compile_tex_to_pdf_via_docker(output_tex)
        
        elif ext == '.docx':
            output_docx = os.path.join(OUTPUT_DIR, f"{base}_translated.docx")
            translate_docx(input_path, output_docx)
    
    except KeyboardInterrupt:
        print("\n\n❌ Отменено пользователем.")
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
        import traceback
        traceback.print_exc()

def main():
    try:
        load_env_vars()
    except ValueError as e:
        print(f"⚠️ {e}")
        print("ℹ️  Режим компиляции доступен без API ключа.")
    
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
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

if __name__ == "__main__":
    main()