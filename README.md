# AICommentBot

Instagram gönderilerine gelen yorumları otomatik olarak okuyup, yapay zeka (Groq API) ile cevap taslakları üreten ve hesap sahibinin onayladıktan sonra Instagram'a gönderen bir Flask uygulaması.

## Özellikler

- Instagram webhook üzerinden gelen yorumları otomatik yakalar
- Groq API (LLM) ile her yoruma özel cevap taslağı üretir
- Hesap sahibi, üretilen cevabı **onaylayabilir, düzenleyebilir veya reddedebilir**
- Her Instagram hesabı için özel AI kuralları/ayarları tanımlanabilir
- Onaylanan cevaplar Instagram Graph API ile otomatik gönderilir
- Silinen yorumlar uygulamadan da otomatik kaldırılır

## Kurulum

### 1. Depoyu klonla

```bash
git clone https://github.com/gizeesm/aicommentbot.git
cd aicommentbot
```

### 2. Sanal ortam oluştur ve bağımlılıkları yükle

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. PostgreSQL veritabanını hazırla

```bash
createdb aicommentbot
```

### 4. `.env` dosyasını oluştur

Proje klasöründe bir `.env` dosyası oluştur ve aşağıdaki değişkenleri kendi bilgilerinle doldur:

```
GROQ_API_KEY=senin_groq_api_anahtarın
INSTAGRAM_ACCESS_TOKEN=senin_instagram_erişim_tokenın
ADMIN_USERNAME=admin_kullanıcı_adı
ADMIN_PASSWORD=admin_şifresi
FLASK_SECRET_KEY=rastgele_bir_gizli_anahtar
```

> Instagram erişim token'ını nasıl alacağını bilmiyorsan, uygulamadaki `/connect-instagram` sayfasında "Token nasıl alınır?" bölümüne bakabilir veya `static/rehber/Instagram_Token_Final.pdf` dosyasındaki görselli rehberi inceleyebilirsin.

### 5. Uygulamayı çalıştır

```bash
python3 app.py
```

Uygulama varsayılan olarak `http://127.0.0.1:5001` adresinde çalışır.

## Instagram Hesabını Bağlama

1. Instagram hesabını **Profesyonel (İşletme)** hesaba çevir
2. [Meta for Developers](https://developers.facebook.com/apps) üzerinden bir uygulama oluştur
3. Instagram hesabını uygulamaya ekleyip erişim token'ı oluştur
4. `/connect-instagram` sayfasından kullanıcı adı ve token'ı girerek bağlan

Detaylı adımlar için `static/rehber/Instagram_Token_Final.pdf` dosyasına bakabilirsin.

## Teknolojiler

- Python / Flask
- PostgreSQL
- Groq API (yapay zeka cevap üretimi)
- Instagram Graph API
