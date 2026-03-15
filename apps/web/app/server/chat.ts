import { createServerFn } from '@tanstack/react-start'
import { z } from 'zod'

const ChatMessageData = z.object({
  message: z.string().min(1),
  collectionIds: z.array(z.string()).min(1),
  conversationId: z.string().optional(),
})

export const sendChatMessage = createServerFn({ method: 'POST' })
  .handler(async ({ data }) => {
    const validated = ChatMessageData.parse(data)
    const agentUrl = process.env.AGENT_URL || 'http://localhost:8000'
    
    const response = await fetch(`${agentUrl}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: validated.message,
        collection_ids: validated.collectionIds,
        conversation_id: validated.conversationId,
      }),
    })

    if (!response.ok) {
      throw new Error(`Agent request failed: ${response.statusText}`)
    }

    return { streamUrl: `${agentUrl}/chat/stream` }
  })
