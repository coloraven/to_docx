import base64
import os

import requests
from joblib import Parallel, delayed

API_URL = "http://localhost:8000/convert"
INPUT_FILE = r"C:\Users\Administrator\Desktop\WPS_Server\无法转换.wps"
SOURCE_TYPE = "wps"
TARGET_TYPE = "pptx"

if not os.path.exists(INPUT_FILE):
    print(f"文件 {INPUT_FILE} 不存在")
    exit(1)

# 读取文件并进行 Base64 编码
with open(INPUT_FILE, "rb") as f:
    file_bytes = base64.b64encode(f.read()).decode("utf-8")

# 发送 API 请求
data = {
    "fileBytes": file_bytes,
    "sourceType": SOURCE_TYPE,
    "targetType": TARGET_TYPE
}
def main(i):
    response = requests.post(API_URL, json=data)

    if response.status_code == 200:
        result = response.json()
        if result["status"] == "ok":
            print("转换成功，保存文件...")
            # output_file = f"{i}converted.{TARGET_TYPE}"
            print(i,len(base64.b64decode(result["fileBytes"])))
            # with open(output_file, "wb") as f:
            #     f.write(base64.b64decode(result["fileBytes"]))
            # print(f"转换后的文件已保存为 {output_file}")
        else:
            print("转换失败:", result.get("message", "未知错误"))
    else:
        print("请求失败，状态码:", response.status_code)

# 使用 joblib 并发测试 10 个文件转换
if __name__ == "__main__":
    # 并发执行 10 次文件转换
    Parallel(n_jobs=10)(delayed(main)(i) for i in range(100))