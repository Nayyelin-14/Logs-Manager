import dotenv from "dotenv";
dotenv.config();
import { PrismaClient } from "../generated/prisma"; // relative to your file
const prisma = new PrismaClient();

export async function connectWithRetry(retries = 5, delay = 2000) {
  for (let i = 0; i < retries; i++) {
    try {
      await prisma.$connect();
      console.log(" Database connected successfully!");
      return;
    } catch (err) {
      console.warn(` Database connection failed. Retry ${i + 1}/${retries}...`);
      if (i === retries - 1) throw err;
      await new Promise((res) => setTimeout(res, delay));
    }
  }
}
