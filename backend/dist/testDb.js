"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const pg_1 = __importDefault(require("pg"));
const dotenv_1 = __importDefault(require("dotenv"));
dotenv_1.default.config();
const { Client } = pg_1.default;
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
    }
    catch (err) {
        console.error("Connection failed:", err.message);
    }
    finally {
        await client.end();
    }
}
test();
//# sourceMappingURL=testDb.js.map