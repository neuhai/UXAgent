#!/usr/bin/env python3
"""
格式化 API trace 檔案的工具
將 run 目錄中的 API trace JSON 檔案轉換成更易讀的 Markdown 或 HTML 格式
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import argparse


def format_content_for_markdown(content: str, max_width: int = 100) -> str:
    """將長文本格式化為更易讀的形式"""
    # 如果是 JSON，嘗試格式化
    try:
        data = json.loads(content)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except:
        pass

    # 否則按寬度換行
    lines = content.split('\n')
    formatted_lines = []
    for line in lines:
        if len(line) > max_width:
            # 簡單的換行處理
            words = line.split(' ')
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 > max_width:
                    if current_line:
                        formatted_lines.append(current_line)
                    current_line = word
                else:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
            if current_line:
                formatted_lines.append(current_line)
        else:
            formatted_lines.append(line)

    return '\n'.join(formatted_lines)


def create_markdown_output(api_trace_data: Dict[str, Any], filename: str) -> str:
    """將 API trace 轉換為 Markdown 格式"""
    md = []
    md.append(f"# {filename}\n")

    # 基本資訊
    md.append(f"**方法**: {api_trace_data.get('method_name', 'N/A')}")
    md.append(f"**執行時間**: {api_trace_data.get('time', 'N/A'):.2f}s\n")

    # Request
    md.append("## Request\n")
    requests = api_trace_data.get('request', [])
    if requests and len(requests) > 0:
        for msg in requests[0]:  # 取第一個 request group
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')

            if role == 'system':
                md.append(f"### System Prompt\n")
                # 系統提示通常很長，簡化顯示
                lines = content.split('\n')
                if len(lines) > 20:
                    md.append(f"```\n{chr(10).join(lines[:10])}\n\n... (省略 {len(lines)-20} 行) ...\n\n{chr(10).join(lines[-10:])}\n```\n")
                else:
                    md.append(f"```\n{content}\n```\n")
            else:
                md.append(f"### User Input\n")
                # 嘗試格式化內容
                formatted = format_content_for_markdown(content)
                if len(formatted) > 2000:
                    # 如果太長，只顯示前後部分
                    md.append(f"```\n{formatted[:1000]}\n\n... (省略中間內容) ...\n\n{formatted[-1000:]}\n```\n")
                else:
                    md.append(f"```\n{formatted}\n```\n")

    # Response
    md.append("## Response\n")
    responses = api_trace_data.get('response', [])
    if responses:
        response_text = responses[0] if isinstance(responses, list) else str(responses)
        formatted_response = format_content_for_markdown(response_text)

        if len(formatted_response) > 2000:
            md.append(f"```\n{formatted_response[:1500]}\n\n... (省略中間內容) ...\n\n{formatted_response[-500:]}\n```\n")
        else:
            md.append(f"```\n{formatted_response}\n```\n")

    return '\n'.join(md)


def format_api_trace_files(run_path: str, output_format: str = 'markdown', output_dir: Optional[str] = None):
    """
    格式化一個 run 目錄下的所有 API trace 檔案

    Args:
        run_path: runs 目錄下的某個 run 的路徑
        output_format: 輸出格式 ('markdown' 或 'html')
        output_dir: 輸出目錄，如果為 None 則在 run 目錄中建立
    """
    run_path = Path(run_path)
    api_trace_dir = run_path / "api_trace"

    if not api_trace_dir.exists():
        print(f"錯誤: {api_trace_dir} 不存在")
        return

    if output_dir is None:
        output_dir = run_path / "api_trace_formatted"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 取得所有 api_trace_{number}.json 檔案
    api_trace_files = sorted(api_trace_dir.glob("api_trace_*.json"), key=lambda x: int(x.stem.split('_')[2]))

    print(f"發現 {len(api_trace_files)} 個 API trace 檔案\n")
    print(f"輸出到: {output_dir}\n")

    for api_file in api_trace_files:
        try:
            with open(api_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 建立輸出檔名
            base_name = api_file.stem  # api_trace_1
            method_name = data.get('method_name', 'unknown')
            output_filename = f"{base_name}_{method_name}.md"
            output_path = output_dir / output_filename

            # 生成 Markdown 內容
            content = create_markdown_output(data, f"{base_name} ({method_name})")

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✓ {output_filename} ({data.get('time', 0):.2f}s)")

        except Exception as e:
            print(f"✗ {api_file.name} - 錯誤: {e}")

    print(f"\n完成！所有檔案已輸出到 {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='格式化 UXAgent API trace 檔案',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python3 format_api_trace.py /Users/akiraeason/Desktop/UXAgent/runs/2025-11-28_08-31-02_a1c0
  python3 format_api_trace.py /Users/akiraeason/Desktop/UXAgent/runs/2025-11-28_08-31-02_a1c0 -o ./output
        """
    )

    parser.add_argument('run_path', help='run 目錄的路徑')
    parser.add_argument('-o', '--output', help='輸出目錄 (預設: run_path/api_trace_formatted)')
    parser.add_argument('-f', '--format', choices=['markdown', 'html'], default='markdown', help='輸出格式')

    args = parser.parse_args()

    format_api_trace_files(args.run_path, args.format, args.output)


if __name__ == '__main__':
    main()
