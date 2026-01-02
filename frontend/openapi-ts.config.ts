import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  // Fetch from running backend (localhost:3001/openapi.json during dev)
  // For CI/CD, generate openapi.json from backend first
  input: process.env.OPENAPI_URL || "http://localhost:3001/openapi.json",
  output: "src/lib/api-client",
  plugins: ["@hey-api/client-fetch"],
});
