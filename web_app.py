"""
图片格式批量转换工具 — Web 版
FastAPI + Tailwind CSS + Alpine.js
"""

import os
import io
import json
import uuid
import shutil
import asyncio
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# 复用原有核心转换模块
# ---------------------------------------------------------------------------
from image_converter_core import convert_image, ALL_FORMATS, FORMAT_HINTS

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
UPLOAD_DIR = Path(tempfile.gettempdir()) / "img_converter_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024   # 50 MB / 单文件
MAX_TOTAL_SIZE = 200 * 1024 * 1024 # 200 MB / 批次

SUPPORTED_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp",
    ".tiff", ".tif", ".ico", ".svg", ".heic", ".heif",
}

FORMAT_EXT_MAP = {
    "PNG": ".png", "JPEG": ".jpg", "TIFF": ".tiff",
    "BMP": ".bmp", "WEBP": ".webp", "ICO": ".ico",
    "SVG": ".svg", "HEIC": ".heic",
}

FORMAT_ICONS = {
    "PNG": "🖼️", "JPEG": "📷", "TIFF": "🖨️", "BMP": "🎨",
    "WEBP": "⚡", "ICO": "🪟", "SVG": "✏️", "HEIC": "🍎",
}

# ---------------------------------------------------------------------------
# 应用状态
# ---------------------------------------------------------------------------
tasks: dict = {}          # { task_id: { ... } }
task_lock = asyncio.Lock()


async def cleanup_stale_tasks():
    """每 10 分钟清理超过 1 小时的任务"""
    while True:
        await asyncio.sleep(600)
        async with task_lock:
            cutoff = datetime.now() - timedelta(hours=1)
            stale = [k for k, v in tasks.items()
                     if v.get("created_at", datetime.now()) < cutoff]
            for k in stale:
                shutil.rmtree(tasks[k].get("dir", ""), ignore_errors=True)
                del tasks[k]

# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------
app = FastAPI(title="图片格式转换工具")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.on_event("startup")
async def startup():
    asyncio.create_task(cleanup_stale_tasks())


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "formats": ALL_FORMATS,
            "format_hints": FORMAT_HINTS,
            "format_icons": FORMAT_ICONS,
        },
    )


# ---------------------------------------------------------------------------
# 文件上传
# ---------------------------------------------------------------------------
@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "请选择至少一个文件")

    task_dir = UPLOAD_DIR / uuid.uuid4().hex[:12]
    task_dir.mkdir()
    results = []
    skipped = 0
    total_size = 0

    for f in files:
        ext = Path(f.filename or "file").suffix.lower()
        # 跳过不支持的格式
        if ext not in SUPPORTED_EXTS:
            skipped += 1
            continue

        data = await f.read()
        # 跳过空文件
        if len(data) == 0:
            skipped += 1
            continue

        total_size += len(data)
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(413, f"总文件大小超过 {MAX_TOTAL_SIZE // 1024 // 1024}MB 限制")
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(413, f"单文件大小超过 {MAX_FILE_SIZE // 1024 // 1024}MB 限制")

        file_id = uuid.uuid4().hex[:10]
        saved_path = task_dir / f"{file_id}{ext}"
        saved_path.write_bytes(data)

        results.append({
            "id": file_id,
            "name": f.filename,
            "size": len(data),
            "ext": ext,
        })

    if not results:
        raise HTTPException(400, "未找到任何支持的图片文件")

    return {"task_dir": str(task_dir), "files": results, "skipped": skipped}


# ---------------------------------------------------------------------------
# 转换（SSE 流式进度）
# ---------------------------------------------------------------------------
class ConvertRequest(BaseModel):
    files: list          # [{id, name, ext}]
    target_format: str = "PNG"
    task_dir: str = ""


@app.post("/api/convert")
async def convert(req: ConvertRequest):
    if not req.files:
        raise HTTPException(400, "无文件")
    if req.target_format not in ALL_FORMATS:
        raise HTTPException(400, "不支持的目标格式")
    if not req.task_dir or not Path(req.task_dir).exists():
        raise HTTPException(400, "上传目录不存在")

    file_list = req.files
    task_id = uuid.uuid4().hex[:10]
    out_dir = Path(req.task_dir) / "converted"
    out_dir.mkdir(exist_ok=True)

    async with task_lock:
        tasks[task_id] = {
            "id": task_id,
            "dir": req.task_dir,
            "out_dir": str(out_dir),
            "format": req.target_format,
            "status": "processing",
            "results": [],
            "created_at": datetime.now(),
        }

    async def event_stream():
        total = len(file_list)
        success_count = 0
        error_count = 0
        target_ext = FORMAT_EXT_MAP[req.target_format]

        for idx, f in enumerate(file_list, 1):
            src = Path(req.task_dir) / f"{f['id']}{f['ext']}"
            out_name = f"{Path(f['name']).stem}{target_ext}"
            dst = out_dir / out_name

            try:
                await asyncio.to_thread(convert_image, str(src), str(dst), req.target_format)
                success_count += 1
                file_size = dst.stat().st_size
                result_entry = {"name": out_name, "id": f["id"], "size": file_size}
                async with task_lock:
                    tasks[task_id]["results"].append(result_entry)
                yield f"event: file_done\ndata: {json.dumps({'index': idx, 'total': total, 'name': out_name, 'success': True, 'size': file_size})}\n\n"
            except Exception as exc:
                error_count += 1
                yield f"event: file_done\ndata: {json.dumps({'index': idx, 'total': total, 'name': f['name'], 'success': False, 'error': str(exc)[:200]})}\n\n"

        async with task_lock:
            tasks[task_id]["status"] = "done"

        yield f"event: done\ndata: {json.dumps({'task_id': task_id, 'success': success_count, 'errors': error_count})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# 文件下载
# ---------------------------------------------------------------------------
@app.get("/api/download/{task_id}/{filename}")
async def download_file(task_id: str, filename: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    path = Path(task["out_dir"]) / filename
    if not path.exists():
        raise HTTPException(404, "文件不存在")
    return FileResponse(
        str(path),
        filename=filename,
        media_type="application/octet-stream",
    )


@app.get("/api/download-all/{task_id}")
async def download_all(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    results = task.get("results", [])
    if not results:
        raise HTTPException(404, "无文件可下载")

    out_dir = Path(task["out_dir"])

    # 单文件直接返回
    if len(results) == 1:
        path = out_dir / results[0]["name"]
        if path.exists():
            return FileResponse(str(path), filename=results[0]["name"])

    # 多文件打包 ZIP（内存中）
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            path = out_dir / r["name"]
            if path.exists():
                zf.write(path, r["name"])
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="converted_images.zip"'},
    )


# ---------------------------------------------------------------------------
# 任务状态查询
# ---------------------------------------------------------------------------
@app.get("/api/task/{task_id}")
async def get_task(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return {
        "id": task["id"],
        "status": task["status"],
        "format": task["format"],
        "results": task["results"],
    }


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
