# ---------- Base stage ----------
FROM node:22-alpine AS base
WORKDIR /usr/local/app
COPY package*.json ./

# ---------- Prod stage ----------
FROM base AS prod
ENV NODE_ENV=production

RUN npm install
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
