package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

var (
	srvAddr             string
	supportedExtensions []string
	targetFmt           string
	tempDir             = "converted_files"
)

// FileResponse 定义转换 API 的响应结构
type FileResponse struct {
	Message       string `json:"message"`
	DownloadURL   string `json:"download_url"`
	RetentionTime int    `json:"retention_time"`
}

func init() {
	// 设置命令行参数
	flag.StringVar(&srvAddr, "s", "http://12.15.9.250:8500", "服务端地址 (默认: http://12.15.9.250:8500)")
	fileFormats := flag.String("f", "doc,wps", "查找的文件格式 (多个用 , 分隔，默认: doc,wps)")
	flag.StringVar(&targetFmt, "t", "docx", "目标文件格式 (默认: docx)")

	// 解析命令行参数
	flag.Parse()

	// 解析支持的文件格式
	supportedExtensions = strings.Split(*fileFormats, ",")
	for i := range supportedExtensions {
		supportedExtensions[i] = "." + strings.ToLower(strings.TrimSpace(supportedExtensions[i]))
	}
}

// convertFile 调用 API 上传并转换文件
func convertFile(filePath string) (string, error) {
	fmt.Printf("正在转换: %s\t", filePath)

	// 打开文件
	file, err := os.Open(filePath)
	if err != nil {
		return "", fmt.Errorf("打开文件失败: %v", err)
	}
	defer file.Close()

	// 创建 multipart 表单
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	part, err := writer.CreateFormFile("file", filepath.Base(filePath))
	if err != nil {
		return "", fmt.Errorf("创建表单文件失败: %v", err)
	}
	if _, err = io.Copy(part, file); err != nil {
		return "", fmt.Errorf("复制文件内容失败: %v", err)
	}

	// 添加其他表单字段
	_ = writer.WriteField("target_format", targetFmt)
	_ = writer.WriteField("retention_time", "60")
	writer.Close()

	// 构造 API URL
	apiConvertURL := fmt.Sprintf("%s/convert", srvAddr)

	// 发送 POST 请求
	req, err := http.NewRequest("POST", apiConvertURL, body)
	if err != nil {
		return "", fmt.Errorf("创建请求失败: %v", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	client := &http.Client{Timeout: 300 * time.Second} // 设置超时时间
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("发送请求失败: %v", err)
	}
	defer resp.Body.Close()

	// 处理响应
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("转换失败: %s", resp.Status)
	}

	var fileResponse FileResponse
	if err = json.NewDecoder(resp.Body).Decode(&fileResponse); err != nil {
		return "", fmt.Errorf("解析响应失败: %v", err)
	}

	if fileResponse.DownloadURL == "" {
		return "", fmt.Errorf("响应中未包含下载链接")
	}
	return fileResponse.DownloadURL, nil
}

// downloadFile 下载转换后的文件
func downloadFile(downloadURL, outputPath string) error {
	apiDownloadURL := fmt.Sprintf("%s/download/%s", srvAddr, filepath.Base(downloadURL))

	resp, err := http.Get(apiDownloadURL)
	if err != nil {
		return fmt.Errorf("发送下载请求失败: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("下载失败: %s", resp.Status)
	}

	outFile, err := os.Create(outputPath)
	if err != nil {
		return fmt.Errorf("创建文件失败: %v", err)
	}
	defer outFile.Close()

	if _, err := io.Copy(outFile, resp.Body); err != nil {
		return fmt.Errorf("保存文件失败: %v", err)
	}
	return nil
}

// findFiles 递归查找符合扩展名的文件
func findFiles(root string) ([]string, error) {
	var files []string
	err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() && isSupportedExtension(filepath.Ext(path)) {
			files = append(files, path)
		}
		return nil
	})
	return files, err
}

// isSupportedExtension 检查文件扩展名是否受支持
func isSupportedExtension(ext string) bool {
	ext = strings.ToLower(ext)
	for _, supported := range supportedExtensions {
		if ext == supported {
			return true
		}
	}
	return false
}

func main() {
	startTime := time.Now()

	// 创建输出目录
	if _, err := os.Stat(tempDir); os.IsNotExist(err) {
		if err := os.MkdirAll(tempDir, os.ModePerm); err != nil {
			fmt.Printf("创建输出目录失败: %v\n", err)
			return
		}
	}

	// 查找所有符合条件的文件
	files, err := findFiles(".")
	if err != nil {
		fmt.Printf("查找文件失败: %v\n", err)
		return
	}

	if len(files) == 0 {
		fmt.Printf("当前目录及其子目录下未找到需要转换的%s文件.\n", strings.Join(supportedExtensions, ","))
		return
	}

	fmt.Printf("共找到 %d 个需要转换的文件 (%s).\n", len(files), strings.Join(supportedExtensions, ","))

	successfulConversions := 0

	// 转换和下载文件
	for _, filePath := range files {
		fileStartTime := time.Now()

		// 转换文件
		downloadURL, err := convertFile(filePath)
		if err != nil {
			fmt.Printf("转换失败 %s: %v\n", filePath, err)
			continue
		}

		// 生成输出路径
		relativePath, _ := filepath.Rel(".", filePath)
		convertedFilename := strings.TrimSuffix(relativePath, filepath.Ext(relativePath)) + "." + targetFmt
		outputPath := filepath.Join(tempDir, convertedFilename)

		// 创建子目录
		if err := os.MkdirAll(filepath.Dir(outputPath), os.ModePerm); err != nil {
			fmt.Printf("为文件 %s 创建输出目录失败: %v\n", filePath, err)
			continue
		}

		// 下载文件
		if err := downloadFile(downloadURL, outputPath); err != nil {
			fmt.Printf("下载文件失败 %s: %v\n", filePath, err)
			continue
		}

		successfulConversions++
		fmt.Printf("耗时: %.2f 秒\n", time.Since(fileStartTime).Seconds())
	}

	// 打印汇总信息
	totalTime := time.Since(startTime).Seconds()
	avgTime := totalTime / float64(successfulConversions)
	fmt.Printf("\n转换完成:\n")
	fmt.Printf("提交文件总数: %d\n", len(files))
	fmt.Printf("成功转换文件数: %d\n", successfulConversions)
	fmt.Printf("总耗时: %.2f 秒\n", totalTime)
	fmt.Printf("平均耗时(秒/文件): %.2f 秒\n", avgTime)
}
