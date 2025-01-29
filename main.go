package main

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// ConvertRequest 结构体：定义请求体
type ConvertRequest struct {
	FileBytes  string `json:"fileBytes"`
	TargetType string `json:"targetType"`
	SourceType string `json:"sourceType"`
}

var (
	srvAddr             string
	supportedExtensions []string
	targetFmt           string
	concurrency         int
	outputDir           string
)

// 目标格式映射表
var targetTypeMapping = map[string]string{
	"ppt": "pptx", "dps": "pptx",
	"doc": "docx", "wps": "docx",
	"xls": "xlsx", "et": "xlsx",
}

// PDF 目标格式支持的文件类型
var pdfCompatibleFormats = []string{"doc", "docx", "wps", "et", "xls", "xlsx", "txt", "csv", "tsv", "dps", "ppt", "pptx"}

func init() {
	flag.StringVar(&srvAddr, "s", "http://192.168.2.128:8500", "服务端地址 (默认: http://192.168.2.128:8500)")
	fileFormats := flag.String("f", "doc,ppt,xls,wps,dps,et", "查找的文件格式 (多个用 , 分隔，默认: ppt,doc,xls,wps,dps,et)")
	flag.IntVar(&concurrency, "c", 5, "并发转换数量 (默认: 5)")
	flag.StringVar(&targetFmt, "t", "", "目标转换格式 (默认: 根据文件类型自动推断)")
	flag.StringVar(&outputDir, "o", "", "转换后文件的保存目录 (默认: 原目录，并将原文件移动到 ./源文件/ 目录)")

	flag.Parse()

	// 如果 -t 指定为 pdf，则查找支持转换为 PDF 的所有格式
	if targetFmt == "pdf" {
		supportedExtensions = pdfCompatibleFormats
	} else {
		supportedExtensions = strings.Split(*fileFormats, ",")
	}

	// 统一格式，确保前面带 "."
	for i := range supportedExtensions {
		supportedExtensions[i] = "." + strings.ToLower(strings.TrimSpace(supportedExtensions[i]))
	}
}

// 推断目标格式
func getTargetType(sourceExt string) string {
	if targetFmt != "" {
		return targetFmt
	}
	if val, ok := targetTypeMapping[sourceExt]; ok {
		return val
	}
	return "pdf" // 默认格式
}

// moveToBackupDir 移动原文件到 ./源文件/ 目录
func moveToBackupDir(filePath string) error {
	backupDir := "./源文件/"
	relPath, _ := filepath.Rel(".", filePath)
	newPath := filepath.Join(backupDir, relPath)

	// 创建目标目录
	if err := os.MkdirAll(filepath.Dir(newPath), os.ModePerm); err != nil {
		return fmt.Errorf("创建备份目录失败: %v", err)
	}

	// 移动文件
	err := os.Rename(filePath, newPath)
	if err != nil {
		return fmt.Errorf("移动文件失败: %v", err)
	}

	fmt.Printf("原文件已移动到: %s\n", newPath)
	return nil
}

func PathExists(path string) (bool, error) {
	_, err := os.Stat(path)
	if err == nil {
		return true, nil
	}
	if os.IsNotExist(err) {
		return false, nil
	}
	return false, err
}

