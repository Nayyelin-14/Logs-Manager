import emailQueue from "../jobs/queues/emailQueue";

export const OtpEmailQueue = async (payload: {
  email: string;
  otp: number;
  otpId: number;
}) => {
  return await emailQueue.add(
    "OtpEmail", // job name
    {
      // job data
      email: payload.email,
      otpCode: payload.otp,
    },
    {
      // job options
      jobId: `OTP:${payload.otpId}:email`,
      attempts: 3,
      backoff: { type: "exponential", delay: 1000 },
      removeOnComplete: true,
      removeOnFail: 1000,
    }
  );
};

export const AlertEmailQueue = async (payload: {
  email: string;
  username: string;
  tenant: string;
  title: string;
  description: string;
  severity: string;
}) => {
  return await emailQueue.add(
    "AlertEmail",
    {
      email: payload.email,
      username: payload.username,
      tenant: payload.tenant,
      title: payload.title,
      description: payload.description,
      severity: payload.severity,
    },
    {
      jobId: `ALERT:${payload.tenant}:${Date.now()}`,
      attempts: 3,
      backoff: { type: "exponential", delay: 1000 },
      removeOnComplete: true,
      removeOnFail: 1000,
    }
  );
};
