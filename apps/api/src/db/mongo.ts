import mongoose, { Schema } from "mongoose";

export type ChatRole = "user" | "assistant";

export interface ChatMessageRecord {
  sessionId: string;
  role: ChatRole;
  content: string;
  retrievalTrace?: unknown;
  createdAt: Date;
  updatedAt: Date;
}

const ChatMessageSchema = new Schema<ChatMessageRecord>(
  {
    sessionId: { type: String, required: true, index: true },
    role: { type: String, enum: ["user", "assistant"], required: true },
    content: { type: String, required: true },
    retrievalTrace: { type: Schema.Types.Mixed }
  },
  { timestamps: true }
);

ChatMessageSchema.index({ sessionId: 1, createdAt: 1 });

export const ChatMessage =
  mongoose.models.ChatMessage ?? mongoose.model<ChatMessageRecord>("ChatMessage", ChatMessageSchema);

export async function connectMongo(uri: string) {
  mongoose.set("strictQuery", true);
  await mongoose.connect(uri);
}

