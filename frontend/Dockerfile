# Dev-friendly image: the Vite dev server with HMR, source mounted by compose.
# NOT the production build — prod is the repo-root Dockerfile, which builds this
# app and has FastAPI serve the result on one origin. See docs/DEPLOY.md.
FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
