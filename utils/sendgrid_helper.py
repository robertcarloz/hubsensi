# sendgrid_helper.py
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Ambil API key dari environment variable
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
FROM_EMAIL = os.environ.get('SENDGRID_FROM_EMAIL')  # misal: "no-reply@hubsensi.com"

if not SENDGRID_API_KEY:
    raise ValueError("Environment variable SENDGRID_API_KEY belum diset")
if not FROM_EMAIL:
    raise ValueError("Environment variable SENDGRID_FROM_EMAIL belum diset")

def send_email(to_email: str, subject: str, body: str) -> dict:
    """
    Mengirim email via SendGrid.
    :param to_email: alamat penerima
    :param subject: subject email
    :param body: isi email (plain text)
    :return: response dict dari SendGrid
    """
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        plain_text_content=body
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return {
            "status_code": response.status_code,
            "body": response.body.decode() if hasattr(response.body, 'decode') else str(response.body),
            "headers": dict(response.headers)
        }
    except Exception as e:
        raise RuntimeError(f"Gagal mengirim email: {e}")
