"""Compute aggregate voice statistics. Raw messages and review excerpts stay local."""
import argparse
import hashlib
import json
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--self', dest='self_path', type=Path, required=True)
parser.add_argument('--full', dest='full_path', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--review-file', type=Path, required=True)
args = parser.parse_args()
rows = [json.loads(line) for line in args.self_path.read_text(encoding='utf-8').splitlines()]
full = [json.loads(line) for line in args.full_path.read_text(encoding='utf-8').splitlines()]
assert all(r['sender_role'] != 'unknown' and ('@'+'chatroom') not in r['chat_username'] for r in full)
assert len(rows) == sum(r['sender_role']=='me' and r['kind'] in ('text','quoted_reply') for r in full)

def credential_like(text):
    if re.search(r'\b(?:sk-|gh[pousr]_|github_pat_|AIzaSy)[A-Za-z0-9_-]{8,}', text):
        return True
    for token in re.findall(r'[^\s\u4e00-\u9fff]{12,}', text):
        if re.search(r'[A-Za-z]',token) and re.search(r'\d',token) and len(re.findall(r'[^A-Za-z0-9@./:_-]',token))>=2:
            return True
    return False

def flags(text):
    reasons = []
    if not text.strip(): reasons.append('empty')
    if re.fullmatch(r'\s*(?:https?://\S+\s*)+', text): reasons.append('link_only')
    if len(text) > 400: reasons.append('long_authorship_uncertain')
    if re.search(r'```|<!DOCTYPE|<html|^\s*(?:def |class |import |function |SELECT |#include)', text, re.I|re.M): reasons.append('code_or_structured')
    if re.search(r'^\s*(?:sudo |npm (?:install|run)|pip(?:3)? install|git (?:clone|push|pull)|winget |curl |npx )',text): reasons.append('command')
    if re.search(r'复制此口令|#墨墨背单词#|访问\s+www\.|^I am .+\x27s ',text): reasons.append('shared_or_system_template')
    if re.fullmatch(r'\s*\d{4,}\s*',text): reasons.append('numeric_identifier')
    if credential_like(text): reasons.append('credential_like')
    if len(text)>100 and (text.count('\n')>=6 or len(re.findall(r'https?://',text))>=2): reasons.append('formatted_authorship_uncertain')
    return reasons

eligible = [r for r in rows if not flags(r['text'])]
excluded = [r for r in rows if flags(r['text'])]

def percentile(values, p):
    a=sorted(values)
    return a[int((len(a)-1)*p)] if a else None

def distribution(source):
    texts=[r['text'] for r in source]
    lengths=[len(t) for t in texts]
    buckets=Counter('1-5' if n<=5 else '6-10' if n<=10 else '11-20' if n<=20 else '21-50' if n<=50 else '51-100' if n<=100 else '101+' for n in lengths)
    n=len(texts)
    return {'messages':n,'characters':sum(lengths),'median_characters':statistics.median(lengths),'mean_characters':round(statistics.mean(lengths),3),
            'p75_characters':percentile(lengths,.75),'p90_characters':percentile(lengths,.9),'p95_characters':percentile(lengths,.95),'max_characters':max(lengths),
            'length_buckets':dict(buckets),'no_terminal_punctuation':sum(bool(t.strip()) and not re.search(r'[。！？!?；;…\.]\s*$',t) for t in texts),
            'with_question_mark':sum(bool(re.search(r'[?？]',t)) for t in texts),
            'with_exclamation_mark':sum(bool(re.search(r'[!！]',t)) for t in texts),
            'with_full_stop':sum('。' in t for t in texts),'with_newline':sum('\n' in t for t in texts),
            'with_wechat_emoticon':sum(bool(re.search(r'\[[^\[\]\n]{1,10}\]',t)) for t in texts),
            'with_unicode_emoji':sum(bool(re.search('[\U0001f300-\U0001faff\u2600-\u27bf]',t)) for t in texts)}

allowed_short=['好','好的','好滴','好嘞','嗯','嗯嗯','哦','哦哦','噢','噢噢','行','行吧','可以','可以的','对','对的','是的','不是','没有','没事','没事的','谢谢','谢谢老师','收到','知道了','不知道','哈哈','哈哈哈','哈哈哈哈','确实','也是','那行','好吧','OK','ok','okk','OKK','？','?']
exact=Counter(r['text'].strip() for r in eligible)
tokens=['然后','就是','我觉得','我感觉','感觉','应该','可能','好像','其实','主要','因为','所以','但是','不过','不一定','能不能','可以吗','怎么','为什么','为啥','咋','要不','先','再','比如','如果','是不是','有没有','不是','而是','哈哈','[捂脸]','[笑哭]','谢谢','麻烦','老师','您','你好','您好','直接','就','啊','吧','呗','嘛','呢','啥','意思','问题','不用','不对','等会','晚点','一下','发一下','帮','把','请问','我看看','我试试']
token_counts={}
for token in tokens:
    matched=[r for r in eligible if token in r['text']]
    token_counts[token]={'messages':len(matched),'chats':len({r['chat_id'] for r in matched}),'occurrences':sum(r['text'].count(token) for r in matched)}

by_chat=defaultdict(list)
for r in full: by_chat[r['chat_id']].append(r)
turns=[]
for chat,messages in by_chat.items():
    messages.sort(key=lambda r:(r['timestamp'],r['local_id']))
    current=[]
    for r in messages:
        good=r['sender_role']=='me' and r['kind'] in ('text','quoted_reply') and not flags(r['text'])
        if good:
            if current and r['timestamp']-current[-1]['timestamp']>120:
                turns.append(current); current=[]
            current.append(r)
        elif r['sender_role'] != 'system':
            if current: turns.append(current);current=[]
    if current: turns.append(current)

turn_sizes=[len(t) for t in turns]
chat_counts=Counter(r['chat_id'] for r in eligible)
months=Counter(r['time'][:7] for r in rows)
out={'schema_version':1,'analysis_date':'2026-10-24','timezone':'Asia/Shanghai',
     'source':{'self_messages':len(rows),'self_message_chats':len({r['chat_id'] for r in rows}),
               'all_exported_messages':len(full),'all_exported_chats':len(by_chat),
               'first_self_message':min(r['time'] for r in rows),'last_self_message':max(r['time'] for r in rows),
               'self_jsonl_sha256':hashlib.sha256(args.self_path.read_bytes()).hexdigest(),
               'full_jsonl_sha256':hashlib.sha256(args.full_path.read_bytes()).hexdigest()},
     'all_self_messages':distribution(rows),'candidate_spontaneous_messages':distribution(eligible),
     'excluded_candidate_messages':len(excluded),'exclusion_reason_counts':dict(Counter(reason for r in excluded for reason in flags(r['text']))),
     'monthly_message_counts':dict(sorted(months.items())),
     'own_all_message_types':dict(Counter(str(r['message_type'] & 0xffffffff) for r in full if r['sender_role']=='me')),
     'safe_common_short_replies':{word:exact[word] for word in allowed_short if exact[word]},
     'predefined_expression_counts':token_counts,
     'turn_definition':'consecutive eligible own text messages, no intervening non-system other/media message, adjacent gap <=120 seconds',
     'turns':{'count':len(turns),'median_messages':statistics.median(turn_sizes),'multi_message_turns':sum(n>1 for n in turn_sizes),
              'messages_in_multi_message_turns':sum(n for n in turn_sizes if n>1),'three_or_more_message_turns':sum(n>=3 for n in turn_sizes)},
     'sampling_concentration':{'largest_chat_share':round(max(chat_counts.values())/len(eligible),4),
                                'top_five_chat_share':round(sum(sorted(chat_counts.values(),reverse=True)[:5])/len(eligible),4)},
     'limitations':['Sent by the owner is not proof of original authorship.','The filtering rules are heuristics, not AI detection.',
                   'Chat samples do not establish an article or formal-document voice.','Relationship, personality and private facts are not inferred.',
                   'Phrase counts are substring counts; one message may match several phrases.','The current readable local corpus begins in February 2026.']}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Review material is written only to the caller-selected local path; never to evidence/.
names={r['chat_name'] for r in full if len(r['chat_name'])>=2}
names |= {r['chat_username'] for r in full}
names |= {r['sender_username'] for r in full if r['sender_username']}
name_pattern=re.compile('|'.join(re.escape(n) for n in sorted(names,key=len,reverse=True)))
def redact(text):
    if credential_like(text): return '[含疑似凭据的整条消息已屏蔽]'
    text=name_pattern.sub('[称呼]',text)
    text=re.sub(r'https?://\S+','[链接]',text)
    text=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[邮箱]',text)
    text=re.sub(r'(?<!\d)1[3-9]\d{9}(?!\d)','[手机号]',text)
    text=re.sub(r'\b\d{8,}\b','[长数字]',text)
    text=re.sub(r'(?<!\d)\d{4,}(?!\d)','[数字字段]',text)
    text=re.sub(r'(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?','[域名]',text)
    text=re.sub(r'wxid_[\w]+|[A-Za-z0-9_-]+@(?:chatroom|openim)','[账号]',text)
    text=re.sub(r'(?:地址|收货地址|身份证|密码|验证码|卡号|银行卡|护照)[：:].*','[敏感字段]',text)
    return text

rng=random.Random(20261024)
sample=[]
for month in sorted(months):
    pool=[r for r in eligible if r['time'].startswith(month)]
    sample += rng.sample(pool,min(12,len(pool)))
for chat,pool in by_chat.items():
    own=[r for r in pool if r['sender_role']=='me' and r['kind'] in ('text','quoted_reply') and 12<=len(r['text'])<=240 and not flags(r['text'])]
    sample += rng.sample(own,min(3,len(own)))
for token in ['我觉得','我感觉','因为','所以','但是','不过','先','然后','能不能','要不','不一定','谢谢','老师']:
    pool=[r for r in eligible if token in r['text'] and 15<=len(r['text'])<=240]
    sample += rng.sample(pool,min(5,len(pool)))
sample += sorted(eligible,key=lambda r:len(r['text']),reverse=True)[:12]
seen=set();review=[]
for r in sample:
    key=(r['chat_id'],r['local_id'],r['server_id'])
    if key in seen:continue
    seen.add(key)
    review.append({'section':'individual','source_id':hashlib.sha256(str(key).encode()).hexdigest()[:12], 'chars':len(r['text']),'text':redact(r['text'])})
chosen=[t for t in turns if len(t)>=3 and 20<=sum(len(r['text']) for r in t)<=250]
for turn in rng.sample(chosen,min(45,len(chosen))):
    review.append({'section':'multi_message_turn','messages':[redact(r['text']) for r in turn]})
for r in sorted(excluded,key=lambda r:len(r['text']),reverse=True)[:10]:
    review.append({'section':'excluded_authorship_uncertain','chars':len(r['text']),'reasons':flags(r['text']),'text':redact(r['text'][:500])})
args.review_file.parent.mkdir(parents=True,exist_ok=True)
args.review_file.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in review)+'\n',encoding='utf-8')
print(json.dumps({'stats_file':str(args.output),'review_items':len(review),'raw_self_messages':len(rows),'eligible_candidate_messages':len(eligible),'excluded_messages':len(excluded)},ensure_ascii=False))
