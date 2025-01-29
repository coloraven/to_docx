import os
import time

import requests

# API 地址
API_CONVERT_URL = "http://192.168.2.128:8500/convert"
API_DOWNLOAD_URL = "http://192.168.2.128:8500/download/"

# 定义当前目录和输出目录
current_dir = os.getcwd()
output_dir = os.path.join(current_dir, "converted_files")

# 创建输出目录
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 支持的文件扩展名
supported_extensions = [".doc", ".wps"]


def convert_file(file_path):
    """调用 API 转换文件"""
    with open(file_path, "rb") as file:
        filename = os.path.basename(file_path)
        print(f"Converting: {filename}...")
        response = requests.post(
            API_CONVERT_URL,
            files={"file": file},
            data={"target_format": "docx", "retention_time": "60"},  # 保留时间 60 秒
            timeout=300,
        )
        if response.status_code == 200:
            data = response.json()
            download_url = data.get("download_url")
            if download_url:
                return download_url
            else:
                print(f"Failed to get download URL for {filename}")
                return None
        else:
            print(f"转换失败 {filename}: {response.text}")
            return None


def download_file(download_url, output_path):
    """下载转换后的文件"""
    response = requests.get(f"{API_DOWNLOAD_URL}{download_url.split('/')[-1]}")
    if response.status_code == 200:
        with open(output_path, "wb") as file:
            file.write(response.content)
        print(f"Downloaded: {output_path}")
    else:
        print(f"链接下载失败: {download_url}")


def main():
    # 遍历当前目录及其子目录，寻找符合条件的文件
    files_to_convert = []
    for root, _, files in os.walk(current_dir):
        for file in files:
            if os.path.splitext(file)[1].lower() in supported_extensions:
                files_to_convert.append(os.path.join(root, file))

    if not files_to_convert:
        print("未发现需要转换的文件.")
        return

    print(f"找到 {len(files_to_convert)} 个需要转换的文件.")

    start_time = time.time()  # 记录总开始时间
    successful_conversions = 0

    # 批量转换和下载
    for file_path in files_to_convert:
        file_start_time = time.time()  # 单个文件开始时间

        download_url = convert_file(file_path)
        if download_url:
            # 生成下载路径
            relative_path = os.path.relpath(file_path, current_dir)  # 获取相对路径
            converted_filename = relative_path.rsplit(".", 1)[0] + ".docx"
            output_path = os.path.join(output_dir, converted_filename)

            # 创建子目录结构
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # 等待文件在服务端生成后下载
            time.sleep(2)  # 等待 2 秒以确保文件已准备好
            download_file(download_url, output_path)

            # 统计成功转换文件数
            successful_conversions += 1

        file_elapsed_time = time.time() - file_start_time
        # print(f"Time taken for {os.path.basename(file_path)}: {file_elapsed_time:.2f} 秒")

    total_elapsed_time = time.time() - start_time  # 总耗时
    average_time_per_file = (
        total_elapsed_time / successful_conversions if successful_conversions > 0 else 0
    )

    print("\全部转换完毕:")
    print(f"提交文件总数: {len(files_to_convert)}")
    print(f"成功转换文件数: {successful_conversions}")
    print(f"总耗时: {total_elapsed_time:.2f} 秒", end="，")
    print(f"平均耗时(秒/文件): {average_time_per_file:.2f} 秒")


if __name__ == "__main__":
    main()
    main()
