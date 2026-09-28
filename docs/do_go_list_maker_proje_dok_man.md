# Proje Adı: Do&Go List Maker

**Proje Türü:** İşbirlikçi (Collaborative) Liste Oluşturma ve Yönetim Web Uygulaması
**Hedef Kitle:** Gençler, çiftler ve arkadaş grupları.
**Geliştirme Stratejisi:** Prototip odaklı, aşamalı (phased) geliştirme. Karmaşık yapılardan kaçınılarak adım adım ilerlenecek.

## 1. Proje Amacı ve Özeti

İnsanların sosyal medyada gördükleri ve gitmek/yapmak istedikleri şeyleri arkadaşlarıyla paylaşarak organize etmelerini sağlayan bir web uygulaması. Sadece mekan (kafe, restoran, gezilecek yer) değil; film izleme listeleri, ev alışverişi veya yapılacak işler gibi tamamen özelleştirilebilir listeler oluşturulabilir. Kullanıcılar bu listeleri ortaklaşa yönetebilir, tamamlananlara tik atabilir, puan verebilir ve yorum bırakabilirler.

## 2. Teknoloji Yığını (Tech Stack)

* **Backend:** Python, FastAPI
* **Template Engine:** Jinja2 (HTML sayfalarını backend üzerinden render etmek için)
* **Veritabanı ve Auth:** Supabase (PostgreSQL ve kullanıcı doğrulama işlemleri için)
* **Frontend:** HTML, CSS, Vanilla JavaScript (Ayrı bir framework olmadan, Jinja2 şablonları içerisinde)
* **Deployment:** Vercel (Serverless Functions)

## 3. Temel Gereksinimler ve Kurallar

* **Kullanıcı Yönetimi:** E-posta, parola ve kullanıcı adı (username) ile kayıt/giriş. Supabase Auth kullanılabilir veya FastAPI üzerinden JWT ile özel bir yapı kurulabilir. Puanlamalarda ve yorumlarda (feedback) kullanıcı adı görünecek.
* **Liste Erişimi:** Link ile paylaşım (UUID vb. ile). Linke tıklayan ziyaretçiler listeyi "sadece okuyabilir" (Read-only). Listeye eleman eklemek, puan veya feedback vermek için üye girişi zorunludur.
* **Yetkilendirme:** Listeyi oluşturan kişi, linki paylaştığı kişilere (eğer platforma üyelerse) "silme" veya "düzenleme" gibi ekstra yetkiler tanımlayabilir.
* **Harita Entegrasyonu:** Eklenen bir mekanın konumu opsiyonel olarak eklenebilir. İsime tıklandığında Google Maps'te açılmalıdır.
* **Değerlendirme Sistemi:** Her kullanıcı listedeki bir maddeye bağımsız olarak 1-5 arası yıldız verebilir ve yorum yapabilir. Bu puanların ortalaması hesaplanarak o maddenin genel puanı oluşturulur.
* **Arayüz (UI/UX):** Temiz, gençlere hitap eden, modern bir tasarım. Hızlı prototipleme için Tailwind CSS CDN olarak projeye dahil edilebilir.

## 4. Geliştirme Fazları (Yapay Zeka İçin Talimatlar)

**ÖNEMLİ NOT:** Geliştirmeye sadece **FAZ 1** ile başla. Faz 1 tamamlanıp test edilmeden diğer fazlara geçme.

### FAZ 1: Temel MVP (Prototip) ve Kullanıcı Yönetimi

**Hedef:** Sistemin iskeletini kurmak, FastAPI-Jinja2 entegrasyonunu sağlamak ve temel CRUD işlemlerini yapmak.

* FastAPI projesinin iskeletinin oluşturulması ve Supabase veritabanı/auth bağlantısının (Supabase Python Client ile) yapılması.
* Jinja2Templates yapılandırmasının kurularak `templates` ve `static` klasörlerinin ayarlanması.
* Kullanıcı modelinin oluşturulması/ayarlanması (Email, Şifre, Username).
* Kayıt Ol (Register), Giriş Yap (Login), Çıkış Yap (Logout) sayfalarının oluşturulması (Session veya Cookie tabanlı JWT/Supabase token yönetimi).
* Kullanıcının sadece kendine ait (Private) bir liste oluşturabilmesi, silebilmesi ve güncelleyebilmesi.
* Oluşturulan listeye "Madde (Item)" eklenebilmesi, tamamlandığında "Check (Tik)" atılabilmesi ve maddelerin silinebilmesi.

### FAZ 2: İşbirliği (Collaboration) ve Link Paylaşımı

**Hedef:** Listeleri başkalarıyla paylaşmak ve yetki sınırlarını belirlemek.

* Listeler için benzersiz bir URL rotası üretme (Örn: `GET /list/{list_uuid}`).
* Linki açan kişinin eğer girişi (login token'ı) yoksa listeyi sadece görüntüleyebilmesi.
* Giriş yapmış bir kullanıcı linki açarsa, liste sahibinin belirlediği yetkiye göre API endpoint'lerine (POST/DELETE) erişebilmesi.
* Liste Sahibinin (Owner), listeye katılan kullanıcıların yetkilerini arayüz üzerinden (AJAX/Fetch API ile FastAPI'ye istek atarak) yönetebilmesi.

### FAZ 3: Puanlama, Feedback ve Harita Özelliği

**Hedef:** Etkileşimi artırmak ve veriyi zenginleştirmek.

* Liste maddelerine (Items) opsiyonel "Konum Linki (Google Maps URL)" alanı eklenmesi. Link varsa Jinja2 template tarafında `target="_blank"` ile Maps bağlantısı verilmesi.
* Tamamlanan (Check atılan) maddeler için 1-5 Yıldız Puanlama ve Yorum (Feedback) yapısının kurulması.
* Bir maddeye birden fazla kullanıcının puan verebilmesi; bu puanların ortalamasının backend'de hesaplanıp (veya veritabanı view/trigger ile) arayüze gönderilmesi.
* Yorumların yanında kullanıcı adlarının (Username) gösterilmesi.

### FAZ 4: UI/UX İyileştirmeleri ve Vercel Deployment

**Hedef:** Arayüzü parlatmak ve projeyi serverless ortamda yayına almak.

* Tailwind CSS (CDN) ve biraz Vanilla JS eklenerek arayüzün mobil uyumlu, temiz ve dinamik hale getirilmesi.
* Vercel'de FastAPI'yi çalıştırmak için gerekli olan `vercel.json` dosyasının (rewrites ve serverless functions ayarları) oluşturulması.
* Projenin Vercel'e deploy edilmesi ve Supabase ortam değişkenlerinin (Environment Variables) ayarlanması.

## 5. Önerilen Veritabanı Şeması (Fikir Vermesi Açısından)

* **Users:** id, username, email, created_at (Supabase Auth ile senkronize çalışabilir)
* **Lists:** id, uuid, title, description, owner_id (FK), created_at, is_shared
* **ListPermissions:** id, list_id (FK), user_id (FK), can_delete (Boolean)
* **ListItems:** id, list_id (FK), title, location_url (nullable), is_completed, created_by (FK)
* **Feedbacks:** id, item_id (FK), user_id (FK), rating (Int 1-5), comment (Text)

*(Yapay Zeka'ya Not: Lütfen kod yazmaya başladığında ilk olarak FAZ 1'in veritabanı bağlantılarını, FastAPI route'larını ve Jinja2 HTML şablonlarını oluşturmakla başla.)*