import "dotenv/config";

export const env = {
  port: Number(process.env.PORT ?? 3001),
  mongoUri: process.env.MONGO_URI ?? "mongodb://localhost:27017/sesamekiller_compass",
  ragServiceUrl: process.env.RAG_SERVICE_URL ?? "http://localhost:5001",
  jwtSecret: process.env.JWT_SECRET ?? "local-development-secret"
};
