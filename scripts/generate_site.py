"""
Notionデータベースからニュースを取得してindex.htmlを生成するスクリプト。
GitHub Actionsから毎日7:00 JSTに実行される。
"""

import os
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter, defaultdict

NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
NOTION_VERSION = "2022-06-28"
JST = timezone(timedelta(hours=9))

THEORY_DESCRIPTIONS = {
    "資源ベース理論（RBV）": "企業内部の希少で模倣困難な資源・能力こそが持続的競争優位の源泉とする理論。人材・組織文化・ノウハウを戦略資産として捉える視点を与えてくれます。",
    "センスメイキング理論": "不確実な状況を人々がどう「意味づけ」するかに注目する組織論。変化の渦中にあるとき、リーダーが語るナラティブが組織行動を方向づけます。",
    "ダイナミック・ケイパビリティ": "環境変化に合わせて自社の能力を感知・捕捉・再構成する力。テクノロジーが急変する時代において、静的な強みではなく変化する能力そのものが競争優位になります。",
}

# 理論ごとのカラー（バッジの色分けに使えるよう定義）
THEORY_COLORS = {
    "資源ベース理論（RBV）": "#6B8F71",
    "センスメイキング理論": "#7B8FA0",
    "ダイナミック・ケイパビリティ": "#9B7FA0",
}


def notion_request(path: str, payload: dict) -> dict:
    url = f"https://api.notion.com/v1/{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_all_news(limit: int = 50) -> list[dict]:
    payload = {
        "sorts": [{"property": "配信日", "direction": "descending"}],
        "page_size": limit,
    }
    result = notion_request(f"databases/{NOTION_DATABASE_ID}/query", payload)
    return result.get("results", [])


def extract_text(prop: dict) -> str | list:
    if not prop:
        return ""
    ptype = prop.get("type")
    if ptype == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    if ptype == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    if ptype == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if ptype == "multi_select":
        return [s.get("name", "") for s in prop.get("multi_select", [])]
    if ptype == "date":
        d = prop.get("date")
        return d.get("start", "") if d else ""
    if ptype == "url":
        return prop.get("url", "") or ""
    return ""


def page_to_item(page: dict) -> dict:
    props = page.get("properties", {})
    return {
        "headline": extract_text(props.get("ヘッドライン", {})),
        "tags": extract_text(props.get("タグ", {})) or [],
        "summary": extract_text(props.get("要約", {})),
        "source": extract_text(props.get("出典", {})),
        "theory": extract_text(props.get("経営理論", {})),
        "date": extract_text(props.get("配信日", {})),
        "link": extract_text(props.get("リンク", {})),
    }


def render_theory_box(theory: str) -> str:
    desc = THEORY_DESCRIPTIONS.get(theory, "")
    if not desc:
        return ""
    # Thinking cat SVG inline
    cat_svg = """<svg class="theory-box-cat" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="20" cy="16" r="10" fill="#6B8F71"/>
          <polygon points="12,10 14,4 18,10" fill="#6B8F71"/>
          <polygon points="28,10 26,4 22,10" fill="#6B8F71"/>
          <polygon points="12.5,9 14.5,5 17.5,9" fill="#E8A0B4"/>
          <polygon points="27.5,9 25.5,5 22.5,9" fill="#E8A0B4"/>
          <ellipse cx="16" cy="15" rx="2.5" ry="3" fill="#FAF7F2"/>
          <ellipse cx="24" cy="15" rx="2.5" ry="3" fill="#FAF7F2"/>
          <circle cx="16.5" cy="15.5" r="1.5" fill="#2B2620"/>
          <circle cx="24.5" cy="15.5" r="1.5" fill="#2B2620"/>
          <ellipse cx="20" cy="20" rx="1.5" ry="1" fill="#E8A0B4"/>
          <ellipse cx="20" cy="31" rx="10" ry="8" fill="#6B8F71"/>
          <ellipse cx="13" cy="38" rx="5" ry="3.5" fill="#6B8F71"/>
          <ellipse cx="27" cy="38" rx="5" ry="3.5" fill="#6B8F71"/>
          <text x="28" y="10" font-size="7" fill="#E8A0B4">?</text>
        </svg>"""
    return f"""<div class="theory-box">
          {cat_svg}
          <div class="theory-box-content">
            <div class="theory-box-label">経営理論の視点 ▶ {theory}</div>
            <p class="theory-box-text">{desc}</p>
          </div>
        </div>"""


def render_card(item: dict, num: int, is_today: bool = True) -> str:
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in item["tags"])
    theory = item["theory"] or "未分類"
    theory_box = render_theory_box(theory) if is_today else ""
    new_badge = '<span class="new-badge">NEW</span>' if is_today else ""
    link_html = (
        f'<a class="read-link" href="{item["link"]}" target="_blank" rel="noopener">元記事を読む →</a>'
        if item["link"] else ""
    )
    return f"""    <div class="news-card">
      <div class="card-num">{num:02d}</div>
      <div class="card-meta">
        <span class="theory-badge">{theory}</span>
        {new_badge}
        {tags_html}
      </div>
      <h2 class="card-headline">{item["headline"]}</h2>
      <p class="card-summary">{item["summary"]}</p>
      {theory_box}
      <div class="card-footer">
        <span class="card-source">{item["source"]}</span>
        {link_html}
      </div>
    </div>"""


