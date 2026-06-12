# -*- coding: utf-8 -*-
import zipfile
import xml.etree.ElementTree as ET

docx_path = r'C:/Users/Administrator/Documents/WeChat Files/wxid_ucag2pjrmhm822/FileStorage/File/2026-04/思想政治教育_饶超_202124320032026年4月11日格式修改.docx'

W  = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W14 = 'http://schemas.microsoft.com/office/word/2010/wordml'

with zipfile.ZipFile(docx_path, 'r') as z:
    names = z.namelist()

    results = []

    # 读取批注
    if 'word/comments.xml' in names:
        with z.open('word/comments.xml') as f:
            tree = ET.parse(f)
            root = tree.getroot()
        comments = []
        for comment in root.findall(f'{{{W}}}comment'):
            cid     = comment.get(f'{{{W}}}id', '')
            author  = comment.get(f'{{{W}}}author', '')
            date    = comment.get(f'{{{W}}}date', '')
            texts = []
            for t in comment.findall(f'.//{{{W}}}t'):
                if t.text:
                    texts.append(t.text)
            text = ''.join(texts).strip()
            comments.append((cid, author, date, text))
        results.append(('批注', comments))
    else:
        results.append(('批注', []))

    # 读取正文段落
    if 'word/document.xml' in names:
        with z.open('word/document.xml') as f:
            tree = ET.parse(f)
            root = tree.getroot()
        paragraphs = []
        for para in root.findall(f'.//{{{W}}}p'):
            texts = []
            for t in para.findall(f'.//{{{W}}}t'):
                if t.text:
                    texts.append(t.text)
            line = ''.join(texts).strip()
            if line:
                paragraphs.append(line)
        results.append(('正文', paragraphs))

with open('output/april11_comments.txt', 'w', encoding='utf-8') as f:
    for section, items in results:
        if section == '批注':
            f.write(f'=== Word批注 共{len(items)}条 ===\n\n')
            for cid, author, date, text in items:
                f.write(f'[批注#{cid}] 作者:{author}  时间:{date[:10] if date else ""}\n')
                f.write(f'{text}\n\n')
        else:
            f.write(f'\n=== 正文 共{len(items)}段 ===\n\n')
            for i, p in enumerate(items, 1):
                f.write(f'{i}. {p}\n\n')

print('完成，写入 output/april11_comments.txt')
print(f'包含文件: {names}')
