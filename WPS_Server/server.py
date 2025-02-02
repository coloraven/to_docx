import base64
import os
import tempfile

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pywpsrpc.common import S_OK
from pywpsrpc.rpcetapi import createEtRpcInstance, etapi
from pywpsrpc.rpcwppapi import createWppRpcInstance, wppapi
from pywpsrpc.rpcwpsapi import createWpsRpcInstance, wpsapi

# 支持的格式映射
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

# 定义请求体
class ConvertRequest(BaseModel):
    fileBytes: str  # Base64 编码的文件内容
    sourceType: str  # 源文件类型（如 docx, pdf）
    targetType: str  # 目标文件类型（如 doc, pdf）

# 启动 FastAPI
app = FastAPI()

class ConvertException(Exception):
    def __init__(self, text, hr):
        self.text = text
        self.hr = hr

    def __str__(self):
        return f"Convert failed: {self.text}, ErrCode: {hex(self.hr & 0xFFFFFFFF)}"

# 文件转换函数
def convert_file(input_file, output_file, target_format):
    ext = input_file.rsplit('.', 1)[-1].lower()

    if ext in ['doc', 'docx', 'rtf', 'html', 'pdf', 'xml', 'wps']:
        hr, rpc = createWpsRpcInstance()
        hr, app = rpc.getWpsApplication()
        app.Visible = False
        docs = app.Documents
        hr, doc = docs.Open(input_file, ReadOnly=True)
        if hr != S_OK:
            app.Quit()
            raise ConvertException("Failed to open document", hr)
        hr = doc.SaveAs2(output_file, FileFormat=formats[target_format])
        doc.Close(wpsapi.wdDoNotSaveChanges)
        app.Quit()
    if ext in ['ppt', 'pptx', 'dps']:
        hr, rpc = createWppRpcInstance()
        hr, app = rpc.getWppApplication()
        # app.Visible = wppapi.MsoTriState.msoFalse
        presentations = app.Presentations
        hr, presentation = presentations.Open(input_file, WithWindow=False)
        if hr != S_OK:
            app.Quit()
            raise ConvertException("Failed to open presentation", hr)
        hr = presentation.SaveAs(output_file, FileFormat=formats[target_format])
        presentation.Close()
        app.Quit()
    if ext in ['xls', 'xlsx', 'csv', 'et']:
        hr, rpc = createEtRpcInstance()
        hr, app = rpc.getEtApplication()
        app.Visible = False
        workbooks = app.Workbooks
        hr, workbook = workbooks.Open(input_file)
        if hr != S_OK:
            app.Quit()
            raise ConvertException("Failed to open workbook", hr)
        hr = workbook.SaveAs(output_file, FileFormat=formats[target_format])
        workbook.Close()
        app.Quit()
    

    if hr != S_OK:
        raise ConvertException("Failed to save file", hr)

# API 路由
@app.post("/convert")
def convert(request: ConvertRequest):
    if request.sourceType not in formats or request.targetType not in formats:
        return {"status": "error", "message": "Unsupported file type"}
        # raise HTTPException(status_code=400, detail="Unsupported file type")
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

# 运行 API 服务器 
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
