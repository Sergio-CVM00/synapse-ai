import { createServerFn } from '@tanstack/react-start'

export const sendChatMessage = createServerFn({ method: 'POST' })
  .validator(
    (data: {
      message: string
      collectionIds: string[]
      conversationId?: string
    }) => data
  )
  .handler(async ({ data }) => {
    const agentUrl = process.env.AGENT_URL || 'http://localhost:8000'
    
    const response = await fetch(`${agentUrl}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: data.message,
        collection_ids: data.collectionIds,
        conversation_id: data.conversationId,
      }),
    })

    if (!response.ok) {
      throw new Error(`Agent request failed: ${response.statusText}`)
    }

    return { streamUrl: `${agentUrl}/chat/stream` }
  })