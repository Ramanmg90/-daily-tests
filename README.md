# راه‌اندازی قدم به قدم

1. توی تلگرام برو سراغ باتت و دکمه‌ی Start رو بزن (یا یه پیام بده).
2. توی github.com ثبت‌نام کن. بعد + بالا سمت راست، New repository، یه اسم بذار، گزینه‌ی **Private** رو انتخاب کن و Create.
3. این زیپ رو extract کن. توی صفحه‌ی ریپو روی "uploading an existing file" کلیک کن و **همه‌ی محتوای پوشه** (از جمله پوشه‌ی .github) رو بکش و بنداز. بعد Commit changes.
   - اگه پوشه‌ی .github آپلود نشد: Add file > Create new file، اسم رو بنویس `.github/workflows/daily.yml` و محتوای فایل daily.yml رو paste کن.
4. (اختیاری) Settings > Secrets and variables > Actions > Variables: سه تا متغیر بساز با اسم‌های SUBJECT (مثلاً ریاضی)، GRADE (مثلاً پایه نهم)، LANGUAGE (مثلاً فارسی). اگه نسازی، پیش‌فرض ریاضی/نهم/فارسی استفاده می‌شه.
5. تب Actions > اگه دکمه‌ی فعال‌سازی دید، بزن > daily-tests > Run workflow. بعد از ۲ تا ۳ دقیقه باید پیام و PDF توی تلگرام برسه.

ساعت ارسال: توی daily.yml خط cron (به وقت UTC). الان ۱۲:۰۰ UTC = ۱۵:۳۰ ایران.
بعداً توکن‌ها رو عوض کن: فایل local_secrets.py رو توی گیت‌هاب ویرایش کن.
