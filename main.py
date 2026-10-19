import os, json, re, datetime, html, requests

# ================== تنظیمات ==================
SUBJECT   = (os.getenv("SUBJECT") or "ریاضی")
GRADE     = (os.getenv("GRADE") or "پایه نهم")
PER_DAY   = 10                      # تعداد سوال در هر روز
QUESTIONS_FILE = "questions.txt"    # فایل سوال و جواب‌های خودت
STATE_FILE = "history.json"         # اینجا فقط شماره‌ی سوال بعدی ذخیره می‌شه
# ============================================

import local_secrets as _s
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or _s.TELEGRAM_BOT_TOKEN
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID") or _s.TELEGRAM_CHAT_ID

ANSWER_RE = re.compile(r"^\s*(پاسخ|جواب)\s*[:：]", re.M)


def load_questions():
    """هر سوال با یک خط شامل --- جدا می‌شه. از اولین خطی که با «پاسخ:» شروع بشه، بخش جواب حساب می‌شه."""
    raw = open(QUESTIONS_FILE, encoding="utf-8").read()
    items = []
    for b in re.split(r"^\s*-{3,}\s*$", raw, flags=re.M):
        b = b.strip()
        if not b:
            continue
        m = ANSWER_RE.search(b)
        if m:
            q, a = b[:m.start()].strip(), b[m.start():].strip()
        else:
            q, a = b, "پاسخ برای این سوال ثبت نشده."
        items.append((q, a))
    return items


def load_cursor():
    try:
        data = json.load(open(STATE_FILE, encoding="utf-8"))
        return int(data.get("next", 0)) if isinstance(data, dict) else 0
    except Exception:
        return 0


def save_cursor(n):
    json.dump({"next": n}, open(STATE_FILE, "w", encoding="utf-8"))


def strip_number(text):
    lines = text.splitlines()
    lines[0] = re.sub(r"^\s*[\d۰-۹]+\s*[\.\-\)]\s*", "", lines[0])
    return "\n".join(lines)


def fmt(text):
    return html.escape(text).replace("\n", "<br>")


OPT_RE = re.compile(r"^\s*([1-4۱-۴]|الف|ب|ج|د|[A-Da-d])\s*[\)\-\.]\s*(.*)$")


def parse_question(q):
    """سوال رو به متن سوال و گزینه‌ها تقسیم می‌کنه."""
    stem, opts = [], []
    for line in strip_number(q).splitlines():
        m = OPT_RE.match(line)
        if m:
            opts.append([m.group(1), m.group(2)])
        elif opts:
            opts[-1][1] += " " + line.strip()
        else:
            stem.append(line)
    return "\n".join(stem).strip(), opts


def parse_answer(a):
    lines = [l.strip() for l in a.splitlines() if l.strip()]
    head = re.sub(r"^(پاسخ|جواب)\s*[:：]\s*", "", lines[0]) if lines else ""
    reason = "\n".join(lines[1:])
    reason = re.sub(r"^(دلیل|توضیح)\s*[:：]\s*", "", reason)
    return head, reason


CSS = """
@page {
  size: A4; margin: 1.6cm 1.6cm 2cm 1.6cm;
  @bottom-center { content: "RoboRam  •  " counter(page); font-size: 10px; color: #8b8fb5; }
}
body { font-family: 'Vazirmatn','Noto Naskh Arabic','Noto Sans Arabic','DejaVu Sans',sans-serif;
       font-size: 13px; line-height: 1.9; color: #1f2347; }
.hero { background: linear-gradient(135deg, #4f46e5, #9333ea); color: #fff; border-radius: 18px;
        padding: 22px 26px; margin-bottom: 22px; }
.hero .brand { font-size: 12px; letter-spacing: 4px; opacity: .85; direction: ltr; text-align: left; }
.hero h1 { margin: 4px 0 8px 0; font-size: 28px; }
.hero .meta span { display: inline-block; background: rgba(255,255,255,.22); border-radius: 20px;
                   padding: 2px 14px; margin-left: 8px; font-size: 12px; }
.card { background: #f6f7ff; border: 1px solid #dfe2ff; border-right: 6px solid #6366f1;
        border-radius: 14px; padding: 12px 16px; margin: 0 0 14px 0; page-break-inside: avoid; }
.num { display: inline-block; background: #4f46e5; color: #fff; border-radius: 50%;
       width: 26px; height: 26px; line-height: 26px; text-align: center; font-weight: bold;
       font-size: 12px; margin-left: 8px; }
.stem { font-weight: bold; margin-bottom: 6px; }
.opt { margin: 3px 0; padding: 3px 10px; background: #fff; border: 1px solid #e3e5fb; border-radius: 10px; }
.lbl { display: inline-block; min-width: 20px; text-align: center; color: #fff; background: #9333ea;
       border-radius: 8px; font-size: 11px; padding: 0 5px; margin-left: 8px; }
.ans-title { background: linear-gradient(135deg, #059669, #10b981); color: #fff; border-radius: 18px;
             padding: 14px 26px; font-size: 22px; font-weight: bold; margin-bottom: 18px; }
.acard { background: #f0fdf6; border: 1px solid #c7f0da; border-right: 6px solid #10b981;
         border-radius: 14px; padding: 10px 16px; margin: 0 0 12px 0; page-break-inside: avoid; }
.acard .num { background: #059669; }
.ahead { display: inline-block; background: #10b981; color: #fff; border-radius: 10px; padding: 0 12px; font-weight: bold; }
.reason { margin-top: 4px; color: #2b3a33; }
.wm { position: fixed; top: 40%; left: 0; width: 100%; text-align: center; direction: ltr;
      font-family: 'DejaVu Sans', sans-serif; font-weight: bold; font-size: 115px; letter-spacing: 10px;
      color: rgba(79, 70, 229, 0.08); transform: rotate(-32deg); }
"""


