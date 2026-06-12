import sqlite3, json, csv, os, sys, re, glob
from datetime import datetime
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

keyword = '何超敏'
micro_db = 'output/decrypted_db/MicroMsg.db'
msg_db_dir = 'output/decrypted_db/Multi/'
out_dir = 'output'

# --- Step 1: 搜索目标成员 ---
print(f'正在搜索联系人: {keyword}')
conn_micro = sqlite3.connect(micro_db)
cur_micro = conn_micro.cursor()

cur_micro.execute("""
    SELECT UserName, NickName, Remark FROM Contact
    WHERE NickName LIKE ? OR Remark LIKE ?
""", (f'%{keyword}%', f'%{keyword}%'))
targets = cur_micro.fetchall()

print(f'找到 {len(targets)} 个匹配联系人:')
for wxid, nick, remark in targets:
    print(f'  {wxid} | {nick} | {remark}')

if not targets:
    print(f'未找到匹配的联系人: {keyword}')
    conn_micro.close()
    sys.exit(0)

target_wxids = [t[0] for t in targets]

# --- Step 2: 找出其所在群聊 ---
groups_for_member = {}
for wxid in target_wxids:
    cur_micro.execute("""
        SELECT ChatRoomName FROM ChatRoom WHERE UserNameList LIKE ?
    """, (f'%{wxid}%',))
    for (room_id,) in cur_micro.fetchall():
        if room_id not in groups_for_member:
            cur_micro.execute('SELECT strNickName FROM Session WHERE strUsrName=?', (room_id,))
            row = cur_micro.fetchone()
            groups_for_member[room_id] = row[0] if row and row[0] else room_id

print(f'\n该成员所在群聊: {len(groups_for_member)} 个')
for gid, gname in groups_for_member.items():
    print(f'  {gname} ({gid})')

# --- Step 3: 解析 BytesExtra ---
def parse_bytes_extra(data):
    if not data:
        return None
    try:
        i = 0
        while i < len(data):
            if data[i] == 0x1a:
                i += 1
                if i >= len(data): break
                length = data[i]; i += 1
                sub = data[i:i+length]
                j = 0
                while j < len(sub):
                    if sub[j]==0x08 and j+1<len(sub) and sub[j+1]==0x01 and j+2<len(sub) and sub[j+2]==0x12:
                        j += 3
                        wxid_len = sub[j]; j += 1
                        return sub[j:j+wxid_len].decode('utf-8', errors='ignore')
                    j += 1
                i += length
            else:
                i += 1
    except:
        pass
    return None

# --- Step 4: 遍历所有 MSG*.db 文件提取消息 ---
msg_db_files = glob.glob(os.path.join(msg_db_dir, 'MSG*.db'))
print(f'\n找到 {len(msg_db_files)} 个消息数据库文件:')
for db_file in msg_db_files:
    print(f'  {os.path.basename(db_file)}')

type_text_map = {3:'[图片]',34:'[语音]',43:'[视频]',47:'[表情包]',49:'[链接/文件]',10000:'[系统消息]'}
all_messages = []

for msg_db_file in msg_db_files:
    db_name = os.path.basename(msg_db_file)
    print(f'\n正在查询 {db_name}...')

    conn_msg = sqlite3.connect(msg_db_file)
    cur_msg = conn_msg.cursor()

    for group_id, group_name in groups_for_member.items():
        cur_msg.execute("""
            SELECT Type, IsSender, CreateTime, StrContent, BytesExtra
            FROM MSG WHERE StrTalker=? ORDER BY CreateTime DESC
        """, (group_id,))

        for msg_type, is_sender, ts, content, bytes_extra in cur_msg.fetchall():
            sender_wxid = parse_bytes_extra(bytes_extra) if not is_sender else ''
            if sender_wxid not in target_wxids:
                continue

            ts_str   = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else '未知'
            date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d') if ts else '未知'
            type_map = {1:'文本',3:'图片',34:'语音',43:'视频',47:'表情包',10000:'系统消息',49:'链接/文件'}
            type_name = type_map.get(msg_type, f'类型{msg_type}')
            text = type_text_map.get(msg_type, content or '') if msg_type != 1 else (content or '')

            all_messages.append((ts_str, date_str, group_id, group_name, sender_wxid, type_name, text, ts))

    conn_msg.close()

# 按时间正序排列
all_messages.sort(key=lambda x: x[7])

# --- Step 5: 统计分析 ---
total = len(all_messages)
group_cnt = Counter(m[3] for m in all_messages)
date_cnt  = Counter(m[1] for m in all_messages)
type_cnt  = Counter(m[5] for m in all_messages)

print(f'\n=== {keyword} 消息统计 ===')
print(f'总发言数: {total}')
print('\n【按群分布】')
for g, c in group_cnt.most_common():
    print(f'  {g}: {c}条')
print('\n【按日期分布】')
for d in sorted(date_cnt): print(f'  {d}: {date_cnt[d]}条')
print('\n【消息类型】')
for t, c in type_cnt.most_common(): print(f'  {t}: {c}条')

