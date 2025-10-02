import pkg from "pg";
import dotenv from "dotenv";

dotenv.config();
const { Client } = pkg;
console.log(process.env.DATABASE_URL);
const client = new Client({
  connectionString: process.env.DATABASE_URL,
  ssl: {
    rejectUnauthorized: false,
  },
});

async function test() {
  try {
    await client.connect();
    console.log("Connected to database!");
    const res = await client.query("SELECT NOW()");
    console.log("Server time:", res.rows[0]);
  } catch (err: any) {
    console.error("Connection failed:", err.message);
  } finally {
    await client.end();
  }
}

test();
