import { createRoot } from 'react-dom/client'
import { StartClient } from '@tanstack/react-start/client'
import { RouterProvider } from '@tanstack/react-router'
import { createRouter } from './router'

const router = createRouter()

createRoot(document.getElementById('app')!).render(
  <RouterProvider router={router} />
)

if (import.meta.hot) {
  import.meta.hot.dispose(() => router.dispose())
}