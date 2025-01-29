import requests
from joblib import Parallel, delayed


# 定义文件转换函数
def convert_file(index):
    # 打开文件并准备发送
    with open("优惠政策.wps", "rb") as f:
        files = {
            "file": ("优惠政策.wps", f, "application/vnd.ms-works")
        }  # 文件字段名为 "file"

        # 发送 POST 请求
        r = requests.post("http://192.168.2.128:8500/convert", files=files)

        print(index, "\t", len(r.content))


# 使用 joblib 并发测试 10 个文件转换
if __name__ == "__main__":
    # 并发执行 10 次文件转换
    Parallel(n_jobs=10)(delayed(convert_file)(i) for i in range(100))
