"""
Notionデータベースからニュースを取得してindex.htmlを生成するスクリプト。
GitHub Actionsから毎日7:00 JSTに実行される。

実装済み施策:
  T3: 著者コメント欄
  T4: SNS投稿文 (post_queue.md)
  T2: 理論用語集ページ (theories/{slug}/index.html)
  T1: OGPカード画像 (assets/og/today.png, assets/og/theory-{slug}.png)
"""

import os
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter, defaultdict

NOTION_API_KEY      = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID  = os.environ["NOTION_DATABASE_ID"]
BLOG_DATABASE_ID    = "72e7bb27a6fe40e0ae5e111e94163f7a"
NOTION_VERSION      = "2022-06-28"
JST                 = timezone(timedelta(hours=9))
SITE_URL            = "https://keieiriron.github.io/harunekochan/"
SITE_NAME           = "はるねこちゃん"

# ── 理論スラッグ ──────────────────────────────────────────────
THEORY_SLUGS = {
    "SCP理論":                      "scp",
    "ゲーム理論":                   "game-theory",
    "取引費用理論":                 "transaction-cost",
    "エージェンシー理論":           "agency-theory",
    "コア・コンピタンス理論":       "core-competence",
    "資源ベース理論（RBV）":        "rbv",
    "ダイナミック・ケイパビリティ": "dynamic-capability",
    "リアル・オプション理論":       "real-option",
    "知識創造理論":                 "knowledge-creation",
    "組織学習論":                   "organizational-learning",
    "両利きの経営":                 "ambidexterity",
    "センスメイキング理論":         "sensemaking",
    "上位集団理論":                 "upper-echelon",
    "組織アイデンティティ理論":     "org-identity",
    "制度理論":                     "institutional",
    "組織エコロジー":               "org-ecology",
    "社会ネットワーク理論（弱い紐帯）":   "weak-ties",
    "社会ネットワーク理論（構造的空隙）": "structural-holes",
    "正統性理論":                   "legitimacy",
    "認知理論（経営）":             "cognitive-theory",
    "プロスペクト理論":             "prospect-theory",
    "イノベーションのジレンマ":     "innovators-dilemma",
    "アントレプレナーシップ理論":   "entrepreneurship",
    "スピンオフ理論":               "spinoff",
    "未分類":                       "others",
}

THEORY_PROPOSERS = {
    "SCP理論":                      "マイケル・ポーター（1980年代）",
    "ゲーム理論":                   "ジョン・フォン・ノイマン／ナッシュ他",
    "取引費用理論":                 "オリバー・ウィリアムソン（1975）",
    "エージェンシー理論":           "ジェンセン＆メックリング（1976）",
    "コア・コンピタンス理論":       "プラハラード＆ハメル（1990）",
    "資源ベース理論（RBV）":        "バーニー（1991）",
    "ダイナミック・ケイパビリティ": "ティース他（1997）",
    "リアル・オプション理論":       "マイヤーズ他（1977〜）",
    "知識創造理論":                 "野中郁次郎＆竹内弘高（1995）",
    "組織学習論":                   "アージリス＆ショーン（1978）",
    "両利きの経営":                 "オライリー＆タッシュマン（1996〜）",
    "センスメイキング理論":         "カール・ワイク（1995）",
    "上位集団理論":                 "ハンブリック＆メイソン（1984）",
    "組織アイデンティティ理論":     "アルバート＆ウェッテン（1985）",
    "制度理論":                     "ディマジオ＆パウエル（1983）",
    "組織エコロジー":               "ハナン＆フリーマン（1977）",
    "社会ネットワーク理論（弱い紐帯）":   "マーク・グラノヴェッター（1973）",
    "社会ネットワーク理論（構造的空隙）": "ロナルド・バート（1992）",
    "正統性理論":                   "サッチマン（1995）",
    "認知理論（経営）":             "サイモン他（1945〜）",
    "プロスペクト理論":             "カーネマン＆トヴェルスキー（1979）",
    "イノベーションのジレンマ":     "クレイトン・クリステンセン（1997）",
    "アントレプレナーシップ理論":   "シェーン＆ヴェンカタラマン（2000）",
    "スピンオフ理論":               "アルメイダ＆コグート他",
    "未分類":                       "—",
}

THEORY_DESCRIPTIONS = {
    "SCP理論": "産業構造（Structure）が企業行動（Conduct）を決め、パフォーマンス（Performance）を左右するという枠組み。ポーターの「5つの力」の基盤となり、業界の魅力度を分析する出発点です。",
    "ゲーム理論": "競合・顧客・サプライヤーなど複数のプレーヤーが相互に意思決定し合う状況を分析する理論。価格競争・協調・交渉など、戦略的相互依存を読み解くための強力なツールです。",
    "取引費用理論": "市場取引には探索・交渉・監視などのコストがかかるという考え方。内製か外注か、どの範囲まで組織内に取り込むかという「組織の境界」を決める際の基本論理です。",
    "エージェンシー理論": "依頼人（プリンシパル）と代理人（エージェント）の間に生まれる利害対立と情報非対称を扱う理論。報酬設計・ガバナンス・インセンティブ設計の核心をなします。",
    "コア・コンピタンス理論": "競合が簡単に模倣できない、顧客価値の源泉となる中核能力を指す概念。自社の強みを起点に事業多角化を考える際の指針となります。",
    "資源ベース理論（RBV）": "企業内部の希少で模倣困難な資源・能力こそが持続的競争優位の源泉とする理論。人材・組織文化・ノウハウを戦略資産として捉える視点を与えてくれます。",
    "ダイナミック・ケイパビリティ": "環境変化に合わせて自社の能力を感知・捕捉・再構成する力。テクノロジーが急変する時代において、静的な強みではなく変化する能力そのものが競争優位になります。",
    "リアル・オプション理論": "不確実な状況下での投資判断を「オプション（選択権）」として捉える考え方。段階的投資・撤退・延期の柔軟性に経済的価値を見出し、意思決定の質を高めます。",
    "知識創造理論": "暗黙知と形式知の相互変換（SECIモデル）を通じて組織的知識が創られるプロセスを説く理論。野中郁次郎らが提唱し、イノベーションと学習の源泉を説明します。",
    "組織学習論": "個人の学びが組織全体の知識・ルーティンへと昇華していく仕組みを扱う理論。シングルループ学習（修正）とダブルループ学習（前提の問い直し）の区別が鍵となります。",
    "両利きの経営": "既存事業の「深化（exploitation）」と新規事業の「探索（exploration）」を同時に追求する組織能力の理論。成熟企業がイノベーションを実現するための組織論的解答です。",
    "センスメイキング理論": "不確実な状況を人々がどう「意味づけ」するかに注目する組織論。変化の渦中にあるとき、リーダーが語るナラティブが組織行動を方向づけます。",
    "上位集団理論": "組織のパフォーマンスはトップマネジメントチームの特性（経験・価値観・認知）を反映するという理論。リーダーシップ研究や後継者計画に深く関わります。",
    "組織アイデンティティ理論": "「我々は何者か」という組織の自己認識が、戦略・文化・意思決定に大きな影響を与えるとする理論。組織変革時のメンバーの抵抗感や一体感を理解する鍵です。",
    "制度理論": "企業は経済合理性だけでなく、社会的規範・規制・慣行に適応することで正統性を獲得するとする理論。業界標準への同調や制度的圧力を読み解く視点を提供します。",
    "組織エコロジー": "生物進化に倣い、組織の誕生・成長・死滅を個体群レベルで捉える理論。特定業界で「どんな組織が生き残り、なぜ消えるか」を長期的に分析します。",
    "社会ネットワーク理論（弱い紐帯）": "強い絆よりも「弱いつながり」のほうが、異質な情報・機会・革新をもたらすというグラノヴェッターの知見。人脈・採用・知識探索の設計に応用できます。",
    "社会ネットワーク理論（構造的空隙）": "他者同士がつながっていない「空白」を橋渡しするポジションが、情報・影響力・交渉力の優位をもたらすというバートの理論。組織内外のブローカー的役割を説明します。",
    "正統性理論": "組織が社会・ステークホルダーから「存在する理由がある」と認められることの重要性を説く理論。ESGやブランド戦略、ステークホルダー対応に直結します。",
    "認知理論（経営）": "経営者の認知・信念・注意配分が戦略選択に影響するとする行動論的アプローチ。バイアスや認知の枠組みを意識することで、より良い意思決定が可能になります。",
    "プロスペクト理論": "人は利益より損失を大きく感じる（損失回避）という行動経済学の知見。リスク判断・交渉・報酬設計など、合理性からの逸脱を予測・活用するための理論です。",
    "イノベーションのジレンマ": "優良企業が持続的イノベーションに集中するあまり、破壊的イノベーターに市場を奪われるパラドックスを説くクリステンセンの理論。既存事業の優等生ほど危ない理由です。",
    "アントレプレナーシップ理論": "新たな機会を発見・創造し、資源を結合して価値を生み出す企業家的行動を扱う理論。大企業の社内起業（イントラプレナーシップ）や新規事業開発にも応用されます。",
    "スピンオフ理論": "既存組織から独立した新事業・新企業が生まれるプロセスとその成功要因を扱う理論。親組織の知識・資源・人材がどう次世代イノベーションを生むかを分析します。",
    "未分類": "現時点では既存の経営理論に明確に分類しにくいニュースです。今後の理論的文脈の変化とともに再分類される可能性があります。",
}

