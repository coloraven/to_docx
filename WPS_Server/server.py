import base64
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


# ------------------------------------------------------------------------------
# 定义全局的 Xvfb 管理器
# ------------------------------------------------------------------------------
class XvfbManager:
    def __init__(self, display=":99", screen="0", resolution="800x600x16",
                 auth="/tmp/xvfb-run.iNFExt/Xauthority", idle_timeout=10):
        """
        :param display: 虚拟桌面号，如 :99
        :param screen: 屏幕号，通常为 "0"
        :param resolution: 分辨率与色深，示例 "800x600x16" 可降低资源占用
        :param auth: Xvfb 启动时使用的认证文件路径
        :param idle_timeout: 空闲多长时间（秒）后自动关闭 Xvfb
        """
        self.display = display
        self.screen = screen
        self.resolution = resolution
        self.auth = auth
        self.idle_timeout = idle_timeout
        self.process = None
        self.last_used = None
        self.lock = threading.Lock()
        self.shutdown_timer = None

    def start_if_not_running(self):
        """如果 Xvfb 尚未启动，则启动；否则更新最后使用时间，并取消待关闭计时器。"""
        with self.lock:
            if self.process is None:
                cmd = [
                    "Xvfb", self.display,
                    "-screen", self.screen, self.resolution,
                    "-nolisten", "tcp",
                    "-auth", self.auth
                ]
                self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # 等待 Xvfb 启动
                time.sleep(1)
                os.environ["DISPLAY"] = self.display
            self.last_used = time.time()
            if self.shutdown_timer is not None:
                self.shutdown_timer.cancel()
                self.shutdown_timer = None

    def schedule_shutdown(self):
        """调度一个计时器，在空闲 idle_timeout 秒后关闭 Xvfb。"""
        with self.lock:
            if self.shutdown_timer is not None:
                self.shutdown_timer.cancel()
            self.shutdown_timer = threading.Timer(self.idle_timeout, self.shutdown_if_idle)
            self.shutdown_timer.start()

    def shutdown_if_idle(self):
        """如果距离上次使用超过 idle_timeout，则关闭 Xvfb。"""
        with self.lock:
            now = time.time()
            if self.last_used is None or now - self.last_used >= self.idle_timeout:
                if self.process is not None:
                    self.process.terminate()
                    self.process.wait()
                    self.process = None

# 实例化全局的 Xvfb 管理器
xvfb_manager = XvfbManager()

# ------------------------------------------------------------------------------
# 定义支持的文件格式映射
# ------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------
# 定义请求体
# ------------------------------------------------------------------------------
class ConvertRequest(BaseModel):
    fileBytes: str  # Base64 编码的文件内容
    sourceType: str  # 源文件类型（如 docx, pdf）
    targetType: str  # 目标文件类型（如 doc, pdf）

# ------------------------------------------------------------------------------
# 启动 FastAPI 应用
# ------------------------------------------------------------------------------
app = FastAPI()

class ConvertException(Exception):
    def __init__(self, text, hr):
        self.text = text
        self.hr = hr

    def __str__(self):
        return f"Convert failed: {self.text}, ErrCode: {hex(self.hr & 0xFFFFFFFF)}"

# 使用全局锁，确保同一时间只有一个 WPS（或相关）实例在工作
conversion_lock = threading.Lock()

# ------------------------------------------------------------------------------
# 文件转换函数（转换期间自动启动/刷新 Xvfb，并在结束后调度关闭）
# ------------------------------------------------------------------------------
def convert_file(input_file, output_file, target_format):
    with conversion_lock:
        # 启动或刷新 Xvfb
        xvfb_manager.start_if_not_running()
        try:
            ext = input_file.rsplit('.', 1)[-1].lower()
            hr = S_OK  # 初始化返回码

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
        finally:
            # 无论转换成功与否，都调度10秒后关闭 Xvfb（如果10秒内无新的转换请求，该进程将被终止）
            xvfb_manager.schedule_shutdown()

# ------------------------------------------------------------------------------
# API 路由：转换接口
# ------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------
# 后台线程：每 3 秒检测并结束 /opt/kingsoft/wps-office/office6/wpscloudsvr 进程
# ------------------------------------------------------------------------------
def monitor_wpscloudsvr():
    while True:
        subprocess.call(["pkill", "-f", "/opt/kingsoft/wps-office/office6/wpscloudsvr"])
        time.sleep(3)

# ------------------------------------------------------------------------------
# 主程序入口
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # 启动监控线程（守护线程，主程序退出时自动结束）
    monitor_thread = threading.Thread(target=monitor_wpscloudsvr, daemon=True)
    monitor_thread.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
