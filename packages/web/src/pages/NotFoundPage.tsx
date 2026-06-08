import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20">
      <h1 className="text-3xl font-semibold text-foreground">404 — Page not found</h1>
      <Link to="/" className="text-sm text-primary underline-offset-4 hover:underline">
        Back to Dashboard
      </Link>
    </div>
  )
}