# ── Notion API ────────────────────────────────────────────────
def notion_request(path: str, payload: dict) -> dict:
    url  = f"https://api.notion.com/v1/{path}"
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Authorization":    f"Bearer {NOTION_API_KEY}",
            "Notion-Version":   NOTION_VERSION,
            "Content-Type":     "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_all_news(limit: int = 60) -> list[dict]:
    payload = {
        "sorts": [{"property": "配信日", "direction": "descending"}],
        "page_size": limit,
    }
    return notion_request(f"databases/{NOTION_DATABASE_ID}/query", payload).get("results", [])


def extract_text(prop: dict) -> str | list:
    if not prop:
        return ""
    t = prop.get("type")
    if t == "title":
        return "".join(x.get("plain_text", "") for x in prop.get("title", []))
    if t == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop.get("rich_text", []))
    if t == "select":
        s = prop.get("select"); return s.get("name", "") if s else ""
    if t == "multi_select":
        return [s.get("name", "") for s in prop.get("multi_select", [])]
    if t == "date":
        d = prop.get("date"); return d.get("start", "") if d else ""
    if t == "url":
        return prop.get("url", "") or ""
    return ""


def page_to_item(page: dict) -> dict:
    props = page.get("properties", {})
    return {
        "headline":       extract_text(props.get("ヘッドライン", {})),
        "tags":           extract_text(props.get("タグ", {})) or [],
        "summary":        extract_text(props.get("要約", {})),
        "source":         extract_text(props.get("出典", {})),
        "theory":         extract_text(props.get("経営理論", {})),
        "date":           extract_text(props.get("配信日", {})),
        "link":           extract_text(props.get("リンク", {})),
        "author_comment": extract_text(props.get("著者コメント", {})),  # T3
    }

# ── テキスト解析 ──────────────────────────────────────────────
def parse_summary_sections(text: str) -> dict:
    sections = {"facts": "", "analysis": "", "insights": "", "plain": ""}
    markers  = {"【事実】": "facts", "【考察】": "analysis", "【示唆】": "insights"}
    if not any(m in text for m in markers):
        sections["plain"] = text
        return sections
    current = "plain"
    for line in text.replace("\r", "").split("\n"):
        matched = False
        for marker, key in markers.items():
            if line.startswith(marker):
                current = key
                rest = line[len(marker):].strip()
                if rest:
                    sections[current] = (sections[current] + " " + rest).strip()
                matched = True
                break
        if not matched and line.strip():
            sections[current] = (sections[current] + " " + line.strip()).strip()
    return sections

# ── HTML レンダリング ─────────────────────────────────────────
def theory_page_url(theory: str) -> str:
    slug = THEORY_SLUGS.get(theory, "")
    return f"../../theories/{slug}/" if slug else ""


def render_theory_badge(theory: str) -> str:
    url = theory_page_url(theory)
    if url:
        return f'<a class="badge-theory" href="{url}" title="{theory}の解説ページへ">📚 {theory}</a>'
    return f'<span class="badge-theory">📚 {theory}</span>'


def render_theory_box(theory: str) -> str:
    desc = THEORY_DESCRIPTIONS.get(theory, "")
    if not desc:
        return ""
    url = theory_page_url(theory)
    link = f' <a href="{url}" class="theory-box-more">→ 理論を詳しく見る</a>' if url else ""
    return (
        f'<div class="theory-box">'
        f'<div class="theory-box-label">📚 経営理論の視点 ▶ {theory}</div>'
        f'<p class="theory-box-text">{desc}{link}</p>'
        f'</div>'
    )


def render_fb_share(link: str = "") -> str:
    target = link if link else SITE_URL
    enc    = urllib.parse.quote(target, safe="")
    return (
        f'<a class="fb-share" href="https://www.facebook.com/sharer/sharer.php?u={enc}" '
        f'target="_blank" rel="noopener">'
        f'<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">'
        f'<path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/>'
        f'</svg>シェア</a>'
    )


