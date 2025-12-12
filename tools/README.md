# UXAgent API Trace 分析工具

這個目錄包含了幾個工具，用來幫助你閱讀和分析 UXAgent 執行過程中儲存的 LLM 輸入輸出日誌（API trace）。

## 工具概述

### 1. `format_api_trace.py` - 格式化 API Trace 檔案

將原始的 JSON API trace 檔案轉換成易於閱讀的 Markdown 格式。

**使用方式:**
```bash
python3 tools/format_api_trace.py <run_path>
```

**例子:**
```bash
python3 tools/format_api_trace.py runs/2025-11-28_08-31-02_a1c0
```

**輸出:**
- 在 `runs/<run_name>/api_trace_formatted/` 目錄下生成 Markdown 檔案
- 每個 API 呼叫都會有一個檔案，例如 `api_trace_1_perceive.md`

**包含內容:**
- 方法名稱（perceive、plan、act）
- 執行時間
- 格式化的 System Prompt
- 用戶輸入的 HTML 頁面
- 模型的回應

### 2. `generate_api_summary.py` - 生成執行摘要

生成整個執行過程的摘要報告，包括時間線、統計資訊和詳細的執行步驟。

**使用方式:**
```bash
python3 tools/generate_api_summary.py <run_path>
```

**例子:**
```bash
python3 tools/generate_api_summary.py runs/2025-11-28_08-31-02_a1c0
```

**輸出:**
- 在 `runs/<run_name>/api_summary.md` 生成摘要檔案

**包含內容:**
1. **執行時間線表格**: 顯示每個 API 呼叫的編號、方法、執行時間和預覽
2. **方法統計**: 各個方法（perceive、plan、act）的呼叫次數和時間統計
3. **詳細執行過程**: 按照循環組織的詳細日誌，包括每個 perceive-plan-act 循環

## API Trace 檔案結構

原始的 API trace 檔案存儲在：
```
runs/<run_name>/api_trace/api_trace_<number>.json
```

每個檔案包含：
```json
{
  "request": [
    [
      {"role": "system", "content": "..."},
      {"role": "user", "content": "..."}
    ]
  ],
  "response": ["LLM output..."],
  "method_name": "perceive|plan|act",
  "retrieve_result": [],
  "time": 51.93
}
```

## Agent 的三個核心方法

### Perceive（觀察）
Agent 觀察當前網頁，理解頁面內容。
- **輸入**: 頁面的 HTML 內容
- **輸出**: 自然語言描述的頁面觀察

### Plan（計畫）
Agent 根據觀察和目標，制定下一步的計畫。
- **輸入**: 觀察、目標、記憶
- **輸出**: 計畫和理由

### Act（執行）
Agent 執行具體的動作（點擊、輸入文字等）。
- **輸入**: 計畫
- **輸出**: 具體的動作列表

## 範例

### 查看格式化的單個 API trace
```bash
# 先生成格式化的檔案
python3 tools/format_api_trace.py runs/2025-11-28_08-31-02_a1c0

# 然後查看特定的檔案
cat runs/2025-11-28_08-31-02_a1c0/api_trace_formatted/api_trace_1_perceive.md
```

### 查看執行摘要
```bash
# 生成摘要
python3 tools/generate_api_summary.py runs/2025-11-28_08-31-02_a1c0

# 查看摘要
cat runs/2025-11-28_08-31-02_a1c0/api_summary.md
```

## 性能分析

使用這些工具可以快速了解 Agent 的性能：

- **Perceive 時間**: 通常最長（30-100s），因為需要分析複雜的 HTML
- **Plan 時間**: 中等（10-30s），取決於計劃的複雜性
- **Act 時間**: 通常較短（1-15s）

如果某個方法花費的時間異常長，可能表示：
- 頁面內容過於複雜
- 模型需要更多思考時間
- 網路延遲

## 故障排除

### 檔案讀取錯誤
如果看到 "無法讀取" 的錯誤，檢查：
1. Run 目錄的路徑是否正確
2. API trace 檔案是否完整未損壞

### 編碼問題
如果看到亂碼，確保：
1. 使用 Python 3.8+
2. 終端支持 UTF-8 編碼

## 進階用法

### 只查看特定方法的 API traces
```bash
# 只看 perceive 方法
ls runs/2025-11-28_08-31-02_a1c0/api_trace_formatted/*_perceive.md

# 只看 act 方法
ls runs/2025-11-28_08-31-02_a1c0/api_trace_formatted/*_act.md
```

### 搜索特定內容
```bash
# 搜索提到 "jacket" 的所有日誌
grep -r "jacket" runs/2025-11-28_08-31-02_a1c0/api_trace_formatted/

# 搜索特定的錯誤或警告
grep -r "error\|warn" runs/2025-11-28_08-31-02_a1c0/api_trace_formatted/
```

## 貢獻

如果你對這些工具有改進建議或發現了 bug，歡迎提出！
