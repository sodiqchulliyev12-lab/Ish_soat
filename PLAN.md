# Ishchilar boti: reja

**Maqsad:** ishchilar kelgan-ketgan vaqtini Telegram orqali belgilaydi, rahbar esa kunlik holatni va oylik hisobotni (Excel) oladi.

Platforma: **Telegram**. Texnologiya: Python, aiogram 3, SQLite, APScheduler, openpyxl (Excel). Shaxsiy botdan alohida bot (alohida token).

## 1. Rollar

| Rol | Kim | Nima qiladi |
|---|---|---|
| 👑 Admin | Siz (va o'rinbosarlar) | Ishchilarni tasdiqlaydi, kunlik holatni ko'radi, oylik hisobot oladi, sozlamalarni o'zgartiradi |
| 👷 Ishchi | Xodimlar | "Keldim" / "Ketdim" bosadi, o'z hisobotini ko'radi |

Admin `.env` dagi `ADMIN_IDS` orqali belgilanadi (Telegram ID; botga /start bossangiz ID ingizni ko'rsatadi).

## 2. Ishchi uchun

1. Botga **/start** bosadi va **📱 Telefon raqamni yuborish** tugmasini bosadi.
2. Adminga "Yangi ishchi: Ali, +998..." xabari keladi, **✅ Qabul / ❌ Rad** tugmalari bilan.
3. Qabul qilingach ishchida 3 ta tugma paydo bo'ladi:
   - **✅ Keldim**: kelgan vaqt yoziladi
   - **🏁 Ketdim**: ketgan vaqt yoziladi
   - **📊 Mening oyim**: shu oy necha kun keldi, necha soat ishladi, necha marta kechikdi
4. **Joylashuv tekshiruvi (ixtiyoriy):** agar ish joyi koordinatasi kiritilgan bo'lsa, "Keldim/Ketdim" uchun joylashuv yuborish so'raladi. Belgilangan radiusdan (masalan, 150 m) uzoqda bo'lsa qabul qilinmaydi.

## 3. Admin uchun

- **Admin menyusi:** 📋 Bugun, 👥 Ishchilar, 📊 Oylik hisobot, ⚙️ Sozlamalar
- **📋 Bugun:** kim keldi (soati), kim kechikdi, kim kelmadi, kim hali ishda.
- **📊 Oylik hisobot:** matn ko'rinishidagi xulosa va **Excel fayl** (2 varaq):
  - *Umumiy:* ishchi, ish kunlari, kelgan / kelmagan kunlar, kechikishlar soni va daqiqasi, erta ketish, jami soat, maosh hisobi
  - *Batafsil:* har bir kun bo'yicha keldi, ketdi va soat
  - O'tgan oy uchun: `/hisobot 2026-09`
- **Maosh hisobi:** har bir ishchiga turini belgilash mumkin:
  - oylik (ish kuniga nisbatan hisoblanadi), kunlik yoki soatlik: `/maosh 5 oylik 4000000`
- **Tuzatish:** ishchi "Ketdim"ni unutgan bo'lsa: `/tuzat 5 2026-10-15 09:05 18:10`
- **Bildirishnomalar:** har bir kelish/ketish haqida adminga xabar (o'chirsa bo'ladi).

## 4. Avtomatik

- Ish tugash vaqtidan 30 daqiqa keyin hali "Ketdim" bosmaganlarga eslatma.
- Smena tugashidan 6 soat o'tib ham yopilmagan smena ish tugash vaqti bilan yopiladi va "avto" deb belgilanadi.
- Har kuni soat 19:00 da adminga kunlik xulosa: keldi X/Y, kechikkanlar, kelmaganlar.

## 5. Sozlamalar (/sozlama)

| Sozlama | Standart |
|---|---|
| Ish boshlanishi / tugashi | 09:00 / 18:00 |
| Kechikishga ruxsat | 10 daqiqa |
| Dam olish kunlari | Yakshanba |
| Ish joyi koordinatasi va radius | yo'q (joylashuv so'ralmaydi) / 150 m |
| Kunlik xulosa vaqti | 19:00 |
| Har bir kelish/ketish haqida xabar | yoqilgan |

## 6. Ma'lumotlar (SQLite)

- `workers(tg_id, name, phone, status[pending/active/blocked], rate_type, rate, created_at)`
- `shifts(id, tg_id, date, in_at, out_at, in_lat, in_lon, out_lat, out_lon, auto_closed, note)`
- `settings(key, value)`, `flags(key)` (bir kunda bir marta yuboriladigan xabarlar uchun)

## 7. Bosqichlar

1. **MVP (tayyor, 17.10):** Keldim/Ketdim, admin paneli, oylik Excel, eslatmalar.
2. **2-bosqich (tayyor, 17.10):**
   - 🎉 **Bayramlar:** `/bayram 21.03 Navro'z`. Bu kun hech kim kelmagan hisoblanmaydi, oylik maosh shu kunsiz hisoblanadi.
   - 🏖 **Ta'til va ruxsat:** ishchi `📝 Ruxsat so'rash` orqali so'raydi, admin tugma bilan tasdiqlaydi yoki `/tatil` bilan o'zi yozadi. Turlari: ta'til va kasallik (haq to'lanadi), ruxsat (o'z hisobidan).
   - 🏢 **Filiallar:** har biriga alohida joylashuv va radius. Ishchini bitta filialga bog'lash yoki istalgan filialda belgilashga ruxsat berish.
   - 🌙 **Shaxsiy grafik va tungi smena:** `/grafik ID 20:00 08:00`. Tungi smena ertasi kuni yopiladi, kechikish va erta ketish shaxsiy grafik bo'yicha hisoblanadi.
   - 🤳 **Selfi:** `/sozlama selfi on`. Kelish/ketishda selfi so'raladi, rasm adminga boradi.
   - 🎥 **Dumaloq video (17.10):** `/sozlama selfi video`. Ishchi joylashuv yuboradi (filial radiusi tekshiriladi), keyin dumaloq video yozadi. Adminga video, filial nomi, masofa va xarita havolasi boradi.
   - Unutilgan "Ketdim" endi har bir ishchining smena tugashidan 6 soat keyin avtomatik yopiladi.
3. **Keyingi:** serverga (VPS) qo'yish va bazani har kuni zaxiralash, ishchi ichki kodi (QR) bilan belgilash, Google Sheets ga avtomatik yuborish.
