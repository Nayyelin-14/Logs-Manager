// AlertEmail.ts
export function alertEmailHtml(
  username: string,
  title: string,
  description: string,
  severity: string
) {
  // Define colors based on severity
  const severityColor =
    {
      low: "#28a745",
      medium: "#ffc107",
      high: "#dc3545",
      critical: "#8B0000",
    }[severity.toLowerCase()] || "#007bff"; // default blue

  return `
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Alert Notification</title>
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
      .alert-title {
        font-size: 20px;
        font-weight: bold;
        color: ${severityColor};
        margin: 12px 0;
      }
      .alert-description {
        font-size: 14px;
        line-height: 1.5;
        margin: 8px 0 16px 0;
      }
      .severity-badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 6px;
        background-color: ${severityColor};
        color: #fff;
        font-weight: bold;
        font-size: 12px;
        margin-bottom: 16px;
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
      <p class="severity-badge">${severity.toUpperCase()}</p>
      <p class="alert-title">${title}</p>
      <p class="alert-description">${description}</p>
      <p>Please take the necessary actions if required.</p>
      <p>Best regards,<br/>Your Security Team</p>
    </div>
  </body>
</html>
  `;
}
