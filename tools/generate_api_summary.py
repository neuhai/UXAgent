#!/usr/bin/env python3
"""
生成 API trace 執行過程的摘要報告
包括時間線、方法統計、執行時間分析等
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
import argparse
from collections import defaultdict


def load_api_traces(api_trace_dir: Path) -> List[tuple[int, Dict[str, Any]]]:
    """讀取所有 API trace 檔案，按編號排序"""
    traces = []
    for file in sorted(api_trace_dir.glob("api_trace_*.json"), key=lambda x: int(x.stem.split('_')[2])):
        trace_num = int(file.stem.split('_')[2])
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            traces.append((trace_num, data))
        except Exception as e:
            print(f"警告: 無法讀取 {file.name}: {e}")

    return traces


def extract_user_input_preview(request_data: list, max_chars: int = 200) -> str:
    """從 request 中提取用戶輸入的預覽"""
    if not request_data or len(request_data) < 2:
        return "N/A"

    user_msg = None
    for msg in request_data[0]:
        if msg.get('role') == 'user':
            user_msg = msg.get('content', '')
            break

    if not user_msg:
        return "N/A"

    # 移除 JSON 引號和逃脫字符
    preview = user_msg.replace('\\"', '"').replace('\\n', ' ')

    # 嘗試解析 JSON 以獲得更好的預覽
    try:
        if preview.startswith('"'):
            preview = preview[1:-1]
    except:
        pass

    # 截短預覽
    if len(preview) > max_chars:
        return preview[:max_chars] + "..."
    return preview


def extract_response_preview(response_data: list, max_chars: int = 150) -> str:
    """從 response 中提取回覆的預覽"""
    if not response_data:
        return "N/A"

    response_text = response_data[0] if isinstance(response_data, list) else str(response_data)

    # 嘗試解析 JSON
    try:
        data = json.loads(response_text)
        # 如果是 observations，取第一個觀察
        if 'observations' in data and data['observations']:
            preview = data['observations'][0]
        else:
            preview = json.dumps(data, ensure_ascii=False)[:max_chars]
    except:
        preview = response_text

    if len(preview) > max_chars:
        return preview[:max_chars] + "..."
    return preview


def generate_summary_report(run_path: str, output_file: str = None) -> str:
    """生成 API 執行摘要報告"""
    run_path = Path(run_path)
    api_trace_dir = run_path / "api_trace"

    if not api_trace_dir.exists():
        return f"錯誤: {api_trace_dir} 不存在"

    traces = load_api_traces(api_trace_dir)

    if not traces:
        return f"錯誤: 在 {api_trace_dir} 中找不到 API trace 檔案"

    # 統計資訊
    method_counts = defaultdict(int)
    method_times = defaultdict(float)
    total_time = 0.0
    method_details = defaultdict(list)

    # 構建報告
    report = []
    report.append("# UXAgent API 執行摘要\n")
    report.append(f"Run: {run_path.name}\n")
    report.append(f"API Trace 檔案數: {len(traces)}\n\n")

    # 時間線
    report.append("## 執行時間線\n")
    report.append("| # | 方法 | 時間 (s) | 預覽 |\n")
    report.append("|---|------|---------|------|\n")

    for trace_num, data in traces:
        method = data.get('method_name', 'unknown')
        time_taken = data.get('time', 0)

        # 統計
        method_counts[method] += 1
        method_times[method] += time_taken
        total_time += time_taken

        # 提取預覽
        user_preview = extract_user_input_preview(data.get('request', []), max_chars=50)
        response_preview = extract_response_preview(data.get('response', []), max_chars=50)

        # 根據方法選擇顯示的預覽
        if method == 'perceive':
            preview = f"觀察到: {response_preview[:40]}"
        elif method == 'plan':
            preview = f"計畫: {response_preview[:40]}"
        elif method == 'act':
            preview = f"行動: {response_preview[:40]}"
        else:
            preview = response_preview[:40]

        report.append(f"| {trace_num} | {method} | {time_taken:.2f} | {preview} |\n")

    # 統計摘要
    report.append("\n## 方法統計\n")
    report.append("| 方法 | 次數 | 總時間 (s) | 平均時間 (s) |\n")
    report.append("|------|------|-----------|-------------|\n")

    for method in sorted(method_counts.keys()):
        count = method_counts[method]
        total = method_times[method]
        avg = total / count if count > 0 else 0
        report.append(f"| {method} | {count} | {total:.2f} | {avg:.2f} |\n")

    report.append(f"\n**總執行時間**: {total_time:.2f}s\n")

    # 方法詳細列表
    report.append("\n## 詳細執行過程\n")

    current_cycle = 0
    perceived_step = False

    for trace_num, data in traces:
        method = data.get('method_name', 'unknown')
        time_taken = data.get('time', 0)

        # 追蹤循環 (perceive -> plan -> act)
        if method == 'perceive':
            current_cycle += 1
            perceived_step = True
            report.append(f"\n### 循環 {current_cycle}\n")

        if perceived_step:
            report.append(f"\n**{method.upper()}** (#{trace_num}, {time_taken:.2f}s)\n")

            # 根據方法提供不同的摘要
            request_data = data.get('request', [])
            response_data = data.get('response', [])

            if method == 'perceive':
                # 顯示觀察到的內容摘要
                preview = extract_response_preview(response_data, max_chars=300)
                report.append(f"觀察: {preview}\n")

            elif method == 'plan':
                # 顯示計畫內容
                preview = extract_response_preview(response_data, max_chars=300)
                report.append(f"計畫: {preview}\n")

            elif method == 'act':
                # 顯示執行的動作
                preview = extract_response_preview(response_data, max_chars=200)
                report.append(f"動作: {preview}\n")

    report_str = ''.join(report)

    # 寫入檔案
    if output_file is None:
        output_file = run_path / "api_summary.md"
    else:
        output_file = Path(output_file)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_str)

    print(f"✓ 摘要報告已生成: {output_file}")
    return report_str


def main():
    parser = argparse.ArgumentParser(
        description='生成 UXAgent API trace 執行摘要',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python3 generate_api_summary.py /Users/akiraeason/Desktop/UXAgent/runs/2025-11-28_08-31-02_a1c0
  python3 generate_api_summary.py /Users/akiraeason/Desktop/UXAgent/runs/2025-11-28_08-31-02_a1c0 -o ./summary.md
        """
    )

    parser.add_argument('run_path', help='run 目錄的路徑')
    parser.add_argument('-o', '--output', help='輸出檔案路徑')

    args = parser.parse_args()

    generate_summary_report(args.run_path, args.output)


if __name__ == '__main__':
    main()
