import os
import requests
from functools import wraps
from flask import Flask, request, render_template, redirect, url_for, session
from dotenv import load_dotenv
from groq import Groq
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

VERIFY_TOKEN = "aicommentbot_dogrulama_2026"
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_db_connection():
    return psycopg2.connect(dbname="aicommentbot")


def get_current_user():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, instagram_username, instagram_access_token, ai_instructions FROM users WHERE username = %s",
        (session.get("username"),)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "instagram_username": row[2], "instagram_access_token": row[3], "ai_instructions": row[4]}
    return None


def get_media_info(media_id, access_token):
    url = f"https://graph.instagram.com/{media_id}"
    params = {
        "fields": "media_url,permalink,caption",
        "access_token": access_token
    }
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        print(f"Medya bilgisi alınamadı: {e}")
        return {}


def generate_ai_reply(comment_text, caption=None, media_url=None, custom_instructions=None):
    caption_note = f"\nGönderinin açıklaması: \"{caption}\"" if caption else ""
    persona = custom_instructions.strip() if custom_instructions else "Sen bir kitap Instagram hesabının sahibisin."

    system_prompt = (
        f"{persona} Yorumlara her zaman samimi, saygılı ve doğru bir tonda, "
        "kısa (1-2 cümle) cevap ver, gramer hatası yapma. Kendini asla yapay zeka, "
        "bot veya AI olarak tanıtma; her zaman hesabın gerçek sahibiymişsin gibi, "
        "birinci ağızdan bir insan gibi konuş.\n\n"
        "ÇOK ÖNEMLİ KURAL: %100 emin olmadığın hiçbir bilgiyi verme. Bu; bahsedilen "
        "eserin/ürünün konusu, ana karakteri, sonu, teknik detayları, tarihleri VE "
        "özellikle Türkçe çeviri/isim başlıkları için geçerli. Bir ismin Türkçe "
        "karşılığından TAM OLARAK emin değilsen, ASLA kendin bir çeviri uydurma; "
        "bunun yerine orijinal adını olduğu gibi kullan. Bir konuda %100 emin "
        "değilsen tahmin yürütme veya uydurma; bunun yerine kısaca 'bu konuda tam "
        "bilgim yok ama...' diyerek genel bir yorum yap. Yanlış ama kendinden emin "
        "görünen bir cevap vermek, hiç cevap vermemekten çok daha kötüdür.\n\n"
        "ÖNERİ KURALI: Sana benzer bir şey önerisi sorulursa (kitap, ürün, film vb.), "
        "ASLA spesifik bir isim uydurma riskine girme; SADECE türe, temaya veya tarza "
        "dayalı genel bir yorum yap, isim vermekten kaçın."
        f"{caption_note}"
    )

    if media_url:
        user_content = [
            {"type": "text", "text": comment_text},
            {"type": "image_url", "image_url": {"url": media_url}}
        ]
        model = "qwen/qwen3.8-27b"
    else:
        user_content = comment_text
        model = "openai/gpt-oss-20b"

    response = groq_client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    )
    return response.choices[0].message.content


def check_comment_exists(comment_id, access_token):
    url = f"https://graph.instagram.com/{comment_id}"
    params = {"fields": "id", "access_token": access_token}
    try:
        response = requests.get(url, params=params)
        return response.ok
    except Exception as e:
        print(f"Yorum kontrolu basarisiz: {e}")
        return True


def post_reply_to_instagram(instagram_comment_id, message, access_token):
    url = f"https://graph.instagram.com/{instagram_comment_id}/replies"
    data = {
        "message": message,
        "access_token": access_token
    }
    try:
        response = requests.post(url, data=data)
        print(f"Instagram'a gönderildi: {response.json()}")
        return response.ok
    except Exception as e:
        print(f"Instagram'a gönderilemedi: {e}")
        return False


