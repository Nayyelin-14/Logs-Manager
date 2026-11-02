import "dotenv/config";
import { app } from "./app";
import { connectWithRetry } from "./config/PrismaClient";
import { startSyslogListeners } from "./ingest";

const PORT = process.env.PORT || 4500;

(async () => {
  await connectWithRetry();
  app.listen(PORT, () => console.log(`server is running at ${PORT}`));
  startSyslogListeners();
})();
