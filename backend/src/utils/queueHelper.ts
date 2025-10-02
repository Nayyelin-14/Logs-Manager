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
