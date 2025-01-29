import asyncio
import base64
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from importlib import metadata
from xmlrpc.client import ServerProxy

import uvicorn
from fastapi import FastAPI, File, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

class ConvertRequest(BaseModel):
    fileBytes: str   # Base64 编码的二进制数据
    sourceType: str
    targetType: str  # 例如 "pdf"


# 创建线程池
executor = ThreadPoolExecutor(max_workers=4)
API_VERSION = "3"
__version__ = metadata.version("unoserver")
logger = logging.getLogger("unoserver")

class UnoClient:
    def __init__(self, server="127.0.0.1", port="2003", host_location="auto"):
        self.server = server
        self.port = port
        if host_location == "auto":
            if server in ("127.0.0.1", "localhost"):
                self.remote = False
            else:
                self.remote = True
        elif host_location == "remote":
            self.remote = True
        elif host_location == "local":
            self.remote = False
        else:
            raise RuntimeError("host_location can be 'auto', 'remote', or 'local'")

    def _connect(self, proxy, retries=5, sleep=10):
        while retries > 0:
            try:
                info = proxy.info()
                if not info["api"] == API_VERSION:
                    raise RuntimeError(
                        f"API Version mismatch. Client {__version__} uses API {API_VERSION} "
                        f"while Server {info['unoserver']} uses API {info['api']}."
                    )
                return info
            except ConnectionError as e:
                logger.debug(f"Error {e.strerror}, waiting...")
                retries -= 1
                if retries > 0:
                    time.sleep(sleep)
                    logger.debug("Retrying...")
                else:
                    raise

    def convert(
        self,
        inpath=None,
        indata=None,
        outpath=None,
        convert_to=None,
        filtername=None,
        filter_options=[],
        update_index=True,
        infiltername=None,
    ):
        if inpath is None and indata is None:
            raise RuntimeError("Nothing to convert.")

        if inpath is not None and indata is not None:
            raise RuntimeError("You can only pass in inpath or indata, not both.")

        if convert_to is None:
            if outpath is None:
                raise RuntimeError(
                    "If you don't specify an output path, you must specify a file-type."
                )
            else:
                convert_to = os.path.splitext(outpath)[-1].strip(os.path.extsep)

        with ServerProxy(f"http://{self.server}:{self.port}", allow_none=True) as proxy:
            logger.info("Connecting.")
            logger.debug(f"Host: {self.server} Port: {self.port}")
            info = self._connect(proxy)

            if infiltername and infiltername not in info["import_filters"]:
                existing = "\n".join(sorted(info["import_filters"]))
                logger.critical(
                    f"Unknown import filter: {infiltername}. Available filters:\n{existing}"
                )
                raise RuntimeError("Invalid parameter")

            if filtername and filtername not in info["export_filters"]:
                existing = "\n".join(sorted(info["export_filters"]))
                logger.critical(
                    f"Unknown export filter: {filtername}. Available filters:\n{existing}"
                )
                raise RuntimeError("Invalid parameter")

            logger.info("Converting.")
            result = proxy.convert(
                inpath,
                indata,
                None if self.remote else outpath,
                convert_to,
                filtername,
                filter_options,
                update_index,
                infiltername,
            )
            if result is not None:
                # We got the file back over xmlrpc:
                if outpath:
                    logger.info(f"Writing to {outpath}.")
                    with open(outpath, "wb") as outfile:
                        outfile.write(result.data)
                else:
                    # Return the result as a blob
                    logger.info(f"Returning {len(result.data)} bytes.")
                    return result.data
            else:
                logger.info(f"Saved to {outpath}.")

client = UnoClient(server="127.0.0.1", port = 2003)
def sync_convert(infileData:bytes=None,convert_to:str="docx"):
    result = client.convert(
        inpath=None,
        indata=infileData,
        outpath=None,
        convert_to=convert_to,
        filtername=None,
        filter_options=[],
        update_index=True,
        infiltername=None,
    )
    return result

@app.post("/convert")
async def convert_file(request: ConvertRequest):
    print(request.sourceType,"==>",request.targetType)
    if request.sourceType=='pdf':
        return JSONResponse(content={"error":f"unsurpported source file type"})
    if request.sourceType in ['ppt','pptx'] and request.targetType in ['doc','docx','xls','xlsx']:
        return JSONResponse(content={"error":f"unsurpported that source file type ({request.sourceType}) to the targetType:{request.targetType}"})
    # Base64 解码
    binary_data = base64.b64decode(request.fileBytes)

    # 执行转换
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            executor, sync_convert, binary_data, request.targetType
        )
        return Response(content=result, media_type="application/octet-stream")
    except Exception as e:
        print('执行转换失败：',request.sourceType,"==>",request.targetType,e,)
        return JSONResponse(content={"error":f"{e}"})

@app.post("/uploadfile")
async def convert_file(
    file: UploadFile = File(...),
    target_format: str = "docx",
):
    """For test"""
    binary_data = await file.read()
    # 执行转换
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            executor, sync_convert, binary_data, target_format
        )
        return Response(content=result, media_type="application/octet-stream")
    except Exception as e:
        print(e)
    

if __name__ == "__main__":
    print("start uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8001)