def build_pdf(items, path, start=0, total=0):
    from weasyprint import HTML
    today = datetime.date.today().isoformat()
    e = html.escape
    rng = f"<span>سوال {start+1} تا {start+len(items)} از {total}</span>" if total else ""
    body = (f"<div class='hero'><div class='brand'>ROBORAM</div>"
            f"<h1>{e(SUBJECT)}</h1>"
            f"<div class='meta'><span>{e(GRADE)}</span><span>{today}</span>{rng}</div></div>")
    for i, (q, _) in enumerate(items, 1):
        stem, opts = parse_question(q)
        opts_html = "".join(f"<div class='opt'><span class='lbl'>{e(l)}</span>{e(t)}</div>" for l, t in opts)
        body += f"<div class='card'><div class='stem'><span class='num'>{i}</span>{fmt(stem)}</div>{opts_html}</div>"
    body += "<div style='page-break-before:always'></div><div class='ans-title'>✅ پاسخنامه</div>"
    for i, (_, a) in enumerate(items, 1):
        head, reason = parse_answer(a)
        r = f"<div class='reason'>{fmt(reason)}</div>" if reason else ""
        body += f"<div class='acard'><span class='num'>{i}</span><span class='ahead'>{e(head)}</span>{r}</div>"
    body += "<div class='wm'>RoboRam</div>"
    doc = f"<html dir='rtl'><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    HTML(string=doc).write_pdf(path)


def tg(method, **kw):
    r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", timeout=120, **kw)
    r.raise_for_status()


def find_chat_id():
    r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", timeout=60)
    r.raise_for_status()
    for upd in reversed(r.json().get("result", [])):
        msg = upd.get("message") or upd.get("edited_message")
        if msg:
            return str(msg["chat"]["id"])
    raise RuntimeError("اول توی تلگرام به باتت پیام Start بده، بعد دوباره اجرا کن.")


def main():
    global CHAT_ID
    if not CHAT_ID:
        CHAT_ID = find_chat_id()

    all_q = load_questions()
    if not all_q:
        raise RuntimeError("فایل questions.txt خالیه!")
    cur = load_cursor()
    if cur >= len(all_q):
        tg("sendMessage", data={"chat_id": CHAT_ID, "text": "✅ همه‌ی سوال‌های فایل تموم شد! از اول شروع می‌کنم. وقتشه فایل questions.txt رو با سوال‌های جدید عوض کنی."})
        cur = 0
    items = all_q[cur: cur + PER_DAY]
    end = cur + len(items)

    tg("sendMessage", data={"chat_id": CHAT_ID, "text": f"⏰ وقت تست حل کردنه!\nدرس: {SUBJECT}\nسوال‌های {cur+1} تا {end} از {len(all_q)}\nتا چند لحظه دیگه می‌رسن 👇"})
    pdf_path = f"tests-{datetime.date.today().isoformat()}.pdf"
    build_pdf(items, pdf_path, cur, len(all_q))
    with open(pdf_path, "rb") as f:
        tg("sendDocument", data={"chat_id": CHAT_ID, "caption": f"{len(items)} تست امروز ✅"}, files={"document": f})
    save_cursor(end)


if __name__ == "__main__":
    main()
