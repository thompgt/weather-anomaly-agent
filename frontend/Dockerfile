FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

# VITE_API_BASE_URL is passed in by infra/docker-compose.yml.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
