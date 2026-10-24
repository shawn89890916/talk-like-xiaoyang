"""Publish aggregate punctuation and expression frequencies; never emits source text or chat IDs."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--self', dest='self_path', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--markdown', type=Path, required=True)
args = parser.parse_args()
rows = [json.loads(line) for line in args.self_path.read_text(encoding='utf-8').splitlines()]

def credential_like(text):
    if re.search(r'\b(?:sk-|gh[pousr]_|github_pat_|AIzaSy)[A-Za-z0-9_-]{8,}', text):
        return True
    for token in re.findall(r'[^\s\u4e00-\u9fff]{12,}', text):
        if re.search(r'[A-Za-z]', token) and re.search(r'\d', token) and len(re.findall(r'[^A-Za-z0-9@./:_-]', token)) >= 2:
            return True
    return False

def exclude_reasons(text):
    reasons = []
    if not text.strip(): reasons.append('empty')
    if re.fullmatch(r'\s*(?:https?://\S+\s*)+', text): reasons.append('link_only')
    if len(text) > 400: reasons.append('long_authorship_uncertain')
    if re.search(r'```|<!DOCTYPE|<html|^\s*(?:def |class |import |function |SELECT |#include)', text, re.I | re.M): reasons.append('code_or_structured')
    if re.search(r'^\s*(?:sudo |npm (?:install|run)|pip(?:3)? install|git (?:clone|push|pull)|winget |curl |npx )', text): reasons.append('command')
    if re.search(r'复制此口令|#墨墨背单词#|访问\s+www\.|^I am .+\x27s ', text): reasons.append('shared_or_system_template')
    if re.fullmatch(r'\s*\d{4,}\s*', text): reasons.append('numeric_identifier')
    if credential_like(text): reasons.append('credential_like')
    if len(text) > 100 and (text.count('\n') >= 6 or len(re.findall(r'https?://', text)) >= 2): reasons.append('formatted_authorship_uncertain')
    return reasons

eligible = [r for r in rows if not exclude_reasons(r['text'])]
excluded = [r for r in rows if exclude_reasons(r['text'])]
texts = [r['text'] for r in eligible]
n = len(texts)
chars = sum(len(t) for t in texts)
chat_ids = {r['chat_id'] for r in eligible}

def rate_record(matched_messages, occurrences):
    return {
        'messages': matched_messages,
        'message_share': round(matched_messages / n, 6) if n else 0,
        'messages_per_1000': round(matched_messages * 1000 / n, 3) if n else 0,
        'occurrences': occurrences,
        'occurrences_per_1000_messages': round(occurrences * 1000 / n, 3) if n else 0,
        'occurrences_per_1000_characters': round(occurrences * 1000 / chars, 3) if chars else 0,
        'chats': None,
    }

punctuation = {
    'comma': ['，', ','],
    'full_stop': ['。', '.'],
    'question_mark': ['？', '?'],
    'exclamation_mark': ['！', '!'],
    'enumeration_comma': ['、'],
    'semicolon': ['；', ';'],
    'colon': ['：', ':'],
    'ellipsis_mark': ['…'],
    'dash': ['—', '–', '－'],
    'hyphen': ['-'],
    'parentheses': ['（', '）', '(', ')'],
    'quotation_marks': ['“', '”', '‘', '’', '「', '」', '『', '』', '"', "'"],
    'brackets': ['【', '】', '[', ']', '《', '》', '<', '>'],
    'slash': ['/', '／'],
}
punctuation_stats = {}
for category, glyphs in punctuation.items():
    hit = [t for t in texts if any(g in t for g in glyphs)]
    occurrences = sum(t.count(g) for t in texts for g in glyphs)
    record = rate_record(len(hit), occurrences)
    record['chats'] = len({r['chat_id'] for r in eligible if any(g in r['text'] for g in glyphs)})
    record['glyphs'] = {g: sum(t.count(g) for t in texts) for g in glyphs}
    punctuation_stats[category] = record

terminal_map = {
    'comma': set('，,'), 'full_stop': set('。.'), 'question_mark': set('？?'),
    'exclamation_mark': set('！!'), 'ellipsis_mark': set('…'),
    'semicolon': set('；;'), 'colon': set('：:'),
}
closing = set('”’」』）》】）)]}»')
terminal_counts = Counter()
for text in texts:
    ending = text.rstrip()
    while ending and ending[-1] in closing:
        ending = ending[:-1].rstrip()
    if not ending:
        category = 'empty_after_trim'
    else:
        last = ending[-1]
        category = next((name for name, glyphs in terminal_map.items() if last in glyphs), 'none_or_other')
    terminal_counts[category] += 1
terminal_stats = {
    key: {'messages': count, 'share': round(count / n, 6) if n else 0}
    for key, count in sorted(terminal_counts.items())
}

term_groups = {
    'discourse_connectors': ['然后', '就是', '主要', '其实', '因为', '所以', '但是', '不过', '先', '再', '直接', '比如', '如果'],
    'stance_and_uncertainty': ['我觉得', '我感觉', '感觉', '应该', '可能', '好像', '不一定', '我认为'],
    'particles_and_interjections': ['啊', '吧', '呢', '嘛', '呗', '呀', '哦', '噢', '嗯', '诶', '欸'],
    'colloquial_questions': ['啥', '咋', '为啥', '怎么', '为什么', '是不是', '有没有', '能不能', '可以吗'],
    'requests_and_politeness': ['麻烦', '方便', '请问', '帮我', '谢谢', '你好', '您好', '老师'],
    'short_reply_and_laughter': ['好', '好的', '行', '可以', '没事', '收到', '哈哈', '哈哈哈', '哈哈哈哈'],
    'time_and_action': ['等会', '等下', '晚点', '一下', '发一下', '我看看', '我试试'],
}
expression_stats = {}
for group, phrases in term_groups.items():
    expression_stats[group] = {}
    for phrase in phrases:
        hit_rows = [r for r in eligible if phrase in r['text']]
        occurrences = sum(r['text'].count(phrase) for r in hit_rows)
        expression_stats[group][phrase] = rate_record(len(hit_rows), occurrences)
        expression_stats[group][phrase]['chats'] = len({r['chat_id'] for r in hit_rows})

short_reply_candidates = ['好', '好的', '好滴', '好嘞', '嗯', '嗯嗯', '哦', '哦哦', '噢', '噢噢', '行', '行吧', '可以', '可以的', '可以啊', '可以呀', '对', '对的', '是的', '没有', '没事', '谢谢', '收到', '知道了', '哈哈', '哈哈哈', 'OK', 'ok', 'okk', 'okok']
exact = Counter(t.strip() for t in texts)
short_replies = {phrase: {'messages': exact[phrase], 'message_share': round(exact[phrase] / n, 6) if n else 0}
                 for phrase in short_reply_candidates if exact[phrase]}

source_hash = hashlib.sha256(args.self_path.read_bytes()).hexdigest()
result = {
    'schema_version': 1,
    'analysis_date': '2026-10-24',
    'timezone': 'Asia/Shanghai',
    'source': {
        'self_messages': len(rows), 'eligible_messages': n, 'eligible_chats': len(chat_ids),
        'eligible_characters': chars, 'excluded_messages': len(excluded),
        'self_jsonl_sha256': source_hash,
        'first_message': min(r['time'] for r in rows), 'last_message': max(r['time'] for r in rows),
    },
    'punctuation': {
        'definition': 'Occurrences count every matching glyph; message_share is the fraction of eligible messages containing at least one glyph in the category. Categories can overlap.',
        'categories': punctuation_stats,
        'terminal_style': terminal_stats,
    },
    'expression_candidates': {
        'definition': 'Predefined substring counts, not automatic proof of filler-word or catchphrase status. Phrases overlap; each message may count in multiple entries.',
        'groups': expression_stats,
        'exact_short_replies': short_replies,
    },
    'limitations': [
        'Scope is the currently readable local WeChat export, not a complete lifetime corpus.',
        'Eligible messages are heuristic candidates; sending direction does not establish original authorship.',
        'Probabilities are empirical message shares within the eligible sample, not probabilities for every context.',
        'Substrings may occur with different meanings; occurrence counts do not establish a catchphrase.',
        'Contacts, chat IDs, raw excerpts and message-level results are not published.',
    ],
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

def pct(value):
    return f"{value * 100:.2f}%"

lines = [
    '# 聊天标点与表达词频', '',
    f"分析范围：{n:,} 条候选本人文字，{len(chat_ids)} 个会话，共 {chars:,} 个字符；导出区间 {result['source']['first_message'][:10]} 至 {result['source']['last_message'][:10]}。",
    '',
    '这里的比例是“候选消息中至少出现一次的比例”；每千条频次按实际出现次数计算。词条使用子串匹配，彼此会重叠，统计结果只能描述这份可读取语料。', '',
    '![词云与常见标点](language-cloud.png)', '',
    '## 标点', '',
    '| 类型 | 含标点消息 | 消息占比 | 出现次数 | 每千条消息 |',
    '| --- | ---: | ---: | ---: | ---: |',
]
punctuation_labels = {
    'comma': '逗号', 'question_mark': '问号', 'full_stop': '句号', 'brackets': '方括号/书名号',
    'colon': '冒号', 'parentheses': '括号', 'hyphen': '连字符', 'exclamation_mark': '感叹号',
    'quotation_marks': '引号', 'slash': '斜线', 'enumeration_comma': '顿号', 'semicolon': '分号',
    'ellipsis_mark': '省略号', 'dash': '破折号/短横线',
}
for name, rec in sorted(punctuation_stats.items(), key=lambda item: (-item[1]['messages'], item[0])):
    glyphs = '、'.join(punctuation[name])
    lines.append(f"| {punctuation_labels[name]}（{glyphs}） | {rec['messages']:,} | {pct(rec['message_share'])} | {rec['occurrences']:,} | {rec['occurrences_per_1000_messages']:.1f} |")
group_labels = {
    'discourse_connectors': '承接与顺序', 'stance_and_uncertainty': '判断与不确定',
    'particles_and_interjections': '语气词与感叹词', 'colloquial_questions': '口语提问',
    'requests_and_politeness': '请求与礼貌', 'short_reply_and_laughter': '简短回应与笑声',
    'time_and_action': '时间与动作',
}
lines += ['', '## 常见词和短语候选', '', '| 分组 | 词条 | 含词条消息 | 消息占比 | 出现次数 | 会话数 |', '| --- | --- | ---: | ---: | ---: | ---: |']
ranked = []
for group, phrases in expression_stats.items():
    for phrase, rec in phrases.items():
        if rec['messages']:
            ranked.append((rec['messages'], group, phrase, rec))
for _, group, phrase, rec in sorted(ranked, reverse=True)[:40]:
    lines.append(f"| {group_labels[group]} | {phrase} | {rec['messages']:,} | {pct(rec['message_share'])} | {rec['occurrences']:,} | {rec['chats']} |")
lines += ['', '## 完全匹配的短回复', '', '这里要求整条消息（去掉首尾空白后）与词条完全相同。', '', '| 短回复 | 消息数 | 候选消息占比 |', '| --- | ---: | ---: |']
for phrase, rec in sorted(short_replies.items(), key=lambda item: (-item[1]['messages'], item[0])):
    lines.append(f"| {phrase} | {rec['messages']:,} | {pct(rec['message_share'])} |")
lines += ['', '## 消息结尾', '', '| 结尾类型 | 消息数 | 占比 |', '| --- | ---: | ---: |']
for category, rec in sorted(terminal_stats.items(), key=lambda item: (-item[1]['messages'], item[0])):
    lines.append(f"| {category} | {rec['messages']:,} | {pct(rec['share'])} |")
lines += ['', '## 怎么看这些数', '', '- 高频只说明它在当前候选语料里常见，不能单独证明它是固定口头禅。', '- “口水词”按预设词条统计，可能在不同语境里承担不同作用；例如“就”“啊”“所以”不一定是填充词。', '- 亲疏关系、单一高频会话、引用或转发会影响比例；原始统计不等于对每种场合的判断。', '- 明细 JSON 只保留聚合数，不包含联系人、会话 ID 或原句。', '']
args.markdown.parent.mkdir(parents=True, exist_ok=True)
args.markdown.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
print(json.dumps({'eligible_messages': n, 'eligible_chats': len(chat_ids), 'characters': chars, 'excluded_messages': len(excluded), 'self_jsonl_sha256': source_hash, 'top_punctuation': sorted(punctuation_stats.items(), key=lambda item: -item[1]['messages'])[:4]}, ensure_ascii=False))
