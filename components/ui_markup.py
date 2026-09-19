"""Escaped, data-only HTML for progressive UI enhancements (no network access)."""
from hashlib import sha256
from html import escape
import math
import re

from portfolio_logic import goal_progress, money, percent, quantity


def animated_value(value, key, *, masked=False):
    text = str(value)
    if masked:
        text = '••••••'
    enabled = not masked and any(c.isdigit() for c in text)
    digits = ''.join(f'<span class="cf-digit" aria-hidden="true">{escape(c)}</span>' for c in text)
    return (f'<span class="cf-number" data-motion-key="{escape(str(key), quote=True)}" '
            f'data-motion-enabled="{str(enabled).lower()}" role="text" aria-label="{escape(text, quote=True)}">'
            f'{digits}</span>')


def success_markup(message):
    return ('<div class="cf-success" role="status">'
            '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10"/>'
            '<path d="m7 12 3.5 3.5L17 9"/></svg>'
            f'<span>{escape(str(message))}</span></div>')


def loading_markup(label, kind='cards'):
    text = f'<span class="cf-loading-label">{escape(label)}</span>'
    if kind == 'thinking':
        content = f'<span class="cf-thinking-dot" aria-hidden="true"></span>{text}'
    elif kind == 'chart':
        content = text + '<div class="cf-skeleton-chart cf-skeleton" aria-hidden="true"></div>'
    else:
        blocks = ''.join('<div class="cf-skeleton-card"><i class="cf-skeleton"></i><b class="cf-skeleton"></b><i class="cf-skeleton"></i></div>' for _ in range(4))
        content = text + f'<div class="cf-skeleton-grid" aria-hidden="true">{blocks}</div>'
    return f'<div class="cf-loading cf-loading-{kind}" role="status" aria-live="polite" aria-busy="true">{content}</div>'


def _comment(text):
    # Emphasize only numbers actually present in the saved memo. No live-price
    # metrics are mixed into a memo generated from an earlier data timestamp.
    return re.sub(r'([+−-]?\d[\d,.]*\s*(?:%|％|pp|パーセントポイント|パーセント|ポイント))', r'<strong class="cf-inline-number">\1</strong>', escape(str(text))).replace('\n', '<br>')


def insight_markup(record, *, archive=False):
    title = '過去の分析メモ' if archive else '本日の分析メモ'
    stamp = str(record.get('date', ''))
    sections = record.get('sections')
    if not isinstance(sections, dict) or not all(k in sections for k in ('overview', 'drivers', 'watch')):
        return f'<div class="ai-insight-card"><strong>{title} · {escape(stamp)}</strong><p>{_comment(record.get("comment", ""))}</p></div>'
    deck_id = 'insight-' + sha256(f'{archive}-{stamp}'.encode()).hexdigest()[:12]
    labels = [('overview', '今日の全体像', '全体像'), ('drivers', '変化をつくった銘柄', '影響'), ('watch', '構成比と確認ポイント', '確認点')]
    tabs, cards = [], []
    for index, (key, label, short) in enumerate(labels):
        tabs.append(f'<button type="button" role="tab" id="{deck_id}-tab-{index}" aria-controls="{deck_id}-card-{index}" aria-selected="{str(index == 0).lower()}" data-insight-index="{index}">{short}</button>')
        cards.append(f'<article class="cf-insight" id="{deck_id}-card-{index}" data-insight-card="{index}" aria-labelledby="{deck_id}-heading-{index}"><div class="cf-insight-index" aria-hidden="true">0{index+1}</div><h4 id="{deck_id}-heading-{index}">{label}</h4><p>{_comment(sections[key])}</p></article>')
    return (f'<section class="ai-insight-card cf-insight-deck" data-insight-id="{deck_id}">'
            f'<div class="cf-insight-heading"><strong>{title}</strong><span>{escape(stamp)}</span></div>'
            f'<div class="cf-insight-tabs" role="tablist" aria-label="分析メモの表示内容">{"".join(tabs)}</div>'
            f'<div class="cf-insight-grid">{"".join(cards)}</div></section>')


def goal_markup(symbol, row, goal, currency, mask=False, *, complete=True):
    progress = goal_progress(row['holdings'], goal.get('target_quantity'), row.get('weight'), goal.get('target_weight'))
    body = f'<div class="cf-goal-heading"><h3>{escape(symbol)}</h3><span>保有目標</span></div>'
    ratio = progress['ratio']
    if ratio is not None and math.isfinite(ratio):
        filled = min(max(ratio, 0), 1) * 100
        rate = animated_value(f'{ratio*100:.1f}%', f'goal-{goal["asset_id"]}', masked=mask)
        body += f'<div class="cf-goal-rate"><span>数量目標の達成率</span><strong>{rate}</strong></div>'
        if not mask:
            body += (f'<div class="goal-progress-track" role="progressbar" aria-label="数量目標の達成率" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{filled:.1f}" aria-valuetext="{ratio*100:.1f}%">'
                     f'<div class="goal-progress-fill" style="width:{filled:.4f}%"></div></div>')
        values = [('現在', quantity(row['holdings'], masked=mask)), ('目標', quantity(goal['target_quantity'], masked=mask)), ('あと', quantity(progress['remaining'], masked=mask))]
        body += '<dl class="cf-goal-comparison">' + ''.join(f'<div><dt>{label}</dt><dd>{escape(value)}<small>{escape(symbol)}</small></dd></div>' for label, value in values) + '</dl>'
        cost = progress['remaining'] * row['price'] if row.get('price') is not None else None
        note = '数量目標を達成しています。' if ratio >= 1 and not mask else f'残りの数量の現在評価額：{money(cost, currency, masked=mask)}'
        body += f'<p class="cf-goal-note">{escape(note)}</p>'
    if goal.get('target_weight') is not None:
        gap = progress['weight_gap']
        gap_text = f'{gap:+.1f}ポイント' if gap is not None else '—'
        values = [('現在の構成比', percent(row.get('weight'), signed=False)), ('目標の構成比', percent(goal['target_weight'], signed=False)), ('目標との差', gap_text)]
        body += '<dl class="cf-goal-comparison cf-goal-weights">' + ''.join(f'<div><dt>{label}</dt><dd>{escape(value)}</dd></div>' for label, value in values) + '</dl>'
        if gap is None:
            body += '<p class="cf-goal-note">価格が揃うと配分差を計算します。</p>'
        elif not complete:
            body += '<p class="cf-goal-note">現在の構成比は価格を取得できた分で計算しています。</p>'
    return f'<article class="cf-goal-card">{body}</article>'
