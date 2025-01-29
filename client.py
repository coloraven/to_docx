import requests

# 打开文件并准备发送
with open("优惠政策.wps", "rb") as f:
    files = {
        "file": ("优惠政策.wps", f, "application/vnd.ms-works")
    }  # 文件字段名为 "file"
    # 添加目标格式参数
    data = {"target_format": "pdf"}
    # 发送 POST 请求
    r = requests.post("http://192.168.2.128:8500/convert", files=files, data=data)
    with open("test.pdf", "wb") as f:
        f.write(r.content)
