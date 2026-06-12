from docx import Document
import sys

sys.stdout.reconfigure(encoding='utf-8')

paths = [
 r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\FileStorage\File\2026-05\综合平台_成都词频与语义网络分析.docx',
 r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\FileStorage\File\2026-05\成都小红书_ROST分析结果(1).docx'
]

for doc_path in paths:
 print('\n' + '=' * 80)
 print('FILE: ' + doc_path.split('\\')[-1])
 print('=' * 80 + '\n')
 doc = Document(doc_path)
 for para in doc.paragraphs:
  if para.text.strip():
   print(para.text)
 print('\n--- Tables ---\n')
 for i, table in enumerate(doc.tables):
  print('Table ' + str(i+1) + ':')
  for row in table.rows:
   cells = [cell.text.strip() for cell in row.cells]
   print(' | '.join(cells))
  print()
