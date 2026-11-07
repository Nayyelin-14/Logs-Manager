"""
Email Templates

HTML and text email templates for OTP and alert notifications.
"""

def render_otp_email(email: str, otp_code: int) -> str:
    """Render OTP verification email HTML."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify OTP</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9f9f9; margin: 0; padding: 20px;">
    <div style="max-width: 480px; margin: 0 auto; background-color: #fff; border-radius: 8px; border: 1px solid #ddd; padding: 20px;">
        <h2 style="color: #333; margin-top: 0;">Verify One Time Password</h2>
        <p>Hello <strong>{email}</strong>,</p>
        <p>Your verification code is:</p>
        <div style="text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 4px; color: #0066cc; font-family: monospace;">{otp_code}</span>
        </div>
        <p style="color: #666; font-size: 14px;">This code expires in <strong>2 minutes</strong>.</p>
        <p>If you didn't request this, please ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">Log Manager Security System</p>
    </div>
</body>
</html>
"""


def render_alert_email(username: str, title: str, description: str, severity: str, tenant: str) -> str:
    """Render alert notification email HTML."""
    severity_colors = {
        "low": "#28a745",
        "medium": "#ffc107",
        "high": "#dc3545",
        "critical": "#8B0000",
    }
    color = severity_colors.get(severity.lower(), "#007bff")
    
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alert Notification</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f9f9f9; margin: 0; padding: 20px;">
    <div style="max-width: 480px; margin: 0 auto; background-color: #fff; border-radius: 8px; border: 1px solid #ddd; padding: 20px;">
        <p>Hello <strong>{username}</strong>,</p>
        <p class="severity-badge" style="display: inline-block; padding: 6px 12px; border-radius: 6px; background-color: {color}; color: #fff; font-weight: bold; font-size: 12px; margin-bottom: 16px;">
            {severity.upper()}
        </p>
        <p class="alert-title" style="font-size: 20px; font-weight: bold; color: {color}; margin: 12px 0;">
            {title}
        </p>
        <p class="alert-description" style="font-size: 14px; line-height: 1.5; margin: 8px 0 16px 0;">
            {description}
        </p>
        <p>Tenant: <strong>{tenant}</strong></p>
        <p>Please take the necessary actions if required.</p>
        <p>Best regards,<br/>Your Security Team</p>
    </div>
</body>
</html>
"""


def render_alert_email_text(username: str, title: str, description: str, severity: str, tenant: str) -> str:
    """Render alert notification email plain text."""
    return f"""
Hello {username},

A security alert has been triggered.

Alert: {title}
Severity: {severity.upper()}
Tenant: {tenant}

{description}

Please review this alert in the Log Manager dashboard.

---
Log Manager Security System
"""