import { createStartApp } from "@tanstack/react-start";
import { defineConfig } from "vinxi";

var app_config_default = createStartApp({
  ssr: false,
  future: {
    v3_fetcherPersist: true,
    v3_relativeSsrPath: true,
    v3_throwAbortReason: true,
    v3_singleFetch: true,
    v3_lazyRouteDiscovery: true
  }
});

var config = defineConfig({
  routeglobs: ["app/routes/**/*.{ts,tsx}"],
  serverBuildDir: "./dist/server",
  publicDir: "./public",
  staticDir: "./public",
  output: "static",
  server: {
    preset: "vercel"
  }
});

export {
  config,
  app_config_default as default
};