from unoserver.client import UnoClient

client = UnoClient("btzry.top", 2003, "remote")


def doc_convert(binary_data, target_format="docx"):
    # 调用 convert 函数，传递二进制数据
    result: bytes = client.convert(
        inpath=None,
        indata=binary_data,
        outpath=None,  # 输出路径为 None，返回字节流
        convert_to=target_format,  # 目标格式
        filtername=None,  # 自动选择导出过滤器
        filter_options=[],  # 无过滤器选项
        update_index=True,  # 更新索引
        infiltername=None,  # 自动选择导入过滤器
    )
    return result
