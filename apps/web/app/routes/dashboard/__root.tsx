import { Outlet, createFileRoute } from '@tanstack/react-router'

function DashboardLayout() {
  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-white border-r border-gray-200 p-4">
        <nav className="space-y-2">
          <a href="/dashboard" className="block px-4 py-2 rounded hover:bg-gray-100">
            Dashboard
          </a>
          <a href="/dashboard/collections" className="block px-4 py-2 rounded hover:bg-gray-100">
            Collections
          </a>
          <a href="/dashboard/chat" className="block px-4 py-2 rounded hover:bg-gray-100">
            New Chat
          </a>
        </nav>
      </aside>
      <main className="flex-1 p-8">
        <Outlet />
      </main>
    </div>
  )
}

export const Route = createFileRoute('/dashboard')({
  component: DashboardLayout,
})