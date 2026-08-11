import type { Express } from "express";
import { ApolloServer } from "@apollo/server";
import { expressMiddleware } from "@apollo/server/express4";

import { ChatMessage } from "./db/mongo.js";
import { getAirportCatalog } from "./services/ragClient.js";

const typeDefs = `#graphql
  type Health {
    status: String!
    service: String!
  }

  type Message {
    id: ID!
    sessionId: String!
    role: String!
    content: String!
    createdAt: String!
  }

  type AirportSummary {
    code: String!
    name: String!
    city: String!
    terminalCount: Int!
  }

  type Query {
    health: Health!
    messages(sessionId: ID!): [Message!]!
    airports: [AirportSummary!]!
  }
`;

const resolvers = {
  Query: {
    health: () => ({ status: "ok", service: "api-graphql" }),
    messages: async (_parent: unknown, args: { sessionId: string }) => {
      const messages = await ChatMessage.find({ sessionId: args.sessionId })
        .sort({ createdAt: 1 })
        .lean();
      return messages.map((message) => ({
        id: String(message._id),
        sessionId: message.sessionId,
        role: message.role,
        content: message.content,
        createdAt: message.createdAt.toISOString()
      }));
    },
    airports: () => getAirportCatalog()
  }
};

export async function mountGraphql(app: Express) {
  const server = new ApolloServer({ typeDefs, resolvers });
  await server.start();
  app.use("/graphql", expressMiddleware(server));
}

