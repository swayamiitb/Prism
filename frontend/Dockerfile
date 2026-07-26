# SAAS AI frontend image.
FROM node:20-alpine

WORKDIR /app

# Install deps first for caching.
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
