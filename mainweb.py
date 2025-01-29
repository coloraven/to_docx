import asyncio
from concurrent.futures import ThreadPoolExecutor

import uvicorn
from fastapi import FastAPI, File, Response, UploadFile
from unoserver.client import UnoClient

app = FastAPI()

# 初始化 UnoClient
client = UnoClient()

# 创建线程池
executor = ThreadPoolExecutor(max_workers=4)


def sync_convert(binary_data, target_format):
    return client.convert(
        inpath=None,
        indata=binary_data,
        outpath=None,
        convert_to=target_format,
        filtername=None,
        filter_options=[],
        update_index=True,
        infiltername=None,
    )


@app.post("/convert/")
async def convert_file(file: UploadFile = File(...), target_format: str = "docx"):
    binary_data = await file.read()

    # 将同步任务放到线程池中运行
    result = await asyncio.get_event_loop().run_in_executor(
        executor, sync_convert, binary_data, target_format
    )

    return Response(content=result, media_type="application/octet-stream")


if __name__ == "__main__":
    print("start uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=4)
