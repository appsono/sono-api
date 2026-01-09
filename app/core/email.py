import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def send_password_reset_email(email: str, reset_token: str, username: str) -> bool:
    """
    send password reset email with token

    args:
        email: user email address
        reset_token: password reset token
        username: user username

    returns:
        bool: true => email sent, false otherwise
    """
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME:
        logger.error("SMTP not configured")
        return False

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    
    msg = MIMEMultipart('alternative')
    msg['From'] = settings.SMTP_FROM
    msg['To'] = email
    msg['Subject'] = "Password Reset Request - Sono"
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background-color: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            padding: 40px 32px;
            text-align: center;
        }}
        .logo {{
            width: 48px;
            height: 48px;
            margin: 0 auto 16px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 600;
            color: #ffffff;
            letter-spacing: 1px;
        }}
        .content {{
            padding: 40px 32px;
            color: #333333;
            line-height: 1.6;
        }}
        .greeting {{
            font-size: 18px;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 20px;
        }}
        .message {{
            font-size: 15px;
            color: #555555;
            margin-bottom: 24px;
        }}
        .highlight {{
            background-color: #f8f9fa;
            border-left: 4px solid #FF4893;
            padding: 16px;
            margin: 24px 0;
            border-radius: 4px;
        }}
        .button-container {{
            text-align: center;
            margin: 32px 0;
        }}
        .reset-button {{
            display: inline-block;
            background-color: #FF4893;
            color: #ffffff !important;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 15px;
            transition: background-color 0.3s ease;
        }}
        .reset-button:hover {{
            background-color: #E93B82;
        }}
        .token-box {{
            background-color: #f8f9fa;
            border: 1px solid #e5e5e5;
            padding: 12px;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            word-break: break-all;
            color: #333333;
            margin: 16px 0;
        }}
        .warning {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 16px;
            margin: 24px 0;
            border-radius: 4px;
            font-size: 14px;
            color: #856404;
        }}
        .signature {{
            margin-top: 32px;
            font-size: 15px;
            color: #333333;
            font-weight: 500;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 24px 32px;
            text-align: center;
            border-top: 1px solid #e5e5e5;
        }}
        .footer-links {{
            margin-bottom: 12px;
        }}
        .footer-links a {{
            color: #666666;
            text-decoration: none;
            font-size: 13px;
            margin: 0 12px;
        }}
        .footer-links a:hover {{
            color: #1a1a1a;
        }}
        .footer-text {{
            font-size: 12px;
            color: #999999;
            margin-top: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <svg width="250" xmlns="http://www.w3.org/2000/svg" height="250" class="logo" viewBox="0 0 250 250" xmlns:xlink="http://www.w3.org/1999/xlink" fill="none" version="1.1"><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d18" rx="0" ry="0"><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d19"><g class="fills" id="fills-51d457f2-f03e-8034-8006-09a04a8d8d19"><rect rx="0" ry="0" x="0" y="0" transform="matrix(1.000000, 0.000000, 0.000000, 1.000000, 0.000000, 0.000000)" width="250" height="250" style="fill: rgb(255, 72, 147); fill-opacity: 0;"/></g></g><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d1a"><g class="fills" id="fills-51d457f2-f03e-8034-8006-09a04a8d8d1a"><ellipse cx="125" cy="125" rx="125" ry="125" transform="matrix(1.000000, 0.000000, 0.000000, 1.000000, 0.000000, 0.000000)" style="fill: rgb(255, 72, 147); fill-opacity: 0;"/></g></g><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d1b" rx="0" ry="0"><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d1c" rx="0" ry="0" style="display: none;"><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d1e"><g class="fills" id="fills-51d457f2-f03e-8034-8006-09a04a8d8d1e"><ellipse cx="92.22197697703723" cy="151.2031939778688" rx="45" ry="44.99999999999994" transform="matrix(0.866025, 0.500000, -0.500000, 0.866025, 87.956999, -25.853602)" style="fill: rgb(233, 59, 130); fill-opacity: 1;"/></g></g><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d1f"><g class="fills" id="fills-51d457f2-f03e-8034-8006-09a04a8d8d1f"><path d="M86.96012595025832,95.76442841485016 h116.00000000000011 a22.999999999999886,22.999999999999886 0 0 1 22.999999999999886,22.999999999999886 v0 a0,0 0 0 1 0,0 h-139 a0,0 0 0 1 0,0 v-22.999999999999886 a0,0 0 0 1 0,0 z" x="86.96012595025832" y="95.76442841485016" transform="matrix(0.500000, -0.866025, 0.866025, 0.500000, -14.663657, 189.130658)" width="139" height="22.999999999999886" style="fill: rgb(233, 59, 130); fill-opacity: 1;"/></g></g><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d20"><g class="fills" id="fills-51d457f2-f03e-8034-8006-09a04a8d8d20"><path d="M186.18500000000017,61.101212042215025 h37.13000000000011 a0,0 0 0 1 0,0 v11.934999999999718 a18.565000000000055,18.565000000000055 0 0 1 -18.565000000000055,18.565000000000055 h0 a18.565000000000055,18.565000000000055 0 0 1 -18.565000000000055,-18.565000000000055 v-11.934999999999718 a0,0 0 0 1 0,0 z" x="186.18500000000017" y="61.101212042215025" transform="matrix(0.501003, -0.865445, 0.865445, 0.501003, 36.091804, 215.298983)" width="37.13000000000011" height="30.499999999999773" style="fill: rgb(233, 59, 130); fill-opacity: 1;"/></g></g></g><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d1d" rx="0" ry="0"><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d21"><g class="fills" id="fills-51d457f2-f03e-8034-8006-09a04a8d8d21"><ellipse cx="88.22197697703723" cy="149.2031939778688" rx="45" ry="44.99999999999994" transform="matrix(0.866025, 0.500000, -0.500000, 0.866025, 86.421101, -24.121551)" style="fill: rgb(255, 255, 255); fill-opacity: 1;"/></g></g><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d22"><g class="fills" id="fills-51d457f2-f03e-8034-8006-09a04a8d8d22"><path d="M82.96012595025832,93.76442841485016 h116.00000000000011 a22.999999999999886,22.999999999999886 0 0 1 22.999999999999886,22.999999999999886 v0 a0,0 0 0 1 0,0 h-139 a0,0 0 0 1 0,0 v-22.999999999999886 a0,0 0 0 1 0,0 z" x="82.96012595025832" y="93.76442841485016" transform="matrix(0.500000, -0.866025, 0.866025, 0.500000, -14.931606, 184.666556)" width="139" height="22.999999999999886" style="fill: rgb(255, 255, 255); fill-opacity: 1;"/></g></g><g id="shape-51d457f2-f03e-8034-8006-09a04a8d8d23"><g class="fills" id="fills-51d457f2-f03e-8034-8006-09a04a8d8d23"><path d="M182.18500000000017,59.101212042215025 h37.13000000000011 a0,0 0 0 1 0,0 v11.934999999999718 a18.565000000000055,18.565000000000055 0 0 1 -18.565000000000055,18.565000000000055 h0 a18.565000000000055,18.565000000000055 0 0 1 -18.565000000000055,-18.565000000000055 v-11.934999999999718 a0,0 0 0 1 0,0 z" x="182.18500000000017" y="59.101212042215025" transform="matrix(0.501003, -0.865445, 0.865445, 0.501003, 35.826708, 210.839207)" width="37.13000000000011" height="30.499999999999773" style="fill: rgb(255, 255, 255); fill-opacity: 1;"/></g></g></g></g></g></svg>
            <h1>Sono</h1>
        </div>
        
        <div class="content">
            <div class="greeting">Hi {username},</div>
            
            <div class="message">
                We received a request to reset your password for your Sono account. If you didn't make this request, you can safely ignore this email.
            </div>
            
            <div class="highlight">
                To reset your password, click the button below. This link will expire in <strong>1 hour</strong>.
            </div>
            
            <div class="button-container">
                <a href="{reset_url}" class="reset-button">Reset Password</a>
            </div>
            
            <div class="message">
                Or copy and paste this link into your browser:
            </div>
            
            <div class="token-box">
                {reset_url}
            </div>
            
            <div class="warning">
                <strong>⚠️ Security Notice:</strong> Never share this link with anyone. Sono staff will never ask you for this link or your password.
            </div>
            
            <div class="message">
                If you didn't request a password reset, please ignore this email or contact us if you have concerns about your account security.
            </div>
            
            <div class="signature">
                Best regards,<br>
                The Sono Team
            </div>
        </div>
        
        <div class="footer">
            <div class="footer-links">
                <a href="https://sono.wtf/terms">Terms</a>
                <span style="color: #e5e5e5;">|</span>
                <a href="https://sono.wtf/privacy">Privacy</a>
                <span style="color: #e5e5e5;">|</span>
                <a href="https://sono.wtf">sono.wtf</a>
            </div>
            <div class="footer-text">
                This email was sent to {email}. If you received this in error, please ignore it.
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    msg.attach(MIMEText(html_body, 'html'))
    
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Password reset email sent successfully to {email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        return False