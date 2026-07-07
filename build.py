"""
图片格式批量转换工具 — PyInstaller 打包脚本
运行方式：
    python build.py            # 打包为单文件 .exe
    python build.py --clean    # 清理后重新打包
    python build.py --spec     # 仅生成 .spec 文件（不打包）
"""

import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

APP_NAME = "ImageConverter"
ENTRY_FILE = ROOT / "image_converter.py"
ICON_FILE = ROOT / "icon.ico"          # 可选：放一个 .ico 文件即可自动使用
ADD_DATA = [
    # (源文件, 目标目录) — 核心模块需随包一起
    (ROOT / "image_converter_core.py", "."),
]


# ---------------------------------------------------------------------------
# PyInstaller 参数
# ---------------------------------------------------------------------------
def build_command() -> list[str]:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        # -- 基本设置 --
        "--name", APP_NAME,
        "--onefile",                          # 打包为单个 .exe
        "--windowed",                         # 无控制台窗口（GUI 应用）
        # "--console",                        # 如需调试窗口，取消此行注释
        "--clean",                            # 每次清理临时文件

        # -- 输出目录 --
        f"--distpath={ROOT / 'dist'}",
        f"--workpath={ROOT / 'build'}",
        f"--specpath={ROOT}",

        # -- 隐藏导入（customtkinter / PIL 依赖） --
        "--hidden-import", "customtkinter",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "pillow_heif",
        "--hidden-import", "vtracer",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.messagebox",

        # -- 收集子模块 --
        "--collect-submodules", "PIL",
        "--collect-submodules", "customtkinter",
        "--collect-submodules", "vtracer",
    ]

    # 添加额外数据文件
    for src, dst in ADD_DATA:
        if src.exists():
            sep = ";" if sys.platform == "win32" else ":"
            cmd.append(f"--add-data={src}{sep}{dst}")

    # 图标（可选）
    if ICON_FILE.exists():
        cmd.append(f"--icon={ICON_FILE}")

    # 入口
    cmd.append(str(ENTRY_FILE))

    return cmd


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    clean_first = "--clean" in sys.argv
    spec_only = "--spec" in sys.argv

    if clean_first:
        for d in [ROOT / "dist", ROOT / "build"]:
            if d.exists():
                print(f"[CLEAN] {d.name}")
                shutil.rmtree(d, ignore_errors=True)

    if spec_only:
        makespec_cmd = [
            sys.executable, "-m", "PyInstaller",
            "--name", APP_NAME,
            "--onefile",
            "--windowed",
            "--hidden-import", "customtkinter",
            "--hidden-import", "PIL",
            "--hidden-import", "pillow_heif",
            "--hidden-import", "tkinter",
            "--collect-submodules", "PIL",
            "--collect-submodules", "customtkinter",
            str(ENTRY_FILE),
        ]
        print("[SPEC] Generating .spec file...")
        subprocess.run(makespec_cmd, cwd=str(ROOT), check=True)
        print(f"[OK] {APP_NAME}.spec generated.")
    else:
        cmd = build_command()
        print("[BUILD] Starting PyInstaller...")
        print(" ".join(cmd))
        subprocess.run(cmd, cwd=str(ROOT), check=True)

        exe = ROOT / "dist" / f"{APP_NAME}.exe"
        if exe.exists():
            size_mb = exe.stat().st_size / (1024 * 1024)
            print(f"\n[OK] Build complete!")
            print(f"     Output: {exe}")
            print(f"     Size:   {size_mb:.1f} MB")
        else:
            print("\n[FAIL] Build seems to have failed. Check output above.")
