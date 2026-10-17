# Ishchilar boti: ishga tushirish

Ishchilar Telegram orqali **Keldim / Ketdim** bosadi, admin kunlik holatni va **oylik Excel hisobot** oladi. To'liq imkoniyatlar: [PLAN.md](PLAN.md). Hisobot qanday ko'rinishi: `namuna_hisobot_sentabr.xlsx`.

## 1. Yangi bot yarating
1. Telegramda **@BotFather** → `/newbot` → nom bering (masalan, "Ishxona davomat").
2. Bergan tokenni nusxalang. Bu shaxsiy botingizdan **alohida** bot.

## 2. O'rnatish
Python 3.10+ kerak.
```bash
git clone https://github.com/sodiqchulliyev12-lab/Ish_soat.git
cd Ish_soat
python -m venv venv
# Windows: venv\Scripts\activate    Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```
`.env.example` dan nusxa olib `.env` deb nomlang va tokenni yozing:
```
BOT_TOKEN=123456789:AA...
ADMIN_IDS=
```

## 3. Admin ID ni kiriting
1. `python main.py` bilan ishga tushiring, botga `/start` bosing: bot sizning Telegram ID ingizni ko'rsatadi.
2. Botni to'xtating (Ctrl+C), ID ni `.env` ga yozing: `ADMIN_IDS=123456789` (bir nechta bo'lsa vergul bilan).
3. Qayta ishga tushiring: `python main.py`. Endi sizda admin menyusi chiqadi.

## 4. Ishchilarni qo'shish
Ishchilarga bot havolasini yuboring. Ular `/start` → **📱 Telefon raqamni yuborish** ni bosadi, sizga **✅ Qabul / ❌ Rad** tugmalari bilan xabar keladi.

## 5. Birinchi sozlamalar
- `/sozlama ish 09:00 18:00`: ish vaqti
- `/sozlama dam yakshanba`: dam olish kunlari
- `/filial qosh Asosiy`: ish joyida turib joylashuv yuborsangiz, ishchilar faqat shu joydan 150 m ichida belgilay oladi (ixtiyoriy, bir nechta filial bo'lishi mumkin)
- `/bayram 01.01 Yangi yil`: bayram kunlari
- `/grafik ID 20:00 08:00`: boshqacha yoki tungi grafikdagi ishchi uchun
- `/sozlama selfi on`: kelish/ketishda selfi so'rash
- `/lavozim ID Sotuvchi`: lavozimni o'zgartirish (yangi ishchini qabul qilganda bot lavozimni o'zi so'raydi)
- `/sozlama selfi video`: kelish/ketishda dumaloq video so'rash (joylashuv filial radiusida tekshiriladi, video va xarita havolasi adminga boradi)
- `/maosh ID oylik 4000000`: maosh hisoblanishi uchun (ID: 👥 Ishchilar)
- Hamma buyruqlar: `/yordam`

## Railway'ga joylash (doimiy ishlashi uchun)
1. https://railway.com ga kiring → **Login with GitHub**.
2. **New Project** → **Deploy from GitHub repo** → `Ish_soat` ni tanlang (so'rasa, Railway'ga shu omborga ruxsat bering).
3. Xizmat (service) ustiga bosing → **Variables** → qo'shing:
   - `BOT_TOKEN` = @BotFather bergan token
   - `ADMIN_IDS` = Telegram ID ingiz (bilmasangiz, avval bo'sh qoldiring, botga /start bosing, keyin yozing)
4. Bazaning saqlanib qolishi uchun **Volume** qo'shing: loyiha oynasida o'ng tugma (yoki Ctrl+K) → **Volume** → xizmatga ulang, mount path: `/data`. Bot bazani o'zi shu yerga yozadi.
5. **Deploy** ni bosing. **Deployments → View logs** da `Ishchilar boti ishga tushdi` chiqsa, bot ishlayapti.

Eslatma: botdan faqat **bitta** nusxa ishlashi kerak (Replicas = 1). Kompyuteringizda ham ishga tushirsangiz, ikkalasi to'qnashadi. Railway pullik: sinov kreditidan keyin Hobby rejasi oyiga taxminan $5.


- Bot faqat dastur ishlab turganda ishlaydi. Ishchilar har kuni foydalangani uchun uni serverga (VPS) qo'yish kerak.
- Ma'lumotlar `ishchilar.db` faylida. Uni vaqti-vaqti bilan nusxalab qo'ying.
- Eski versiyadan yangilasangiz, `ishchilar.db` saqlanadi: yangi ustunlar o'zi qo'shiladi, `/sozlama joy` bilan kiritilgan joy «Asosiy» filialga aylanadi.

## Tekshirish
```bash
python tests/test_bot.py
```
Telegramga ulanmasdan barcha jarayonni sinaydi, oxirida `ALL OK` chiqadi.

## Tuzilishi
```
main.py            ishga tushirish
app/worker.py      ro'yxatdan o'tish, Keldim/Ketdim, joylashuv va selfi, ruxsat so'rash
app/admin.py       admin buyruqlari: ishchilar, grafik, filial, bayram, ta'til, sozlamalar
app/days.py        grafik, tungi smena, bayram va ta'til kunlarini aniqlash
app/report.py      hisob-kitob, matnli xulosa, Excel
app/scheduler.py   eslatma, avto yopish, kunlik xulosa
app/db.py          SQLite
```
