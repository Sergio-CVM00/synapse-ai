import { createFileRoute } from '@tanstack/react-router'
import { Link } from '@tanstack/react-router'

function CollectionsIndex() {
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Collections</h1>
        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          New Collection
        </button>
      </div>
      <p className="text-gray-600">No collections yet. Create one to get started.</p>
    </div>
  )
}

export const Route = createFileRoute('/dashboard/collections/')({
  component: CollectionsIndex,
})