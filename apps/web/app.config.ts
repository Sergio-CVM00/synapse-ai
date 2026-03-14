import { createStartApp } from '@tanstack/react-start/config'
import { defineConfig } from 'vinxi'

export default createStartApp({
  future: {
    v3_fetcherPersist: true,
    v3_relativeSsrPath: true,
    v3_throwAbortReason: true,
    v3_singleFetch: true,
    v3_lazyRouteDiscovery: true,
  },
})

export const config = defineConfig({
  routeglobs: ['app/routes/**/*.{ts,tsx}'],
  serverBuildDir: './dist/server',
  publicDir: './public',
  staticDir: './public',
  output: 'server',
  server: {
    preset: 'vercel',
  },
})