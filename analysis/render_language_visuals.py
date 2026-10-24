"""Render a privacy-safe word cloud and punctuation marks from aggregate JSON only."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.fonttype'] = 'none'
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch

parser = argparse.ArgumentParser()
parser.add_argument('--stats', type=Path, default=Path('evidence/language-markers.json'))
parser.add_argument('--png', type=Path, default=Path('evidence/language-cloud.png'))
parser.add_argument('--svg', type=Path, default=Path('evidence/language-cloud.svg'))
args = parser.parse_args()
data = json.loads(args.stats.read_text(encoding='utf-8'))
font_path = Path('C:/Windows/Fonts/NotoSansSC-VF.ttf')
if not font_path.exists():
    font_path = Path('C:/Windows/Fonts/msyh.ttc')
font = FontProperties(fname=str(font_path))

paper = '#F6F2EA'
ink = '#2E3437'
muted = '#747A7A'
palette = {
    'short_reply_and_laughter': '#326B6A',
    'colloquial_questions': '#C56F58',
    'time_and_action': '#6F7B9A',
    'particles_and_interjections': '#B78C45',
    'discourse_connectors': '#5B6569',
    'requests_and_politeness': '#92759C',
    'stance_and_uncertainty': '#62836B',
}

ranked = []
for group, phrases in data['expression_candidates']['groups'].items():
    for phrase, record in phrases.items():
        if record['messages']:
            ranked.append((record['messages'], group, phrase))
ranked.sort(reverse=True)
top = ranked[:24]
by_phrase = {phrase: (count, group) for count, group, phrase in top}
rows = [top[i:i + 4] for i in range(0, len(top), 4)]

fig = plt.figure(figsize=(15, 8.7), facecolor=paper)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
ax.add_patch(FancyBboxPatch((0.015, 0.015), 0.97, 0.97, boxstyle='round,pad=0.006,rounding_size=0.02',
                            linewidth=1.0, edgecolor='#D9D2C5', facecolor=paper, transform=ax.transAxes))
ax.text(0.055, 0.925, '聊天里常见的词和标点', fontproperties=font, fontsize=25, color=ink, weight='bold', va='top')
source = data['source']
ax.text(0.057, 0.872, f"{source['eligible_messages']:,} 条候选消息  ·  {source['eligible_chats']} 个会话  ·  {source['eligible_characters']:,} 字",
        fontproperties=font, fontsize=11, color=muted, va='top')
ax.text(0.057, 0.825, '词越大，含该词的消息越多；右侧标点数字为 glyph 出现次数。',
        fontproperties=font, fontsize=10.5, color=muted, va='top')

# A clean, measured tag cloud: size reflects messages containing each term.
x_positions = [0.11, 0.275, 0.44, 0.605]
y_positions = [0.735, 0.635, 0.535, 0.435, 0.335, 0.235]
max_count = max(count for count, _, _ in top)
for row_index, row in enumerate(rows):
    for column_index, (count, group, phrase) in enumerate(row):
        x, y = x_positions[column_index], y_positions[row_index]
        size = 16 + 31 * (count / max_count) ** 0.55
        ax.text(x, y, phrase, fontproperties=font, fontsize=size, color=palette[group],
                ha='center', va='center', weight='bold' if count > 100 else 'regular')
        ax.text(x, y - 0.038, f'{count:,} 条', fontproperties=font, fontsize=8.5, color=muted, ha='center', va='center')

# Punctuation cards use glyph-specific counts and message-level category shares.
ax.plot([0.735, 0.735], [0.18, 0.79], color='#D8D1C4', linewidth=1.0)
ax.text(0.78, 0.775, '常见标点', fontproperties=font, fontsize=14, color=ink, weight='bold', va='top')
punct = data['punctuation']['categories']
cards = [
    ('，', '中文逗号', punct['comma']['glyphs']['，'], punct['comma']),
    ('？', '中文问号', punct['question_mark']['glyphs']['？'], punct['question_mark']),
    ('。', '中文句号', punct['full_stop']['glyphs']['。'], punct['full_stop']),
]
for i, (glyph, label, glyph_count, group) in enumerate(cards):
    y = 0.64 - i * 0.19
    ax.add_patch(FancyBboxPatch((0.775, y - 0.11), 0.17, 0.15, boxstyle='round,pad=0.012,rounding_size=0.012',
                                linewidth=0.8, edgecolor='#DED7CA', facecolor='#FBF9F4', transform=ax.transAxes))
    ax.text(0.815, y - 0.025, glyph, fontproperties=font, fontsize=34, color='#C56F58', ha='center', va='center')
    ax.text(0.855, y + 0.005, label, fontproperties=font, fontsize=9, color=muted, va='center')
    ax.text(0.855, y - 0.035, f'{glyph_count:,} 次', fontproperties=font, fontsize=13, color=ink, weight='bold', va='center')
    ax.text(0.855, y - 0.07, f"{group['message_share'] * 100:.1f}% 消息含此类", fontproperties=font, fontsize=7.6, color=muted, va='center')

ax.text(0.055, 0.075, '词频用子串匹配；“就、啊、所以”等在不同语境里含义不同，频次本身不等于固定口头禅。',
        fontproperties=font, fontsize=9, color=muted, va='center')
ax.text(0.945, 0.075, '2026-10-24', fontproperties=font, fontsize=9, color=muted, ha='right', va='center')

args.png.parent.mkdir(parents=True, exist_ok=True)
args.svg.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(args.png, dpi=180, facecolor=paper, bbox_inches=None)
fig.savefig(args.svg, facecolor=paper, bbox_inches=None)
plt.close(fig)
# Matplotlib's vector paths may end each wrapped coordinate line with a space.
svg_text = args.svg.read_text(encoding='utf-8')
args.svg.write_text('\n'.join(line.rstrip() for line in svg_text.splitlines()) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'png': str(args.png), 'svg': str(args.svg), 'terms': len(top), 'font': str(font_path)}))
