db = db.getSiblingDB("sesamekiller_compass");

db.createCollection("chatmessages");
db.chatmessages.createIndex({ sessionId: 1, createdAt: 1 });
db.chatmessages.createIndex({ role: 1 });
