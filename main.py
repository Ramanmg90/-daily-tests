import os, json, re, datetime, html, requests

# ================== تنظیمات (اینجا رو تغییر بده) ==================
SUBJECT   = (os.getenv("SUBJECT") or "ریاضی")          # درس
GRADE     = (os.getenv("GRADE") or "پایه نهم")          # پایه
LANGUAGE  = (os.getenv("LANGUAGE") or "فارسی")          # زبان تست‌ها
TOPICS    = [t.strip() for t in os.getenv("TOPICS", "").split(",") if t.strip()]  # اختیاری: مباحث، جدا شده با کاما
N_QUESTIONS = 10
# مدل‌های رایگان OpenRouter (اگه یکی کار نکرد، بعدی امتحان می‌شه)
MODELS = (os.getenv("MODELS") or "openrouter/free,meta-llama/llama-3.3-70b-instruct:free,openai/gpt-oss-20b:free,qwen/qwen3-coder-480b-a35b-instruct:free").split(",")
# ===================================================================

import local_secrets as _s
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY") or _s.OPENROUTER_API_KEY
BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN") or _s.TELEGRAM_BOT_TOKEN
CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID") or _s.TELEGRAM_CHAT_ID
HISTORY_FILE   = "history.json"


def load_history():
    try:
        return json.load(open(HISTORY_FILE, encoding="utf-8"))
    except Exception:
        return []


def pick_topic():
    if not TOPICS:
        return "یک مبحث دلخواه از کتاب درسی که کمتر تکرار شده"
    return TOPICS[datetime.date.today().toordinal() % len(TOPICS)]


def ask_model(prompt):
    import time
    last_err = None
    for model in MODELS:
        for attempt in range(2):
            try:
                r = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                    json={"model": model.strip(), "messages": [{"role": "user", "content": prompt}], "max_tokens": 6000},
                    timeout=180,
                )
                if r.status_code != 200:
                    print(f"خطا با {model} (تلاش {attempt+1}): {r.status_code} {r.text[:400]}")
                    last_err = f"{r.status_code} {r.text[:200]}"
                    time.sleep(5)
                    continue
                text = r.json()["choices"][0]["message"]["content"] or ""
                text = re.sub(r"```(?:json)?", "", text)
                start, end = text.find("["), text.rfind("]")
                data = json.loads(text[start:end + 1])
                if len(data) >= N_QUESTIONS:
                    print("مدل موفق:", model)
                    return data[:N_QUESTIONS]
                print(f"{model}: تعداد سوال کم بود ({len(data)})")
            except Exception as e:
                last_err = e
                print(f"خطا با {model} (تلاش {attempt+1}): {e}")
                time.sleep(5)
    raise RuntimeError(f"هیچ مدلی جواب نداد: {last_err}")


def generate_questions(topic, history):
    avoid = "\n".join(history[-60:]) or "ندارد"
    prompt = f"""تو یک معلم باتجربه هستی. {N_QUESTIONS} تست چهارگزینه‌ای برای درس «{SUBJECT}» {GRADE} بنویس.
مبحث: {topic}
زبان تست‌ها: {LANGUAGE}
قوانین:
- سطح سوال‌ها ترکیبی از آسان، متوسط و سخت باشد.
- فقط یک گزینه درست باشد و پاسخ‌ها را دوباره چک کن که حتماً درست باشند.
- فرمول‌ها را با متن ساده بنویس (بدون LaTeX).
- از این سوال‌های قبلی تکرار نکن:
{avoid}
خروجی فقط یک آرایه JSON باشد، بدون هیچ توضیح اضافه، با این ساختار:
[{{"question": "...", "options": ["...", "...", "...", "..."], "answer": 0, "explanation": "توضیح کوتاه حل"}}]
که answer شماره گزینه درست است (۰ تا ۳)."""
    return ask_model(prompt)


def build_pdf(questions, topic, path):
    from weasyprint import HTML
    rtl = LANGUAGE in ("فارسی", "عربی", "Persian", "Arabic")
    today = datetime.date.today().isoformat()
    letters = ["الف", "ب", "ج", "د"] if rtl else ["A", "B", "C", "D"]
    e = html.escape
    body = f"<h1>{e(SUBJECT)} - {e(GRADE)}</h1><p class='sub'>{e(topic)} | {today}</p>"
    for i, q in enumerate(questions, 1):
        opts = "".join(f"<li>{letters[j]}) {e(str(o))}</li>" for j, o in enumerate(q["options"][:4]))
        body += f"<div class='q'><b>{i}.</b> {e(q['question'])}<ul>{opts}</ul></div>"
    body += "<div style='page-break-before:always'></div><h2>پاسخنامه</h2>" if rtl else "<div style='page-break-before:always'></div><h2>Answers</h2>"
    for i, q in enumerate(questions, 1):
        body += f"<p><b>{i}. {letters[int(q['answer'])]}</b> - {e(q.get('explanation', ''))}</p>"
    doc = f"""<html dir="{'rtl' if rtl else 'ltr'}"><head><meta charset="utf-8"><style>
    @page {{ size: A4; margin: 2cm; }}
    body {{ font-family: 'Vazirmatn','Noto Naskh Arabic','Noto Sans Arabic','DejaVu Sans',sans-serif; font-size: 13px; line-height: 1.9; }}
    h1 {{ text-align:center; margin-bottom:0; }} .sub {{ text-align:center; color:#666; }}
    .q {{ margin: 14px 0; }} ul {{ list-style:none; padding:0; margin:4px 0 0 0; }}
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
        print("chat_id پیدا شد")
    topic = pick_topic()
    tg("sendMessage", data={"chat_id": CHAT_ID, "text": f"⏰ وقت تست حل کردنه!\nدرس: {SUBJECT}\nمبحث: {topic}\nتست‌های امروز تا چند لحظه دیگه می‌رسن 👇"})
    history = load_history()
    questions = generate_questions(topic, history)
    pdf_path = f"tests-{datetime.date.today().isoformat()}.pdf"
    build_pdf(questions, topic, pdf_path)
    with open(pdf_path, "rb") as f:
        tg("sendDocument", data={"chat_id": CHAT_ID, "caption": f"{N_QUESTIONS} تست امروز ✅"}, files={"document": f})
    history += [q["question"][:80] for q in questions]
    json.dump(history[-200:], open(HISTORY_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