def render_archive_card(item: dict, num: int) -> str:
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in item["tags"])
    theory = item["theory"] or "未分類"
    link_html = (
        f'<a class="read-link" href="{item["link"]}" target="_blank" rel="noopener">元記事を読む →</a>'
        if item["link"] else ""
    )
    return f"""    <div class="news-card" style="opacity:0.85;">
      <div class="card-num">{num:02d}</div>
      <div class="card-meta">
        <span class="theory-badge">{theory}</span>
        {tags_html}
      </div>
      <h2 class="card-headline">{item["headline"]}</h2>
      <p class="card-summary">{item["summary"]}</p>
      <div class="card-footer">
        <span class="card-source">{item["source"]}</span>
        {link_html}
      </div>
    </div>"""


def format_date_ja(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        d = datetime.fromisoformat(date_str)
        return d.strftime("%-m月%-d日")
    except Exception:
        return date_str


def main():
    pages = fetch_all_news()
    items = [page_to_item(p) for p in pages]

    now = datetime.now(JST)
    today_str = now.strftime("%Y-%m-%d")
    date_label = now.strftime("%-m月%-d日")

    # Split today vs archive
    today_items = [i for i in items if i["date"] == today_str]
    archive_items = [i for i in items if i["date"] != today_str]

    # Today cards
    if today_items:
        today_cards_html = "\n".join(render_card(i, n + 1, True) for n, i in enumerate(today_items))
    else:
        today_cards_html = """    <div class="empty-state">
      <svg class="cat-sleep" viewBox="0 0 100 70" fill="none" xmlns="http://www.w3.org/2000/svg">
        <ellipse cx="50" cy="45" rx="38" ry="20" fill="#9DB8A2"/>
        <circle cx="20" cy="35" r="18" fill="#9DB8A2"/>
        <polygon points="8,26 12,14 20,26" fill="#9DB8A2"/>
        <polygon points="32,26 28,14 20,26" fill="#9DB8A2"/>
        <polygon points="9,25 13,16 19,25" fill="#D4C4CA"/>
        <polygon points="31,25 27,16 21,25" fill="#D4C4CA"/>
        <path d="M13 34 Q20 31 27 34" stroke="#FAF7F2" stroke-width="1.5" stroke-linecap="round" fill="none"/>
        <ellipse cx="20" cy="40" rx="2" ry="1.5" fill="#D4C4CA"/>
        <text x="38" y="28" font-size="12" fill="#9DB8A2">z</text>
        <text x="52" y="20" font-size="9" fill="#9DB8A2">z</text>
        <text x="63" y="14" font-size="7" fill="#9DB8A2">z</text>
      </svg>
      <p>今日のニュースはまだ届いていません。<br>毎朝6時に自動収集します。</p>
    </div>"""

    # Archive grouped by date
    archive_by_date = defaultdict(list)
    for item in archive_items:
        archive_by_date[item["date"]].append(item)

    archive_cards_html = ""
    card_num = 1
    for date_str in sorted(archive_by_date.keys(), reverse=True):
        date_items = archive_by_date[date_str]
        date_ja = format_date_ja(date_str)
        archive_cards_html += f"""  <div style="margin-bottom:36px;">
    <div style="font-family:'Shippori Mincho',serif;font-size:0.9rem;font-weight:700;color:var(--text-sub);letter-spacing:0.06em;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid var(--border);">{date_ja}のニュース</div>
"""
        for item in date_items:
            archive_cards_html += render_archive_card(item, card_num) + "\n"
            card_num += 1
        archive_cards_html += "  </div>\n"

    if not archive_cards_html:
        archive_cards_html = '<p style="color:var(--text-light);font-size:0.85rem;">アーカイブはまだありません。</p>'

    # Tag cloud
    all_tags = []
    for item in items:
        all_tags.extend(item["tags"])
    tag_counts = Counter(all_tags)

    topic_tags_html = ""
    for tag, count in tag_counts.most_common():
        topic_tags_html += f'<span class="topic-tag">{tag}<span class="topic-count">{count}</span></span>\n'

    # Sidebar archive list (recent 10)
    archive_list_html = ""
    recent_archive = archive_items[:10]
    if recent_archive:
        cur_date = None
        for item in recent_archive:
            if item["date"] != cur_date:
                cur_date = item["date"]
                archive_list_html += f'<div class="archive-date">{format_date_ja(cur_date)}</div>\n'
            link_start = f'<a class="archive-item" href="{item["link"]}" target="_blank" rel="noopener">' if item["link"] else '<div class="archive-item">'
            link_end = "</a>" if item["link"] else "</div>"
            archive_list_html += f'{link_start}<div class="archive-theory-dot"></div><div class="archive-headline">{item["headline"]}</div>{link_end}\n'
    else:
        archive_list_html = '<p style="color:var(--text-light);font-size:0.8rem;">まだありません。</p>'

    # Build index.html from template
    template = Path("template.html").read_text(encoding="utf-8")
    html = template
    html = html.replace("<!-- DATE_LABEL -->", date_label)
    html = html.replace("<!-- TODAY_COUNT -->", str(len(today_items)))
    html = html.replace("<!-- TOTAL_COUNT -->", str(len(items)))
    html = html.replace("<!-- TODAY_CARDS -->", today_cards_html)
    html = html.replace("<!-- ARCHIVE_HTML -->", archive_cards_html)
    html = html.replace("<!-- TOPIC_TAGS_HTML -->", topic_tags_html)
    html = html.replace("<!-- ARCHIVE_LIST_HTML -->", archive_list_html)

    Path("index.html").write_text(html, encoding="utf-8")
    print(f"✅ index.html を生成しました（今日 {len(today_items)} 件 / アーカイブ {len(archive_items)} 件 / 合計 {len(items)} 件）")


if __name__ == "__main__":
    main()