# --- Step 6: 导出结果 ---
safe_name = keyword.replace(' ', '_')

csv_path = os.path.join(out_dir, f'trace_{safe_name}.csv')
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['时间', '群名', '发送者wxid', '消息类型', '内容'])
    for m in all_messages:
        w.writerow([m[0], m[3], m[4], m[5], m[6]])

txt_path = os.path.join(out_dir, f'trace_{safe_name}.txt')
with open(txt_path, 'w', encoding='utf-8') as f:
    f.write(f'=== {keyword} 跨群发言记录 ===\n总消息: {total}\n\n')
    for group_id, group_name in groups_for_member.items():
        msgs = [m for m in all_messages if m[2] == group_id]
        if not msgs: continue
        f.write(f'\n{"="*50}\n群: {group_name}\n消息数: {len(msgs)}\n{"="*50}\n\n')
        for m in msgs:
            f.write(f'[{m[0]}] ({m[5]})\n{m[6]}\n\n')

stats_path = os.path.join(out_dir, f'trace_{safe_name}_stats.txt')
with open(stats_path, 'w', encoding='utf-8') as f:
    f.write(f'=== {keyword} 消息统计报告 ===\n\n总发言数: {total}\n\n')
    f.write('【按群分布】\n')
    for g, c in group_cnt.most_common(): f.write(f'  {g}: {c}条\n')
    f.write('\n【按日期分布】\n')
    for d in sorted(date_cnt): f.write(f'  {d}: {date_cnt[d]}条\n')
    f.write('\n【消息类型分布】\n')
    for t, c in type_cnt.most_common(): f.write(f'  {t}: {c}条\n')

print(f'\n已导出:\n  {csv_path}\n  {txt_path}\n  {stats_path}')

# --- Step 7: 内容分析 ---
text_messages = [m for m in all_messages if m[5] == '文本']
text_contents = [m[6] for m in text_messages]

print(f'\n=== 内容分析 ===')
print(f'文本消息数: {len(text_messages)}')

# 最近消息（按时间倒序取最新30条文本）
recent_texts = text_messages[-30:]
print(f'\n最近 {len(recent_texts)} 条文本消息:')
for m in recent_texts:
    print(f'  [{m[0]}] [{m[3]}] {m[6][:100]}')

# 关键词提取
all_text = ' '.join(text_contents)
# 简单分词：按非中文字符分割
words = re.findall(r'[\u4e00-\u9fa5]{2,}', all_text)
word_counter = Counter(words)
common_words = word_counter.most_common(30)
print('\n【高频关键词 TOP 30】')
for w, c in common_words:
    print(f'  {w}: {c}次')

# 项目需求关键词
requirement_keywords = ['需求', '功能', '开发', '项目', '系统', '网站', '小程序', '后台', '前端', '数据库',
                       '接口', '设计', '页面', '模块', '用户', '管理', '查询', '添加', '修改', '删除',
                       '报价', '价格', '费用', '预算', '周期', '时间', '交付', '上线', '测试', '部署']

requirement_messages = []
for m in text_messages:
    text = m[6]
    if any(kw in text for kw in requirement_keywords):
        requirement_messages.append(m)

print(f'\n【包含需求关键词的消息: {len(requirement_messages)} 条】')
for m in requirement_messages[:20]:  # 显示前20条
    print(f'  [{m[0]}] {m[6][:150]}')

# 导出需求分析报告
report_path = os.path.join(out_dir, f'trace_{safe_name}_requirements.txt')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(f'=== {keyword} 项目需求分析报告 ===\n\n')
    f.write(f'一、基础统计\n')
    f.write(f'  总发言数: {total} 条\n')
    f.write(f'  文本消息: {len(text_messages)} 条\n')
    f.write(f'  非文本消息: {total - len(text_messages)} 条\n')
    if all_messages:
        f.write(f'  时间跨度: {all_messages[0][0]} ~ {all_messages[-1][0]}\n')
    f.write(f'\n二、群聊分布\n')
    for g, c in group_cnt.most_common():
        f.write(f'  {g}: {c}条\n')
    f.write(f'\n三、日期分布\n')
    for d in sorted(date_cnt): f.write(f'  {d}: {date_cnt[d]}条\n')
    f.write(f'\n四、消息类型分布\n')
    for t, c in type_cnt.most_common(): f.write(f'  {t}: {c}条\n')
    f.write(f'\n五、高频关键词 TOP 30\n')
    for w, c in common_words:
        f.write(f'  {w}: {c}次\n')
    f.write(f'\n六、包含需求关键词的消息 ({len(requirement_messages)} 条)\n')
    for m in requirement_messages:
        f.write(f'\n[{m[0]}] [{m[3]}]\n{m[6]}\n')
    f.write(f'\n七、完整聊天记录（按时间顺序）\n')
    for m in text_messages:
        f.write(f'\n[{m[0]}] [{m[3]}]\n{m[6]}\n')

print(f'\n需求分析报告已导出: {report_path}')

conn_micro.close()
