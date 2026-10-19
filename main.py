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


def build_pdf(items, path):
    from weasyprint import HTML
    today = datetime.date.today().isoformat()
    body = f"<h1>{html.escape(SUBJECT)} - {html.escape(GRADE)}</h1><p class='sub'>{today}</p>"
    for i, (q, _) in enumerate(items, 1):
        body += f"<div class='q'><b>{i}.</b> {fmt(strip_number(q))}</div>"
    body += "<div style='page-break-before:always'></div><h2>پاسخنامه</h2>"
    for i, (_, a) in enumerate(items, 1):
        body += f"<div class='q'><b>{i}.</b> {fmt(a)}</div>"
    doc = f"""<html dir="rtl"><head><meta charset="utf-8"><style>
    @page {{ size: A4; margin: 2cm; }}
    body {{ font-family: 'Vazirmatn','Noto Naskh Arabic','Noto Sans Arabic','DejaVu Sans',sans-serif; font-size: 13px; line-height: 1.9; }}
    h1 {{ text-align:center; margin-bottom:0; }} .sub {{ text-align:center; color:#666; }}
    .q {{ margin: 16px 0; }}
    </style></head><body>{body}</body></html>"""
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
    build_pdf(items, pdf_path)
    with open(pdf_path, "rb") as f:
        tg("sendDocument", data={"chat_id": CHAT_ID, "caption": f"{len(items)} تست امروز ✅"}, files={"document": f})
    save_cursor(end)


if __name__ == "__main__":
    main()
