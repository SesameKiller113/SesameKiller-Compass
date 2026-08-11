import cors from "cors";
import express, { type NextFunction, type Request, type Response } from "express";
import morgan from "morgan";

import { connectMongo } from "./db/mongo.js";
import { env } from "./env.js";
import { mountGraphql } from "./graphql.js";
import chatRouter from "./routes/chat.js";
import { RagServiceError } from "./services/ragClient.js";

async function bootstrap() {
  await connectMongo(env.mongoUri);

  const app = express();
  app.use(cors());
  app.use(express.json({ limit: "1mb" }));
  app.use(morgan("dev"));

  app.use("/api", chatRouter);
  await mountGraphql(app);

  app.use((error: unknown, _req: Request, res: Response, _next: NextFunction) => {
    const message = error instanceof Error ? error.message : "Unexpected API error";
    const status =
      error instanceof RagServiceError
        ? error.status
        : message.includes("required") || message.includes("validation")
          ? 400
          : 500;
    res.status(status).json({ error: message });
  });

  app.listen(env.port, () => {
    console.log(`API listening on http://localhost:${env.port}`);
  });
}

bootstrap().catch((error) => {
  console.error("API failed to start", error);
  process.exit(1);
});
