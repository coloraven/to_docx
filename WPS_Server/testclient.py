import base64
import os

import requests

API_URL = "http://localhost:8565/convert"
INPUT_FILE = "无法转换.wps"
SOURCE_TYPE = "wps"
TARGET_TYPE = "docx"

if not os.path.exists(INPUT_FILE):
    print(f"文件 {INPUT_FILE} 不存在")
    exit(1)

# 读取文件并进行 Base64 编码
with open(INPUT_FILE, "rb") as f:
    file_bytes = base64.b64encode(f.read()).decode("utf-8")

# 发送 API 请求
data = {
    "filebytes": file_bytes,
    "sourcetype": SOURCE_TYPE,
    "targettype": TARGET_TYPE
}

response = requests.post(API_URL, json=data)

if response.status_code == 200:
    result = response.json()
    if result["status"] == "ok":
        print("转换成功，保存文件...")
        output_file = f"converted.{TARGET_TYPE}"
        with open(output_file, "wb") as f:
            f.write(base64.b64decode(result["filebytes"]))
        print(f"转换后的文件已保存为 {output_file}")
    else:
        print("转换失败:", result.get("message", "未知错误"))
else:
    print("请求失败，状态码:", response.status_code)