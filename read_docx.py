# -*- coding: utf-8 -*-
import zipfile
import xml.etree.ElementTree as ET

docx_path = r'C:/Users/Administrator/Documents/WeChat Files/wxid_ucag2pjrmhm822/FileStorage/File/2026-04/修改意见.docx'

ns = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
}

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

with zipfile.ZipFile(docx_path, 'r') as z:
    names = z.namelist()
    print("所有文件:", names)

    # 读取正文
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

with open('output/word_comments.txt', 'w', encoding='utf-8') as f:
    f.write(f"修改意见.docx 正文共 {len(paragraphs)} 段\n\n")
    for i, p in enumerate(paragraphs, 1):
        f.write(f"{i}. {p}\n\n")

print(f"共 {len(paragraphs)} 段，写入 output/word_comments.txt")
