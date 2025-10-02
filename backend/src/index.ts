import dotenv from "dotenv";
import { app } from "./app";
import { connectWithRetry } from "./config/PrismaClient";

dotenv.config();

const PORT = process.env.PORT || 8080;

(async () => {
  await connectWithRetry();
  app.listen(PORT, () => console.log(`server is running at ${PORT}`));
})();
