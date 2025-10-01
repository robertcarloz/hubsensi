from PIL import Image, ImageDraw, ImageFont,ImageOps
import requests
import io
import textwrap

def generate_student_card(student_name, nis, qr_code):
    """
    Generates a student card with text wrapping for the student's name.
    """
    template = Image.open("static/img/card_template.png")
    draw = ImageDraw.Draw(template)

    try:
        font_bold = ImageFont.truetype("static/fonts/AvenirBlack.ttf", 65)
        font_regular = ImageFont.truetype("static/fonts/AvenirMedium.ttf", 65)
    except IOError:
        font_bold = ImageFont.load_default()
        font_regular = ImageFont.load_default()

    # --- LOGIKA TEXT WRAP DIMULAI DI SINI ---

    # 1. Tentukan lebar maksimal untuk teks nama (dalam jumlah karakter)
    #    Anda mungkin perlu menyesuaikan angka '15' ini agar pas dengan desain kartu
    max_width_char = 15
    
    # 2. Bungkus teks nama siswa menjadi beberapa baris
    wrapped_name = textwrap.wrap(student_name.upper(), width=max_width_char)

    # 3. Tentukan posisi awal untuk teks dan tinggi baris
    y_position = 450  # Posisi y awal untuk baris pertama
    line_height = font_bold.getbbox('A')[3] + 10 # Tinggi font ditambah sedikit spasi

    # 4. Tulis setiap baris teks ke gambar
    for line in wrapped_name:
        # Gunakan textbbox untuk mendapatkan lebar teks agar bisa diposisikan di tengah
        text_width = draw.textbbox((0, 0), line, font=font_bold)[2]
        x_position = (template.width - text_width) / 2 # Posisi x di tengah
        
        draw.text((x_position, y_position), line, font=font_bold, fill=(255, 255, 255))
        y_position += line_height # Pindahkan posisi y ke bawah untuk baris berikutnya

    # --- LOGIKA TEXT WRAP SELESAI ---

    # 1. Buat string teks untuk NIS
    nis_text = f"NIS: {nis}"
    # 2. Hitung lebar teks NIS menggunakan textbbox
    nis_text_width = draw.textbbox((0, 0), nis_text, font=font_regular)[2]
    # 3. Hitung posisi x agar teks berada di tengah
    nis_x_position = (template.width - nis_text_width) / 2
    # 4. Gambar teks NIS di posisi yang sudah dihitung
    draw.text((nis_x_position, y_position + 20), nis_text, font=font_regular, fill=(255, 255, 255, 255))

    if qr_code:
        try:
            response = requests.get(qr_code)
            response.raise_for_status() 
            qr_img = Image.open(io.BytesIO(response.content)).resize((700, 700))
            qr_img_grayscale = qr_img.convert('L')
            inverted_qr_mask = ImageOps.invert(qr_img_grayscale)
            black = 0
            template.paste(black, (290, 1100), mask=inverted_qr_mask)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching QR code from S3: {e}")
            pass

    # Save the image to a byte stream
    img_byte_arr = io.BytesIO()
    template.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()

    return img_byte_arr