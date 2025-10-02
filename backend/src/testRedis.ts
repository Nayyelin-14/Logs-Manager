import { redisConnection } from "./config/redisClient";
import { OtpEmailQueue } from "./utils/queueHelper";

async function testRedis() {
  try {
    console.log("🔄 Testing Redis...");

    await redisConnection.set("foo", "bar");
    console.log("✅ Set foo = bar");

    const value = await redisConnection.get("foo");
    console.log("✅ Get foo =", value);

    await redisConnection.del("foo");
    console.log("✅ Deleted foo");

    console.log("✅ Redis test completed");
  } catch (err) {
    console.error("❌ Redis test failed:", err);
  }
}

async function testEmail() {
  try {
    const job = await OtpEmailQueue({
      email: "thisisnayyelin1234@gmail.com",
      otp: 123456,
      otpId: 999,
    });
    console.log("Job added:", job.id);
  } catch (err) {
    console.error("❌ Failed to add email job:", err);
  }
}

(async () => {
  await testRedis();
  await testEmail();

  console.log("🚀 Test finished, keep worker running to process jobs");
})();
