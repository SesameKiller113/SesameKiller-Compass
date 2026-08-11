import { createAsyncThunk, createSlice, type PayloadAction } from "@reduxjs/toolkit";

import { sendChatMessage, type ChatMessage, type ChatResponse } from "../lib/api";

interface ChatState {
  sessionId?: string;
  messages: ChatMessage[];
  status: "idle" | "loading" | "failed";
  error?: string;
  mode?: ChatResponse["mode"];
  retrieval?: ChatResponse["retrieval"];
}

const initialState: ChatState = {
  messages: [
    {
      id: "welcome",
      role: "assistant",
      content:
        "Ask about a seeded airport like RWI, HVA, or BHI. I will run semantic retrieval, Cypher graph retrieval, and answer generation."
    }
  ],
  status: "idle"
};

export const askQuestion = createAsyncThunk<
  ChatResponse,
  string,
  { state: { chat: ChatState }; rejectValue: string }
>("chat/askQuestion", async (message, thunkApi) => {
  try {
    const sessionId = thunkApi.getState().chat.sessionId;
    return await sendChatMessage(message, sessionId);
  } catch (error) {
    return thunkApi.rejectWithValue(error instanceof Error ? error.message : "Chat request failed");
  }
});

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    clearChat(state) {
      state.sessionId = undefined;
      state.messages = [...initialState.messages];
      state.status = "idle";
      state.error = undefined;
      state.retrieval = undefined;
      state.mode = undefined;
    },
    addUserMessage(state, action: PayloadAction<string>) {
      state.messages.push({
        id: crypto.randomUUID(),
        role: "user",
        content: action.payload
      });
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(askQuestion.pending, (state) => {
        state.status = "loading";
        state.error = undefined;
      })
      .addCase(askQuestion.fulfilled, (state, action) => {
        state.status = "idle";
        state.sessionId = action.payload.sessionId;
        state.mode = action.payload.mode;
        state.retrieval = action.payload.retrieval;
        state.messages.push({
          id: crypto.randomUUID(),
          role: "assistant",
          content: action.payload.answer
        });
      })
      .addCase(askQuestion.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.payload ?? "Chat request failed";
        state.messages.push({
          id: crypto.randomUUID(),
          role: "assistant",
          content: `The API request failed: ${state.error}`
        });
      });
  }
});

export const { addUserMessage, clearChat } = chatSlice.actions;
export default chatSlice.reducer;
