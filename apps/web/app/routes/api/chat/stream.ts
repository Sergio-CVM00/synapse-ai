import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/api/chat/stream')({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const agentUrl = process.env.AGENT_URL || 'http://localhost:8000'

        const upstream = await fetch(`${agentUrl}/chat/stream`, {
          method: 'POST',
          body: request.body,
          headers: {
            'Content-Type': 'application/json',
          },
        })

        return new Response(upstream.body, {
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            Connection: 'keep-alive',
          },
        })
      },
    },
  },
})
