# TODO

## K8s 部署相关

- [ ] **PDF 下载/导出功能持久化方案**：当前 download_service 和 export_service 写入本地文件系统，K8s pod 重启后文件丢失。需要决定方案：
  - 方案 A：挂载 PersistentVolume（EBS/EFS）到 `/app/downloads` 和 `/app/exports`
  - 方案 B：改为返回文件流（不落盘），由调用方自行存储
  - 方案 C：上传到 S3，返回预签名 URL
  - 暂不影响搜索和元数据查询功能，可后续决定

## 代码质量

- [ ] **修复 pytest 配置**：pytest-asyncio 0.23+ 需要在 pyproject.toml 中添加 `asyncio_mode = "auto"`
- [ ] **统一日志**：部分 connector 使用 `print()` 而非 `logger`，需要统一
- [ ] **自定义异常层级**：替换裸 `Exception`，建立 `PaperSearchError` → `ConnectorError` / `DownloadError` 体系
