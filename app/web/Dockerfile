FROM node:20-alpine
WORKDIR /app
COPY app/web/package.json app/web/package-lock.json ./
RUN npm install
COPY app/web/ .
COPY data/laurie-engine /data/laurie-engine
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
