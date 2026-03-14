import { createFileRoute, Link } from '@tanstack/react-router'

function Index() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">Agentic RAG</h1>
        <p className="text-gray-600 mb-8">Connect knowledge sources and ask questions in natural language</p>
        <div className="space-x-4">
          <Link
            to="/dashboard"
            className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Go to Dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}

export const Route = createFileRoute('/')({
  component: Index,
})