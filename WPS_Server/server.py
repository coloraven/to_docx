import base64
import contextlib
import os
import subprocess
import tempfile
import threading
import time

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pywpsrpc.common import S_OK
from pywpsrpc.rpcetapi import createEtRpcInstance, etapi
from pywpsrpc.rpcwppapi import createWppRpcInstance, wppapi
from pywpsrpc.rpcwpsapi import createWpsRpcInstance, wpsapi


# ---------------------------
# 定义 xvfb 上下文管理器
# ---------------------------
@contextlib.contextmanager
def xvfb_run(display=":99", screen="0", resolution="800x600x16"):
    """
    启动 Xvfb 虚拟桌面，并设置环境变量 DISPLAY。
    使用以下参数启动 Xvfb：
      Xvfb :99 -screen 0 800x600x16 -nolisten tcp -auth /tmp/xvfb-run.iNFExt/Xauthority
    其中降低了分辨率以减少内存占用。
    """
    cmd = [
        "Xvfb",
        display,
        "-screen", screen, resolution,
        "-nolisten", "tcp",
        "-auth", "/tmp/xvfb-run.iNFExt/Xauthority"
    ]
    xvfb_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # 等待 Xvfb 启动（视环境情况可调整等待时间或检测启动状态）
    time.sleep(1)
    original_display = os.environ.get("DISPLAY")
    os.environ["DISPLAY"] = display
    try:
        yield
    finally:
        if original_display is not None:
            os.environ["DISPLAY"] = original_display
        else:
            os.environ.pop("DISPLAY", None)
        xvfb_proc.terminate()
        xvfb_proc.wait()

# ---------------------------
# 定义支持的格式映射
# ---------------------------
formats = {
    # WPS 文字
    "doc": wpsapi.wdFormatDocument,
    "docx": wpsapi.wdFormatXMLDocument,
    "rtf": wpsapi.wdFormatRTF,
    "html": wpsapi.wdFormatHTML,
    "pdf": wpsapi.wdFormatPDF,
    "xml": wpsapi.wdFormatXML,
    "wps": '',
    # WPS 演示
    "ppt": wppapi.ppSaveAsPresentation,
    "pptx": wppapi.ppSaveAsOpenXMLPresentation,
    "dps": '',
    # WPS 表格
    "xls": etapi.xlExcel8,
    "xlsx": etapi.xlOpenXMLWorkbook,
    "csv": etapi.xlCSV,
    "et": '',
}

# ---------------------------
# 定义请求体
# ---------------------------
class ConvertRequest(BaseModel):
    fileBytes: str  # Base64 编码的文件内容
    sourceType: str  # 源文件类型（如 docx, pdf）
    targetType: str  # 目标文件类型（如 doc, pdf）

# ---------------------------
# 启动 FastAPI
# ---------------------------
app = FastAPI()

class ConvertException(Exception):
    def __init__(self, text, hr):
        self.text = text
        self.hr = hr

    def __str__(self):
        return f"Convert failed: {self.text}, ErrCode: {hex(self.hr & 0xFFFFFFFF)}"

# 全局锁，确保同一时间只有一个 WPS（或相关）实例在工作
conversion_lock = threading.Lock()

# ---------------------------
# 文件转换函数
# ---------------------------
def convert_file(input_file, output_file, target_format):
    with conversion_lock:
        # 在转换时启动 xvfb 虚拟桌面
        with xvfb_run():
            ext = input_file.rsplit('.', 1)[-1].lower()
            hr = S_OK  # 初始化 hr

            if ext in ['doc', 'docx', 'rtf', 'html', 'pdf', 'xml', 'wps']:
                hr, rpc = createWpsRpcInstance()
                hr, app_instance = rpc.getWpsApplication()
                app_instance.Visible = False
                docs = app_instance.Documents
                hr, doc = docs.Open(input_file, ReadOnly=True)
                if hr != S_OK:
                    app_instance.Quit()
                    raise ConvertException("Failed to open document", hr)
                hr = doc.SaveAs2(output_file, FileFormat=formats[target_format])
                doc.Close(wpsapi.wdDoNotSaveChanges)
                app_instance.Quit()

            elif ext in ['ppt', 'pptx', 'dps']:
                hr, rpc = createWppRpcInstance()
                hr, app_instance = rpc.getWppApplication()
                presentations = app_instance.Presentations
                hr, presentation = presentations.Open(input_file, WithWindow=False)
                if hr != S_OK:
                    app_instance.Quit()
                    raise ConvertException("Failed to open presentation", hr)
                hr = presentation.SaveAs(output_file, FileFormat=formats[target_format])
                presentation.Close()
                app_instance.Quit()

            elif ext in ['xls', 'xlsx', 'csv', 'et']:
                hr, rpc = createEtRpcInstance()
                hr, app_instance = rpc.getEtApplication()
                app_instance.Visible = False
                workbooks = app_instance.Workbooks
                hr, workbook = workbooks.Open(input_file)
                if hr != S_OK:
                    app_instance.Quit()
                    raise ConvertException("Failed to open workbook", hr)
                hr = workbook.SaveAs(output_file, FileFormat=formats[target_format])
                workbook.Close()
                app_instance.Quit()
            
            if hr != S_OK:
                raise ConvertException("Failed to save file", hr)

# ---------------------------
# API 路由
# ---------------------------
@app.post("/convert")
def convert(request: ConvertRequest):
    if request.sourceType not in formats or request.targetType not in formats:
        return {"status": "error", "message": "Unsupported file type"}
    if request.sourceType == "dps" and request.targetType == "pdf":
        return {"status": "error", "message": "不支持dps（演示文稿）转换为pdf!"}

    try:
        file_data = base64.b64decode(request.fileBytes)
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{request.sourceType}") as temp_input:
            temp_input.write(file_data)
            temp_input_path = temp_input.name

        temp_output_path = temp_input_path.replace(f".{request.sourceType}", f".{request.targetType}")
        convert_file(temp_input_path, temp_output_path, request.targetType)

        with open(temp_output_path, "rb") as output_file:
            converted_file_data = base64.b64encode(output_file.read()).decode("utf-8")

        os.remove(temp_input_path)
        os.remove(temp_output_path)
        
        return {"status": "ok", "fileBytes": converted_file_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------
# 单独线程：每 3 秒检测并结束 wpscloudsvr 进程
# ---------------------------
def monitor_wpscloudsvr():
    while True:
        subprocess.call(["pkill", "-f", "/opt/kingsoft/wps-office/office6/wpscloudsvr"])
        time.sleep(3)

# ---------------------------
# 主程序入口
# ---------------------------
if __name__ == "__main__":
    monitor_thread = threading.Thread(target=monitor_wpscloudsvr, daemon=True)
    monitor_thread.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
