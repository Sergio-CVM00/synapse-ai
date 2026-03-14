import { createFileRoute } from '@tanstack/react-router'

function CollectionDetail() {
  const { id } = Route.useParams()
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Collection: {id}</h1>
      <p className="text-gray-600">Collection details coming soon.</p>
    </div>
  )
}

export const Route = createFileRoute('/dashboard/collections/$id')({
  component: CollectionDetail,
})