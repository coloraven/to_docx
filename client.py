import base64

import requests
from joblib import Parallel, delayed


def convert_file(index):
    with open(r"ttt.dps",'rb') as f:
        encoded_bytes = base64.b64encode(f.read()).decode()
        # 添加目标格式参数
    jsondata = {"fileBytes": encoded_bytes, "targetType": "pdf", "sourceType":"dps"}
    # 发送 POST 请求
    r = requests.post("http://192.168.2.128:8500/convert", json=jsondata)
    # print(r.content)
    with open(f"{index}_client_test.pdf", "wb") as f:
        f.write(r.content)

# 使用 joblib 并发测试 10 个文件转换
if __name__ == "__main__":
    # 并发执行 10 次文件转换
    Parallel(n_jobs=10)(delayed(convert_file)(i) for i in range(1))