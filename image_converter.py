"""
图片格式批量转换工具  (CustomTkinter 版)
支持 .heic / .png / .jpg / .tiff / .bmp / .webp 格式之间无损转换

GUI 层 —— 所有业务逻辑在 image_converter_core.py 中
"""

import sys
import threading
from pathlib import Path

# ---------------------------------------------------------------------------
# 依赖检查（先检查再导入，给出友好提示）
# ---------------------------------------------------------------------------
try:
    import customtkinter as ctk
    from tkinter import filedialog, messagebox
except ImportError:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "缺少依赖",
        "请先安装 CustomTkinter：\n"
        "pip install customtkinter\n\n"
        "图片处理依赖：\n"
        "pip install pillow pillow-heif",
    )
    sys.exit(1)

try:
    from PIL import Image  # noqa: F401  — 仅验证可用性
except ImportError:
    messagebox.showerror(
        "缺少依赖",
        "请先安装 Pillow：\npip install pillow\n\n"
        "如需 HEIC 支持，还需安装：\npip install pillow-heif",
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# 导入核心模块
# ---------------------------------------------------------------------------
from image_converter_core import (
    ALL_FORMATS,
    READABLE_EXTS,
    FORMAT_HINTS,
    scan_folder,
    BatchConverter,
)


# ---------------------------------------------------------------------------
# GUI 应用
# ---------------------------------------------------------------------------
class ImageConverterApp(ctk.CTk):
    WIDTH  = 720
    HEIGHT = 680

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title("图片格式批量转换工具")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(self.WIDTH, self.HEIGHT)

        self.source_files: list[str] = []
        self._converter: BatchConverter | None = None

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # ---------- 顶部标题栏 ----------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            header, text="图片格式批量转换工具",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            header, text="FOR  MY LOVER XSN",
            font=ctk.CTkFont(size=14, weight="normal", slant="italic"),
            text_color="#e91e63",
        ).pack(side="left", padx=(8, 0), pady=(6, 0))

        # 主题切换
        self.theme_var = ctk.StringVar(value="light")
        ctk.CTkSegmentedButton(
            header,
            values=["浅色", "深色"],
            command=self._toggle_theme,
            variable=self.theme_var,
            width=140,
        ).pack(side="right")

        # ---------- 来源区域 ----------
        src_frame = ctk.CTkFrame(self)
        src_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=6)
        src_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            src_frame, text="📂  来源",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(12, 4))

        # 来源模式
        self.source_mode = ctk.StringVar(value="files")
        mode_frame = ctk.CTkFrame(src_frame, fg_color="transparent")
        mode_frame.grid(row=1, column=0, columnspan=2, sticky="w", padx=16)
        ctk.CTkRadioButton(
            mode_frame, text="选择文件",
            variable=self.source_mode, value="files",
            command=self._on_mode_change,
        ).pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(
            mode_frame, text="选择文件夹",
            variable=self.source_mode, value="folder",
            command=self._on_mode_change,
        ).pack(side="left")

        # 格式过滤
        ctk.CTkLabel(src_frame, text="过滤格式：").grid(
            row=1, column=2, sticky="e", padx=(0, 6),
        )
        self.src_format_var = ctk.StringVar(value="全部格式")
        ctk.CTkOptionMenu(
            src_frame,
            variable=self.src_format_var,
            values=["全部格式"] + ALL_FORMATS,
            width=120,
            command=lambda _: self._rescan_if_folder(),
        ).grid(row=1, column=3, sticky="w", padx=(0, 16))

        # 浏览 & 路径
        btn_row = ctk.CTkFrame(src_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=4, sticky="ew", padx=16, pady=(8, 4))
        ctk.CTkButton(
            btn_row, text="浏览…", width=90,
            command=self._browse_source,
        ).pack(side="left")

        self.src_path_var = ctk.StringVar(value="（未选择）")
        ctk.CTkLabel(
            btn_row, textvariable=self.src_path_var,
            text_color="gray", anchor="w",
        ).pack(side="left", padx=(12, 0), fill="x", expand=True)

        self.file_count_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            src_frame, textvariable=self.file_count_var,
            text_color="#2563eb", anchor="w",
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=16, pady=(0, 12))

        # ---------- 目标区域 ----------
        dst_frame = ctk.CTkFrame(self)
        dst_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        dst_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            dst_frame, text="💾  目标",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(12, 4))

        ctk.CTkLabel(dst_frame, text="目标格式：").grid(
            row=1, column=0, sticky="w", padx=16,
        )
        self.dst_format_var = ctk.StringVar(value="PNG")
        fmt_menu = ctk.CTkOptionMenu(
            dst_frame,
            variable=self.dst_format_var,
            values=ALL_FORMATS,
            width=120,
            command=self._update_format_hint,
        )
        fmt_menu.grid(row=1, column=1, sticky="w", padx=(0, 8))

        self.format_hint_var = ctk.StringVar(value=FORMAT_HINTS["PNG"])
        ctk.CTkLabel(
            dst_frame, textvariable=self.format_hint_var,
            text_color="gray", font=ctk.CTkFont(size=11),
        ).grid(row=1, column=2, columnspan=2, sticky="w", padx=(8, 16))

        dst_btn_row = ctk.CTkFrame(dst_frame, fg_color="transparent")
        dst_btn_row.grid(row=2, column=0, columnspan=4, sticky="ew", padx=16, pady=(8, 12))
        ctk.CTkButton(
            dst_btn_row, text="选择保存位置…", width=130,
            command=self._browse_dest,
        ).pack(side="left")

        self.dst_path_var = ctk.StringVar(value="（未选择）")
        ctk.CTkLabel(
            dst_btn_row, textvariable=self.dst_path_var,
            text_color="gray", anchor="w",
        ).pack(side="left", padx=(12, 0), fill="x", expand=True)

        # ---------- 进度区域 ----------
        prog_frame = ctk.CTkFrame(self)
        prog_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        prog_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            prog_frame, text="⏳  进度",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self.progress_bar = ctk.CTkProgressBar(prog_frame, height=16)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.progress_bar.set(0)

        self.progress_label_var = ctk.StringVar(value="就绪")
        ctk.CTkLabel(
            prog_frame, textvariable=self.progress_label_var, anchor="w",
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 12))

        # ---------- 操作按钮 ----------
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=4)

        self.convert_btn = ctk.CTkButton(
            btn_frame, text="开始转换",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40, width=160,
            fg_color="#2563eb", hover_color="#1d4ed8",
            command=self._start_convert,
        )
        self.convert_btn.pack(side="left")

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="停止",
            height=40, width=90,
            fg_color="#dc2626", hover_color="#b91c1c",
            state="disabled",
            command=self._stop_convert,
        )
        self.stop_btn.pack(side="left", padx=(12, 0))

        self.clear_btn = ctk.CTkButton(
            btn_frame, text="清空日志",
            height=40, width=100,
            fg_color="gray", hover_color="#6b7280",
            command=self._clear_log,
        )
        self.clear_btn.pack(side="right")

        # ---------- 日志区域 ----------
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=5, column=0, sticky="nsew", padx=20, pady=(4, 16))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            log_frame, text="📋  日志",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        self.log_text = ctk.CTkTextbox(
            log_frame, state="disabled",
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))

    # ------------------------------------------------------------------ 主题
    def _toggle_theme(self, value: str):
        ctk.set_appearance_mode("dark" if value == "深色" else "light")

    # ------------------------------------------------------------------ 格式提示
    def _update_format_hint(self, fmt: str):
        self.format_hint_var.set(FORMAT_HINTS.get(fmt, ""))

    # ------------------------------------------------------------------ 模式切换
    def _on_mode_change(self):
        self.source_files = []
        self.src_path_var.set("（未选择）")
        self.file_count_var.set("")

    def _rescan_if_folder(self):
        """文件夹模式下，切换过滤格式时自动重新扫描"""
        if self.source_mode.get() == "folder" and self.src_path_var.get() != "（未选择）":
            self._do_scan_folder(self.src_path_var.get())

    # ------------------------------------------------------------------ 浏览
    def _browse_source(self):
        mode = self.source_mode.get()
        if mode == "files":
            filetypes = [
                ("图片文件", " ".join(f"*{e}" for e in READABLE_EXTS)),
                ("所有文件", "*.*"),
            ]
            paths = filedialog.askopenfilenames(title="选择图片文件", filetypes=filetypes)
            if paths:
                self.source_files = list(paths)
                self.src_path_var.set(str(Path(paths[0]).parent))
                self.file_count_var.set(f"已选 {len(self.source_files)} 个文件")
        else:
            folder = filedialog.askdirectory(title="选择包含图片的文件夹")
            if folder:
                self.src_path_var.set(folder)
                self._do_scan_folder(folder)

    def _do_scan_folder(self, folder: str):
        """调用核心模块 scan_folder 并刷新 UI。"""
        fmt_filter = self.src_format_var.get()
        self.source_files = scan_folder(folder, fmt_filter)
        self.file_count_var.set(f"扫描到 {len(self.source_files)} 个文件")

    def _browse_dest(self):
        folder = filedialog.askdirectory(title="选择保存位置")
        if folder:
            self.dst_path_var.set(folder)

    # ------------------------------------------------------------------ 转换
    def _start_convert(self):
        if not self.source_files:
            messagebox.showwarning("提示", "请先选择来源文件或文件夹。")
            return
        dst = self.dst_path_var.get()
        if dst.startswith("（"):
            messagebox.showwarning("提示", "请选择保存位置。")
            return

        self.convert_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)
        self._log("━" * 50)
        self._log(f"开始转换  {len(self.source_files)} 个文件 → {self.dst_format_var.get()}")
        self._log("━" * 50)

        # 创建 BatchConverter 并绑定回调
        self._converter = BatchConverter(
            source_files=self.source_files,
            dst_folder=dst,
            target_format=self.dst_format_var.get(),
        )
        self._converter.on_log = self._log
        self._converter.on_progress = self._update_progress
        self._converter.on_done = self._on_convert_done

        threading.Thread(target=self._converter.run, daemon=True).start()

    def _stop_convert(self):
        if self._converter is not None:
            self._converter.stop()

    def _on_convert_done(self, success: int, errors: list[tuple[str, str]]):
        """BatchConverter 完成回调（已不在 worker 线程中）。"""
        if errors:
            detail = "\n".join(f"• {n}: {r}" for n, r in errors[:20])
            if len(errors) > 20:
                detail += f"\n… 还有 {len(errors) - 20} 个错误"
            self.after(0, lambda: messagebox.showerror(
                f"转换失败（{len(errors)} 个文件）", detail
            ))
        else:
            done_text = f"完成！成功 {success} 个，失败 0 个"
            self.after(0, lambda: messagebox.showinfo("完成", done_text))

        self.after(0, self._reset_buttons)

    # ------------------------------------------------------------------ UI 更新（线程安全）
    def _log(self, msg: str):
        def _do():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, _do)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("0.0", "end")
        self.log_text.configure(state="disabled")

    def _update_progress(self, pct: float, text: str):
        def _do():
            self.progress_bar.set(pct)
            self.progress_label_var.set(text)
        self.after(0, _do)

    def _reset_buttons(self):
        self.convert_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._converter = None


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = ImageConverterApp()
    app.mainloop()
