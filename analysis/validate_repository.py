"""Validate publication boundaries and aggregate data; not a voice-quality test."""
import argparse
import hashlib
import json
import re
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--self',dest='self_path',type=Path,required=True)
parser.add_argument('--full',dest='full_path',type=Path,required=True)
args=parser.parse_args()
root=Path(__file__).absolute().parent.parent
allowed={'.gitignore','README.md','AGENTS.md','CHANGELOG.md',
         'analysis/analyze_style.py','analysis/analyze_markers.py','analysis/render_language_visuals.py','analysis/validate_repository.py',
         'profile/VOICE.md','profile/voice-profile.json',
         'scenarios/chat.md','scenarios/article.md','scenarios/formal.md',
         'prompts/use-my-voice.md','evidence/corpus-stats.json','evidence/methodology.md',
         'evidence/validation.json','evidence/language-markers.json','evidence/language-markers.md',
         'evidence/language-cloud.svg','evidence/obsidian-writing.md',
         'evaluation/cases.json','evaluation/README.md',*[f'calibration/round-{n}.json' for n in range(1,16)]}
files={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix()!='evidence/language-cloud.png' and '.git' not in p.relative_to(root).parts}
assert set(files)<=allowed, 'Unexpected publication file'
assert allowed-{'evidence/validation.json'} <= set(files), 'Missing publication file'
self_rows=[json.loads(l) for l in args.self_path.read_text(encoding='utf-8').splitlines()]
full=[json.loads(l) for l in args.full_path.read_text(encoding='utf-8').splitlines()]
stats=json.loads((root/'evidence/corpus-stats.json').read_text(encoding='utf-8'))
assert stats['source']['self_messages']==len(self_rows)==9661
assert stats['source']['all_exported_messages']==len(full)==22547
assert stats['source']['self_message_chats']==len({r['chat_id'] for r in self_rows})==82
assert stats['source']['all_exported_chats']==len({r['chat_id'] for r in full})==93
assert stats['all_self_messages']['characters']==sum(len(r['text']) for r in self_rows)
assert stats['source']['self_jsonl_sha256']==hashlib.sha256(args.self_path.read_bytes()).hexdigest()
assert stats['source']['full_jsonl_sha256']==hashlib.sha256(args.full_path.read_bytes()).hexdigest()
assert stats['candidate_spontaneous_messages']['messages']+stats['excluded_candidate_messages']==len(self_rows)
assert sum(stats['candidate_spontaneous_messages']['length_buckets'].values())==stats['candidate_spontaneous_messages']['messages']
assert all(('@'+'chatroom') not in r['chat_username'] for r in full)

marker_stats=json.loads((root/'evidence/language-markers.json').read_text(encoding='utf-8'))
assert marker_stats['source']['self_jsonl_sha256']==hashlib.sha256(args.self_path.read_bytes()).hexdigest()
assert marker_stats['source']['eligible_messages']==9514
assert marker_stats['source']['eligible_chats']==81
assert marker_stats['source']['eligible_characters']==82529
assert marker_stats['source']['excluded_messages']==147
assert set(marker_stats['punctuation']['categories'])=={'comma','full_stop','question_mark','exclamation_mark','enumeration_comma','semicolon','colon','ellipsis_mark','dash','hyphen','parentheses','quotation_marks','brackets','slash'}
assert marker_stats['expression_candidates']['exact_short_replies']
assert '<svg' in (root/'evidence/language-cloud.svg').read_text(encoding='utf-8')[:1000]

