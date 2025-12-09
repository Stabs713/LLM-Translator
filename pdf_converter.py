# pdf_converter.py

import os
import subprocess
import tempfile
import shutil
import zipfile
import re


def patch_mdpi_for_lualatex(work_dir):
    """Патчит mdpi.cls для совместимости с LuaLaTeX"""
    for root, _, files in os.walk(work_dir):
        for file in files:
            if file == "mdpi.cls":
                cls_path = os.path.join(root, file)
                try:
                    with open(cls_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    if "\\LoadClass" in content and "RequirePackage{luatex85}" not in content:
                        pos = content.find("\\LoadClass")
                        if pos > 0:
                            fix = (
                                "\n% Fix for LuaLaTeX compatibility\n"
                                "\\RequirePackage{luatex85}\n\n"
                            )
                            content = content[:pos] + fix + content[pos:]
                            with open(cls_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            print(f"  ✓ Патч применён к {file}")
                            return True
                except Exception as e:
                    print(f"  ⚠️ Не удалось пропатчить {file}: {e}")
    return False


def detect_document_class(tex_path):
    """Определяет класс документа из .tex файла"""
    try:
        with open(tex_path, "r", encoding="utf-8") as f:
            content = f.read(5000)
        m = re.search(r"\\documentclass(?:\[[^\]]*])?\{([^}]+)\}", content)
        if m:
            doc_class = m.group(1)
            if "mdpi" in doc_class.lower():
                return "mdpi"
            return doc_class
    except Exception:
        pass
    return None


def _run_latexmk_in_docker(work_dir: str, tex_name: str, compiler: str) -> bool:
    """
    Запускает latexmk внутри Docker.
    Возвращает True, если в work_dir появился PDF, даже если latexmk вернул код 1
    из‑за undefined citations/refs.
    """
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{work_dir}:/work",
                "-w", "/work",
                "texlive/texlive",
                "latexmk", f"-{compiler}",
                "-interaction=nonstopmode",
                "-file-line-error",
                "-shell-escape",
                tex_name,
            ],
            capture_output=False,
            text=True,
            timeout=240,
        )
    except subprocess.TimeoutExpired:
        print("⚠️ Тайм-аут компиляции (4 мин).")
        return False
    except Exception as e:
        print(f"💥 Ошибка запуска Docker: {e}")
        return False

    pdf_path = os.path.join(work_dir, os.path.splitext(tex_name)[0] + ".pdf")
    if os.path.exists(pdf_path):
        # PDF есть — считаем компиляцию успешной, даже если latexmk вернул 1
        return True

    # PDF нет — это реальная ошибка
    print("⚠️ PDF не найден после компиляции. Проверьте лог latexmk.")
    return False


def compile_tex_to_pdf_via_docker(tex_path):
    """Компилирует .tex файл в .pdf с помощью Docker и LuaLaTeX/XeLaTeX."""
    if not os.path.exists(tex_path):
        print("❌ Указанный .tex файл не найден.")
        return False

    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("ℹ️ Docker не запущен. Запустите Docker Desktop.")
        return False

    doc_class = detect_document_class(tex_path)
    if doc_class == "mdpi":
        compiler = "lualatex"
        print("🐳 Компиляция в PDF через Docker (LuaLaTeX для MDPI)...")
    else:
        compiler = "xelatex"
        print("🐳 Компиляция в PDF через Docker (XeLaTeX)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_dir = os.path.dirname(os.path.abspath(tex_path))
        tex_filename = os.path.basename(tex_path)

        # Копируем весь проект (tex + cls + figs + bib и т.д.)
        for item in os.listdir(tex_dir):
            src = os.path.join(tex_dir, item)
            dst = os.path.join(tmpdir, item)
            try:
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                elif os.path.isdir(src):
                    shutil.copytree(src, dst)
            except Exception as e:
                print(f"⚠️ Не удалось скопировать {item}: {e}")

        if doc_class == "mdpi":
            patch_mdpi_for_lualatex(tmpdir)

        ok = _run_latexmk_in_docker(tmpdir, tex_filename, compiler)
        if not ok:
            return False

        generated_pdf = os.path.join(tmpdir, os.path.splitext(tex_filename)[0] + ".pdf")
        if os.path.exists(generated_pdf):
            output_pdf = os.path.join(tex_dir, os.path.splitext(tex_filename)[0] + ".pdf")
            shutil.copy2(generated_pdf, output_pdf)
            print(f"✅ PDF создан: {output_pdf}")
            return True

        print("⚠️ PDF не найден после копирования.")
        return False


def compile_zip_to_pdf_via_docker(zip_path, main_tex_name):
    """Компилирует ZIP с LaTeX файлами в PDF."""
    if not os.path.exists(zip_path):
        print("❌ ZIP-файл не найден.")
        return False

    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("ℹ️ Docker не запущен. Запустите Docker Desktop.")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        full_tex_path = os.path.join(tmpdir, main_tex_name)
        if not os.path.exists(full_tex_path):
            print(f"❌ Главный .tex файл не найден: {main_tex_name}")
            return False

        doc_class = detect_document_class(full_tex_path)
        if doc_class == "mdpi":
            compiler = "lualatex"
            print("🐳 Компиляция PDF через Docker (LuaLaTeX для MDPI)...")
            patch_mdpi_for_lualatex(tmpdir)
        else:
            compiler = "xelatex"
            print("🐳 Компиляция PDF через Docker (XeLaTeX)...")

        ok = _run_latexmk_in_docker(tmpdir, main_tex_name, compiler)
        if not ok:
            return False

        generated_pdf = os.path.join(tmpdir, os.path.splitext(main_tex_name)[0] + ".pdf")
        if os.path.exists(generated_pdf):
            output_pdf = os.path.splitext(zip_path)[0] + ".pdf"
            shutil.copy2(generated_pdf, output_pdf)
            print(f"✅ PDF создан: {output_pdf}")
            return True

        print("⚠️ PDF не найден после копирования.")
        return False
