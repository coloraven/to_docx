### 部署
```bash
docker build -t uno_api .
docker run -itd \
    --name uno_api \
    -p 8000:8000 \
    -p 2003:2003 \ # 可选
    uno_api
```

`8000`端口提供`web api`服务  
`2003`端口提供原unoserver的`xmlrpc`服务.

#### 客户端测试
```python
import base64

import requests
from joblib import Parallel, delayed

test_path = 'test.dps'

def convert_file(index):
    with open(test_path,'rb') as f:
        encoded_bytes = base64.b64encode(f.read()).decode()
        # 添加目标格式参数
    jsondata = {"fileBytes": encoded_bytes, "targetType": "pdf", "sourceType":"dps"}
    # 发送 POST 请求
    r = requests.post("http://192.168.2.128:8000/convert", json=jsondata)
    # print(r.content)
    with open(f"{index}_client_test.pdf", "wb") as f:
        f.write(r.content)

# 使用 joblib 并发测试 100 个文件转换
if __name__ == "__main__":
    # 并发执行 100 次文件转换
    Parallel(n_jobs=10)(delayed(convert_file)(i) for i in range(100))
```
## 批量转换客户端
建议在`GitHub CodeSpace`下编译
```bash
sudo apt install mingw-w64 -y
GOOS=windows GOARCH=amd64 go build -o converter_winx64.exe main.go # win64
GOOS=windows GOARCH=386 go build -o converter_winx86.exe main.go # win32
```
不添加任何参数时，`converter.exe`将自动查找当前目录及其子目录下的`ppt,doc,xls,wps,dps,et`文件分别对应转为`pptx,docx,xlsx,docx,pptx,xlsx`:
    "ppt" => "pptx"
    "dps" => "pptx"
	"doc" => "docx"
    "wps" => "docx"
	"xls" => "xlsx"
    "et"  => "xlsx"
**进阶用法**：  

```md
-s 服务地址({ip}:{port})，默认192.168.2.128:8500
-t 目标格式，不指定时默认按照上述映射关系尽心转换，当指定为`pdf`时，且`-f`未指定时，自动查找`"doc", "docx", "wps", "et", "xls", "xlsx", "txt", "csv", "tsv", "dps", "ppt", "pptx"`格式文件
-f 查找指定的以,分隔的多种文件格式
-o 指定时按照原来的目录结构输出文件到指定目录，不指定时，默认输出文件到原文件所在目录，并会将原文件全部转移到程序所在目录的`源文件`子目录中
```

## 其他
1. 经过测试，当转换仓库根目录下的`无法转换.wps`
这个文件时，服务端`CPU`一直高占用，LibreOffice假死，使用LibreOffice桌面版程序也打不开，程序假死，已向LibreOffice官方[反映](https://bugs.documentfoundation.org/show_bug.cgi?id=164929)。  


    > **此文件来源**：谷歌搜索`9937311.wps`或者`wps文件 filetype:wps`看到的，原始下载链接为：https://www.haizhu.gov.cn/gzhzcg/attachment/7/7706/7706583/9937311.wps。


2. `test\sub`目录下的`test.dps`来源：谷歌搜索`简历 filetype:ppt`然后使用`wps`软件另存为而来。
