import resend
import os
from dotenv import load_dotenv
load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

def enviar_email_verificacion(email: str, token: str):
    enlace = f"https://yvexiq.com/verificar-email?token={token}"
    try:
        resend.Emails.send({
            "from": "YvexIQ <noreply@yvexiq.com>",
            "to": email,
            "subject": "Confirma tu correo electrónico — YvexIQ",
            "html": f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#07081a;font-family:'DM Sans',Arial,sans-serif;">
  <div style="max-width:560px;margin:40px auto;padding:40px;background:#0d0f28;border:1px solid rgba(255,255,255,0.08);border-radius:20px;">
    <div style="text-align:center;margin-bottom:32px;">
      <img src="https://yvexiq.com/yvexiq_256.png" width="56" height="56" style="border-radius:14px;" alt="YvexIQ">
    </div>
    <h1 style="color:#f5f3ff;font-size:24px;font-weight:700;margin:0 0 12px;text-align:center;">Confirma tu correo electrónico</h1>
    <p style="color:rgba(245,243,255,0.55);font-size:15px;line-height:1.7;margin:0 0 32px;text-align:center;">
      Gracias por registrarte en YvexIQ. Haz clic en el botón para confirmar tu correo y asegurar tu cuenta.
    </p>
    <div style="text-align:center;margin-bottom:32px;">
      <a href="{enlace}" style="display:inline-block;background:linear-gradient(135deg,#7c22d4,#d946ef);color:white;text-decoration:none;padding:14px 36px;border-radius:12px;font-size:15px;font-weight:600;">
        Confirmar correo electrónico
      </a>
    </div>
    <p style="color:rgba(245,243,255,0.35);font-size:13px;line-height:1.6;text-align:center;margin:0 0 8px;">
      Este enlace expira en 7 días. Si no creaste esta cuenta, ignora este mensaje.
    </p>
    <p style="color:rgba(245,243,255,0.25);font-size:12px;text-align:center;margin:0;">
      Si el botón no funciona, copia este enlace: <a href="{enlace}" style="color:#a855f7;">{enlace}</a>
    </p>
  </div>
</body>
</html>
            """
        })
        return True
    except Exception as e:
        print(f"Error enviando email: {e}")
        return False

def enviar_email_contacto(nombre: str, email: str, asunto: str, plan: str, mensaje: str):
    try:
        resend.Emails.send({
            "from": "YvexIQ Contacto <noreply@yvexiq.com>",
            "to": "contacto@yvexiq.com",
            "reply_to": email,
            "subject": f"[Contacto] {asunto} — {nombre}",
            "html": f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#07081a;font-family:Arial,sans-serif;">
  <div style="max-width:560px;margin:40px auto;padding:40px;background:#0d0f28;border:1px solid rgba(255,255,255,0.08);border-radius:20px;">
    <div style="text-align:center;margin-bottom:24px;">
      <img src="https://yvexiq.com/yvexiq_256.png" width="48" height="48" style="border-radius:12px;" alt="YvexIQ">
    </div>
    <h2 style="color:#f5f3ff;font-size:20px;margin:0 0 20px;">Nuevo mensaje de contacto</h2>
    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="color:rgba(245,243,255,0.5);font-size:13px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);">Nombre</td><td style="color:#f5f3ff;font-size:14px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);">{nombre}</td></tr>
      <tr><td style="color:rgba(245,243,255,0.5);font-size:13px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);">Email</td><td style="color:#a855f7;font-size:14px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);"><a href="mailto:{email}" style="color:#a855f7;">{email}</a></td></tr>
      <tr><td style="color:rgba(245,243,255,0.5);font-size:13px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);">Asunto</td><td style="color:#f5f3ff;font-size:14px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);">{asunto}</td></tr>
      <tr><td style="color:rgba(245,243,255,0.5);font-size:13px;padding:8px 0;">Plan</td><td style="color:#f5f3ff;font-size:14px;padding:8px 0;">{plan if plan else 'Sin cuenta'}</td></tr>
    </table>
    <div style="margin-top:24px;padding:16px;background:rgba(255,255,255,0.04);border-radius:12px;">
      <p style="color:rgba(245,243,255,0.5);font-size:12px;margin:0 0 8px;">Mensaje:</p>
      <p style="color:#f5f3ff;font-size:14px;line-height:1.7;margin:0;">{mensaje}</p>
    </div>
    <p style="color:rgba(245,243,255,0.3);font-size:12px;margin-top:24px;text-align:center;">
      Responde directamente a este email para contactar con {nombre}
    </p>
  </div>
</body>
</html>
            """
        })
        return True
    except Exception as e:
        print(f"Error enviando email de contacto: {e}")
        return False
