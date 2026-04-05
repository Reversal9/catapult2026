# ---------- Base stage ----------
FROM node:22-alpine AS base
WORKDIR /usr/local/app
COPY package*.json ./

# ---------- Prod stage ----------
FROM base AS prod
# Set this AFTER npm install if you want to keep devDependencies during build
RUN npm install 
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