def render_card(item: dict, num: int, is_today: bool = True) -> str:
    tags_html      = "".join(f'<span class="tag">{t}</span>' for t in item["tags"])
    theory         = item["theory"] or "未分類"
    new_badge      = '<span class="badge-new">NEW</span>' if is_today else ""
    theory_badge   = render_theory_badge(theory)

    # 構造化セクション
    secs = parse_summary_sections(item["summary"])
    content_html = ""
    if secs["facts"]:
        content_html += f'<div class="art-section fact"><span class="art-label">📰 事実</span><p>{secs["facts"]}</p></div>'
    if secs["analysis"]:
        content_html += f'<div class="art-section analysis"><span class="art-label">🔍 考察</span><p>{secs["analysis"]}</p></div>'
    if secs["insights"]:
        content_html += f'<div class="art-section insight"><span class="art-label">💡 示唆</span><p>{secs["insights"]}</p></div>'
    if not content_html and secs["plain"]:
        content_html = f'<p class="card-summary">{secs["plain"]}</p>'

    theory_box = render_theory_box(theory) if is_today else ""

    # T3: 著者コメント
    author_html = ""
    if item.get("author_comment"):
        author_html = (
            f'<div class="author-comment">'
            f'<div class="author-comment-head">💬 管理人の視点</div>'
            f'<p class="author-comment-text">{item["author_comment"]}</p>'
            f'</div>'
        )

    # 出典・リンク
    if item["link"]:
        source_html = f'<a class="card-source" href="{item["link"]}" target="_blank" rel="noopener">📎 {item["source"]}</a>'
        link_btn    = f'<a class="read-btn" href="{item["link"]}" target="_blank" rel="noopener">元記事 →</a>'
    else:
        source_html = f'<span class="card-source">{item["source"]}</span>'
        link_btn    = ""

    fb = render_fb_share(item.get("link", ""))

    return f"""<div class="card">
  <div class="card-num">{num:02d}</div>
  <div class="card-meta">
    {theory_badge}
    {new_badge}
    {tags_html}
  </div>
  <h2 class="card-headline">{item["headline"]}</h2>
  {content_html}
  {theory_box}
  {author_html}
  <div class="card-foot">
    {source_html}
    <div class="card-foot-right">{link_btn}{fb}</div>
  </div>
</div>"""


def render_archive_card(item: dict, num: int) -> str:
    tags_html    = "".join(f'<span class="tag">{t}</span>' for t in item["tags"])
    theory       = item["theory"] or "未分類"
    theory_badge = render_theory_badge(theory)
    secs         = parse_summary_sections(item["summary"])
    summary_text = secs["plain"] or secs["facts"] or item["summary"]

    if item["link"]:
        source_html = f'<a class="card-source" href="{item["link"]}" target="_blank" rel="noopener">📎 {item["source"]}</a>'
        link_btn    = f'<a class="read-btn" href="{item["link"]}" target="_blank" rel="noopener">元記事 →</a>'
    else:
        source_html = f'<span class="card-source">{item["source"]}</span>'
        link_btn    = ""

    author_html = ""
    if item.get("author_comment"):
        author_html = (
            f'<div class="author-comment">'
            f'<div class="author-comment-head">💬 管理人の視点</div>'
            f'<p class="author-comment-text">{item["author_comment"]}</p>'
            f'</div>'
        )

    fb = render_fb_share(item.get("link", ""))

    return f"""<div class="arc-card">
  <div class="card-meta">{theory_badge}{tags_html}</div>
  <h3 class="card-headline">{item["headline"]}</h3>
  <p class="card-summary">{summary_text}</p>
  {author_html}
  <div class="card-foot">
    {source_html}
    <div class="card-foot-right">{link_btn}{fb}</div>
  </div>
</div>"""


def format_date_ja(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        return datetime.fromisoformat(date_str).strftime("%-m月%-d日")
    except Exception:
        return date_str

# ── T4: SNS 投稿文生成 ────────────────────────────────────────
def generate_post_queue(items: list[dict], today_str: str) -> str:
    today_items = [i for i in items if i["date"] == today_str]
    if not today_items:
        return "# 📭 本日の新着なし\n"

    now_ja = datetime.now(JST).strftime("%Y年%-m月%-d日")
    lines  = [f"# はるねこちゃん SNS投稿キュー — {now_ja}\n"]

    for i, item in enumerate(today_items, 1):
        theory  = item["theory"] or "未分類"
        tags_x  = " ".join(f"#{t.replace('・','').replace('（','').replace('）','')}" for t in item["tags"])
        secs    = parse_summary_sections(item["summary"])
        point   = (secs["insights"] or secs["analysis"] or secs["plain"] or "")[:60]
        if point and not point.endswith(("。", "…")):
            point = point.rstrip("、") + "…"
        link    = item["link"] or SITE_URL

        # X (旧Twitter) — 140字以内
        x_text = (
            f"【{theory}】{item['headline']}\n\n"
            f"{point}\n\n"
            f"{link}\n"
            f"#人事 #経営理論 #HRM {tags_x}"
        )

        # LinkedIn — 500字程度
        li_full = (
            (secs["facts"][:100] + "…\n\n" if secs["facts"] else "")
            + (secs["insights"] or secs["analysis"] or "")[:200]
        )
        li_text = (
            f"📰 {item['headline']}\n\n"
            f"{li_full}\n\n"
            f"▶ 経営理論で読む：{theory}\n"
            f"記事全文 → {link}\n\n"
            f"#経営理論 #人事 #HRマネジメント #組織開発 #{theory.replace('（','').replace('）','').replace('・','')}"
        )

        lines.append(f"## 記事{i}：{item['headline']}\n")
        lines.append("### X（旧Twitter）用\n```")
        lines.append(x_text)
        lines.append("```\n")
        lines.append("### LinkedIn用\n```")
        lines.append(li_text)
        lines.append("```\n")
        lines.append("---\n")

    return "\n".join(lines)

# ── T2: 理論用語集ページ生成 ──────────────────────────────────
THEORY_PAGE_CSS = """
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:#FAF7F2;color:#2B2620;font-family:'Noto Sans JP',sans-serif;line-height:1.75}
nav{background:rgba(255,255,255,.95);border-bottom:1px solid #E5DFD4;padding:0 32px;height:58px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:100}
.nav-logo{display:flex;align-items:center;gap:8px;text-decoration:none;color:#2B2620;font-weight:700;font-size:1rem}
.back-link{font-size:.8rem;color:#6B8F71;text-decoration:none;margin-left:auto}
.back-link:hover{text-decoration:underline}
.hero{background:#fff;border-bottom:1px solid #E5DFD4;padding:48px 40px 36px}
.hero-inner{max-width:820px;margin:0 auto}
.hero-cat{font-size:.7rem;font-weight:700;color:#4F6E55;letter-spacing:.14em;text-transform:uppercase;margin-bottom:12px}
h1{font-size:clamp(1.8rem,4vw,2.8rem);font-weight:800;line-height:1.2;margin-bottom:12px}
.hero-proposer{font-size:.82rem;color:#A89F96;margin-bottom:20px}
.hero-desc{font-size:.95rem;color:#6B645C;line-height:1.9;max-width:680px;padding:20px 24px;background:#EEF4EF;border-left:4px solid #6B8F71;border-radius:0 12px 12px 0}
.wrap{max-width:820px;margin:0 auto;padding:48px 40px 80px}
.section-title{font-size:1rem;font-weight:700;color:#2B2620;border-bottom:2px solid #E5DFD4;padding-bottom:8px;margin:36px 0 16px}
.article-item{background:#fff;border:1.5px solid #E5DFD4;border-left:4px solid #6B8F71;border-radius:12px;padding:16px 20px;margin-bottom:12px;transition:box-shadow .15s}
.article-item:hover{box-shadow:0 4px 16px rgba(43,38,32,.08)}
.article-item a{text-decoration:none;color:inherit}
.article-headline{font-size:.95rem;font-weight:700;margin-bottom:6px;color:#2B2620}
.article-meta{font-size:.72rem;color:#A89F96}
.empty-msg{font-size:.87rem;color:#A89F96;padding:20px 0}
.theory-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.theory-card{background:#fff;border:1px solid #E5DFD4;border-radius:10px;padding:14px 16px;text-decoration:none;color:#2B2620;transition:all .15s;font-size:.84rem}
.theory-card:hover{border-color:#D4E6D7;background:#EEF4EF;transform:translateY(-1px)}
.theory-card-name{font-weight:700;margin-bottom:4px}
.theory-card-proposer{font-size:.7rem;color:#A89F96}
footer{background:#1A1410;color:rgba(255,255,255,.45);padding:24px 40px;text-align:center;font-size:.75rem}
@media(max-width:600px){.hero,.wrap,footer{padding-left:20px;padding-right:20px}}
</style>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;800&display=swap" rel="stylesheet">
"""


def generate_theory_pages(items: list[dict]) -> None:
    # 全理論ページ
    for theory, slug in THEORY_SLUGS.items():
        if slug == "others":
            continue
        desc     = THEORY_DESCRIPTIONS.get(theory, "")
        proposer = THEORY_PROPOSERS.get(theory, "")
        related  = [i for i in items if i["theory"] == theory]
        related_html = ""
        if related:
            for item in related[:10]:
                link_open  = f'<a href="{item["link"]}" target="_blank" rel="noopener">' if item["link"] else "<span>"
                link_close = "</a>" if item["link"] else "</span>"
                related_html += (
                    f'<div class="article-item">{link_open}'
                    f'<div class="article-headline">{item["headline"]}</div>'
                    f'<div class="article-meta">{format_date_ja(item["date"])} ／ {item["source"]}</div>'
                    f'{link_close}</div>\n'
                )
        else:
            related_html = '<p class="empty-msg">まだこの理論で解説した記事がありません。</p>'

        # 他の理論一覧
        others_html = ""
        for t2, s2 in THEORY_SLUGS.items():
            if s2 == "others" or t2 == theory:
                continue
            others_html += (
                f'<a class="theory-card" href="../{s2}/">'
                f'<div class="theory-card-name">{t2}</div>'
                f'<div class="theory-card-proposer">{THEORY_PROPOSERS.get(t2,"")}</div>'
                f'</a>\n'
            )

        html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{theory} | 経営理論用語集 | はるねこちゃん</title>
<meta name="description" content="{theory}とは？{desc[:80]}…">
<meta property="og:title" content="{theory} | 経営理論用語集">
<meta property="og:description" content="{desc[:120]}">
<meta property="og:url" content="{SITE_URL}theories/{slug}/">
<link rel="canonical" href="{SITE_URL}theories/{slug}/">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"DefinedTerm","name":"{theory}","description":"{desc}","inDefinedTermSet":{{"@type":"DefinedTermSet","name":"世界標準の経営理論","author":{{"@type":"Person","name":"入山章栄"}}}}}}
</script>
{THEORY_PAGE_CSS}
</head>
<body>
<nav>
  <a class="nav-logo" href="../../">🐱 はるねこちゃん</a>
  <a class="back-link" href="../../">← トップに戻る</a>
