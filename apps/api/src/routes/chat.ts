import { Router } from "express";
import { z } from "zod";

import { ChatMessage } from "../db/mongo.js";
import { optionalJwt } from "../middleware/auth.js";
import { getAirportCatalog, queryRagService } from "../services/ragClient.js";
import { normalizeUserMessage, resolveSessionId } from "../services/session.js";

const router = Router();

const ChatRequestSchema = z.object({
  sessionId: z.unknown().optional(),
  message: z.string().min(1).max(2000)
});

router.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "api" });
});

router.get("/airports", async (_req, res, next) => {
  try {
    res.json({ airports: await getAirportCatalog() });
  } catch (error) {
    next(error);
  }
});

router.get("/sessions/:sessionId/messages", optionalJwt, async (req, res, next) => {
  try {
    const messages = await ChatMessage.find({ sessionId: req.params.sessionId })
      .sort({ createdAt: 1 })
      .lean();
    res.json({ sessionId: req.params.sessionId, messages });
  } catch (error) {
    next(error);
  }
});

router.post("/chat", optionalJwt, async (req, res, next) => {
  try {
    const parsed = ChatRequestSchema.parse(req.body);
    const sessionId = resolveSessionId(parsed.sessionId);
    const message = normalizeUserMessage(parsed.message);

    const history = await ChatMessage.find({ sessionId })
      .sort({ createdAt: 1 })
      .limit(12)
      .lean();

    await ChatMessage.create({ sessionId, role: "user", content: message });

    const ragResponse = await queryRagService({
      question: message,
      sessionId,
      chatHistory: history.map((item) => ({ role: item.role, content: item.content }))
    });

    await ChatMessage.create({
      sessionId,
      role: "assistant",
      content: ragResponse.answer,
      retrievalTrace: ragResponse.retrieval
    });

    res.status(201).json({
      sessionId,
      user: req.user,
      answer: ragResponse.answer,
      mode: ragResponse.mode,
      retrieval: ragResponse.retrieval
    });
  } catch (error) {
    next(error);
  }
});

export default router;
