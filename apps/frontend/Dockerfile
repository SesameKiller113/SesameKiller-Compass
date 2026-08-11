FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY index.html tsconfig.json tsconfig.node.json vite.config.ts postcss.config.js tailwind.config.ts ./
COPY src ./src

EXPOSE 5173

CMD ["npm", "run", "dev"]

