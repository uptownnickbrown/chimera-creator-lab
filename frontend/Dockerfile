# Dev-friendly image: the Vite dev server with HMR, source mounted by compose.
# Swap for a multi-stage nginx build (Agora's frontend/Dockerfile) at deploy time.
FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