profile=json.loads((root/'profile/voice-profile.json').read_text(encoding='utf-8'))
assert len({r['id'] for r in profile['rules']})==len(profile['rules'])
assert all(r['status'] in profile['status_definitions'] for r in profile['rules'])
assert profile['owner_review_status']=='partially_calibrated'
assert any(r['id']=='instruction.priority_tact_nonrepetition' and r['status']=='user_confirmed' for r in profile['rules'])
assert profile['source_sets']['wechat']['includes_obsidian'] is False
assert profile['source_sets']['obsidian_personal_narrative']['includes_wechat'] is False
assert profile['source_sets']['obsidian_personal_narrative']['sample_count']==1
assert profile['source_sets']['obsidian_dictation']['excluded_from']==['written_style_rules','punctuation_counts','phrase_frequencies']
assert profile['coverage']['article']=='five_short_synthetic_preferences_insufficient_for_long_form'
assert profile['calibration']=={'rounds':15,'case_count':21,'owner_written_replies':10,'owner_written_variant_sets':1,'owner_selected_options':10,'blind_evaluation':False,'record':profile['calibration']['record'],'generalization':'case-scoped preferences confirmed; cross-case synthesis remains hypothetical'}
calibration_rounds=[json.loads((root/f'calibration/round-{n}.json').read_text(encoding='utf-8')) for n in range(1,16)]
assert all(r['blind_evaluation'] is False for r in calibration_rounds)
assert [len(r['cases']) for r in calibration_rounds]==[7]+[1]*14
calibration_cases=[c for r in calibration_rounds for c in r['cases']]
assert len({c['id'] for c in calibration_cases})==21
assert sum(c['evidence_kind']=='owner_written_synthetic_reply' for c in calibration_cases)==10
assert sum(c['evidence_kind']=='owner_selected_synthetic_option' for c in calibration_cases)==10
assert sum(c['evidence_kind']=='owner_written_synthetic_variants' for c in calibration_cases)==1
variant_case=calibration_rounds[13]['cases'][0]
assert variant_case['ordering']=='unordered' and len(variant_case['preferred_variants'])==10
assert calibration_rounds[0]['interaction_preference']['status']=='user_confirmed'
assert calibration_rounds[3]['owner_confirmed_delivery_preference']['status']=='user_confirmed'
cases=json.loads((root/'evaluation/cases.json').read_text(encoding='utf-8'))
assert cases['all_scenarios_synthetic'] is True and cases['owner_blind_review']=='not_run'
assert len(cases['cases'])==10 and len({c['id'] for c in cases['cases']})==10
assert all(c['must_preserve'] and c['must_not_invent'] and c['style_checks'] for c in cases['cases'])

contents={name:p.read_text(encoding='utf-8') for name,p in files.items() if p.suffix.lower() not in {'.png','.jpg','.jpeg'}}
assert all('\ufffd' not in text and '\x00' not in text for text in contents.values())
secret_patterns=[r'\b(?:ghp_|gho_|github_pat_|sk-)[A-Za-z0-9_-]{20,}',
                 r'(?<![A-Za-z0-9])1[3-9]\d{9}(?![A-Za-z0-9])',
                 r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
                 r'wxid_[A-Za-z0-9]{8,}',
                 r'shawn89890916/' + r'agent-memory',r'mem_[a-f0-9]{12,}']
for text in contents.values():
    assert not any(re.search(pattern,text) for pattern in secret_patterns), 'Identifier or credential pattern in publication'

generic={'老师','同学','微信','文件传输助手','妈妈','爸爸','爷爷','奶奶','外公','外婆','哥哥','姐姐','弟弟','妹妹','你好'}
private_names={r['chat_name'] for r in full if len(r['chat_name'])>=2 and r['chat_name'] not in generic}
private_ids={r['chat_username'] for r in full if len(r['chat_username'])>=6}
private_ids|={r['sender_username'] for r in full if r['sender_username'] and len(r['sender_username'])>=6}
joined='\n'.join(contents.values())
def contains_name(text,name):
    if re.fullmatch(r'[A-Za-z0-9_ .-]+',name):
        return re.search(r'(?<![A-Za-z0-9_])'+re.escape(name)+r'(?![A-Za-z0-9_])',text) is not None
    return name in text
assert not any(contains_name(joined,name) for name in private_names), 'Private contact display name in publication'
assert not any(identifier in joined for identifier in private_ids), 'Private account identifier in publication'

raw_long={r['text'].strip() for r in self_rows if len(r['text'].strip())>=32}
assert not any(text in joined for text in raw_long), 'Verbatim long private message in publication'
credential_tokens=set()
for record in full:
    for token in re.findall(r'[^\s\u4e00-\u9fff]{12,}',record['text']):
        if re.search('[A-Za-z]',token) and re.search(r'\d',token) and len(re.findall(r'[^A-Za-z0-9@./:_-]',token))>=2:
            credential_tokens.add(token)
assert not any(token in joined for token in credential_tokens), 'Private credential-like token copied into publication'

report={'status':'passed','validation_type':'artifact_data_and_privacy_only',
        'source_self_messages':len(self_rows),'source_full_messages':len(full),
        'candidate_messages':stats['candidate_spontaneous_messages']['messages'],
        'publication_file_count':len(files),'rule_count':len(profile['rules']),'synthetic_case_count':len(cases['cases']),
        'checks':['explicit file allowlist','source SHA-256 and aggregate counts','JSON structure and rule states',
                  'private contact and account identifiers absent','credential patterns and source tokens absent',
                  'no private memory-store references','no verbatim long private messages','UTF-8 text without replacement characters','aggregate marker totals and chart outputs',
                  'synthetic examples separated from observed evidence'],
        'owner_voice_quality_evaluation':'twenty_one_nonblind_synthetic_cases_with_one_unranked_variant_set',
        'owner_blind_evaluation':'not_run','calibration_case_count':len(calibration_cases)}
(root/'evidence/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(report,ensure_ascii=False))
