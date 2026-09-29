# Do&Go List Maker

İşbirlikçi (Collaborative) Liste Oluşturma ve Yönetim Web Uygulaması. Arkadaş gruplarının, çiftlerin ve gençlerin sosyal medyada gördükleri mekanları, aktiviteleri veya görevleri tek bir ortak listede organize etmelerini sağlar.

## 🛠️ Teknoloji Yığını (Tech Stack)

* **Backend:** Python, [FastAPI](https://fastapi.tiangolo.com/)
* **Template Engine:** [Jinja2](https://palletsprojects.com/p/jinja/) (Server-Side Rendering)
* **Auth & Veritabanı:** [Supabase](https://supabase.com/) (PostgreSQL & Supabase Auth)
* **Frontend:** HTML5, Vanilla JavaScript, [Tailwind CSS (CDN)](https://tailwindcss.com/), [Lucide Icons](https://lucide.dev/)
* **Deployment Hedefi:** Vercel (Serverless Functions)

---

## 📁 Proje Dizin Yapısı

```text
Do&GoListMaker/
├── app/
│   ├── core/
│   │   ├── config.py           # Pydantic Settings ve .env konfigürasyonu
│   │   ├── supabase.py         # Supabase client fabrika fonksiyonları
│   │   └── dependencies.py     # Cookie tabanlı Auth/Oturum bağımlılıkları
│   ├── routers/
│   │   ├── auth.py             # Giriş, Kayıt ve Çıkış rotaları
│   │   └── lists.py            # Liste ve Madde CRUD rotaları
│   └── main.py                 # FastAPI ana uygulama başlangıç noktası
├── docs/
│   └── do_go_list_maker_proje_dok_man.md # Proje şartnamesi ve faz dokümanı
├── static/                     # CSS, JS, statik varlıklar
├── templates/                  # Jinja2 HTML şablonları
│   ├── auth/                   # login.html, register.html
│   ├── lists/                  # index.html, detail.html
│   └── base.html               # Ortak iskelet (Navbar, Footer, Tailwind, Lucide)
├── .env.example                # Ortam değişkenleri şablonu
├── requirements.txt            # Python bağımlılıkları
├── schema.sql                  # Supabase tabloları, trigger'lar ve RLS kuralları
└── README.md
```

---

## 🚀 Kurulum ve Yerel Geliştirme

### 1. Sanal Ortam Oluşturma ve Bağımlılıkları Yükleme
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Supabase Veritabanını Hazırlama
1. Supabase projenizin **SQL Editor** sekmesine gidin.
2. Projedeki `schema.sql` dosyasının içeriğini yapıştırıp **Run** butonuna basarak tabloları ve RLS politikalarını oluşturun.

### 3. Ortam Değişkenleri (.env)
Kök dizinde `.env` dosyası oluşturun:
```env
SUPABASE_URL=https://<your-project-id>.supabase.co
SUPABASE_KEY=<your-anon-or-service-key>
SECRET_KEY=do-and-go-super-secret-key-change-in-production
ENVIRONMENT=development
```

### 4. Geliştirme Sunucusunu Başlatma
```bash
.venv/bin/uvicorn app.main:app --reload
```
Tarayıcınızda açın: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 📌 Geliştirme Fazları ve Durumu

- [x] **FAZ 1: Temel MVP ve Kullanıcı Yönetimi**
  - [x] FastAPI ve Jinja2 entegrasyonu
  - [x] Supabase Auth ve Cookie tabanlı oturum mimarisi
  - [x] Giriş (Login), Kayıt Ol (Register), Çıkış (Logout) sayfaları
  - [x] Liste oluşturma, listeleme ve silme
  - [x] Listeye madde ekleme, check/tamamlama ve silme
- [x] **FAZ 2: İşbirliği (Collaboration) ve Link Paylaşımı**
  - [x] Liste için dinamik paylaşım linki oluşturma ve tek tıkla kopyalama
  - [x] Liste sahibi için paylaşıma açma/kapama (`is_shared` toggle)
  - [x] Giriş yapmamış ziyaretçiler için "Salt Okunur (Read-only)" görünüm ve CTA banner'ı
  - [x] Üye kullanıcıların paylaşılan listelere katılımcı olarak dahil olması
  - [x] Katılımcılar için "Benimle Paylaşılanlar" sekmesi/bölümü
  - [x] Liste sahibi için "Katılımcılar ve Yetkiler" paneli (Silme izni tanımlama)
- [x] **FAZ 3: Puanlama, Feedback ve Harita Özelliği**
  - [x] Harita entegrasyonu (Google Maps linkleri, yeni sekmede açılma)
  - [x] Tamamlanan maddeler için 1-5 yıldız puanlama ve yorum (feedback) sistemi
  - [x] Maddelerin ortalama puanının dinamik hesaplanıp arayüzde gösterilmesi
  - [x] Kullanıcıların kendi puanlarını güncelleyebilmesi (Upsert)
  - [x] Yorumların yanında kullanıcı adları (@username) ve tarih gösterimi
- [ ] **FAZ 4: UI/UX İyileştirmeleri ve Vercel Deployment**
  - [ ] Mobil uyumlu detaylı animasyonlar ve mikro-etkileşimler
  - [ ] `vercel.json` ve Serverless deploy hazırlığı
