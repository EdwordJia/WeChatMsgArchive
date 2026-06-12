# -*- coding: utf-8 -*-
"""分析Excel文件中的问题清单并生成Markdown报告"""

import pandas as pd
import sys
import os

def analyze_excel_files():
    """分析两个Excel文件并生成报告"""

    file1 = r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\FileStorage\File\2026-05\新建 XLSX 工作表(2).xlsx'
    file2 = r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\FileStorage\File\2026-05\案件信息表-SH20251022185248288282.xlsx'

    results = {}

    # 读取文件1
    print("=== 分析文件1：文书问题清单 ===")
    try:
        xl1 = pd.ExcelFile(file1)
        print(f"工作表: {xl1.sheet_names}")
        results['file1'] = {
            'name': '新建 XLSX 工作表(2).xlsx',
            'desc': '文书问题清单',
            'sheets': {}
        }
        for sheet in xl1.sheet_names:
      df = pd.read_excel(file1, sheet_name=sheet)
          print(f"\n--- 工作表: {sheet} ---")
            print(f"行数: {len(df)}, 列数: {len(df.columns)}")
            print(f"列名: {list(df.columns)}")
            results['file1']['sheets'][sheet] = {
                'rows': len(df),
         'cols': len(df.columns),
                'columns': list(df.columns),
                'data': df
            }
         pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            pd.set_option('display.max_colwidth', 200)
            print("\n数据内容:")
            print(df.to_string())
    except Exception as e:
     print(f"读取文件1失败: {e}")
        import traceback
        traceback.print_exc()
     results['file1'] = {'error': str(e)}

    print("\n" + "="*60 + "\n")

    # 读取文件2
    print("=== 分析文件2：案件信息表 ===")
    try:
        xl2 = pd.ExcelFile(file2)
        print(f"工作表: {xl2.sheet_names}")
        results['file2'] = {
            'name': '案件信息表-SH20251022185248288282.xlsx',
            'desc': '列表字段问题',
         'sheets': {}
        }
        for sheet in xl2.sheet_names:
            df = pd.read_excel(file2, sheet_name=sheet)
            print(f"\n--- 工作表: {sheet} ---")
            print(f"行数: {len(df)}, 列数: {len(df.columns)}")
            print(f"列名: {list(df.columns)}")
            results['file2']['sheets'][sheet] = {
            'rows': len(df),
           'cols': len(df.columns),
         'columns': list(df.columns),
            'data': df
            }
            print("\n数据内容:")
            print(df.to_string())
    except Exception as e:
        print(f"读取文件2失败: {e}")
        import traceback
        traceback.print_exc()
      results['file2'] = {'error': str(e)}

    return results

if __name__ == '__main__':
    results = analyze_excel_files()