</nav>
<div class="hero">
  <div class="hero-inner">
    <p class="hero-cat">経営理論用語集 — THEORY GLOSSARY</p>
    <h1>{theory}</h1>
    <p class="hero-proposer">提唱者：{proposer}</p>
    <p class="hero-desc">{desc}</p>
  </div>
</div>
<div class="wrap">
  <div class="section-title">📰 この理論で読み解いた記事（{len(related)}件）</div>
  {related_html}
  <div class="section-title">📚 他の経営理論を見る</div>
  <div class="theory-grid">{others_html}</div>
</div>
<footer>© 2025 はるねこちゃん — 入山章栄『世界標準の経営理論』をベースに解説</footer>
</body>
</html>"""

        out_dir = Path("theories") / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(html, encoding="utf-8")

    # 理論一覧インデックス
    index_cards = ""
    for theory, slug in THEORY_SLUGS.items():
        if slug == "others":
            continue
        cnt = sum(1 for i in items if i["theory"] == theory)
        index_cards += (
            f'<a class="theory-card" href="{slug}/">'
            f'<div class="theory-card-name">{theory}</div>'
            f'<div class="theory-card-proposer">{THEORY_PROPOSERS.get(theory,"")} — {cnt}件</div>'
            f'</a>\n'
        )

    index_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>経営理論用語集（全25理論）| はるねこちゃん</title>
<meta name="description" content="入山章栄『世界標準の経営理論』掲載の全25理論を解説。人事・経営ニュースと紐づけてわかりやすく解説します。">
{THEORY_PAGE_CSS}
</head>
<body>
<nav>
  <a class="nav-logo" href="../">🐱 はるねこちゃん</a>
  <a class="back-link" href="../">← トップに戻る</a>
</nav>
<div class="hero">
  <div class="hero-inner">
    <p class="hero-cat">THEORY GLOSSARY</p>
    <h1>経営理論用語集</h1>
    <p class="hero-proposer">入山章栄『世界標準の経営理論』掲載 — 全25理論</p>
    <p class="hero-desc">人事・経営ニュースを深く読み解くための理論フレームワーク集。各理論をクリックすると詳細解説と関連記事が読めます。</p>
  </div>
</div>
<div class="wrap">
  <div class="section-title">全理論一覧</div>
  <div class="theory-grid">{index_cards}</div>
</div>
<footer>© 2025 はるねこちゃん — 入山章栄『世界標準の経営理論』をベースに解説</footer>
</body>
</html>"""

    Path("theories").mkdir(exist_ok=True)
    (Path("theories") / "index.html").write_text(index_html, encoding="utf-8")
    print(f"✅ 理論用語集ページ生成完了（{len(THEORY_SLUGS)-1}理論）")


