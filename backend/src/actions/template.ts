// OtpEmail.js
export function otpEmailHtml(username: string, otpCode: number) {
  return `
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Email Verification</title>
    <style>
      body {
        background-color: #f9f9f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        color: #333;
        margin: 0;
        padding: 0;
      }
      .container {
        max-width: 480px;
        margin: 0 auto;
        padding: 20px;
        background-color: #fff;
        border-radius: 8px;
        border: 1px solid #ddd;
      }
      .otp {
        display: inline-block;
        font-size: 24px;
        font-weight: bold;
        color: #28a745;
        padding: 12px 24px;
        margin: 16px 0;
        border: 1px dashed #28a745;
        border-radius: 6px;
        letter-spacing: 2px;
      }
      a.button {
        display: inline-block;
        padding: 12px 24px;
        background-color: #28a745;
        color: #fff !important;
        text-decoration: none;
        border-radius: 6px;
        font-size: 16px;
      }
      p {
        line-height: 1.5;
        font-size: 14px;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <p>Hello <strong>${username}</strong>,</p>
      <p>Use the OTP code below to verify your email address. It is valid for 5 minutes:</p>
      <div class="otp">${otpCode}</div>
      <p>If you did not request this, please ignore this email.</p>
      <p>Happy learning!<br/>Your App Team</p>
    </div>
  </body>
</html>
  `;
}
