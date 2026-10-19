import os, json, re, time, datetime, html, requests

# ================== تنظیمات ==================
SUBJECT   = (os.getenv("SUBJECT") or "ریاضی")
GRADE     = (os.getenv("GRADE") or "پایه نهم")
PER_DAY   = 10                      # تعداد سوال در هر روز
QUESTIONS_FILE = "questions.txt"    # فایل سوال‌های خودت
STATE_FILE = "history.json"         # اینجا فقط شماره‌ی سوال بعدی ذخیره می‌شه
MODELS = (os.getenv("MODELS") or "openrouter/free,meta-llama/llama-3.3-70b-instruct:free,openai/gpt-oss-20b:free").split(",")
# ============================================

import local_secrets as _s
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY") or _s.OPENROUTER_API_KEY
BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN") or _s.TELEGRAM_BOT_TOKEN
CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID") or _s.TELEGRAM_CHAT_ID


# ---------- خواندن سوال‌ها ----------
def load_questions():
    """سوال‌ها با یک خط شامل --- از هم جدا می‌شن."""
    raw = open(QUESTIONS_FILE, encoding="utf-8").read()
    blocks = [b.strip() for b in re.split(r"^\s*-{3,}\s*$", raw, flags=re.M)]
    return [b for b in blocks if b]


def load_cursor():
    try:
        data = json.load(open(STATE_FILE, encoding="utf-8"))
        return int(data.get("next", 0)) if isinstance(data, dict) else 0
    except Exception:
        return 0


def save_cursor(n):
    json.dump({"next": n}, open(STATE_FILE, "w", encoding="utf-8"))


# ---------- پاسخ‌دادن با هوش مصنوعی ----------
def ask_model(prompt, n):
    last_err = None
    for model in MODELS:
        for attempt in range(2):
            try:
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                    json={"model": model.strip(), "temperature": 0.1, "max_tokens": 6000,
                          "messages": [{"role": "user", "content": prompt}]},
                    timeout=180,
                )
                if r.status_code != 200:
                    print(f"خطا با {model} (تلاش {attempt+1}): {r.status_code} {r.text[:400]}")
                    last_err = f"{r.status_code} {r.text[:200]}"
                    time.sleep(5)
                    continue
                text = r.json()["choices"][0]["message"]["content"] or ""
                text = re.sub(r"```(?:json)?", "", text)
                data = json.loads(text[text.find("["): text.rfind("]") + 1])
                if len(data) >= n:
                    print("مدل موفق:", model)
                    return data[:n]
                print(f"{model}: تعداد پاسخ کم بود ({len(data)})")
            except Exception as e:
                last_err = e
                print(f"خطا با {model} (تلاش {attempt+1}): {e}")
                time.sleep(5)
    raise RuntimeError(f"هیچ مدلی جواب نداد: {last_err}")


def solve(blocks):
    listing = "\n\n".join(f"[سوال {i}]\n{b}" for i, b in enumerate(blocks, 1))
    prompt = f"""تو یک معلم دقیق برای درس «{SUBJECT}» {GRADE} هستی.
برای هر سوال زیر، گزینه‌ی درست را پیدا کن و حل را کوتاه و آموزنده توضیح بده.
هر سوال را قدم‌به‌قدم و با دقت حل کن و قبل از جواب نهایی دوباره چک کن.
اگر سوال گزینه‌ی درست نداشت یا مبهم بود، همین را در توضیح بنویس.
{listing}

خروجی فقط یک آرایه JSON باشد، بدون هیچ توضیح اضافه، به همین ترتیب سوال‌ها:
[{{"answer": 2, "explanation": "..."}}]
که answer شماره‌ی گزینه‌ی درست است (۱ تا ۴، به ترتیبی که گزینه‌ها در متن سوال آمده‌اند).
فرمول‌ها را با متن ساده بنویس (بدون LaTeX)."""
    return ask_model(prompt, len(blocks))


# ---------- ساخت PDF ----------
def clean_block(b):
    lines = b.splitlines()
    lines[0] = re.sub(r"^\s*[\d۰-۹]+\s*[\.\-\)]\s*", "", lines[0])
    return "\n".join(lines)


def build_pdf(blocks, answers, start, path):
    from weasyprint import HTML
    e = html.escape
    today = datetime.date.today().isoformat()
    body = f"<h1>{e(SUBJECT)} - {e(GRADE)}</h1><p class='sub'>{today}</p>"
    for i, b in enumerate(blocks, 1):
        text = e(clean_block(b)).replace("\n", "<br>")
        body += f"<div class='q'><b>{i}.</b> {text}</div>"
    body += "<div style='page-break-before:always'></div><h2>پاسخنامه</h2>"
    for i, a in enumerate(answers, 1):
        body += f"<p><b>{i}. گزینه {e(str(a.get('answer', '?')))}</b> - {e(str(a.get('explanation', '')))}</p>"
    doc = f"""<html dir="rtl"><head><meta charset="utf-8"><style>
    @page {{ size: A4; margin: 2cm; }}
    body {{ font-family: 'Vazirmatn','Noto Naskh Arabic','Noto Sans Arabic','DejaVu Sans',sans-serif; font-size: 13px; line-height: 1.9; }}
    h1 {{ text-align:center; margin-bottom:0; }} .sub {{ text-align:center; color:#666; }}
    .q {{ margin: 16px 0; }}
    </style></head><body>{body}</body></html>"""
    HTML(string=doc).write_pdf(path)


# ---------- تلگرام ----------
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
    blocks = all_q[cur: cur + PER_DAY]
    end = cur + len(blocks)

    tg("sendMessage", data={"chat_id": CHAT_ID, "text": f"⏰ وقت تست حل کردنه!\nدرس: {SUBJECT}\nسوال‌های {cur+1} تا {end} از {len(all_q)}\nتا چند لحظه دیگه می‌رسن 👇"})
    answers = solve(blocks)
    pdf_path = f"tests-{datetime.date.today().isoformat()}.pdf"
    build_pdf(blocks, answers, cur, pdf_path)
    with open(pdf_path, "rb") as f:
        tg("sendDocument", data={"chat_id": CHAT_ID, "caption": f"{len(blocks)} تست امروز ✅"}, files={"document": f})
    save_cursor(end)


if __name__ == "__main__":
    main()
