import os
import subprocess
import threading

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# 临时文件保存路径
TEMP_DIR = "/tmp/converted_files"

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# 静态文件目录（用于存储 HTML、CSS、JS 文件）
STATIC_DIR = "./static"

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)


# 定义文件删除任务
def delete_file_later(file_path: str, delay: int):
    """在指定延迟时间后删除文件"""

    def delete_task():
        if os.path.exists(file_path):
            os.remove(file_path)

    threading.Timer(delay, delete_task).start()


@app.post("/convert/")
async def convert_file(
    file: UploadFile = File(...),
    target_format: str = "docx",
    retention_time: int = 3 * 60 * 60,  # 默认保留时间为 3 小时（以秒为单位）
):
    """
    上传文件并转换为指定格式
    :param file: 上传的文件
    :param target_format: 转换的目标格式，默认为 docx
    :param retention_time: 文件保留的时间，以秒为单位，默认 3 小时
    """
    # 保存上传的文件
    input_file_path = os.path.join(TEMP_DIR, file.filename)
    with open(input_file_path, "wb") as f:
        f.write(await file.read())

    # 目标文件路径
    output_file_name = f"{os.path.splitext(file.filename)[0]}.{target_format}"
    output_file_path = os.path.join(TEMP_DIR, output_file_name)

    # 使用 LibreOffice 进行文件转换
    try:
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                target_format,
                input_file_path,
                "--outdir",
                TEMP_DIR,
            ],
            check=True,
        )

        # 添加文件删除任务
        delete_file_later(input_file_path, delay=retention_time)  # 上传文件
        delete_file_later(output_file_path, delay=retention_time)  # 转换后的文件

        # 返回文件下载路径
        return {
            "message": "File converted successfully",
            "download_url": f"/download/{output_file_name}",
            "retention_time": retention_time,
        }

    except subprocess.CalledProcessError as e:
        return {"error": f"Conversion failed: {e}"}


@app.get("/download/{file_name}")
async def download_file(file_name: str):
    """提供转换后的文件下载"""
    file_path = os.path.join(TEMP_DIR, file_name)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=file_name)
    else:
        return {"error": "File not found"}


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """返回 Web UI HTML 页面"""
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# 将静态文件目录挂载
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