// convertFile 进行 Base64 转换并调用 API
func convertFile(index int, filePath string, wg *sync.WaitGroup) {
	defer wg.Done()

	fmt.Printf("[任务 %d] 正在转换: %s\n", index, filePath)

	// 读取文件内容
	fileBytes, err := os.ReadFile(filePath)
	if err != nil {
		fmt.Printf("[任务 %d] 读取文件失败: %v\n", index, err)
		return
	}

	// Base64 编码
	encoded := base64.StdEncoding.EncodeToString(fileBytes)
	sourceExt := strings.TrimPrefix(filepath.Ext(filePath), ".") // 源文件类型
	targetType := getTargetType(sourceExt)

	// 构造 JSON 请求
	reqData := ConvertRequest{
		FileBytes:  encoded,
		TargetType: targetType,
		SourceType: sourceExt,
	}
	jsonData, _ := json.Marshal(reqData)

	// 发送 POST 请求
	client := &http.Client{Timeout: 30 * time.Second}
	req, err := http.NewRequest("POST", srvAddr+"/convert", bytes.NewBuffer(jsonData))
	if err != nil {
		fmt.Printf("[任务 %d] 创建请求失败: %v\n", index, err)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("[任务 %d] 发送请求失败: %v\n", index, err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		fmt.Printf("[任务 %d] 转换失败，HTTP状态码: %d\n", index, resp.StatusCode)
		return
	}

	// 读取转换后的文件
	convertedBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Printf("[任务 %d] 读取响应数据失败: %v\n", index, err)
		return
	}

	// 计算输出路径
	var outputFile string
	if outputDir == "" {
		// 保存在原目录
		outputFile = strings.TrimSuffix(filePath, filepath.Ext(filePath)) + "." + targetType

		// fmt.Printf("[任务 %d] outputFile:\t%s\n", index, outputFile)

	} else {
		// 按照原目录结构存放到 `outputDir`
		relPath, _ := filepath.Rel(".", filePath)
		outputFile = filepath.Join(outputDir, strings.TrimSuffix(relPath, filepath.Ext(filePath))+"."+targetType)
		// fmt.Printf("[任务 %d] outputFile:\t%s\n", index, outputFile)

		// 创建对应的目录结构
		if err := os.MkdirAll(filepath.Dir(outputFile), os.ModePerm); err != nil {
			fmt.Printf("[任务 %d] 创建目录失败: %v\n", index, err)
			return
		}
	}
	// 生成唯一文件名，防止覆盖
	outputFile = getUniqueFileName(outputFile, filepath.Base(filePath), targetType)
	// 保存转换后的文件
	err = os.WriteFile(outputFile, convertedBytes, 0644)
	if err != nil {
		fmt.Printf("[任务 %d] 保存文件失败: %v\n", index, err)
		return
	}

	// 如果 `-o` 未指定，则移动原文件到 ./源文件/
	if outputDir == "" {
		moveToBackupDir(filePath)
	}

	fmt.Printf("[任务 %d] 转换完成: %s\n", index, outputFile)
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

// 获取目标文件名，避免覆盖
func getUniqueFileName(outputFile string, originalFileName string, targetType string) string {
	// fmt.Println(targetType)
	exists, _ := PathExists(outputFile)
	if !exists {
		fmt.Println(outputFile, "不存在同名文件")
		return outputFile
	}
	// fmt.Println("存在同名文件")
	dir := filepath.Dir(outputFile)
	base := filepath.Base(outputFile)
	ext := filepath.Ext(outputFile)
	name := strings.TrimSuffix(base, ext)

	// 直接加上 `_(原文件名)`
	uniqueName := fmt.Sprintf("%s_(%s)%s", name, originalFileName, ext)
	uniquePath := filepath.Join(dir, uniqueName)
	fmt.Println(uniquePath)
	return uniquePath
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

	// 查找所有符合条件的文件
	files, err := findFiles(".")
	if err != nil {
		fmt.Printf("查找文件失败: %v\n", err)
		return
	}

	if len(files) == 0 {
		fmt.Printf("当前目录及其子目录下未找到需要转换的 %s 文件.\n", strings.Join(supportedExtensions, ","))
		return
	}

	fmt.Printf("共找到 %d 个需要转换的文件 (%s).\n", len(files), strings.Join(supportedExtensions, ","))

	// 使用 goroutine 进行并发转换
	var wg sync.WaitGroup
	sem := make(chan struct{}, concurrency) // 控制并发数

	for i, filePath := range files {
		wg.Add(1)
		sem <- struct{}{}
		go func(idx int, f string) {
			defer func() { <-sem }()
			convertFile(idx, f, &wg)
		}(i, filePath)
	}

	wg.Wait()
	fmt.Printf("\n转换完成，总耗时: %.2f 秒\n", time.Since(startTime).Seconds())
}
