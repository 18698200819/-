# 图片格式批量转换工具

基于 CustomTkinter 的图片格式批量转换工具，支持 HEIC / PNG / JPEG / TIFF / BMP / WEBP / ICO 格式之间无损转换。

## 功能

- **多格式支持**: HEIC、PNG、JPEG、TIFF、BMP、WEBP、ICO 互相转换
- **批量处理**: 选择单个文件或整个文件夹批量转换
- **格式过滤**: 按源文件格式筛选，只转换需要的图片
- **浅色/深色主题**: 支持浅色和深色两种 UI 主题
- **线程安全**: 后台线程转换，界面不卡顿，支持随时停止

## 运行

```bash
pip install -r requirements.txt
python image_converter.py
```

## 打包为 Windows exe

```bash
python build.py          # 打包为单文件 .exe
python build.py --clean  # 清理旧文件后重新打包
```

输出在 `dist/ImageConverter.exe`。

## 项目结构

```
├── image_converter.py       # GUI 层（CustomTkinter）
├── image_converter_core.py  # 核心模块（格式转换、批量处理）
├── build.py                 # PyInstaller 打包脚本
├── requirements.txt         # Python 依赖
└── .gitignore
```

## FOR LOVER