# ── T1: OGP画像生成 ───────────────────────────────────────────
def generate_og_images(items: list[dict], today_str: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("⚠️  Pillow未インストール — OGP生成スキップ")
        return

    Path("assets/og").mkdir(parents=True, exist_ok=True)

    # フォント（GitHub Actions: Noto CJK, ローカル: フォールバック）
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJKjp-Bold.otf",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    font_path = next((p for p in font_paths if Path(p).exists()), None)

    def make_font(size: int):
        try:
            return ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        except Exception:
            return ImageFont.load_default()

    def wrap_text(text: str, font, max_width: int, draw) -> list[str]:
        lines, cur = [], ""
        for ch in text:
            test = cur + ch
            w = draw.textlength(test, font=font)
            if w > max_width:
                lines.append(cur)
                cur = ch
            else:
                cur = test
        if cur:
            lines.append(cur)
        return lines

    GREEN     = (107, 143, 113)
    GREEN_DK  = (79,  110,  85)
    BG        = (250, 247, 242)
    TEXT      = (43,   38,  32)
    TEXT_LIGHT= (168, 159, 150)
    WHITE     = (255, 255, 255)
    ROSE      = (232, 160, 180)

    def draw_og(headline: str, theory: str, date_label: str, out_path: str) -> None:
        W, H = 1200, 630
        img  = Image.new("RGB", (W, H), BG)
        d    = ImageDraw.Draw(img)

        # ヘッダーバー
        d.rectangle([(0, 0), (W, 120)], fill=GREEN)
        f_site = make_font(36)
        d.text((48, 42), "はるねこちゃん — 人事・経営ニュース × 経営理論", font=f_site, fill=WHITE)

        # 理論バッジ
        f_theory = make_font(32)
        badge_w  = d.textlength(f"📚 {theory}", font=f_theory) + 40
        d.rounded_rectangle([(48, 150), (48 + badge_w, 200)], radius=24, fill=GREEN_DK)
        d.text((68, 160), f"📚 {theory}", font=f_theory, fill=WHITE)

        # 見出し
        f_head = make_font(52)
        lines  = wrap_text(headline, f_head, W - 96, d)
        y = 230
        for line in lines[:3]:
            d.text((48, y), line, font=f_head, fill=TEXT)
            y += 66

        # 区切り線
        d.rectangle([(48, 500), (W - 48, 503)], fill=(229, 223, 212))

        # 日付 & URL
        f_sub = make_font(28)
        d.text((48, 522), date_label, font=f_sub, fill=TEXT_LIGHT)
        d.text((48, 560), SITE_URL, font=f_sub, fill=GREEN)

        # ロゴ猫（右下）
        cat_x, cat_y = W - 200, H - 180
        d.ellipse([(cat_x, cat_y), (cat_x+120, cat_y+120)], fill=WHITE, outline=(59,30,8), width=4)
        d.ellipse([(cat_x+20, cat_y+30), (cat_x+56, cat_y+72)], fill=(59,30,8))
        d.ellipse([(cat_x+64, cat_y+30), (cat_x+100, cat_y+72)], fill=(59,30,8))
        d.ellipse([(cat_x+50, cat_y+76), (cat_x+70, cat_y+92)], fill=(59,30,8))
        d.ellipse([(cat_x+6,  cat_y+68), (cat_x+30, cat_y+84)], fill=ROSE)
        d.ellipse([(cat_x+90, cat_y+68), (cat_x+114, cat_y+84)], fill=ROSE)

        img.save(out_path, "PNG", optimize=True)

    # 今日のOGP
    today_items = [i for i in items if i["date"] == today_str]
    if today_items:
        date_label = format_date_ja(today_str)
        draw_og(today_items[0]["headline"], today_items[0]["theory"] or "未分類",
                f"{date_label}のニュース", "assets/og/today.png")
        print("✅ OGP today.png 生成")

    # 理論ページOGP
    for theory, slug in THEORY_SLUGS.items():
        if slug == "others":
            continue
        draw_og(f"{theory}とは？", theory, "経営理論用語集", f"assets/og/theory-{slug}.png")
    print("✅ OGP theory-*.png 生成（25理論）")


# ── インサイトHTML (リデザイン版) ──────────────────────────────
def generate_insights_html(items: list[dict], today_str: str) -> str:
    if not items:
        return '<p style="color:var(--text-light);font-size:.9rem;padding:40px 0;">まだデータが蓄積されていません。</p>'

    now       = datetime.now(JST)
    week_ago  = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    total          = len(items)
    recent_7       = sum(1 for i in items if i["date"] >= week_ago)
    theory_types   = len(set(i["theory"] for i in items if i["theory"]))

    # ── 統計カード ──
    stats_html = f"""<div class="ins-stats-row">
  <div class="ins-stat-card">
    <div class="ins-stat-num">{total}<small>件</small></div>
    <div class="ins-stat-label">Total Articles</div>
    <div class="ins-stat-sub">累計収集・分析済み記事</div>
  </div>
  <div class="ins-stat-card">
    <div class="ins-stat-num">{recent_7}<small>件</small></div>
    <div class="ins-stat-label">This Week</div>
    <div class="ins-stat-sub">直近7日間の新着</div>
  </div>
  <div class="ins-stat-card">
    <div class="ins-stat-num">{theory_types}<small>理論</small></div>
    <div class="ins-stat-label">Theories Applied</div>
    <div class="ins-stat-sub">使用中の経営理論数</div>
  </div>
</div>"""

    # ── 理論ランキング ──
    theory_counter: Counter = Counter(
        i["theory"] for i in items if i["theory"] and i["theory"] != "未分類"
    )
    max_cnt = max(theory_counter.values(), default=1)
    top8    = theory_counter.most_common(8)
    rank_html = ""
    for idx, (theory, cnt) in enumerate(top8, 1):
        slug     = THEORY_SLUGS.get(theory, "")
        url      = f"theories/{slug}/" if slug and slug != "others" else ""
        name_tag = f'<a href="{url}">{theory}</a>' if url else theory
        cls      = {1: "r1", 2: "r2", 3: "r3"}.get(idx, "")
        bar_w    = int(cnt / max_cnt * 100)
        rank_html += f"""<div class="ins-rank-item">
  <div class="ins-rank-num {cls}">{idx}</div>
  <div class="ins-rank-content">
    <div class="ins-rank-theory">{name_tag}</div>
    <div class="ins-rank-bar-bg"><div class="ins-rank-bar" style="width:{bar_w}%"></div></div>
  </div>
  <div class="ins-rank-cnt">{cnt}件</div>
</div>"""

    # 最頻出理論ボックス
    top_theory   = top8[0][0] if top8 else ""
    top_slug     = THEORY_SLUGS.get(top_theory, "")
    top_desc     = THEORY_DESCRIPTIONS.get(top_theory, "")
    feat_box_link = f'<a class="ins-feat-box-link" href="theories/{top_slug}/">→ 理論の詳細を見る</a>' if top_slug and top_slug != "others" else ""
    feat_box = f"""<div class="ins-feat-box">
  <div class="ins-feat-box-label">🏆 最頻出理論</div>
  <div class="ins-feat-box-name">{top_theory}</div>
  <div class="ins-feat-box-desc">{top_desc[:100]}…</div>
  {feat_box_link}
</div>""" if top_theory else ""

    # ── キーワードクラウド ──
    tag_counter: Counter = Counter()
    for i in items:
        tag_counter.update(i["tags"])
    max_tag = max(tag_counter.values(), default=1)
    kw_html = ""
    for tag, cnt in tag_counter.most_common(14):
        ratio = cnt / max_tag
        sz    = "sz3" if ratio >= .65 else ("sz2" if ratio >= .35 else "sz1")
        kw_html += f'<span class="ins-kw {sz}">{tag}</span>'

    # ── 週次カード ──
    fb_url = urllib.parse.quote(f"{SITE_URL}#insights")
    weekly_html = f"""<div class="ins-weekly-card">
  <div class="ins-weekly-label">This Week's Volume</div>
  <div class="ins-weekly-num">{recent_7}</div>
  <div class="ins-weekly-sub">件のニュースを自動収集・解説</div>
  <div class="ins-weekly-share">
    <a href="https://www.facebook.com/sharer/sharer.php?u={fb_url}" target="_blank" rel="noopener">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/></svg>
      レポートをシェア
    </a>
  </div>
</div>"""

    main_grid = f"""<div class="ins-main-grid">
  <div class="ins-panel">
    <div class="ins-panel-title">📊 経営理論ランキング</div>
    <div class="ins-rank-list">{rank_html}</div>
    {feat_box}
  </div>
  <div>
    <div class="ins-panel">
      <div class="ins-panel-title">🏷 注目キーワード</div>
      <div class="ins-kw-cloud">{kw_html}</div>
    </div>
    {weekly_html}
  </div>
</div>"""

    # ── フィーチャード記事 ──
    rich_items = [i for i in items if "【考察】" in i["summary"] or "【示唆】" in i["summary"]]
    feature_html = ""
    if rich_items:
        feat     = rich_items[0]
        secs     = parse_summary_sections(feat["summary"])
        facts_txt = (secs["facts"] or secs["plain"] or "")[:160]
        ins_txt  = (secs["insights"] or secs["analysis"] or "")[:180]
        theory   = feat["theory"] or "未分類"
        date_ja  = format_date_ja(feat["date"])
        link_a   = f'href="{feat["link"]}" target="_blank" rel="noopener"' if feat["link"] else 'href="javascript:void(0)"'
        cat_svg  = """<svg viewBox="0 0 200 220" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:140px;opacity:.9">
  <path d="M65 136 Q100 154 135 136 L130 200 Q100 212 70 200Z" fill="white" stroke="#3B1E08" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M72 143 Q50 166 54 186" stroke="#3B1E08" stroke-width="12" stroke-linecap="round" fill="none"/>
  <path d="M128 142 Q152 116 154 92" stroke="#3B1E08" stroke-width="12" stroke-linecap="round" fill="none"/>
  <ellipse cx="82" cy="210" rx="18" ry="11" fill="white" stroke="#3B1E08" stroke-width="3"/>
  <ellipse cx="118" cy="210" rx="18" ry="11" fill="white" stroke="#3B1E08" stroke-width="3"/>
  <path d="M44 58 Q50 8 86 28 Q80 52 60 62Z" fill="white" stroke="#3B1E08" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M49 56 Q55 16 84 30 Q78 50 63 58Z" fill="#F9C5D0"/>
  <path d="M156 58 Q150 8 114 28 Q120 52 140 62Z" fill="white" stroke="#3B1E08" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M151 56 Q145 16 116 30 Q122 50 137 58Z" fill="#F9C5D0"/>
  <circle cx="100" cy="80" r="60" fill="white" stroke="#3B1E08" stroke-width="4"/>
  <ellipse cx="100" cy="86" rx="5" ry="3.5" fill="#3B1E08"/>
  <ellipse cx="68" cy="92" rx="14" ry="8" fill="#F4A0B4" opacity=".45"/>
  <ellipse cx="132" cy="92" rx="14" ry="8" fill="#F4A0B4" opacity=".45"/>
  <path d="M88 96 Q94 102 100 98 Q106 102 112 96" stroke="#3B1E08" stroke-width="2.5" stroke-linecap="round" fill="none"/>
</svg>"""
        feature_html = f"""<div class="ins-section-label">Featured Article — 今週の注目記事</div>
<div class="ins-feature-card">
  <div>
    <div class="ins-feature-theory">{render_theory_badge(theory)}</div>
    <h3 class="ins-feature-headline">{feat["headline"]}</h3>
    <p class="ins-feature-facts">{facts_txt}…</p>
    <div class="ins-feature-insight">
      <div class="ins-feature-insight-label">💡 示唆</div>
      <p class="ins-feature-insight-text">{ins_txt}…</p>
    </div>
    <div class="ins-feature-actions">
      <a class="ins-feature-btn" {link_a}>記事を読む →</a>
      <span class="ins-feature-date">📅 {date_ja} ／ {feat["source"]}</span>
    </div>
  </div>
  <div class="ins-feature-right">{cat_svg}</div>
</div>"""

    # ── 深掘り3記事グリッド ──
    deep_pool = (rich_items[1:] if len(rich_items) > 1 else [])
    if len(deep_pool) < 3:
        others    = [i for i in items if i not in rich_items]
        deep_pool = (deep_pool + others)[:3]
    deep_cards = ""
    for item in deep_pool[:3]:
        secs    = parse_summary_sections(item["summary"])
        excerpt = (secs["insights"] or secs["analysis"] or secs["plain"] or "")[:90]
        theory  = item["theory"] or "未分類"
        date_ja = format_date_ja(item["date"])
        deep_cards += f"""<div class="ins-deep-card">
  <div>{render_theory_badge(theory)}</div>
  <div class="ins-deep-headline">{item["headline"]}</div>
  <div class="ins-deep-excerpt">{excerpt}…</div>
  <div class="ins-deep-foot">📅 {date_ja} ／ {item["source"]}</div>
</div>"""
    deep_html = f"""<div class="ins-section-label">深掘り記事ピックアップ</div>
<div class="ins-deep-grid">{deep_cards}</div>""" if deep_cards else ""

    # ── 理論CTA ──
    theory_cta = f"""<div class="ins-theory-cta">
  <div class="ins-theory-cta-title">📚 全25の経営理論を学ぶ</div>
  <div class="ins-theory-cta-sub">入山章栄『世界標準の経営理論』掲載の全理論を実際のニュースと紐づけて解説。<br>理論別に記事を探すこともできます。</div>
  <a class="ins-cta-btn" href="theories/">全理論の用語集を見る →</a>
</div>"""

    # ── シェアバナー ──
    mail_body  = urllib.parse.quote(f"はるねこちゃんの週次インサイトレポートが面白いです。\n{SITE_URL}#insights")
    share_html = f"""<div class="ins-share-banner">
  <div>
    <div class="ins-share-title">📣 このレポートをシェアする</div>
    <div class="ins-share-sub">毎週更新。気になった方にぜひシェアを。</div>
  </div>
  <div class="ins-share-btns">
    <a class="ins-share-fb" href="https://www.facebook.com/sharer/sharer.php?u={fb_url}" target="_blank" rel="noopener">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 00-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 011-1h3z"/></svg>
      Facebookでシェア
    </a>
    <a class="ins-share-mail" href="mailto:?subject=はるねこちゃん 今週の人事・経営インサイト&body={mail_body}">
      📩 メールで紹介
    </a>
  </div>
</div>"""

    return stats_html + main_grid + feature_html + deep_html + theory_cta + share_html



# ── ブログ: Notion取得 & パース ────────────────────────────────
def fetch_all_blog_posts() -> list[dict]:
    payload = {
        "filter": {"property": "公開", "checkbox": {"equals": True}},
        "sorts": [{"property": "公開日", "direction": "descending"}],
        "page_size": 100,
    }
    return notion_request(f"databases/{BLOG_DATABASE_ID}/query", payload).get("results", [])


def blog_page_to_item(page: dict) -> dict:
    props = page.get("properties", {})
    return {
        "title":    extract_text(props.get("タイトル", {})),
        "lead":     extract_text(props.get("リード文", {})),
        "body":     extract_text(props.get("本文", {})),
        "category": extract_text(props.get("カテゴリ", {})),
        "tags":     extract_text(props.get("タグ", {})) or [],
        "date":     extract_text(props.get("公開日", {})),
        "slug":     extract_text(props.get("スラッグ", {})),
    }


BLOG_CSS = """<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:#FAF7F2;color:#2B2620;font-family:'Noto Sans JP',sans-serif;line-height:1.75;min-height:100vh}
nav{background:rgba(255,255,255,.95);backdrop-filter:blur(14px);border-bottom:1px solid #E5DFD4;height:56px;padding:0 28px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:400}
.nav-logo{display:flex;align-items:center;gap:8px;text-decoration:none;color:#2B2620;font-weight:700;font-size:1rem}
.nav-logo img{width:28px;height:28px}
.nav-back{font-size:.8rem;color:#6B8F71;text-decoration:none;margin-left:auto;font-weight:700}
.nav-back:hover{color:#4F6E55}
.hero{background:#fff;border-bottom:1px solid #E5DFD4;padding:52px 28px 40px}
.hero-inner{max-width:860px;margin:0 auto}
.hero-kicker{font-size:.68rem;font-weight:700;color:#4F6E55;letter-spacing:.15em;text-transform:uppercase;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.hero-kicker::before{content:'';width:16px;height:2px;background:#6B8F71;display:block}
h1{font-size:clamp(1.7rem,4vw,2.6rem);font-weight:800;line-height:1.25;margin-bottom:14px;font-family:serif}
.hero-lead{font-size:.9rem;color:#6B645C;line-height:1.85;max-width:580px}
.container{max-width:860px;margin:0 auto;padding:48px 28px 80px}
.blog-list{display:flex;flex-direction:column;gap:24px}
.blog-card{background:#fff;border:1.5px solid #E5DFD4;border-top:4px solid #6B8F71;border-radius:16px;padding:26px 28px 20px;box-shadow:0 4px 18px rgba(43,38,32,.06);transition:box-shadow .2s,transform .2s;text-decoration:none;color:inherit;display:block}
.blog-card:hover{box-shadow:0 10px 36px rgba(43,38,32,.12);transform:translateY(-2px)}
.blog-card-meta{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.cat-badge{font-size:.62rem;font-weight:700;padding:3px 10px;border-radius:20px;background:#6B8F71;color:#fff;letter-spacing:.04em}
.date-badge{font-size:.66rem;color:#A89F96;font-weight:500}
.tag-badge{font-size:.62rem;padding:3px 10px;border-radius:6px;background:#FAF7F2;border:1px solid #E5DFD4;color:#A89F96}
.blog-card-title{font-size:1.15rem;font-weight:800;line-height:1.5;margin-bottom:10px;font-family:serif;color:#2B2620}
.blog-card-lead{font-size:.86rem;color:#6B645C;line-height:1.8;margin-bottom:14px}
.read-more{font-size:.76rem;font-weight:700;color:#4F6E55;display:inline-flex;align-items:center;gap:4px}
.read-more::after{content:'→'}
/* Single post */
.post-hero{background:#fff;border-bottom:1px solid #E5DFD4;padding:52px 28px 40px}
.post-hero-inner{max-width:740px;margin:0 auto}
.post-hero .cat-badge{display:inline-block;margin-bottom:14px}
.post-hero h1{font-size:clamp(1.6rem,4vw,2.4rem);font-weight:800;line-height:1.3;margin-bottom:16px;font-family:serif}
.post-hero-lead{font-size:.95rem;color:#6B645C;line-height:1.85;padding:18px 22px;background:#EEF4EF;border-left:3px solid #6B8F71;border-radius:0 10px 10px 0}
.post-meta{margin-top:16px;font-size:.72rem;color:#A89F96;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.post-body{max-width:740px;margin:0 auto;padding:48px 28px 80px}
.post-body p{font-size:.93rem;line-height:1.95;color:#2B2620;margin-bottom:1.4em}
.post-body h2{font-family:serif;font-size:1.2rem;font-weight:800;color:#2B2620;margin:2em 0 .8em;padding-bottom:.4em;border-bottom:2px solid #E5DFD4}
.post-body h3{font-family:serif;font-size:1rem;font-weight:700;color:#2B2620;margin:1.5em 0 .6em}
.back-btn{display:inline-flex;align-items:center;gap:8px;font-size:.84rem;font-weight:700;color:#4F6E55;background:#EEF4EF;border:1px solid #D4E6D7;padding:10px 22px;border-radius:24px;text-decoration:none;margin-top:32px;transition:background .15s}
.back-btn:hover{background:#D4E6D7}
.empty-state{text-align:center;padding:60px 24px;color:#A89F96;font-size:.9rem}
footer{background:#1A1410;color:rgba(255,255,255,.45);padding:24px 28px;text-align:center;font-size:.75rem}
@media(max-width:600px){
  nav{padding:0 14px;height:52px}
  .hero,.post-hero{padding:36px 16px 28px}
  .container,.post-body{padding:28px 16px 60px}
  .blog-card{padding:18px 16px 14px}
  .blog-card-title{font-size:1rem}
}
</style>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;800&display=swap" rel="stylesheet">"""


def _body_to_html(body: str) -> str:
    if not body:
        return ""
    html_parts = []
    for block in body.replace("\r", "").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("## "):
            html_parts.append(f"<h2>{block[3:].strip()}</h2>")
        elif block.startswith("# "):
            html_parts.append(f"<h2>{block[2:].strip()}</h2>")
        elif block.startswith("### "):
            html_parts.append(f"<h3>{block[4:].strip()}</h3>")
        else:
            inner = block.replace("\n", "<br>")
            html_parts.append(f"<p>{inner}</p>")
    return "\n".join(html_parts)


def generate_blog_pages(posts: list[dict]) -> None:
    Path("blog/posts").mkdir(parents=True, exist_ok=True)

    # ── 個別記事ページ ──────────────────────────────
    for post in posts:
        slug = post["slug"] or re.sub(r"[^\w\-]", "-", post["title"])[:40]
        if not slug:
            continue
        body_html = _body_to_html(post["body"])
        tags_html = "".join(f'<span class="tag-badge">{t}</span>' for t in post["tags"])
        cat_html  = f'<span class="cat-badge">{post["category"]}</span>' if post["category"] else ""
        date_ja   = format_date_ja(post["date"])

        post_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{post["title"]} | はるねこちゃんブログ</title>
<meta name="description" content="{post['lead'][:120]}">
<meta property="og:title" content="{post['title']}">
<meta property="og:description" content="{post['lead'][:120]}">
<meta property="og:url" content="{SITE_URL}blog/posts/{slug}/">
<link rel="icon" href="../../../favicon.svg" type="image/svg+xml">
{BLOG_CSS}
</head>
<body>
<nav>
  <a class="nav-logo" href="../../../"><img src="../../../favicon.svg" alt="">はるねこちゃん</a>
  <a class="nav-back" href="../../">← ブログ一覧</a>
</nav>
<div class="post-hero">
  <div class="post-hero-inner">
    {cat_html}
    <h1>{post["title"]}</h1>
    <p class="post-hero-lead">{post["lead"]}</p>
    <div class="post-meta">
      <span>📅 {date_ja}</span>
      {tags_html}
    </div>
  </div>
</div>
<div class="post-body">
  {body_html}
  <a class="back-btn" href="../../">← ブログ一覧に戻る</a>
</div>
<footer>© 2025 はるねこちゃん — 人事・経営ニュース × 経営理論</footer>
</body>
</html>"""
        out_dir = Path("blog/posts") / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(post_html, encoding="utf-8")

    # ── ブログ一覧ページ ────────────────────────────
    cards_html = ""
    for post in posts:
        slug = post["slug"] or re.sub(r"[^\w\-]", "-", post["title"])[:40]
        if not slug:
            continue
        tags_html = "".join(f'<span class="tag-badge">{t}</span>' for t in post["tags"])
        cat_html  = f'<span class="cat-badge">{post["category"]}</span>' if post["category"] else ""
        date_ja   = format_date_ja(post["date"])
        cards_html += f"""<a class="blog-card" href="posts/{slug}/">
  <div class="blog-card-meta">{cat_html}<span class="date-badge">📅 {date_ja}</span>{tags_html}</div>
  <div class="blog-card-title">{post["title"]}</div>
  <div class="blog-card-lead">{post["lead"]}</div>
  <span class="read-more">続きを読む</span>
</a>\n"""

    if not cards_html:
        cards_html = '<div class="empty-state">まだブログ記事がありません。<br>近日公開予定です。</div>'

    index_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>はるねこちゃんの独り言 | はるねこちゃん</title>
<meta name="description" content="人事・組織・経営に関するコラム。経営理論を実務に接続するHRプロフェッショナルの視点でお届けします。">
<meta property="og:title" content="はるねこちゃんの独り言 | はるねこちゃん">
<meta property="og:url" content="{SITE_URL}blog/">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
{BLOG_CSS}
</head>
<body>
<nav>
  <a class="nav-logo" href="../"><img src="../favicon.svg" alt="">はるねこちゃん</a>
  <a class="nav-back" href="../">← トップへ</a>
</nav>
<div class="hero">
  <div class="hero-inner">
    <p class="hero-kicker">Blog — HR &amp; Management Column</p>
    <h1>はるねこちゃんの独り言</h1>
    <p class="hero-lead">人事・組織・経営に関するコラム。ニュース解説とは別に、実務で感じたことや経営理論の実践的な使い方を書いています。</p>
  </div>
</div>
<div class="container">
  <div class="blog-list">
    {cards_html}
  </div>
</div>
<footer>© 2025 はるねこちゃん — 人事・経営ニュース × 経営理論</footer>
</body>
</html>"""

    (Path("blog") / "index.html").write_text(index_html, encoding="utf-8")
    print(f"✅ ブログページ生成完了（{len(posts)}件）")


# ── メイン ────────────────────────────────────────────────────
def main():
    pages = fetch_all_news()
    items = [page_to_item(p) for p in pages]

    now        = datetime.now(JST)
    today_str  = now.strftime("%Y-%m-%d")
    date_label = now.strftime("%-m月%-d日")

    today_items   = [i for i in items if i["date"] == today_str]
    archive_items = [i for i in items if i["date"] != today_str]

    # ─ 今日のカード
    if today_items:
        today_cards_html = "\n".join(render_card(i, n+1, True) for n, i in enumerate(today_items))
    else:
        today_cards_html = """<div class="empty">
  <p style="margin-top:12px;">今日のニュースはまだ届いていません。<br>毎朝6時に自動収集します。</p>
</div>"""

    # ─ アーカイブ
    by_date: defaultdict = defaultdict(list)
    for item in archive_items:
        by_date[item["date"]].append(item)
    archive_html = ""
    card_num = 1
    for ds in sorted(by_date.keys(), reverse=True):
        archive_html += f'<div class="archive-group"><div class="archive-group-head">{format_date_ja(ds)}のニュース</div>\n'
        for item in by_date[ds]:
            archive_html += render_archive_card(item, card_num) + "\n"
            card_num += 1
        archive_html += "</div>\n"
    if not archive_html:
        archive_html = '<p style="color:var(--text-light);font-size:.85rem;">アーカイブはまだありません。</p>'

    # ─ タグクラウド
    all_tags: list[str] = []
    for item in items:
        all_tags.extend(item["tags"])
    tag_counts = Counter(all_tags)
    topic_tags_html = "".join(
        f'<span class="topic-pill">{tag}<span class="topic-cnt">{cnt}</span></span>\n'
        for tag, cnt in tag_counts.most_common()
    )

    # ─ サイドバーアーカイブリスト
    archive_list_html = ""
    cur_date = None
    for item in archive_items[:10]:
        if item["date"] != cur_date:
            cur_date = item["date"]
            archive_list_html += f'<div class="arc-date-lbl">{format_date_ja(cur_date)}</div>\n'
        if item["link"]:
            archive_list_html += (
                f'<a class="arc-list-item" href="{item["link"]}" target="_blank" rel="noopener">'
                f'<div class="arc-dot"></div><div class="arc-text">{item["headline"]}</div></a>\n'
            )
        else:
            archive_list_html += (
                f'<div class="arc-list-item"><div class="arc-dot"></div>'
                f'<div class="arc-text">{item["headline"]}</div></div>\n'
            )
    if not archive_list_html:
        archive_list_html = '<p style="color:var(--text-light);font-size:.8rem;">まだありません。</p>'

    # ─ インサイトページ
    insights_html = generate_insights_html(items, today_str)

    # ─ OGP meta (今日のニュースがある場合)
    og_image_tag = ""
    if today_items and Path("assets/og/today.png").exists():
        og_image_tag = f'<meta property="og:image" content="{SITE_URL}assets/og/today.png">'

    # ─ index.html 生成
    template = Path("template.html").read_text(encoding="utf-8")
    html = (template
        .replace("<!-- DATE_LABEL -->",       date_label)
        .replace("<!-- TODAY_COUNT -->",       str(len(today_items)))
        .replace("<!-- TOTAL_COUNT -->",       str(len(items)))
        .replace("<!-- TODAY_CARDS -->",       today_cards_html)
        .replace("<!-- ARCHIVE_HTML -->",      archive_html)
        .replace("<!-- TOPIC_TAGS_HTML -->",   topic_tags_html)
        .replace("<!-- ARCHIVE_LIST_HTML -->", archive_list_html)
        .replace("<!-- INSIGHTS_HTML -->",     insights_html)
        .replace("<!-- OG_IMAGE_TAG -->",      og_image_tag)
    )
    Path("index.html").write_text(html, encoding="utf-8")
    print(f"✅ index.html 生成（今日 {len(today_items)} 件 / 合計 {len(items)} 件）")

    # ─ T4: SNS投稿キュー
    post_queue = generate_post_queue(items, today_str)
    Path("post_queue.md").write_text(post_queue, encoding="utf-8")
    print("✅ post_queue.md 生成")

    # ─ T2: 理論用語集ページ
    generate_theory_pages(items)

    # ─ T1: OGP画像
    generate_og_images(items, today_str)

    # ─ ブログ
    blog_pages = fetch_all_blog_posts()
    blog_posts = [blog_page_to_item(p) for p in blog_pages]
    generate_blog_pages(blog_posts)


if __name__ == "__main__":
    main()
