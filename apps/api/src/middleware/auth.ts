import type { NextFunction, Request, Response } from "express";
import jwt from "jsonwebtoken";

import { env } from "../env.js";

declare global {
  namespace Express {
    interface Request {
      user?: {
        id: string;
        mode: "anonymous" | "jwt";
      };
    }
  }
}

export function optionalJwt(req: Request, _res: Response, next: NextFunction) {
  const authHeader = req.header("authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    req.user = { id: "anonymous-user", mode: "anonymous" };
    next();
    return;
  }

  try {
    const token = authHeader.replace("Bearer ", "");
    const decoded = jwt.verify(token, env.jwtSecret) as { sub?: string };
    req.user = { id: decoded.sub ?? "anonymous-user", mode: "jwt" };
  } catch {
    req.user = { id: "anonymous-user", mode: "anonymous" };
  }
  next();
}
