import { createTransport } from "nodemailer";
import dotenv from "dotenv";
import { otpEmailHtml } from "../emailTemplates.ts/OTP-template";
import { alertEmailHtml } from "../emailTemplates.ts/Alert-template";
dotenv.config();

export async function sendOTPEmail(email: string, otpCode: number) {
  try {
    const transporter = createTransport({
      service: "gmail",
      auth: {
        user: process.env.GMAIL_USER,
        pass: process.env.GMAIL_PASS,
      },
    });

    const subject = "Verify One Time Password";

    const message = otpEmailHtml(email, otpCode);

    await transporter.sendMail({
      from: process.env.GMAIL_USER,
      to: email,
      subject,
      html: message,
    });

    console.log("Verification email sent successfully!");
    return {
      isSuccess: true,
      message: "Verification email sent successfully.",
    };
  } catch (error) {
    console.error("Error sending verification email:", error);
    return { isSuccess: false, message: "Failed to send verification email." };
  }
}

export async function sendAlertEmail(
  email: string,
  username: string,
  tenant: string,
  title: string,
  description: string,
  severity: string
) {
  try {
    const transporter = createTransport({
      service: "gmail",
      auth: {
        user: process.env.GMAIL_USER,
        pass: process.env.GMAIL_PASS,
      },
    });

    const subject = `[ALERT] ${title} - Severity: ${severity} at ${tenant}`;

    const message = alertEmailHtml(username, title, description, severity);

    await transporter.sendMail({
      from: process.env.GMAIL_USER,
      to: email,
      subject,
      html: message,
    });

    console.log("Alert email sent successfully!");
    return {
      isSuccess: true,
      message: "Alert email sent successfully.",
    };
  } catch (error) {
    console.error("Error sending Alert email:", error);
    return { isSuccess: false, message: "Failed to send Alert email." };
  }
}
