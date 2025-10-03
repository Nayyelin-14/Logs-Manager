// workers/emailWorker.ts
import { Worker, Job } from "bullmq";
import { redisConnection } from "../../config/redisClient";
import { sendAlertEmail, sendOTPEmail } from "../../actions/emailAction";

// Create a worker that listens to the "otp_email" queue
const emailWorker = new Worker(
  "email-Queue",
  async (job: Job) => {
    // job.data should contain { email, otpCode }
    console.log(job);
    if (job.name === "OtpEmail") {
      const { email, otpCode } = job.data;
      console.log(`📤 Sending OTP email to ${email} with code ${otpCode}`);

      const result = await sendOTPEmail(email, otpCode);

      if (!result.isSuccess) {
        throw new Error(result.message); // Mark the job as failed in BullMQ
      }

      return result;
    } else if (job.name === "AlertEmail") {
      const { email, username, tenant, title, description, severity } =
        job.data;
      console.log(
        `📤 Sending an alert mail to ${username} who belongs to ${tenant}`
      );

      const result = await sendAlertEmail(
        email,
        username,
        tenant,
        title,
        description,
        severity
      );

      if (!result.isSuccess) {
        throw new Error(result.message); // Mark the job as failed in BullMQ
      }

      return result;
    }
  },
  {
    connection: redisConnection,
    concurrency: 5, // optional: process up to 5 jobs in parallel
  }
);

// Event listeners
emailWorker.on("completed", (job: Job) => {
  console.log(`Job completed: ${job.id}`);
});

emailWorker.on("failed", (job, err) => {
  if (job) {
    console.error(`Job ${job.id} failed: ${err.message}`);
  } else {
    console.error(`Job failed, but job is undefined: ${err.message}`);
  }
});

console.log("🚀 Email worker is running...");