def get_grouped_posts(owner_user_id, access_token):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM comments WHERE owner_user_id = %s ORDER BY created_at DESC", (owner_user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    grouped = {}
    for row in rows:
        media_id = row[6] if len(row) > 6 else None
        if media_id not in grouped:
            grouped[media_id] = {
                "media_id": media_id,
                "media_url": None,
                "permalink": None,
                "comments": [],
                "latest": row[5]
            }
        grouped[media_id]["comments"].append(row)

    posts = list(grouped.values())
    posts.sort(key=lambda p: p["latest"], reverse=True)

    for post in posts:
        if post["media_id"]:
            info = get_media_info(post["media_id"], access_token)
            post["media_url"] = info.get("media_url")
            post["permalink"] = info.get("permalink")

    return posts


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not username or not password:
            error = "Kullanıcı adı ve şifre boş olamaz"
        elif password != password2:
            error = "Şifreler eşleşmiyor"
        elif len(password) < 6:
            error = "Şifre en az 6 karakter olmalı"
        else:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                error = "Bu kullanıcı adı zaten alınmış"
            else:
                password_hash = generate_password_hash(password)
                cur.execute(
                    "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                    (username, password_hash)
                )
                conn.commit()
                cur.close()
                conn.close()
                session['logged_in'] = True
                session['username'] = username
                return redirect(url_for('connect_instagram'))
            cur.close()
            conn.close()

    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row and check_password_hash(row[0], password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('gallery'))
        else:
            error = "Kullanıcı adı veya şifre hatalı"
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/connect-instagram', methods=['GET', 'POST'])
@login_required
def connect_instagram():
    error = None
    if request.method == 'POST':
        ig_username = request.form.get('instagram_username', '').strip()
        ig_token = request.form.get('instagram_token', '').strip()

        if not ig_username or not ig_token:
            error = "Kullanıcı adı ve token boş olamaz"
        else:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET instagram_username = %s, instagram_access_token = %s WHERE username = %s",
                (ig_username, ig_token, session.get("username"))
            )
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('gallery'))

    return render_template('connect_instagram.html', error=error)


@app.route('/')
@login_required
def gallery():
    user = get_current_user()
    if not user or not user["instagram_access_token"]:
        return redirect(url_for('connect_instagram'))
    posts = get_grouped_posts(user["id"], user["instagram_access_token"])
    total_comments = sum(len(p["comments"]) for p in posts)
    return render_template('gallery.html', posts=posts, total_comments=total_comments, user=user)


@app.route('/post/<media_id>')
@login_required
def post_detail(media_id):
    user = get_current_user()
    if not user or not user["instagram_access_token"]:
        return redirect(url_for('connect_instagram'))
    posts = get_grouped_posts(user["id"], user["instagram_access_token"])
    post = next((p for p in posts if p["media_id"] == media_id), None)
    if post is None:
        return "Gönderi bulunamadı", 404
    return render_template('post_detail.html', post=post)


@app.route('/comment/<int:comment_id>/approve', methods=['POST'])
@login_required
def approve_comment(comment_id):
    user = get_current_user()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT instagram_comment_id, ai_reply, media_id FROM comments WHERE id = %s", (comment_id,))
    row = cur.fetchone()
    if row:
        instagram_comment_id, ai_reply, media_id = row
        if not check_comment_exists(instagram_comment_id, user["instagram_access_token"]):
            print(f"Yorum Instagram'da silinmis, uygulamadan da kaldirildi: {comment_id}")
            cur.execute("DELETE FROM comments WHERE id = %s", (comment_id,))
            conn.commit()
        else:
            success = post_reply_to_instagram(instagram_comment_id, ai_reply, user["instagram_access_token"])
            if success:
                cur.execute("UPDATE comments SET status = 'approved' WHERE id = %s", (comment_id,))
                conn.commit()
    cur.close()
    conn.close()
    return redirect(request.referrer or url_for('gallery'))


