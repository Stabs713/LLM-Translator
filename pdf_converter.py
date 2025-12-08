import os
import subprocess
import tempfile
import shutil
import zipfile


def compile_tex_to_pdf_via_docker(tex_path):
    """Компилирует .tex файл в .pdf с помощью Docker и XeLaTeX."""
    if not os.path.exists(tex_path):
        print("❌ Указанный .tex файл не найден.")
        return False

    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("ℹ️  Docker не запущен. Запустите Docker Desktop.")
        return False

    print("🐳 Компиляция в PDF через Docker (XeLaTeX)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copy(tex_path, tmpdir)
        tex_filename = os.path.basename(tex_path)
        try:
            result = subprocess.run([
                "docker", "run", "--rm",
                "-v", f"{tmpdir}:/work",
                "-w", "/work",
                "texlive/texlive",
                "latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_filename
            ], capture_output=False, text=True, timeout=180)

            if result.returncode == 0:
                pdf_path = os.path.splitext(tex_path)[0] + ".pdf"
                generated_pdf = os.path.join(tmpdir, os.path.splitext(tex_filename)[0] + ".pdf")
                if os.path.exists(generated_pdf):
                    shutil.copy(generated_pdf, pdf_path)
                    print(f"✅ PDF создан: {pdf_path}")
                    return True
            else:
                print("⚠️  Ошибка компиляции в Docker.")
        except subprocess.TimeoutExpired:
            print("⚠️  Тайм-аут компиляции (3 мин).")
        except Exception as e:
            print(f"💥 Ошибка: {e}")
    return False


def compile_zip_to_pdf_via_docker(zip_path, main_tex_name):
    """Компилирует ZIP с LaTeX файлами в PDF"""
    if not os.path.exists(zip_path):
        print("❌ ZIP-файл не найден.")
        return False

    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("ℹ️ Docker не запущен. Запустите Docker Desktop.")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)

        full_tex_path = os.path.join(tmpdir, main_tex_name)
        if not os.path.exists(full_tex_path):
            print(f"❌ Главный .tex файл не найден: {main_tex_name}")
            return False

        print("🐳 Компиляция PDF через Docker (XeLaTeX)...")
        try:
            result = subprocess.run([
                "docker", "run", "--rm",
                "-v", f"{tmpdir}:/work",
                "-w", "/work",
                "texlive/texlive",
                "latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", main_tex_name
            ], capture_output=False, text=True, timeout=180)

            if result.returncode == 0:
                generated_pdf = os.path.join(tmpdir, os.path.splitext(main_tex_name)[0] + ".pdf")
                if os.path.exists(generated_pdf):
                    output_pdf = os.path.splitext(zip_path)[0] + ".pdf"
                    shutil.copy(generated_pdf, output_pdf)
                    print(f"✅ PDF создан: {output_pdf}")
                    return True
                else:
                    print("⚠️ PDF не найден после компиляции.")
            else:
                print("⚠️ Ошибка компиляции в Docker.")
        except subprocess.TimeoutExpired:
            print("⚠️ Тайм-аут компиляции (3 мин).")
        except Exception as e:
            print(f"💥 Ошибка: {e}")
    return False
