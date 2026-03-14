import { createAPIFileRoute } from '@tanstack/react-start/api'

export const Route = createAPIFileRoute('/api/chat/stream')({
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
})