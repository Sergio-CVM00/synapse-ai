import { createFileRoute } from '@tanstack/react-router'
import { Link } from '@tanstack/react-router'

function DashboardIndex() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link
          to="/dashboard/collections"
          className="p-6 bg-white rounded-lg border border-gray-200 hover:border-blue-500 transition-colors"
        >
          <h2 className="text-lg font-semibold mb-2">Collections</h2>
          <p className="text-gray-600">Manage your knowledge sources</p>
        </Link>
        <Link
          to="/dashboard/chat"
          className="p-6 bg-white rounded-lg border border-gray-200 hover:border-blue-500 transition-colors"
        >
          <h2 className="text-lg font-semibold mb-2">New Chat</h2>
          <p className="text-gray-600">Start a new conversation</p>
        </Link>
      </div>
    </div>
  )
}

export const Route = createFileRoute('/dashboard/')({
  component: DashboardIndex,
})