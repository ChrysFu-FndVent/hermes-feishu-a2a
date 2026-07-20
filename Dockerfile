FROM node:20-alpine
WORKDIR /app
COPY package.json README.md LICENSE .env.example ./
COPY src ./src
COPY config ./config
COPY scripts ./scripts
COPY docs ./docs
ENV NODE_ENV=production HOST=0.0.0.0 PORT=8787
EXPOSE 8787
USER node
CMD ["node", "src/cli.js", "serve"]