@app.route('/comment/<int:comment_id>/edit', methods=['POST'])
@login_required
def edit_comment(comment_id):
    new_text = request.form.get('new_reply')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE comments SET ai_reply = %s, status = 'pending' WHERE id = %s", (new_text, comment_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(request.referrer or url_for('gallery'))


@app.route('/comment/<int:comment_id>/regenerate', methods=['POST'])
@login_required
def regenerate_comment(comment_id):
    user = get_current_user()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT comment_text, media_id FROM comments WHERE id = %s", (comment_id,))
    row = cur.fetchone()
    if row:
        comment_text, media_id = row
        media_info = get_media_info(media_id, user["instagram_access_token"])
        caption = media_info.get('caption')
        media_url = media_info.get('media_url')
        new_reply = generate_ai_reply(comment_text, caption, media_url, user.get("ai_instructions"))
        cur.execute("UPDATE comments SET ai_reply = %s, status = 'pending' WHERE id = %s", (new_reply, comment_id))
        conn.commit()
    cur.close()
    conn.close()
    return redirect(request.referrer or url_for('gallery'))


@app.route('/comment/<int:comment_id>/reject', methods=['POST'])
@login_required
def reject_comment(comment_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM comments WHERE id = %s", (comment_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(request.referrer or url_for('gallery'))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = get_current_user()
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        new_instructions = request.form.get('ai_instructions', '').strip()
        cur.execute("UPDATE users SET ai_instructions = %s WHERE id = %s", (new_instructions, user["id"]))
        conn.commit()
        user["ai_instructions"] = new_instructions

    cur.close()
    conn.close()
    return render_template('settings.html', user=user)


@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("Webhook doğrulandı!")
        return challenge, 200
    else:
        return "Doğrulama başarısız", 403


@app.route('/webhook', methods=['POST'])
def receive_webhook():
    data = request.get_json()
    print("Yeni webhook verisi geldi:")
    print(data)

    try:
        entry = data['entry'][0]
        instagram_account_id = entry.get('id')
        change = entry['changes'][0]
        value = change['value']

        comment_id = value.get('id')
        username = value.get('from', {}).get('username')
        comment_text = value.get('text')
        media_id = value.get('media', {}).get('id')

        if comment_text:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, instagram_access_token, ai_instructions, instagram_username FROM users WHERE instagram_username IS NOT NULL")
            users = cur.fetchall()

            owner_user_id = None
            access_token = None
            owner_instructions = None
            owner_instagram_username = None
            for uid, token, instructions, ig_username in users:
                info = get_media_info(media_id, token)
                if info.get('media_url') or info.get('permalink'):
                    owner_user_id = uid
                    access_token = token
                    owner_instructions = instructions
                    owner_instagram_username = ig_username
                    break

            if owner_user_id and username and owner_instagram_username and username.lower() == owner_instagram_username.lower():
                print("Bu yorum botun kendi hesabından geldiği için atlandı (kendine cevap döngüsü önlendi).")
            elif owner_user_id:
                media_info = get_media_info(media_id, access_token)
                caption = media_info.get('caption')
                media_url = media_info.get('media_url')

                ai_reply = generate_ai_reply(comment_text, caption, media_url, owner_instructions)
                print(f"AI cevabı üretildi: {ai_reply}")

                cur.execute(
                    """
                    INSERT INTO comments (instagram_comment_id, username, comment_text, ai_reply, media_id, owner_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (instagram_comment_id) DO NOTHING
                    """,
                    (comment_id, username, comment_text, ai_reply, media_id, owner_user_id)
                )
                conn.commit()
                print("Veritabanına kaydedildi.")
            else:
                print("Bu yorumun hangi kullanıcıya ait olduğu bulunamadı.")

            cur.close()
            conn.close()

    except Exception as e:
        print(f"Hata oluştu: {e}")

    return "OK", 200


if __name__ == '__main__':
    app.run(port=5001, debug=True)

