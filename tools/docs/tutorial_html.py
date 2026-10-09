"""TUTORIAL.md -> a styled single HTML page (for publishing).
Usage: python tools/docs/tutorial_html.py TUTORIAL.md out.html tools/docs/tutorial_tpl.html
Handles the subset the tutorial uses:
headings, paragraphs, ordered/unordered lists (one level + continuation lines), tables, fenced code,
inline code, bold, links, horizontal rules."""
import html
import re
import sys
from pathlib import Path

src = Path(sys.argv[1]).read_text(encoding='utf-8')
out = Path(sys.argv[2])


def inline(t):
    parts = re.split(r'(`[^`]+`)', t)
    res = []
    for p in parts:
        if p.startswith('`') and p.endswith('`') and len(p) > 1:
            res.append('<code>' + html.escape(p[1:-1]) + '</code>')
        else:
            p = html.escape(p)
            p = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', p)
            p = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', p)
            res.append(p)
    return ''.join(res)


lines = src.splitlines()
body, toc = [], []
i = 0
h2n = 0
title = subtitle = ''


def slug(n):
    return f's{n}'


while i < len(lines):
    l = lines[i]
    if l.startswith('```'):
        lang = l[3:].strip()
        j = i + 1
        code = []
        while j < len(lines) and not lines[j].startswith('```'):
            code.append(lines[j]); j += 1
        body.append(f'<div class="code"><pre><code>{html.escape(chr(10).join(code))}</code></pre></div>')
        i = j + 1; continue
    if l.startswith('# '):
        title = l[2:].strip(); i += 1; continue
    if l.startswith('## ') and not title == '' and not subtitle and l[3:].startswith('——'):
        subtitle = l[3:].strip('— ').strip(); i += 1; continue
    if l.startswith('## '):
        h2n += 1
        txt = l[3:].strip()
        toc.append((slug(h2n), txt))
        body.append(f'<h2 id="{slug(h2n)}">{inline(txt)}</h2>'); i += 1; continue
    if l.startswith('### '):
        body.append(f'<h3>{inline(l[4:].strip())}</h3>'); i += 1; continue
    if l.strip() == '---':
        i += 1; continue
    if l.startswith('|'):
        rows = []
        while i < len(lines) and lines[i].startswith('|'):
            rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')]); i += 1
        head, rest = rows[0], rows[2:]
        t = ['<div class="table"><table><thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in head) + '</tr></thead><tbody>']
        for r in rest:
            t.append('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>')
        t.append('</tbody></table></div>')
        body.append(''.join(t)); continue
    m = re.match(r'^(\d+)\. (.*)', l)
    if m or l.startswith('- '):
        ordered = bool(m)
        items = []
        while i < len(lines):
            l = lines[i]
            m2 = re.match(r'^(\d+)\. (.*)', l) if ordered else (re.match(r'^- (.*)', l))
            if m2:
                items.append([m2.group(2) if ordered else m2.group(1), []]); i += 1; continue
            if l.startswith('   ') and items:
                if l.strip().startswith('```'):
                    j = i + 1; code = []
                    while j < len(lines) and not lines[j].strip().startswith('```'):
                        code.append(lines[j][3:]); j += 1
                    items[-1][1].append(f'<div class="code"><pre><code>{html.escape(chr(10).join(code))}</code></pre></div>')
                    i = j + 1; continue
                sub = l.strip()
                if sub.startswith('- ') or re.match(r'^\d+\. ', sub):
                    items[-1][1].append('<li>' + inline(re.sub(r'^(- |\d+\. )', '', sub)) + '</li>')
                else:
                    items[-1][0] += sub
                i += 1; continue
            if l.startswith('  - ') and items:
                items[-1][1].append('<li>' + inline(l.strip()[2:]) + '</li>'); i += 1; continue
            break
        tag = 'ol' if ordered else 'ul'
        h = [f'<{tag}>']
        for txt, extra in items:
            lis = [e for e in extra if e.startswith('<li>')]
            other = [e for e in extra if not e.startswith('<li>')]
            h.append('<li>' + inline(txt) + ''.join(other) + (f'<ul>{"".join(lis)}</ul>' if lis else '') + '</li>')
        h.append(f'</{tag}>')
        body.append(''.join(h)); continue
    if not l.strip():
        i += 1; continue
    para = [l.strip()]
    i += 1
    while i < len(lines) and lines[i].strip() and not re.match(r'^(#|\||```|- |\d+\. |---)', lines[i]):
        para.append(lines[i].strip()); i += 1
    body.append('<p>' + inline(''.join(para)) + '</p>')

toc_html = ''.join(f'<li><a href="#{a}">{inline(t)}</a></li>' for a, t in toc)
tpl = Path(sys.argv[3]).read_text(encoding='utf-8')
page = (tpl.replace('{{TITLE}}', html.escape(title)).replace('{{SUBTITLE}}', html.escape(subtitle))
        .replace('{{TOC}}', toc_html).replace('{{BODY}}', '\n'.join(body)))
out.write_text(page, encoding='utf-8')
print('ok', len(page), 'bytes,', h2n, 'sections')
